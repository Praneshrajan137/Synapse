"""
Unit (example-based) tests for the uplift result-assembly + reporting API (task 10.1).

These complement the Property 13–19 tests (tasks 10.2–10.8); here we pin down concrete
behavior of :func:`uplift.harness.assemble_uplift_result`, the fidelity-co-located
:func:`uplift.harness.build_uplift_report`, and :func:`uplift.harness.uplift_exit_code`
on small, hand-built :class:`HarnessResult` fixtures.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from uplift.contract import MetricContract
from uplift.fidelity import FidelityReport
from uplift.harness import (
    EXIT_NO_COMPLETED_RUN,
    EXIT_SUCCESS,
    HarnessResult,
    aggregate_arm,
    assemble_uplift_result,
    build_uplift_report,
    completed_run_count,
    uplift_exit_code,
)
from uplift.interfaces import (
    ArmResult,
    Direction,
    KpiVector,
    Outcome,
    Scenario,
    ScenarioRun,
)
from digital_twin.simulation.monte_carlo import ShockParams


CONTRACT = MetricContract(
    primary_kpis={"fill_rate": Direction.HIGHER_IS_BETTER},
    effect_size="cohens_d+rel_pct",
    significance_test="mann_whitney_u",
    alpha=0.05,
    mde={"fill_rate": 0.2},
    decision_rule="significant_and_favorable_and_meets_mde",
)

# A fidelity report that is available and within bound, so reporting is deterministic
# (no dependence on the live C34 gauge in unit tests).
FIDELITY = FidelityReport(kl_divergence=0.02, threshold=0.1)


def _kpi(fill_rate: float) -> KpiVector:
    return KpiVector(
        fill_rate=fill_rate,
        spoilage_rate=0.0,
        stockout_rate=0.0,
        avg_delivery_time_min=1.0,
        margin=1.0,
        co2_estimate=1.0,
    )


def _runs(arm: str, fill_rates: list[float]) -> list[ScenarioRun]:
    return [
        ScenarioRun(arm=arm, seed=i, kpis=_kpi(fr), failed=False, error=None)
        for i, fr in enumerate(fill_rates)
    ]


def _series(base: float, n: int = 40) -> list[float]:
    """A small spread of values so the significance test is well-defined."""
    return [base + (i % 5) * 0.001 for i in range(n)]


def _harness_result(
    runs_by_pair: dict[tuple[str, str], list[ScenarioRun]],
    scenarios: tuple[Scenario, ...],
    arm_names: tuple[str, ...],
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
        arm_names=arm_names,
    )


SCEN = Scenario(name="demand-spike", seed=1, shock=ShockParams(demand_multiplier=2.0))


def test_synapse_wins_when_consensus_clearly_higher():
    runs_by_pair = {
        ("demand-spike", "consensus"): _runs("consensus", _series(0.9)),
        ("demand-spike", "baseline"): _runs("baseline", _series(0.5)),
    }
    hr = _harness_result(runs_by_pair, (SCEN,), ("consensus", "baseline"))

    result = assemble_uplift_result(hr, CONTRACT, fidelity=FIDELITY)

    assert result.per_scenario[("demand-spike", "fill_rate")] is Outcome.SYNAPSE_WINS
    assert result.per_kpi["fill_rate"] is Outcome.SYNAPSE_WINS
    # every pair is a SYNAPSE win -> self-scrutiny warning (R4.5)
    assert result.all_wins_warning is True
    assert result.incomplete is False
    # relative % improvement of 0.9 over 0.5 ~ +80 pp, positive because higher-is-better
    assert result.headline_uplift > 0.0


def test_secondary_kpis_are_all_non_primary_fields():
    runs_by_pair = {
        ("demand-spike", "consensus"): _runs("consensus", _series(0.9)),
        ("demand-spike", "baseline"): _runs("baseline", _series(0.5)),
    }
    hr = _harness_result(runs_by_pair, (SCEN,), ("consensus", "baseline"))

    result = assemble_uplift_result(hr, CONTRACT, fidelity=FIDELITY)

    assert "fill_rate" not in result.secondary_kpis
    assert set(result.secondary_kpis) == {
        "spoilage_rate",
        "stockout_rate",
        "avg_delivery_time_min",
        "margin",
        "co2_estimate",
    }


def test_all_wins_warning_false_when_a_tie_exists():
    # consensus == baseline distribution -> tie/inconclusive, not a SYNAPSE win.
    runs_by_pair = {
        ("demand-spike", "consensus"): _runs("consensus", _series(0.6)),
        ("demand-spike", "baseline"): _runs("baseline", _series(0.6)),
    }
    hr = _harness_result(runs_by_pair, (SCEN,), ("consensus", "baseline"))

    result = assemble_uplift_result(hr, CONTRACT, fidelity=FIDELITY)

    assert result.per_scenario[("demand-spike", "fill_rate")] is Outcome.TIE_INCONCLUSIVE
    assert result.all_wins_warning is False


def test_incomplete_pair_never_credited_to_synapse():
    # A failed consensus run for the scenario -> no completed consensus samples.
    failed_consensus = [
        ScenarioRun(arm="consensus", seed=0, kpis=None, failed=True, error="boom")
    ]
    runs_by_pair = {
        ("demand-spike", "consensus"): failed_consensus,
        ("demand-spike", "baseline"): _runs("baseline", _series(0.5)),
    }
    hr = _harness_result(runs_by_pair, (SCEN,), ("consensus", "baseline"))

    result = assemble_uplift_result(hr, CONTRACT, fidelity=FIDELITY)

    assert result.incomplete is True
    outcome = result.per_scenario[("demand-spike", "fill_rate")]
    assert outcome is Outcome.TIE_INCONCLUSIVE
    assert outcome is not Outcome.SYNAPSE_WINS


def test_every_executed_scenario_is_reported():
    scen2 = Scenario(name="supplier-default", seed=2, shock=ShockParams(lead_time_multiplier=2.0))
    runs_by_pair = {
        ("demand-spike", "consensus"): _runs("consensus", _series(0.9)),
        ("demand-spike", "baseline"): _runs("baseline", _series(0.5)),
        ("supplier-default", "consensus"): _runs("consensus", _series(0.4)),
        ("supplier-default", "baseline"): _runs("baseline", _series(0.8)),
    }
    hr = _harness_result(runs_by_pair, (SCEN, scen2), ("consensus", "baseline"))

    result = assemble_uplift_result(hr, CONTRACT, fidelity=FIDELITY)

    reported_scenarios = {scenario for scenario, _ in result.per_scenario}
    assert reported_scenarios == {"demand-spike", "supplier-default"}
    # baseline beats consensus on the second scenario -> not an all-wins grid
    assert result.per_scenario[("supplier-default", "fill_rate")] is Outcome.BASELINE_WINS
    assert result.all_wins_warning is False


def test_pooled_baseline_over_multiple_baseline_arms():
    runs_by_pair = {
        ("demand-spike", "consensus"): _runs("consensus", _series(0.9)),
        ("demand-spike", "par_level_reorder"): _runs("par_level_reorder", _series(0.5)),
        ("demand-spike", "static_pricing"): _runs("static_pricing", _series(0.55)),
    }
    hr = _harness_result(
        runs_by_pair,
        (SCEN,),
        ("consensus", "par_level_reorder", "static_pricing"),
    )

    result = assemble_uplift_result(hr, CONTRACT, fidelity=FIDELITY)

    # consensus (0.9) vs pooled baselines (~0.5/0.55) -> SYNAPSE wins
    assert result.per_scenario[("demand-spike", "fill_rate")] is Outcome.SYNAPSE_WINS


def test_exit_code_success_when_any_run_completed():
    runs_by_pair = {
        ("demand-spike", "consensus"): _runs("consensus", _series(0.9)),
        ("demand-spike", "baseline"): _runs("baseline", _series(0.5)),
    }
    hr = _harness_result(runs_by_pair, (SCEN,), ("consensus", "baseline"))

    assert completed_run_count(hr) == 80
    assert uplift_exit_code(hr) == EXIT_SUCCESS


def test_exit_code_failure_when_nothing_completed():
    only_failed = {
        ("demand-spike", "consensus"): [
            ScenarioRun(arm="consensus", seed=0, kpis=None, failed=True, error="x")
        ],
    }
    hr = _harness_result(only_failed, (SCEN,), ("consensus",))

    assert completed_run_count(hr) == 0
    assert uplift_exit_code(hr) == EXIT_NO_COMPLETED_RUN


def test_report_colocates_uplift_with_fidelity_context():
    runs_by_pair = {
        ("demand-spike", "consensus"): _runs("consensus", _series(0.9)),
        ("demand-spike", "baseline"): _runs("baseline", _series(0.5)),
    }
    hr = _harness_result(runs_by_pair, (SCEN,), ("consensus", "baseline"))
    result = assemble_uplift_result(hr, CONTRACT, fidelity=FIDELITY)

    report = build_uplift_report(result)
    assert report.primary_kpi == "fill_rate"
    assert report.kl_divergence == pytest.approx(0.02)
    assert report.threshold == pytest.approx(0.1)
    assert report.within_fidelity_bound is True
    assert report.confidence == "within_fidelity_bound"

    rendered = report.render()
    assert "headline uplift" in rendered
    assert "twin KL divergence" in rendered
    assert "bounded by twin fidelity" in rendered
    assert "within_fidelity_bound" in rendered


def test_report_marks_unavailable_fidelity():
    runs_by_pair = {
        ("demand-spike", "consensus"): _runs("consensus", _series(0.9)),
        ("demand-spike", "baseline"): _runs("baseline", _series(0.5)),
    }
    hr = _harness_result(runs_by_pair, (SCEN,), ("consensus", "baseline"))
    unavailable = FidelityReport(kl_divergence=None, threshold=0.1)
    result = assemble_uplift_result(hr, CONTRACT, fidelity=unavailable)

    report = build_uplift_report(result)
    assert report.within_fidelity_bound is None
    assert report.confidence == "unknown"
    assert "unavailable" in report.render()
