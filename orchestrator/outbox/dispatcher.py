"""
SYNAPSE Orchestrator — Outbox Dispatcher (Sprint 7, WS-2).

Drains rows from ``audit_outbox`` and publishes each to Kafka, with the
following guarantees:

    * Exactly-once-effect downstream:  Kafka's ``enable.idempotence=true``
      plus the dispatcher's atomic ``status='PENDING' -> 'IN_FLIGHT' ->
      'PUBLISHED'`` transitions ensure that a single audit row is
      published to Kafka *at-least-once*; downstream consumers dedupe by
      ``decision_id`` to make the effect exactly-once.
    * Concurrent-safe:  rows are claimed with ``SELECT ... FOR UPDATE
      SKIP LOCKED`` so multiple dispatcher replicas can run in parallel
      without double-publishing.
    * Backoff under failure:  Full Jitter (ADR-016) computed via
      ``synapse_common.retry.full_jitter_delay``. After ``max_retries``
      attempts the row transitions to ``FAILED`` for human review.
    * Circuit-broken Kafka:  publish goes through a named circuit breaker
      so a Kafka outage cannot make the dispatcher livelock.
    * Graceful shutdown:  the dispatcher exposes ``stop()``; the
      orchestrator lifespan calls it before flushing the producer so any
      in-flight transition completes cleanly.

Invocation:
    dispatcher = OutboxDispatcher(session_factory, producer)
    await dispatcher.start()
    ...
    await dispatcher.stop()
"""

from __future__ import annotations

import asyncio
import contextlib
import json
from typing import TYPE_CHECKING, Any

import structlog
from sqlalchemy import select, text, update
from synapse_common.breakers import BreakerOpenError, get_breaker
from synapse_common.metrics import OUTBOX_DISPATCH_TOTAL, OUTBOX_LAG_SECONDS
from synapse_common.retry import full_jitter_delay

from orchestrator.audit.models import AuditOutboxRow

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
    from synapse_common.kafka_client import SynapseProducer

logger = structlog.get_logger(__name__)

DEFAULT_BATCH_SIZE = 32
DEFAULT_POLL_INTERVAL_SECONDS = 1.0
DEFAULT_MAX_RETRIES = 10
DEFAULT_BASE_BACKOFF_SECONDS = 0.5
DEFAULT_BACKOFF_CAP_SECONDS = 60.0


