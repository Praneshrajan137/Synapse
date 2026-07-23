"""Property-based test that every executed scenario is reported without filtering.

Feature: decision-integrity-uplift-proof
Property 16: Every executed scenario is reported without filtering.

    *For any* distribution of scenario outcomes (some SYNAPSE_WINS, some BASELINE_WINS,
    some TIE / inconclusive), the set of scenarios reported in the assembled adversarial
    result equals the set of scenarios executed; no scenario is omitted or filtered on
    the basis of its outcome.

The scenario outcome distribution is engineered per Hypothesis example by drawing a
per-scenario *outcome intent* and choosing consensus/baseline sample values that force
that intent through :meth:`uplift.contract.MetricContract.classify`:

- WIN  -> consensus values clearly higher than baseline (higher-is-better KPI) so the
          effect is significant, exceeds the MDE, and favors the consensus arm.
- LOSS -> consensus values clearly lower than baseline so the effect favors baseline.
- TIE  -> identical consensus/baseline distributions so the comparison is inconclusive.

Regardless of how the intents are mixed across scenarios, the reported scenario set is
asserted to be exactly the executed scenario set.

Validates: Requirements 4.4
"""
from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from uplift.contract import MetricContract
from uplift.fidelity import FidelityReport
from uplift.harness import HarnessResult, aggregate_arm, assemble_uplift_result
from uplift.interfaces import Direction, KpiVector, Outcome, Scenario, ScenarioRun

from digital_twin.simulation.monte_carlo import ShockParams


_CONSENSUS_ARM = "consensus"
_BASELINE_ARM = "baseline"

# A single higher-is-better primary KPI is enough to exercise the full outcome space;
# the property is about the reported *scenario* set, not the KPI cross-product.
_PRIMARY_KPI = "fill_rate"

_CONTRACT = MetricContract(
    primary_kpis={_PRIMARY_KPI: Direction.HIGHER_IS_BETTER},
    effect_size="cohens_d+rel_pct",
    significance_test="mann_whitney_u",
    alpha=0.05,
    mde={_PRIMARY_KPI: 0.2},
    decision_rule="significant_and_favorable_and_meets_mde",
)

# A deterministic, available, within-bound fidelity report so assembly never depends on
# the live C34 gauge (fidelity context is irrelevant to Property 16).
_FIDELITY = FidelityReport(kl_divergence=0.02, threshold=0.1)

# High / low fill-rate levels far enough apart that the higher level always wins the
# significant-and-favorable-and-meets-MDE comparison against the lower level.
_HIGH = 0.9
_LOW = 0.5
_TIE = 0.6

# The three engineered outcome intents.
_WIN, _LOSS, _TIE_INTENT = "win", "loss", "tie"


def _kpi(fill_rate: float) -> KpiVector:
    """A KpiVector carrying ``fill_rate``; other fields are irrelevant here."""
    return KpiVector(
        fill_rate=fill_rate,
        spoilage_rate=0.0,
        stockout_rate=0.0,
        avg_delivery_time_min=1.0,
        margin=1.0,
        co2_estimate=1.0,
    )


def _series(base: float, n: int = 40) -> list[float]:
    """A small spread around ``base`` so the significance test is well-defined."""
    return [base + (i % 5) * 0.001 for i in range(n)]


def _runs(arm: str, fill_rates: list[float]) -> list[ScenarioRun]:
    return [
        ScenarioRun(arm=arm, seed=i, kpis=_kpi(fr), failed=False, error=None)
        for i, fr in enumerate(fill_rates)
    ]


def _levels_for_intent(intent: str) -> tuple[float, float]:
    """Return (consensus_base, baseline_base) engineered to force ``intent``."""
    if intent == _WIN:
        return _HIGH, _LOW
    if intent == _LOSS:
        return _LOW, _HIGH
    return _TIE, _TIE  # identical distributions -> tie / inconclusive


# Distinct scenario names crossed with a per-scenario engineered outcome intent. Drawing
# names + intents together guarantees a varied outcome distribution across examples.
_scenarios_with_intents = st.lists(
    st.tuples(
        st.text(alphabet="abcdefghijklmnopqrstuvwxyz-", min_size=1, max_size=12),
        st.sampled_from([_WIN, _LOSS, _TIE_INTENT]),
    ),
    min_size=1,
    max_size=6,
    unique_by=lambda pair: pair[0],
)


@settings(max_examples=200)
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
    expected_outcomes = {
        name: {
            _WIN: Outcome.SYNAPSE_WINS,
            _LOSS: Outcome.BASELINE_WINS,
            _TIE_INTENT: Outcome.TIE_INCONCLUSIVE,
        }[intent]
        for name, intent in scenarios_with_intents
    }
    for name, expected in expected_outcomes.items():
        assert result.per_scenario[(name, _PRIMARY_KPI)] is expected
