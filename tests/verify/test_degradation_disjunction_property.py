"""Property-based test for the degradation contract of the Demand_Forecaster (E4).

Feature: decision-quality-proof, Property 70: Degradation is exactly the three-term
disjunction, and confidence moves across SKUs

    *For any* combination of model availability, feature source and calibrated-interval
    availability, the Demand_Forecaster reports ``degraded`` true iff at least one of
    those three terms holds -- no term dropped and no fourth condition smuggled in -- and
    on the healthy path a batch of at least three SKUs carrying distinct feature vectors
    is served at least two distinct confidence values at the four decimal places it
    serves.

What "exactly" means here, and why it needs both directions
----------------------------------------------------------

R9.9 was widened from ``WHILE no checkpoint is published`` to the full disjunction in
``agents/demand_prophet/inference/pipeline.py`` (a **tightening**: strictly more responses
are obliged to report ``degraded``). Two failure modes sit either side of that:

* **A dropped term** would let a real model applied to synthesised features, or a real
  model whose restored calibrator produced no interval, be served as a healthy forecast.
  Facets 1 and 2 close it: the rule is enumerated over its whole closed input space, and
  each single term is shown to flip the verdict from the all-healthy state.
* **A smuggled fourth condition** would make ``degraded`` fire on something R9.9 does not
  name, which is not an honesty win but an unfalsifiable gate: nobody could say what makes
  it wrong. Facet 3 closes it by asserting the rule's arity from its own signature and by
  asserting the verdict is a function of exactly those three inputs.

Why the confidence half lives in the same property. A constant confidence and a false
``degraded`` are one defect seen twice: ``packages/synapse_common/provenance.py`` records
that a constant confidence above the HITL threshold makes I-5 (confidence-gated
escalation) impossible to fire, and the honest floor is emitted only on the degraded path.
So "degraded is exact" and "confidence moves" are the two halves of one contract -- the
first says when the floor is owed, the second says the non-floor value is a measurement.

Subjects, and which surface each facet drives
---------------------------------------------

* ``pipeline.is_degraded`` -- the extracted rule (facets 1, 2, 3). Pure, so the rule can
  be discharged by enumeration rather than only sampled.
* ``DemandProphetPipeline.predict`` + ``last_provenance`` -- the serving path (facets 4,
  5). Without this the property would pin a helper the pipeline might not call.
* ``scripts.audit.runtime_substance.confidence_moves`` -- the CI gate's own predicate
  (facets 5, 6, 7), driven directly so the gate and this property cannot disagree about
  what "moves" means. That clause previously fired only on total collapse to the fallback
  floor; facet 6 asserts it now fails a constant nowhere near that floor.

Non-vacuity. Facet 2's enumeration is asserted to reach BOTH verdicts, facet 5 is paired
with facet 7's falsifier (a model with identical widths must NOT satisfy the spread
floor), and facet 6 asserts both branches of the gate predicate. Every "must hold"
assertion below therefore has a demonstrated way to fail.

I-0 and $0: nothing is trained, fetched, or bound to a port. The model, calibrator and
feature store are in-process fakes and the whole file is arithmetic over small numpy
arrays, which is why it is not slow-marked and belongs in the fast selection.

``max_examples`` is never set here -- the budget comes from the root ``conftest.py``
profiles (``dev``=10, ``heavy``=100, ``ci``/``default``=500, ``nightly``=5000).

**Validates: Requirements 8.4, 9.3, 9.4, 9.9**
"""

from __future__ import annotations

import inspect
from typing import TYPE_CHECKING, Any, Final

import numpy as np
import numpy.typing as npt
from hypothesis import given
from hypothesis import strategies as st
from synapse_common.provenance import ConfidenceBasis, FeatureSource

from agents.demand_prophet.inference.pipeline import (
    FALLBACK_CONFIDENCE,
    VALID_HORIZONS,
    DemandProphetPipeline,
    is_degraded,
)
from scripts.audit.runtime_substance import (
    CONFIDENCE_DECIMALS,
    MIN_DISTINCT_CONFIDENCES,
    MIN_DISTINCT_ENTITIES,
    StubFeatureStore,
    confidence_moves,
    served_confidences,
)

