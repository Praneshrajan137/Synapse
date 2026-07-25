"""Property-based test for the All_Wins_Guard self-scrutiny warning.

Feature: core-purpose-uplift, Property 21: The all-wins guard fires exactly when every
pair is a SYNAPSE win.

    *For any* non-empty classified ``per_scenario`` grid, ``all_wins_warning`` is
    ``true`` if and only if every classified pair is ``SYNAPSE_WINS``; an empty grid
    never warns.

    Requirement 6.7: "WHEN every classified pair is `SYNAPSE_WINS`, THE Uplift_Harness
    SHALL raise the All_Wins_Guard warning prompting a measurement-bias review."

Synthetic ``HarnessResult`` / ``ScenarioRun`` data is constructed directly — no twin
runs, no consensus assembly — so the property is pure, fast, and $0.

**Validates: Requirements 6.7**
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
# C34 gauge (fidelity context is irrelevant to Property 21).
_FIDELITY = FidelityReport(kl_divergence=0.02, threshold=0.1)

# Replicate count per arm: large enough that a ~0.4 mean gap with tight within-arm
# spread is Mann-Whitney significant with |d| far above the 0.2 MDE.
_N = 24

# Per-scenario modes, each with a KNOWN classified outcome under the real contract.
#   win     -> consensus clearly higher on a higher-is-better KPI  -> SYNAPSE_WINS
#   tie     -> identical distributions (no significance)           -> TIE_INCONCLUSIVE
#   loss    -> baseline clearly higher                             -> BASELINE_WINS
#   partial -> win-looking samples + one failed consensus replicate
#              -> TIE_INCONCLUSIVE per R2.5 (never credited to SYNAPSE)
_MODE_OUTCOME = {
    "win": Outcome.SYNAPSE_WINS,
    "tie": Outcome.TIE_INCONCLUSIVE,
    "loss": Outcome.BASELINE_WINS,
    "partial": Outcome.TIE_INCONCLUSIVE,
}
_MODES = tuple(_MODE_OUTCOME)


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


def _consensus_runs(mode: str) -> list[ScenarioRun]:
    """The consensus-arm run list realising ``mode``."""
    if mode == "win":
        return _completed(_CONSENSUS_ARM, _series(0.9))
    if mode == "loss":
        return _completed(_CONSENSUS_ARM, _series(0.5))
    if mode == "tie":
        return _completed(_CONSENSUS_ARM, _series(0.6))
    if mode == "partial":
        # Win-looking completed replicates plus one failed replicate: some but not all
        # replicates completed, so the pair resolves TIE_INCONCLUSIVE (R2.5).
        runs = _completed(_CONSENSUS_ARM, _series(0.9, _N - 1))
        runs.append(
            ScenarioRun(
                arm=_CONSENSUS_ARM,
                seed=1_000,
                kpis=None,
                failed=True,
                error="injected failure",
            )
        )
        return runs
    raise ValueError(f"unknown mode {mode!r}")  # pragma: no cover


def _baseline_runs(mode: str) -> list[ScenarioRun]:
    """The baseline-arm run list for ``mode`` (always fully completed)."""
    if mode == "loss":
        return _completed(_BASELINE_ARM, _series(0.9))
    if mode == "tie":
        return _completed(_BASELINE_ARM, _series(0.6))
    return _completed(_BASELINE_ARM, _series(0.5))


def _harness_result(modes: list[str]) -> HarnessResult:
    """Build a multi-scenario consensus-vs-baseline HarnessResult from ``modes``.

    Each mode becomes a distinct, uniquely named scenario whose classified outcome is
    known in advance (``_MODE_OUTCOME``). An empty ``modes`` list yields an empty grid.
    """
    scenarios: list[Scenario] = []
    runs_by_pair: dict[tuple[str, str], list[ScenarioRun]] = {}
    for index, mode in enumerate(modes):
        name = f"scenario-{index}-{mode}"
        scenarios.append(
            Scenario(name=name, seed=index, shock=ShockParams(demand_multiplier=1.0))
        )
        runs_by_pair[(name, _CONSENSUS_ARM)] = _consensus_runs(mode)
        runs_by_pair[(name, _BASELINE_ARM)] = _baseline_runs(mode)

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


# Grids include the empty grid (min_size=0) so the "empty never warns" clause is part of
# the same biconditional, all-"win" grids (guard MUST fire), and mixed grids (MUST NOT).
_mode_grids = st.lists(st.sampled_from(_MODES), min_size=0, max_size=5)


@settings(max_examples=150, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(modes=_mode_grids)
def test_all_wins_guard_fires_iff_every_pair_is_a_synapse_win(modes: list[str]) -> None:
    """all_wins_warning is True IFF the grid is non-empty and every pair is a win."""
    result = assemble_uplift_result(_harness_result(modes), _CONTRACT, fidelity=_FIDELITY)

    # Ground truth: each scenario classified to exactly its mode's known outcome,
    # established independently of the guard logic under test.
    for index, mode in enumerate(modes):
        name = f"scenario-{index}-{mode}"
        assert result.per_scenario[(name, _PRIMARY_KPI)] is _MODE_OUTCOME[mode], (
            f"scenario {name} classified unexpectedly"
        )

    # The expected guard state computed two independent ways:
    #  (a) from the assembled grid: non-empty and every classified pair is SYNAPSE_WINS
    #  (b) from the modes: non-empty and every mode is "win"
    expected_from_grid = bool(result.per_scenario) and all(
        outcome is Outcome.SYNAPSE_WINS for outcome in result.per_scenario.values()
    )
    expected_from_modes = bool(modes) and all(mode == "win" for mode in modes)
    assert expected_from_grid == expected_from_modes

    assert result.all_wins_warning is expected_from_grid
    assert result.all_wins_warning is expected_from_modes
