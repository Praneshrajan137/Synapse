"""Outbox-after-crash test (WS-2 §3 acceptance, ADR-026).

Uses an in-memory SQLite database (no Postgres dependency) plus a
stubbed ``SynapseProducer`` to exercise the dispatcher's exactly-once
semantics:

  1. Enqueue 3 outbox rows in a single transaction.
  2. Run the dispatcher once — all rows should publish + mark SENT.
  3. Simulate a crash: stop the dispatcher mid-run; rows in PENDING
     state remain pending. Restart — the dispatcher picks them up.

The test asserts on the producer's recorded calls and the row
``status`` transitions, not on real Kafka delivery.
"""

import pytest

pytest.importorskip("sqlalchemy")
pytest.importorskip("aiosqlite")

from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from orchestrator.audit.models import AuditOutboxRow, Base


class _StubProducer:
    def __init__(self, fail_first_n: int = 0) -> None:
        self.calls: list[dict[str, Any]] = []
        self._fail_first_n = fail_first_n

    def produce(
        self,
        topic: str,
        value: dict[str, Any],
        key: str | None = None,
        headers: list[tuple[str, bytes]] | None = None,
    ) -> None:
        if self._fail_first_n > 0:
            self._fail_first_n -= 1
            raise RuntimeError("simulated transient kafka outage")
        self.calls.append({"topic": topic, "value": value, "key": key})

    def flush(self, timeout: float = 10.0) -> int:
        return 0


@pytest_asyncio.fixture
async def session_factory() -> Any:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield factory
    await engine.dispose()


async def _enqueue_n(factory: async_sessionmaker, topic: str, n: int) -> list[Any]:
    rows: list[Any] = []
    async with factory() as session:
        for i in range(n):
            row = AuditOutboxRow(
                decision_id=uuid4(),
                topic=topic,
                message_key=f"k{i}",
                payload={"i": i},
            )
            session.add(row)
            rows.append(row)
        await session.commit()
    return rows


@pytest.mark.integration
@pytest.mark.asyncio
async def test_dispatcher_drains_pending_rows(session_factory: Any) -> None:
    from orchestrator.outbox.dispatcher import OutboxDispatcher

    await _enqueue_n(session_factory, "synapse.orders.demand", 3)
    producer = _StubProducer()
    dispatcher = OutboxDispatcher(session_factory, producer, poll_interval_s=0.05)
    await dispatcher._drain_once()
    assert len(producer.calls) == 3
    async with session_factory() as session:
        result = await session.execute(select(AuditOutboxRow))
        rows = list(result.scalars())
    assert all(row.status == "SENT" for row in rows)
    assert all(row.sent_at is not None for row in rows)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_dispatcher_keeps_rows_pending_on_transient_failure(
    session_factory: Any,
) -> None:
    from orchestrator.outbox.dispatcher import OutboxDispatcher

    await _enqueue_n(session_factory, "synapse.orders.demand", 2)
    producer = _StubProducer(fail_first_n=2)
    dispatcher = OutboxDispatcher(session_factory, producer, poll_interval_s=0.05)
    await dispatcher._drain_once()
    async with session_factory() as session:
        result = await session.execute(select(AuditOutboxRow))
        rows = list(result.scalars())
    assert all(row.status == "PENDING" for row in rows)
    assert all(row.attempts == 1 for row in rows)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_dispatcher_picks_up_after_restart(session_factory: Any) -> None:
    from orchestrator.outbox.dispatcher import OutboxDispatcher

    await _enqueue_n(session_factory, "synapse.orders.demand", 2)
    producer1 = _StubProducer(fail_first_n=2)
    dispatcher1 = OutboxDispatcher(session_factory, producer1, poll_interval_s=0.05)
    await dispatcher1._drain_once()
    assert producer1.calls == []

    # Simulate restart with a healthy producer.
    producer2 = _StubProducer()
    dispatcher2 = OutboxDispatcher(session_factory, producer2, poll_interval_s=0.05)
    await dispatcher2._drain_once()
    assert len(producer2.calls) == 2
    async with session_factory() as session:
        result = await session.execute(select(AuditOutboxRow))
        rows = list(result.scalars())
    assert all(row.status == "SENT" for row in rows)
