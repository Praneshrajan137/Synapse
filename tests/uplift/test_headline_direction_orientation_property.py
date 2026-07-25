"""Property-based test that the headline uplift is direction-oriented.

Feature: core-purpose-uplift
Property 6: Headline uplift is direction-oriented so positive always means improvement

    *For any* consensus and baseline sample arrays and either :class:`~uplift.interfaces.Direction`,
    the headline uplift equals the relative percentage change for a higher-is-better KPI
    and its negation for a lower-is-better KPI; consequently any arrangement where
    consensus is genuinely better on the primary KPI yields a non-negative headline.

    Requirement 2.2: "WHILE the assembled ``UpliftResult`` is not incomplete, THE
    Uplift_Harness SHALL compute a numeric Headline_Uplift as the direction-oriented
    relative percentage change (in percentage points) of the Consensus_Arm pooled mean
    over the pooled Baseline_Arm mean on the FIRST declared primary KPI in the
    Metric_Contract, such that a positive value always denotes improvement (raw for
    higher-is-better, negated for lower-is-better)."

    The test builds ``HarnessResult`` / ``ScenarioRun`` data directly from synthetic
    sample arrays — no twin runs and no consensus assembly — so it is pure, fast, and
    network-free ($0, I-1).

**Validates: Requirements 2.2**
"""
from __future__ import annotations

import dataclasses

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from uplift.contract import load_contract, relative_pct_change
from uplift.fidelity import FidelityReport
from uplift.harness import HarnessResult, aggregate_arm, assemble_uplift_result
from uplift.interfaces import Direction, KpiVector, Scenario, ScenarioRun

from digital_twin.simulation.monte_carlo import ShockParams

# The real, version-controlled metric contract; its headline (first) primary KPI is
# ``fill_rate``. Only the declared direction is varied per example, so the *same*
# sample arrays are adjudicated under both orientations.
_BASE_CONTRACT = load_contract()
_HEADLINE_KPI = "fill_rate"
_CONSENSUS_ARM = "consensus"
_BASELINE_ARM = "baseline"

# Deterministic, available, within-bound fidelity so assembly never touches the live
# C34 gauge — fidelity context is irrelevant to the orientation of the headline number.
_FIDELITY = FidelityReport(kl_divergence=0.02, threshold=0.1)

# ``fill_rate`` is a fraction in [0, 1]; the lower bound stays strictly positive so the
# pooled baseline mean is never zero (a zero denominator is the documented degenerate
# case of ``relative_pct_change`` and is covered by its own contract property).
_SAMPLES = st.lists(
    st.floats(min_value=0.05, max_value=1.0, allow_nan=False, allow_infinity=False),
    min_size=1,
    max_size=6,
)


def _kpi(fill_rate: float) -> KpiVector:
    """A KpiVector varying only ``fill_rate``; the other fields are fixed constants."""
    return KpiVector(
        fill_rate=fill_rate,
        spoilage_rate=0.0,
        stockout_rate=0.0,
        avg_delivery_time_min=1.0,
        margin=1.0,
        co2_estimate=1.0,
    )


def _completed_runs(arm: str, fill_rates: list[float]) -> list[ScenarioRun]:
    """Completed (non-failed) runs for ``arm`` carrying the given fill_rate samples."""
    return [
        ScenarioRun(arm=arm, seed=index, kpis=_kpi(value), failed=False, error=None)
        for index, value in enumerate(fill_rates)
    ]


def _harness_result(
    per_scenario_samples: list[tuple[list[float], list[float]]],
) -> HarnessResult:
    """A complete consensus-vs-baseline HarnessResult from per-scenario sample arrays."""
    scenarios: list[Scenario] = []
    runs_by_pair: dict[tuple[str, str], list[ScenarioRun]] = {}
    for index, (consensus, baseline) in enumerate(per_scenario_samples):
        name = f"scenario-{index}"
        scenarios.append(
            Scenario(name=name, seed=7001 + index, shock=ShockParams(demand_multiplier=1.0))
        )
        runs_by_pair[(name, _CONSENSUS_ARM)] = _completed_runs(_CONSENSUS_ARM, consensus)
        runs_by_pair[(name, _BASELINE_ARM)] = _completed_runs(_BASELINE_ARM, baseline)

    all_runs = [run for runs in runs_by_pair.values() for run in runs]
    return HarnessResult(
        arm_results={pair: aggregate_arm(pair[1], runs) for pair, runs in runs_by_pair.items()},
        runs_by_pair=runs_by_pair,
        all_runs=all_runs,
        results_path=None,
        scenarios=tuple(scenarios),
        arm_names=(_CONSENSUS_ARM, _BASELINE_ARM),
    )


def _contract_with(direction: Direction):
    """The real contract re-declared with the headline KPI's improvement direction."""
    return dataclasses.replace(
        _BASE_CONTRACT, primary_kpis={_HEADLINE_KPI: direction}
    )


