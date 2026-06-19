"""Property-based tests for the pure concession helper (ADR-052, R3).

Implementation under test: ``synapse_common.debate.concession`` — the three pure
helpers every agent shares when it revises a proposal toward the round consensus:

  * :func:`consensus_position` — arithmetic mean of the round's utility scores (R3.2).
  * :func:`within_convergence_band` — the maintain-rather-than-concede band, whose
    half-width is ``sqrt(variance_threshold)`` (R3.9).
  * :func:`concede_toward` — a bounded, monotone, non-overshooting move toward the
    consensus (R3.3) that reduces to a no-op at the consensus.

This module implements **Property 8** from the design document.

Example budget is controlled by the active Hypothesis profile (see the root
``conftest.py``): ``dev`` (10), ``default``/``ci`` (500), ``nightly`` (5_000).
"""

from __future__ import annotations

import math

import pytest

try:
    from hypothesis import given, settings
    from hypothesis import strategies as st
except ImportError:  # hypothesis is optional in some environments
    pytest.skip("hypothesis not installed", allow_module_level=True)

from synapse_common.debate.concession import (
    concede_toward,
    consensus_position,
    within_convergence_band,
)

# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------
# Utility scores are bounded, finite reals. We keep the range well away from the
# float extremes so the algebraic identities below are not swamped by rounding,
# while still spanning negative, zero, and positive positions and large gaps.
_score_st = st.floats(
    min_value=-1_000.0, max_value=1_000.0, allow_nan=False, allow_infinity=False
)
_fraction_st = st.floats(
    min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False
)
# Non-empty list of scores for the consensus (arithmetic mean) property.
_scores_list_st = st.lists(_score_st, min_size=1, max_size=8)
# Variance threshold whose square root defines the convergence-band half-width.
_variance_st = st.floats(
    min_value=0.0, max_value=4.0, allow_nan=False, allow_infinity=False
)

# Absolute tolerance for floating-point identity checks across the bounded range.
_ATOL = 1e-9


# ---------------------------------------------------------------------------
# Property 8: Concession is bounded, monotone toward consensus, and honest
# Validates: Requirements 3.2, 3.3, 3.7, 3.9
# ---------------------------------------------------------------------------


@given(current=_score_st, consensus=_score_st, max_fraction=_fraction_st)
@settings(deadline=None)
def test_concession_does_not_overshoot_consensus(
    current: float, consensus: float, max_fraction: float
) -> None:
    """The revised score lies on the segment ``[current, consensus]`` (R3.3).

    Concession never crosses past the consensus, regardless of which side the
    current value starts on.

    **Validates: Requirements 3.3**
    """
    revised = concede_toward(current, consensus, max_fraction=max_fraction)
    lo, hi = (current, consensus) if current <= consensus else (consensus, current)
    assert lo - _ATOL <= revised <= hi + _ATOL


@given(current=_score_st, consensus=_score_st)
@settings(deadline=None)
def test_concession_moves_at_most_half_the_gap(current: float, consensus: float) -> None:
    """A default concession closes at most 50% of the gap to consensus (R3.3).

    **Validates: Requirements 3.3**
    """
    revised = concede_toward(current, consensus)
    gap = abs(consensus - current)
    moved = abs(revised - current)
    assert moved <= 0.5 * gap + _ATOL


@given(current=_score_st, consensus=_score_st, max_fraction=_fraction_st)
@settings(deadline=None)
def test_concession_is_monotone_toward_consensus(
    current: float, consensus: float, max_fraction: float
) -> None:
    """The revised score is no further from consensus than the current score.

    Moving toward consensus by a non-negative fraction of the gap can only reduce
    (or preserve) the distance to consensus — never increase it.

    **Validates: Requirements 3.3**
    """
    revised = concede_toward(current, consensus, max_fraction=max_fraction)
    assert abs(revised - consensus) <= abs(current - consensus) + _ATOL