class OutboxDispatcher:
    """Async background drainer for ``audit_outbox``."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        producer: SynapseProducer,
        *,
        batch_size: int = DEFAULT_BATCH_SIZE,
        poll_interval_seconds: float = DEFAULT_POLL_INTERVAL_SECONDS,
        max_retries: int = DEFAULT_MAX_RETRIES,
        base_backoff_seconds: float = DEFAULT_BASE_BACKOFF_SECONDS,
        backoff_cap_seconds: float = DEFAULT_BACKOFF_CAP_SECONDS,
    ) -> None:
        if batch_size <= 0:
            raise ValueError("batch_size must be > 0")
        if poll_interval_seconds <= 0:
            raise ValueError("poll_interval_seconds must be > 0")
        if max_retries <= 0:
            raise ValueError("max_retries must be > 0")
        self._session_factory = session_factory
        self._producer = producer
        self._batch_size = batch_size
        self._poll_interval = poll_interval_seconds
        self._max_retries = max_retries
        self._base_backoff = base_backoff_seconds
        self._backoff_cap = backoff_cap_seconds
        self._breaker = get_breaker(
            "kafka_outbox_publish",
            fail_max=5,
            reset_timeout=30.0,
            expected_exceptions=(Exception,),
        )
        self._task: asyncio.Task[None] | None = None
        self._stop_event = asyncio.Event()
        self._wakeup_event = asyncio.Event()
        self._published: int = 0
        self._failed: int = 0

    @property
    def published_count(self) -> int:
        return self._published

    @property
    def failed_count(self) -> int:
        return self._failed

    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    def wake(self) -> None:
        """Signal the dispatcher to drain immediately, e.g. after an INSERT."""
        self._wakeup_event.set()

    async def start(self) -> None:
        if self.running:
            return
        self._stop_event.clear()
        self._task = asyncio.create_task(self._run(), name="outbox_dispatcher")
        logger.info("outbox_dispatcher_started", batch_size=self._batch_size)

    async def stop(self, timeout: float = 30.0) -> None:
        if not self.running:
            return
        self._stop_event.set()
        self._wakeup_event.set()
        try:
            await asyncio.wait_for(self._task, timeout=timeout)  # type: ignore[arg-type]
        except TimeoutError:
            logger.warning("outbox_dispatcher_stop_timeout")
            assert self._task is not None
            self._task.cancel()
        logger.info(
            "outbox_dispatcher_stopped",
            published=self._published,
            failed=self._failed,
        )

    async def _run(self) -> None:
        while not self._stop_event.is_set():
            drained = await self._drain_once()
            if drained == 0:
                # Drained nothing: refresh lag gauge so operators can see
                # the oldest unsent row's age even during quiet periods.
                await self._observe_lag()
                # Idle wait: woken by wake() or by the poll interval.
                with contextlib.suppress(TimeoutError):
                    await asyncio.wait_for(
                        self._wakeup_event.wait(),
                        timeout=self._poll_interval,
                    )
                self._wakeup_event.clear()

    async def _observe_lag(self) -> None:
        """Publish the age (in seconds) of the oldest PENDING row.

        Idle-only observation — keeps the lag visible to Prometheus when
        the dispatcher has nothing to do but the queue isn't empty
        (e.g. all PENDING rows are scheduled in the future via Full
        Jitter). When the queue is empty the gauge reports 0.0.
        """
        try:
            async with self._session_factory() as session:
                result = await session.execute(
                    select(AuditOutboxRow.next_attempt_at)
                    .where(AuditOutboxRow.status == "PENDING")
                    .order_by(AuditOutboxRow.next_attempt_at.asc())
                    .limit(1)
                )
                oldest = result.scalar_one_or_none()
                if oldest is None:
                    OUTBOX_LAG_SECONDS.set(0.0)
                    return
                row_q = await session.execute(text("SELECT NOW()"))
                now = row_q.scalar_one()
                lag = max(0.0, (now - oldest).total_seconds())
                OUTBOX_LAG_SECONDS.set(lag)
        except Exception as exc:  # noqa: BLE001
            # Never let the metric path bring the dispatcher down.
            logger.debug("outbox_lag_observation_failed", error=str(exc))

    async def _drain_once(self) -> int:
        """Claim a batch of PENDING rows and dispatch each. Returns count drained."""
        try:
            async with self._session_factory() as session:
                rows = await self._claim_batch(session)
                if not rows:
                    return 0
                await session.commit()
        except Exception as exc:  # noqa: BLE001
            logger.warning("outbox_claim_failed", error=str(exc))
            return 0

        for row in rows:
            await self._dispatch_one(row)
        return len(rows)

    async def _claim_batch(self, session: AsyncSession) -> list[AuditOutboxRow]:
        """Atomically transition up to batch_size PENDING rows to IN_FLIGHT.

        Uses ``FOR UPDATE SKIP LOCKED`` so concurrent dispatchers can each
        carve their own slice of the queue without contention. The
        transition happens inside one transaction; rows that come back
        are guaranteed to be locked-in IN_FLIGHT for this worker.
        """
        # Postgres-specific: SKIP LOCKED requires SELECT-FOR-UPDATE.
        stmt = (
            select(AuditOutboxRow)
            .where(AuditOutboxRow.status == "PENDING")
            .where(AuditOutboxRow.next_attempt_at <= text("NOW()"))
            .order_by(AuditOutboxRow.next_attempt_at)
            .limit(self._batch_size)
            .with_for_update(skip_locked=True)
        )
        result = await session.execute(stmt)
        rows: list[AuditOutboxRow] = list(result.scalars().all())
        if not rows:
            return []
        ids = [r.id for r in rows]
        await session.execute(
            update(AuditOutboxRow)
            .where(AuditOutboxRow.id.in_(ids))
            .values(status="IN_FLIGHT")
        )
        return rows

    async def _dispatch_one(self, row: AuditOutboxRow) -> None:
        try:
            async with self._breaker.guard():
                await self._publish(row)
            await self._mark_published(row)
            self._published += 1
            OUTBOX_DISPATCH_TOTAL.labels(status="PUBLISHED").inc()
        except BreakerOpenError as exc:
            await self._reschedule(row, error=str(exc))
        except Exception as exc:  # noqa: BLE001
            await self._reschedule(row, error=str(exc))

    async def _publish(self, row: AuditOutboxRow) -> None:
        """Run the Kafka produce in a worker thread to keep the loop free.

        The audit row carries the trace headers captured at the moment the
        decision was committed; we replay those exact headers onto the Kafka
        message so the full trace stays joined across the gap between
        Postgres commit and Kafka publish.
        """
        stored_headers: dict[str, str] = dict(row.headers or {})
        # mypy's asyncio.to_thread stub does not propagate the callee's
        # kwargs — the runtime contract is to_thread(func, *args, **kwargs)
        # so this call is correct. Targeted ignore preserves --strict.
        await asyncio.to_thread(
            self._producer.produce,
            topic=row.topic,
            value=row.payload,
            key=row.partition_key,
            headers=stored_headers,  # type: ignore[call-arg]
        )

    async def _mark_published(self, row: AuditOutboxRow) -> None:
        async with self._session_factory() as session:
            await session.execute(
                update(AuditOutboxRow)
                .where(AuditOutboxRow.id == row.id)
                .values(
                    status="PUBLISHED",
                    published_at=text("NOW()"),
                    last_error=None,
                )
            )
            await session.commit()

    async def _reschedule(self, row: AuditOutboxRow, *, error: str) -> None:
        async with self._session_factory() as session:
            new_retries = int(row.retries) + 1
            if new_retries >= self._max_retries:
                await session.execute(
                    update(AuditOutboxRow)
                    .where(AuditOutboxRow.id == row.id)
                    .values(
                        status="FAILED",
                        retries=new_retries,
                        last_error=error,
                    )
                )
                await session.commit()
                self._failed += 1
                OUTBOX_DISPATCH_TOTAL.labels(status="FAILED").inc()
                logger.error(
                    "outbox_row_poison_pill",
                    outbox_id=str(row.id),
                    decision_id=str(row.decision_id),
                    retries=new_retries,
                    error=error,
                )
                return
            delay = full_jitter_delay(
                self._base_backoff, new_retries, cap=self._backoff_cap
            )
            await session.execute(
                text(
                    """
                    UPDATE audit_outbox
                       SET status          = 'PENDING',
                           retries         = :retries,
                           last_error      = :err,
                           next_attempt_at = NOW() + (:delay_seconds || ' seconds')::interval
                     WHERE id = :id
                    """
                ),
                {
                    "retries": new_retries,
                    "err": error,
                    "delay_seconds": delay,
                    "id": row.id,
                },
            )
            await session.commit()
            OUTBOX_DISPATCH_TOTAL.labels(status="RESCHEDULED").inc()
            logger.warning(
                "outbox_row_rescheduled",
                outbox_id=str(row.id),
                decision_id=str(row.decision_id),
                retries=new_retries,
                delay_seconds=round(delay, 2),
                error=error,
            )

    @staticmethod
    def serialise_payload(payload: dict[str, Any]) -> bytes:
        """Helper: deterministic JSON bytes for a payload dict (I-13)."""
        return json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        ).encode("utf-8")
