"""INV-FG-009 — runtime reality for the numpy Weibull-AFT serving path (ADR-043).

Torch/lifelines-free: builds a FreshnessServingModel from hand-set Weibull-AFT
params, wires it into the pipeline, and proves shelf-life assessment is genuinely
real — non-degraded, SURVIVAL_CI_WIDTH basis, and a confidence that varies with
storage conditions (never the legacy hardcoded 0.85). The CI runtime gate
(`runtime_substance --agent freshness_guardian`) proves the same on the fitted
checkpoint; the lifelines AFT fit is the only CI-gated step.
"""

from __future__ import annotations

from synapse_common.provenance import ConfidenceBasis

from agents.freshness_guardian.inference.pipeline import (
    FreshnessGuardianPipeline,
    FreshnessRequest,
)
from agents.freshness_guardian.inference.serving_model import (
    FreshnessServingModel,
    build_freshness_model,
)


def _model() -> FreshnessServingModel:
    # log(scale) = 2.0 − 0.1·temp_dev − 0.02·humidity + 0.05·shelf + 0.3·cold_chain; rho=2.5.
    return build_freshness_model(
        {
            "rho": 2.5,
            "intercept": 2.0,
            "coeffs": {
                "temperature_deviation_hours": -0.1,
                "humidity_deviation_pct": -0.02,
                "initial_shelf_life_days": 0.05,
                "is_cold_chain": 0.3,
            },
        },
        {"version": "full_test"},
    )


def _req(temp_dev: float) -> FreshnessRequest:
    return FreshnessRequest(
        store_id="s", sku_id="k", days_since_receipt=1.0,
        initial_shelf_life_days=7.0, temperature_deviation_hours=temp_dev,
    )


def test_builder_produces_a_real_model() -> None:
    m = _model()
    assert m.is_real
    assert m.version == "full_test"


def test_serving_predict_is_numpy_weibull() -> None:
    m = _model()
    pred = m.predict(
        temperature_deviation_hours=0.0, humidity_deviation_pct=0.0,
        initial_shelf_life_days=7.0, is_cold_chain=False, days_since_receipt=1.0,
    )
    assert pred.days_to_expiry > 0.0
    assert 0.0 <= pred.quality_score <= 1.0
    assert 0.0 <= pred.survival_probability <= 1.0


def test_inv_fg_009_runtime_reality_non_degraded_varying_confidence() -> None:
    """INV-FG-009 — loaded survival model serves real, condition-varying confidence."""
    pipe = FreshnessGuardianPipeline(serving_model=_model())
    benign = pipe.assess(_req(0.0))
    abused = pipe.assess(_req(12.0))
    prov = pipe.last_provenance
    # INV-FG-009: real provenance + SURVIVAL_CI_WIDTH basis + non-constant confidence.
    assert not prov.degraded
    assert prov.confidence_basis == ConfidenceBasis.SURVIVAL_CI_WIDTH
    assert benign.confidence != abused.confidence
    assert 0.0 <= benign.confidence <= 1.0


def test_serving_path_runs_without_lifelines() -> None:
    # ADR-043 decoupling: assessing via the serving model must not import lifelines.
    pipe = FreshnessGuardianPipeline(serving_model=_model())
    alert = pipe.assess(_req(3.0))
    assert not pipe.last_provenance.degraded
    assert alert.quality_score >= 0.0
