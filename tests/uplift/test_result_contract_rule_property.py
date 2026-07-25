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


# The real, version-controlled metric contract; its primary KPI is ``fill_rate``.
_CONTRACT = load_contract()
_PRIMARY_KPI = "fill_rate"

# A deterministic, available, within-bound fidelity report so assembly does not depend
# on the live C34 gauge (the fidelity context is irrelevant to Property 13).
_FIDELITY = FidelityReport(kl_divergence=0.02, threshold=0.1)

_SCENARIO = Scenario(name="demand-spike", seed=1, shock=ShockParams(demand_multiplier=2.0))
_CONSENSUS_ARM = "consensus"
_BASELINE_ARM = "baseline"


def _kpi(fill_rate: float) -> KpiVector:
    """A KpiVector varying only ``fill_rate``; other fields are fixed constants."""
    return KpiVector(
        fill_rate=fill_rate,
        spoilage_rate=0.0,
        stockout_rate=0.0,
        avg_delivery_time_min=1.0,
        margin=1.0,
        co2_estimate=1.0,
    )


def _runs(arm: str, fill_rates: list[float]) -> list[ScenarioRun]:
    """Completed (non-failed) runs for ``arm`` from a list of fill_rate samples."""
    return [
        ScenarioRun(arm=arm, seed=i, kpis=_kpi(fr), failed=False, error=None)
        for i, fr in enumerate(fill_rates)
    ]


def _harness_result(
    consensus_fill_rates: list[float], baseline_fill_rates: list[float]
) -> HarnessResult:
    """Hand-build a single-scenario, consensus-vs-baseline HarnessResult fixture."""
    runs_by_pair = {
        (_SCENARIO.name, _CONSENSUS_ARM): _runs(_CONSENSUS_ARM, consensus_fill_rates),
        (_SCENARIO.name, _BASELINE_ARM): _runs(_BASELINE_ARM, baseline_fill_rates),
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
    )


# Finite fill_rate samples over a spread wide enough to produce SYNAPSE_WINS,
# BASELINE_WINS, and TIE_INCONCLUSIVE outcomes across the search space. Both arms have
# >= 2 completed samples so the pair is never forced to TIE by the incomplete guard.
_fill_rates = st.lists(
    st.floats(allow_nan=False, allow_infinity=False, min_value=-1_000.0, max_value=1_000.0),
    min_size=2,
    max_size=30,
)


@settings(max_examples=150, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(consensus_fill_rates=_fill_rates, baseline_fill_rates=_fill_rates)
def test_harness_applies_contract_rule_exactly(
    consensus_fill_rates: list[float], baseline_fill_rates: list[float]
) -> None:
    """result.per_scenario / per_kpi equal contract.classify on the same pooled inputs."""
    harness_result = _harness_result(consensus_fill_rates, baseline_fill_rates)

    result = assemble_uplift_result(harness_result, _CONTRACT, fidelity=_FIDELITY)

    # The independent, ground-truth verdict from the contract rule on the SAME inputs
    # the harness pools for this single-scenario / single-baseline configuration.
    expected = _CONTRACT.classify(
        consensus_fill_rates, baseline_fill_rates, _PRIMARY_KPI
    )

    # The harness re-uses the contract rule verbatim — no logic of its own — so both the
    # per-scenario outcome and the pooled per-KPI verdict match the contract exactly.
    assert result.per_scenario[(_SCENARIO.name, _PRIMARY_KPI)] == expected
    assert result.per_kpi[_PRIMARY_KPI] == expected
