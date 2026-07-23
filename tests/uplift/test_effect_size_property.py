"""Property-based tests for the effect-size computation in ``uplift.contract``.

Feature: decision-integrity-uplift-proof
Property 11: Effect-size computation matches the reference formula.

    *For any* two per-scenario KPI sample arrays that are non-degenerate — sizes
    ``>= 2``, non-constant so the pooled standard deviation is strictly positive,
    and a baseline mean that is not zero — the module-level ``cohens_d`` and
    ``relative_pct_change`` equal an INDEPENDENT reference implementation of their
    documented formulas (computed here with numpy, never by calling the functions
    under test).

Validates: Requirements 3.2
"""
from __future__ import annotations

import math

import numpy as np
from hypothesis import assume, given, settings
from hypothesis import strategies as st

from uplift.contract import cohens_d, relative_pct_change


# ---------------------------------------------------------------------------
# Strategies
#
# Bounded, finite float samples keep the reference arithmetic numerically stable
# (no overflow to inf, no catastrophic cancellation). Sizes are >= 2 so the sample
# variance (ddof=1) is defined for each arm. ``assume`` rejects the remaining
# degenerate cases the formulas guard against (zero pooled std, zero baseline mean).
# ---------------------------------------------------------------------------
_finite_values = st.floats(
    min_value=-1e6,
    max_value=1e6,
    allow_nan=False,
    allow_infinity=False,
    width=64,
)


def _sample_arrays() -> st.SearchStrategy[tuple[list[float], list[float]]]:
    return st.tuples(
        st.lists(_finite_values, min_size=2, max_size=64),
        st.lists(_finite_values, min_size=2, max_size=64),
    )


def _reference_cohens_d(consensus: np.ndarray, baseline: np.ndarray) -> float:
    """Independent reference for pooled-std Cohen's d (ddof=1)."""
    n1, n2 = consensus.size, baseline.size
    var_c = float(np.var(consensus, ddof=1))
    var_b = float(np.var(baseline, ddof=1))
    pooled_var = ((n1 - 1) * var_c + (n2 - 1) * var_b) / (n1 + n2 - 2)
    pooled_std = math.sqrt(pooled_var)
    return (float(np.mean(consensus)) - float(np.mean(baseline))) / pooled_std


def _reference_rel_pct(consensus: np.ndarray, baseline: np.ndarray) -> float:
    """Independent reference for relative percentage change."""
    mean_b = float(np.mean(baseline))
    return (float(np.mean(consensus)) - mean_b) / mean_b * 100.0


# ---------------------------------------------------------------------------
# Property 11: computed effect sizes equal the reference formulas (R3.2)
# ---------------------------------------------------------------------------
@settings(max_examples=300)
@given(arrays=_sample_arrays())
def test_effect_sizes_match_reference_formulas(
    arrays: tuple[list[float], list[float]],
) -> None:
    """cohens_d and relative_pct_change equal an independent numpy reference."""
    consensus_list, baseline_list = arrays
    consensus = np.asarray(consensus_list, dtype=float)
    baseline = np.asarray(baseline_list, dtype=float)

    # --- Non-degeneracy guards matching the functions' documented contract. ---
    # Pooled std must be strictly positive: at least one arm must be non-constant.
    n1, n2 = consensus.size, baseline.size
    pooled_var = (
        (n1 - 1) * float(np.var(consensus, ddof=1))
        + (n2 - 1) * float(np.var(baseline, ddof=1))
    ) / (n1 + n2 - 2)
    assume(pooled_var > 0.0)
    # Baseline mean must be non-zero for a defined relative percentage change.
    mean_b = float(np.mean(baseline))
    assume(abs(mean_b) > 1e-9)

    ref_d = _reference_cohens_d(consensus, baseline)
    ref_rel = _reference_rel_pct(consensus, baseline)

    # Both reference values must be finite for this non-degenerate branch.
    assume(math.isfinite(ref_d))
    assume(math.isfinite(ref_rel))

    got_d = cohens_d(consensus_list, baseline_list)
    got_rel = relative_pct_change(consensus_list, baseline_list)

    assert math.isclose(got_d, ref_d, rel_tol=1e-9, abs_tol=1e-9)
    assert math.isclose(got_rel, ref_rel, rel_tol=1e-9, abs_tol=1e-6)


# ---------------------------------------------------------------------------
# Documented degenerate-input behavior: both functions return 0.0 (never raise).
# ---------------------------------------------------------------------------
@settings(max_examples=100)
@given(samples=st.lists(_finite_values, min_size=2, max_size=32))
def test_empty_input_returns_zero(samples: list[float]) -> None:
    """An empty arm makes both effect sizes 0.0 (degenerate input)."""
    assert cohens_d([], samples) == 0.0
    assert cohens_d(samples, []) == 0.0
    assert relative_pct_change([], samples) == 0.0
    assert relative_pct_change(samples, []) == 0.0


@settings(max_examples=100)
@given(
    # Small, exactly-representable integer values so the sample variance of a
    # repeated value is *exactly* zero (avoids floating-point residue that a large
    # magnitude would introduce), giving a genuine zero-pooled-std degenerate case.
    value=st.integers(min_value=-1000, max_value=1000).map(float),
    n1=st.integers(min_value=2, max_value=16),
    n2=st.integers(min_value=2, max_value=16),
)
def test_zero_pooled_std_returns_zero_cohens_d(value: float, n1: int, n2: int) -> None:
    """When both arms are constant (pooled std = 0), Cohen's d is 0.0."""
    consensus = [value] * n1
    baseline = [value] * n2
    assert cohens_d(consensus, baseline) == 0.0


@settings(max_examples=100)
@given(consensus=st.lists(_finite_values, min_size=2, max_size=16))
def test_zero_baseline_mean_returns_zero_rel_pct(consensus: list[float]) -> None:
    """A zero baseline mean makes relative percentage change 0.0."""
    baseline = [1.0, -1.0]  # mean is exactly 0.0
    assert relative_pct_change(consensus, baseline) == 0.0