if TYPE_CHECKING:  # annotation-only: `Callable` appears in signatures, never at runtime
    from collections.abc import Callable

Matrix = npt.NDArray[np.float64]

#: The three keyword parameters R9.9 names, and nothing else. Asserted against the
#: rule's own signature so a fourth term cannot be added without failing facet 3.
DECLARED_TERMS: Final[frozenset[str]] = frozenset(
    {"model_degraded", "feature_source", "has_intervals"}
)

#: Every feature source a served response can carry. Taken from the enum rather than
#: from a hand-picked pair, so a source added to the domain enters this property
#: automatically instead of silently escaping it.
ALL_FEATURE_SOURCES: Final[tuple[FeatureSource, ...]] = tuple(FeatureSource)

#: The feature template the runtime gate itself uses: four refs whose values differ per
#: entity index. Reused rather than re-invented so "distinct feature vectors" means the
#: same thing here and in the gate.
FEATURE_TEMPLATE: Final[dict[str, Callable[[int], float]]] = {
    "sku_demand_signals:rolling_mean_7d": lambda i: 8.0 + 3.0 * i,
    "sku_demand_signals:rolling_std_7d": lambda i: 1.0 + 0.5 * i,
    "sku_demand_signals:trend_slope": lambda i: 0.05 * (i + 1),
    "sku_demand_signals:seasonality_idx": lambda i: 0.2 + 0.1 * i,
}


# ---------------------------------------------------------------------------
# In-process fakes. No torch, no Feast, no sockets.
# ---------------------------------------------------------------------------


class _Online:
    """The shape a Feast online response presents to the anti-corruption layer."""

    def __init__(self, skus: list[str]) -> None:
        self._skus = skus

    def to_dict(self) -> dict[str, list[Any]]:
        count = len(self._skus)
        payload: dict[str, list[Any]] = {"sku_id": list(self._skus)}
        for ref, builder in FEATURE_TEMPLATE.items():
            payload[ref] = [builder(index) for index in range(count)]
        return payload


class ResolvedFeast:
    """A reachable online store, so ``feature_source`` resolves to FEAST."""

    def get_online_features(self, features: object, entity_rows: list[dict[str, Any]]) -> _Online:
        return _Online([str(row["sku_id"]) for row in entity_rows])


class FlatModel:
    """A real model whose interval width is identical for every SKU.

    The honest fixture for the degradation facets, and the falsifier for the spread
    facet: its confidence cannot move, so a spread assertion that passed against it
    would be measuring rounding rather than the model.
    """

    version = "flat"

    def predict_quantiles(self, feature_matrix: Matrix, graph_context: object) -> dict[str, Matrix]:
        rows = int(feature_matrix.shape[0])
        point = np.full(rows, 20.0)
        return {
            horizon: np.stack([point * 0.95, point, point * 1.05], axis=1)
            for horizon in VALID_HORIZONS
        }


class WidthVariesBySkuModel:
    """A real model whose relative interval width grows with the SKU index."""

    version = "spread"

    def __init__(self, step: float) -> None:
        self._step = step

    def predict_quantiles(self, feature_matrix: Matrix, graph_context: object) -> dict[str, Matrix]:
        rows = int(feature_matrix.shape[0])
        point = np.full(rows, 20.0)
        spread = np.array([1.0 + self._step * index for index in range(rows)], dtype=np.float64)
        return {
            horizon: np.stack([point - spread, point, point + spread], axis=1)
            for horizon in VALID_HORIZONS
        }


class RealCalibrator:
    """A fitted calibrator: returns the model's own outer quantiles as intervals."""

    last_coverage_p90 = 0.9

    def predict_intervals(
        self, predictions: dict[str, Matrix]
    ) -> dict[str, tuple[Matrix, Matrix]]:
        return {
            horizon: (predictions[horizon][:, 0], predictions[horizon][:, 2])
            for horizon in predictions
        }


