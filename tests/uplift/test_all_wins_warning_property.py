"""Property-based test for the all-wins self-scrutiny warning.

Feature: decision-integrity-uplift-proof
Property 17: All-wins triggers the self-scrutiny warning.

    *For any* adversarial outcome grid, the harness emits the self-scrutiny warning
    (``result.all_wins_warning is True``) **if and only if** every ``(scenario, primary
    KPI)`` pair is classified ``SYNAPSE_WINS`` (and the grid is non-empty). If even one
    pair is a baseline win or a tie/inconclusive, the warning is not emitted.

    Requirement 4.5: "IF every (Scenario, primary KPI) pair is classified 'SYNAPSE
    wins' with no baseline win or tie, THEN THE Uplift_Harness SHALL emit ... a warning
    that the absence of any baseline win or tie is itself a signal to scrutinize the
    harness."

Validates: Requirements 4.5
"""
from __future__ import annotations

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from uplift.contract import load_contract
from uplift.fidelity import FidelityReport
from uplift.harness import HarnessResult, aggregate_arm, assemble_uplift_result
from uplift.interfaces import KpiVector, Outcome, Scenario, ScenarioRun

from digital_twin.simulation.monte_carlo import ShockParams


# The real, version-controlled metric contract; its single primary KPI is ``fill_rate``
# (higher-is-better, Cohen's d MDE 0.2, Mann-Whitney U at alpha 0.05).
_CONTRACT = load_contract()
_PRIMARY_KPI = "fill_rate"
_CONSENSUS_ARM = "consensus"
_BASELINE_ARM = "baseline"

# A deterministic, available, within-bound fidelity report so assembly never depends on
# the live C34 gauge (fidelity context is irrelevant to Property 17).
_FIDELITY = FidelityReport(kl_divergence=0.02, threshold=0.1)

# Per-arm replicate count: large enough that a well-separated pair of arms is
# Mann-Whitney significant with |Cohen's d| >> 0.2 MDE, so the intended outcome of each
# scenario ("win" / "tie" / "loss") is realised deterministically by the contract rule.
_N = 30

# The three per-scenario intents we can construct with a KNOWN classified outcome.
_INTENTS = ("win", "tie", "loss")

# Map each intent to the outcome the contract MUST assign, given the well-separated
# fill_rate distributions built by ``_series_for`` below.
_INTENT_OUTCOME = {
    "win": Outcome.SYNAPSE_WINS,   # consensus clearly higher on a higher-is-better KPI
    "tie": Outcome.TIE_INCONCLUSIVE,  # identical distributions -> not significant
    "loss": Outcome.BASELINE_WINS,  # baseline clearly higher
}


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


def _series(base: float, n: int = _N) -> list[float]:
    """A tight spread around ``base`` (small within-arm variance) so a 0.4 mean gap is
    strongly significant while a zero mean gap is a genuine tie."""
    return [base + (i % 5) * 0.001 for i in range(n)]


def _runs(arm: str, fill_rates: list[float]) -> list[ScenarioRun]:
    """Completed (non-failed) runs for ``arm`` from a list of fill_rate samples."""
    return [
        ScenarioRun(arm=arm, seed=i, kpis=_kpi(fr), failed=False, error=None)
        for i, fr in enumerate(fill_rates)
    ]


def _series_for(intent: str) -> tuple[list[float], list[float]]:
    """Consensus + baseline fill_rate samples yielding the intent's KNOWN outcome.

    Well-separated arms (means ~0.9 vs ~0.5, tight within-arm variance, n=30) make the
    Mann-Whitney test significant and |Cohen's d| far above the 0.2 MDE, so:
      - "win"  -> consensus 0.9 vs baseline 0.5 -> SYNAPSE_WINS
      - "tie"  -> both 0.6                       -> TIE_INCONCLUSIVE (no significance)
      - "loss" -> consensus 0.5 vs baseline 0.9  -> BASELINE_WINS
    """
    if intent == "win":
        return _series(0.9), _series(0.5)
    if intent == "loss":
        return _series(0.5), _series(0.9)
    # tie: identical distributions -> zero effect -> inconclusive
    return _series(0.6), _series(0.6)


