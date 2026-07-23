"""Property-based tests for aggregation integrity under failures.

Feature: decision-integrity-uplift-proof
Property 9: Aggregation integrity under failures.

    *For any* set of scenario attempts with an arbitrary subset failing, the harness's
    ``aggregate_arm`` excludes every failed run from KPI aggregation, aggregates exactly
    the completed runs, and reports per-arm ``completed`` and ``failed`` counts whose sum
    equals the number of attempts (``completed + failed == len(runs)``). The per-KPI mean
    and standard deviation are computed over exactly the completed runs' KpiVectors
    (population std, ``ddof=0``), and the all-failed case yields ``completed == 0``.

Validates: Requirements 2.7, 2.9
"""
from __future__ import annotations

import numpy as np
from hypothesis import given, settings
from hypothesis import strategies as st

from uplift.harness import KPI_FIELDS, aggregate_arm
from uplift.interfaces import KpiVector, ScenarioRun

# ---------------------------------------------------------------------------
# Strategies
#
# A scenario attempt is either COMPLETED (failed=False, kpis=a KpiVector carrying
# finite floats) or FAILED (failed=True, kpis=None). ``aggregate_arm`` classifies a
# run as completed iff ``not r.failed and r.kpis is not None``, so these two shapes
# exercise both branches cleanly.
#
# KPI values are bounded finite floats. Bounding avoids float overflow to inf in the
# numpy mean/std reduction so the reference statistics and the implementation agree
# exactly; KPI values in the real harness are likewise bounded (rates in [0,1],
# non-negative times, finite margins/CO2).
# ---------------------------------------------------------------------------

_arms = st.text(min_size=0, max_size=16)
_seeds = st.integers(min_value=-(10**9), max_value=10**9)
_kpi_floats = st.floats(
    min_value=-1e6, max_value=1e6, allow_nan=False, allow_infinity=False
)


def _kpi_vectors() -> st.SearchStrategy[KpiVector]:
    """A KpiVector with bounded finite floats in every one of its six fields."""
    return st.builds(
        KpiVector,
        fill_rate=_kpi_floats,
        spoilage_rate=_kpi_floats,
        stockout_rate=_kpi_floats,
        avg_delivery_time_min=_kpi_floats,
        margin=_kpi_floats,
        co2_estimate=_kpi_floats,
    )


@st.composite
def _scenario_runs(draw: st.DrawFn) -> ScenarioRun:
    """A ScenarioRun that is either completed (has a KpiVector) or failed (kpis=None)."""
    failed = draw(st.booleans())
    return ScenarioRun(
        arm=draw(_arms),
        seed=draw(_seeds),
        kpis=None if failed else draw(_kpi_vectors()),
        failed=failed,
        error="boom" if failed else None,
    )


def _reference_mean_std(
    completed: list[ScenarioRun],
) -> tuple[dict[str, float], dict[str, float]]:
    """Reference per-KPI mean and population std (ddof=0) over the completed runs."""
    mean: dict[str, float] = {}
    std: dict[str, float] = {}
    for field in KPI_FIELDS:
        if completed:
            values = np.array(
                [float(getattr(run.kpis, field)) for run in completed], dtype=float
            )
            mean[field] = float(np.mean(values))
            std[field] = float(np.std(values))
        else:
            mean[field] = 0.0
            std[field] = 0.0
    return mean, std


# ---------------------------------------------------------------------------
# Property 9: aggregation integrity under an arbitrary failing subset (R2.7/R2.9)
# ---------------------------------------------------------------------------
@settings(max_examples=200)
@given(arm=_arms, runs=st.lists(_scenario_runs(), max_size=40))
def test_aggregation_integrity_under_failures(arm: str, runs: list[ScenarioRun]) -> None:
    """Failed runs are excluded; counts sum to attempts; stats over completed only."""
    result = aggregate_arm(arm, runs)

    completed = [r for r in runs if not r.failed and r.kpis is not None]
    n_failed = len(runs) - len(completed)

    # Counts reflect the completed / failed split exactly (R2.9).
    assert result.completed == len(completed)
    assert result.failed == n_failed

    # completed + failed always equals the number of attempts (Property 9).
    assert result.completed + result.failed == len(runs)

    # KPI statistics are computed over exactly the completed runs (R2.7, R2.8):
    # failed runs (kpis=None) are excluded from aggregation.
    ref_mean, ref_std = _reference_mean_std(completed)
    assert result.kpi_mean == ref_mean
    assert result.kpi_std == ref_std


# ---------------------------------------------------------------------------
# Property 9 (all-failed variant): every attempt fails => completed == 0 (R2.7)
# ---------------------------------------------------------------------------
@settings(max_examples=100)
@given(
    arm=_arms,
    seeds=st.lists(_seeds, min_size=1, max_size=40),
)
def test_aggregation_all_failed_yields_zero_completed(
    arm: str, seeds: list[int]
) -> None:
    """When every run failed, completed is 0, failed is the attempt count, stats are 0."""
    runs = [
        ScenarioRun(arm=arm, seed=seed, kpis=None, failed=True, error="boom")
        for seed in seeds
    ]

    result = aggregate_arm(arm, runs)

    assert result.completed == 0
    assert result.failed == len(runs)
    assert result.completed + result.failed == len(runs)
    # No completed runs contribute, so every KPI aggregate defaults to 0.0.
    for field in KPI_FIELDS:
        assert result.kpi_mean[field] == 0.0
        assert result.kpi_std[field] == 0.0
