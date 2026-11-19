"""The committed objective E5 prices a replicate with (ADR-055 D2; ``policy.yaml`` section 1).

Ported from ``uplift/regret.py::RegretObjective.cost`` as ``uplift/kpi.py::committed_objective``
loads it: five terms, summed in the committed order, each normalised then weighted. These are
the LEGACY weights (8:1:1 from the measured agent's own defaults; truth finding F-14a); the
release's economic weights are sealed separately (``docs/truth/sealed/``) and are not these.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from synapse_kernel.engine import SupplyChainSimulation

#: The summation order of the committed objective (``uplift.regret.OBJECTIVE_TERMS``).
TERMS: Final[tuple[str, ...]] = (
    "stockout_rate",
    "spoilage_rate",
    "on_hand",
    "delivery_latency",
    "unmet_service",
)
WEIGHTS: Final[dict[str, float]] = {
    "stockout_rate": 0.0,
    "spoilage_rate": 1.0,
    "on_hand": 1.0,
    "delivery_latency": 1.0,
    "unmet_service": 8.0,
}
ON_HAND_NORMALISER: Final[float] = 1000.0
DELIVERY_NORMALISER: Final[float] = 27.5


def legacy_cost(
    *,
    stockout_rate: float,
    spoilage_rate: float,
    fill_rate: float,
    avg_on_hand_units: float,
    avg_delivery_time_min: float,
) -> float:
    """The committed scalar cost of one replicate's five KPIs, summed in :data:`TERMS` order."""
    raw = {
        "stockout_rate": stockout_rate,
        "spoilage_rate": spoilage_rate,
        "on_hand": avg_on_hand_units,
        "delivery_latency": avg_delivery_time_min,
        "unmet_service": 1.0 - fill_rate,
    }
    normalised = dict(raw)
    normalised["on_hand"] = raw["on_hand"] / ON_HAND_NORMALISER
    normalised["delivery_latency"] = raw["delivery_latency"] / DELIVERY_NORMALISER
    return sum(normalised[term] * WEIGHTS[term] for term in TERMS)


def replicate_cost(sim: SupplyChainSimulation) -> float:
    """A finished replicate priced as ``uplift.e5_suite.production_arm_cost`` prices it."""
    metrics = sim.metrics
    return legacy_cost(
        stockout_rate=metrics.stockout_rate,
        spoilage_rate=metrics.spoilage_rate,
        fill_rate=metrics.fill_rate,
        avg_on_hand_units=metrics.avg_on_hand_units(sim.sim_time_min),
        avg_delivery_time_min=metrics.avg_delivery_time_min,
    )
