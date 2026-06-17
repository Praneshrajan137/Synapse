"""Tests for the ADR-052 SensorLoop — autonomous perception → initiative.

Driven with fakes (no twin, no agents, no sleeps) so the autonomy logic is deterministic.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from orchestrator.sensor.loop import SensorLoop


class FakeProtocol:
    def __init__(self) -> None:
        self.requests: list[dict[str, Any]] = []
        self.fail = False

    async def run_consensus(self, decision_request: dict[str, Any]) -> dict[str, Any]:
        if self.fail:
            raise RuntimeError("consensus boom")
        self.requests.append(decision_request)
        return {"decision_id": "x"}


class FakeWorld:
    def __init__(self, states: dict[str, dict[str, Any] | None]) -> None:
        self._states = states

    async def world_state(self, city: str) -> dict[str, Any] | None:
        return self._states.get(city)


@pytest.mark.asyncio
async def test_low_stock_triggers_autonomous_decision() -> None:
    world = FakeWorld({"bengaluru": {"inventory": {"sku_0": 5.0, "sku_1": 80.0}}})
    proto = FakeProtocol()
    loop = SensorLoop(
        proto, world, cities=["bengaluru"], reorder_point=40.0, heartbeat_idle_polls=0
    )

    fired = await loop.poll_once()

    assert fired == 1
    assert len(proto.requests) == 1
    req = proto.requests[0]
    # The decision was initiated BY THE SYSTEM (auto- prefix), not a human/synthetic POST.
    assert req["order_id"].startswith("auto-bengaluru-reorder_point")
    assert req["trigger"] == "reorder_point"
    assert req["sku_ids"] == ["sku_0"]  # only the SKU below the reorder point
    assert req["items"][0]["sku_id"] == "sku_0"
    assert loop.decisions_triggered == 1


@pytest.mark.asyncio
async def test_debounce_prevents_double_fire() -> None:
    world = FakeWorld({"bengaluru": {"inventory": {"sku_0": 5.0}}})
    proto = FakeProtocol()
    loop = SensorLoop(
        proto,
        world,
        cities=["bengaluru"],
        reorder_point=40.0,
        debounce_s=999.0,
        heartbeat_idle_polls=0,
    )
    await loop.poll_once()
    await loop.poll_once()
    assert loop.decisions_triggered == 1  # the second identical condition is debounced


@pytest.mark.asyncio
async def test_world_unavailable_degrades_without_firing() -> None:
    world = FakeWorld({"bengaluru": None})  # twin unreachable
    proto = FakeProtocol()
    loop = SensorLoop(proto, world, cities=["bengaluru"], heartbeat_idle_polls=0)
    fired = await loop.poll_once()
    assert fired == 0
    assert proto.requests == []
    assert loop.polls == 1  # it polled, degraded honestly, and kept going (I-7)


@pytest.mark.asyncio
async def test_heartbeat_fires_after_idle_window() -> None:
    world = FakeWorld({"bengaluru": {"inventory": {"sku_0": 100.0}}})  # nothing low
    proto = FakeProtocol()
    loop = SensorLoop(
        proto, world, cities=["bengaluru"], reorder_point=40.0, heartbeat_idle_polls=2
    )
    await loop.poll_once()  # idle 1
    assert loop.decisions_triggered == 0
    await loop.poll_once()  # idle 2 → heartbeat keepalive
    assert loop.decisions_triggered == 1
    assert proto.requests[-1]["trigger"] == "heartbeat"


@pytest.mark.asyncio
async def test_failed_decision_does_not_crash_loop() -> None:
    world = FakeWorld({"bengaluru": {"inventory": {"sku_0": 5.0}}})
    proto = FakeProtocol()
    proto.fail = True
    loop = SensorLoop(
        proto, world, cities=["bengaluru"], reorder_point=40.0, heartbeat_idle_polls=0
    )
    fired = await loop.poll_once()  # must not raise
    assert fired == 0
    assert loop.decisions_triggered == 0


@pytest.mark.asyncio
async def test_start_stop_background_lifecycle() -> None:
    world = FakeWorld({"bengaluru": {"inventory": {"sku_0": 100.0}}})
    proto = FakeProtocol()
    loop = SensorLoop(
        proto, world, cities=["bengaluru"], poll_interval_s=0.01, heartbeat_idle_polls=0
    )
    await loop.start()
    assert loop.running is True
    await asyncio.sleep(0.05)
    await loop.stop()
    assert loop.running is False
    assert loop.polls >= 1
