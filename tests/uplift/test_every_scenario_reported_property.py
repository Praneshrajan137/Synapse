"""Property-based test that every executed scenario is reported without filtering.

Feature: decision-integrity-uplift-proof
Property 16: Every executed scenario is reported without filtering.

    *For any* distribution of scenario outcomes (some SYNAPSE_WINS, some BASELINE_WINS,
    some TIE / inconclusive), the set of scenarios reported in the assembled adversarial
    result equals the set of scenarios executed; no scenario is omitted or filtered on
    the basis of its outcome.

Carried to Metric_Contract v2 (decision-quality-proof task 29.4). The committed contract is
loaded, so the judged KPI is the ``objective`` -- a cost, lower is better -- and each
scenario is classified by the four-valued interval rule against the committed materiality
margin ``m``. The outcome distribution is engineered per Hypothesis example by drawing a
per-scenario *outcome intent* and a paired objective difference (baseline minus consensus,
the same on every seed-paired replicate) that forces it through
:meth:`uplift.contract.MetricContract.classify`:

- WIN        -> the difference is ``4m``: the interval lies wholly above the margin.
- SUB_MARGIN -> the difference is ``m / 2``: above zero, not above the margin -- a tie.
- LOSS       -> the difference is ``-4m``: the interval lies wholly below zero.
- TIE        -> identical objectives, so the interval is ``[0, 0]`` and contains zero.

Regardless of how the intents are mixed across scenarios, the reported scenario set is
asserted to be exactly the executed scenario set.

Validates: Requirements 4.4
"""
from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from digital_twin.simulation.monte_carlo import ShockParams
from uplift.contract import load_contract
from uplift.fidelity import FidelityReport
from uplift.harness import HarnessResult, aggregate_arm, assemble_uplift_result
from uplift.interfaces import KpiVector, Outcome, Scenario, ScenarioRun

_CONSENSUS_ARM = "consensus"
_BASELINE_ARM = "baseline"

# The real, version-controlled metric contract (v2): one primary KPI, the objective, whose
# MDE is the committed materiality margin. One primary KPI is enough to exercise the full
# outcome space; the property is about the reported *scenario* set, not the KPI product.
_CONTRACT = load_contract()
_PRIMARY_KPI = _CONTRACT.objective_kpi
_MARGIN = _CONTRACT.materiality_margin

# A deterministic, available, within-bound fidelity report so assembly never depends on
# the live C34 gauge (fidelity context is irrelevant to Property 16).
_FIDELITY = FidelityReport(kl_divergence=0.02, threshold=0.1)

# The consensus arm's objective level; each intent prices the baseline relative to it.
_CONSENSUS_COST = 10.0

# The four engineered outcome intents.
_WIN, _SUB_MARGIN, _LOSS, _TIE_INTENT = "win", "sub_margin", "loss", "tie"

# Paired difference (baseline minus consensus) per intent, in units of the margin.
_DIFFERENCE_IN_MARGINS = {_WIN: 4.0, _SUB_MARGIN: 0.5, _LOSS: -4.0, _TIE_INTENT: 0.0}

# The outcome each intent must classify as. A sub-margin gain is not a material win.
_EXPECTED_OUTCOME = {
    _WIN: Outcome.SYNAPSE_WINS,
    _SUB_MARGIN: Outcome.TIE_INCONCLUSIVE,
    _LOSS: Outcome.BASELINE_WINS,
    _TIE_INTENT: Outcome.TIE_INCONCLUSIVE,
}


def _kpi(objective: float) -> KpiVector:
    """A KpiVector carrying ``objective``; the secondary fields are irrelevant here."""
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


def _series(base: float, n: int = 40) -> list[float]:
    """A small spread around ``base``; both arms share it, so paired differences are flat."""
    return [base + (i % 5) * 0.001 for i in range(n)]


def _runs(arm: str, objectives: list[float]) -> list[ScenarioRun]:
    return [
        ScenarioRun(arm=arm, seed=i, kpis=_kpi(objective), failed=False, error=None)
        for i, objective in enumerate(objectives)
    ]


def _levels_for_intent(intent: str) -> tuple[float, float]:
    """Return (consensus_base, baseline_base) objectives engineered to force ``intent``."""
    return _CONSENSUS_COST, _CONSENSUS_COST + _DIFFERENCE_IN_MARGINS[intent] * _MARGIN


# Distinct scenario names crossed with a per-scenario engineered outcome intent. Drawing
# names + intents together guarantees a varied outcome distribution across examples.
_scenarios_with_intents = st.lists(
    st.tuples(
        st.text(alphabet="abcdefghijklmnopqrstuvwxyz-", min_size=1, max_size=12),
        st.sampled_from([_WIN, _SUB_MARGIN, _LOSS, _TIE_INTENT]),
    ),
    min_size=1,
    max_size=6,
    unique_by=lambda pair: pair[0],
)


@given(scenarios_with_intents=_scenarios_with_intents)
def test_every_executed_scenario_is_reported(
    scenarios_with_intents: list[tuple[str, str]],
) -> None:
    """Reported scenario set == executed scenario set for any outcome mix (R4.4)."""
    executed_names = [name for name, _ in scenarios_with_intents]

    runs_by_pair: dict[tuple[str, str], list[ScenarioRun]] = {}
    for name, intent in scenarios_with_intents:
        consensus_base, baseline_base = _levels_for_intent(intent)
        runs_by_pair[(name, _CONSENSUS_ARM)] = _runs(
            _CONSENSUS_ARM, _series(consensus_base)
        )
        runs_by_pair[(name, _BASELINE_ARM)] = _runs(
            _BASELINE_ARM, _series(baseline_base)
        )

    scenarios = tuple(
        Scenario(name=name, seed=i, shock=ShockParams())
        for i, name in enumerate(executed_names)
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

    reported_names = {scenario_name for scenario_name, _ in result.per_scenario}

    # The core property: every executed scenario is reported, and no extra scenario is
    # invented — the reported set equals the executed set regardless of the outcome mix.
    assert reported_names == set(executed_names)

    # No scenario was filtered out on the basis of its outcome: the report carries one
    # (scenario, primary KPI) entry for every executed scenario (single primary KPI).
    assert len(result.per_scenario) == len(executed_names)

    # Sanity: the engineered intents actually span the outcome space, so this example
    # exercises a genuine distribution rather than a single uniform outcome.
    for name, intent in scenarios_with_intents:
        assert result.per_scenario[(name, _PRIMARY_KPI)] is _EXPECTED_OUTCOME[intent]