@given(consensus=_score_st, max_fraction=_fraction_st)
@settings(deadline=None)
def test_concession_is_a_no_op_at_consensus(consensus: float, max_fraction: float) -> None:
    """When already at the consensus, concession does not move (idempotent at band).

    **Validates: Requirements 3.3, 3.9**
    """
    revised = concede_toward(consensus, consensus, max_fraction=max_fraction)
    assert revised == pytest.approx(consensus, abs=_ATOL)


@given(current=_score_st, consensus=_score_st)
@settings(deadline=None)
def test_revised_value_is_the_reported_position(current: float, consensus: float) -> None:
    """The revised score the helper returns IS the value an honest handler reports.

    The pure helper returns exactly ``current + 0.5*(consensus - current)`` with no
    fabricated adjustment, so the handler's reported revised ``utility_score`` matches
    the concession arithmetic (R3.7).

    **Validates: Requirements 3.7**
    """
    revised = concede_toward(current, consensus)
    expected = current + 0.5 * (consensus - current)
    assert revised == pytest.approx(expected, abs=_ATOL)


@given(current=_score_st, consensus=_score_st, variance_threshold=_variance_st)
@settings(deadline=None)
def test_within_convergence_band_uses_sqrt_of_variance_threshold(
    current: float, consensus: float, variance_threshold: float
) -> None:
    """The band half-width is exactly ``sqrt(variance_threshold)`` (R3.9).

    **Validates: Requirements 3.9**
    """
    expected = abs(current - consensus) <= math.sqrt(variance_threshold)
    assert (
        within_convergence_band(
            current, consensus, variance_threshold=variance_threshold
        )
        is expected
    )


@given(consensus=_score_st, variance_threshold=_variance_st)
@settings(deadline=None)
def test_value_at_consensus_is_always_within_band(
    consensus: float, variance_threshold: float
) -> None:
    """A value already at the consensus is always within the band → maintain (R3.9).

    This is the maintain-rather-than-concede case: a handler at consensus reports a
    maintained position rather than a revision.

    **Validates: Requirements 3.9**
    """
    assert (
        within_convergence_band(
            consensus, consensus, variance_threshold=variance_threshold
        )
        is True
    )


@given(scores=_scores_list_st)
@settings(deadline=None)
def test_consensus_position_is_arithmetic_mean(scores: list[float]) -> None:
    """The consensus position is the arithmetic mean of the round's scores (R3.2).

    **Validates: Requirements 3.2**
    """
    result = consensus_position(scores)
    expected = math.fsum(scores) / len(scores)
    assert result == pytest.approx(expected, abs=_ATOL)
    # The mean always lies within the closed range of the inputs.
    assert min(scores) - _ATOL <= result <= max(scores) + _ATOL


# ---------------------------------------------------------------------------
# Example-based edge cases (complement the properties above)
# ---------------------------------------------------------------------------


def test_consensus_position_rejects_empty_sequence() -> None:
    """An empty round has no defined consensus and must raise (R3.2)."""
    with pytest.raises(ValueError, match="at least one utility score"):
        consensus_position([])


def test_concede_toward_rejects_fraction_out_of_range() -> None:
    """``max_fraction`` outside ``[0, 1]`` is rejected (bounded concession, R3.3)."""
    with pytest.raises(ValueError, match=r"\[0, 1\]"):
        concede_toward(0.2, 0.8, max_fraction=1.5)
    with pytest.raises(ValueError, match=r"\[0, 1\]"):
        concede_toward(0.2, 0.8, max_fraction=-0.1)


def test_within_convergence_band_rejects_negative_threshold() -> None:
    """A negative variance threshold has no real square root and must raise (R3.9)."""
    with pytest.raises(ValueError, match="non-negative"):
        within_convergence_band(0.4, 0.5, variance_threshold=-0.01)


def test_concession_closes_half_the_gap_concrete() -> None:
    """A concrete 0.40 → 0.60 example closes exactly half the gap (0.40 → 0.50)."""
    assert concede_toward(0.40, 0.60) == pytest.approx(0.50, abs=_ATOL)
