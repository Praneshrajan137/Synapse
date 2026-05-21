"""
SYNAPSE Outbox Dispatcher (WS-2 §3, ADR-026).

Drains ``audit_outbox`` rows with ``status='PENDING'`` and publishes them
to Kafka via ``synapse_common.kafka_client.SynapseProducer`` (idempotent
producer). On success the row is marked SENT with ``sent_at`` stamped.
On failure the dispatcher increments ``attempts`` and applies Full-Jitter
retry (ADR-016).

The dispatcher is a long-lived asyncio task. It is registered with the
orchestrator's ``Lifespan`` so SIGTERM stops it cleanly without losing
unfinished work — restart picks up whatever was still PENDING.
"""

from __future__ import annotations

import asyncio
import contextlib
import os
import random
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import structlog
from sqlalchemy import select, update
from synapse_common.metrics import OUTBOX_DISPATCH_TOTAL, OUTBOX_LAG_SECONDS

from orchestrator.audit.models import AuditOutboxRow

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
    from synapse_common.kafka_client import SynapseProducer

logger = structlog.get_logger(__name__)


POLL_INTERVAL_S: float = float(os.environ.get("SYNAPSE_OUTBOX_POLL_S", "0.5"))
MAX_ATTEMPTS: int = int(os.environ.get("SYNAPSE_OUTBOX_MAX_ATTEMPTS", "10"))
BATCH_SIZE: int = int(os.environ.get("SYNAPSE_OUTBOX_BATCH_SIZE", "20"))


class OutboxDispatcher:
    """Asyncio task that drains audit_outbox to Kafka."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        producer: SynapseProducer,
        poll_interval_s: float = POLL_INTERVAL_S,
        batch_size: int = BATCH_SIZE,
    ) -> None:
        self._session_factory = session_factory
        self._producer = producer
        self._poll_interval_s = poll_interval_s
        self._batch_size = batch_size
        self._stop_event = asyncio.Event()
        self._task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        if self._task is not None:
            return
        self._stop_event.clear()
        self._task = asyncio.create_task(self._run(), name="outbox_dispatcher")
        logger.info("outbox_dispatcher_started")

    async def stop(self) -> None:
        self._stop_event.set()
        if self._task is None:
            return
        try:
            await asyncio.wait_for(self._task, timeout=10.0)
        except TimeoutError:
            logger.warning("outbox_dispatcher_stop_timeout")
            self._task.cancel()
        except asyncio.CancelledError:
            pass
        finally:
            self._task = None
            logger.info("outbox_dispatcher_stopped")

    async def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                drained = await self._drain_once()
            except Exception as exc:  # noqa: BLE001
                logger.error("outbox_dispatcher_loop_error", error=str(exc))
                drained = 0
            sleep_s = 0.05 if drained == self._batch_size else self._poll_interval_s
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(self._stop_event.wait(), timeout=sleep_s)

    async def _drain_once(self) -> int:
        async with self._session_factory() as session:
            rows = await self._claim_batch(session)
            if not rows:
                await self._update_lag_gauge(session)
                return 0
            for row in rows:
                await self._dispatch_row(session, row)
            await session.commit()
        return len(rows)

    async def _claim_batch(self, session: AsyncSession) -> list[AuditOutboxRow]:
        stmt = (
            select(AuditOutboxRow)
            .where(AuditOutboxRow.status == "PENDING")
            .order_by(AuditOutboxRow.created_at.asc())
            .limit(self._batch_size)
            .with_for_update(skip_locked=True)
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def _dispatch_row(self, session: AsyncSession, row: AuditOutboxRow) -> None:
        try:
            self._producer.produce(
                topic=row.topic,
                value=row.payload,
                key=row.message_key,
            )
            self._producer.flush(timeout=5.0)
            await session.execute(
                update(AuditOutboxRow)
                .where(AuditOutboxRow.id == row.id)
                .values(status="SENT", sent_at=datetime.now(UTC), last_error=None)
            )
            OUTBOX_DISPATCH_TOTAL.labels(status="SENT").inc()
            logger.info("outbox_row_sent", outbox_id=str(row.id), topic=row.topic)
        except Exception as exc:  # noqa: BLE001
            attempts = int(row.attempts) + 1
            terminal = attempts >= MAX_ATTEMPTS
            new_status = "FAILED" if terminal else "PENDING"
            await session.execute(
                update(AuditOutboxRow)
                .where(AuditOutboxRow.id == row.id)
                .values(
                    status=new_status,
                    attempts=attempts,
                    last_error=str(exc)[:1900],
                )
            )
            OUTBOX_DISPATCH_TOTAL.labels(status=new_status).inc()
            logger.warning(
                "outbox_row_dispatch_failed",
                outbox_id=str(row.id),
                attempts=attempts,
                terminal=terminal,
                error=str(exc),
            )
            if not terminal:
                await asyncio.sleep(random.uniform(0, min(8.0, 0.5 * (2**attempts))))  # noqa: S311

    async def _update_lag_gauge(self, session: AsyncSession) -> None:
        stmt = (
            select(AuditOutboxRow.created_at)
            .where(AuditOutboxRow.status == "PENDING")
            .order_by(AuditOutboxRow.created_at.asc())
            .limit(1)
        )
        result = await session.execute(stmt)
        oldest = result.scalar_one_or_none()
        if oldest is None:
            OUTBOX_LAG_SECONDS.set(0.0)
            return
        lag = (datetime.now(UTC) - oldest).total_seconds()
        OUTBOX_LAG_SECONDS.set(max(0.0, lag))
