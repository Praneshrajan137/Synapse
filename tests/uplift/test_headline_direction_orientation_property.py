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

**The quoted formula is FALSE by decision; its orientation guarantee is kept.**
Metric_Contract v2 (decision-quality-proof task 29.4, R7.19) replaces the relative percentage
change with the mean SEED-PAIRED difference of the committed objective, comparator minus
consensus, in objective units, and it fixes the direction: the objective is a cost, and
construction refuses any direction but lower-is-better for it, so "either Direction" has one
admissible value (the refusal is asserted in ``test_result_kpi_partition_property.py``). The
tag line is kept so the property stays traceable; what is asserted is the v2 orientation:

* the headline equals ``fmean(baseline - consensus)`` over every replicate both arms completed
  at the same seed, recomputed here -- and it IS the reported interval's point;
* positive means the consensus arm is CHEAPER, so exchanging the subject and the comparator
  negates the headline exactly (the v2 analogue of flipping the declared direction);
* consequently a consensus arm cheaper than every baseline replicate yields a strictly
  positive headline whose interval lies above zero, and a dearer one a negative headline.

Budget inherited from the root ``conftest.py`` profile; no ``max_examples`` literal.

**Validates: Requirements 2.2**
"""
from __future__ import annotations

import statistics
from typing import TYPE_CHECKING

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from uplift.contract import load_contract
from uplift.fidelity import FidelityReport
from uplift.harness import HarnessResult, aggregate_arm, assemble_uplift_result
from uplift.interfaces import KpiVector, Scenario, ScenarioRun

from digital_twin.simulation.monte_carlo import ShockParams

if TYPE_CHECKING:
    from uplift.interfaces import UpliftResult

# The real, version-controlled metric contract (v2): the headline KPI is the committed
# objective, a cost, lower is better -- the only direction construction admits for it.
_CONTRACT = load_contract()
_MARGIN = _CONTRACT.materiality_margin
_CONSENSUS_ARM = "consensus"
_BASELINE_ARM = "baseline"

# Deterministic, available, within-bound fidelity so assembly never touches the live
# C34 gauge — fidelity context is irrelevant to the orientation of the headline number.
_FIDELITY = FidelityReport(kl_divergence=0.02, threshold=0.1)

# Objective costs. The lower bound stays strictly positive so that "genuinely cheaper" --
# half the cheapest baseline cost -- is a strictly cheaper, still non-negative cost.
_SAMPLES = st.lists(
    st.floats(min_value=0.05, max_value=1.0, allow_nan=False, allow_infinity=False),
    min_size=1,
    max_size=6,
)


def _kpi(objective: float) -> KpiVector:
    """A KpiVector varying only ``objective``; the other fields are fixed constants."""
    return KpiVector(
        fill_rate=1.0,
        spoilage_rate=0.0,
        stockout_rate=0.0,
        avg_delivery_time_min=1.0,
        margin=1.0,
        co2_estimate=1.0,
        avg_on_hand_units=1.0,
        objective=objective,
    )


def _completed_runs(arm: str, objectives: list[float]) -> list[ScenarioRun]:
    """Completed (non-failed) runs for ``arm``; replicate ``i`` runs at seed ``i``."""
    return [
        ScenarioRun(arm=arm, seed=index, kpis=_kpi(value), failed=False, error=None)
        for index, value in enumerate(objectives)
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
        arm_roles={_CONSENSUS_ARM: "consensus", _BASELINE_ARM: "baseline"},
    )


def _assemble(
    per_scenario_samples: list[tuple[list[float], list[float]]], *, swapped: bool
) -> UpliftResult:
    """Assemble with consensus as the subject or, ``swapped``, with the two roles exchanged.

    The comparator is NAMED in both orientations, so each contrast is exactly the two arms.
    """
    subject, comparator = (
        (_BASELINE_ARM, _CONSENSUS_ARM) if swapped else (_CONSENSUS_ARM, _BASELINE_ARM)
    )
    return assemble_uplift_result(
        _harness_result(per_scenario_samples),
        _CONTRACT,
        fidelity=_FIDELITY,
        consensus_arm=subject,
        baseline_arm=comparator,
    )


def _seed_paired_gains(
    per_scenario_samples: list[tuple[list[float], list[float]]],
) -> list[float]:
    """``baseline - consensus`` at every seed both arms completed, scenario by scenario.

    Replicate ``i`` of each arm runs at seed ``i``, so the seeds both arms recorded on a
    scenario are the first ``min(len)`` of each array: those, and only those, pair.
    """
    gains: list[float] = []
    for consensus, baseline in per_scenario_samples:
        paired = min(len(consensus), len(baseline))
        gains.extend(
            b - c for c, b in zip(consensus[:paired], baseline[:paired], strict=True)
        )
    return gains


@st.composite
def _sample_grids(draw: st.DrawFn) -> list[tuple[list[float], list[float]]]:
    """Per-scenario ``(consensus samples, baseline samples)`` arrays (1-3 scenarios).

    Small grids keep the test pure and fast: the headline number depends only on the
    seed-paired differences pooled across scenarios, so a handful of scenarios already
    exercises pooling across scenarios and both signs of the gap.
    """
    n_scenarios = draw(st.integers(min_value=1, max_value=3))
    return [(draw(_SAMPLES), draw(_SAMPLES)) for _ in range(n_scenarios)]


@settings(deadline=None)
@given(grid=_sample_grids())
def test_headline_uplift_is_direction_oriented(
    grid: list[tuple[list[float], list[float]]],
) -> None:
    """The headline is the mean seed-paired cost saving; exchanging the arms negates it."""
    result = _assemble(grid, swapped=False)

    # Every pair completes cleanly, so the headline is computed for a non-incomplete run.
    assert result.incomplete is False
    assert result.interval is not None

    # The headline is the mean paired cost saving, comparator minus consensus, recomputed
    # here from the drawn arrays -- and it is exactly the interval's point, not a second
    # computation of it.
    expected = statistics.fmean(_seed_paired_gains(grid))
    assert result.headline_uplift == result.interval.point
    assert result.headline_uplift == expected, (
        f"headline={result.headline_uplift} != mean seed-paired saving {expected}"
    )

    # The orientation guarantee: exchanging the subject and the comparator negates the
    # headline exactly, so one orientation is precisely the negation of the other.
    swapped = _assemble(grid, swapped=True)
    assert swapped.interval is not None
    assert swapped.headline_uplift == -result.headline_uplift

    # Consequence: an arrangement where consensus is *genuinely better* -- cheaper than
    # every baseline replicate of every scenario -- never reports a negative headline. Built
    # from the same drawn baselines by replacing each consensus cost with half the cheapest
    # baseline cost, so every seed-paired saving is strictly positive.
    pooled_baseline = [value for _, baseline in grid for value in baseline]
    cheaper_value = min(pooled_baseline) / 2.0
    cheaper_grid = [
        ([cheaper_value] * len(consensus), baseline) for consensus, baseline in grid
    ]
    cheaper = _assemble(cheaper_grid, swapped=False)
    assert cheaper.incomplete is False
    assert cheaper.interval is not None
    assert cheaper.headline_uplift > 0.0, (
        f"genuinely cheaper consensus reported the headline {cheaper.headline_uplift}"
    )
    # Every resampled mean of strictly positive savings is positive, so the interval lies
    # wholly above zero: a gain of either size, never inconclusive and never a loss.
    assert cheaper.interval.low > 0.0
    assert cheaper.headline_verdict in ("win", "sub_margin_gain")


def test_a_cheaper_consensus_is_a_positive_headline() -> None:
    """A consensus arm two margins cheaper on every replicate reports that saving."""
    cheap = 10.0
    result = _assemble([([cheap, cheap], [cheap + 2.0 * _MARGIN] * 2)], swapped=False)

    assert result.incomplete is False
    assert result.headline_uplift == pytest.approx(2.0 * _MARGIN)
    assert result.headline_verdict == "win"


def test_the_headline_is_a_cost_difference_never_a_relative_change() -> None:
    """v1 reported these arrays as +20 percentage points; v2 reports the paired saving."""
    result = _assemble([([0.40, 0.40], [0.50, 0.50])], swapped=False)

    assert result.incomplete is False
    # 0.50 - 0.40 in objective units, positive because consensus is cheaper. The v1 headline
    # for the same arrays, the negated relative change, was +20.0.
    assert result.headline_uplift == pytest.approx(0.10)
    assert result.headline_uplift != pytest.approx(20.0)


def test_a_dearer_consensus_is_a_negative_headline() -> None:
    """A genuinely dearer consensus arm never reports a positive headline."""
    dearer = _assemble([([0.60, 0.60], [0.50, 0.50])], swapped=False)
    exchanged = _assemble([([0.60, 0.60], [0.50, 0.50])], swapped=True)

    assert dearer.headline_uplift == pytest.approx(-0.10)
    # With the roles exchanged the cheaper arm is the subject, and its saving is positive.
    assert exchanged.headline_uplift == pytest.approx(0.10)
