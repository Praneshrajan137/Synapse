"""Property-based test that an unnamed baseline pools every non-consensus arm.

Feature: core-purpose-uplift, Property 8: Unnamed baseline pools all non-consensus arms.

    *For any* arm set with no explicitly designated baseline, the baseline sample set
    for each ``(scenario, KPI)`` equals the concatenation of the completed samples of
    every non-consensus arm for that pair.

    Requirement 2.6: "WHERE no explicit baseline arm is designated, THE Uplift_Harness
    SHALL pool the completed samples of every non-consensus arm into a single
    Baseline_Arm distribution per (scenario, KPI)."

Synthetic ``HarnessResult`` / ``ScenarioRun`` data is constructed directly — no twin
runs, no consensus assembly — so the property is pure, fast, and $0.

**Validates: Requirements 2.6**
"""
from __future__ import annotations

import dataclasses
import math

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from uplift.contract import load_contract
from uplift.fidelity import FidelityReport
from uplift.harness import (
    DEFAULT_CONSENSUS_ARM,
    KPI_FIELDS,
    HarnessResult,
    _pooled_samples,
    _resolve_baseline_arms,
    aggregate_arm,
    assemble_uplift_result,
)
from uplift.interfaces import KpiVector, Scenario, ScenarioRun

from digital_twin.simulation.monte_carlo import ShockParams

# The real, version-controlled metric contract (primary KPI ``fill_rate``).
_CONTRACT = load_contract()
_CONSENSUS_ARM = DEFAULT_CONSENSUS_ARM

# The four pre-registered transparent baseline policies plus an extra unnamed control,
# so the drawn arm set can be any non-empty subset of "everything that is not consensus".
_BASELINE_ARM_NAMES = (
    "par_level_reorder",
    "static_pricing",
    "greedy_routing",
    "no_op_disruption",
    "manual_operator",
)

# The name given to the explicitly-designated merged baseline in the behavioral check.
_MERGED_BASELINE = "merged_baseline"

# Deterministic within-bound fidelity so assembly never reads the live C34 gauge.
_FIDELITY = FidelityReport(kl_divergence=0.02, threshold=0.1)

#: One drawn run: its KPI base value and whether the replicate failed.
_RunSpec = tuple[float, bool]


def _kpi(base: float) -> KpiVector:
    """A KpiVector whose every field is a distinct offset of ``base``.

    Distinct per-field values mean a pooling bug that mixed up KPIs (or arms) shows up
    as a concrete value mismatch rather than an accidental coincidence.
    """
    return KpiVector(
        fill_rate=base,
        spoilage_rate=base + 0.1,
        stockout_rate=base + 0.2,
        avg_delivery_time_min=base + 0.3,
        margin=base + 0.4,
        co2_estimate=base + 0.5,
    )


def _runs(arm: str, specs: list[_RunSpec]) -> list[ScenarioRun]:
    """Build the run list for one ``(scenario, arm)`` pair.

    Failed replicates deliberately still carry a ``KpiVector`` — an adversarial shape:
    pooling must exclude them because ``failed`` is set, not because ``kpis`` is None.
    """
    return [
        ScenarioRun(
            arm=arm,
            seed=index,
            kpis=_kpi(base),
            failed=failed,
            error="injected failure" if failed else None,
        )
        for index, (base, failed) in enumerate(specs)
    ]


def _harness_result(
    arm_names: list[str], grid: dict[tuple[str, str], list[_RunSpec]], n_scenarios: int
) -> HarnessResult:
    """Assemble a synthetic multi-scenario, multi-arm HarnessResult from drawn specs."""
    scenarios = [
        Scenario(name=f"scenario-{i}", seed=i, shock=ShockParams(demand_multiplier=1.0))
        for i in range(n_scenarios)
    ]
    runs_by_pair = {
        (scenario.name, arm): _runs(arm, grid[(scenario.name, arm)])
        for scenario in scenarios
        for arm in arm_names
    }
    return HarnessResult(
        arm_results={
            pair: aggregate_arm(pair[1], runs) for pair, runs in runs_by_pair.items()
        },
        runs_by_pair=runs_by_pair,
        all_runs=[run for runs in runs_by_pair.values() for run in runs],
        results_path=None,
        scenarios=tuple(scenarios),
        arm_names=tuple(arm_names),
    )


