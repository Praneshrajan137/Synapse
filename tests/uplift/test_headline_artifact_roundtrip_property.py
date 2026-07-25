"""Property-based test that the headline uplift round-trips through the result artifact.

Feature: core-purpose-uplift
Property 7: Headline uplift round-trips through the result artifact

    *For any* assembled non-incomplete :class:`~uplift.interfaces.UpliftResult`, writing
    the result artifact and reading it back yields a finite numeric ``headline_uplift``
    and ``incomplete = false``.

    Requirement 2.3: "WHEN the result artifact is written for a non-incomplete run, THE
    Uplift_Harness SHALL persist a finite numeric ``headline_uplift`` field to
    ``artifacts/uplift/result.json`` with ``incomplete`` set to ``false``."

    The test builds ``HarnessResult`` / ``ScenarioRun`` data directly — no twin runs and
    no consensus assembly — so it is pure, fast, and network-free ($0, I-1). Artifacts
    are written under a pytest temp directory, never to the repo's
    ``artifacts/uplift/result.json``.

    Read-back is done through the C60 gate's own reader
    (:func:`scripts.audit.uplift_truth.read_measured_uplift`), which returns ``None`` for
    any unavailable measurement (missing / unreadable / non-numeric / non-finite), so the
    round-trip is asserted against the exact consumer of the artifact.

**Validates: Requirements 2.3**
"""
from __future__ import annotations

import json
import math

from hypothesis import given, settings
from hypothesis import strategies as st

from scripts.audit.uplift_truth import read_measured_uplift
from uplift.cli import _write_result_artifact
from uplift.contract import load_contract
from uplift.fidelity import FidelityReport
from uplift.harness import (
    DEFAULT_CONSENSUS_ARM,
    HarnessResult,
    aggregate_arm,
    assemble_uplift_result,
    build_uplift_report,
)
from uplift.interfaces import KpiVector, Scenario, ScenarioRun

from digital_twin.simulation.monte_carlo import ShockParams

# The real, version-controlled metric contract (single primary KPI ``fill_rate``).
_CONTRACT = load_contract()

# fill_rate values are kept strictly positive so the pooled baseline mean is non-zero and
# the relative-change denominator is defined; the other KPI fields are fixed constants
# because the headline is computed on the FIRST declared primary KPI only.
_FILL_RATES = st.floats(
    min_value=0.05, max_value=1.0, allow_nan=False, allow_infinity=False
)


def _kpi(fill_rate: float) -> KpiVector:
    return KpiVector(
        fill_rate=fill_rate,
        spoilage_rate=0.0,
        stockout_rate=0.0,
        avg_delivery_time_min=1.0,
        margin=1.0,
        co2_estimate=1.0,
    )


def _completed_runs(arm: str, fill_rates: list[float]) -> list[ScenarioRun]:
    """Runs for one ``(scenario, arm)`` pair that all complete cleanly."""
    return [
        ScenarioRun(arm=arm, seed=index, kpis=_kpi(value), failed=False, error=None)
        for index, value in enumerate(fill_rates)
    ]


