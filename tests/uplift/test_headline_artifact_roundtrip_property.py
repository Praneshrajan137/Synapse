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

    Read-back is done through the artifact model the C60 gate actually consumes
    (:meth:`uplift.harness.UpliftArtifact.read`), which rejects any payload that does not
    carry a finite ``headline_uplift``, a boolean ``incomplete``, an integral
    replicates-per-arm count, and a provenance record, so the round-trip is asserted
    against the exact consumer of the artifact. (Before the purpose-achievement-audit R2
    remediation this read went through ``uplift_truth.read_measured_uplift``, which looked
    at ``headline_uplift`` alone; that reader is gone with the tautology it enabled.)

    **Carried to Metric_Contract v2 (decision-quality-proof tasks 15.1 and 29.4).** The
    headline is no longer a relative change in ``fill_rate``: it is the mean paired
    difference of the committed ``objective`` (comparator minus subject, objective units,
    positive = the consensus arm is cheaper), computed once as the point of the
    ``1 - alpha`` interval. The claim is unchanged and is restated over the objective, so
    the generated runs vary ``objective`` -- ``fill_rate`` is secondary and cannot move the
    headline. The round trip is also asserted to keep the v2 pin: the persisted headline is
    the persisted interval's point (or the no-estimate sentinel when no interval exists),
    carried beside the verdict it licenses, the margin, the comparator and the whole-run
    flag. The artifact is written with the provenance ``uplift.cli.main`` records, arm
    roles included.

**Validates: Requirements 2.3**
"""
from __future__ import annotations

import json
import math
from typing import TYPE_CHECKING, Final

from hypothesis import given, settings
from hypothesis import strategies as st

from uplift.cli import _write_result_artifact
from uplift.contract import interval_verdict, load_contract
from uplift.fidelity import FidelityReport
from uplift.harness import (
    ARTIFACT_SCHEMA_VERSION,
    DEFAULT_CONSENSUS_ARM,
    NO_ESTIMATE_HEADLINE,
    ArtifactInterval,
    HarnessResult,
    UpliftArtifact,
    UpliftProvenance,
    aggregate_arm,
    assemble_uplift_result,
    build_uplift_report,
    resolve_provenance,
)
from uplift.interfaces import ArmRole, KpiVector, Scenario, ScenarioRun

from digital_twin.simulation.monte_carlo import ShockParams

if TYPE_CHECKING:
    from pathlib import Path

    import pytest

# The real, version-controlled metric contract (Metric_Contract v2: the committed objective is
# the sole primary KPI, judged against the committed materiality margin).
_CONTRACT = load_contract()

# Objective values are a COST (lower is better). The v2 headline is a mean paired
# DIFFERENCE, so no denominator has to be kept away from zero; the other seven KPI fields are
# fixed constants because none of them can move the v2 headline.
_OBJECTIVES = st.floats(min_value=0.0, max_value=1e3, allow_nan=False, allow_infinity=False)

#: The attributed identity every written artifact records, so nothing is read from the
#: environment and the provenance is the same on a dev box and on a CI runner.
_REVISION: Final[str] = "0f1e2d3c4b5a"
_RUN_ID: Final[str] = "run-20260101-01"


def _kpi(objective: float) -> KpiVector:
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


def _completed_runs(arm: str, objectives: list[float]) -> list[ScenarioRun]:
    """Runs for one ``(scenario, arm)`` pair that all complete cleanly.

    Replicate ``i`` records seed ``i`` in every arm, which is what the harness pairs on.
    """
    return [
        ScenarioRun(arm=arm, seed=index, kpis=_kpi(value), failed=False, error=None)
        for index, value in enumerate(objectives)
    ]


def _role(arm: str) -> ArmRole:
    """The consensus arm is the subject; every other generated arm is a declared baseline."""
    if arm == DEFAULT_CONSENSUS_ARM:
        return "consensus"
    return "baseline"


def _harness_result(
    scenarios: list[Scenario],
    runs_by_pair: dict[tuple[str, str], list[ScenarioRun]],
    arm_names: tuple[str, ...],
) -> HarnessResult:
    return HarnessResult(
        arm_results={pair: aggregate_arm(pair[1], runs) for pair, runs in runs_by_pair.items()},
        runs_by_pair=runs_by_pair,
        all_runs=[run for runs in runs_by_pair.values() for run in runs],
        results_path=None,
        scenarios=tuple(scenarios),
        arm_names=arm_names,
        arm_roles={arm: _role(arm) for arm in arm_names},
    )


def _provenance(harness_result: HarnessResult, replicates: int) -> UpliftProvenance:
    """The provenance ``uplift.cli.main`` records: the arms WITH their declared roles."""
    return resolve_provenance(
        arms=harness_result.arm_names,
        arm_roles=harness_result.arm_roles,
        replicates_per_arm=replicates,
        seeds=[scenario.seed for scenario in harness_result.scenarios],
        revision=_REVISION,
        run_id=_RUN_ID,
    )


@st.composite
def _complete_harness_results(
    draw: st.DrawFn,
) -> tuple[HarnessResult, FidelityReport, int]:
    """A synthetic HarnessResult in which EVERY compared pair completes cleanly.

    Every ``(scenario, arm)`` pair records at least one completed run and zero failed
    runs, which is exactly the ``_run_is_incomplete`` predicate for a non-incomplete
    result — the precondition of Property 7. The grid is kept small (1-3 scenarios x 1-3
    baseline arms, 2-4 replicates) because the property depends on artifact persistence,
    not on sample size. The fidelity report is generated (available/unavailable, within
    and beyond the threshold) so the artifact's co-located fidelity block varies too.
    The replicate count is returned beside the run so the provenance can record it.
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
            objectives = draw(
                st.lists(_OBJECTIVES, min_size=n_replicates, max_size=n_replicates)
            )
            runs_by_pair[(scenario.name, arm)] = _completed_runs(arm, objectives)

    harness_result = _harness_result(scenarios, runs_by_pair, arm_names)

    kl = draw(st.none() | st.floats(min_value=0.0, max_value=1.0, allow_nan=False))
    fidelity = FidelityReport(kl_divergence=kl, threshold=0.1)
    return harness_result, fidelity, n_replicates


