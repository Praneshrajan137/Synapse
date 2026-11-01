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

Carried to Metric_Contract v2 (decision-quality-proof task 29.4). The committed contract is
loaded, so each scenario is classified by the four-valued interval rule on the ``objective``
(a cost, lower is better) against the committed materiality margin ``m``. Each intent is
engineered as a flat paired difference, comparator minus consensus, on every seed-paired
replicate: ``win`` is ``+4m`` (the interval lies wholly above the margin), ``tie`` is ``0``
(identical objectives, so the interval is ``[0, 0]``), ``loss`` is ``-4m``. v2 adds a fourth
intent, ``sub_margin`` (``+m/2``): a gain that does not clear the margin is TIE_INCONCLUSIVE,
so a grid of material wins with one sub-margin gain in it must not warn. Budget inherited from
the root ``conftest.py`` profile; no ``max_examples`` literal.

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


# The real, version-controlled metric contract (v2): its single primary KPI is the committed
# ``objective`` (lower is better), judged by its 1 - alpha paired interval against the margin.
_CONTRACT = load_contract()
_PRIMARY_KPI = _CONTRACT.objective_kpi
_MARGIN = _CONTRACT.materiality_margin
_CONSENSUS_ARM = "consensus"
_BASELINE_ARM = "baseline"

# A deterministic, available, within-bound fidelity report so assembly never depends on
# the live C34 gauge (fidelity context is irrelevant to Property 17).
_FIDELITY = FidelityReport(kl_divergence=0.02, threshold=0.1)

# Per-arm replicate count. Both arms share ``_series``'s spread, so every paired difference
# is the intent's difference and the interval is a point there: the verdict does not depend on
# how many replicates there are. v1's 30 was what a rank test needed for significance; every
# v2 replicate costs a share of the committed bootstrap's resamples instead.
_N = 8

# The four per-scenario intents we can construct with a KNOWN classified outcome.
_INTENTS = ("win", "sub_margin", "tie", "loss")

# Map each intent to the outcome the contract MUST assign, given the flat paired
# differences built by ``_series_for`` below.
_INTENT_OUTCOME = {
    "win": Outcome.SYNAPSE_WINS,  # consensus four margins cheaper: the interval clears m
    "sub_margin": Outcome.TIE_INCONCLUSIVE,  # half a margin cheaper: not a material win
    "tie": Outcome.TIE_INCONCLUSIVE,  # identical objectives: the interval contains 0
    "loss": Outcome.BASELINE_WINS,  # consensus four margins dearer: wholly below 0
}

# The consensus objective level; each intent prices the baseline relative to it.
_CONSENSUS_COST = 10.0

# Paired difference (baseline minus consensus) per intent, in units of the margin.
_DIFFERENCE_IN_MARGINS = {"win": 4.0, "sub_margin": 0.5, "tie": 0.0, "loss": -4.0}


def _kpi(objective: float) -> KpiVector:
    """A KpiVector varying only ``objective``; other fields are fixed constants."""
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


def _series(base: float, n: int = _N) -> list[float]:
    """A tight spread around ``base``, shared by both arms so the paired differences are flat."""
    return [base + (i % 5) * 0.001 for i in range(n)]


def _runs(arm: str, objectives: list[float]) -> list[ScenarioRun]:
    """Completed (non-failed) runs for ``arm``; replicate ``i`` runs at seed ``i``."""
    return [
        ScenarioRun(arm=arm, seed=i, kpis=_kpi(value), failed=False, error=None)
        for i, value in enumerate(objectives)
    ]


def _series_for(intent: str) -> tuple[list[float], list[float]]:
    """Consensus + baseline objectives yielding the intent's KNOWN outcome.

    Consensus costs ``_CONSENSUS_COST``; the baseline costs that plus the intent's
    difference in margins, so on every seed-paired replicate:
      - "win"        -> +4m: the interval lies wholly above the margin -> SYNAPSE_WINS
      - "sub_margin" -> +m/2: above zero, not above the margin       -> TIE_INCONCLUSIVE
      - "tie"        -> 0: identical objectives, interval [0, 0]      -> TIE_INCONCLUSIVE
      - "loss"       -> -4m: the interval lies wholly below zero      -> BASELINE_WINS
    """
    baseline_cost = _CONSENSUS_COST + _DIFFERENCE_IN_MARGINS[intent] * _MARGIN
    return _series(_CONSENSUS_COST), _series(baseline_cost)


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
        consensus_objectives, baseline_objectives = _series_for(intent)
        runs_by_pair[(name, _CONSENSUS_ARM)] = _runs(_CONSENSUS_ARM, consensus_objectives)
        runs_by_pair[(name, _BASELINE_ARM)] = _runs(_BASELINE_ARM, baseline_objectives)

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
        arm_roles={_CONSENSUS_ARM: "consensus", _BASELINE_ARM: "baseline"},
    )


# A non-empty grid of per-scenario intents. Mixed grids (with at least one sub-margin gain,
# tie or loss) must NOT warn; all-"win" grids MUST warn — the biconditional Property 17.
_intent_grids = st.lists(st.sampled_from(_INTENTS), min_size=1, max_size=6)


@settings(deadline=None, suppress_health_check=[HealthCheck.too_slow])
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


def test_all_wins_warning_false_when_one_gain_falls_short_of_the_margin() -> None:
    """A gain that does not clear the margin is not a win, so it suppresses the warning."""
    result = assemble_uplift_result(
        _harness_result(["win", "sub_margin", "win"]), _CONTRACT, fidelity=_FIDELITY
    )
    assert result.per_scenario[("scenario-1-sub_margin", _PRIMARY_KPI)] is (
        Outcome.TIE_INCONCLUSIVE
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
        arm_roles={_CONSENSUS_ARM: "consensus", _BASELINE_ARM: "baseline"},
    )
    result = assemble_uplift_result(empty, _CONTRACT, fidelity=_FIDELITY)
    assert result.per_scenario == {}
    assert result.all_wins_warning is False
