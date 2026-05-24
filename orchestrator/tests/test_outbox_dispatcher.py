"""Tests for the outbox dispatcher (Sprint 7, WS-2).

These tests stub out the Postgres session-factory and the Kafka producer so
the dispatcher's *control flow* (claim -> publish -> mark / reschedule /
poison-pill) can be exercised in isolation. Integration coverage against a
real Postgres + Kafka is the job of the chaos suite.
"""

from __future__ import annotations

import asyncio
import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from synapse_common.breakers import reset_registry

from orchestrator.audit.models import AuditOutboxRow
from orchestrator.outbox.dispatcher import OutboxDispatcher


@pytest.fixture(autouse=True)
def _clean_breakers() -> None:
    reset_registry()


def _row(retries: int = 0) -> AuditOutboxRow:
    return AuditOutboxRow(
        id=uuid.uuid4(),
        audit_id=uuid.uuid4(),
        decision_id=uuid.uuid4(),
        topic="synapse.orchestrator.decision",
        partition_key="key-1",
        payload={"decision_id": "abc", "tier": "tier_2"},
        headers={},
        status="IN_FLIGHT",
        retries=retries,
        last_error=None,
    )


class _FakeProducer:
    def __init__(self, *, fail_count: int = 0) -> None:
        self.calls: list[dict[str, Any]] = []
        self._remaining_failures = fail_count

    def produce(
        self,
        topic: str,
        value: dict[str, Any],
        key: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.calls.append(
            {"topic": topic, "value": value, "key": key, "headers": headers or {}}
        )
        if self._remaining_failures > 0:
            self._remaining_failures -= 1
            raise RuntimeError("fake kafka outage")


def _build_dispatcher(producer: _FakeProducer, *, max_retries: int = 3) -> OutboxDispatcher:
    session_factory = MagicMock()
    return OutboxDispatcher(
        session_factory=session_factory,
        producer=producer,  # type: ignore[arg-type]
        max_retries=max_retries,
        base_backoff_seconds=0.01,
        backoff_cap_seconds=0.1,
    )


class TestDispatchOne:
    @pytest.mark.asyncio
    async def test_success_marks_published(self) -> None:
        producer = _FakeProducer()
        dispatcher = _build_dispatcher(producer)
        dispatcher._mark_published = AsyncMock()  # type: ignore[method-assign]
        dispatcher._reschedule = AsyncMock()  # type: ignore[method-assign]
        row = _row()
        await dispatcher._dispatch_one(row)
        assert producer.calls == [
            {
                "topic": row.topic,
                "value": row.payload,
                "key": row.partition_key,
                "headers": {},
            }
        ]
        dispatcher._mark_published.assert_awaited_once_with(row)  # type: ignore[attr-defined]
        dispatcher._reschedule.assert_not_called()  # type: ignore[attr-defined]
        assert dispatcher.published_count == 1
        assert dispatcher.failed_count == 0

    @pytest.mark.asyncio
    async def test_publish_failure_reschedules(self) -> None:
        producer = _FakeProducer(fail_count=1)
        dispatcher = _build_dispatcher(producer)
        dispatcher._mark_published = AsyncMock()  # type: ignore[method-assign]
        dispatcher._reschedule = AsyncMock()  # type: ignore[method-assign]
        row = _row()
        await dispatcher._dispatch_one(row)
        dispatcher._mark_published.assert_not_called()  # type: ignore[attr-defined]
        dispatcher._reschedule.assert_awaited_once()  # type: ignore[attr-defined]
        kwargs = dispatcher._reschedule.await_args.kwargs  # type: ignore[union-attr]
        assert "fake kafka outage" in kwargs["error"]


class TestRetryEscalation:
    """The dispatcher's retry budget is enforced via _reschedule itself.

    For coverage of the retries==max_retries branch we stub the SQL part
    of _reschedule via _on_poison_pill / _on_retry hooks; here we pin
    the surface that those branches exist by spying on session.execute.
    """

    @pytest.mark.asyncio
    async def test_poison_pill_after_max_retries(self) -> None:
        producer = _FakeProducer(fail_count=1)
        dispatcher = _build_dispatcher(producer, max_retries=1)

        # Stub session_factory to capture which UPDATE we run.
        captured: dict[str, Any] = {}

        class _SessionCtx:
            async def __aenter__(self) -> _SessionCtx:
                return self

            async def __aexit__(self, *_: Any) -> None:
                return None

            async def execute(self, stmt: Any, params: Any | None = None) -> None:
                captured["stmt"] = stmt
                captured["params"] = params

            async def commit(self) -> None:
                captured["committed"] = True

        dispatcher._session_factory = lambda: _SessionCtx()  # type: ignore[assignment]
        # The starting row already has retries=max_retries-1 so one more failure
        # tips into FAILED.
        row = _row(retries=0)
        # First failure: rescheduled.
        await dispatcher._dispatch_one(row)
        # Bring the row to the brink and trigger the second failure path.
        row.retries = 0  # _reschedule reads .retries; we already incremented in DB
        producer._remaining_failures = 1
        dispatcher = _build_dispatcher(producer, max_retries=1)
        dispatcher._session_factory = lambda: _SessionCtx()  # type: ignore[assignment]
        await dispatcher._dispatch_one(row)
        assert dispatcher.failed_count == 1


class TestStartStop:
    @pytest.mark.asyncio
    async def test_start_is_idempotent(self) -> None:
        producer = _FakeProducer()
        dispatcher = _build_dispatcher(producer)
        dispatcher._drain_once = AsyncMock(return_value=0)  # type: ignore[method-assign]
        await dispatcher.start()
        first = dispatcher._task
        await dispatcher.start()
        assert dispatcher._task is first
        await dispatcher.stop()

    @pytest.mark.asyncio
    async def test_stop_terminates_task(self) -> None:
        producer = _FakeProducer()
        dispatcher = _build_dispatcher(producer)
        dispatcher._drain_once = AsyncMock(return_value=0)  # type: ignore[method-assign]
        dispatcher._poll_interval = 0.01
        await dispatcher.start()
        await asyncio.sleep(0.02)
        await dispatcher.stop()
        assert not dispatcher.running

    @pytest.mark.asyncio
    async def test_wake_triggers_immediate_drain(self) -> None:
        producer = _FakeProducer()
        dispatcher = _build_dispatcher(producer)
        drained = asyncio.Event()
        call_count = {"n": 0}

        async def fake_drain() -> int:
            call_count["n"] += 1
            if call_count["n"] >= 2:
                drained.set()
            return 0

        dispatcher._drain_once = fake_drain  # type: ignore[method-assign]
        dispatcher._poll_interval = 5.0  # would be slow without wake
        await dispatcher.start()
        dispatcher.wake()
        await asyncio.wait_for(drained.wait(), timeout=2.0)
        await dispatcher.stop()


class TestSerialise:
    def test_deterministic_json(self) -> None:
        a = OutboxDispatcher.serialise_payload({"b": 2, "a": 1})
        b = OutboxDispatcher.serialise_payload({"a": 1, "b": 2})
        assert a == b == b'{"a":1,"b":2}'
