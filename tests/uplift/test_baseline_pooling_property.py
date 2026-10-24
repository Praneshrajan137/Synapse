"""Property-based test of what an unnamed baseline pools: every declared baseline, no other.

Feature: core-purpose-uplift, Property 8: Unnamed baseline pools all non-consensus arms.

    *For any* arm set with no explicitly designated baseline, the baseline sample set
    for each ``(scenario, KPI)`` equals the concatenation of the completed samples of
    every non-consensus arm for that pair.

    Requirement 2.6: "WHERE no explicit baseline arm is designated, THE Uplift_Harness
    SHALL pool the completed samples of every non-consensus arm into a single
    Baseline_Arm distribution per (scenario, KPI)."

**Both quoted claims are FALSE by decision.** decision-quality-proof AD-16 (task 15.5) makes an
arm declare its role, so "every non-consensus arm" would now absorb an oracle; Metric_Contract
v2 (task 29.4) pairs replicates on seed, so the pooled sample is no longer a concatenation. The
tag line is kept so the property stays traceable; what is asserted is AD-16's rule:

* an unnamed comparator pools EXACTLY the arms that declared the ``baseline`` role, in
  registration order -- never an ``oracle`` or ``excluded`` arm, never the subject -- and is
  recorded as ``"pooled:"`` plus their sorted names;
* its sample at each seed-paired replicate is the MEAN of the pooled arms' objectives, over the
  replicates that completed in the subject and in every pooled arm;
* so implicit pooling is observationally identical to naming one merged arm that carries
  exactly that per-replicate mean: every verdict, the interval and both completeness flags;
* a named comparator is never pooled, whatever role it declared, and an empty pool is refused
  rather than compared against nothing.

Synthetic ``HarnessResult`` / ``ScenarioRun`` data is constructed directly — no twin
runs, no consensus assembly — so the property is pure, fast, and $0.

**Validates: Requirements 2.6**
"""
from __future__ import annotations

import statistics

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from digital_twin.simulation.monte_carlo import ShockParams
from uplift.contract import load_contract
from uplift.fidelity import FidelityReport
from uplift.harness import (
    DEFAULT_CONSENSUS_ARM,
    POOLED_COMPARATOR_PREFIX,
    HarnessResult,
    _paired_objectives,
    _resolve_baseline_arms,
    aggregate_arm,
    assemble_uplift_result,
)
from uplift.interfaces import ArmRole, KpiVector, Scenario, ScenarioRun

# The real, version-controlled metric contract (v2: the committed objective is judged).
_CONTRACT = load_contract()
_CONSENSUS_ARM = DEFAULT_CONSENSUS_ARM

# The four pre-registered transparent baseline policies plus an extra control, so the drawn
# baseline set can be any non-empty subset of them.
_BASELINE_ARM_NAMES = (
    "par_level_reorder",
    "static_pricing",
    "greedy_routing",
    "no_op_disruption",
    "manual_operator",
)

# Arms registered beside the contrast, each declaring a role pooling must never absorb.
_OUTSIDE_ARM_NAMES = ("oracle_arm", "shadow_arm")
_OUTSIDE_ROLES: tuple[ArmRole, ...] = ("oracle", "excluded")

# The name given to the explicitly-designated merged baseline in the behavioral check.
_MERGED_BASELINE = "merged_baseline"

# The merged arm's non-objective KPI fields: a value no drawn field takes, so only the
# objective is carried across the merge and a comparator reading any other field diverges.
_MERGED_SECONDARY = -1.0

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
        avg_on_hand_units=base + 0.6,
        objective=base + 0.7,
    )


def _merged_kpi(objective: float) -> KpiVector:
    """The merged arm's vector: the pooled objective and nothing else carried over."""
    return KpiVector(
        fill_rate=_MERGED_SECONDARY,
        spoilage_rate=_MERGED_SECONDARY,
        stockout_rate=_MERGED_SECONDARY,
        avg_delivery_time_min=_MERGED_SECONDARY,
        margin=_MERGED_SECONDARY,
        co2_estimate=_MERGED_SECONDARY,
        avg_on_hand_units=_MERGED_SECONDARY,
        objective=objective,
    )


def _runs(arm: str, specs: list[_RunSpec]) -> list[ScenarioRun]:
    """One run per replicate seed ``0..len(specs) - 1``, the seeds every arm of a scenario shares.

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


def _from_runs(
    runs_by_pair: dict[tuple[str, str], list[ScenarioRun]],
    scenarios: tuple[Scenario, ...],
    arm_roles: dict[str, ArmRole],
) -> HarnessResult:
    """A HarnessResult registering every arm, in ``arm_roles`` order, with its role."""
    return HarnessResult(
        arm_results={
            pair: aggregate_arm(pair[1], runs) for pair, runs in runs_by_pair.items()
        },
        runs_by_pair=runs_by_pair,
        all_runs=[run for runs in runs_by_pair.values() for run in runs],
        results_path=None,
        scenarios=scenarios,
        arm_names=tuple(arm_roles),
        arm_roles=arm_roles,
    )


def _scenarios(count: int) -> tuple[Scenario, ...]:
    return tuple(
        Scenario(name=f"scenario-{i}", seed=i, shock=ShockParams(demand_multiplier=1.0))
        for i in range(count)
    )


def _completed_objectives(
    harness_result: HarnessResult, scenario_name: str, arm: str
) -> dict[int, float]:
    """Each completed replicate's objective for one pair, keyed by seed, read off the runs."""
    return {
        run.seed: run.kpis.objective
        for run in harness_result.runs_by_pair[(scenario_name, arm)]
        if not run.failed and run.kpis is not None
    }


