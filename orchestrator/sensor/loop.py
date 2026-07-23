"""SYNAPSE SensorLoop — autonomous perception → initiative (ADR-052, the keystone).

This is the single change that turns SYNAPSE from "answers when POSTed" into an agent
system that *acts on its own*. A background task continuously **perceives** each city's
standing world (``WorldRuntime.perceive`` via the twin's A2A ``world_state``), applies
rule-based condition detectors (reorder-point breach today; demand-spike / spoilage /
disruption are additive), debounces, and **triggers consensus itself** — no human POST,
no synthetic ticker.

Honest degradation (I-7): if the world is unreachable the loop idles and logs; it never
crashes the orchestrator or fabricates a decision. Lifecycle (``start``/``stop``/
``running``) mirrors ``orchestrator/outbox/dispatcher.py::OutboxDispatcher`` so the
orchestrator lifespan manages it identically.
"""

from __future__ import annotations

import asyncio
import contextlib
import os
import time
from typing import Any, Protocol, runtime_checkable

import structlog
from synapse_common.a2a_sdk import send_a2a_request

logger = structlog.get_logger(__name__)

TWIN_ENDPOINT = os.environ.get("SYNAPSE_TWIN_ENDPOINT", "http://digital-twin:8009")
DEFAULT_STORE_ID = os.environ.get("SYNAPSE_SENSOR_STORE_ID", "store_001")


@runtime_checkable
class WorldClient(Protocol):
    """Perception transport — fetch one city's world snapshot (None ⇒ unavailable)."""

    async def world_state(self, city: str) -> dict[str, Any] | None: ...


@runtime_checkable
class ConsensusRunner(Protocol):
    """The minimal slice of ConsensusProtocol the sensor drives."""

    async def run_consensus(self, decision_request: dict[str, Any]) -> Any: ...


class A2AWorldClient:
    """Production ``WorldClient`` — perceives the twin's standing world over A2A (I-9)."""

    def __init__(self, twin_url: str = TWIN_ENDPOINT, timeout: float = 5.0) -> None:
        self._url = twin_url
        self._timeout = timeout

    async def world_state(self, city: str) -> dict[str, Any] | None:
        try:
            resp = await send_a2a_request(
                target_url=self._url,
                method="world_state",
                params={"city": city},
                timeout=self._timeout,
            )
            if resp.error:
                logger.warning("sensor_world_state_error", city=city, error=resp.error)
                return None
            return resp.result
        except Exception as exc:  # noqa: BLE001 — an unreachable world idles the sensor (I-7)
            logger.warning("sensor_world_state_unreachable", city=city, error=str(exc))
            return None


