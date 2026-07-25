"""Property-based test that the ``incomplete`` flag exactly tracks run completeness.

Feature: core-purpose-uplift
Property 4: `incomplete` flag exactly tracks run completeness

    *For any* synthetic :class:`~uplift.harness.HarnessResult`, the assembled
    ``UpliftResult.incomplete`` is ``False`` **if and only if** every compared
    ``(scenario, arm)`` pair (the consensus arm and every baseline arm) has at least one
    completed run and zero failed runs.

    Requirement 2.1: "WHEN, for every declared adversarial scenario, both the
    Consensus_Arm and every compared Baseline_Arm have at least one completed run AND
    zero failed runs, THE Uplift_Harness SHALL assemble an ``UpliftResult`` whose
    ``incomplete`` field is ``false`` (matching ``_run_is_incomplete``)."

    The test builds ``HarnessResult`` / ``ScenarioRun`` data directly — no twin runs and
    no consensus assembly — so it is pure, fast, and network-free ($0, I-1).

**Validates: Requirements 2.1**
"""
from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from uplift.contract import load_contract
from uplift.fidelity import FidelityReport
from uplift.harness import HarnessResult, aggregate_arm, assemble_uplift_result
from uplift.interfaces import KpiVector, Scenario, ScenarioRun

from digital_twin.simulation.monte_carlo import ShockParams

# The real, version-controlled metric contract (single primary KPI ``fill_rate``).
_CONTRACT = load_contract()
_CONSENSUS_ARM = "consensus"

# Deterministic, available, within-bound fidelity so assembly never touches the live
# C34 gauge — fidelity context is irrelevant to the completeness flag.
_FIDELITY = FidelityReport(kl_divergence=0.02, threshold=0.1)

# Per-``(scenario, arm)`` completeness states with a KNOWN ground truth:
#   "complete"   -> >= 1 completed run, 0 failed runs      => pair IS complete
#   "partial"    -> >= 1 completed run AND >= 1 failed run => pair is NOT complete
#   "all_failed" -> only failed runs                       => pair is NOT complete
#   "empty"      -> no runs recorded at all                => pair is NOT complete
#   "no_kpis"    -> runs not marked failed but carrying no KpiVector (nothing usable)
#                                                          => pair is NOT complete
_COMPLETE_STATE = "complete"
_STATES = (_COMPLETE_STATE, "partial", "all_failed", "empty", "no_kpis")


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


def _runs_for_state(arm: str, state: str, n_completed: int, n_failed: int) -> list[ScenarioRun]:
    """Runs for one ``(scenario, arm)`` pair realising ``state``'s completeness."""
    completed = [
        ScenarioRun(
            arm=arm,
            seed=i,
            kpis=_kpi(0.5 + (i % 5) * 0.001),
            failed=False,
            error=None,
        )
        for i in range(n_completed)
    ]
    failed = [
        ScenarioRun(arm=arm, seed=1000 + i, kpis=None, failed=True, error="injected failure")
        for i in range(n_failed)
    ]
    if state == "complete":
        return completed
    if state == "partial":
        return completed + failed
    if state == "all_failed":
        return failed
    if state == "empty":
        return []
    if state == "no_kpis":
        return [
            ScenarioRun(arm=arm, seed=i, kpis=None, failed=False, error=None)
            for i in range(n_completed)
        ]
    raise ValueError(f"unknown state {state!r}")  # pragma: no cover


