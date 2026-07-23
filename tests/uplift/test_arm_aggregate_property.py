"""Property-based tests for per-arm aggregate statistics in ``uplift.harness``.

Feature: decision-integrity-uplift-proof
Property 10: Per-arm aggregates match the reference statistics.

    *For any* set of completed ``KpiVector``s for an arm, the harness's per-arm
    mean and standard deviation of each KPI (``aggregate_arm(...).kpi_mean`` /
    ``.kpi_std``) equal an INDEPENDENT reference mean and population standard
    deviation (numpy, ``ddof=0``) computed over exactly the completed set — never
    by calling the aggregation under test.

Validates: Requirements 2.8
"""
from __future__ import annotations

import math

import numpy as np
from hypothesis import given, settings
from hypothesis import strategies as st

from uplift.harness import KPI_FIELDS, aggregate_arm
from uplift.interfaces import KpiVector, ScenarioRun


# ---------------------------------------------------------------------------
# Strategies
#
# Bounded, finite floats keep the reference arithmetic numerically stable (no
# overflow to inf, no catastrophic cancellation) so ``np.mean``/``np.std`` on the
# harness path and the reference path agree to floating-point tolerance. Each
# completed run carries a full six-field ``KpiVector``; the arm has at least one
# completed run (``min_size=1``) so mean/std are defined.
# ---------------------------------------------------------------------------
_finite_values = st.floats(
    min_value=-1e6,
    max_value=1e6,
    allow_nan=False,
    allow_infinity=False,
    width=64,
)


@st.composite
def _completed_runs(draw: st.DrawFn) -> list[ScenarioRun]:
    """A non-empty list of completed ``ScenarioRun``s with full KPI vectors."""
    n = draw(st.integers(min_value=1, max_value=32))
    runs: list[ScenarioRun] = []
    for index in range(n):
        values = draw(
            st.lists(_finite_values, min_size=len(KPI_FIELDS), max_size=len(KPI_FIELDS))
        )
        kpis = KpiVector(*values)
        runs.append(
            ScenarioRun(arm="arm", seed=index, kpis=kpis, failed=False, error=None)
        )
    return runs


# ---------------------------------------------------------------------------
# Property 10: per-arm mean/std equal the reference over the completed set (R2.8)
# ---------------------------------------------------------------------------
@settings(max_examples=200)
@given(runs=_completed_runs())
def test_aggregate_matches_reference_statistics(runs: list[ScenarioRun]) -> None:
    """aggregate_arm mean/std equal an independent numpy (ddof=0) reference."""
    result = aggregate_arm("arm", runs)

    # The completed set is exactly the input here (all runs are completed).
    assert result.completed == len(runs)
    assert result.failed == 0

    for field in KPI_FIELDS:
        reference = np.array(
            [float(getattr(run.kpis, field)) for run in runs], dtype=float
        )
        ref_mean = float(np.mean(reference))
        ref_std = float(np.std(reference))  # population std, ddof=0

        assert math.isclose(
            result.kpi_mean[field], ref_mean, rel_tol=1e-9, abs_tol=1e-9
        )
        assert math.isclose(
            result.kpi_std[field], ref_std, rel_tol=1e-9, abs_tol=1e-9
        )


# ---------------------------------------------------------------------------
# Failed runs are excluded: aggregates match the reference over ONLY the
# completed subset, never the failed runs (R2.7/R2.8).
# ---------------------------------------------------------------------------
@settings(max_examples=200)
@given(
    completed=_completed_runs(),
    n_failed=st.integers(min_value=0, max_value=8),
)
def test_aggregate_excludes_failed_runs(
    completed: list[ScenarioRun], n_failed: int
) -> None:
    """Failed runs are excluded; stats match the reference over the completed set."""
    failed = [
        ScenarioRun(arm="arm", seed=1000 + i, kpis=None, failed=True, error="boom")
        for i in range(n_failed)
    ]
    runs = completed + failed

    result = aggregate_arm("arm", runs)

    assert result.completed == len(completed)
    assert result.failed == n_failed

    for field in KPI_FIELDS:
        reference = np.array(
            [float(getattr(run.kpis, field)) for run in completed], dtype=float
        )
        assert math.isclose(
            result.kpi_mean[field], float(np.mean(reference)), rel_tol=1e-9, abs_tol=1e-9
        )
        assert math.isclose(
            result.kpi_std[field], float(np.std(reference)), rel_tol=1e-9, abs_tol=1e-9
        )


# ---------------------------------------------------------------------------
# Documented empty-case behavior: with no completed runs the impl returns 0.0
# for every KPI mean/std (never raises, never fabricates a KPI).
# ---------------------------------------------------------------------------
@settings(max_examples=50)
@given(n_failed=st.integers(min_value=0, max_value=16))
def test_empty_completed_set_returns_zero(n_failed: int) -> None:
    """No completed runs => every per-KPI mean/std is 0.0."""
    runs = [
        ScenarioRun(arm="arm", seed=i, kpis=None, failed=True, error="boom")
        for i in range(n_failed)
    ]
    result = aggregate_arm("arm", runs)

    assert result.completed == 0
    assert result.failed == n_failed
    for field in KPI_FIELDS:
        assert result.kpi_mean[field] == 0.0
        assert result.kpi_std[field] == 0.0
