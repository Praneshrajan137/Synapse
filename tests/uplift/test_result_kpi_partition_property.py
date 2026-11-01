"""Property-based test that reported KPIs partition into primary and secondary.

Feature: decision-integrity-uplift-proof
Property 14: Reported KPIs partition into primary and secondary.

    *For any* metric contract (varying which KpiVector fields are declared primary,
    with their improvement directions) and reported KPI set, every reported KPI that is
    not declared primary is labelled secondary, and no KPI is labelled both. The primary
    and secondary labels are disjoint (primary ∩ secondary = ∅) and together cover
    exactly the six ``KpiVector`` fields (primary ∪ secondary == all KPI fields).

Carried to Metric_Contract v2 (decision-quality-proof task 29.4). The claim -- every non-primary
KPI is labelled secondary and none is labelled both -- is unchanged; two phrases in the statement
no longer describe anything that exists. ``KpiVector`` has EIGHT fields (task 29.4 appended
``avg_on_hand_units`` and ``objective``), read here from the dataclass rather than counted. And a
contract can no longer vary which fields are primary: construction refuses every primary set
except ``{objective: lower}`` (R7.19), so ``fill_rate``, v1's only primary KPI, is secondary. So:

1. the partition is asserted for every contract that CAN exist -- any admissible ``alpha`` and
   margin -- over runs whose verdicts vary, so no outcome can move a label; and
2. the varied primary sets the statement ranges over are asserted REFUSED at construction,
   which is why clause 1 has exactly one primary KPI to partition around.

Budget inherited from the root ``conftest.py`` profile; no ``max_examples`` literal.

Validates: Requirements 3.8
"""
from __future__ import annotations

import dataclasses

import pytest
from hypothesis import given
from hypothesis import strategies as st

from uplift.contract import MetricContractError, load_contract
from uplift.fidelity import FidelityReport
from uplift.harness import HarnessResult, aggregate_arm, assemble_uplift_result
from uplift.interfaces import Direction, KpiVector, Scenario, ScenarioRun

from digital_twin.simulation.monte_carlo import ShockParams


# The real, version-controlled metric contract (v2): the objective is its sole primary KPI.
_CONTRACT = load_contract()

# A deterministic, available, within-bound fidelity report so assembly does not depend
# on the live C34 gauge (the fidelity context is irrelevant to Property 14).
_FIDELITY = FidelityReport(kl_divergence=0.02, threshold=0.1)

_SCENARIO = Scenario(name="demand-spike", seed=1, shock=ShockParams(demand_multiplier=2.0))
_CONSENSUS_ARM = "consensus"
_BASELINE_ARM = "baseline"

# Every KpiVector field, read from the dataclass itself -- not from the harness's own
# ``KPI_FIELDS`` -- so the coverage clause is checked against an independent source.
_ALL_KPIS = [field.name for field in dataclasses.fields(KpiVector)]

# The one primary-KPI set construction admits.
_ADMISSIBLE_PRIMARY = {"objective": Direction.LOWER_IS_BETTER}

# Replicates per arm. Each arm's objective is constant, so the interval is a point.
_REPLICATES = 4


def _kpi(objective: float) -> KpiVector:
    """A fixed, finite KpiVector but for ``objective``, which moves only the verdict."""
    return KpiVector(
        fill_rate=0.9,
        spoilage_rate=0.1,
        stockout_rate=0.1,
        avg_delivery_time_min=1.0,
        margin=1.0,
        co2_estimate=1.0,
        avg_on_hand_units=1.0,
        objective=objective,
    )


def _runs(arm: str, objective: float) -> list[ScenarioRun]:
    """A few completed (non-failed) runs for ``arm`` with a constant KpiVector."""
    return [
        ScenarioRun(arm=arm, seed=i, kpis=_kpi(objective), failed=False, error=None)
        for i in range(_REPLICATES)
    ]


def _harness_result(consensus_cost: float, baseline_cost: float) -> HarnessResult:
    """Hand-build a single-scenario, consensus-vs-baseline HarnessResult fixture."""
    runs_by_pair = {
        (_SCENARIO.name, _CONSENSUS_ARM): _runs(_CONSENSUS_ARM, consensus_cost),
        (_SCENARIO.name, _BASELINE_ARM): _runs(_BASELINE_ARM, baseline_cost),
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


# Every contract that can exist: the committed one, re-declared at another confidence level
# and margin -- the only two rule inputs construction lets vary.
_alphas = st.sampled_from((0.05, 0.1, 0.2, 0.5))
_margins = st.floats(min_value=1e-6, max_value=100.0, allow_nan=False, allow_infinity=False)
# Objective levels that put the verdict anywhere relative to 0 and to the drawn margin.
_costs = st.floats(min_value=0.0, max_value=20.0, allow_nan=False, allow_infinity=False)


@given(alpha=_alphas, margin=_margins, consensus_cost=_costs, baseline_cost=_costs)
def test_reported_kpis_partition_into_primary_and_secondary(
    alpha: float, margin: float, consensus_cost: float, baseline_cost: float
) -> None:
    """Every non-primary reported KPI is secondary; primary/secondary partition the fields."""
    contract = dataclasses.replace(
        _CONTRACT, alpha=alpha, mde={_CONTRACT.objective_kpi: margin}
    )

    result = assemble_uplift_result(
        _harness_result(consensus_cost, baseline_cost), contract, fidelity=_FIDELITY
    )

    primary = set(contract.primary_kpis)
    secondary = set(result.secondary_kpis)

    # (a) every KPI labelled secondary is NOT a declared primary KPI.
    assert secondary.isdisjoint(primary)

    # (b) no KPI is labelled both primary and secondary (disjointness, restated as an
    # empty intersection over the reported KPI universe).
    assert primary & secondary == set()

    # (c) primary ∪ secondary covers exactly the reported KpiVector fields — so every
    # reported non-primary KPI is labelled secondary (nothing is left unlabelled).
    assert primary | secondary == set(_ALL_KPIS)

    # secondary is precisely the complement of the primary KPIs over the KPI fields.
    assert secondary == set(_ALL_KPIS) - primary

    # v2: the one primary KPI is the objective, so v1's primary KPI is now secondary
    # (R7.19); each secondary KPI is labelled once; and the per-KPI verdict is reported for
    # exactly the primary set.
    assert primary == {"objective"}
    assert "fill_rate" in secondary
    assert len(result.secondary_kpis) == len(secondary)
    assert set(result.per_kpi) == primary


# Any primary-KPI map the statement ranges over -- a non-empty subset of the fields, each with
# a direction -- with the admissible map drawn too, so both answers are exercised.
_primary_kpi_maps = st.one_of(
    st.just(_ADMISSIBLE_PRIMARY),
    st.dictionaries(
        keys=st.sampled_from(_ALL_KPIS),
        values=st.sampled_from(list(Direction)),
        min_size=1,
        max_size=len(_ALL_KPIS),
    ),
)


@given(primary_kpis=_primary_kpi_maps)
def test_a_contract_declaring_any_other_primary_kpi_set_is_refused(
    primary_kpis: dict[str, Direction],
) -> None:
    """Construction admits exactly ``{objective: lower}``; every other primary set is refused."""
    if primary_kpis == _ADMISSIBLE_PRIMARY:
        assert dataclasses.replace(_CONTRACT, primary_kpis=primary_kpis) == _CONTRACT
    else:
        with pytest.raises(MetricContractError, match="primary_kpis must be exactly"):
            dataclasses.replace(_CONTRACT, primary_kpis=primary_kpis)
