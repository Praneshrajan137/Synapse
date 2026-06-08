"""Serving-path calibration substance (ADR-043) — the tests that would have caught
the two latent defects in the flagship slice, plus the disguised-constant detector.

All torch-free: lightweight fakes stand in for the trained module. Covers:
  * calibrator state round-trips and travels on the serving model;
  * a real model + UNFIT calibrator degrades instead of raising (the latent-500);
  * the degraded confidence is the honest FALLBACK_CONFIDENCE floor (fires I-5),
    not the disguised ~0.71 arithmetic constant that sat above the threshold;
  * on the real path, distinct uncertainty → distinct confidence (no disguised
    constant).
"""

from __future__ import annotations

import json

import numpy as np
import pytest
from synapse_common.model_registry import LoadedModel
from synapse_common.provenance import ConfidenceBasis, FeatureSource

from agents.demand_prophet.config import DemandProphetConfig
from agents.demand_prophet.inference.pipeline import (
    FALLBACK_CONFIDENCE,
    VALID_HORIZONS,
    DemandProphetPipeline,
)
from agents.demand_prophet.inference.serving_model import load_serving_model
from agents.demand_prophet.training.conformal import ConformalCalibrator

HORIZONS = ["15min", "1h", "6h", "24h", "7d"]


# --------------------------------------------------------------------------- #
# Fakes
# --------------------------------------------------------------------------- #
class _FakeOnline:
    def __init__(self, skus: list[str]) -> None:
        self._skus = skus

    def to_dict(self) -> dict[str, list]:
        n = len(self._skus)
        return {
            "sku_id": self._skus,
            "sku_demand_signals:rolling_mean_7d": [10.0] * n,
            "sku_demand_signals:rolling_std_7d": [1.0] * n,
            "sku_demand_signals:trend_slope": [0.1] * n,
            "sku_demand_signals:seasonality_idx": [0.2] * n,
        }


class _FakeFeast:
    def get_online_features(self, features: object, entity_rows: list[dict]) -> _FakeOnline:
        return _FakeOnline([r["sku_id"] for r in entity_rows])


class _FixedModel:
    version = "vfix"

    def predict_quantiles(self, feature_matrix, graph_context) -> dict:  # noqa: ANN001
        n = feature_matrix.shape[0]
        return {
            h: np.stack([np.full(n, 11.0), np.full(n, 12.0), np.full(n, 13.0)], axis=1)
            for h in VALID_HORIZONS
        }


class _PerSkuWidthModel:
    """A model whose interval width grows with the SKU row index → distinct
    per-SKU uncertainty, so a correct pipeline yields distinct confidences."""

    version = "vwidth"

    def predict_quantiles(self, feature_matrix, graph_context) -> dict:  # noqa: ANN001
        n = feature_matrix.shape[0]
        half = np.array([1.0 + 4.0 * i for i in range(n)])
        point = np.full(n, 20.0)
        return {h: np.stack([point - half, point, point + half], axis=1) for h in VALID_HORIZONS}


class _PassthroughCalibrator:
    """A fitted-enough fake: returns the raw band as the interval (no recalibration)."""

    def predict_intervals(self, predictions) -> dict:  # noqa: ANN001
        return {h: (predictions[h][:, 0], predictions[h][:, 2]) for h in predictions}


class _FakeRegistry:
    def __init__(self, loaded: LoadedModel) -> None:
        self._loaded = loaded

    def load(self, base_name: str, *, city: str = "bengaluru", **_: object) -> LoadedModel:
        return self._loaded


def _fitted_calibrator() -> ConformalCalibrator:
    rng = np.random.default_rng(11)
    preds, actuals = {}, {}
    for h in HORIZONS:
        truth = rng.normal(20.0, 6.0, size=1500)
        point = truth + rng.normal(0.0, 4.0, size=1500)
        narrow = 0.25 * 6.0
        preds[h] = np.stack([point - narrow, point, point + narrow], axis=1)
        actuals[h] = truth
    c = ConformalCalibrator(alpha=0.1, coverage_target=0.85)
    c.fit(preds, actuals)
    return c


