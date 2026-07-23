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

Validates: Requirements 4.6
"""
from __future__ import annotations

from hypothesis import given, settings
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
from uplift.interfaces import KpiVector, Scenario, ScenarioRun

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


def _kpi(fill_rate: float) -> KpiVector:
    """A KpiVector varying only ``fill_rate`` (the winner-determining KPI)."""
    return KpiVector(
        fill_rate=fill_rate,
        spoilage_rate=0.0,
        stockout_rate=0.0,
        avg_delivery_time_min=1.0,
        margin=1.0,
        co2_estimate=1.0,
    )


# A single per-arm outcome for one scenario: either a COMPLETED run carrying a fill_rate
# (whose value decides the winner) or a FAILED run (kpis=None, excluded from completion).
_completed_run = st.floats(
    allow_nan=False, allow_infinity=False, min_value=0.0, max_value=1.0
).map(lambda fr: ("completed", fr))
_failed_run = st.just(("failed", None))
_run_spec = st.one_of(_completed_run, _failed_run)


def _build_run(arm: str, seed: int, spec: tuple[str, float | None]) -> ScenarioRun:
    kind, fill_rate = spec
    if kind == "completed":
        return ScenarioRun(arm=arm, seed=seed, kpis=_kpi(fill_rate), failed=False, error=None)
    return ScenarioRun(arm=arm, seed=seed, kpis=None, failed=True, error="boom")


@st.composite
def _harness_results(draw: st.DrawFn) -> HarnessResult:
    """A HarnessResult over the adversarial scenarios with an arbitrary winner mix.

    For each scenario the consensus and baseline arms each get a list of runs; each run
    is independently completed (with an arbitrary fill_rate, so the winner of every
    pair varies freely across the search space) or failed. This spans every winner
    distribution — consensus wins, baseline wins, ties — plus arbitrary failure mixes.
    """
    n_scenarios = draw(st.integers(min_value=1, max_value=len(_SCENARIO_NAMES)))
    scenario_names = _SCENARIO_NAMES[:n_scenarios]

    runs_by_pair: dict[tuple[str, str], list[ScenarioRun]] = {}
    scenarios: list[Scenario] = []
    for s_index, name in enumerate(scenario_names):
        scenarios.append(
            Scenario(name=name, seed=s_index + 1, shock=ShockParams(demand_multiplier=2.0))
        )
        for arm in (_CONSENSUS_ARM, _BASELINE_ARM):
            specs = draw(st.lists(_run_spec, min_size=0, max_size=6))
            runs_by_pair[(name, arm)] = [
                _build_run(arm, seed, spec) for seed, spec in enumerate(specs)
            ]

    arm_results = {
        pair: aggregate_arm(pair[1], runs) for pair, runs in runs_by_pair.items()
    }
    all_runs = [run for runs in runs_by_pair.values() for run in runs]
    return HarnessResult(
        arm_results=arm_results,
        runs_by_pair=runs_by_pair,
        all_runs=all_runs,
        results_path=None,
        scenarios=tuple(scenarios),
        arm_names=(_CONSENSUS_ARM, _BASELINE_ARM),
    )


@settings(max_examples=200)
@given(harness_result=_harness_results())
def test_exit_success_iff_any_run_completed(harness_result: HarnessResult) -> None:
    """Exit is SUCCESS iff >=1 completed run, for ANY winner distribution (R4.6)."""
    n_completed = completed_run_count(harness_result)
    exit_code = uplift_exit_code(harness_result)

    if n_completed > 0:
        # A completed adversarial run is a valid outcome regardless of which arm wins.
        assert exit_code == EXIT_SUCCESS
    else:
        # Nothing completed: there is no result to report.
        assert exit_code == EXIT_NO_COMPLETED_RUN


@settings(max_examples=100)
@given(
    # An arbitrary spread of winners: consensus and baseline fill_rates are drawn
    # independently, so consensus may win, baseline may win, or they may tie — and the
    # exit code must be SUCCESS in every case because runs completed.
    consensus_fill_rates=st.lists(
        st.floats(allow_nan=False, allow_infinity=False, min_value=0.0, max_value=1.0),
        min_size=1,
        max_size=20,
    ),
    baseline_fill_rates=st.lists(
        st.floats(allow_nan=False, allow_infinity=False, min_value=0.0, max_value=1.0),
        min_size=1,
        max_size=20,
    ),
)
def test_winner_distribution_never_changes_success(
    consensus_fill_rates: list[float], baseline_fill_rates: list[float]
) -> None:
    """Any winner distribution over completed runs still exits SUCCESS (R4.6)."""
    scenario = Scenario(
        name="demand-spike", seed=1, shock=ShockParams(demand_multiplier=2.0)
    )
    runs_by_pair = {
        ("demand-spike", _CONSENSUS_ARM): [
            ScenarioRun(arm=_CONSENSUS_ARM, seed=i, kpis=_kpi(fr), failed=False, error=None)
            for i, fr in enumerate(consensus_fill_rates)
        ],
        ("demand-spike", _BASELINE_ARM): [
            ScenarioRun(arm=_BASELINE_ARM, seed=i, kpis=_kpi(fr), failed=False, error=None)
            for i, fr in enumerate(baseline_fill_rates)
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
    )

    assert completed_run_count(harness_result) > 0
    assert uplift_exit_code(harness_result) == EXIT_SUCCESS


@settings(max_examples=100)
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
    )

    assert completed_run_count(harness_result) == 0
    assert uplift_exit_code(harness_result) == EXIT_NO_COMPLETED_RUN
