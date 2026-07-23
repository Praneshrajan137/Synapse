"""Property-based test that reported KPIs partition into primary and secondary.

Feature: decision-integrity-uplift-proof
Property 14: Reported KPIs partition into primary and secondary.

    *For any* metric contract (varying which KpiVector fields are declared primary,
    with their improvement directions) and reported KPI set, every reported KPI that is
    not declared primary is labelled secondary, and no KPI is labelled both. The primary
    and secondary labels are disjoint (primary ∩ secondary = ∅) and together cover
    exactly the six ``KpiVector`` fields (primary ∪ secondary == all KPI fields).

Validates: Requirements 3.8
"""
from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from uplift.contract import MetricContract
from uplift.fidelity import FidelityReport
from uplift.harness import (
    KPI_FIELDS,
    HarnessResult,
    aggregate_arm,
    assemble_uplift_result,
)
from uplift.interfaces import Direction, KpiVector, Scenario, ScenarioRun

from digital_twin.simulation.monte_carlo import ShockParams


# A deterministic, available, within-bound fidelity report so assembly does not depend
# on the live C34 gauge (the fidelity context is irrelevant to Property 14).
_FIDELITY = FidelityReport(kl_divergence=0.02, threshold=0.1)

_SCENARIO = Scenario(name="demand-spike", seed=1, shock=ShockParams(demand_multiplier=2.0))
_CONSENSUS_ARM = "consensus"
_BASELINE_ARM = "baseline"

# The six KpiVector fields the contract may declare primary (KPI_FIELDS is the harness's
# canonical, declaration-order tuple of the same fields).
_ALL_KPIS = list(KPI_FIELDS)


def _kpi() -> KpiVector:
    """A fixed, finite KpiVector; the partition does not depend on KPI values."""
    return KpiVector(
        fill_rate=0.9,
        spoilage_rate=0.1,
        stockout_rate=0.1,
        avg_delivery_time_min=1.0,
        margin=1.0,
        co2_estimate=1.0,
    )


def _runs(arm: str, n: int = 4) -> list[ScenarioRun]:
    """A few completed (non-failed) runs for ``arm`` with a constant KpiVector."""
    return [
        ScenarioRun(arm=arm, seed=i, kpis=_kpi(), failed=False, error=None)
        for i in range(n)
    ]


def _harness_result() -> HarnessResult:
    """Hand-build a single-scenario, consensus-vs-baseline HarnessResult fixture."""
    runs_by_pair = {
        (_SCENARIO.name, _CONSENSUS_ARM): _runs(_CONSENSUS_ARM),
        (_SCENARIO.name, _BASELINE_ARM): _runs(_BASELINE_ARM),
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


# A non-empty subset of the six KpiVector fields, each paired with an improvement
# direction — exactly the shape of a valid ``primary_kpis`` mapping.
_primary_kpis = st.dictionaries(
    keys=st.sampled_from(_ALL_KPIS),
    values=st.sampled_from(list(Direction)),
    min_size=1,
    max_size=len(_ALL_KPIS),
)


def _contract(primary_kpis: dict[str, Direction]) -> MetricContract:
    """A valid MetricContract with the given primary KPIs (MDE declared for each)."""
    return MetricContract(
        primary_kpis=primary_kpis,
        effect_size="cohens_d+rel_pct",
        significance_test="mann_whitney_u",
        alpha=0.05,
        mde={kpi: 0.2 for kpi in primary_kpis},
        decision_rule="significant_and_favorable_and_meets_mde",
    )


@settings(max_examples=150)
@given(primary_kpis=_primary_kpis)
def test_reported_kpis_partition_into_primary_and_secondary(
    primary_kpis: dict[str, Direction],
) -> None:
    """Every non-primary reported KPI is secondary; primary/secondary partition the fields."""
    contract = _contract(primary_kpis)

    result = assemble_uplift_result(_harness_result(), contract, fidelity=_FIDELITY)

    primary = set(primary_kpis)
    secondary = set(result.secondary_kpis)

    # (a) every KPI labelled secondary is NOT a declared primary KPI.
    assert secondary.isdisjoint(primary)

    # (b) no KPI is labelled both primary and secondary (disjointness, restated as an
    # empty intersection over the reported KPI universe).
    assert primary & secondary == set()

    # (c) primary ∪ secondary covers exactly the six reported KpiVector fields — so
    # every reported non-primary KPI is labelled secondary (nothing is left unlabelled).
    assert primary | secondary == set(_ALL_KPIS)

    # secondary is precisely the complement of the primary KPIs over the KPI fields.
    assert secondary == set(_ALL_KPIS) - primary
