"""One replicate: observe -> decide -> order -> advance, hour by hour.

The loop of ``uplift/foresight.py::run_single_arm`` (``_new_arm_engine`` then ``_drive_arm``) with
the observation of ``uplift/harness.py::observe`` and the ordering of ``_apply_reorders``, at E5's
cadence: one decision per simulated hour, the engine's own restock switched off (``0.0``, the
committed comparator threshold), so the policy's orders are the only replenishment.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Final

from synapse_kernel.engine import SupplyChainSimulation
from synapse_kernel.observation import Observation

if TYPE_CHECKING:
    from collections.abc import Mapping

    from synapse_kernel.observation import Policy
    from synapse_kernel.world import ResolvedWorld

#: One decision per this many simulated minutes (``uplift.foresight.FORESIGHT_WINDOW_MIN``).
DECISION_WINDOW_MIN: Final[float] = 60.0
#: The committed comparator restock threshold (``policy.yaml`` ``comparator.restock_threshold``):
#: 0.0 disables the engine's own restock, so only the policy replenishes.
RESTOCK_THRESHOLD: Final[float] = 0.0
#: E5's replicate length, in hours.
E5_HOURS: Final[float] = 24.0
#: The SKU catalogue the per-SKU unit costs are derived over (``uplift/harness.py``).
CANONICAL_SKUS: Final[tuple[str, ...]] = tuple(f"sku_{i}" for i in range(10))


def unit_costs() -> dict[str, float]:
    """The legacy harness's fixed per-SKU unit costs (``_derive_unit_costs``)."""
    return {sku: round(1.0 + index * 0.5, 2) for index, sku in enumerate(CANONICAL_SKUS)}


def cadence(hours: float) -> tuple[int, float]:
    """``(slices, slice_hours)``: one decision per :data:`DECISION_WINDOW_MIN`, at least one."""
    slices = max(1, int((hours * 60.0) // DECISION_WINDOW_MIN))
    return slices, hours / slices


def observe(sim: SupplyChainSimulation, *, costs: Mapping[str, float]) -> Observation:
    """The snapshot a policy decides on (``uplift/harness.py::observe``, without the shock)."""
    metrics = sim.metrics
    return Observation(
        inventory={sku: int(level) for sku, level in sim.inventory.items()},
        sim_time=sim.sim_time_min,
        delivery_count=int(metrics.orders_delivered),
        spoilage_count=int(metrics.orders_spoiled),
        stockout_count=int(metrics.unmet_demand_events),
        unit_costs=costs,
        on_order=sim.on_order,
        supplier_lead_time_history=sim.supplier_lead_time_history,
        demand_to_date=sim.demand_to_date,
        sku_supplier=sim.sku_supplier,
        start_weekday=sim.start_weekday,
    )


def apply_reorders(sim: SupplyChainSimulation, quantities: Mapping[str, float]) -> None:
    """Place each finite, positive quantity with its supplier (``_apply_reorders``)."""
    for sku, qty in quantities.items():
        try:
            quantity = float(qty)
        except (TypeError, ValueError):
            continue
        if math.isfinite(quantity) and quantity > 0.0:
            sim.place_order(str(sku), quantity)


def run_replicate(
    seed: int,
    policy: Policy,
    world: ResolvedWorld | None,
    *,
    hours: float = E5_HOURS,
    restock_threshold: float = RESTOCK_THRESHOLD,
) -> SupplyChainSimulation:
    """Drive ``policy`` for ``hours`` at ``seed`` in ``world``; return the finished engine."""
    slices, slice_hours = cadence(hours)
    sim = SupplyChainSimulation(seed=seed, world=world)
    sim.start()
    sim.set_policy(restock_threshold=restock_threshold)
    costs = unit_costs()
    for _ in range(slices):
        action = policy.decide(observe(sim, costs=costs))
        if action.reorder_quantities:
            apply_reorders(sim, action.reorder_quantities)
        sim.advance(slice_hours)
    return sim