def _harness_result(intents: list[str]) -> HarnessResult:
    """Build a multi-scenario consensus-vs-baseline HarnessResult from per-scenario intents.

    Each intent becomes a distinct, uniquely named scenario with a consensus arm and a
    baseline arm whose completed samples realise that intent's KNOWN classified outcome.
    """
    scenarios: list[Scenario] = []
    runs_by_pair: dict[tuple[str, str], list[ScenarioRun]] = {}
    for index, intent in enumerate(intents):
        name = f"scenario-{index}-{intent}"
        scenarios.append(
            Scenario(name=name, seed=index, shock=ShockParams(demand_multiplier=1.0))
        )
        consensus_fr, baseline_fr = _series_for(intent)
        runs_by_pair[(name, _CONSENSUS_ARM)] = _runs(_CONSENSUS_ARM, consensus_fr)
        runs_by_pair[(name, _BASELINE_ARM)] = _runs(_BASELINE_ARM, baseline_fr)

    arm_results = {
        pair: aggregate_arm(pair[1], runs) for pair, runs in runs_by_pair.items()
    }
    all_runs = [run for runs in runs_by_pair.values() for run in runs]
    return HarnessResult(
        arm_results=arm_results,
        runs_by_pair=runs_by_pair,
        all_runs=all_runs,
        results_path=None,
        scenarios=tuple(scenarios),
        arm_names=(_CONSENSUS_ARM, _BASELINE_ARM),
    )


# A non-empty grid of per-scenario intents. Mixed grids (with at least one tie/loss)
# must NOT warn; all-"win" grids MUST warn — the biconditional Property 17.
_intent_grids = st.lists(st.sampled_from(_INTENTS), min_size=1, max_size=6)


@settings(max_examples=120, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(intents=_intent_grids)
def test_all_wins_warning_iff_every_pair_is_synapse_wins(intents: list[str]) -> None:
    """result.all_wins_warning is True IFF every (scenario, primary KPI) pair is a win."""
    harness_result = _harness_result(intents)

    result = assemble_uplift_result(harness_result, _CONTRACT, fidelity=_FIDELITY)

    # Ground-truth: every constructed scenario classified to exactly its intended
    # outcome (independent of the warning logic under test).
    for index, intent in enumerate(intents):
        name = f"scenario-{index}-{intent}"
        assert (
            result.per_scenario[(name, _PRIMARY_KPI)] is _INTENT_OUTCOME[intent]
        ), f"scenario {name} classified unexpectedly"

    # The property under test, computed two independent ways:
    #  (a) from the assembled outcome grid itself (non-empty and all SYNAPSE_WINS), and
    #  (b) from the intents (all "win"), since intents are non-empty (min_size=1).
    expected_from_grid = bool(result.per_scenario) and all(
        outcome is Outcome.SYNAPSE_WINS for outcome in result.per_scenario.values()
    )
    expected_from_intents = all(intent == "win" for intent in intents)

    assert expected_from_grid == expected_from_intents
    # Property 17 biconditional: the warning fires IFF the grid is all-wins.
    assert result.all_wins_warning is expected_from_grid
    assert result.all_wins_warning is expected_from_intents


def test_all_wins_warning_true_for_a_pure_all_wins_grid() -> None:
    """A grid where every scenario is a SYNAPSE win emits the self-scrutiny warning."""
    result = assemble_uplift_result(
        _harness_result(["win", "win", "win"]), _CONTRACT, fidelity=_FIDELITY
    )
    assert all(o is Outcome.SYNAPSE_WINS for o in result.per_scenario.values())
    assert result.all_wins_warning is True


def test_all_wins_warning_false_when_one_tie_present() -> None:
    """A single tie among wins suppresses the warning (there IS a non-win pair)."""
    result = assemble_uplift_result(
        _harness_result(["win", "tie", "win"]), _CONTRACT, fidelity=_FIDELITY
    )
    assert result.all_wins_warning is False


def test_all_wins_warning_false_when_one_loss_present() -> None:
    """A single baseline win among wins suppresses the warning."""
    result = assemble_uplift_result(
        _harness_result(["win", "win", "loss"]), _CONTRACT, fidelity=_FIDELITY
    )
    assert result.all_wins_warning is False


def test_empty_grid_never_warns() -> None:
    """An empty outcome grid (no scenarios) never emits the warning (R4.5 non-empty)."""
    empty = HarnessResult(
        arm_results={},
        runs_by_pair={},
        all_runs=[],
        results_path=None,
        scenarios=(),
        arm_names=(_CONSENSUS_ARM, _BASELINE_ARM),
    )
    result = assemble_uplift_result(empty, _CONTRACT, fidelity=_FIDELITY)
    assert result.per_scenario == {}
    assert result.all_wins_warning is False
