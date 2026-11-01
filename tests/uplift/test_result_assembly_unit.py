"""
Unit (example-based) tests for the uplift result-assembly + reporting API (task 10.1).

These complement the Property 13–19 tests (tasks 10.2–10.8); here we pin down concrete
behavior of :func:`uplift.harness.assemble_uplift_result`, the fidelity-co-located
:func:`uplift.harness.build_uplift_report`, and :func:`uplift.harness.uplift_exit_code`
on small, hand-built :class:`HarnessResult` fixtures.

Carried to Metric_Contract v2 and the v2 harness (decision-quality-proof tasks 29.4, 15.5).
The committed contract is loaded, so the judged KPI is the ``objective`` -- a cost, lower is
better -- and a verdict is read off the ``1 - alpha`` paired interval against the committed
materiality margin. Every fixture registers its arms with their roles, and the v2 result
fields (the interval, the four-valued verdict, the margin, the recorded comparator and the
whole-run predicate) are pinned beside the outcomes they explain.
"""
from __future__ import annotations

import pytest

from digital_twin.simulation.monte_carlo import ShockParams
from uplift.contract import load_contract
from uplift.fidelity import FidelityReport
from uplift.harness import (
    EXIT_NO_COMPLETED_RUN,
    EXIT_SUCCESS,
    NO_ESTIMATE_HEADLINE,
    HarnessResult,
    aggregate_arm,
    assemble_uplift_result,
    build_uplift_report,
    completed_run_count,
    uplift_exit_code,
)
from uplift.interfaces import ArmRole, KpiVector, Outcome, Scenario, ScenarioRun

# The real, version-controlled metric contract (v2).
CONTRACT = load_contract()
OBJECTIVE = CONTRACT.objective_kpi
MARGIN = CONTRACT.materiality_margin

# A fidelity report that is available and within bound, so reporting is deterministic
# (no dependence on the live C34 gauge in unit tests).
FIDELITY = FidelityReport(kl_divergence=0.02, threshold=0.1)

# Objective levels (lower is better): the baseline costs four margins more than consensus,
# so a contrast between them lies wholly above the margin.
CHEAP = 10.0
DEAR = CHEAP + 4.0 * MARGIN

#: The two-arm registration most fixtures use.
TWO_ARMS: dict[str, ArmRole] = {"consensus": "consensus", "baseline": "baseline"}


def _kpi(objective: float) -> KpiVector:
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


def _runs(arm: str, objectives: list[float]) -> list[ScenarioRun]:
    return [
        ScenarioRun(arm=arm, seed=i, kpis=_kpi(objective), failed=False, error=None)
        for i, objective in enumerate(objectives)
    ]


def _series(base: float, n: int = 40) -> list[float]:
    """A small spread of values, shared by every arm so the paired differences are flat."""
    return [base + (i % 5) * 0.001 for i in range(n)]


def _harness_result(
    runs_by_pair: dict[tuple[str, str], list[ScenarioRun]],
    scenarios: tuple[Scenario, ...],
    arm_roles: dict[str, ArmRole],
) -> HarnessResult:
    arm_results = {
        pair: aggregate_arm(pair[1], runs) for pair, runs in runs_by_pair.items()
    }
    all_runs = [run for runs in runs_by_pair.values() for run in runs]
    return HarnessResult(
        arm_results=arm_results,
        runs_by_pair=runs_by_pair,
        all_runs=all_runs,
        results_path=None,
        scenarios=scenarios,
        arm_names=tuple(arm_roles),
        arm_roles=arm_roles,
    )


SCEN = Scenario(name="demand-spike", seed=1, shock=ShockParams(demand_multiplier=2.0))


def test_synapse_wins_when_consensus_is_clearly_cheaper() -> None:
    runs_by_pair = {
        ("demand-spike", "consensus"): _runs("consensus", _series(CHEAP)),
        ("demand-spike", "baseline"): _runs("baseline", _series(DEAR)),
    }
    hr = _harness_result(runs_by_pair, (SCEN,), TWO_ARMS)

    result = assemble_uplift_result(hr, CONTRACT, fidelity=FIDELITY)

    assert result.per_scenario[("demand-spike", OBJECTIVE)] is Outcome.SYNAPSE_WINS
    assert result.per_kpi[OBJECTIVE] is Outcome.SYNAPSE_WINS
    # every pair is a SYNAPSE win -> self-scrutiny warning (R4.5)
    assert result.all_wins_warning is True
    assert result.incomplete is False
    assert result.run_incomplete is False
    # The headline is the mean paired objective difference, comparator minus subject, in
    # objective units: positive because consensus is cheaper. It IS the interval's point,
    # and the interval lies wholly above the committed margin, so the verdict is a win.
    assert result.interval is not None
    assert result.headline_uplift == result.interval.point
    assert result.headline_uplift == pytest.approx(4.0 * MARGIN)
    assert result.interval.low > MARGIN
    assert result.headline_verdict == "win"
    assert result.materiality_margin == MARGIN
    # The unnamed comparator is recorded as the pool it is, never left implicit (AD-16).
    assert result.comparator == "pooled:baseline"


