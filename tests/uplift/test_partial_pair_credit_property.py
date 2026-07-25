"""Property-based test that incomplete/partial pairs are never credited to SYNAPSE.

Feature: core-purpose-uplift, Property 5: Incomplete or partial pairs are never
credited to SYNAPSE.

    *For any* scenario that has zero completed consensus runs, or any consensus pair
    with at least one failed replicate, the run is marked ``incomplete`` and the
    affected pair's ``Outcome`` is ``TIE_INCONCLUSIVE`` (never ``SYNAPSE_WINS``).

    Requirement 2.4: "IF any declared scenario has zero completed Consensus_Arm runs,
    THEN THE Uplift_Harness SHALL mark the assembled UpliftResult as incomplete and
    SHALL NOT credit any incomplete pair to SYNAPSE."

    Requirement 2.5: "IF a scenario has some but not all Consensus_Arm replicates
    completed (at least one failed replicate), THEN THE Uplift_Harness SHALL mark the
    run incomplete and SHALL classify the affected pair as TIE_INCONCLUSIVE, never
    SYNAPSE_WINS."

Synthetic ``HarnessResult`` / ``ScenarioRun`` data is constructed directly — no twin
runs, no consensus assembly — so the property is pure, fast, and $0.

**Validates: Requirements 2.4, 2.5**
"""
from __future__ import annotations

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from uplift.contract import load_contract
from uplift.fidelity import FidelityReport
from uplift.harness import HarnessResult, aggregate_arm, assemble_uplift_result
from uplift.interfaces import KpiVector, Outcome, Scenario, ScenarioRun

from digital_twin.simulation.monte_carlo import ShockParams


# The real, version-controlled metric contract: single primary KPI ``fill_rate``
# (higher-is-better, Cohen's d MDE 0.2, Mann-Whitney U at alpha 0.05).
_CONTRACT = load_contract()
_PRIMARY_KPI = "fill_rate"
_CONSENSUS_ARM = "consensus"
_BASELINE_ARM = "baseline"

# Deterministic, available, within-bound fidelity so assembly never touches the live
# C34 gauge (fidelity context is irrelevant to Property 5).
_FIDELITY = FidelityReport(kl_divergence=0.02, threshold=0.1)

# Replicate count per arm: large enough that a ~0.4 mean gap with tight within-arm
# spread is Mann-Whitney significant with |d| far above the 0.2 MDE, so a *fully*
# completed pair deterministically classifies SYNAPSE_WINS. That makes the affected
# modes below adversarial: the completed consensus data always "looks" like a win.
_N = 24

# Modes with a KNOWN completeness state for the consensus pair.
#   complete_win      -> control: all consensus replicates completed, clearly better
#   zero_all_failed   -> every consensus replicate failed (zero completed) - R2.4
#   zero_no_runs      -> no consensus runs recorded at all (zero completed)  - R2.4
#   partial_failed    -> some completed (strong) + at least one failed       - R2.5
_CONTROL_MODES = ("complete_win",)
_AFFECTED_MODES = ("zero_all_failed", "zero_no_runs", "partial_failed")
_ALL_MODES = _CONTROL_MODES + _AFFECTED_MODES


def _kpi(fill_rate: float) -> KpiVector:
    """A KpiVector varying only ``fill_rate``; the other fields are fixed constants."""
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


def _completed(arm: str, fill_rates: list[float]) -> list[ScenarioRun]:
    """Completed (non-failed) runs for ``arm``."""
    return [
        ScenarioRun(arm=arm, seed=i, kpis=_kpi(fr), failed=False, error=None)
        for i, fr in enumerate(fill_rates)
    ]


def _failed(arm: str, fill_rates: list[float]) -> list[ScenarioRun]:
    """Failed runs for ``arm``, carrying strong-looking (but uncreditable) KPIs."""
    return [
        ScenarioRun(
            arm=arm, seed=1_000 + i, kpis=_kpi(fr), failed=True, error="injected failure"
        )
        for i, fr in enumerate(fill_rates)
    ]


