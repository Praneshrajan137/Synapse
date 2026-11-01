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

Carried to the v2 harness (decision-quality-proof task 15.5). ``incomplete`` is the CONTRAST
predicate: the compared pairs are the consensus arm's and the comparator's, which under the
pooled default are exactly the arms that declared the ``baseline`` role. The whole-run
predicate, ``_run_is_incomplete``, is now reported as ``run_incomplete``. Arms declaring
``oracle`` or ``excluded`` are drawn beside the contrast with free states, and both
biconditionals are asserted.

The biconditional rests on a premise the harness supplies (Property 17): the arms' replicates
share seeds. v2 pairs replicates on seed, so a scenario with no seed-paired replicate is
incomplete even when every pair completed. This generator meets the premise (every completed
run list starts at seed 0); the seed-disjoint case is pinned separately.

**Validates: Requirements 2.1**
"""
from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from digital_twin.simulation.monte_carlo import ShockParams
from uplift.contract import load_contract
from uplift.fidelity import FidelityReport
from uplift.harness import HarnessResult, aggregate_arm, assemble_uplift_result
from uplift.interfaces import ArmRole, KpiVector, Scenario, ScenarioRun

if TYPE_CHECKING:
    from collections.abc import Iterable

# The real, version-controlled metric contract (v2: the committed objective is the sole
# primary KPI).
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

#: The roles that register an arm WITHOUT placing it in the consensus contrast (AD-16).
_OUTSIDE_ROLES: tuple[ArmRole, ...] = ("oracle", "excluded")


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


def _completed(arm: str, seeds: Iterable[int]) -> list[ScenarioRun]:
    """Completed runs for ``arm`` at ``seeds``, with a small spread of objectives."""
    return [
        ScenarioRun(
            arm=arm, seed=seed, kpis=_kpi(0.5 + (seed % 5) * 0.001), failed=False, error=None
        )
        for seed in seeds
    ]


def _runs_for_state(arm: str, state: str, n_completed: int, n_failed: int) -> list[ScenarioRun]:
    """Runs for one ``(scenario, arm)`` pair realising ``state``'s completeness."""
    completed = _completed(arm, range(n_completed))
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


def _harness(
    runs_by_pair: dict[tuple[str, str], list[ScenarioRun]],
    scenarios: Iterable[Scenario],
    arm_roles: dict[str, ArmRole],
) -> HarnessResult:
    """A HarnessResult over ``runs_by_pair``, registering every arm with its declared role."""
    return HarnessResult(
        arm_results={pair: aggregate_arm(pair[1], runs) for pair, runs in runs_by_pair.items()},
        runs_by_pair=runs_by_pair,
        all_runs=[run for runs in runs_by_pair.values() for run in runs],
        results_path=None,
        scenarios=tuple(scenarios),
        arm_names=tuple(arm_roles),
        arm_roles=arm_roles,
    )


def _scenario(index: int) -> Scenario:
    return Scenario(
        name=f"scenario-{index}", seed=4001 + index, shock=ShockParams(demand_multiplier=1.0)
    )


def _observed_complete(harness_result: HarnessResult, pairs: Iterable[tuple[str, str]]) -> bool:
    """Every pair has >= 1 completed run and 0 failed runs, read off the recorded runs."""
    return all(
        bool(harness_result.completed_runs(scenario, arm))
        and not any(run.failed for run in harness_result.runs_by_pair[(scenario, arm)])
        for scenario, arm in pairs
    )


@dataclasses.dataclass(frozen=True)
class _Case:
    """A synthetic run, the per-pair states that are its ground truth, and its contrast."""

    harness_result: HarnessResult
    states: dict[tuple[str, str], str]
    contrast_arms: frozenset[str]


