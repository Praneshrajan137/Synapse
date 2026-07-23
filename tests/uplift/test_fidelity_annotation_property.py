"""Property-based tests for the ``FidelityReport`` confidence annotation.

Feature: decision-integrity-uplift-proof
Property 20: Fidelity annotation follows the C34 threshold mapping.

    *For any* fidelity value, the confidence annotation is ``unknown`` (and not
    fidelity-validated) when the KL value is unavailable, ``low_confidence_divergent``
    when the value is strictly greater than the C34 re-sync threshold, and
    ``within_fidelity_bound`` when the value is at or below the threshold.

Validates: Requirements 5.3, 5.4, 5.5
"""
from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from uplift.fidelity import (
    CONFIDENCE_LOW_DIVERGENT,
    CONFIDENCE_UNKNOWN,
    CONFIDENCE_WITHIN_BOUND,
    FidelityReport,
)


# ---------------------------------------------------------------------------
# Strategies — finite floats for KL divergence and threshold, plus ``None`` for
# the unavailable case. Bounded to sensible finite ranges so the comparison to
# the threshold stays meaningful (KL divergence and the C34 threshold are both
# non-negative in practice, but we allow the full finite range to exercise the
# mapping robustly).
# ---------------------------------------------------------------------------
_finite_kl = st.floats(
    min_value=0.0,
    max_value=1e9,
    allow_nan=False,
    allow_infinity=False,
)
_threshold = st.floats(
    min_value=0.0,
    max_value=1e9,
    allow_nan=False,
    allow_infinity=False,
)
# kl_divergence including ``None`` (the unavailable case, R5.3)
_kl_or_none = st.one_of(st.none(), _finite_kl)


# ---------------------------------------------------------------------------
# Property 20: the three-way confidence mapping against the threshold
# ---------------------------------------------------------------------------
@given(kl_divergence=_kl_or_none, threshold=_threshold)
def test_confidence_follows_threshold_mapping(
    kl_divergence: float | None, threshold: float
) -> None:
    """confidence maps None -> unknown, > threshold -> divergent, <= -> within bound."""
    report = FidelityReport(kl_divergence=kl_divergence, threshold=threshold)

    if kl_divergence is None:
        # R5.3: unavailable value -> unknown, and NOT fidelity-validated
        assert report.confidence == CONFIDENCE_UNKNOWN
        assert report.is_fidelity_validated is False
    elif kl_divergence > threshold:
        # R5.4: strictly above threshold -> low-confidence divergent
        assert report.confidence == CONFIDENCE_LOW_DIVERGENT
        assert report.is_fidelity_validated is True
    else:
        # R5.5: at or below threshold -> within fidelity bound
        assert report.confidence == CONFIDENCE_WITHIN_BOUND
        assert report.is_fidelity_validated is True


# ---------------------------------------------------------------------------
# Property 20 (boundary): kl == threshold is annotated within_fidelity_bound (R5.5)
# ---------------------------------------------------------------------------
@given(threshold=_threshold)
def test_boundary_value_is_within_fidelity_bound(threshold: float) -> None:
    """When kl == threshold, the annotation is within_fidelity_bound (R5.5 '<=')."""
    report = FidelityReport(kl_divergence=threshold, threshold=threshold)
    assert report.confidence == CONFIDENCE_WITHIN_BOUND
    assert report.is_fidelity_validated is True


# ---------------------------------------------------------------------------
# Property 20 (None branch): None is never fidelity-validated (R5.3)
# ---------------------------------------------------------------------------
@given(threshold=_threshold)
def test_none_is_unknown_and_not_validated(threshold: float) -> None:
    """A missing KL value maps to unknown and is not presented as validated (R5.3)."""
    report = FidelityReport(kl_divergence=None, threshold=threshold)
    assert report.confidence == CONFIDENCE_UNKNOWN
    assert report.is_fidelity_validated is False
