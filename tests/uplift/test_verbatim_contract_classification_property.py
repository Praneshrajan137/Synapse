"""Property-based test that result assembly applies the contract rule verbatim.

Feature: core-purpose-uplift, Property 9: Assembly classifies pairs by the contract rule
verbatim.

    *For any* complete ``(scenario, primary KPI)`` pair, the assembled ``per_scenario``
    outcome equals ``MetricContract.classify(consensus_samples, baseline_samples, kpi)``
    computed directly — the assembly substitutes no alternative rule.

    Requirement 2.7: "THE Uplift_Harness SHALL classify each scenario pair using the
    Metric_Contract decision rule exactly as declared, without substituting an
    alternative rule."

Carried to Metric_Contract v2 (decision-quality-proof task 29.4). The claim holds as stated;
what ``consensus_samples`` and ``baseline_samples`` mean is v2's. The judged KPI is the
``objective``, and the two samples are PAIRED ON SEED: at every replicate seed that completed in
the consensus arm and in every comparator arm, the consensus objective beside the MEAN of the
comparator arms' objectives at that seed (AD-16's pooled comparator; with one comparator arm,
that arm's own objective). Two independent things are pinned here:

1. **Verbatim outcome.** For every pair whose compared arms completed *every* replicate
   (the "complete pair" precondition — a pair with at least one failed replicate resolves
   to ``TIE_INCONCLUSIVE`` by R2.5, design C5, so it is out of this property's scope), the
   assembled outcome equals ``classify`` recomputed directly from the raw
   ``runs_by_pair`` samples, paired on seed here without using any harness helper.
2. **The rule comes from the passed contract, not from assembly.** The drawn contract is
   the real pre-registered one *or* a variant of a rule input v2 still lets vary: a looser
   confidence level (``alpha = 0.5``), a margin no generated gain can clear, and a margin almost
   any gain clears. Assembly must track whichever contract it is handed, so it cannot be
   carrying its own hardcoded margin or confidence level. v1's other two variants no longer
   exist to draw: construction refuses a margin of ``0.0`` and any direction but
   lower-is-better for the objective (pinned in ``test_contract_schema.py``).

Synthetic ``HarnessResult`` / ``ScenarioRun`` data is built directly — no twin runs, no
consensus assembly — so the property is pure, fast, network-free, and $0. Budget inherited
from the root ``conftest.py`` profile; no ``max_examples`` literal.

**Validates: Requirements 2.7**
"""
from __future__ import annotations

import dataclasses
import statistics

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
from uplift.interfaces import ArmRole, KpiVector, Scenario, ScenarioRun

from digital_twin.simulation.monte_carlo import ShockParams

# The real, version-controlled metric contract (v2: the objective, lower is better, judged by
# its paired interval against the committed materiality margin).
_CONTRACT = load_contract()
_CONSENSUS_ARM = DEFAULT_CONSENSUS_ARM
_MARGIN = _CONTRACT.materiality_margin

# The transparent baseline policies; the drawn arm set is consensus plus a non-empty
# subset of these, so the baseline is pooled across one *or several* arms.
_BASELINE_ARM_NAMES = ("par_level_reorder", "static_pricing", "greedy_routing")

# Deterministic within-bound fidelity so assembly never reads the live C34 gauge.
_FIDELITY = FidelityReport(kl_divergence=0.02, threshold=0.1)

#: One drawn replicate: its ``objective`` value and whether the replicate failed.
_RunSpec = tuple[float, bool]


def _contract_variants() -> tuple[MetricContract, ...]:
    """The real contract plus mutations of each rule input v2 lets vary (alpha, the margin).

    Assembly is handed one of these; because each variant changes the *declared* rule,
    an assembly that hardcoded the confidence level or the margin instead of applying the
    passed contract verbatim would disagree with ``classify``. The drawn gains stay within
    five margins (see ``_pair_specs``), so ``100 m`` is out of reach.
    """
    kpi = _CONTRACT.objective_kpi
    return (
        _CONTRACT,
        dataclasses.replace(_CONTRACT, alpha=0.5),  # a 50% interval: narrower, more decisive
        dataclasses.replace(_CONTRACT, mde={kpi: 100.0 * _MARGIN}),  # no gain is material
        dataclasses.replace(_CONTRACT, mde={kpi: 1e-9 * _MARGIN}),  # almost any gain is
    )


_CONTRACTS = _contract_variants()


def _kpi(objective: float) -> KpiVector:
    """A ``KpiVector`` varying only ``objective``; the other fields are fixed constants."""
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


def _runs(arm: str, specs: list[_RunSpec]) -> list[ScenarioRun]:
    """Build one ``(scenario, arm)`` pair's replicate runs from drawn specs.

    A failed replicate deliberately still carries KPIs — an adversarial shape: a failed
    replicate must be recognised by its ``failed`` flag, not by ``kpis is None``.
    Replicate ``index`` runs at seed ``index`` in every arm, which is what pairs them.
    """
    return [
        ScenarioRun(
            arm=arm,
            seed=index,
            kpis=_kpi(objective),
            failed=failed,
            error="injected failure" if failed else None,
        )
        for index, (objective, failed) in enumerate(specs)
    ]


def _role(arm: str) -> ArmRole:
    """The role each drawn arm registers with: the subject, or a poolable baseline."""
    return "consensus" if arm == _CONSENSUS_ARM else "baseline"


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
        arm_roles={arm: _role(arm) for arm in arm_names},
    )


