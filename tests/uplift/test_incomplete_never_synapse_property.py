"""Property-based test that incomplete pairs are never credited to SYNAPSE.

Feature: decision-integrity-uplift-proof
Property 19: Incomplete pairs are never credited to SYNAPSE.

    *For any* adversarial scenario that cannot complete for an arm (a failed run, no
    completed samples, or no run at all — for the consensus arm and/or the baseline
    arm), :func:`uplift.harness.assemble_uplift_result` records the failure by marking
    ``result.incomplete is True`` and the affected ``(scenario, primary KPI)`` pair is
    NEVER classified ``SYNAPSE_WINS``. Per the implementation an incomplete pair
    resolves to ``TIE_INCONCLUSIVE`` — it can never default to a SYNAPSE win even when
    the consensus arm carries strong-looking (but failed/absent) data.

    Requirement 4.7: "WHEN an adversarial scenario cannot complete for an arm THEN THE
    Uplift_Harness SHALL record a failed run for that arm, mark the result incomplete,
    and never default the affected (Scenario, primary KPI) pair to 'SYNAPSE wins'."

Carried to Metric_Contract v2 and the v2 harness (decision-quality-proof tasks 29.4, 15.5).
The primary KPI is the committed ``objective``, a cost, so "strong-looking" means CHEAP.
``incomplete`` is the contrast predicate and ``run_incomplete`` the whole-run one; both are
asserted. An ``oracle``-role arm is registered beside the contrast, adversarially cheaper than
consensus when it completes, and sometimes failed or absent: pooled, it would flip a complete
scenario to a loss, and counted, its failure would withhold the credit. Neither may happen.

Validates: Requirements 4.7
"""
from __future__ import annotations

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from digital_twin.simulation.monte_carlo import ShockParams
from uplift.contract import load_contract
from uplift.fidelity import FidelityReport
from uplift.harness import (
    NO_ESTIMATE_HEADLINE,
    HarnessResult,
    aggregate_arm,
    assemble_uplift_result,
)
from uplift.interfaces import ArmRole, KpiVector, Outcome, Scenario, ScenarioRun

# The real, version-controlled metric contract (v2): the sole primary KPI is the committed
# objective, judged by the four-valued interval rule against the materiality margin.
_CONTRACT = load_contract()
_PRIMARY_KPI = _CONTRACT.objective_kpi
_MARGIN = _CONTRACT.materiality_margin
_CONSENSUS_ARM = "consensus"
_BASELINE_ARM = "baseline"
_ORACLE_ARM = "oracle"

#: Every arm declares its role (AD-16): the oracle is registered, never pooled.
_ARM_ROLES: dict[str, ArmRole] = {
    _CONSENSUS_ARM: "consensus",
    _BASELINE_ARM: "baseline",
    _ORACLE_ARM: "oracle",
}

# Deterministic, available, within-bound fidelity so assembly never depends on the live
# C34 gauge (fidelity context is irrelevant to Property 19).
_FIDELITY = FidelityReport(kl_divergence=0.02, threshold=0.1)

# Per-arm replicate count, kept from the v1 fixture. Under v2 a complete pair's paired
# difference is the same on every replicate, so the interval is decided at any count; this
# is a fixture size, not a power claim.
_N = 30

# Objective levels (lower is better). A complete consensus arm is four margins cheaper than
# the baseline, so a complete scenario's interval lies wholly above the margin: SYNAPSE_WINS.
_CHEAP = 10.0
_DEAR = _CHEAP + 4.0 * _MARGIN
# What failed consensus runs carry: cheaper still, so they would dominate if trusted.
_TOO_GOOD = _CHEAP - 4.0 * _MARGIN
# A completing oracle: cheap enough that pooling it would turn a SYNAPSE win into a loss.
_ORACLE_COST = _CHEAP - 8.0 * _MARGIN

# The per-scenario modes we can construct with a KNOWN completeness state.
#   complete_win        -> both arms complete; consensus clearly cheaper -> SYNAPSE_WINS
#   consensus_failed    -> consensus runs are failed but carry STRONG-looking kpis;
#                          adversarially strong yet never creditable (no completed data)
#   consensus_empty     -> consensus has no runs at all for the scenario
#   baseline_failed     -> baseline runs failed; consensus completes strong
#   both_failed         -> neither arm can complete
_COMPLETE_MODES = ("complete_win",)
_INCOMPLETE_MODES = (
    "consensus_failed",
    "consensus_empty",
    "baseline_failed",
    "both_failed",
)
_ALL_MODES = _COMPLETE_MODES + _INCOMPLETE_MODES

# What the oracle arm does in a scenario: completes (cheapest), fails, or records nothing.
_ORACLE_MODES = ("cheapest", "failed", "empty")


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
    """A tight spread around ``base``, shared by every arm so paired differences are flat."""
    return [base + (i % 5) * 0.001 for i in range(n)]


