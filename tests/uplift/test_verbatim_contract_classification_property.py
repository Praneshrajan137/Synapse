"""Property-based test that result assembly applies the contract rule verbatim.

Feature: core-purpose-uplift, Property 9: Assembly classifies pairs by the contract rule
verbatim.

    *For any* complete ``(scenario, primary KPI)`` pair, the assembled ``per_scenario``
    outcome equals ``MetricContract.classify(consensus_samples, baseline_samples, kpi)``
    computed directly — the assembly substitutes no alternative rule.

    Requirement 2.7: "THE Uplift_Harness SHALL classify each scenario pair using the
    Metric_Contract decision rule exactly as declared, without substituting an
    alternative rule."

Two independent things are pinned here:

1. **Verbatim outcome.** For every pair whose compared arms completed *every* replicate
   (the "complete pair" precondition — a pair with at least one failed replicate resolves
   to ``TIE_INCONCLUSIVE`` by R2.5, design C5, so it is out of this property's scope), the
   assembled outcome equals ``classify`` recomputed directly from the raw
   ``runs_by_pair`` samples, gathered here without using any harness helper.
2. **The rule comes from the passed contract, not from assembly.** The drawn contract is
   the real pre-registered one *or* a mutated variant (tightened ``alpha``, raised
   ``mde``, flipped direction). Assembly must track whichever contract it is handed, so
   it cannot be carrying its own hardcoded thresholds or direction logic.

Synthetic ``HarnessResult`` / ``ScenarioRun`` data is built directly — no twin runs, no
consensus assembly — so the property is pure, fast, network-free, and $0.

**Validates: Requirements 2.7**
"""
from __future__ import annotations

import dataclasses

from hypothesis import HealthCheck, event, given, settings
from hypothesis import strategies as st

from uplift.contract import MetricContract, load_contract
from uplift.fidelity import FidelityReport
from uplift.harness import (
    DEFAULT_CONSENSUS_ARM,
    HarnessResult,
    aggregate_arm,
    assemble_uplift_result,
)
from uplift.interfaces import Direction, KpiVector, Scenario, ScenarioRun

from digital_twin.simulation.monte_carlo import ShockParams

# The real, version-controlled metric contract (primary KPI ``fill_rate``, higher better).
_CONTRACT = load_contract()
_CONSENSUS_ARM = DEFAULT_CONSENSUS_ARM

# The transparent baseline policies; the drawn arm set is consensus plus a non-empty
# subset of these, so the baseline is pooled across one *or several* arms.
_BASELINE_ARM_NAMES = ("par_level_reorder", "static_pricing", "greedy_routing")

# Deterministic within-bound fidelity so assembly never reads the live C34 gauge.
_FIDELITY = FidelityReport(kl_divergence=0.02, threshold=0.1)

#: One drawn replicate: its ``fill_rate`` value and whether the replicate failed.
_RunSpec = tuple[float, bool]


def _contract_variants() -> tuple[MetricContract, ...]:
    """The real contract plus mutations of each rule input (alpha, MDE, direction).

    Assembly is handed one of these; because each variant changes the *declared* rule,
    an assembly that hardcoded thresholds or the improvement direction instead of
    applying the passed contract verbatim would disagree with ``classify``.
    """
    kpi = next(iter(_CONTRACT.primary_kpis))
    flipped = (
        Direction.LOWER_IS_BETTER
        if _CONTRACT.primary_kpis[kpi] is Direction.HIGHER_IS_BETTER
        else Direction.HIGHER_IS_BETTER
    )
    return (
        _CONTRACT,
        dataclasses.replace(_CONTRACT, alpha=1e-6),  # almost nothing is significant
        dataclasses.replace(_CONTRACT, mde={**_CONTRACT.mde, kpi: 50.0}),  # unreachable MDE
        dataclasses.replace(_CONTRACT, mde={**_CONTRACT.mde, kpi: 0.0}),  # any effect
        dataclasses.replace(
            _CONTRACT, primary_kpis={**_CONTRACT.primary_kpis, kpi: flipped}
        ),
    )


