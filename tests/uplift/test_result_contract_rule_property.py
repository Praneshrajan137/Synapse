"""Property-based test that result assembly applies the metric contract rule verbatim.

Feature: decision-integrity-uplift-proof
Property 13: The harness applies the contract rule exactly as declared.

    *For any* aggregated per-arm inputs (a consensus arm's KPI sample set and a
    baseline arm's KPI sample set for a single scenario), the outcome the harness
    reports for that ``(scenario, primary KPI)`` pair — ``result.per_scenario`` — and
    the pooled per-KPI verdict — ``result.per_kpi`` — are *exactly* the outcome
    ``MetricContract.classify`` returns for the same pooled inputs. The harness adds no
    adjudication logic of its own; it re-uses the pre-registered contract rule verbatim.

Validates: Requirements 3.7

Carried to Metric_Contract v2 (decision-quality-proof task 29.4). The KPI is the committed
``objective``, and "the same pooled inputs" are the same SEED-PAIRED inputs: the harness pairs
replicate ``i`` of each arm on its seed, so two arms that recorded different replicate counts
are compared over the seeds both recorded -- never by list position. The rule's v2 products
are pinned beside the outcome: the reported interval IS ``MetricContract.interval`` on those
inputs, the headline verdict IS ``MetricContract.verdict`` of it, and the headline IS its point.
Budget inherited from the root ``conftest.py`` profile; no ``max_examples`` literal.

The same behavior is pinned, over a wider input space (pooled multi-arm baselines,
multi-scenario grids, mixed failed replicates, and mutated contract variants), by
``test_verbatim_contract_classification_property.py`` — core-purpose-uplift Property 9,
Requirements 2.7.

Timing note: the assertions here are exact-equality checks on a deterministic function,
so this test can only fail on a real classification mismatch. ``deadline=None`` and the
suppressed ``too_slow`` health check remove the only observed source of intermittent
failure — Hypothesis' wall-clock timing guards firing on a transient stall (a slow
example is recorded in ``.hypothesis`` and can then replay as a flake), which says
nothing about the property.
"""
from __future__ import annotations

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from uplift.contract import load_contract
from uplift.harness import HarnessResult, aggregate_arm, assemble_uplift_result
from uplift.fidelity import FidelityReport
from uplift.interfaces import KpiVector, Scenario, ScenarioRun

from digital_twin.simulation.monte_carlo import ShockParams


# The real, version-controlled metric contract (v2); its sole primary KPI is ``objective``.
_CONTRACT = load_contract()
_PRIMARY_KPI = _CONTRACT.objective_kpi

# A deterministic, available, within-bound fidelity report so assembly does not depend
# on the live C34 gauge (the fidelity context is irrelevant to Property 13).
_FIDELITY = FidelityReport(kl_divergence=0.02, threshold=0.1)

_SCENARIO = Scenario(name="demand-spike", seed=1, shock=ShockParams(demand_multiplier=2.0))
_CONSENSUS_ARM = "consensus"
_BASELINE_ARM = "baseline"


def _kpi(objective: float) -> KpiVector:
    """A KpiVector varying only ``objective``; the secondary fields are fixed constants."""
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
    """Completed (non-failed) runs for ``arm``; replicate ``i`` runs at seed ``i``."""
    return [
        ScenarioRun(arm=arm, seed=i, kpis=_kpi(value), failed=False, error=None)
        for i, value in enumerate(objectives)
    ]


def _harness_result(
    consensus_objectives: list[float], baseline_objectives: list[float]
) -> HarnessResult:
    """Hand-build a single-scenario, consensus-vs-baseline HarnessResult fixture."""
    runs_by_pair = {
        (_SCENARIO.name, _CONSENSUS_ARM): _runs(_CONSENSUS_ARM, consensus_objectives),
        (_SCENARIO.name, _BASELINE_ARM): _runs(_BASELINE_ARM, baseline_objectives),
    }
    arm_results = {
        pair: aggregate_arm(pair[1], runs) for pair, runs in runs_by_pair.items()
    }
    all_runs = [run for runs in runs_by_pair.values() for run in runs]
    return HarnessResult(
        arm_results=arm_results,
        runs_by_pair=runs_by_pair,
        all_runs=all_runs,
        results_path=None,
        scenarios=(_SCENARIO,),
        arm_names=(_CONSENSUS_ARM, _BASELINE_ARM),
        arm_roles={_CONSENSUS_ARM: "consensus", _BASELINE_ARM: "baseline"},
    )


# Finite objective samples over a spread wide enough to produce every verdict. Both arms
# have >= 2 completed samples so the pair is never forced to TIE by the incomplete guard.
_objectives = st.lists(
    st.floats(allow_nan=False, allow_infinity=False, min_value=-1_000.0, max_value=1_000.0),
    min_size=2,
    max_size=30,
)


@settings(deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(consensus_objectives=_objectives, baseline_objectives=_objectives)
def test_harness_applies_contract_rule_exactly(
    consensus_objectives: list[float], baseline_objectives: list[float]
) -> None:
    """result.per_scenario / per_kpi equal contract.classify on the same seed-paired inputs."""
    harness_result = _harness_result(consensus_objectives, baseline_objectives)

    result = assemble_uplift_result(harness_result, _CONTRACT, fidelity=_FIDELITY)

    # The same inputs the harness pairs, built here from the drawn values rather than read
    # through a harness helper: replicate i of each arm ran at seed i, so the seeds both arms
    # recorded are the first min(len) of each, in seed order.
    paired = min(len(consensus_objectives), len(baseline_objectives))
    consensus = consensus_objectives[:paired]
    baseline = baseline_objectives[:paired]

    # The independent, ground-truth verdict from the contract rule on the SAME inputs.
    expected = _CONTRACT.classify(consensus, baseline, _PRIMARY_KPI)

    # The harness re-uses the contract rule verbatim — no logic of its own — so both the
    # per-scenario outcome and the pooled per-KPI verdict match the contract exactly.
    assert result.per_scenario[(_SCENARIO.name, _PRIMARY_KPI)] == expected
    assert result.per_kpi[_PRIMARY_KPI] == expected

    # ... and so are the v2 products the verdict is read from: the contract's own interval
    # on those inputs, its verdict, and its point as the headline.
    interval = _CONTRACT.interval(consensus, baseline)
    assert result.interval == interval
    assert result.headline_verdict == _CONTRACT.verdict(interval)
    assert result.headline_uplift == interval.point
