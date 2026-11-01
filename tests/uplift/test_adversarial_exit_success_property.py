"""Property-based test that any completed adversarial run exits success.

Feature: decision-integrity-uplift-proof
Property 18: Any completed adversarial run exits success.

    *For any* distribution of winners across completed adversarial runs — regardless of
    which arm (consensus or baseline) wins each ``(scenario, KPI)`` pair — the harness
    exits with a success status (:data:`uplift.harness.EXIT_SUCCESS` == ``0``) as long
    as at least one scenario completed for some arm. Conversely, when *no* run completed
    (every recorded run failed, or there are no runs at all), the harness returns
    :data:`uplift.harness.EXIT_NO_COMPLETED_RUN` (== ``1``). The exit code is a pure
    function of whether any completed run exists — the winner distribution never affects
    it.

Carried to Metric_Contract v2 (decision-quality-proof task 29.4): a pair's winner is decided by
the committed ``objective``, so that is the KPI varied here. Every registered arm declares its
role (task 15.5), and an ``oracle``-role arm is drawn beside the contrast, so the count the
exit code reads is checked over every registered arm, against a count taken from the draws
rather than from the function under test.

Validates: Requirements 4.6
"""
from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from digital_twin.simulation.monte_carlo import ShockParams
from uplift.harness import (
    EXIT_NO_COMPLETED_RUN,
    EXIT_SUCCESS,
    HarnessResult,
    aggregate_arm,
    completed_run_count,
    uplift_exit_code,
)
from uplift.interfaces import ArmRole, KpiVector, Scenario, ScenarioRun

# The four adversarial scenarios (R4.1); winners are varied across these so the exit
# code is exercised under every winner distribution.
_SCENARIO_NAMES = (
    "demand-spike",
    "supplier-default",
    "monsoon-disruption",
    "cold-start-city",
)
_CONSENSUS_ARM = "consensus"
_BASELINE_ARM = "baseline"
_ORACLE_ARM = "oracle"

#: The role each arm declares (AD-16). The oracle is registered but outside the contrast.
_ARM_ROLES: dict[str, ArmRole] = {
    _CONSENSUS_ARM: "consensus",
    _BASELINE_ARM: "baseline",
    _ORACLE_ARM: "oracle",
}

#: A committed objective on the scale the committed weights produce (lower is better).
_objectives = st.floats(allow_nan=False, allow_infinity=False, min_value=0.0, max_value=12.0)


def _kpi(objective: float) -> KpiVector:
    """A KpiVector varying only ``objective``, the sole primary and so winner-deciding KPI."""
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


# A single per-arm outcome for one scenario: either a COMPLETED run carrying an objective
# (whose value decides the winner) or a FAILED run (``None``: kpis=None, excluded from
# completion).
_run_spec = st.one_of(_objectives, st.none())


def _build_run(arm: str, seed: int, objective: float | None) -> ScenarioRun:
    if objective is not None:
        return ScenarioRun(arm=arm, seed=seed, kpis=_kpi(objective), failed=False, error=None)
    return ScenarioRun(arm=arm, seed=seed, kpis=None, failed=True, error="boom")


@st.composite
def _harness_results(draw: st.DrawFn) -> tuple[HarnessResult, int]:
    """A HarnessResult over the adversarial scenarios with an arbitrary winner mix.

    For each scenario every registered arm gets a list of runs; each run is independently
    completed (with an arbitrary objective, so the winner of every pair varies freely across
    the search space) or failed. This spans every winner distribution — consensus wins,
    baseline wins, ties — plus arbitrary failure mixes, in any arm of any role.

    Returns the result and the number of completed runs DRAWN, counted here from the specs,
    so the property's ground truth is independent of ``completed_run_count``.
    """
    n_scenarios = draw(st.integers(min_value=1, max_value=len(_SCENARIO_NAMES)))
    scenario_names = _SCENARIO_NAMES[:n_scenarios]

    runs_by_pair: dict[tuple[str, str], list[ScenarioRun]] = {}
    scenarios: list[Scenario] = []
    drawn_completed = 0
    for s_index, name in enumerate(scenario_names):
        scenarios.append(
            Scenario(name=name, seed=s_index + 1, shock=ShockParams(demand_multiplier=2.0))
        )
        for arm in _ARM_ROLES:
            specs = draw(st.lists(_run_spec, min_size=0, max_size=6))
            drawn_completed += sum(1 for spec in specs if spec is not None)
            runs_by_pair[(name, arm)] = [
                _build_run(arm, seed, spec) for seed, spec in enumerate(specs)
            ]

    arm_results = {
        pair: aggregate_arm(pair[1], runs) for pair, runs in runs_by_pair.items()
    }
    all_runs = [run for runs in runs_by_pair.values() for run in runs]
    harness_result = HarnessResult(
        arm_results=arm_results,
        runs_by_pair=runs_by_pair,
        all_runs=all_runs,
        results_path=None,
        scenarios=tuple(scenarios),
        arm_names=tuple(_ARM_ROLES),
        arm_roles=_ARM_ROLES,
    )
    return harness_result, drawn_completed


