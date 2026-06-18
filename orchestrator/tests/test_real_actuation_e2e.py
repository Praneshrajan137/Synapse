"""ADR-052 end-to-end: a converted lever agent ACTUALLY changes the standing world.

This is the R9.7 proof. It wires the REAL components together in-process — a live
``WorldRuntime`` (a real SimPy world) and the REAL ``PricingOracleA2AHandler.execute()``
(the converted ``SET_PRICE_MULT`` actuation) — with a thin in-process actuator that only
bypasses the HTTP transport.

The production ``WorldActuator`` speaks A2A/HTTP (``POST /a2a apply_action``). To exercise
the genuine actuation path without standing up an HTTP server, ``InProcessActuator``
implements the same ``Actuator`` protocol and forwards ``apply`` straight to the live
``WorldRuntime.apply_action`` — returning the identical ``{"applied": True, "result": ...}``
envelope the HTTP client would. This is exactly the shim ``test_agentic_loop_e2e.py`` uses,
so the handler runs its real lever-building, real actuation, and real honest-status logic
against a real world; only the network hop is removed.

What it proves, deterministically: executing a ratified ``pricing_oracle`` proposal applies
a ``SET_PRICE_MULT`` lever that the world genuinely accepts, the state observed via
``perceive()`` actually changes (demand is scaled through the price lever), and the agent
returns the honest status ``"executed"``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from agents.pricing_oracle.a2a.handler import PricingOracleA2AHandler
from digital_twin.world import WorldRuntime

if TYPE_CHECKING:
    from synapse_common.world.models import WorldAction


class InProcessActuator:
    """Agent actuation that calls the real ``WorldRuntime`` directly (bypasses HTTP).

    Mirrors the production ``WorldActuator`` contract — ``apply(action)`` returns
    ``{"applied": bool, "result": <twin apply_action envelope>}`` — by forwarding to the
    live runtime's ``apply_action`` instead of POSTing it over A2A.
    """

    def __init__(self, runtime: WorldRuntime) -> None:
        self._rt = runtime

    def apply(self, action: WorldAction) -> dict[str, Any]:
        return {"applied": True, "result": self._rt.apply_action(action)}


_STORE = "store_001"
_TS = "2025-01-01T00:00:00Z"


def _pricing_update(sku: str, multiplier: float) -> dict[str, Any]:
    """A schema-valid ``pricing_update`` sub-object (proto/domain/pricing_update)."""
    base_price = 100.0
    return {
        "pricing_id": f"pid-{sku}",
        "sku_id": sku,
        "store_id": _STORE,
        "category": "staples",
        "base_price": base_price,
        "multiplier": multiplier,
        "final_price": base_price * multiplier,
        "is_essential": False,
        "elasticity_source": "correlation_fallback",
        "timestamp": _TS,
        "confidence": 0.8,
    }


def test_real_actuation_changes_world_e2e() -> None:
    """A converted lever agent's execute() changes the live world and returns "executed".

    **Validates: Requirements 9.7**
    """
    # 1. A live, standing world (manual-tick so the proof is deterministic).
    rt = WorldRuntime(city="bengaluru", seed=7).start(run_clock=False)
    for _ in range(5):
        rt.tick()

    # 2. Snapshot the objective-relevant state BEFORE actuation. pricing_oracle scales
    #    world demand through the price lever (SET_PRICE_MULT → demand_mult), which is
    #    observable in perceive().demand_rate.
    before = rt.perceive()
    assert before.demand_rate > 0.0

    # 3. Execute a ratified pricing proposal through the REAL handler wired to the REAL
    #    world via an in-process actuator. A multiplier of 1.5 raises price, which the
    #    world translates into a suppressed demand_mult (1/1.5), changing demand_rate.
    handler = PricingOracleA2AHandler(actuator=InProcessActuator(rt))
    result = handler.execute(
        {
            "decision_id": "e2e-pricing-1",
            "city": "bengaluru",
            "ratified_proposal": {"payload": {"updates": [_pricing_update("sku_0", 1.5)]}},
        }
    )

    # 4. The agent honestly reports it actuated the world.
    assert result["status"] == "executed"
    assert result["city"] == "bengaluru"
    assert any(effect.get("applied") for effect in result["world_effects"])

    # 5. The observed world state ACTUALLY changed: demand was scaled through the price
    #    lever (a real mutation in perceive(), not a fabricated effect).
    after = rt.perceive()
    assert after.demand_rate != before.demand_rate
    rt.stop()