_CONTRACTS = _contract_variants()


def _kpi(fill_rate: float) -> KpiVector:
    """A ``KpiVector`` varying only ``fill_rate``; the other fields are fixed constants."""
    return KpiVector(
        fill_rate=fill_rate,
        spoilage_rate=0.0,
        stockout_rate=0.0,
        avg_delivery_time_min=1.0,
        margin=1.0,
        co2_estimate=1.0,
    )


def _runs(arm: str, specs: list[_RunSpec]) -> list[ScenarioRun]:
    """Build one ``(scenario, arm)`` pair's replicate runs from drawn specs.

    A failed replicate deliberately still carries KPIs — an adversarial shape: a failed
    replicate must be recognised by its ``failed`` flag, not by ``kpis is None``.
    """
    return [
        ScenarioRun(
            arm=arm,
            seed=index,
            kpis=_kpi(fill_rate),
            failed=failed,
            error="injected failure" if failed else None,
        )
        for index, (fill_rate, failed) in enumerate(specs)
    ]


def _harness_result(
    arm_names: list[str],
    scenario_names: list[str],
    grid: dict[tuple[str, str], list[_RunSpec]],
) -> HarnessResult:
    """Assemble a synthetic multi-scenario, multi-arm ``HarnessResult`` from drawn specs."""
    scenarios = [
        Scenario(name=name, seed=index, shock=ShockParams(demand_multiplier=2.0))
        for index, name in enumerate(scenario_names)
    ]
    runs_by_pair = {
        (name, arm): _runs(arm, grid[(name, arm)])
        for name in scenario_names
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


# Replicate values are drawn around a per-pair centre with a per-pair spread, so
# consensus and baseline distributions can separate far enough to reach SYNAPSE_WINS /
# BASELINE_WINS, or overlap into TIE_INCONCLUSIVE.
_centres = st.floats(min_value=0.05, max_value=0.95, allow_nan=False, allow_infinity=False)
_spreads = st.floats(min_value=0.0, max_value=0.05, allow_nan=False, allow_infinity=False)
_failed_flags = st.integers(min_value=0, max_value=7).map(lambda i: i == 0)


@st.composite
def _pair_specs(draw: st.DrawFn, *, allow_failures: bool) -> list[_RunSpec]:
    """5-9 replicates spread around a drawn centre.

    ``allow_failures`` is drawn once per example: half the examples record an all-complete
    grid (so complete pairs — Property 9's precondition — are exercised in quantity) and
    half sprinkle failed replicates (so the property is also checked on grids where some
    pairs are excluded, and the excluded ones cannot mask a wrong classification).
    """
    n = draw(st.integers(min_value=5, max_value=9))
    centre = draw(_centres)
    spread = draw(_spreads)
    return [
        (centre + spread * index, draw(_failed_flags) if allow_failures else False)
        for index in range(n)
    ]


@st.composite
def _cases(draw: st.DrawFn) -> tuple[HarnessResult, MetricContract]:
    """A synthetic ``HarnessResult`` over consensus + 1-3 baseline arms, and a contract."""
    baselines = draw(
        st.lists(st.sampled_from(_BASELINE_ARM_NAMES), min_size=1, max_size=3, unique=True)
    )
    consensus_at = draw(st.integers(min_value=0, max_value=len(baselines)))
    arm_names = list(baselines)
    arm_names.insert(consensus_at, _CONSENSUS_ARM)

    scenario_names = [
        f"scenario-{i}" for i in range(draw(st.integers(min_value=1, max_value=2)))
    ]
    allow_failures = draw(st.booleans())
    grid = {
        (name, arm): draw(_pair_specs(allow_failures=allow_failures))
        for name in scenario_names
        for arm in arm_names
    }
    contract = draw(st.sampled_from(_CONTRACTS))
    return _harness_result(arm_names, scenario_names, grid), contract


def _raw_samples(
    harness_result: HarnessResult, scenario_name: str, arms: list[str], kpi: str
) -> list[float]:
    """Completed samples for ``arms`` on one scenario, read straight from the raw runs.

    Deliberately does not call ``HarnessResult.kpi_samples`` / ``_pooled_samples``: the
    expected classification must be computed from the recorded runs independently of the
    helpers assembly itself uses.
    """
    return [
        float(getattr(run.kpis, kpi))
        for arm in arms
        for run in harness_result.runs_by_pair[(scenario_name, arm)]
        if not run.failed and run.kpis is not None
    ]


def _pair_complete(harness_result: HarnessResult, scenario_name: str, arm: str) -> bool:
    """True iff the ``(scenario, arm)`` pair recorded replicates and none of them failed.

    This is Property 9's "complete pair" precondition under R2.5: a pair with at least
    one failed replicate is forced to ``TIE_INCONCLUSIVE`` by assembly regardless of the
    contract, so it is excluded from the verbatim comparison.
    """
    runs = harness_result.runs_by_pair.get((scenario_name, arm), [])
    return bool(runs) and not any(run.failed for run in runs)


@settings(max_examples=150, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(case=_cases())
def test_assembly_classifies_pairs_by_the_contract_rule_verbatim(
    case: tuple[HarnessResult, MetricContract],
) -> None:
    """Complete pairs carry exactly ``contract.classify``'s outcome on the same samples."""
    harness_result, contract = case
    baseline_arms = [arm for arm in harness_result.arm_names if arm != _CONSENSUS_ARM]

    result = assemble_uplift_result(
        harness_result, contract, fidelity=_FIDELITY, consensus_arm=_CONSENSUS_ARM
    )

    scenario_names = [scenario.name for scenario in harness_result.scenarios]

    # Every (scenario, primary KPI) pair is classified exactly once — no pair is dropped,
    # so the verbatim check below covers the whole reported grid.
    assert set(result.per_scenario) == {
        (name, kpi) for name in scenario_names for kpi in contract.primary_kpis
    }

    run_complete = True
    for name in scenario_names:
        complete = all(
            _pair_complete(harness_result, name, arm)
            for arm in (_CONSENSUS_ARM, *baseline_arms)
        )
        run_complete = run_complete and complete
        for kpi in contract.primary_kpis:
            consensus = _raw_samples(harness_result, name, [_CONSENSUS_ARM], kpi)
            baseline = _raw_samples(harness_result, name, baseline_arms, kpi)
            if not (complete and consensus and baseline):
                # Out of scope for Property 9 (R2.5 forces TIE_INCONCLUSIVE here); that
                # behavior is pinned by Property 5.
                event("pair: incomplete (out of scope)")
                continue
            expected = contract.classify(consensus, baseline, kpi)
            event(f"complete pair outcome: {expected.value}")
            assert result.per_scenario[(name, kpi)] == expected, (
                f"({name}, {kpi}) was assembled as "
                f"{result.per_scenario[(name, kpi)]} but the declared contract rule "
                f"classifies the same samples as {expected}"
            )

    # A fully complete run's pooled per-KPI verdict is likewise the contract's own
    # verdict on the pooled samples — assembly adds no cross-scenario adjudication.
    if run_complete:
        for kpi in contract.primary_kpis:
            consensus = [
                value
                for name in scenario_names
                for value in _raw_samples(harness_result, name, [_CONSENSUS_ARM], kpi)
            ]
            baseline = [
                value
                for name in scenario_names
                for value in _raw_samples(harness_result, name, baseline_arms, kpi)
            ]
            if consensus and baseline:
                assert result.per_kpi[kpi] == contract.classify(consensus, baseline, kpi)
