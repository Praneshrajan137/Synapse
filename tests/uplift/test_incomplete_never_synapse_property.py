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

Validates: Requirements 4.7
"""
from __future__ import annotations

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from uplift.contract import load_contract
from uplift.fidelity import FidelityReport
from uplift.harness import HarnessResult, aggregate_arm, assemble_uplift_result
from uplift.interfaces import KpiVector, Outcome, Scenario, ScenarioRun

from digital_twin.simulation.monte_carlo import ShockParams


# The real, version-controlled metric contract; single primary KPI ``fill_rate``
# (higher-is-better, Cohen's d MDE 0.2, Mann-Whitney U at alpha 0.05).
_CONTRACT = load_contract()
_PRIMARY_KPI = "fill_rate"
_CONSENSUS_ARM = "consensus"
_BASELINE_ARM = "baseline"

# Deterministic, available, within-bound fidelity so assembly never depends on the live
# C34 gauge (fidelity context is irrelevant to Property 19).
_FIDELITY = FidelityReport(kl_divergence=0.02, threshold=0.1)

# Per-arm replicate count large enough that a well-separated pair of arms is
# Mann-Whitney significant with |Cohen's d| >> the 0.2 MDE, so a *complete* scenario
# realises SYNAPSE_WINS deterministically.
_N = 30

# The per-scenario modes we can construct with a KNOWN completeness state.
#   complete_win        -> both arms complete; consensus clearly higher -> SYNAPSE_WINS
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
    """A tight spread around ``base`` so a 0.4 mean gap is strongly significant."""
    return [base + (i % 5) * 0.001 for i in range(n)]


def _completed_runs(arm: str, fill_rates: list[float]) -> list[ScenarioRun]:
    """Completed (non-failed) runs for ``arm`` from a list of fill_rate samples."""
    return [
        ScenarioRun(arm=arm, seed=i, kpis=_kpi(fr), failed=False, error=None)
        for i, fr in enumerate(fill_rates)
    ]


def _failed_runs(arm: str, fill_rates: list[float]) -> list[ScenarioRun]:
    """Failed runs for ``arm``.

    They carry STRONG-looking fill_rate values on purpose — the adversarial case where
    the consensus arm *would* dominate if the numbers were trusted — but ``failed=True``
    means :meth:`HarnessResult.completed_runs` excludes them, so the pair has no
    completed samples and must never be credited to SYNAPSE.
    """
    return [
        ScenarioRun(arm=arm, seed=i, kpis=_kpi(fr), failed=True, error="injected failure")
        for i, fr in enumerate(fill_rates)
    ]


def _runs_for_mode(mode: str) -> dict[str, list[ScenarioRun]]:
    """Consensus + baseline run lists (by arm) realising ``mode``'s completeness state."""
    if mode == "complete_win":
        return {
            _CONSENSUS_ARM: _completed_runs(_CONSENSUS_ARM, _series(0.9)),
            _BASELINE_ARM: _completed_runs(_BASELINE_ARM, _series(0.5)),
        }
    if mode == "consensus_failed":
        # Strong-looking but FAILED consensus data; baseline completes normally.
        return {
            _CONSENSUS_ARM: _failed_runs(_CONSENSUS_ARM, _series(0.99)),
            _BASELINE_ARM: _completed_runs(_BASELINE_ARM, _series(0.5)),
        }
    if mode == "consensus_empty":
        # No consensus runs recorded at all; baseline completes normally.
        return {
            _CONSENSUS_ARM: [],
            _BASELINE_ARM: _completed_runs(_BASELINE_ARM, _series(0.5)),
        }
    if mode == "baseline_failed":
        # Consensus completes strong; baseline could not complete.
        return {
            _CONSENSUS_ARM: _completed_runs(_CONSENSUS_ARM, _series(0.9)),
            _BASELINE_ARM: _failed_runs(_BASELINE_ARM, _series(0.5)),
        }
    if mode == "both_failed":
        return {
            _CONSENSUS_ARM: _failed_runs(_CONSENSUS_ARM, _series(0.99)),
            _BASELINE_ARM: _failed_runs(_BASELINE_ARM, _series(0.5)),
        }
    raise ValueError(f"unknown mode {mode!r}")  # pragma: no cover