def _headline(
    per_scenario_samples: list[tuple[list[float], list[float]]], direction: Direction
) -> tuple[float, bool]:
    """Assemble and return ``(headline_uplift, incomplete)`` for the given samples."""
    result = assemble_uplift_result(
        _harness_result(per_scenario_samples),
        _contract_with(direction),
        fidelity=_FIDELITY,
        consensus_arm=_CONSENSUS_ARM,
        baseline_arm=_BASELINE_ARM,
    )
    return result.headline_uplift, result.incomplete


@st.composite
def _sample_grids(draw: st.DrawFn) -> list[tuple[list[float], list[float]]]:
    """Per-scenario ``(consensus samples, baseline samples)`` arrays (1-3 scenarios).

    Small grids keep the test pure and fast: the headline number depends only on the
    *pooled* consensus and baseline means, so a handful of scenarios already exercises
    pooling across scenarios and both orientations of the mean gap.
    """
    n_scenarios = draw(st.integers(min_value=1, max_value=3))
    return [(draw(_SAMPLES), draw(_SAMPLES)) for _ in range(n_scenarios)]


@settings(max_examples=200, deadline=None)
@given(grid=_sample_grids(), direction=st.sampled_from(list(Direction)))
def test_headline_uplift_is_direction_oriented(
    grid: list[tuple[list[float], list[float]]], direction: Direction
) -> None:
    """The headline equals the pooled relative % change, negated for lower-is-better."""
    headline, incomplete = _headline(grid, direction)

    # Every pair completes cleanly, so the headline is computed for a non-incomplete run.
    assert incomplete is False

    pooled_consensus = [value for consensus, _ in grid for value in consensus]
    pooled_baseline = [value for _, baseline in grid for value in baseline]
    rel = relative_pct_change(pooled_consensus, pooled_baseline)

    expected = rel if direction is Direction.HIGHER_IS_BETTER else -rel
    assert headline == pytest.approx(expected, rel=1e-9, abs=1e-12), (
        f"headline={headline} != {expected} for direction={direction} "
        f"(pooled rel_pct={rel})"
    )

    # The orientation guarantee: flipping the declared direction flips the sign, so one
    # of the two orientations is exactly the negation of the other.
    flipped = (
        Direction.LOWER_IS_BETTER
        if direction is Direction.HIGHER_IS_BETTER
        else Direction.HIGHER_IS_BETTER
    )
    flipped_headline, _ = _headline(grid, flipped)
    assert flipped_headline == pytest.approx(-headline, rel=1e-9, abs=1e-12)

    # Consequence: an arrangement where consensus is *genuinely better* on the primary
    # KPI (strictly better under the declared direction) never reports a negative
    # headline. Built from the same drawn samples by shifting consensus in the
    # improving direction, staying inside the [0, 1] fraction range.
    # The headline pools across scenarios, so "genuinely better" is expressed against
    # the *global* baseline extremes: every consensus sample beats every baseline sample
    # under the declared direction, which forces the pooled means apart the right way.
    better_value = (
        min(1.0, max(pooled_baseline) + 0.02)
        if direction is Direction.HIGHER_IS_BETTER
        else min(pooled_baseline) / 2.0
    )
    better_grid = [
        ([better_value] * len(consensus), baseline) for consensus, baseline in grid
    ]
    better_headline, better_incomplete = _headline(better_grid, direction)
    assert better_incomplete is False
    assert better_headline >= 0.0, (
        f"genuinely better consensus reported a negative headline {better_headline} "
        f"under direction={direction}"
    )


def test_higher_is_better_uses_raw_relative_change() -> None:
    """A higher consensus mean on a higher-is-better KPI is a positive headline."""
    grid = [([0.60, 0.60], [0.50, 0.50])]

    headline, incomplete = _headline(grid, Direction.HIGHER_IS_BETTER)

    assert incomplete is False
    assert headline == pytest.approx(20.0)


def test_lower_is_better_negates_relative_change() -> None:
    """A lower consensus mean on a lower-is-better KPI is a positive headline."""
    grid = [([0.40, 0.40], [0.50, 0.50])]

    headline, incomplete = _headline(grid, Direction.LOWER_IS_BETTER)

    assert incomplete is False
    # Raw relative change is -20 pp; negated for a lower-is-better KPI it reports +20 pp.
    assert headline == pytest.approx(20.0)


def test_worse_consensus_is_negative_under_both_directions() -> None:
    """A genuinely worse consensus arm never reports a positive headline."""
    higher, _ = _headline([([0.40, 0.40], [0.50, 0.50])], Direction.HIGHER_IS_BETTER)
    lower, _ = _headline([([0.60, 0.60], [0.50, 0.50])], Direction.LOWER_IS_BETTER)

    assert higher == pytest.approx(-20.0)
    assert lower == pytest.approx(-20.0)