@st.composite
def _synthetic_harness_results(draw: st.DrawFn) -> _Case:
    """A synthetic HarnessResult plus the per-pair states that define its ground truth.

    Constrained to a small grid (1-3 scenarios x 1-3 baseline arms x 0-2 arms outside the
    contrast, 1-3 replicates) because the property only depends on the per-pair completeness
    states, not on sample sizes — small grids keep the test pure and fast while still
    covering the all-complete case, single-drift cases, and fully-degenerate grids.
    """
    n_scenarios = draw(st.integers(min_value=1, max_value=3))
    n_baselines = draw(st.integers(min_value=1, max_value=3))
    outside_roles = draw(st.lists(st.sampled_from(_OUTSIDE_ROLES), max_size=2))
    baselines = tuple(f"baseline-{i}" for i in range(n_baselines))
    outside = tuple(f"outside-{i}" for i in range(len(outside_roles)))

    arm_roles: dict[str, ArmRole] = {_CONSENSUS_ARM: "consensus"}
    for arm in baselines:
        arm_roles[arm] = "baseline"
    for arm, role in zip(outside, outside_roles, strict=True):
        arm_roles[arm] = role

    scenarios = [_scenario(index) for index in range(n_scenarios)]
    states: dict[tuple[str, str], str] = {}
    runs_by_pair: dict[tuple[str, str], list[ScenarioRun]] = {}
    for scenario in scenarios:
        for arm in arm_roles:
            state = draw(st.sampled_from(_STATES))
            n_completed = draw(st.integers(min_value=1, max_value=3))
            n_failed = draw(st.integers(min_value=1, max_value=3))
            pair = (scenario.name, arm)
            states[pair] = state
            runs_by_pair[pair] = _runs_for_state(arm, state, n_completed, n_failed)

    return _Case(
        harness_result=_harness(runs_by_pair, scenarios, arm_roles),
        states=states,
        contrast_arms=frozenset({_CONSENSUS_ARM, *baselines}),
    )


@settings(deadline=None)
@given(case=_synthetic_harness_results())
def test_incomplete_flag_exactly_tracks_run_completeness(case: _Case) -> None:
    """``incomplete is False`` iff every compared pair has >=1 completed and 0 failed runs."""
    result = assemble_uplift_result(case.harness_result, _CONTRACT, fidelity=_FIDELITY)

    compared = [pair for pair in case.states if pair[1] in case.contrast_arms]
    assert compared, "the contrast must hold the consensus arm and at least one baseline"
    every_compared_pair_complete = all(case.states[pair] == _COMPLETE_STATE for pair in compared)
    every_pair_complete = all(state == _COMPLETE_STATE for state in case.states.values())

    # The biconditional: the flag is exactly the negation of the contrast's completeness ...
    assert result.incomplete is (not every_compared_pair_complete), (
        f"incomplete={result.incomplete} for pair states {case.states}"
    )
    # ... and the whole-run flag is exactly the negation of every registered pair's.
    assert result.run_incomplete is (not every_pair_complete), (
        f"run_incomplete={result.run_incomplete} for pair states {case.states}"
    )

    # Cross-check the ground truth directly against the recorded runs, so the property
    # is anchored to the data (>= 1 completed run and 0 failed runs) and not merely to
    # the generator's labels.
    assert result.incomplete is (not _observed_complete(case.harness_result, compared))
    assert result.run_incomplete is (not _observed_complete(case.harness_result, case.states))


def test_all_pairs_complete_yields_complete_result() -> None:
    """A grid where every compared pair completes cleanly is NOT marked incomplete."""
    scenarios = [_scenario(0), _scenario(1)]
    arm_roles: dict[str, ArmRole] = {_CONSENSUS_ARM: "consensus", "baseline-0": "baseline"}
    runs_by_pair = {
        (scenario.name, arm): _runs_for_state(arm, "complete", 3, 0)
        for scenario in scenarios
        for arm in arm_roles
    }

    result = assemble_uplift_result(
        _harness(runs_by_pair, scenarios, arm_roles), _CONTRACT, fidelity=_FIDELITY
    )

    assert result.incomplete is False
    assert result.run_incomplete is False


def test_single_failed_replicate_marks_incomplete() -> None:
    """One failed consensus replicate in an otherwise complete grid marks incomplete."""
    scenario = _scenario(0)
    arm_roles: dict[str, ArmRole] = {_CONSENSUS_ARM: "consensus", "baseline-0": "baseline"}
    runs_by_pair = {
        (scenario.name, _CONSENSUS_ARM): _runs_for_state(_CONSENSUS_ARM, "partial", 3, 1),
        (scenario.name, "baseline-0"): _runs_for_state("baseline-0", "complete", 3, 0),
    }

    result = assemble_uplift_result(
        _harness(runs_by_pair, [scenario], arm_roles), _CONTRACT, fidelity=_FIDELITY
    )

    # A failed contrast replicate marks the contrast incomplete, and the run with it.
    assert result.incomplete is True
    assert result.run_incomplete is True