class UnfitCalibrator:
    """Restored but never fitted: the pipeline's guard turns this into no intervals."""

    def predict_intervals(
        self, predictions: dict[str, Matrix]
    ) -> dict[str, tuple[Matrix, Matrix]]:
        message = "calibrator was restored but never fitted"
        raise RuntimeError(message)


def build_pipeline(
    *, with_model: bool, with_feast: bool, with_intervals: bool, step: float = 0.0
) -> DemandProphetPipeline:
    """One pipeline per point of the three-term space, wired only through its ctor.

    ``step`` selects the flat model (``0.0``) or a per-SKU spread, so the degradation
    facets and the spread facet share one construction path and cannot diverge in how
    they wire the serving dependencies.
    """
    model: FlatModel | WidthVariesBySkuModel | None = None
    if with_model:
        model = FlatModel() if step == 0.0 else WidthVariesBySkuModel(step)
    calibrator: RealCalibrator | UnfitCalibrator = (
        RealCalibrator() if with_intervals else UnfitCalibrator()
    )
    return DemandProphetPipeline(
        model=model,
        conformal_calibrator=calibrator,
        feast_client=ResolvedFeast() if with_feast else None,
    )


def distinct_sku_batch() -> tuple[list[str], tuple[tuple[float, ...], ...]]:
    """A batch that satisfies R9.4's input precondition, proven rather than assumed."""
    skus = [f"sku_{index}" for index in range(MIN_DISTINCT_ENTITIES)]
    vectors = StubFeatureStore(FEATURE_TEMPLATE).feature_vectors(skus)
    return skus, vectors


def expected_degraded(*, with_model: bool, with_feast: bool, with_intervals: bool) -> bool:
    """R9.9 restated from the CONSTRUCTION, independently of the subject.

    Written out rather than delegated to ``is_degraded`` so the pipeline facet compares
    two implementations of the rule instead of comparing the rule with itself.
    """
    return (not with_model) or (not with_feast) or (not with_intervals)


# ---------------------------------------------------------------------------
# Facet 1 - the rule is exactly the disjunction, across its whole closed space
# ---------------------------------------------------------------------------


# Feature: decision-quality-proof, Property 70: Degradation is exactly the three-term disjunction,
# and confidence moves across SKUs
@given(
    model_degraded=st.booleans(),
    feature_source=st.sampled_from(ALL_FEATURE_SOURCES),
    has_intervals=st.booleans(),
)
def test_degradation_is_true_iff_at_least_one_declared_term_holds(
    model_degraded: bool, feature_source: FeatureSource, has_intervals: bool
) -> None:
    """R9.9: true iff any term holds, with the expectation restated independently.

    **Validates: Requirements 9.9**
    """
    expected = model_degraded or feature_source == FeatureSource.FALLBACK or not has_intervals
    assert (
        is_degraded(
            model_degraded=model_degraded,
            feature_source=feature_source,
            has_intervals=has_intervals,
        )
        is expected
    )


# ---------------------------------------------------------------------------
# Facet 2 - no term is dropped, and the space reaches both verdicts
# ---------------------------------------------------------------------------


def test_flipping_any_single_term_from_the_healthy_state_reports_degraded() -> None:
    """R9.3, R9.9: each term is an independent sufficient condition for degradation.

    Exhaustive rather than sampled: the space is ``2 x len(FeatureSource) x 2``, small
    enough that "for all" can be discharged by enumeration, and an enumeration cannot
    miss the one row a sampler might. Asserting that both verdicts are reached is what
    stops this passing on a rule that always returns true.

    **Validates: Requirements 9.3, 9.9**
    """
    assert (
        is_degraded(model_degraded=False, feature_source=FeatureSource.FEAST, has_intervals=True)
        is False
    )
    # Term 1 alone: no resolved model.
    assert (
        is_degraded(model_degraded=True, feature_source=FeatureSource.FEAST, has_intervals=True)
        is True
    )
    # Term 2 alone: a resolved checkpoint is NOT sufficient for health (R9.9).
    assert (
        is_degraded(
            model_degraded=False, feature_source=FeatureSource.FALLBACK, has_intervals=True
        )
        is True
    )
    # Term 3 alone: a restored calibrator that returned no interval.
    assert (
        is_degraded(model_degraded=False, feature_source=FeatureSource.FEAST, has_intervals=False)
        is True
    )

    verdicts: set[bool] = set()
    for model_degraded in (False, True):
        for source in ALL_FEATURE_SOURCES:
            for has_intervals in (True, False):
                verdicts.add(
                    is_degraded(
                        model_degraded=model_degraded,
                        feature_source=source,
                        has_intervals=has_intervals,
                    )
                )
    assert verdicts == {False, True}
    assert FeatureSource.FALLBACK in ALL_FEATURE_SOURCES
    assert len(ALL_FEATURE_SOURCES) >= 2