def _completed_runs(arm: str, objectives: list[float]) -> list[ScenarioRun]:
    """Completed (non-failed) runs for ``arm`` from a list of objective samples."""
    return [
        ScenarioRun(arm=arm, seed=i, kpis=_kpi(objective), failed=False, error=None)
        for i, objective in enumerate(objectives)
    ]


def _failed_runs(arm: str, objectives: list[float]) -> list[ScenarioRun]:
    """Failed runs for ``arm``.

    They carry STRONG-looking (cheap) objectives on purpose — the adversarial case where
    the consensus arm *would* dominate if the numbers were trusted — but ``failed=True``
    means :meth:`HarnessResult.completed_runs` excludes them, so the pair has no
    completed samples and must never be credited to SYNAPSE.
    """
    return [
        ScenarioRun(arm=arm, seed=i, kpis=_kpi(objective), failed=True, error="injected failure")
        for i, objective in enumerate(objectives)
    ]


def _runs_for_mode(mode: str) -> dict[str, list[ScenarioRun]]:
    """Consensus + baseline run lists (by arm) realising ``mode``'s completeness state."""
    if mode == "complete_win":
        return {
            _CONSENSUS_ARM: _completed_runs(_CONSENSUS_ARM, _series(_CHEAP)),
            _BASELINE_ARM: _completed_runs(_BASELINE_ARM, _series(_DEAR)),
        }
    if mode == "consensus_failed":
        # Strong-looking but FAILED consensus data; baseline completes normally.
        return {
            _CONSENSUS_ARM: _failed_runs(_CONSENSUS_ARM, _series(_TOO_GOOD)),
            _BASELINE_ARM: _completed_runs(_BASELINE_ARM, _series(_DEAR)),
        }
    if mode == "consensus_empty":
        # No consensus runs recorded at all; baseline completes normally.
        return {
            _CONSENSUS_ARM: [],
            _BASELINE_ARM: _completed_runs(_BASELINE_ARM, _series(_DEAR)),
        }
    if mode == "baseline_failed":
        # Consensus completes strong; baseline could not complete.
        return {
            _CONSENSUS_ARM: _completed_runs(_CONSENSUS_ARM, _series(_CHEAP)),
            _BASELINE_ARM: _failed_runs(_BASELINE_ARM, _series(_DEAR)),
        }
    if mode == "both_failed":
        return {
            _CONSENSUS_ARM: _failed_runs(_CONSENSUS_ARM, _series(_TOO_GOOD)),
            _BASELINE_ARM: _failed_runs(_BASELINE_ARM, _series(_DEAR)),
        }
    raise ValueError(f"unknown mode {mode!r}")  # pragma: no cover


def _oracle_runs(oracle_mode: str) -> list[ScenarioRun]:
    """The oracle arm's runs for one scenario, outside the consensus contrast."""
    if oracle_mode == "cheapest":
        return _completed_runs(_ORACLE_ARM, _series(_ORACLE_COST))
    if oracle_mode == "failed":
        return _failed_runs(_ORACLE_ARM, _series(_ORACLE_COST))
    if oracle_mode == "empty":
        return []
    raise ValueError(f"unknown oracle mode {oracle_mode!r}")  # pragma: no cover


def _name(index: int, mode: str) -> str:
    return f"scenario-{index}-{mode}"


def _harness_result(grid: list[tuple[str, str]]) -> HarnessResult:
    """Build a multi-scenario HarnessResult from per-scenario ``(mode, oracle mode)`` pairs.

    Each mode becomes a distinct, uniquely named scenario whose consensus/baseline run
    lists realise that mode's KNOWN completeness state, beside the oracle's runs.
    """
    scenarios: list[Scenario] = []
    runs_by_pair: dict[tuple[str, str], list[ScenarioRun]] = {}
    for index, (mode, oracle_mode) in enumerate(grid):
        name = _name(index, mode)
        scenarios.append(
            Scenario(name=name, seed=index, shock=ShockParams(demand_multiplier=1.0))
        )
        for arm, runs in _runs_for_mode(mode).items():
            runs_by_pair[(name, arm)] = runs
        runs_by_pair[(name, _ORACLE_ARM)] = _oracle_runs(oracle_mode)

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
        arm_names=tuple(_ARM_ROLES),
        arm_roles=_ARM_ROLES,
    )


# A grid mixing arbitrary modes with AT LEAST ONE guaranteed-incomplete scenario, so the
# overall run must be marked incomplete while some scenarios may complete normally.
@st.composite
def _mixed_grids(draw: st.DrawFn) -> list[tuple[str, str]]:
    cells = st.tuples(st.sampled_from(_ALL_MODES), st.sampled_from(_ORACLE_MODES))
    others = draw(st.lists(cells, min_size=0, max_size=5))
    forced_incomplete = draw(
        st.tuples(st.sampled_from(_INCOMPLETE_MODES), st.sampled_from(_ORACLE_MODES))
    )
    insert_at = draw(st.integers(min_value=0, max_value=len(others)))
    grid = list(others)
    grid.insert(insert_at, forced_incomplete)
    return grid


