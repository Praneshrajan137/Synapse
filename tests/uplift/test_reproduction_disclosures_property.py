"""Property-based test that reproduction output always carries its disclosures/labels.

Feature: core-purpose-uplift, Property 12: Reproduction output carries required
disclosures and labels.

    *For any* run mode, the CLI output contains the synthetic-only data-provenance
    disclosure, the no-external-paid-service disclosure, and the "<= 1.0 percentage
    point" noise-tolerance statement; and *for any* reduced-cost run it additionally
    contains the "NOT a fully-powered proof" label.

The generator covers the whole mode surface :func:`uplift.cli._resolve_run_config` can
resolve: ``--smoke``, ``--full``, no mode flag at all, an explicit ``--n`` below the
INV-TW-002 floor, an explicit ``--n`` at/above the floor, and ``--smoke`` combined with
a large ``--n`` (smoke wins, so the run is still reduced-cost) — plus optional cadence
overrides. It also varies the run outcome between a fully completed matrix and one where
the consensus arm failed every replicate (the honest-failure / ``incomplete`` path), so
the disclosures must hold whether or not the headline is credited.

Kept fast (this is the point of the stubs): the real consensus-arm assembly and the real
closed-loop twin run are the expensive parts (Tier-4 twin verification is seconds per
decision, and ``--full`` would demand 1000 replicates per arm), and neither influences
the disclosure text. So ``build_arms``, ``_run_reduced``, and ``UpliftHarness`` are
patched with in-process stubs that return a small hand-built
:class:`~uplift.harness.HarnessResult`; everything downstream of the run — contract
loading, result assembly, fidelity-co-located reporting, disclosure printing, and
artifact writing — is the real CLI code path. No sockets, no models, no paid services.

Validates: Requirements 3.4, 7.2, 7.6
"""
from __future__ import annotations

import contextlib
import io
import tempfile
from pathlib import Path
from unittest.mock import patch

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from digital_twin.simulation.monte_carlo import MIN_SCENARIOS, ShockParams

import uplift.cli as cli
from uplift.cli import NOISE_TOLERANCE_PP, SMOKE_REPLICATES, main
from uplift.harness import DEFAULT_CONSENSUS_ARM, HarnessResult, aggregate_arm
from uplift.interfaces import KpiVector, Observation, PolicyAction, Scenario, ScenarioRun


_BASELINE_ARM = "par_level_reorder"

_SCENARIO = Scenario(
    name="demand-spike", seed=7, shock=ShockParams(demand_multiplier=2.0)
)


class _StubPolicy:
    """A named no-op ``DecisionPolicy``; never actually asked to decide (run is stubbed)."""

    def __init__(self, name: str) -> None:
        self.name = name

    def decide(self, obs: Observation) -> PolicyAction:  # noqa: ARG002 — never invoked
        return PolicyAction()


def _kpi(fill_rate: float) -> KpiVector:
    return KpiVector(
        fill_rate=fill_rate,
        spoilage_rate=0.0,
        stockout_rate=0.0,
        avg_delivery_time_min=1.0,
        margin=1.0,
        co2_estimate=1.0,
    )


def _completed_runs(arm: str, base: float) -> list[ScenarioRun]:
    """A small spread of completed runs so the significance test is well-defined."""
    return [
        ScenarioRun(
            arm=arm,
            seed=i,
            kpis=_kpi(base + (i % 5) * 0.001),
            failed=False,
            error=None,
        )
        for i in range(40)
    ]


def _failed_runs(arm: str) -> list[ScenarioRun]:
    return [
        ScenarioRun(arm=arm, seed=i, kpis=None, failed=True, error="arm unavailable")
        for i in range(5)
    ]


def _stub_harness_result(consensus_failed: bool) -> HarnessResult:
    """A hand-built harness result standing in for a real (slow) closed-loop matrix."""
    consensus = (
        _failed_runs(DEFAULT_CONSENSUS_ARM)
        if consensus_failed
        else _completed_runs(DEFAULT_CONSENSUS_ARM, 0.9)
    )
    runs_by_pair = {
        (_SCENARIO.name, DEFAULT_CONSENSUS_ARM): consensus,
        (_SCENARIO.name, _BASELINE_ARM): _completed_runs(_BASELINE_ARM, 0.5),
    }
    return HarnessResult(
        arm_results={
            pair: aggregate_arm(pair[1], runs) for pair, runs in runs_by_pair.items()
        },
        runs_by_pair=runs_by_pair,
        all_runs=[run for runs in runs_by_pair.values() for run in runs],
        results_path=None,
        scenarios=(_SCENARIO,),
        arm_names=(DEFAULT_CONSENSUS_ARM, _BASELINE_ARM),
    )