def _merge_baselines_explicitly(harness_result: HarnessResult) -> HarnessResult:
    """Rebuild ``harness_result`` with every non-consensus arm merged into one arm.

    The merged arm carries exactly the concatenated runs of the non-consensus arms, in
    arm order, and is then passed to assembly as an *explicitly designated* baseline.
    Implicit pooling must be observationally equivalent to this explicit merge.
    """
    baselines = [arm for arm in harness_result.arm_names if arm != _CONSENSUS_ARM]
    runs_by_pair: dict[tuple[str, str], list[ScenarioRun]] = {}
    for scenario in harness_result.scenarios:
        runs_by_pair[(scenario.name, _CONSENSUS_ARM)] = list(
            harness_result.runs_by_pair[(scenario.name, _CONSENSUS_ARM)]
        )
        runs_by_pair[(scenario.name, _MERGED_BASELINE)] = [
            dataclasses.replace(run, arm=_MERGED_BASELINE)
            for arm in baselines
            for run in harness_result.runs_by_pair[(scenario.name, arm)]
        ]
    return HarnessResult(
        arm_results={
            pair: aggregate_arm(pair[1], runs) for pair, runs in runs_by_pair.items()
        },
        runs_by_pair=runs_by_pair,
        all_runs=[run for runs in runs_by_pair.values() for run in runs],
        results_path=None,
        scenarios=harness_result.scenarios,
        arm_names=(_CONSENSUS_ARM, _MERGED_BASELINE),
    )


@st.composite
def _harness_results(draw: st.DrawFn) -> HarnessResult:
    """A synthetic HarnessResult over a consensus arm plus 1-4 baseline arms.

    Every ``(scenario, arm)`` pair records at least one replicate (so run completeness
    is driven only by the drawn ``failed`` flags), replicates mix completed and failed,
    and the consensus arm may sit at any position in ``arm_names`` so pooling cannot
    rely on it being first.
    """
    baselines = draw(
        st.lists(
            st.sampled_from(_BASELINE_ARM_NAMES), min_size=1, max_size=4, unique=True
        )
    )
    consensus_at = draw(st.integers(min_value=0, max_value=len(baselines)))
    arm_names = list(baselines)
    arm_names.insert(consensus_at, _CONSENSUS_ARM)

    n_scenarios = draw(st.integers(min_value=1, max_value=3))
    bases = st.floats(
        min_value=0.05, max_value=0.95, allow_nan=False, allow_infinity=False
    )
    run_specs = st.lists(
        st.tuples(bases, st.booleans()), min_size=1, max_size=4
    )
    grid = {
        (f"scenario-{i}", arm): draw(run_specs)
        for i in range(n_scenarios)
        for arm in arm_names
    }
    return _harness_result(arm_names, grid, n_scenarios)


@settings(max_examples=150, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(harness_result=_harness_results())
def test_unnamed_baseline_pools_all_non_consensus_arms(
    harness_result: HarnessResult,
) -> None:
    """No designated baseline ⇒ baseline samples = completed samples of every other arm."""
    baseline_arms = _resolve_baseline_arms(harness_result, _CONSENSUS_ARM, None)

    # The resolved baseline is exactly every non-consensus arm, in arm order: none
    # omitted, none duplicated, and the consensus arm never counted as its own control.
    assert baseline_arms == [
        arm for arm in harness_result.arm_names if arm != _CONSENSUS_ARM
    ]
    assert _CONSENSUS_ARM not in baseline_arms

    # Per (scenario, KPI): the pooled baseline sample set equals the concatenation of
    # the completed samples of every non-consensus arm for that pair.
    for scenario in harness_result.scenarios:
        for kpi in KPI_FIELDS:
            pooled = _pooled_samples(
                harness_result, baseline_arms, [scenario.name], kpi
            )
            expected = [
                float(getattr(run.kpis, kpi))
                for arm in baseline_arms
                for run in harness_result.runs_by_pair[(scenario.name, arm)]
                if not run.failed and run.kpis is not None
            ]
            assert pooled == expected, (
                f"pooled baseline for ({scenario.name}, {kpi}) is not the "
                f"concatenation of the non-consensus completed samples"
            )

    # Behavioral equivalence: implicit pooling of N baseline arms is indistinguishable
    # from explicitly designating one arm holding the same concatenated samples.
    implicit = assemble_uplift_result(harness_result, _CONTRACT, fidelity=_FIDELITY)
    explicit = assemble_uplift_result(
        _merge_baselines_explicitly(harness_result),
        _CONTRACT,
        fidelity=_FIDELITY,
        baseline_arm=_MERGED_BASELINE,
    )
    assert implicit.per_scenario == explicit.per_scenario
    assert implicit.per_kpi == explicit.per_kpi
    assert implicit.incomplete == explicit.incomplete
    assert math.isclose(
        implicit.headline_uplift, explicit.headline_uplift, rel_tol=1e-12, abs_tol=1e-12
    )