def _consensus_runs(mode: str, completed_count: int) -> list[ScenarioRun]:
    """The consensus-arm run list realising ``mode``'s completeness state."""
    if mode == "complete_win":
        return _completed(_CONSENSUS_ARM, _series(0.9))
    if mode == "zero_all_failed":
        return _failed(_CONSENSUS_ARM, _series(0.99))
    if mode == "zero_no_runs":
        return []
    if mode == "partial_failed":
        # ``completed_count`` strong completed replicates plus the remainder failed:
        # some but not all replicates completed (R2.5).
        completed = _completed(_CONSENSUS_ARM, _series(0.9, completed_count))
        failed = _failed(_CONSENSUS_ARM, _series(0.99, _N - completed_count))
        return completed + failed
    raise ValueError(f"unknown mode {mode!r}")  # pragma: no cover


def _harness_result(grid: list[tuple[str, int]]) -> HarnessResult:
    """Build a multi-scenario consensus-vs-baseline HarnessResult from ``grid`` modes.

    The baseline arm always completes every replicate, so the only source of
    incompleteness is the consensus pair under test.
    """
    scenarios: list[Scenario] = []
    runs_by_pair: dict[tuple[str, str], list[ScenarioRun]] = {}
    for index, (mode, completed_count) in enumerate(grid):
        name = f"scenario-{index}-{mode}"
        scenarios.append(
            Scenario(name=name, seed=index, shock=ShockParams(demand_multiplier=1.0))
        )
        runs_by_pair[(name, _CONSENSUS_ARM)] = _consensus_runs(mode, completed_count)
        runs_by_pair[(name, _BASELINE_ARM)] = _completed(_BASELINE_ARM, _series(0.5))

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


@st.composite
def _grids(draw: st.DrawFn) -> list[tuple[str, int]]:
    """A scenario grid containing AT LEAST ONE affected (zero/partial) consensus pair.

    Each entry is ``(mode, completed_count)``; ``completed_count`` only matters for
    ``partial_failed``, where it is constrained to ``[1, _N - 1]`` so the pair genuinely
    has some — but not all — replicates completed.
    """
    modes = st.sampled_from(_ALL_MODES)
    counts = st.integers(min_value=1, max_value=_N - 1)
    others = draw(st.lists(st.tuples(modes, counts), min_size=0, max_size=4))
    forced = draw(st.tuples(st.sampled_from(_AFFECTED_MODES), counts))
    insert_at = draw(st.integers(min_value=0, max_value=len(others)))
    grid = list(others)
    grid.insert(insert_at, forced)
    return grid


@settings(max_examples=120, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(grid=_grids())
def test_incomplete_or_partial_pairs_never_credited_to_synapse(
    grid: list[tuple[str, int]],
) -> None:
    """Zero-completed or partially-failed consensus pairs -> incomplete + TIE, never a win."""
    result = assemble_uplift_result(_harness_result(grid), _CONTRACT, fidelity=_FIDELITY)

    # The grid always contains at least one affected pair -> the whole run is incomplete.
    assert result.incomplete is True

    for index, (mode, _count) in enumerate(grid):
        name = f"scenario-{index}-{mode}"
        outcome = result.per_scenario[(name, _PRIMARY_KPI)]
        if mode in _AFFECTED_MODES:
            assert outcome is not Outcome.SYNAPSE_WINS, (
                f"{mode} scenario {name} was wrongly credited to SYNAPSE"
            )
            assert outcome is Outcome.TIE_INCONCLUSIVE, (
                f"{mode} scenario {name} did not resolve to TIE_INCONCLUSIVE "
                f"(got {outcome})"
            )
        else:
            # A fully completed, well-separated pair still classifies normally.
            assert outcome is Outcome.SYNAPSE_WINS