@pytest.mark.parametrize("role", _OUTSIDE_ROLES)
def test_a_failed_replicate_outside_the_contrast_marks_only_the_run_incomplete(
    role: ArmRole,
) -> None:
    """An oracle or excluded arm's failure leaves the contrast complete (AD-16, task 15.5).

    The direction the v2 split exists for: one failed oracle replicate used to drive the
    consensus verdict to unavailable without being any part of it.
    """
    scenario = _scenario(0)
    arm_roles: dict[str, ArmRole] = {
        _CONSENSUS_ARM: "consensus",
        "baseline-0": "baseline",
        "outside-0": role,
    }
    runs_by_pair = {
        (scenario.name, _CONSENSUS_ARM): _runs_for_state(_CONSENSUS_ARM, "complete", 3, 0),
        (scenario.name, "baseline-0"): _runs_for_state("baseline-0", "complete", 3, 0),
        (scenario.name, "outside-0"): _runs_for_state("outside-0", "partial", 3, 1),
    }

    result = assemble_uplift_result(
        _harness(runs_by_pair, [scenario], arm_roles), _CONTRACT, fidelity=_FIDELITY
    )

    assert result.incomplete is False
    assert result.run_incomplete is True
    # The contrast was still estimated: the outside failure withheld nothing from it.
    assert result.interval is not None
    assert result.comparator == "pooled:baseline-0"


def test_a_baseline_the_named_comparator_did_not_choose_cannot_mark_it_incomplete() -> None:
    """Naming a comparator scopes the contrast to it; pooling scopes it to every baseline."""
    scenario = _scenario(0)
    arm_roles: dict[str, ArmRole] = {
        _CONSENSUS_ARM: "consensus",
        "baseline-0": "baseline",
        "baseline-1": "baseline",
    }
    runs_by_pair = {
        (scenario.name, _CONSENSUS_ARM): _runs_for_state(_CONSENSUS_ARM, "complete", 3, 0),
        (scenario.name, "baseline-0"): _runs_for_state("baseline-0", "complete", 3, 0),
        (scenario.name, "baseline-1"): _runs_for_state("baseline-1", "partial", 3, 1),
    }
    harness_result = _harness(runs_by_pair, [scenario], arm_roles)

    named_clean = assemble_uplift_result(
        harness_result, _CONTRACT, fidelity=_FIDELITY, baseline_arm="baseline-0"
    )
    named_failed = assemble_uplift_result(
        harness_result, _CONTRACT, fidelity=_FIDELITY, baseline_arm="baseline-1"
    )
    pooled = assemble_uplift_result(harness_result, _CONTRACT, fidelity=_FIDELITY)

    assert (named_clean.incomplete, named_clean.run_incomplete) == (False, True)
    assert (named_failed.incomplete, named_failed.run_incomplete) == (True, True)
    assert (pooled.incomplete, pooled.run_incomplete) == (True, True)


def test_complete_pairs_with_no_seed_paired_replicate_are_still_incomplete() -> None:
    """Where R2.1's "if" direction stops holding under v2: no paired replicate, no contrast.

    Every pair below has completed runs and no failure, but the two arms ran on disjoint
    seeds, so no replicate pairs and nothing was compared. v2 marks the contrast incomplete
    and estimates no interval rather than judge on nothing. ``UpliftHarness.run`` cannot
    produce this shape (Property 17); a hand-built or merged ``HarnessResult`` can.
    """
    scenario = _scenario(0)
    arm_roles: dict[str, ArmRole] = {_CONSENSUS_ARM: "consensus", "baseline-0": "baseline"}
    runs_by_pair = {
        (scenario.name, _CONSENSUS_ARM): _completed(_CONSENSUS_ARM, range(0, 3)),
        (scenario.name, "baseline-0"): _completed("baseline-0", range(10, 13)),
    }
    harness_result = _harness(runs_by_pair, [scenario], arm_roles)
    assert _observed_complete(harness_result, runs_by_pair)

    result = assemble_uplift_result(harness_result, _CONTRACT, fidelity=_FIDELITY)

    assert result.incomplete is True
    assert result.run_incomplete is False
    assert result.interval is None
    assert result.headline_verdict is None