@settings(deadline=None)
@given(case=_complete_harness_results())
def test_headline_uplift_round_trips_through_result_artifact(
    case: tuple[HarnessResult, FidelityReport, int],
    tmp_path_factory: pytest.TempPathFactory,
) -> None:
    """A non-incomplete result persists a finite numeric headline and ``incomplete: false``."""
    harness_result, fidelity, replicates = case

    result = assemble_uplift_result(harness_result, _CONTRACT, fidelity=fidelity)
    # Precondition of Property 7: the assembled result is NOT incomplete -- neither the
    # contrast nor (every arm completing) the run as a whole.
    assert result.incomplete is False
    assert result.run_incomplete is False

    report = build_uplift_report(result)
    path = tmp_path_factory.mktemp("uplift-artifact") / "result.json"
    written = _write_result_artifact(
        path,
        result,
        report,
        harness_result=harness_result,
        provenance=_provenance(harness_result, replicates),
    )

    payload = json.loads(written.read_text(encoding="utf-8"))

    # The persisted headline is a finite JSON number (not a bool, not a string).
    headline = payload["headline_uplift"]
    assert isinstance(headline, float) and not isinstance(headline, bool)
    assert math.isfinite(headline)

    # ... and it round-trips to the assembled value.
    assert headline == float(result.headline_uplift)

    # The persisted completeness flag is exactly ``false`` for a non-incomplete run.
    assert payload["incomplete"] is False

    # The artifact model the C60 gate consumes parses it and sees the same finite value.
    read_back = UpliftArtifact.read(written)
    measured = read_back.headline_uplift
    assert math.isfinite(measured)
    assert measured == float(result.headline_uplift)

    # v2: the headline is the committed objective's, and it is the persisted interval's
    # point -- or the no-estimate sentinel when no interval exists -- never a second number.
    assert payload["schema_version"] == ARTIFACT_SCHEMA_VERSION
    assert payload["primary_kpi"] == _CONTRACT.objective_kpi
    interval = payload["interval"]
    assert headline == (interval["point"] if interval is not None else NO_ESTIMATE_HEADLINE)
    assert read_back.interval == (
        ArtifactInterval.from_interval(result.interval) if result.interval is not None else None
    )
    # ... persisted beside the verdict it licenses, the margin it was judged against, the
    # comparator it was measured against, and the whole-run flag.
    assert read_back.headline_verdict == result.headline_verdict
    assert read_back.materiality_margin == _CONTRACT.materiality_margin
    assert read_back.comparator == result.comparator
    assert read_back.run_incomplete is False
    assert read_back.provenance.arm_roles == dict(harness_result.arm_roles)


def test_artifact_round_trip_example_positive_headline(tmp_path: Path) -> None:
    """A clean grid where consensus beats the baseline persists a positive headline.

    Under Metric_Contract v2 "beats" means CHEAPER on the committed objective: the consensus
    arm's cost sits below the baseline's on every seed, so every paired difference (baseline
    minus consensus) is positive and so is every resampled mean of them.
    """
    scenario = Scenario(name="scenario-0", seed=4001, shock=ShockParams(demand_multiplier=1.0))
    runs_by_pair = {
        (scenario.name, DEFAULT_CONSENSUS_ARM): _completed_runs(
            DEFAULT_CONSENSUS_ARM, [10.0, 10.2, 10.1]
        ),
        (scenario.name, "baseline-0"): _completed_runs("baseline-0", [16.0, 16.1, 15.9]),
    }
    harness_result = _harness_result(
        [scenario], runs_by_pair, (DEFAULT_CONSENSUS_ARM, "baseline-0")
    )

    result = assemble_uplift_result(
        harness_result, _CONTRACT, fidelity=FidelityReport(kl_divergence=0.02, threshold=0.1)
    )
    written = _write_result_artifact(
        tmp_path / "result.json",
        result,
        build_uplift_report(result),
        harness_result=harness_result,
        provenance=_provenance(harness_result, 3),
    )

    payload = json.loads(written.read_text(encoding="utf-8"))
    assert payload["incomplete"] is False
    assert payload["headline_uplift"] > 0.0
    assert UpliftArtifact.read(written).headline_uplift == payload["headline_uplift"]

    # v2: the positive headline is the point of an interval lying wholly above zero, and the
    # persisted verdict is the one the committed rule derives from those bounds.
    interval = payload["interval"]
    assert interval is not None
    assert interval["point"] == payload["headline_uplift"]
    assert interval["low"] > 0.0
    assert payload["headline_verdict"] == interval_verdict(
        interval["low"], interval["high"], margin=_CONTRACT.materiality_margin
    )
