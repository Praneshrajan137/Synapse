"""Tests for the ADR-052 WorldRuntime — the standing, ticking world the agents act on.

Driven with manual ticks (no clock thread) against the REAL seeded SimPy engine, so the
assertions are deterministic.
"""

from __future__ import annotations

import pytest
from synapse_common.world.models import WorldAction, WorldActionKind

from digital_twin.world import (
    WorldRuntime,
    all_runtimes,
    get_runtime,
    register_runtime,
    reset_runtimes,
)


@pytest.fixture()
def rt() -> WorldRuntime:
    runtime = WorldRuntime(city="bengaluru", seed=42, step_hours=1.0)
    runtime.start(run_clock=False)
    yield runtime
    runtime.stop()


def test_perceive_after_start_is_full_stock(rt: WorldRuntime) -> None:
    s = rt.perceive()
    assert s.city == "bengaluru"
    assert s.is_synthetic is True
    assert len(s.inventory) == 10
    assert all(level == 100.0 for level in s.inventory.values())
    assert s.restocks_triggered == 0
    assert s.clock_advancing is True  # started (manual-tick mode)


def test_demand_depletes_inventory_and_auto_restock_is_disabled(rt: WorldRuntime) -> None:
    for _ in range(12):
        rt.tick()
    s = rt.perceive()
    # Source-driven demand actually arrived and was fulfilled from stock.
    assert sum(s.inventory.values()) < 1000.0
    assert s.pending_orders >= 0
    # The agent reorder is the ONLY replenishment: the engine's auto-restock is off,
    # so restocks_triggered stays 0 (proves the agent is load-bearing, ADR-052).
    assert s.restocks_triggered == 0


def test_reorder_action_actually_changes_the_world(rt: WorldRuntime) -> None:
    before = rt.perceive().inventory["sku_0"]
    result = rt.apply_action(
        WorldAction(
            action_id="r1", kind=WorldActionKind.REORDER, city="bengaluru",
            sku_id="sku_0", params={"quantity": 500.0}, decision_id="dec-1",
        )
    )
    after = rt.perceive().inventory["sku_0"]
    assert after == before + 500.0
    # The returned effect is the REAL new level, not a fabricated status (ADR-052).
    assert result["status"] == "applied"
    assert result["effect"]["new_level"] == after
    assert result["decision_id"] == "dec-1"


def test_set_policy_and_price_actions_return_honest_effects(rt: WorldRuntime) -> None:
    pol = rt.apply_action(
        WorldAction(
            action_id="p1", kind=WorldActionKind.SET_POLICY, city="bengaluru",
            params={"dispatch_speed": 1.4, "order_qty_mult": 1.2},
        )
    )
    assert pol["effect"]["policy"]["dispatch_speed"] == 1.4
    price = rt.apply_action(
        WorldAction(
            action_id="p2", kind=WorldActionKind.SET_PRICE_MULT, city="bengaluru",
            params={"price_mult": 1.25},
        )
    )
    # Higher price → suppressed demand multiplier.
    assert price["effect"]["demand_mult"] < 1.0


def test_inject_disruption_applies_a_live_shock(rt: WorldRuntime) -> None:
    res = rt.inject_disruption(failure_rate_multiplier=5.0, spoilage_rate_multiplier=3.0)
    assert res["effect"]["shock"]["failure_rate_multiplier"] == 5.0
    rt.tick()  # world keeps advancing after a shock
    assert rt.perceive().clock_advancing is True


def test_registry_helpers() -> None:
    reset_runtimes()
    a = register_runtime(WorldRuntime(city="bengaluru", seed=1))
    register_runtime(WorldRuntime(city="mumbai", seed=2))
    assert get_runtime("bengaluru") is a
    assert set(all_runtimes()) == {"bengaluru", "mumbai"}
    reset_runtimes()
    assert all_runtimes() == {}
