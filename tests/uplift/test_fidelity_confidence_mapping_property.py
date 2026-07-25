"""Property-based test for the twin-fidelity confidence mapping.

Feature: core-purpose-uplift, Property 20: Fidelity confidence maps KL divergence
deterministically.

    *For any* KL value and threshold, ``FidelityReport.confidence`` is ``unknown``
    when the value is unavailable, ``low_confidence_divergent`` when strictly above
    the threshold, and ``within_fidelity_bound`` when at or below the threshold;
    ``within_fidelity_bound`` is reported as outside the bound whenever the value
    exceeds the threshold.

    Requirement 6.5: "THE Uplift_Harness SHALL compute the twin-vs-reference KL
    divergence and report whether the result is within the committed Fidelity_Bound
    threshold."
    Requirement 6.6: "IF the twin KL divergence exceeds the committed Fidelity_Bound
    threshold, THEN THE Uplift_Harness SHALL report the result as outside the
    Fidelity_Bound."

``FidelityReport`` is exercised directly with synthetic values — no twin run, no live
C34 gauge read — so the property is pure, fast, and $0. The generator deliberately
includes the unavailable (``None``) case and the exact boundary ``kl == threshold``,
plus values a hair either side of it.

**Validates: Requirements 6.5, 6.6**
"""
from __future__ import annotations

import math

from hypothesis import given, settings
from hypothesis import strategies as st

from uplift.fidelity import (
    CONFIDENCE_LOW_DIVERGENT,
    CONFIDENCE_UNKNOWN,
    CONFIDENCE_WITHIN_BOUND,
    FidelityReport,
)

# Thresholds span the realistic C34 re-sync band (default 0.1) plus the degenerate
# ``0.0`` threshold, where every positive divergence must fall outside the bound.
_thresholds = st.floats(min_value=0.0, max_value=10.0, allow_nan=False, allow_infinity=False)

# Offsets applied to the threshold so the generator lands on the decision boundary
# and its immediate neighbourhood, not just far-away values.
_boundary_offsets = st.sampled_from(
    [0.0, 1e-12, -1e-12, 1e-9, -1e-9, 1e-3, -1e-3, 0.5, -0.5, 5.0, -5.0]
)


@st.composite
def _kl_and_threshold(draw) -> tuple[float | None, float]:
    """Draw a (kl_divergence, threshold) pair covering all three mapping branches.

    Three shapes are drawn with roughly equal weight:
      * ``None`` KL — the unavailable case (confidence ``unknown``);
      * ``threshold + offset`` — the exact boundary and its neighbourhood;
      * an independent finite KL — the general case.
    KL divergence is non-negative by construction, matching the C34 gauge.
    """
    threshold = draw(_thresholds)
    shape = draw(st.sampled_from(["unavailable", "near_boundary", "independent"]))
    if shape == "unavailable":
        return None, threshold
    if shape == "near_boundary":
        kl = threshold + draw(_boundary_offsets)
    else:
        kl = draw(
            st.floats(min_value=0.0, max_value=20.0, allow_nan=False, allow_infinity=False)
        )
    return max(0.0, kl), threshold


@settings(max_examples=200, deadline=None)
@given(case=_kl_and_threshold())
def test_fidelity_confidence_maps_kl_divergence_deterministically(
    case: tuple[float | None, float],
) -> None:
    """confidence is a total, deterministic three-way map over (kl, threshold)."""
    kl_divergence, threshold = case
    report = FidelityReport(kl_divergence=kl_divergence, threshold=threshold)

    confidence = report.confidence

    # The mapping is total over the three declared annotations and never invents a
    # fourth value.
    assert confidence in {
        CONFIDENCE_UNKNOWN,
        CONFIDENCE_LOW_DIVERGENT,
        CONFIDENCE_WITHIN_BOUND,
    }
    # Deterministic: the same inputs always produce the same annotation.
    assert (
        FidelityReport(kl_divergence=kl_divergence, threshold=threshold).confidence
        == confidence
    )

    if kl_divergence is None:
        # R6.5 unavailable: ``unknown`` and never presented as fidelity-validated,
        # and never claimed to be within the bound.
        assert confidence == CONFIDENCE_UNKNOWN
        assert report.is_fidelity_validated is False
        assert confidence != CONFIDENCE_WITHIN_BOUND
        return

    assert report.is_fidelity_validated is True
    assert math.isfinite(kl_divergence)

    exceeds = kl_divergence > threshold
    if exceeds:
        # R6.6: exceeding the committed threshold is reported as outside the bound.
        assert confidence == CONFIDENCE_LOW_DIVERGENT
    else:
        # R6.5: at or below the threshold (including the exact boundary) is within.
        assert confidence == CONFIDENCE_WITHIN_BOUND

    # ``within_fidelity_bound`` holds if and only if the value does not exceed the
    # threshold — i.e. it is reported as outside the bound whenever it does.
    assert (confidence == CONFIDENCE_WITHIN_BOUND) is (not exceeds)