@st.composite
def _run_modes(draw: st.DrawFn) -> tuple[list[str], bool, bool]:
    """Draw (mode argv, expected_reduced, consensus_failed) over every CLI run mode."""
    kind = draw(
        st.sampled_from(["smoke", "full", "default", "n_below", "n_at_or_above", "smoke_big_n"])
    )
    if kind == "smoke":
        argv, n, smoke = ["--smoke"], SMOKE_REPLICATES, True
    elif kind == "full":
        argv, n, smoke = ["--full"], MIN_SCENARIOS, False
    elif kind == "default":
        argv, n, smoke = [], SMOKE_REPLICATES, False
    elif kind == "n_below":
        n = draw(st.integers(min_value=1, max_value=MIN_SCENARIOS - 1))
        argv, smoke = ["--n", str(n)], False
    elif kind == "n_at_or_above":
        n = draw(st.integers(min_value=MIN_SCENARIOS, max_value=5 * MIN_SCENARIOS))
        argv, smoke = ["--n", str(n)], False
    else:  # smoke wins over a large --n: still a reduced-cost run
        n = draw(st.integers(min_value=MIN_SCENARIOS, max_value=5 * MIN_SCENARIOS))
        argv, smoke = ["--smoke", "--n", str(n)], True

    # Mirror cli._resolve_run_config's reduced-cost predicate.
    expected_reduced = smoke or n < MIN_SCENARIOS

    # Optional cadence override (does not affect the disclosures, but is part of the
    # mode surface an operator can pass).
    if draw(st.booleans()):
        argv += ["--duration-hours", str(draw(st.sampled_from([1.0, 2.0, 4.0])))]
    if draw(st.booleans()):
        argv += ["--seed", str(draw(st.integers(min_value=0, max_value=99)))]

    return argv, expected_reduced, draw(st.booleans())


@settings(max_examples=120, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(case=_run_modes())
def test_reproduction_output_carries_disclosures_and_labels(
    case: tuple[list[str], bool, bool],
) -> None:
    """Every run mode discloses provenance, $0-ness, tolerance; reduced runs are labelled.

    **Validates: Requirements 3.4, 7.2, 7.6**
    """
    mode_argv, expected_reduced, consensus_failed = case
    harness_result = _stub_harness_result(consensus_failed)
    arms = (_StubPolicy(DEFAULT_CONSENSUS_ARM), _StubPolicy(_BASELINE_ARM))

    class _StubHarness:
        """Stands in for the real (slow) ``UpliftHarness`` in fully-powered mode."""

        def __init__(self, **kwargs: object) -> None:
            self.kwargs = kwargs

        def run(self, *args: object, **kwargs: object) -> HarnessResult:
            return harness_result

    with tempfile.TemporaryDirectory() as tmpdir:
        output = Path(tmpdir) / "result.json"
        argv = mode_argv + ["--output", str(output)]
        buffer = io.StringIO()
        with (
            patch.object(cli, "build_arms", lambda seed=0: arms),
            patch.object(cli, "_run_reduced", lambda *a, **k: harness_result),
            patch.object(cli, "UpliftHarness", _StubHarness),
            contextlib.redirect_stdout(buffer),
        ):
            code = main(argv)
        out = buffer.getvalue()

    # The run reached the reporting stage (a completed baseline arm always exists).
    assert code == 0, out

    # R7.2 — data provenance is disclosed as synthetic-only, in every mode.
    assert "synthetic seed-generated data only" in out
    # R7.2 / R7.6 — no external paid service is disclosed, in every mode.
    assert "no external paid service" in out

    # R7.6 — the version-controlled noise tolerance is stated, and it is <= 1.0 pp.
    assert NOISE_TOLERANCE_PP <= 1.0
    assert "applied noise tolerance:" in out
    assert f"<= {NOISE_TOLERANCE_PP:.1f} percentage point" in out
    assert "<= 1.0 percentage point" in out

    # R3.4 — a reduced-cost run is labelled NOT a fully-powered proof; a fully-powered
    # run is not mislabelled as reduced-cost.
    if expected_reduced:
        assert "NOT a fully-powered proof" in out
        assert "reduced-cost" in out
    else:
        assert "NOT a fully-powered proof" not in out
        assert "fully-powered PROOF" in out
