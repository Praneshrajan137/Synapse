"""ADR-052 end-to-end: the autonomous loop perceives → decides → acts (no POST).

Wires the REAL components together in-process — the real ``WorldRuntime`` (a live SimPy
world), the real ``SensorLoop`` (autonomous perception + initiative), and the real
``InventorySentinelA2AHandler.execute()`` (actuation) — with thin in-process shims that
only bypass the HTTP transport and the full 8-agent collect/arbitrate (which needs live
agent services + a DB and is not what this test is proving).

What it proves, deterministically: a depleted world is detected by the sensor, which
convenes a decision ON ITS OWN, whose execution ACTUALLY replenishes the world. That is
the perceive→decide→act loop the audit found missing.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from agents.inventory_sentinel.a2a.handler import InventorySentinelA2AHandler
from digital_twin.world import WorldRuntime
from orchestrator.sensor.loop import SensorLoop

if TYPE_CHECKING:
    from synapse_common.world.models import WorldAction


class InProcessWorldClient:
    """Sensor perception that reads the real WorldRuntime directly (bypasses HTTP)."""

    def __init__(self, runtime: WorldRuntime) -> None:
        self._rt = runtime

    async def world_state(self, city: str) -> dict[str, Any] | None:
        return self._rt.perceive().model_dump(mode="json")


class InProcessActuator:
    """Agent actuation that calls the real WorldRuntime directly (bypasses HTTP)."""

    def __init__(self, runtime: WorldRuntime) -> None:
        self._rt = runtime

    def apply(self, action: WorldAction) -> dict[str, Any]:
        return {"applied": True, "result": self._rt.apply_action(action)}


class InProcessConsensus:
    """Minimal real consensus slice: route the reorder to the REAL inventory execute().

    Stands in for ConsensusProtocol's collect→arbitrate→execute (which needs 8 live
    agents + Postgres). The inventory proposal + actuation path it exercises is the
    genuine production code.
    """

    def __init__(self, runtime: WorldRuntime) -> None:
        self._handler = InventorySentinelA2AHandler(actuator=InProcessActuator(runtime))
        self.executed: list[dict[str, Any]] = []

    async def run_consensus(self, request: dict[str, Any]) -> dict[str, Any]:
        low = request.get("sku_ids", [])
        actions = [
            {
                "store_id": request["store_id"],
                "sku_id": sku,
                "action_type": "reorder",
                "quantity": 500.0,
                "safety_stock_multiplier": 1.0,
                "reorder_point": 40,
                "confidence": 0.8,
            }
            for sku in low
        ]
        result = self._handler.execute(
            {
                "decision_id": request["order_id"],
                "city": request["city"],
                "ratified_proposal": {"payload": {"actions": actions}},
            }
        )
        self.executed.append({"request": request, "result": result})
        return result


@pytest.mark.asyncio
async def test_autonomous_loop_perceives_decides_and_acts_on_the_world() -> None:
    # 1. A live world runs forward until demand genuinely depletes stock (auto-restock
    #    is off, so only an agent reorder can replenish — the agent is load-bearing).
    rt = WorldRuntime(city="bengaluru", seed=7).start(run_clock=False)
    for _ in range(40):
        rt.tick()
    depleted = rt.perceive()
    low_skus = [sku for sku, level in depleted.inventory.items() if level < 40.0]
    assert low_skus, "demand should have driven SKUs below the reorder point"
    before = dict(depleted.inventory)

    # 2. The sensor perceives the real world and convenes a decision ON ITS OWN —
    #    no human POST, no synthetic ticker.
    consensus = InProcessConsensus(rt)
    sensor = SensorLoop(
        consensus,
        InProcessWorldClient(rt),
        cities=["bengaluru"],
        reorder_point=40.0,
        heartbeat_idle_polls=0,
    )
    fired = await sensor.poll_once()

    # 3. A decision was autonomously initiated (the audit trail shows `auto-`)...
    assert fired >= 1
    assert consensus.executed
    initiated = consensus.executed[0]["request"]["order_id"]
    assert initiated.startswith("auto-bengaluru-reorder_point")

    # 4. ...and executing it ACTUALLY changed the world: every low SKU was replenished.
    after = rt.perceive().inventory
    for sku in low_skus:
        assert after[sku] > before[sku], f"{sku} should have been reordered into the world"
    assert consensus.executed[0]["result"]["status"] == "executed"
    rt.stop()