# ---------------------------------------------------------------------------
# Facet 3 - no fourth condition
# ---------------------------------------------------------------------------


def test_the_rule_admits_exactly_the_three_declared_terms_and_nothing_else() -> None:
    """R9.9's other direction: a fourth condition cannot be smuggled in.

    Two assertions, because either alone is evadable. The signature check catches a new
    INPUT; the repeated-enumeration check catches a hidden input reached through module
    or class state, which a signature cannot see -- the same verdict must come back for
    the same three arguments on every call.

    **Validates: Requirements 9.9**
    """
    parameters = inspect.signature(is_degraded).parameters
    assert set(parameters) == DECLARED_TERMS, sorted(parameters)
    # Keyword-only, so a positional call cannot silently reorder the terms.
    assert all(
        parameter.kind is inspect.Parameter.KEYWORD_ONLY for parameter in parameters.values()
    )

    for _ in range(2):
        for model_degraded in (False, True):
            for source in ALL_FEATURE_SOURCES:
                for has_intervals in (True, False):
                    expected = (
                        model_degraded or source == FeatureSource.FALLBACK or not has_intervals
                    )
                    assert (
                        is_degraded(
                            model_degraded=model_degraded,
                            feature_source=source,
                            has_intervals=has_intervals,
                        )
                        is expected
                    )


# ---------------------------------------------------------------------------
# Facet 4 - the serving path reports the same rule
# ---------------------------------------------------------------------------


@given(
    with_model=st.booleans(),
    with_feast=st.booleans(),
    with_intervals=st.booleans(),
    skus=st.lists(
        st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789", min_size=1, max_size=6),
        min_size=1,
        max_size=4,
        unique=True,
    ),
)
def test_the_served_provenance_reports_degraded_exactly_when_the_rule_says_so(
    with_model: bool, with_feast: bool, with_intervals: bool, skus: list[str]
) -> None:
    """R8.4, R9.3, R9.9: the pipeline's provenance is the rule, not a second reading.

    Without this facet the property would pin a helper the serving path might not call.
    The expectation is derived from the CONSTRUCTION -- which dependencies were supplied
    -- rather than read back from the pipeline, so the two sides stay independent.

    Every response carries the verdict, not merely the last one: ``confidence_basis`` is
    the honest floor on the degraded path and the conformal basis otherwise, and it is
    never ``CONSTANT``, which ``provenance.py`` forbids outright.

    **Validates: Requirements 8.4, 9.3, 9.9**
    """
    pipeline = build_pipeline(
        with_model=with_model, with_feast=with_feast, with_intervals=with_intervals
    )
    forecasts = pipeline.predict(skus, "store_x", horizons={"1h", "24h"})
    assert len(forecasts) == len(skus)

    expected = expected_degraded(
        with_model=with_model, with_feast=with_feast, with_intervals=with_intervals
    )
    provenance = pipeline.last_provenance
    assert provenance.degraded is expected
    assert provenance.confidence_basis is not ConfidenceBasis.CONSTANT

    if expected:
        assert provenance.confidence_basis is ConfidenceBasis.FALLBACK_FLOOR
        # The floor is emitted on EVERY response, not averaged into one of them.
        assert all(forecast.confidence == FALLBACK_CONFIDENCE for forecast in forecasts)
    else:
        assert provenance.confidence_basis is ConfidenceBasis.CONFORMAL_INTERVAL
        assert provenance.feature_source is FeatureSource.FEAST
        assert all(0.0 <= forecast.confidence <= 1.0 for forecast in forecasts)