def test_secondary_kpis_are_all_non_primary_fields() -> None:
    runs_by_pair = {
        ("demand-spike", "consensus"): _runs("consensus", _series(CHEAP)),
        ("demand-spike", "baseline"): _runs("baseline", _series(DEAR)),
    }
    hr = _harness_result(runs_by_pair, (SCEN,), TWO_ARMS)

    result = assemble_uplift_result(hr, CONTRACT, fidelity=FIDELITY)

    # The objective is the sole primary KPI; every other field -- fill_rate included -- is
    # secondary (R7.19).
    assert OBJECTIVE not in result.secondary_kpis
    assert set(result.secondary_kpis) == {
        "fill_rate",
        "spoilage_rate",
        "stockout_rate",
        "avg_delivery_time_min",
        "margin",
        "co2_estimate",
        "avg_on_hand_units",
    }


def test_all_wins_warning_false_when_a_tie_exists() -> None:
    # consensus == baseline objectives -> the interval contains 0: inconclusive, not a win.
    runs_by_pair = {
        ("demand-spike", "consensus"): _runs("consensus", _series(CHEAP)),
        ("demand-spike", "baseline"): _runs("baseline", _series(CHEAP)),
    }
    hr = _harness_result(runs_by_pair, (SCEN,), TWO_ARMS)

    result = assemble_uplift_result(hr, CONTRACT, fidelity=FIDELITY)

    assert result.per_scenario[("demand-spike", OBJECTIVE)] is Outcome.TIE_INCONCLUSIVE
    assert result.headline_verdict == "inconclusive"
    assert result.all_wins_warning is False


def test_incomplete_pair_never_credited_to_synapse() -> None:
    # A failed consensus run for the scenario -> no completed consensus samples.
    failed_consensus = [
        ScenarioRun(arm="consensus", seed=0, kpis=None, failed=True, error="boom")
    ]
    runs_by_pair = {
        ("demand-spike", "consensus"): failed_consensus,
        ("demand-spike", "baseline"): _runs("baseline", _series(DEAR)),
    }
    hr = _harness_result(runs_by_pair, (SCEN,), TWO_ARMS)

    result = assemble_uplift_result(hr, CONTRACT, fidelity=FIDELITY)

    assert result.incomplete is True
    assert result.run_incomplete is True
    outcome = result.per_scenario[("demand-spike", OBJECTIVE)]
    assert outcome is Outcome.TIE_INCONCLUSIVE
    assert outcome is not Outcome.SYNAPSE_WINS
    # No replicate paired, so nothing was estimated: no interval, no verdict, and the
    # headline is the no-estimate sentinel rather than a measurement (I-7).
    assert result.interval is None
    assert result.headline_verdict is None
    assert result.headline_uplift == NO_ESTIMATE_HEADLINE
    assert result.per_kpi[OBJECTIVE] is Outcome.TIE_INCONCLUSIVE


def test_every_executed_scenario_is_reported() -> None:
    scen2 = Scenario(name="supplier-default", seed=2, shock=ShockParams(lead_time_multiplier=2.0))
    runs_by_pair = {
        ("demand-spike", "consensus"): _runs("consensus", _series(CHEAP)),
        ("demand-spike", "baseline"): _runs("baseline", _series(DEAR)),
        ("supplier-default", "consensus"): _runs("consensus", _series(DEAR)),
        ("supplier-default", "baseline"): _runs("baseline", _series(CHEAP)),
    }
    hr = _harness_result(runs_by_pair, (SCEN, scen2), TWO_ARMS)

    result = assemble_uplift_result(hr, CONTRACT, fidelity=FIDELITY)

    reported_scenarios = {scenario for scenario, _ in result.per_scenario}
    assert reported_scenarios == {"demand-spike", "supplier-default"}
    # baseline is cheaper on the second scenario -> not an all-wins grid
    assert result.per_scenario[("supplier-default", OBJECTIVE)] is Outcome.BASELINE_WINS
    assert result.all_wins_warning is False


