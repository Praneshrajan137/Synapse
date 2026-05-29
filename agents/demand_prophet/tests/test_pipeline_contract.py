"""Honesty-contract tests for the Demand Prophet serving path (ADR-040/041).

These do NOT import torch — they exercise the pipeline's contract behaviour
(feature provider, model path vs I-7 fallback, derived confidence, provenance)
with lightweight fakes, so they run on any runner. The torch model internals are
covered by test_model.py on the CI ML stack.
"""

from __future__ import annotations

import numpy as np
from synapse_common.provenance import ConfidenceBasis, FeatureSource

from agents.demand_prophet.inference.pipeline import VALID_HORIZONS, DemandProphetPipeline


# --------------------------------------------------------------------------- #
# Fakes (duck-typed; no torch)
# --------------------------------------------------------------------------- #
class _FakeOnline:
    def __init__(self, skus: list[str]) -> None:
        self._skus = skus

    def to_dict(self) -> dict[str, list]:
        n = len(self._skus)
        return {
            "sku_id": self._skus,
            "demand_features:rolling_7d_mean": [10.0] * n,
            "demand_features:rolling_7d_std": [1.0] * n,
            "demand_features:trend": [0.1] * n,
            "demand_features:dow_seasonality": [0.2] * n,
        }


class _FakeFeast:
    def get_online_features(self, features: object, entity_rows: list[dict]) -> _FakeOnline:
        skus = [r["sku_id"] for r in entity_rows]
        return _FakeOnline(skus)


class _FakeModel:
    version = "v7"

    def predict_quantiles(self, feature_matrix, graph_context) -> dict:  # noqa: ANN001
        n = feature_matrix.shape[0]
        out = {}
        for h in VALID_HORIZONS:
            point = np.full(n, 12.0)
            out[h] = np.stack([point * 0.95, point, point * 1.05], axis=1)  # tight interval
        return out


class _FakeCalibrator:
    def predict_intervals(self, predictions) -> dict:  # noqa: ANN001
        return {h: (predictions[h][:, 0], predictions[h][:, 2]) for h in predictions}


# --------------------------------------------------------------------------- #
# Degraded path
# --------------------------------------------------------------------------- #
def test_degraded_path_is_honest() -> None:
    p = DemandProphetPipeline()  # no deps at all
    forecasts = p.predict(["sku_1", "sku_2"], "store_a", horizons={"1h", "24h"})
    assert len(forecasts) == 2
    assert p.last_provenance.degraded is True
    assert p.last_provenance.feature_source == FeatureSource.FALLBACK
    assert p.last_provenance.confidence_basis == ConfidenceBasis.FALLBACK_FLOOR
    # confidence is derived, never the old constant 0.85
    assert all(abs(f.confidence - 0.85) > 1e-9 for f in forecasts)
    assert all(0.0 <= f.confidence <= 1.0 for f in forecasts)


def test_order_invariance_mr_dp_004() -> None:
    p = DemandProphetPipeline()
    fwd = {f.sku_id: f.horizons for f in p.predict(["a", "b"], "s")}
    rev = {f.sku_id: f.horizons for f in p.predict(["b", "a"], "s")}
    assert fwd == rev


def test_feast_present_but_model_absent_still_degraded() -> None:
    """Feature source is feast, but no model => still degraded (honest)."""
    p = DemandProphetPipeline(feast_client=_FakeFeast())
    p.predict(["sku_1"], "store_a", horizons={"1h"})
    assert p.last_provenance.feature_source == FeatureSource.FEAST
    assert p.last_provenance.degraded is True  # model missing => degraded


# --------------------------------------------------------------------------- #
# Real path
# --------------------------------------------------------------------------- #
def test_real_path_provenance_and_confidence_basis() -> None:
    p = DemandProphetPipeline(
        model=_FakeModel(),
        conformal_calibrator=_FakeCalibrator(),
        feast_client=_FakeFeast(),
    )
    forecasts = p.predict(["sku_1", "sku_2"], "store_a", horizons={"1h", "24h"})
    assert p.last_provenance.degraded is False
    assert p.last_provenance.feature_source == FeatureSource.FEAST
    assert p.last_provenance.confidence_basis == ConfidenceBasis.CONFORMAL_INTERVAL
    assert "v7" in p.last_provenance.model_version
    # A tight interval (±5%) should yield high-but-not-constant confidence.
    assert all(f.confidence > 0.85 for f in forecasts)


def test_real_path_confidence_tracks_interval_width() -> None:
    """Wider conformal intervals must yield lower confidence (ADR-040)."""

    class WideModel(_FakeModel):
        def predict_quantiles(self, feature_matrix, graph_context) -> dict:  # noqa: ANN001
            n = feature_matrix.shape[0]
            return {
                h: np.stack(
                    [np.full(n, 2.0), np.full(n, 12.0), np.full(n, 22.0)], axis=1
                )  # very wide
                for h in VALID_HORIZONS
            }

    tight = DemandProphetPipeline(
        model=_FakeModel(), conformal_calibrator=_FakeCalibrator(), feast_client=_FakeFeast()
    ).predict(["s"], "store", horizons={"1h"})
    wide = DemandProphetPipeline(
        model=WideModel(), conformal_calibrator=_FakeCalibrator(), feast_client=_FakeFeast()
    ).predict(["s"], "store", horizons={"1h"})
    assert tight[0].confidence > wide[0].confidence