def _harness_result(modes: list[str]) -> HarnessResult:
    """Build a multi-scenario consensus-vs-baseline HarnessResult from per-scenario modes.

    Each mode becomes a distinct, uniquely named scenario whose consensus/baseline run
    lists realise that mode's KNOWN completeness state.
    """
    scenarios: list[Scenario] = []
    runs_by_pair: dict[tuple[str, str], list[ScenarioRun]] = {}
    for index, mode in enumerate(modes):
        name = f"scenario-{index}-{mode}"
        scenarios.append(
            Scenario(name=name, seed=index, shock=ShockParams(demand_multiplier=1.0))
        )
        for arm, runs in _runs_for_mode(mode).items():
            runs_by_pair[(name, arm)] = runs

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


# A grid mixing arbitrary modes with AT LEAST ONE guaranteed-incomplete scenario, so the
# overall run must be marked incomplete while some scenarios may complete normally.
@st.composite
def _mixed_grids(draw: st.DrawFn) -> list[str]:
    others = draw(st.lists(st.sampled_from(_ALL_MODES), min_size=0, max_size=5))
    forced_incomplete = draw(st.sampled_from(_INCOMPLETE_MODES))
    insert_at = draw(st.integers(min_value=0, max_value=len(others)))
    grid = list(others)
    grid.insert(insert_at, forced_incomplete)
    return grid


@settings(max_examples=150, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(modes=_mixed_grids())
def test_incomplete_pairs_never_credited_to_synapse(modes: list[str]) -> None:
    """Incomplete pairs resolve to TIE_INCONCLUSIVE (never SYNAPSE_WINS) and mark incomplete."""
    harness_result = _harness_result(modes)

    result = assemble_uplift_result(harness_result, _CONTRACT, fidelity=_FIDELITY)

    # The grid contains at least one incomplete scenario -> the whole run is incomplete.
    assert result.incomplete is True

    for index, mode in enumerate(modes):
        name = f"scenario-{index}-{mode}"
        outcome = result.per_scenario[(name, _PRIMARY_KPI)]
        if mode in _INCOMPLETE_MODES:
            # The core guarantee (R4.7): an arm that could not complete is NEVER
            # credited to SYNAPSE, even with strong-looking failed/absent data.
            assert outcome is not Outcome.SYNAPSE_WINS, (
                f"incomplete scenario {name} was wrongly credited to SYNAPSE"
            )
            # Per the implementation the affected pair resolves to TIE_INCONCLUSIVE.
            assert outcome is Outcome.TIE_INCONCLUSIVE, (
                f"incomplete scenario {name} did not resolve to TIE_INCONCLUSIVE"
            )
        else:
            # A fully-completed, well-separated scenario still classifies normally.
            assert outcome is Outcome.SYNAPSE_WINS


def test_failed_consensus_run_marks_incomplete_and_never_synapse() -> None:
    """A single strong-looking-but-failed consensus run cannot yield a SYNAPSE win."""
    result = assemble_uplift_result(
        _harness_result(["consensus_failed"]), _CONTRACT, fidelity=_FIDELITY
    )
    outcome = result.per_scenario[("scenario-0-consensus_failed", _PRIMARY_KPI)]
    assert result.incomplete is True
    assert outcome is not Outcome.SYNAPSE_WINS
    assert outcome is Outcome.TIE_INCONCLUSIVE


def test_absent_consensus_runs_mark_incomplete_and_never_synapse() -> None:
    """No consensus runs at all -> incomplete and never a SYNAPSE win."""
    result = assemble_uplift_result(
        _harness_result(["consensus_empty"]), _CONTRACT, fidelity=_FIDELITY
    )
    outcome = result.per_scenario[("scenario-0-consensus_empty", _PRIMARY_KPI)]
    assert result.incomplete is True
    assert outcome is not Outcome.SYNAPSE_WINS
    assert outcome is Outcome.TIE_INCONCLUSIVE


def test_mixed_complete_and_incomplete_only_flags_incomplete() -> None:
    """A completing scenario keeps its SYNAPSE win while the incomplete one never does."""
    result = assemble_uplift_result(
        _harness_result(["complete_win", "baseline_failed"]),
        _CONTRACT,
        fidelity=_FIDELITY,
    )
    assert result.incomplete is True
    assert (
        result.per_scenario[("scenario-0-complete_win", _PRIMARY_KPI)]
        is Outcome.SYNAPSE_WINS
    )
    incomplete_outcome = result.per_scenario[
        ("scenario-1-baseline_failed", _PRIMARY_KPI)
    ]
    assert incomplete_outcome is not Outcome.SYNAPSE_WINS
    assert incomplete_outcome is Outcome.TIE_INCONCLUSIVE