def _expected_pairs(
    harness_result: HarnessResult, scenario_name: str, pool: list[str]
) -> tuple[list[float], list[float]]:
    """The seed-paired (subject, pooled comparator) samples, derived from the runs directly.

    A replicate pairs only where the subject and EVERY pooled arm completed it, and the pooled
    sample there is the mean of the pooled arms' objectives, in ascending seed order.
    """
    subject = _completed_objectives(harness_result, scenario_name, _CONSENSUS_ARM)
    pooled = [_completed_objectives(harness_result, scenario_name, arm) for arm in pool]
    shared = sorted(set(subject).intersection(*pooled))
    return (
        [subject[seed] for seed in shared],
        [statistics.fmean(arm_map[seed] for arm_map in pooled) for seed in shared],
    )


def _merge_pool_explicitly(harness_result: HarnessResult, pool: list[str]) -> HarnessResult:
    """Rebuild ``harness_result`` with the pooled arms replaced by ONE named arm.

    At each replicate seed the merged arm completes iff every pooled arm completed there, and
    then carries exactly the mean of their objectives; otherwise it records a failure. Every
    arm outside the pool -- the subject and the oracle/excluded arms -- is kept unchanged.
    Implicit pooling must be observationally equivalent to naming this arm.
    """
    runs_by_pair: dict[tuple[str, str], list[ScenarioRun]] = {}
    kept = [arm for arm in harness_result.arm_names if arm not in pool]
    for scenario in harness_result.scenarios:
        for arm in kept:
            runs_by_pair[(scenario.name, arm)] = list(
                harness_result.runs_by_pair[(scenario.name, arm)]
            )
        merged: list[ScenarioRun] = []
        pooled_runs = [harness_result.runs_by_pair[(scenario.name, arm)] for arm in pool]
        for replicate in zip(*pooled_runs, strict=True):
            objectives = [
                run.kpis.objective
                for run in replicate
                if not run.failed and run.kpis is not None
            ]
            seed = replicate[0].seed
            if len(objectives) == len(replicate):
                merged.append(
                    ScenarioRun(
                        arm=_MERGED_BASELINE,
                        seed=seed,
                        kpis=_merged_kpi(statistics.fmean(objectives)),
                        failed=False,
                        error=None,
                    )
                )
            else:
                merged.append(
                    ScenarioRun(
                        arm=_MERGED_BASELINE,
                        seed=seed,
                        kpis=None,
                        failed=True,
                        error="a pooled arm failed this replicate",
                    )
                )
        runs_by_pair[(scenario.name, _MERGED_BASELINE)] = merged

    arm_roles: dict[str, ArmRole] = {arm: harness_result.arm_roles[arm] for arm in kept}
    arm_roles[_MERGED_BASELINE] = "baseline"
    return _from_runs(runs_by_pair, harness_result.scenarios, arm_roles)


@st.composite
def _harness_results(draw: st.DrawFn) -> HarnessResult:
    """A synthetic HarnessResult over a consensus arm, 1-4 baselines and 0-2 outside arms.

    Every ``(scenario, arm)`` pair records the scenario's replicate count (so every arm runs
    the same replicate seeds, as ``UpliftHarness.run`` guarantees), replicates mix completed
    and failed, and the registration order is a random permutation, so pooling can rely
    neither on the subject's position nor on the baselines coming first.
    """
    baselines = draw(
        st.lists(
            st.sampled_from(_BASELINE_ARM_NAMES), min_size=1, max_size=4, unique=True
        )
    )
    outside = draw(
        st.lists(st.sampled_from(_OUTSIDE_ARM_NAMES), min_size=0, max_size=2, unique=True)
    )
    registrations: list[tuple[str, ArmRole]] = [(_CONSENSUS_ARM, "consensus")]
    registrations += [(arm, "baseline") for arm in baselines]
    registrations += [(arm, draw(st.sampled_from(_OUTSIDE_ROLES))) for arm in outside]
    arm_roles: dict[str, ArmRole] = dict(draw(st.permutations(registrations)))

    scenarios = _scenarios(draw(st.integers(min_value=1, max_value=3)))
    bases = st.floats(
        min_value=0.05, max_value=0.95, allow_nan=False, allow_infinity=False
    )
    runs_by_pair: dict[tuple[str, str], list[ScenarioRun]] = {}
    for scenario in scenarios:
        replicates = draw(st.integers(min_value=1, max_value=4))
        run_specs = st.lists(
            st.tuples(bases, st.booleans()), min_size=replicates, max_size=replicates
        )
        for arm in arm_roles:
            runs_by_pair[(scenario.name, arm)] = _runs(arm, draw(run_specs))
    return _from_runs(runs_by_pair, scenarios, arm_roles)