#: The consensus-side cost level every pair's centre is drawn above.
_BASE_COST = 10.0

# Replicate objectives are drawn around a per-pair centre with a per-pair spread, both in
# units of the committed margin, so the seed-paired gains of consensus over the pooled
# baselines land on every side of 0 and of the margin: wins, sub-margin gains, inconclusive
# pairs and baseline wins all occur.
_centres = st.floats(
    min_value=0.0, max_value=3.0, allow_nan=False, allow_infinity=False
).map(lambda k: _BASE_COST + k * _MARGIN)
_spreads = st.floats(
    min_value=0.0, max_value=0.25, allow_nan=False, allow_infinity=False
).map(lambda k: k * _MARGIN)
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


def _objectives_by_seed(
    harness_result: HarnessResult, scenario_name: str, arm: str
) -> dict[int, float]:
    """One arm's completed objectives on one scenario, keyed by replicate seed.

    Read straight from the recorded runs; every replicate drawn here has a distinct seed.
    """
    by_seed: dict[int, float] = {}
    for run in harness_result.runs_by_pair[(scenario_name, arm)]:
        if not run.failed and run.kpis is not None:
            by_seed[run.seed] = run.kpis.objective
    return by_seed


def _seed_paired_samples(
    harness_result: HarnessResult, scenario_name: str, comparators: list[str]
) -> tuple[list[float], list[float]]:
    """``(consensus, comparator)`` objectives paired on seed, read straight from the raw runs.

    Deliberately does not call ``HarnessResult.kpi_samples`` / ``_paired_objectives``: the
    expected classification must be computed from the recorded runs independently of the
    helpers assembly itself uses. A seed is paired only when it completed in the consensus
    arm and in EVERY comparator arm, and the comparator's sample there is the mean of those
    arms' objectives.
    """
    consensus = _objectives_by_seed(harness_result, scenario_name, _CONSENSUS_ARM)
    pooled = [_objectives_by_seed(harness_result, scenario_name, arm) for arm in comparators]
    seeds = sorted(set(consensus).intersection(*pooled))
    return (
        [consensus[seed] for seed in seeds],
        [statistics.fmean([by_seed[seed] for by_seed in pooled]) for seed in seeds],
    )


def _pair_complete(harness_result: HarnessResult, scenario_name: str, arm: str) -> bool:
    """True iff the ``(scenario, arm)`` pair recorded replicates and none of them failed.

    This is Property 9's "complete pair" precondition under R2.5: a pair with at least
    one failed replicate is forced to ``TIE_INCONCLUSIVE`` by assembly regardless of the
    contract, so it is excluded from the verbatim comparison.
    """
    runs = harness_result.runs_by_pair.get((scenario_name, arm), [])
    return bool(runs) and not any(run.failed for run in runs)


@settings(deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(case=_cases())
def test_assembly_classifies_pairs_by_the_contract_rule_verbatim(
    case: tuple[HarnessResult, MetricContract],
) -> None:
    """Complete pairs carry exactly ``contract.classify``'s outcome on the same samples."""
    harness_result, contract = case
    baseline_arms = [arm for arm in harness_result.arm_names if arm != _CONSENSUS_ARM]
    kpi = contract.objective_kpi

    result = assemble_uplift_result(
        harness_result, contract, fidelity=_FIDELITY, consensus_arm=_CONSENSUS_ARM
    )

    scenario_names = [scenario.name for scenario in harness_result.scenarios]

    # Every (scenario, primary KPI) pair is classified exactly once — no pair is dropped,
    # so the verbatim check below covers the whole reported grid.
    assert set(result.per_scenario) == {
        (name, primary) for name in scenario_names for primary in contract.primary_kpis
    }
    assert set(contract.primary_kpis) == {kpi}

    run_complete = True
    for name in scenario_names:
        complete = all(
            _pair_complete(harness_result, name, arm)
            for arm in (_CONSENSUS_ARM, *baseline_arms)
        )
        run_complete = run_complete and complete
        consensus, comparator = _seed_paired_samples(harness_result, name, baseline_arms)
        if not (complete and consensus):
            # Out of scope for Property 9 (R2.5 forces TIE_INCONCLUSIVE here); that
            # behavior is pinned by Property 5.
            event("pair: incomplete (out of scope)")
            continue
        expected = contract.classify(consensus, comparator, kpi)
        event(f"complete pair outcome: {expected.value}")
        assert result.per_scenario[(name, kpi)] == expected, (
            f"({name}, {kpi}) was assembled as "
            f"{result.per_scenario[(name, kpi)]} but the declared contract rule "
            f"classifies the same samples as {expected}"
        )

    # A fully complete run's pooled per-KPI verdict is likewise the contract's own
    # verdict on every seed-paired replicate of every scenario — assembly adds no
    # cross-scenario adjudication.
    if run_complete:
        consensus_all: list[float] = []
        comparator_all: list[float] = []
        for name in scenario_names:
            consensus, comparator = _seed_paired_samples(harness_result, name, baseline_arms)
            consensus_all.extend(consensus)
            comparator_all.extend(comparator)
        assert consensus_all
        assert result.per_kpi[kpi] == contract.classify(consensus_all, comparator_all, kpi)
