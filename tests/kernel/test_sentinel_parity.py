"""The kernel's Sentinel equals the legacy agent code decision by decision (stage A, full closure).

At every decision of E5's first twelve replicate seeds on the legacy world, the legacy pathway runs
on the same observation: the consensus arm's own request builder
(``uplift.consensus_arm.observation_to_decision_request``), the Inventory Sentinel's own A2A handler
(``proposal``, which reads the request through ``forecast_from_request`` and decides through
``InventorySentinelPipeline.decide``, then round-trips the proposal through its deterministic JSON),
and the consensus arm's own translation of the binding payload
(``_coerce_reorder_quantities``). Every quantity must equal the kernel port's exactly. Costs are
compared too, as the replicate the kernel's quantities drive. The eight-agent arm itself is compared
through the verdict's pins (``test_sentinel_alone.py``) and re-measured by the verdict on every run.

This file imports the agent stack, so it runs in the kernel workflow's parity job.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import pytest

from synapse_kernel.drive import run_replicate
from synapse_kernel.objective import replicate_cost
from synapse_kernel.observation import Observation, PolicyAction
from synapse_kernel.policies.sentinel import SentinelAlone
from synapse_kernel.world import load_world

PINS = Path(__file__).resolve().parents[2] / "infrastructure" / "quality" / "verdict-pins.json"


class _BothPathways:
    """Decides with the kernel port and checks every quantity against the legacy pathway."""

    def __init__(self, legacy: dict[str, Any]) -> None:
        self._port = SentinelAlone()
        self._legacy = legacy
        self.decisions = 0
        self.quantities = 0
        self.mismatches: list[tuple[float, str, float, float]] = []

    def decide(self, obs: Observation) -> PolicyAction:
        mine = self._port.quantities(obs)
        theirs = self._legacy_quantities(obs)
        self.decisions += 1
        for sku in sorted(set(mine) | set(theirs)):
            self.quantities += 1
            a, b = mine.get(sku, float("nan")), theirs.get(sku, float("nan"))
            if a.hex() != b.hex():
                self.mismatches.append((obs.sim_time, sku, a, b))
        return PolicyAction(reorder_quantities=mine)

    def _legacy_quantities(self, obs: Observation) -> dict[str, float]:
        consensus_arm = self._legacy["consensus_arm"]
        legacy_obs = self._legacy["Observation"](
            inventory=obs.inventory,
            sim_time=obs.sim_time,
            delivery_count=obs.delivery_count,
            spoilage_count=obs.spoilage_count,
            stockout_count=obs.stockout_count,
            unit_costs=obs.unit_costs,
            on_order=obs.on_order,
            supplier_lead_time_history=obs.supplier_lead_time_history,
            demand_to_date=obs.demand_to_date,
            sku_supplier=obs.sku_supplier,
            start_weekday=obs.start_weekday,
        )
        request = consensus_arm.observation_to_decision_request(legacy_obs)
        proposal = self._legacy["handler"].proposal(request)
        quantities: dict[str, float] = consensus_arm._coerce_reorder_quantities(proposal["payload"])
        return quantities


@pytest.fixture(scope="module")
def legacy() -> dict[str, Any]:
    import structlog

    structlog.configure(
        wrapper_class=structlog.make_filtering_bound_logger(logging.CRITICAL),
    )
    from agents.inventory_sentinel.a2a.handler import InventorySentinelA2AHandler
    from uplift import consensus_arm
    from uplift.interfaces import Observation as LegacyObservation

    return {
        "consensus_arm": consensus_arm,
        "Observation": LegacyObservation,
        "handler": InventorySentinelA2AHandler(),
    }


def test_every_decision_equals_the_legacy_pathway_on_e5s_twelve_seeds(
    legacy: dict[str, Any],
) -> None:
    document = json.loads(PINS.read_text(encoding="utf-8"))
    seeds = [int(seed) for seed in document["seeds"]]
    consensus = document["costs"]["consensus"]
    world = load_world()
    decisions = quantities = 0
    for seed in seeds:
        policy = _BothPathways(legacy)
        cost = replicate_cost(run_replicate(seed, policy, world)).hex()
        assert not policy.mismatches, f"seed {seed}: first divergence {policy.mismatches[0]}"
        assert cost == consensus[str(seed)], f"seed {seed}: {cost} != {consensus[str(seed)]}"
        decisions += policy.decisions
        quantities += policy.quantities
    assert decisions == 12 * 24
    assert quantities == 12 * 24 * 10