# ---------------------------------------------------------------------------
# Facets 5, 6, 7 - confidence moves across SKUs, and the gate agrees
# ---------------------------------------------------------------------------


@given(step=st.floats(min_value=0.5, max_value=6.0, allow_nan=False, allow_infinity=False))
def test_confidence_moves_across_skus_carrying_distinct_feature_vectors(step: float) -> None:
    """R9.4: at least two distinct values at the decimal places actually served.

    The batch's input precondition is established first and by construction -- at least
    three SKUs whose feature vectors are provably distinct -- because a spread required
    over identical inputs would be an unsatisfiable assertion, and a spread reported
    over identical inputs would be evidence of nondeterminism rather than of a live
    model.

    **Validates: Requirements 9.4**
    """
    skus, vectors = distinct_sku_batch()
    assert len(skus) >= MIN_DISTINCT_ENTITIES
    assert len(set(vectors)) >= MIN_DISTINCT_ENTITIES

    pipeline = build_pipeline(with_model=True, with_feast=True, with_intervals=True, step=step)
    forecasts = pipeline.predict(skus, "store_x", horizons={"1h", "24h"})
    assert pipeline.last_provenance.degraded is False

    served = served_confidences([forecast.confidence for forecast in forecasts])
    assert len(set(served)) >= MIN_DISTINCT_CONFIDENCES, served
    assert confidence_moves(served) is True
    # Not the floor, and not a value the floor could be mistaken for.
    assert all(value != FALLBACK_CONFIDENCE for value in served), served


@given(
    constant=st.floats(min_value=0.01, max_value=0.99, allow_nan=False, allow_infinity=False),
    count=st.integers(min_value=MIN_DISTINCT_ENTITIES, max_value=8),
)
def test_a_constant_confidence_fails_the_gate_even_far_from_the_fallback_floor(
    constant: float, count: int
) -> None:
    """R9.4: the tightening, asserted exactly where the old clause was blind.

    ``runtime_substance`` previously failed only on
    ``all(c == FALLBACK_CONFIDENCE for c in confs)``, so three SKUs all returning the
    same ``0.7231`` passed -- and that is the dangerous case, not the harmless one,
    because a constant above the 0.7 HITL threshold looks healthy while making I-5
    unable to fire. Both branches of the predicate are asserted, so it is shown to
    discriminate rather than merely to refuse.

    **Validates: Requirements 9.4**
    """
    flat = [constant] * count
    assert confidence_moves(flat) is False
    assert len(set(served_confidences(flat))) == 1

    # Halving one value moves it by at least 0.005, which four decimal places cannot
    # hide, so the accepting branch is reached unconditionally.
    moved = [*flat[:-1], constant / 2.0]
    assert served_confidences([constant / 2.0]) != served_confidences([constant])
    assert confidence_moves(moved) is True


def test_a_flat_model_cannot_satisfy_the_spread_floor() -> None:
    """R9.4's falsifier: the spread facet is about the model, not about rounding.

    A model returning identical quantiles for every SKU must NOT satisfy R9.4, even
    though its features differ. Without this, a resolver returning an arbitrary
    per-index confidence would satisfy the facet above while proving nothing about the
    conformal interval.

    **Validates: Requirements 9.4**
    """
    skus, vectors = distinct_sku_batch()
    assert len(set(vectors)) >= MIN_DISTINCT_ENTITIES

    forecasts = build_pipeline(with_model=True, with_feast=True, with_intervals=True).predict(
        skus, "store_x", horizons={"1h", "24h"}
    )
    served = served_confidences([forecast.confidence for forecast in forecasts])
    assert len(set(served)) == 1, served
    assert confidence_moves(served) is False
    assert CONFIDENCE_DECIMALS == 4