@st.composite
def _synthetic_harness_results(draw: st.DrawFn) -> tuple[HarnessResult, dict[tuple[str, str], str]]:
    """A synthetic HarnessResult plus the per-pair states that define its ground truth.

    Constrained to a small grid (1-3 scenarios x 1-3 baseline arms, 1-3 replicates)
    because the property only depends on the per-pair completeness states, not on
    sample sizes — small grids keep the test pure and fast while still covering the
    all-complete case, single-drift cases, and fully-degenerate grids.
    """
    n_scenarios = draw(st.integers(min_value=1, max_value=3))
    n_baselines = draw(st.integers(min_value=1, max_value=3))
    arm_names = (_CONSENSUS_ARM, *(f"baseline-{i}" for i in range(n_baselines)))

    scenarios = [
        Scenario(
            name=f"scenario-{index}",
            seed=4001 + index,
            shock=ShockParams(demand_multiplier=1.0),
        )
        for index in range(n_scenarios)
    ]

    states: dict[tuple[str, str], str] = {}
    runs_by_pair: dict[tuple[str, str], list[ScenarioRun]] = {}
    for scenario in scenarios:
        for arm in arm_names:
            state = draw(st.sampled_from(_STATES))
            n_completed = draw(st.integers(min_value=1, max_value=3))
            n_failed = draw(st.integers(min_value=1, max_value=3))
            pair = (scenario.name, arm)
            states[pair] = state
            runs_by_pair[pair] = _runs_for_state(arm, state, n_completed, n_failed)

    all_runs = [run for runs in runs_by_pair.values() for run in runs]
    harness_result = HarnessResult(
        arm_results={pair: aggregate_arm(pair[1], runs) for pair, runs in runs_by_pair.items()},
        runs_by_pair=runs_by_pair,
        all_runs=all_runs,
        results_path=None,
        scenarios=tuple(scenarios),
        arm_names=arm_names,
    )
    return harness_result, states


@settings(max_examples=200, deadline=None)
@given(case=_synthetic_harness_results())
def test_incomplete_flag_exactly_tracks_run_completeness(
    case: tuple[HarnessResult, dict[tuple[str, str], str]],
) -> None:
    """``incomplete is False`` iff every compared pair has >=1 completed and 0 failed runs."""
    harness_result, states = case

    result = assemble_uplift_result(harness_result, _CONTRACT, fidelity=_FIDELITY)

    every_pair_complete = all(state == _COMPLETE_STATE for state in states.values())

    # The biconditional: the flag is exactly the negation of full completeness.
    assert result.incomplete is (not every_pair_complete), (
        f"incomplete={result.incomplete} for pair states {states}"
    )

    # Cross-check the ground truth directly against the recorded runs, so the property
    # is anchored to the data (>= 1 completed run and 0 failed runs) and not merely to
    # the generator's labels.
    observed_complete = all(
        bool(harness_result.completed_runs(scenario, arm))
        and not any(run.failed for run in harness_result.runs_by_pair[(scenario, arm)])
        for (scenario, arm) in states
    )
    assert result.incomplete is (not observed_complete)


def test_all_pairs_complete_yields_complete_result() -> None:
    """A grid where every compared pair completes cleanly is NOT marked incomplete."""
    scenarios = [
        Scenario(name="scenario-0", seed=4001, shock=ShockParams(demand_multiplier=1.0)),
        Scenario(name="scenario-1", seed=4002, shock=ShockParams(demand_multiplier=1.0)),
    ]
    arm_names = (_CONSENSUS_ARM, "baseline-0")
    runs_by_pair = {
        (scenario.name, arm): _runs_for_state(arm, "complete", 3, 0)
        for scenario in scenarios
        for arm in arm_names
    }
    harness_result = HarnessResult(
        arm_results={pair: aggregate_arm(pair[1], runs) for pair, runs in runs_by_pair.items()},
        runs_by_pair=runs_by_pair,
        all_runs=[run for runs in runs_by_pair.values() for run in runs],
        results_path=None,
        scenarios=tuple(scenarios),
        arm_names=arm_names,
    )

    result = assemble_uplift_result(harness_result, _CONTRACT, fidelity=_FIDELITY)

    assert result.incomplete is False


def test_single_failed_replicate_marks_incomplete() -> None:
    """One failed consensus replicate in an otherwise complete grid marks incomplete."""
    scenario = Scenario(name="scenario-0", seed=4001, shock=ShockParams(demand_multiplier=1.0))
    arm_names = (_CONSENSUS_ARM, "baseline-0")
    runs_by_pair = {
        (scenario.name, _CONSENSUS_ARM): _runs_for_state(_CONSENSUS_ARM, "partial", 3, 1),
        (scenario.name, "baseline-0"): _runs_for_state("baseline-0", "complete", 3, 0),
    }
    harness_result = HarnessResult(
        arm_results={pair: aggregate_arm(pair[1], runs) for pair, runs in runs_by_pair.items()},
        runs_by_pair=runs_by_pair,
        all_runs=[run for runs in runs_by_pair.values() for run in runs],
        results_path=None,
        scenarios=(scenario,),
        arm_names=arm_names,
    )

    result = assemble_uplift_result(harness_result, _CONTRACT, fidelity=_FIDELITY)

    assert result.incomplete is True
