"""Tests for the graceful-shutdown coordinator (Sprint 7, WS-1)."""

from __future__ import annotations

import asyncio

import pytest
from synapse_common.lifespan import ShutdownCoordinator, deep_health_check


class TestShutdownCoordinator:
    @pytest.mark.asyncio
    async def test_starts_ready(self) -> None:
        c = ShutdownCoordinator(grace_seconds=1.0)
        assert c.ready
        assert not c.shutting_down

    @pytest.mark.asyncio
    async def test_shutdown_marks_unready(self) -> None:
        c = ShutdownCoordinator(grace_seconds=1.0)
        await c.shutdown()
        assert not c.ready
        assert c.shutting_down

    @pytest.mark.asyncio
    async def test_runs_closers_in_reverse_order(self) -> None:
        order: list[str] = []
        c = ShutdownCoordinator(grace_seconds=1.0)
        c.register("first", lambda: order.append("first"))
        c.register("second", lambda: order.append("second"))
        c.register("third", lambda: order.append("third"))
        await c.shutdown()
        assert order == ["third", "second", "first"]

    @pytest.mark.asyncio
    async def test_async_and_sync_closers_both_supported(self) -> None:
        events: list[str] = []
        c = ShutdownCoordinator(grace_seconds=1.0)

        async def async_closer() -> None:
            events.append("async")

        c.register("sync", lambda: events.append("sync"))
        c.register("async", async_closer)
        await c.shutdown()
        assert sorted(events) == ["async", "sync"]

    @pytest.mark.asyncio
    async def test_shutdown_is_idempotent(self) -> None:
        calls: list[str] = []
        c = ShutdownCoordinator(grace_seconds=1.0)
        c.register("once", lambda: calls.append("x"))
        await c.shutdown()
        await c.shutdown()
        assert calls == ["x"]

    @pytest.mark.asyncio
    async def test_failing_closer_does_not_block_others(self) -> None:
        ran: list[str] = []
        c = ShutdownCoordinator(grace_seconds=1.0)
        c.register("ok-first", lambda: ran.append("first"))

        def boom() -> None:
            raise RuntimeError("nope")

        c.register("boom", boom)
        c.register("ok-last", lambda: ran.append("last"))
        await c.shutdown()
        assert ran == ["last", "first"]

    @pytest.mark.asyncio
    async def test_slow_closer_is_timed_out(self) -> None:
        c = ShutdownCoordinator(grace_seconds=0.05)

        async def slow() -> None:
            await asyncio.sleep(2.0)

        c.register("slow", slow)
        await c.shutdown()
        assert c.shutting_down


class TestDeepHealthCheck:
    @pytest.mark.asyncio
    async def test_all_ok(self) -> None:
        async def kafka() -> bool:
            return True

        async def redis() -> bool:
            return True

        probe = deep_health_check(kafka, redis)
        result = await probe()
        assert result == {"status": "ok", "checks": {"kafka": True, "redis": True}}

    @pytest.mark.asyncio
    async def test_one_down_marks_degraded(self) -> None:
        async def kafka() -> bool:
            return True

        async def neo4j() -> bool:
            return False

        probe = deep_health_check(kafka, neo4j)
        result = await probe()
        assert result["status"] == "degraded"
        assert result["checks"]["neo4j"] is False

    @pytest.mark.asyncio
    async def test_raising_check_is_treated_as_down(self) -> None:
        async def crashes() -> bool:
            raise RuntimeError("boom")

        probe = deep_health_check(crashes)
        result = await probe()
        assert result["status"] == "degraded"
        assert result["checks"]["crashes"] is False