@given(case=_harness_results())
def test_exit_success_iff_any_run_completed(case: tuple[HarnessResult, int]) -> None:
    """Exit is SUCCESS iff >=1 completed run, for ANY winner distribution (R4.6)."""
    harness_result, drawn_completed = case

    # The count the exit code reads is the count that was drawn, over every role.
    assert completed_run_count(harness_result) == drawn_completed
    exit_code = uplift_exit_code(harness_result)

    if drawn_completed > 0:
        # A completed adversarial run is a valid outcome regardless of which arm wins.
        assert exit_code == EXIT_SUCCESS
    else:
        # Nothing completed: there is no result to report.
        assert exit_code == EXIT_NO_COMPLETED_RUN


@given(
    # An arbitrary spread of winners: consensus and baseline objectives are drawn
    # independently, so consensus may win, baseline may win, or they may tie — and the
    # exit code must be SUCCESS in every case because runs completed.
    consensus_objectives=st.lists(_objectives, min_size=1, max_size=20),
    baseline_objectives=st.lists(_objectives, min_size=1, max_size=20),
)
def test_winner_distribution_never_changes_success(
    consensus_objectives: list[float], baseline_objectives: list[float]
) -> None:
    """Any winner distribution over completed runs still exits SUCCESS (R4.6)."""
    scenario = Scenario(
        name="demand-spike", seed=1, shock=ShockParams(demand_multiplier=2.0)
    )
    runs_by_pair = {
        ("demand-spike", _CONSENSUS_ARM): [
            ScenarioRun(arm=_CONSENSUS_ARM, seed=i, kpis=_kpi(obj), failed=False, error=None)
            for i, obj in enumerate(consensus_objectives)
        ],
        ("demand-spike", _BASELINE_ARM): [
            ScenarioRun(arm=_BASELINE_ARM, seed=i, kpis=_kpi(obj), failed=False, error=None)
            for i, obj in enumerate(baseline_objectives)
        ],
    }
    arm_results = {
        pair: aggregate_arm(pair[1], runs) for pair, runs in runs_by_pair.items()
    }
    all_runs = [run for runs in runs_by_pair.values() for run in runs]
    harness_result = HarnessResult(
        arm_results=arm_results,
        runs_by_pair=runs_by_pair,
        all_runs=all_runs,
        results_path=None,
        scenarios=(scenario,),
        arm_names=(_CONSENSUS_ARM, _BASELINE_ARM),
        arm_roles={_CONSENSUS_ARM: "consensus", _BASELINE_ARM: "baseline"},
    )

    assert completed_run_count(harness_result) == (
        len(consensus_objectives) + len(baseline_objectives)
    )
    assert uplift_exit_code(harness_result) == EXIT_SUCCESS


@given(
    # Every run across every pair failed -> no completed run -> EXIT_NO_COMPLETED_RUN.
    failed_counts=st.lists(st.integers(min_value=0, max_value=6), min_size=1, max_size=4),
)
def test_all_failed_returns_no_completed_run(failed_counts: list[int]) -> None:
    """When no run completed (all failed), exit is EXIT_NO_COMPLETED_RUN (R4.6)."""
    scenarios: list[Scenario] = []
    runs_by_pair: dict[tuple[str, str], list[ScenarioRun]] = {}
    for s_index, n_failed in enumerate(failed_counts):
        name = _SCENARIO_NAMES[s_index % len(_SCENARIO_NAMES)]
        scenarios.append(
            Scenario(name=name, seed=s_index + 1, shock=ShockParams(demand_multiplier=2.0))
        )
        runs_by_pair[(name, _CONSENSUS_ARM)] = [
            ScenarioRun(arm=_CONSENSUS_ARM, seed=i, kpis=None, failed=True, error="boom")
            for i in range(n_failed)
        ]

    arm_results = {
        pair: aggregate_arm(pair[1], runs) for pair, runs in runs_by_pair.items()
    }
    all_runs = [run for runs in runs_by_pair.values() for run in runs]
    harness_result = HarnessResult(
        arm_results=arm_results,
        runs_by_pair=runs_by_pair,
        all_runs=all_runs,
        results_path=None,
        scenarios=tuple(scenarios),
        arm_names=(_CONSENSUS_ARM,),
        arm_roles={_CONSENSUS_ARM: "consensus"},
    )

    assert completed_run_count(harness_result) == 0
    assert uplift_exit_code(harness_result) == EXIT_NO_COMPLETED_RUN