def test_pooled_baseline_over_multiple_baseline_arms() -> None:
    # An oracle-role arm far cheaper than consensus is registered beside the two baselines.
    # Pooled, it would pull the comparator below consensus; AD-16 keeps it out of the pool.
    arm_roles: dict[str, ArmRole] = {
        "consensus": "consensus",
        "par_level_reorder": "baseline",
        "static_pricing": "baseline",
        "oracle": "oracle",
    }
    runs_by_pair = {
        ("demand-spike", "consensus"): _runs("consensus", _series(CHEAP)),
        ("demand-spike", "par_level_reorder"): _runs("par_level_reorder", _series(DEAR)),
        ("demand-spike", "static_pricing"): _runs("static_pricing", _series(DEAR + MARGIN)),
        ("demand-spike", "oracle"): _runs("oracle", _series(CHEAP - 20.0 * MARGIN)),
    }
    hr = _harness_result(runs_by_pair, (SCEN,), arm_roles)

    result = assemble_uplift_result(hr, CONTRACT, fidelity=FIDELITY)

    # consensus vs the per-replicate mean of the two baselines (4.5 margins dearer) -> win
    assert result.per_scenario[("demand-spike", OBJECTIVE)] is Outcome.SYNAPSE_WINS
    assert result.comparator == "pooled:par_level_reorder,static_pricing"
    assert result.headline_uplift == pytest.approx(4.5 * MARGIN)


def test_exit_code_success_when_any_run_completed() -> None:
    runs_by_pair = {
        ("demand-spike", "consensus"): _runs("consensus", _series(CHEAP)),
        ("demand-spike", "baseline"): _runs("baseline", _series(DEAR)),
    }
    hr = _harness_result(runs_by_pair, (SCEN,), TWO_ARMS)

    assert completed_run_count(hr) == 80
    assert uplift_exit_code(hr) == EXIT_SUCCESS


def test_exit_code_failure_when_nothing_completed() -> None:
    only_failed = {
        ("demand-spike", "consensus"): [
            ScenarioRun(arm="consensus", seed=0, kpis=None, failed=True, error="x")
        ],
    }
    hr = _harness_result(only_failed, (SCEN,), {"consensus": "consensus"})

    assert completed_run_count(hr) == 0
    assert uplift_exit_code(hr) == EXIT_NO_COMPLETED_RUN


def test_report_colocates_uplift_with_fidelity_context() -> None:
    runs_by_pair = {
        ("demand-spike", "consensus"): _runs("consensus", _series(CHEAP)),
        ("demand-spike", "baseline"): _runs("baseline", _series(DEAR)),
    }
    hr = _harness_result(runs_by_pair, (SCEN,), TWO_ARMS)
    result = assemble_uplift_result(hr, CONTRACT, fidelity=FIDELITY)

    report = build_uplift_report(result)
    assert report.primary_kpi == OBJECTIVE
    assert report.kl_divergence == pytest.approx(0.02)
    assert report.threshold == pytest.approx(0.1)
    assert report.within_fidelity_bound is True
    assert report.confidence == "within_fidelity_bound"
    # The interval, verdict, margin and comparator travel with the number (R7.14).
    assert report.interval == result.interval
    assert report.headline_verdict == result.headline_verdict
    assert report.materiality_margin == result.materiality_margin
    assert report.comparator == result.comparator

    rendered = report.render()
    assert "headline uplift" in rendered
    assert "twin KL divergence" in rendered
    assert "bounded by twin fidelity" in rendered
    assert "within_fidelity_bound" in rendered
    assert f"comparator: {result.comparator}" in rendered
    assert "verdict: win" in rendered
    assert "interval: [" in rendered


def test_report_marks_unavailable_fidelity() -> None:
    runs_by_pair = {
        ("demand-spike", "consensus"): _runs("consensus", _series(CHEAP)),
        ("demand-spike", "baseline"): _runs("baseline", _series(DEAR)),
    }
    hr = _harness_result(runs_by_pair, (SCEN,), TWO_ARMS)
    unavailable = FidelityReport(kl_divergence=None, threshold=0.1)
    result = assemble_uplift_result(hr, CONTRACT, fidelity=unavailable)

    report = build_uplift_report(result)
    assert report.within_fidelity_bound is None
    assert report.confidence == "unknown"
    assert "unavailable" in report.render()
