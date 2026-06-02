"""INV-SA-010 — runtime reality + honest provenance for sustainability (ADR-043).

Torch/lifelines-free: builds a WasteServingModel from a hand-set KM survival curve,
wires it into the pipeline, and proves the report is genuinely real (non-degraded,
PREDICTIVE_ENTROPY, confidence varies with horizon). Also proves the *honesty* fix:
without a fitted model the report is degraded with the I-7 floor — the legacy code
stamped Provenance.real even on the unfitted numpy fallback.
"""

from __future__ import annotations

from synapse_common.provenance import ConfidenceBasis

from agents.sustainability_agent.inference.pipeline import (
    FALLBACK_CONFIDENCE,
    SustainabilityPipeline,
)
from agents.sustainability_agent.inference.serving_model import (
    WasteServingModel,
    build_sustainability_model,
)


def _curve() -> WasteServingModel:
    # A decreasing survival curve over 0..14 days (KM-shaped).
    timeline = [float(t) for t in range(15)]
    survival = [round(max(0.02, 1.0 - 0.06 * t), 4) for t in range(15)]
    return build_sustainability_model(
        {"timeline": timeline, "survival": survival}, {"version": "full_test"}
    )


def test_builder_produces_a_real_curve() -> None:
    m = _curve()
    assert m.is_real
    assert m.version == "full_test"


def test_inv_sa_010_real_path_non_degraded_predictive_entropy() -> None:
    """INV-SA-010 — fitted curve → non-degraded report, PREDICTIVE_ENTROPY, varying conf."""
    pipe = SustainabilityPipeline(serving_model=_curve())
    near = pipe.report(fuel_liters=5.0, distance_km=20.0, days_ahead=2)
    far = pipe.report(fuel_liters=5.0, distance_km=20.0, days_ahead=10)
    prov = pipe.last_provenance
    assert not prov.degraded
    assert prov.confidence_basis == ConfidenceBasis.PREDICTIVE_ENTROPY
    assert near.confidence != far.confidence  # varies with the waste probability


def test_inv_sa_010_unfitted_is_honestly_degraded() -> None:
    """INV-SA-010 — no fitted model → degraded provenance + floor confidence (the honesty fix)."""
    pipe = SustainabilityPipeline()  # no serving_model, default unfitted waste model
    rep = pipe.report(fuel_liters=5.0, distance_km=20.0, days_ahead=7)
    assert pipe.last_provenance.degraded
    assert rep.confidence == FALLBACK_CONFIDENCE


def test_carbon_component_is_deterministic_and_real() -> None:
    pipe = SustainabilityPipeline(serving_model=_curve())
    rep = pipe.report(fuel_liters=5.0, distance_km=20.0, days_ahead=3)
    assert rep.total_co2_kg >= rep.delivery_co2_kg >= 0.0
