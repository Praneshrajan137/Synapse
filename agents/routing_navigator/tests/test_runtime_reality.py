"""INV-RN-010 — runtime reality for the calibrated CVRPTW solver (ADR-043, C42).

Torch-free. Builds a :class:`RoutingServingModel` from a synthetic optimality-gap
calibration (no artifact dependency), wires it into the pipeline, and proves the
Tier-2 output is genuinely real: non-degraded, OPTIMALITY_GAP basis, and a
*calibrated* confidence that is monotone in solution quality and never the greedy
Tier-1 floor. The CI runtime gate (`runtime_substance --agent routing_navigator`)
proves the same against the actual smoke checkpoint.
"""

from __future__ import annotations

from synapse_common.provenance import ConfidenceBasis

from agents.routing_navigator.inference.pipeline import RoutingNavigatorPipeline
from agents.routing_navigator.inference.serving_model import (
    RoutingServingModel,
    build_routing_model,
)


def _calibration() -> dict:
    """A plausible empirical LB/achieved ratio distribution from training."""
    ratios = [round(0.30 + 0.01 * i, 4) for i in range(60)]  # 0.30 .. 0.89
    return {"ratios": ratios, "q_lo": 0.35, "q_med": 0.59, "q_hi": 0.85, "n_instances": 60}


def _orders(spread: float, n: int) -> list[dict]:
    return [
        {
            "order_id": f"o{i}",
            "lat": 12.97 + spread * i,
            "lon": 77.59 + spread * i,
            "weight_kg": 2.0,
            "due_min": 300.0,
        }
        for i in range(1, n + 1)
    ]


def test_builder_produces_a_real_calibrated_model() -> None:
    model = build_routing_model(_calibration(), {"version": "full_abc123"})
    assert isinstance(model, RoutingServingModel)
    assert model.is_real
    assert model.version == "full_abc123"


def test_calibrated_confidence_is_monotone_in_quality() -> None:
    # A near-optimal route (ratio close to 1) must score strictly higher than a
    # loose one (small ratio) — the calibrated percentile is monotone, not constant.
    model = build_routing_model(_calibration(), {})
    good = model.calibrated_confidence(lb=9.0, achieved=10.0)  # ratio 0.90
    poor = model.calibrated_confidence(lb=3.0, achieved=10.0)  # ratio 0.30
    assert 0.5 <= poor < good <= 0.99


def test_inv_rn_010_runtime_reality_non_degraded_calibrated() -> None:
    """INV-RN-010 — calibrated Tier-2 solver serves real, non-floor confidence."""
    model = build_routing_model(_calibration(), {"version": "full_abc123"})
    pipe = RoutingNavigatorPipeline(solver_model=model)
    plans = pipe.route(
        _orders(0.01, 5), [{"rider_id": "r1", "capacity_kg": 30.0}], "store_x", use_student=False
    )
    prov = pipe.last_provenance
    # INV-RN-010: real provenance + OPTIMALITY_GAP basis + non-floor confidence.
    assert plans, "Tier-2 solver returned no plans on a valid instance"
    assert not prov.degraded
    assert prov.confidence_basis == ConfidenceBasis.OPTIMALITY_GAP
    assert all(p.confidence != 0.5 for p in plans)
    assert all(0.5 <= p.confidence <= 0.99 for p in plans)


def test_greedy_tier1_is_honestly_degraded() -> None:
    # The Tier-1 student path is the I-7 fallback: floor confidence + degraded.
    model = build_routing_model(_calibration(), {})
    pipe = RoutingNavigatorPipeline(solver_model=model)
    plans = pipe.route(
        _orders(0.01, 5), [{"rider_id": "r1", "capacity_kg": 30.0}], "store_x", use_student=True
    )
    assert pipe.last_provenance.degraded
    assert all(p.confidence == 0.5 for p in plans)