@st.composite
def _complete_harness_results(draw: st.DrawFn) -> tuple[HarnessResult, FidelityReport]:
    """A synthetic HarnessResult in which EVERY compared pair completes cleanly.

    Every ``(scenario, arm)`` pair records at least one completed run and zero failed
    runs, which is exactly the ``_run_is_incomplete`` predicate for a non-incomplete
    result — the precondition of Property 7. The grid is kept small (1-3 scenarios x 1-3
    baseline arms, 2-4 replicates) because the property depends on artifact persistence,
    not on sample size. The fidelity report is generated (available/unavailable, within
    and beyond the threshold) so the artifact's co-located fidelity block varies too.
    """
    n_scenarios = draw(st.integers(min_value=1, max_value=3))
    n_baselines = draw(st.integers(min_value=1, max_value=3))
    n_replicates = draw(st.integers(min_value=2, max_value=4))
    arm_names = (DEFAULT_CONSENSUS_ARM, *(f"baseline-{i}" for i in range(n_baselines)))

    scenarios = [
        Scenario(
            name=f"scenario-{index}",
            seed=4001 + index,
            shock=ShockParams(demand_multiplier=1.0),
        )
        for index in range(n_scenarios)
    ]

    runs_by_pair: dict[tuple[str, str], list[ScenarioRun]] = {}
    for scenario in scenarios:
        for arm in arm_names:
            fill_rates = draw(
                st.lists(_FILL_RATES, min_size=n_replicates, max_size=n_replicates)
            )
            runs_by_pair[(scenario.name, arm)] = _completed_runs(arm, fill_rates)

    harness_result = HarnessResult(
        arm_results={pair: aggregate_arm(pair[1], runs) for pair, runs in runs_by_pair.items()},
        runs_by_pair=runs_by_pair,
        all_runs=[run for runs in runs_by_pair.values() for run in runs],
        results_path=None,
        scenarios=tuple(scenarios),
        arm_names=arm_names,
    )

    kl = draw(st.none() | st.floats(min_value=0.0, max_value=1.0, allow_nan=False))
    fidelity = FidelityReport(kl_divergence=kl, threshold=0.1)
    return harness_result, fidelity


@settings(max_examples=200, deadline=None)
@given(case=_complete_harness_results())
def test_headline_uplift_round_trips_through_result_artifact(
    case: tuple[HarnessResult, FidelityReport], tmp_path_factory
) -> None:
    """A non-incomplete result persists a finite numeric headline and ``incomplete: false``."""
    harness_result, fidelity = case

    result = assemble_uplift_result(harness_result, _CONTRACT, fidelity=fidelity)
    # Precondition of Property 7: the assembled result is NOT incomplete.
    assert result.incomplete is False

    report = build_uplift_report(result)
    path = tmp_path_factory.mktemp("uplift-artifact") / "result.json"
    written = _write_result_artifact(path, result, report)

    payload = json.loads(written.read_text(encoding="utf-8"))

    # The persisted headline is a finite JSON number (not a bool, not a string).
    headline = payload["headline_uplift"]
    assert isinstance(headline, float) and not isinstance(headline, bool)
    assert math.isfinite(headline)

    # ... and it round-trips to the assembled value.
    assert headline == float(result.headline_uplift)

    # The persisted completeness flag is exactly ``false`` for a non-incomplete run.
    assert payload["incomplete"] is False

    # The C60 gate's own reader sees an AVAILABLE finite measurement, never ``None``.
    measured = read_measured_uplift(written)
    assert measured is not None
    assert math.isfinite(measured)
    assert measured == float(result.headline_uplift)


def test_artifact_round_trip_example_positive_headline(tmp_path) -> None:
    """A clean grid where consensus beats the baseline persists a positive headline."""
    scenario = Scenario(name="scenario-0", seed=4001, shock=ShockParams(demand_multiplier=1.0))
    runs_by_pair = {
        (scenario.name, DEFAULT_CONSENSUS_ARM): _completed_runs(
            DEFAULT_CONSENSUS_ARM, [0.90, 0.92, 0.91]
        ),
        (scenario.name, "baseline-0"): _completed_runs("baseline-0", [0.60, 0.61, 0.59]),
    }
    harness_result = HarnessResult(
        arm_results={pair: aggregate_arm(pair[1], runs) for pair, runs in runs_by_pair.items()},
        runs_by_pair=runs_by_pair,
        all_runs=[run for runs in runs_by_pair.values() for run in runs],
        results_path=None,
        scenarios=(scenario,),
        arm_names=(DEFAULT_CONSENSUS_ARM, "baseline-0"),
    )

    result = assemble_uplift_result(
        harness_result, _CONTRACT, fidelity=FidelityReport(kl_divergence=0.02, threshold=0.1)
    )
    written = _write_result_artifact(
        tmp_path / "result.json", result, build_uplift_report(result)
    )

    payload = json.loads(written.read_text(encoding="utf-8"))
    assert payload["incomplete"] is False
    assert payload["headline_uplift"] > 0.0
    assert read_measured_uplift(written) == payload["headline_uplift"]
