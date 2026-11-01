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

Carried to Metric_Contract v2 (decision-quality-proof task 29.4). The claim holds; the set of
primary KPIs it ranges over has one admissible value. Construction refuses every contract whose
primary KPIs are not exactly ``{objective: lower}`` (asserted over generated sets in
``test_result_kpi_partition_property.py``), so the contract here is the committed one and the
product has one KPI column, the objective. What still varies is the run -- the scenario names
and the objective samples, which move the verdict. The design's wording, one outcome
"determined by the contract's decision rule", is now asserted too: every value is ``classify``
of the seed-paired objectives. Budget inherited from the root ``conftest.py`` profile; no
``max_examples`` literal.

Validates: Requirements 4.3
"""
from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from uplift.contract import load_contract
from uplift.fidelity import FidelityReport
from uplift.harness import HarnessResult, aggregate_arm, assemble_uplift_result
from uplift.interfaces import KpiVector, Outcome, Scenario, ScenarioRun

from digital_twin.simulation.monte_carlo import ShockParams


# The real, version-controlled metric contract (v2): its primary KPIs are exactly
# ``{objective: lower}``, the only set construction admits.
_CONTRACT = load_contract()

_CONSENSUS_ARM = "consensus"
_BASELINE_ARM = "baseline"

# A deterministic, available, within-bound fidelity report so assembly never depends on
# the live C34 gauge (fidelity context is irrelevant to Property 15).
_FIDELITY = FidelityReport(kl_divergence=0.02, threshold=0.1)


def _kpi(value: float) -> KpiVector:
    """A KpiVector with every field set to ``value``; only ``objective`` is judged."""
    return KpiVector(
        fill_rate=value,
        spoilage_rate=value,
        stockout_rate=value,
        avg_delivery_time_min=value,
        margin=value,
        co2_estimate=value,
        avg_on_hand_units=value,
        objective=value,
    )


def _runs(arm: str, values: list[float]) -> list[ScenarioRun]:
    """Completed (non-failed) runs for ``arm``; replicate ``i`` runs at seed ``i``."""
    return [
        ScenarioRun(arm=arm, seed=i, kpis=_kpi(v), failed=False, error=None)
        for i, v in enumerate(values)
    ]


# Distinct scenario names.
_scenario_names = st.lists(
    st.text(alphabet="abcdefghijklmnopqrstuvwxyz-", min_size=1, max_size=12),
    min_size=1,
    max_size=6,
    unique=True,
)
# A couple of finite sample values per arm so a pair has completed samples on both sides.
_samples = st.lists(
    st.floats(allow_nan=False, allow_infinity=False, min_value=-100.0, max_value=100.0),
    min_size=2,
    max_size=6,
)


@given(
    scenario_names=_scenario_names,
    consensus_samples=_samples,
    baseline_samples=_samples,
)
def test_each_scenario_primary_kpi_pair_classified_exactly_once(
    scenario_names: list[str],
    consensus_samples: list[float],
    baseline_samples: list[float],
) -> None:
    """per_scenario keys == scenarios × primary KPIs, one Outcome per pair (R4.3)."""
    primary_kpis = _CONTRACT.primary_kpis

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
        arm_roles={_CONSENSUS_ARM: "consensus", _BASELINE_ARM: "baseline"},
    )

    result = assemble_uplift_result(harness_result, _CONTRACT, fidelity=_FIDELITY)

    # The full cartesian product of scenario names × primary KPI names.
    expected_keys = {(name, kpi) for name in scenario_names for kpi in primary_kpis}

    # Exactly one entry per pair: keys equal the product, and the count matches (dict
    # keys are unique by construction, so equal key sets + matching count == no dup/gap).
    assert set(result.per_scenario.keys()) == expected_keys
    assert len(result.per_scenario) == len(scenario_names) * len(primary_kpis)

    # Every classified value is a valid Outcome member.
    assert all(isinstance(outcome, Outcome) for outcome in result.per_scenario.values())

    # v2: the one KPI column is the objective, and every value is the contract rule's own
    # outcome on that scenario's seed-paired samples. Every scenario carries the same two
    # arrays, and replicate i runs at seed i in both arms, so the seeds both recorded are
    # the first min(len) of each and one expectation serves every scenario.
    assert {kpi for _, kpi in result.per_scenario} == {"objective"}
    paired = min(len(consensus_samples), len(baseline_samples))
    expected = _CONTRACT.classify(
        consensus_samples[:paired], baseline_samples[:paired], _CONTRACT.objective_kpi
    )
    assert all(outcome is expected for outcome in result.per_scenario.values())