@settings(deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(harness_result=_harness_results())
def test_an_unnamed_baseline_pools_exactly_the_declared_baseline_arms(
    harness_result: HarnessResult,
) -> None:
    """No designated baseline => the comparator is every declared baseline and nothing else."""
    roles = harness_result.arm_roles
    pool = _resolve_baseline_arms(harness_result, _CONSENSUS_ARM, None)

    # The pool is exactly the declared baselines, in registration order: none omitted,
    # none duplicated, and the consensus arm never counted as its own control.
    assert pool == [arm for arm in harness_result.arm_names if roles[arm] == "baseline"]
    assert pool
    assert _CONSENSUS_ARM not in pool
    # The AD-16 clause the rule exists for: no oracle- or excluded-role arm is absorbed.
    assert all(roles[arm] not in _OUTSIDE_ROLES for arm in pool)

    # Per scenario: the pooled sample at each seed-paired replicate is the mean of the pooled
    # arms' objectives, over the replicates the subject and every pooled arm completed.
    for scenario in harness_result.scenarios:
        assert _paired_objectives(
            harness_result, [scenario.name], _CONSENSUS_ARM, pool
        ) == _expected_pairs(harness_result, scenario.name, pool), (
            f"pooled comparator for {scenario.name} is not the per-replicate mean of {pool}"
        )

    # A named comparator is never pooled, whatever role it declared.
    for arm in [name for name in harness_result.arm_names if name != _CONSENSUS_ARM]:
        assert _resolve_baseline_arms(harness_result, _CONSENSUS_ARM, arm) == [arm]

    # Behavioral equivalence: implicit pooling is indistinguishable from explicitly naming
    # one arm that carries the same per-replicate mean -- exactly, not approximately,
    # because both contrasts are computed from identical paired samples.
    implicit = assemble_uplift_result(harness_result, _CONTRACT, fidelity=_FIDELITY)
    explicit = assemble_uplift_result(
        _merge_pool_explicitly(harness_result, pool),
        _CONTRACT,
        fidelity=_FIDELITY,
        baseline_arm=_MERGED_BASELINE,
    )
    assert implicit.comparator == POOLED_COMPARATOR_PREFIX + ",".join(sorted(pool))
    assert explicit.comparator == _MERGED_BASELINE
    assert implicit.per_scenario == explicit.per_scenario
    assert implicit.per_kpi == explicit.per_kpi
    assert implicit.incomplete == explicit.incomplete
    assert implicit.run_incomplete == explicit.run_incomplete
    assert implicit.interval == explicit.interval
    assert implicit.headline_verdict == explicit.headline_verdict
    assert implicit.headline_uplift == explicit.headline_uplift


def _one_completed_replicate_per_arm(arm_roles: dict[str, ArmRole]) -> HarnessResult:
    scenarios = _scenarios(1)
    runs_by_pair = {
        (scenario.name, arm): _runs(arm, [(0.5, False)])
        for scenario in scenarios
        for arm in arm_roles
    }
    return _from_runs(runs_by_pair, scenarios, arm_roles)


def test_an_empty_pool_is_refused_rather_than_compared_against_nothing() -> None:
    """With no baseline-role arm beside the subject there is nothing to pool: refused."""
    harness_result = _one_completed_replicate_per_arm(
        {_CONSENSUS_ARM: "consensus", "oracle_arm": "oracle", "shadow_arm": "excluded"}
    )

    with pytest.raises(ValueError, match="no baseline-role arm"):
        _resolve_baseline_arms(harness_result, _CONSENSUS_ARM, None)
    with pytest.raises(ValueError, match="no baseline-role arm"):
        assemble_uplift_result(harness_result, _CONTRACT, fidelity=_FIDELITY)


def test_the_subject_is_never_pooled_even_when_it_declared_the_baseline_role() -> None:
    """Pooling excludes the subject by NAME, so a baseline subject is never its own control."""
    subject = "par_level_reorder"
    harness_result = _one_completed_replicate_per_arm(
        {subject: "baseline", "static_pricing": "baseline", "oracle_arm": "oracle"}
    )
    assert _resolve_baseline_arms(harness_result, subject, None) == ["static_pricing"]

    alone = _one_completed_replicate_per_arm({subject: "baseline", "oracle_arm": "oracle"})
    with pytest.raises(ValueError, match="no baseline-role arm"):
        _resolve_baseline_arms(alone, subject, None)