@settings(deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(grid=_mixed_grids())
def test_incomplete_pairs_never_credited_to_synapse(grid: list[tuple[str, str]]) -> None:
    """Incomplete pairs resolve to TIE_INCONCLUSIVE (never SYNAPSE_WINS) and mark incomplete."""
    harness_result = _harness_result(grid)

    result = assemble_uplift_result(harness_result, _CONTRACT, fidelity=_FIDELITY)

    # The grid contains at least one incomplete scenario -> the contrast is incomplete, and
    # so is the whole run.
    assert result.incomplete is True
    assert result.run_incomplete is True
    # The oracle was registered and never pooled.
    assert result.comparator == f"pooled:{_BASELINE_ARM}"
    # Nor is anything credited through the HEADLINE (finding 96). The surviving replicates of
    # a partial scenario, pooled with the complete ones, used to estimate an interval, and the
    # complete scenarios here are four margins cheaper, so its verdict read `win` beside
    # `incomplete: true`. An incomplete contrast records no interval, no verdict and the
    # no-estimate sentinel.
    assert result.interval is None
    assert result.headline_verdict is None
    assert result.headline_uplift == NO_ESTIMATE_HEADLINE
    assert result.per_kpi[_PRIMARY_KPI] is Outcome.TIE_INCONCLUSIVE

    for index, (mode, _oracle_mode) in enumerate(grid):
        outcome = result.per_scenario[(_name(index, mode), _PRIMARY_KPI)]
        if mode in _INCOMPLETE_MODES:
            # The core guarantee (R4.7): an arm that could not complete is NEVER
            # credited to SYNAPSE, even with strong-looking failed/absent data.
            assert outcome is not Outcome.SYNAPSE_WINS, (
                f"incomplete scenario {_name(index, mode)} was wrongly credited to SYNAPSE"
            )
            # Per the implementation the affected pair resolves to TIE_INCONCLUSIVE.
            assert outcome is Outcome.TIE_INCONCLUSIVE, (
                f"incomplete scenario {_name(index, mode)} did not resolve to TIE_INCONCLUSIVE"
            )
        else:
            # A fully-completed, well-separated scenario still classifies normally, whatever
            # the oracle beside it did.
            assert outcome is Outcome.SYNAPSE_WINS


def test_failed_consensus_run_marks_incomplete_and_never_synapse() -> None:
    """A single strong-looking-but-failed consensus run cannot yield a SYNAPSE win."""
    result = assemble_uplift_result(
        _harness_result([("consensus_failed", "cheapest")]), _CONTRACT, fidelity=_FIDELITY
    )
    outcome = result.per_scenario[(_name(0, "consensus_failed"), _PRIMARY_KPI)]
    assert result.incomplete is True
    assert result.run_incomplete is True
    assert outcome is not Outcome.SYNAPSE_WINS
    assert outcome is Outcome.TIE_INCONCLUSIVE


def test_absent_consensus_runs_mark_incomplete_and_never_synapse() -> None:
    """No consensus runs at all -> incomplete and never a SYNAPSE win."""
    result = assemble_uplift_result(
        _harness_result([("consensus_empty", "cheapest")]), _CONTRACT, fidelity=_FIDELITY
    )
    outcome = result.per_scenario[(_name(0, "consensus_empty"), _PRIMARY_KPI)]
    assert result.incomplete is True
    assert result.run_incomplete is True
    assert outcome is not Outcome.SYNAPSE_WINS
    assert outcome is Outcome.TIE_INCONCLUSIVE


def test_mixed_complete_and_incomplete_only_flags_incomplete() -> None:
    """A completing scenario keeps its SYNAPSE win while the incomplete one never does."""
    result = assemble_uplift_result(
        _harness_result([("complete_win", "cheapest"), ("baseline_failed", "cheapest")]),
        _CONTRACT,
        fidelity=_FIDELITY,
    )
    assert result.incomplete is True
    assert (
        result.per_scenario[(_name(0, "complete_win"), _PRIMARY_KPI)]
        is Outcome.SYNAPSE_WINS
    )
    incomplete_outcome = result.per_scenario[(_name(1, "baseline_failed"), _PRIMARY_KPI)]
    assert incomplete_outcome is not Outcome.SYNAPSE_WINS
    assert incomplete_outcome is Outcome.TIE_INCONCLUSIVE


def test_a_failed_oracle_replicate_never_withholds_credit_from_a_complete_contrast() -> None:
    """Outside the contrast, a failure marks only the run incomplete (AD-16, task 15.5)."""
    result = assemble_uplift_result(
        _harness_result([("complete_win", "failed")]), _CONTRACT, fidelity=_FIDELITY
    )
    assert result.incomplete is False
    assert result.run_incomplete is True
    assert result.per_scenario[(_name(0, "complete_win"), _PRIMARY_KPI)] is Outcome.SYNAPSE_WINS
    assert result.headline_verdict == "win"
