"""Property-based test that every (scenario, primary KPI) pair is classified once.

Feature: decision-integrity-uplift-proof
Property 15: Every (scenario, primary KPI) pair is classified exactly once.

    *For any* adversarial run over multiple scenarios (distinct names) crossed with a
    non-empty set of primary KPIs, :func:`uplift.harness.assemble_uplift_result` builds
    ``result.per_scenario`` with **exactly one** entry per ``(scenario, primary KPI)``
    pair: its key set equals the full cartesian product of scenario names × primary KPI
    names (no missing pair, no duplicate, no extra), its size equals
    ``len(scenarios) * len(primary_kpis)``, and every value is a valid
    :class:`~uplift.interfaces.Outcome` member.

Validates: Requirements 4.3
"""
from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from uplift.contract import MetricContract
from uplift.fidelity import FidelityReport
from uplift.harness import HarnessResult, aggregate_arm, assemble_uplift_result
from uplift.interfaces import Direction, KpiVector, Outcome, Scenario, ScenarioRun

from digital_twin.simulation.monte_carlo import ShockParams


# The KPI names the contract may declare primary — exactly the KpiVector fields.
_KPI_NAMES = (
    "fill_rate",
    "spoilage_rate",
    "stockout_rate",
    "avg_delivery_time_min",
    "margin",
    "co2_estimate",
)

_CONSENSUS_ARM = "consensus"
_BASELINE_ARM = "baseline"

# A deterministic, available, within-bound fidelity report so assembly never depends on
# the live C34 gauge (fidelity context is irrelevant to Property 15).
_FIDELITY = FidelityReport(kl_divergence=0.02, threshold=0.1)


def _kpi(value: float) -> KpiVector:
    """A KpiVector with every field set to ``value`` (values are irrelevant here)."""
    return KpiVector(
        fill_rate=value,
        spoilage_rate=value,
        stockout_rate=value,
        avg_delivery_time_min=value,
        margin=value,
        co2_estimate=value,
    )


def _runs(arm: str, values: list[float]) -> list[ScenarioRun]:
    """Completed (non-failed) runs for ``arm`` from a list of sample values."""
    return [
        ScenarioRun(arm=arm, seed=i, kpis=_kpi(v), failed=False, error=None)
        for i, v in enumerate(values)
    ]


# Distinct scenario names, and a non-empty subset of primary KPIs each with a direction.
_scenario_names = st.lists(
    st.text(alphabet="abcdefghijklmnopqrstuvwxyz-", min_size=1, max_size=12),
    min_size=1,
    max_size=6,
    unique=True,
)
_primary_kpi_names = st.lists(
    st.sampled_from(_KPI_NAMES), min_size=1, max_size=len(_KPI_NAMES), unique=True
)
_directions = st.sampled_from(list(Direction))
# A couple of finite sample values per arm so a pair has completed samples on both sides.
_samples = st.lists(
    st.floats(allow_nan=False, allow_infinity=False, min_value=-100.0, max_value=100.0),
    min_size=2,
    max_size=6,
)


@settings(max_examples=150)
@given(
    scenario_names=_scenario_names,
    primary_kpi_names=_primary_kpi_names,
    directions=st.lists(_directions, min_size=len(_KPI_NAMES), max_size=len(_KPI_NAMES)),
    consensus_samples=_samples,
    baseline_samples=_samples,
)
def test_each_scenario_primary_kpi_pair_classified_exactly_once(
    scenario_names: list[str],
    primary_kpi_names: list[str],
    directions: list[Direction],
    consensus_samples: list[float],
    baseline_samples: list[float],
) -> None:
    """per_scenario keys == scenarios × primary KPIs, one Outcome per pair (R4.3)."""
    primary_kpis = {
        kpi: directions[i] for i, kpi in enumerate(primary_kpi_names)
    }
    contract = MetricContract(
        primary_kpis=primary_kpis,
        effect_size="cohens_d+rel_pct",
        significance_test="mann_whitney_u",
        alpha=0.05,
        mde={kpi: 0.2 for kpi in primary_kpis},
        decision_rule="significant_and_favorable_and_meets_mde",
    )

    # Build a consensus + baseline arm for every scenario (the adversarial run grid).
    runs_by_pair: dict[tuple[str, str], list[ScenarioRun]] = {}
    for name in scenario_names:
        runs_by_pair[(name, _CONSENSUS_ARM)] = _runs(_CONSENSUS_ARM, consensus_samples)
        runs_by_pair[(name, _BASELINE_ARM)] = _runs(_BASELINE_ARM, baseline_samples)
    scenarios = tuple(
        Scenario(name=name, seed=i, shock=ShockParams())
        for i, name in enumerate(scenario_names)
    )
    arm_results = {
        pair: aggregate_arm(pair[1], runs) for pair, runs in runs_by_pair.items()
    }
    all_runs = [run for runs in runs_by_pair.values() for run in runs]
    harness_result = HarnessResult(
        arm_results=arm_results,
        runs_by_pair=runs_by_pair,
        all_runs=all_runs,
        results_path=None,
        scenarios=scenarios,
        arm_names=(_CONSENSUS_ARM, _BASELINE_ARM),
    )

    result = assemble_uplift_result(harness_result, contract, fidelity=_FIDELITY)

    # The full cartesian product of scenario names × primary KPI names.
    expected_keys = {(name, kpi) for name in scenario_names for kpi in primary_kpis}

    # Exactly one entry per pair: keys equal the product, and the count matches (dict
    # keys are unique by construction, so equal key sets + matching count == no dup/gap).
    assert set(result.per_scenario.keys()) == expected_keys
    assert len(result.per_scenario) == len(scenario_names) * len(primary_kpis)

    # Every classified value is a valid Outcome member.
    assert all(isinstance(outcome, Outcome) for outcome in result.per_scenario.values())
