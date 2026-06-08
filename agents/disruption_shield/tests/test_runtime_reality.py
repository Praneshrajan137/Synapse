"""INV-DS-008 — runtime reality for the fitted anomaly detector (ADR-043, C42).

Torch-free (sklearn IsolationForest): fits a tiny detector, wraps it in the serving
model, and proves the served confidence is the real anomaly-score margin — a
decisive input scores strictly higher confidence than a borderline one, never the
config constant. The CI runtime gate (`runtime_substance --agent disruption_shield`)
proves the same on the smoke checkpoint.
"""

from __future__ import annotations

import numpy as np
from sklearn.ensemble import IsolationForest

from agents.disruption_shield.inference.serving_model import (
    DisruptionServingModel,
    build_disruption_model,
)


def _fitted_model() -> DisruptionServingModel:
    rng = np.random.default_rng(0)
    x = np.vstack([rng.normal(0, 1, (200, 12)), rng.normal(5, 1.5, (20, 12))])
    iforest = IsolationForest(n_estimators=80, contamination=0.1, random_state=0).fit(x)
    scores = -iforest.decision_function(x)
    return build_disruption_model(
        {"iforest": iforest, "score_lo": float(scores.min()), "score_hi": float(scores.max())},
        {"version": "full_test"},
    )


def test_builder_produces_a_real_detector() -> None:
    model = _fitted_model()
    assert model.is_real
    assert model.version == "full_test"


def test_inv_ds_008_confidence_is_real_anomaly_margin() -> None:
    """INV-DS-008 — confidence varies with the anomaly-score margin, not constant."""
    model = _fitted_model()
    decisive = model.confidence(np.zeros((1, 12)))      # clearly normal
    borderline = model.confidence(np.full((1, 12), 2.5))  # near the boundary
    # INV-DS-008: a decisive call is more confident than a borderline one; non-constant.
    assert decisive > borderline
    assert 0.5 <= borderline <= 0.99
    assert decisive != borderline


def test_anomaly_probability_separates_normal_from_anomalous() -> None:
    model = _fitted_model()
    p_normal = float(model.anomaly_probability(np.zeros((1, 12)))[0])
    p_anom = float(model.anomaly_probability(np.full((1, 12), 6.0))[0])
    assert p_anom > p_normal
