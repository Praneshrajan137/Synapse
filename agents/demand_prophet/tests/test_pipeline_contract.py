"""Honesty-contract tests for the Demand Prophet serving path (ADR-040/041).

These do NOT import torch — they exercise the pipeline's contract behaviour
(feature provider, model path vs I-7 fallback, derived confidence, provenance)
with lightweight fakes, so they run on any runner. The torch model internals are
covered by test_model.py on the CI ML stack.
"""

from __future__ import annotations

import numpy as np
from synapse_common.provenance import ConfidenceBasis, FeatureSource

from agents.demand_prophet.inference.pipeline import (
    VALID_HORIZONS,
    DemandProphetPipeline,
    is_degraded,
)


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
            "sku_demand_signals:rolling_mean_7d": [10.0] * n,
            "sku_demand_signals:rolling_std_7d": [1.0] * n,
            "sku_demand_signals:trend_slope": [0.1] * n,
            "sku_demand_signals:seasonality_idx": [0.2] * n,
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


class _UnfitCalibrator:
    """A restored-but-unfit calibrator: the defect that produced an unhandled 500.

    ``_build_forecasts`` sees ``intervals is None`` after the pipeline's guard
    catches this, which is the third term of the R9.9 disjunction. Raising rather
    than returning ``None`` is deliberate: it exercises the guard that turns a
    RuntimeError on the first real-path request into honest degradation (I-7).
    """

    def predict_intervals(self, predictions) -> dict:  # noqa: ANN001
        message = "calibrator was restored but never fitted"
        raise RuntimeError(message)


class _WidthVariesBySkuModel:
    """A model whose interval width varies per SKU, so confidence must move.

    ``_FakeModel`` returns the same quantiles for every row, so its confidence is
    identical across SKUs by construction — which is why it cannot be the fixture
    for R9.4. Here the relative width grows with the row index, so a batch of
    three SKUs yields three different ``mean_rel_width`` values and therefore
    three different served confidences.
    """

    version = "v9"

    def predict_quantiles(self, feature_matrix, graph_context) -> dict:  # noqa: ANN001
        n = feature_matrix.shape[0]
        point = np.full(n, 20.0)
        spread = np.array([1.0 + 3.0 * i for i in range(n)], dtype=np.float64)
        return {
            h: np.stack([point - spread, point, point + spread], axis=1) for h in VALID_HORIZONS
        }


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
    """R9.9 term 1 IN ISOLATION: no model degrades even when the other two are healthy.

    The calibrator is supplied deliberately. Without it two terms held at once, so
    the test could not establish that the model term is an INDEPENDENT contributor
    — and independence is exactly what "degradation is the three-term disjunction"
    claims. A resolved feature source plus real intervals do not license `degraded`
    false while no model resolved (I-7).
    """
    p = DemandProphetPipeline(conformal_calibrator=_FakeCalibrator(), feast_client=_FakeFeast())
    p.predict(["sku_1"], "store_a", horizons={"1h"})
    assert p.last_provenance.feature_source == FeatureSource.FEAST
    assert p.last_provenance.degraded is True  # model missing => degraded
    assert p.last_provenance.confidence_basis == ConfidenceBasis.FALLBACK_FLOOR


def test_model_and_calibrator_present_but_fallback_features_still_degraded() -> None:
    """R9.9 term 2 IN ISOLATION: a fallback feature source degrades a real model.

    This is the term a checkpoint-only reading of R9.9 dropped. With no Feast
    client the anti-corruption layer synthesises the features (ADR-041), so the
    forecast is a real model applied to invented inputs — which is not a real
    forecast, and must not be served as one.
    """
    p = DemandProphetPipeline(model=_FakeModel(), conformal_calibrator=_FakeCalibrator())
    p.predict(["sku_1"], "store_a", horizons={"1h"})
    assert p.last_provenance.feature_source == FeatureSource.FALLBACK
    assert p.last_provenance.degraded is True
    assert p.last_provenance.confidence_basis == ConfidenceBasis.FALLBACK_FLOOR


def test_model_and_feast_present_but_no_intervals_still_degraded() -> None:
    """R9.9 term 3 IN ISOLATION: no conformal interval degrades a real model.

    The calibrator here was restored but never fitted, which is the defect that
    raised RuntimeError on the first real-path request and produced an unhandled
    500. The pipeline's guard turns it into honest degradation; this pins that the
    guard also stamps `degraded`, rather than serving raw model bands as if they
    were calibrated ones.
    """
    p = DemandProphetPipeline(
        model=_FakeModel(), conformal_calibrator=_UnfitCalibrator(), feast_client=_FakeFeast()
    )
    p.predict(["sku_1"], "store_a", horizons={"1h"})
    assert p.last_provenance.feature_source == FeatureSource.FEAST
    assert p.last_provenance.degraded is True
    assert p.last_provenance.confidence_basis == ConfidenceBasis.FALLBACK_FLOOR


def test_the_degradation_rule_is_exactly_the_three_term_disjunction() -> None:
    """R9.9 in both directions, over the whole closed input space of the rule.

    Eight combinations, enumerated rather than sampled: `is_degraded` is true iff
    at least one term holds. The all-healthy row is the only false one, which is
    what "no term was dropped" means; and the enumeration reaching both verdicts
    is what stops this passing on a function that always returns true.
    """
    seen: set[bool] = set()
    for model_degraded in (False, True):
        for source in (FeatureSource.FEAST, FeatureSource.FALLBACK):
            for has_intervals in (True, False):
                expected = model_degraded or source == FeatureSource.FALLBACK or not has_intervals
                actual = is_degraded(
                    model_degraded=model_degraded,
                    feature_source=source,
                    has_intervals=has_intervals,
                )
                assert actual is expected, (model_degraded, source, has_intervals)
                seen.add(actual)
    assert seen == {False, True}
    # A resolved checkpoint alone is NOT sufficient for `degraded` false (R9.9).
    assert (
        is_degraded(
            model_degraded=False, feature_source=FeatureSource.FALLBACK, has_intervals=True
        )
        is True
    )
    assert (
        is_degraded(model_degraded=False, feature_source=FeatureSource.FEAST, has_intervals=False)
        is True
    )


def test_confidence_moves_across_skus_on_the_real_path() -> None:
    """R9.4: three SKUs with distinct interval widths yield distinct confidences.

    A confidence that does not move across SKUs is a constant by another name, and
    a constant above the 0.7 HITL threshold makes I-5 escalation impossible to
    fire. Pinned at the four decimal places the payload serves, because a
    difference no operator can see is not a spread.
    """
    p = DemandProphetPipeline(
        model=_WidthVariesBySkuModel(),
        conformal_calibrator=_FakeCalibrator(),
        feast_client=_FakeFeast(),
    )
    forecasts = p.predict(["sku_1", "sku_2", "sku_3"], "store_a", horizons={"1h"})
    assert p.last_provenance.degraded is False
    assert p.last_provenance.confidence_basis == ConfidenceBasis.CONFORMAL_INTERVAL
    assert len(forecasts) == 3
    served = [round(f.confidence, 4) for f in forecasts]
    assert len(set(served)) >= 2, served
    # And the falsifier: a model with identical widths cannot satisfy the floor,
    # so the assertion above is about the model's output and not about rounding.
    flat = DemandProphetPipeline(
        model=_FakeModel(), conformal_calibrator=_FakeCalibrator(), feast_client=_FakeFeast()
    ).predict(["sku_1", "sku_2", "sku_3"], "store_a", horizons={"1h"})
    assert len({round(f.confidence, 4) for f in flat}) == 1


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