# --------------------------------------------------------------------------- #
# WS-B: calibrator state persistence
# --------------------------------------------------------------------------- #
def test_calibrator_state_round_trips() -> None:
    c = _fitted_calibrator()
    state = c.to_state()
    # Must be deterministically JSON-serializable (sidecar contract).
    json.dumps(state, sort_keys=True, separators=(",", ":"))

    restored = ConformalCalibrator.from_state(state)
    assert restored.is_calibrated is True
    assert restored.get_adjustments() == c.get_adjustments()
    assert restored.last_coverage_p90 == c.last_coverage_p90

    # Identical adjustments → identical intervals on the same input.
    preds = {
        h: np.stack([np.full(50, 9.0), np.full(50, 12.0), np.full(50, 15.0)], axis=1)
        for h in HORIZONS
    }
    a, b = c.predict_intervals(preds), restored.predict_intervals(preds)
    for h in HORIZONS:
        assert np.allclose(a[h][0], b[h][0]) and np.allclose(a[h][1], b[h][1])


def test_to_state_refuses_unfit_calibrator() -> None:
    with pytest.raises(RuntimeError):
        ConformalCalibrator().to_state()


def test_load_serving_model_attaches_fitted_calibrator() -> None:
    state = _fitted_calibrator().to_state()
    loaded = LoadedModel(
        model=_FixedModel(),
        name="demand_prophet_hgt_tft",
        version="9",
        sha="abc",
        stage="Production",
        degraded=False,
        meta={"calibrator": state},
    )
    model = load_serving_model(_FakeRegistry(loaded))
    assert model is not None
    assert model.calibrator is not None
    assert model.calibrator.is_calibrated is True


def test_load_serving_model_without_sidecar_has_no_calibrator() -> None:
    loaded = LoadedModel(
        model=_FixedModel(),
        name="demand_prophet_hgt_tft",
        version="9",
        sha="abc",
        stage="Production",
        degraded=False,
    )
    model = load_serving_model(_FakeRegistry(loaded))
    assert model is not None
    assert model.calibrator is None


# --------------------------------------------------------------------------- #
# WS-B: the latent-500 regression
# --------------------------------------------------------------------------- #
def test_real_model_with_unfit_calibrator_degrades_not_crashes() -> None:
    """A real model paired with an UNFIT calibrator must NOT raise.

    Before the guard, ConformalCalibrator().predict_intervals raised RuntimeError
    on the first real-path request → unhandled 500. Now it degrades honestly.
    """
    pipe = DemandProphetPipeline(
        model=_FixedModel(),
        conformal_calibrator=ConformalCalibrator(),  # never fit
        feast_client=_FakeFeast(),
    )
    forecasts = pipe.predict(["sku_1", "sku_2"], "store_a", horizons={"1h", "24h"})
    assert len(forecasts) == 2
    # No calibrated interval was produced → honest degradation.
    assert pipe.last_provenance.degraded is True
    assert all(0.0 <= f.confidence <= 1.0 for f in forecasts)


# --------------------------------------------------------------------------- #
# WS-F: honest degraded confidence fires I-5
# --------------------------------------------------------------------------- #
def test_degraded_confidence_is_floor_and_would_escalate() -> None:
    pipe = DemandProphetPipeline()  # fully degraded
    forecasts = pipe.predict(["a", "b"], "s", horizons={"1h", "24h"})
    assert all(f.confidence == FALLBACK_CONFIDENCE for f in forecasts)
    # The disguised ~0.71 constant sat ABOVE the 0.7 HITL threshold and suppressed
    # escalation; the honest floor sits below it, so I-5 fires on degraded output.
    threshold = DemandProphetConfig().confidence_threshold
    assert all(f.confidence < threshold for f in forecasts)
    assert pipe.last_provenance.confidence_basis == ConfidenceBasis.FALLBACK_FLOOR


# --------------------------------------------------------------------------- #
# WS-G: disguised-constant detector — distinct uncertainty → distinct confidence
# --------------------------------------------------------------------------- #
def test_real_path_confidence_varies_with_per_sku_uncertainty() -> None:
    pipe = DemandProphetPipeline(
        model=_PerSkuWidthModel(),
        conformal_calibrator=_PassthroughCalibrator(),
        feast_client=_FakeFeast(),
    )
    forecasts = pipe.predict(["sku_1", "sku_2", "sku_3"], "store_a", horizons={"1h"})
    assert pipe.last_provenance.degraded is False
    assert pipe.last_provenance.feature_source == FeatureSource.FEAST
    confidences = [f.confidence for f in forecasts]
    # Wider interval (higher row index) must mean strictly lower confidence, and
    # the set must not collapse to a single disguised constant.
    assert len(set(confidences)) == len(confidences)
    assert confidences[0] > confidences[1] > confidences[2]


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