class SensorLoop:
    """Perceives each city's world and autonomously convenes consensus on conditions."""

    def __init__(
        self,
        protocol: ConsensusRunner,
        world_client: WorldClient,
        *,
        cities: list[str],
        poll_interval_s: float = 10.0,
        reorder_point: float = 40.0,
        debounce_s: float = 120.0,
        heartbeat_idle_polls: int = 30,
        store_id: str = DEFAULT_STORE_ID,
    ) -> None:
        self._protocol = protocol
        self._world = world_client
        self._cities = list(cities)
        self._poll_interval_s = poll_interval_s
        self._reorder_point = reorder_point
        self._debounce_s = debounce_s
        self._heartbeat_idle_polls = heartbeat_idle_polls
        self._store_id = store_id
        self._running = False
        self._task: asyncio.Task[None] | None = None
        self._last_fired: dict[str, float] = {}
        self._idle_polls = 0
        self._seq = 0
        # Observability counters (read by tests + the agency_truth gate).
        self.decisions_triggered = 0
        self.polls = 0

    @property
    def running(self) -> bool:
        return self._running

    def status(self) -> dict[str, object]:
        """Observability snapshot for the autonomy endpoint (ADR-053).

        Additive to the counters read by tests + the agency_truth gate; exposes
        the loop's self-initiation record so the operator UI can say "the system
        is acting on its own" with real numbers, not a boolean guess.
        """
        return {
            "running": self._running,
            "cities": list(self._cities),
            "poll_interval_s": self._poll_interval_s,
            "reorder_point": self._reorder_point,
            "polls": self.polls,
            "decisions_triggered": self.decisions_triggered,
        }

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._run())
        logger.info("sensor_loop_started", cities=self._cities, interval_s=self._poll_interval_s)

    async def stop(self) -> None:
        self._running = False
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None
        logger.info("sensor_loop_stopped", decisions_triggered=self.decisions_triggered)

    async def _run(self) -> None:
        while self._running:
            try:
                await self.poll_once()
            except Exception as exc:  # noqa: BLE001 — one bad cycle must not kill the loop (I-7)
                logger.error("sensor_poll_failed", error=str(exc))
            await asyncio.sleep(self._poll_interval_s)

    async def poll_once(self) -> int:
        """One perception cycle across all cities. Returns the number of decisions fired."""
        fired = 0
        any_trigger = False
        for city in self._cities:
            state = await self._world.world_state(city)
            self.polls += 1
            if state is None:
                continue  # honest degradation: idle this city, keep polling the rest
            for trig in self._detect(city, state):
                any_trigger = True
                if self._should_fire(trig["key"]) and await self._fire(city, trig):
                    fired += 1
        fired += await self._maybe_heartbeat(any_trigger)
        return fired

    # ── condition detectors (rule-based; additive) ──────────────────────

    def _detect(self, city: str, state: dict[str, Any]) -> list[dict[str, Any]]:
        triggers: list[dict[str, Any]] = []
        inventory = state.get("inventory", {})
        if isinstance(inventory, dict):
            low = sorted(
                sku
                for sku, level in inventory.items()
                if isinstance(level, (int, float)) and level < self._reorder_point
            )
            if low:
                triggers.append(
                    {
                        "trigger": "reorder_point",
                        "key": f"{city}:reorder_point",
                        "low_skus": low,
                        "inventory": inventory,
                    }
                )
        return triggers

    def _should_fire(self, key: str) -> bool:
        now = time.monotonic()
        last = self._last_fired.get(key)
        if last is not None and (now - last) < self._debounce_s:
            return False
        self._last_fired[key] = now
        return True

    async def _maybe_heartbeat(self, any_trigger: bool) -> int:
        """Fire a low-rate keepalive when nothing has triggered for a while.

        So liveness never depends on the synthetic ticker — the system is autonomously
        alive even in quiet windows.
        """
        if any_trigger:
            self._idle_polls = 0
            return 0
        self._idle_polls += 1
        if self._heartbeat_idle_polls and self._idle_polls >= self._heartbeat_idle_polls:
            self._idle_polls = 0
            if await self._fire(self._cities[0], {"trigger": "heartbeat", "key": "heartbeat"}):
                return 1
        return 0

    # ── firing ──────────────────────────────────────────────────────────

    async def _fire(self, city: str, trig: dict[str, Any]) -> bool:
        request = self._build_request(city, trig)
        try:
            await self._protocol.run_consensus(request)
            self.decisions_triggered += 1
            logger.info(
                "sensor_triggered_decision",
                city=city,
                trigger=trig["trigger"],
                order_id=request["order_id"],
            )
            return True
        except Exception as exc:  # noqa: BLE001 — a failed decision is logged, loop continues (I-7)
            logger.error(
                "sensor_decision_failed", city=city, trigger=trig["trigger"], error=str(exc)
            )
            return False

    def _build_request(self, city: str, trig: dict[str, Any]) -> dict[str, Any]:
        self._seq += 1
        # `auto-` prefix marks an autonomously-initiated decision (vs `synthetic-` ticker
        # vs a human order) so the audit trail shows the system acted on its own.
        request: dict[str, Any] = {
            "order_id": f"auto-{city}-{trig['trigger']}-{self._seq}",
            "city": city,
            "store_id": self._store_id,
            "trigger": trig["trigger"],
            "disruption_active": trig["trigger"] == "disruption",
        }
        if trig["trigger"] == "reorder_point":
            low = trig.get("low_skus", [])
            request["sku_ids"] = low
            request["items"] = [
                {"sku_id": sku, "quantity": int(self._reorder_point * 4)} for sku in low
            ]
            request["world_inventory"] = trig.get("inventory", {})
        return request
