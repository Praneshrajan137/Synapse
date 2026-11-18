# Feature: decision-quality-proof, Property 97: The E5 suite measures arm E as B-prime tuned it,
# on seeds disjoint from its tuning
"""The E5 suite measures arm E as checkpoint B-prime tuned it, on seeds disjoint from its tuning.

Feature: decision-quality-proof, session 12 (wave 2; task 22.1's code half; R2.1, R2.5, R7.1,
R7.14, R7.19, R7.20, R7.21). Subjects: ``uplift/bprime_record.py`` (the record, read or
refused), ``uplift/e5_suite.py`` (scenario, seeds, arms, loop, and the reproduction of B-prime's
comparator, API2 amendment 2), ``uplift/policies.py`` (``NamedPolicy``), the harness's
session-12 surface (``Scenario.world``, ``LoopConfig.levers``, ``RunScoped``, ``DecisionCounts``,
``run_arm_on_seeds``, ``decision_count_totals``), ``python -m uplift.cli --suite e5-primary``,
and that command's R7.21 pathway-probe step with ``uplift/dispatch.py``'s refusal record (wave 3,
finding 109: the E5 job itself writes the probe's report, or why it has none).

**Fast and pure.** Records are built in memory, or written with the real builder into a fake
repository under ``tmp_path`` whose physics files are one-line fixtures -- so the digest is
the real :func:`uplift.power.source_set_digest` over a tree whose every byte the test controls.
Every refusal is proven by construction: the defect is injected, and the refusal names it. Some
clauses construct and start an engine without advancing it (``_build_twin``, ``stocked_skus``,
arm O's SKU count), which processes no simulation event. The reproduction is priced by an
injected cost, so no twin runs; the CLI clauses also replace the harness, the probe's fresh arm,
its sampler and the probe itself with stand-ins, and a refused invocation's stand-ins fail if
they are ever reached, so "refused before any replicate runs" is a fact, not a hope.

**Slow (``@pytest.mark.slow``, CI only), six clauses that drive the real SimPy twin:**

* (a) arm E's objective under the harness EQUALS the regret comparator's for the same engine
  physics, at three E5 seeds, compared with ``==`` on floats -- the claim that E5 measures the
  arm B-prime tuned, under the physics B-prime tuned it under;
* (b) ``run_arm_on_seeds`` uses each given seed as the twin seed;
* (c) a ``RunScoped`` policy's tally reaches ``ScenarioRun.decision_counts``, a failing run
  records ``None``, and the run is closed either way;
* (d) under ``reorders_only`` a price the policy sets is never applied;
* (e) ``production_arm_cost`` at one seed is the committed objective of a ``run_single_arm``
  replicate, its five reads taken here;
* (f) arm O as the positive control drives it through the harness EQUALS arm O as the B-prime
  reproduction prices it, at the positive control's first three seeds -- the premise of the
  R6.3 agreement rule, which compares the two instruments' E - O (finding 117).

Budget inherited from the root ``conftest.py`` profile: no example count is set or asserted.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import math
import pickle
from typing import TYPE_CHECKING, Final, Literal, cast

import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError

import uplift.cli as cli
import uplift.e5_suite as e5_suite
from digital_twin.config import TwinConfig
from digital_twin.simulation.monte_carlo import MIN_SCENARIOS, ShockParams
from digital_twin.simulation.policy import comparator_restock_threshold
from digital_twin.simulation.world import load_world
from uplift.bprime_record import (
    BPRIME_ARTIFACT_PATH,
    BPRIME_CELL,
    BPRIME_PHYSICS_SET,
    BPRIME_PROVENANCE_PATH,
    BprimeRecord,
    BprimeRecordError,
    IntervalRecord,
    build_bprime_provenance,
    read_bprime_record,
    write_bprime_provenance,
)
from uplift.consensus_arm import ConsensusArmUnavailable
from uplift.controls import SeedRange
from uplift.controls_run import ARM_CONSTRUCTION_SEED, POSITIVE_START, structure_aware_arm
from uplift.dispatch import (
    DecisionCountsRecord,
    DispatchReport,
    PathwayConsultant,
    PathwayProbeError,
    PathwayProbeRefusal,
    PathwayProbeReport,
    ProbeInputResult,
    read_probe_refusal,
    read_probe_report,
    summarise_dispatch,
)
from uplift.e5_suite import (
    BPRIME_REPRODUCTION_KIND,
    E5_COMPARATOR,
    E5_CONSENSUS_LEVERS,
    E5_HOURS,
    E5_IN_SAMPLE_ARM,
    E5_LOOP,
    E5_REPRODUCED_ARMS,
    E5_SCENARIO_NAME,
    E5_SCENARIO_SEED,
    E5_SUITE,
    REPRODUCED_ARMS,
    ArmReproduction,
    BprimeReproduction,
    BprimeReproductionError,
    ReproducedArm,
    _structure_aware_arm,
    build_e5_arms,
    e5_baseline_arms,
    e5_consensus_policy,
    e5_replicate_seeds,
    e5_scenario,
    measure_bprime_reproduction,
    production_arm_cost,
    read_bprime_reproduction,
    write_bprime_reproduction,
)
from uplift.foresight import _cadence, _new_arm_engine, run_single_arm, stocked_skus
from uplift.harness import (
    DEFAULT_CONSENSUS_ARM,
    LOOP_LEVERS,
    HarnessResult,
    LoopConfig,
    UpliftArtifact,
    UpliftHarness,
    _build_twin,
    aggregate_arm,
    decision_count_totals,
    registered_roles,
    replicate_seed,
    run_closed_loop,
)
from uplift.interfaces import (
    ArmSpec,
    DecisionCounts,
    DecisionPolicy,
    KpiVector,
    Observation,
    PolicyAction,
    RunScoped,
    Scenario,
    ScenarioRun,
)
from uplift.kpi import committed_objective
from uplift.oracle_arm import (
    STRUCTURE_AWARE_ARM,
    StructureAwareBaseStock,
    build_structure_aware_arm,
)
from uplift.policies import NamedPolicy, RunScopedNamedPolicy, UnavailableConsensusArm
from uplift.power import source_set_digest
from uplift.tuned_static import TUNED_STATIC_ARM, GroupParLevelReorder, sku_groups

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence
    from pathlib import Path

    from digital_twin.simulation.world import ResolvedWorld
    from uplift.consensus_arm import ConsensusOutcome
    from uplift.tuned_static import GroupLevels


# ---------------------------------------------------------------------------
# B-prime's committed numbers -- READ from run 36860454801's `twin-regret-primary` artifact
# ---------------------------------------------------------------------------
_ARM_E_LEVELS: Final[dict[str, dict[str, int]]] = {
    "sup_a": {"S": 127, "s": 118},
    "sup_b": {"S": 163, "s": 155},
    "sup_c": {"S": 183, "s": 173},
}
_ARM_E_PRIME_LEVELS: Final[dict[str, dict[str, int]]] = {
    "sup_a": {"S": 127, "s": 119},
    "sup_b": {"S": 163, "s": 155},
    "sup_c": {"S": 183, "s": 173},
}
_E_MINUS_O: Final[dict[str, float]] = {
    "high": 0.275995635964435,
    "low": 0.21442051306302964,
    "point": 0.2462869929615538,
}
_E_MINUS_D: Final[dict[str, float]] = {
    "high": 0.6660569949084235,
    "low": 0.5958317971588388,
    "point": 0.6295348427901005,
}
_TUNING_SEEDS: Final[tuple[int, ...]] = tuple(range(1000, 1100))
_REPLICATES: Final[int] = 200
#: B-prime's three measured means over its measurement seeds, READ from the same artifact's
#: ``mean_tuned_static_cost``, ``mean_in_sample_tuned_static_cost`` and
#: ``mean_structure_aware_cost`` (API2 amendment 1.3).
_MEAN_E: Final[float] = 2.458528200722326
_MEAN_E_PRIME: Final[float] = 2.4571572385261105
_MEAN_O: Final[float] = 2.2122412077607727
_MEANS: Final[dict[str, float]] = {
    "mean_tuned_static_cost": _MEAN_E,
    "mean_in_sample_tuned_static_cost": _MEAN_E_PRIME,
    "mean_structure_aware_cost": _MEAN_O,
}
#: A FIXTURE revision: 40 hex digits beginning with the short sha B-prime ran at. The real full
#: sha is the main agent's to record in the committed provenance file.
_FIXTURE_REVISION: Final[str] = "ec0eb91" + "0" * 33
_RUN_ID: Final[str] = "36860454801"

#: One file per pattern of BPRIME_PHYSICS_SET, so every pattern selects something.
_PHYSICS_FILES: Final[tuple[str, ...]] = (
    "digital_twin/simulation/engine.py",
    "digital_twin/simulation/policy.yaml",
    "digital_twin/config.py",
    "infrastructure/quality/comparator-tuning.yaml",
    "uplift/foresight.py",
    "uplift/harness.py",
    "uplift/regret.py",
    "uplift/tuning.py",
    "uplift/tuned_static.py",
    "uplift/oracle_arm.py",
    "uplift/baselines/par_level_reorder.py",
)

#: ``main`` exactly as ``uplift.yml::uplift-proof`` invokes it, minus ``--output``.
_WORKFLOW_ARGV: Final[tuple[str, ...]] = (
    "--full",
    "--suite",
    "e5-primary",
    "--baseline-arm",
    "tuned_static",
    "--duration-hours",
    "24",
)


def _record(**overrides: object) -> BprimeRecord:
    """B-prime's record built in memory, with any field overridden."""
    fields: dict[str, object] = {
        "source_run_id": _RUN_ID,
        "source_revision_sha": _FIXTURE_REVISION,
        "artifact_sha256": "0" * 64,
        "cell": BPRIME_CELL,
        "replicates": _REPLICATES,
        "hours_per_replicate": 24.0,
        "tuning_seeds": _TUNING_SEEDS,
        "measurement_seeds": SeedRange(start=0, count=_REPLICATES),
        "tuned_static_levels": {group: dict(pair) for group, pair in _ARM_E_LEVELS.items()},
        "in_sample_levels": {group: dict(pair) for group, pair in _ARM_E_PRIME_LEVELS.items()},
        "e_minus_o": IntervalRecord(**_E_MINUS_O),
        "e_minus_d": IntervalRecord(**_E_MINUS_D),
        "alpha": 0.05,
        **_MEANS,
    }
    fields.update(overrides)
    return BprimeRecord.model_validate(fields)


def _artifact_payload(**overrides: object) -> dict[str, object]:
    """The keys of the B-prime artifact the reader reads, at B-prime's values."""
    payload: dict[str, object] = {
        "cell": BPRIME_CELL,
        "primary_cell": True,
        "status": "measured",
        "replicates_usable": _REPLICATES,
        "replicates_unusable": 0,
        "hours_per_replicate": 24.0,
        "tuning_seeds": list(_TUNING_SEEDS),
        "tuning_seeds_injected": False,
        "tuned_static_candidates_injected": False,
        "tuned_static_converged": True,
        "split_admissible": True,
        "tuned_static_levels": _ARM_E_LEVELS,
        "in_sample_tuned_static_levels": _ARM_E_PRIME_LEVELS,
        "achievable_information_value_interval": _E_MINUS_O,
        "information_ceiling_interval": _E_MINUS_D,
        "interval_alpha": 0.05,
        "unusable_seeds": [],
        "verdict": "material",
        **_MEANS,
    }
    payload.update(overrides)
    return payload


def _write_tree(root: Path, artifact: dict[str, object]) -> bytes:
    """A fake repository: physics fixtures, the artifact, and its provenance via the builder."""
    for relative in _PHYSICS_FILES:
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(f"# physics fixture: {relative}\n".encode())
    artifact_bytes = (json.dumps(artifact, sort_keys=True) + "\n").encode()
    artifact_path = root / BPRIME_ARTIFACT_PATH
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_bytes(artifact_bytes)
    provenance = build_bprime_provenance(
        root,
        source_run_id=_RUN_ID,
        source_revision_sha=_FIXTURE_REVISION,
        artifact_name="twin-regret-primary",
        attestation="fixture: no physics file changed between the measuring run and this tree",
    )
    write_bprime_provenance(root, provenance)
    return artifact_bytes


def _provenance_payload(root: Path) -> dict[str, object]:
    loaded = json.loads((root / BPRIME_PROVENANCE_PATH).read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    return loaded


def _write_provenance(root: Path, payload: object, *, canonical: bool = True) -> None:
    text = (
        json.dumps(payload, sort_keys=True, separators=(",", ":"))
        if canonical
        else json.dumps(payload, sort_keys=True, indent=2)
    )
    (root / BPRIME_PROVENANCE_PATH).write_bytes(text.encode())


def _observation() -> Observation:
    return Observation(
        inventory={"sku_0": 10},
        sim_time=0.0,
        delivery_count=0,
        spoilage_count=0,
        stockout_count=0,
        unit_costs={"sku_0": 1.0},
    )


def _kpi(objective: float) -> KpiVector:
    return KpiVector(
        fill_rate=0.9,
        spoilage_rate=0.0,
        stockout_rate=0.0,
        avg_delivery_time_min=1.0,
        margin=0.0,
        co2_estimate=1.0,
        avg_on_hand_units=1.0,
        objective=objective,
    )


# ---------------------------------------------------------------------------
# Policies the clauses drive (module level, so they pickle)
# ---------------------------------------------------------------------------
class _FixedPolicy:
    """A ``DecisionPolicy`` returning one fixed action, so delegation is checked by identity."""

    def __init__(self, name: str, action: PolicyAction | None = None) -> None:
        self.name = name
        self.action = action if action is not None else PolicyAction()

    def decide(self, obs: Observation) -> PolicyAction:
        return self.action


class _TallyingPolicy:
    """``RunScoped``: every decision is one dispatched decision, and one run is open at a time.

    ``begin_run`` REFUSES a second open run, so a harness that left a failed run open would fail
    every later run with "a run is already open" -- which is how clause (c) proves the pairing.
    """

    def __init__(self, name: str = "tallying", *, fail_at: int | None = None) -> None:
        self.name = name
        self.fail_at = fail_at
        self.opened: list[int] = []
        self.closed = 0
        self._decided: int | None = None

    def begin_run(self, seed: int) -> None:
        if self._decided is not None:
            raise RuntimeError("a run is already open")
        self.opened.append(seed)
        self._decided = 0

    def decide(self, obs: Observation) -> PolicyAction:
        if self._decided is None:
            raise RuntimeError("decide outside a run")
        if self.fail_at is not None and self._decided == self.fail_at:
            raise RuntimeError("stub decision failure")
        self._decided += 1
        return PolicyAction()

    def end_run(self) -> DecisionCounts:
        if self._decided is None:
            raise RuntimeError("end_run with no open run")
        decided, self._decided = self._decided, None
        self.closed += 1
        return DecisionCounts(
            dispatched=decided, withheld_for_confidence=0, guardrail_blocked=0, untranslatable=0
        )


class _MistalliedPolicy(_TallyingPolicy):
    """Returns something that is not a ``DecisionCounts`` from ``end_run``."""

    def end_run(self) -> DecisionCounts:
        super().end_run()
        return cast("DecisionCounts", "not a tally")


class _PricedReorderPolicy:
    """Sets a price AND orders, so a loop that applied the price would move demand and margin."""

    def __init__(self, name: str, *, price: float | None) -> None:
        self.name = name
        self.price = price

    def decide(self, obs: Observation) -> PolicyAction:
        return PolicyAction(reorder_quantities={"sku_0": 5.0}, price=self.price)


# ---------------------------------------------------------------------------
# DecisionCounts and ScenarioRun's tally invariant
# ---------------------------------------------------------------------------
_COUNT_FIELDS: Final[tuple[str, ...]] = tuple(
    field.name for field in dataclasses.fields(DecisionCounts)
)
_count = st.integers(min_value=0, max_value=10**9)


@given(counts=st.tuples(_count, _count, _count, _count))
def test_a_tally_totals_its_four_disjoint_outcomes(counts: tuple[int, int, int, int]) -> None:
    tally = DecisionCounts(*counts)
    assert tally.total == sum(counts)
    assert tuple(getattr(tally, name) for name in _COUNT_FIELDS) == counts


@given(
    position=st.sampled_from(_COUNT_FIELDS),
    bad=st.one_of(
        st.integers(max_value=-1), st.booleans(), st.floats(allow_nan=False), st.text(max_size=3)
    ),
)
def test_a_negative_or_non_integer_count_is_refused(position: str, bad: object) -> None:
    fields: dict[str, object] = dict.fromkeys(_COUNT_FIELDS, 1)
    fields[position] = bad
    with pytest.raises(ValueError, match=position):
        DecisionCounts(**cast("dict[str, int]", fields))


def test_a_failed_run_records_no_tally() -> None:
    tally = DecisionCounts(1, 0, 0, 0)
    with pytest.raises(ValueError, match="failed"):
        ScenarioRun(arm="a", seed=1, kpis=None, failed=True, error="x", decision_counts=tally)
    with pytest.raises(ValueError, match="DecisionCounts"):
        ScenarioRun(
            arm="a",
            seed=1,
            kpis=None,
            failed=False,
            error=None,
            decision_counts=cast("DecisionCounts", {"dispatched": 1}),
        )
    kept = ScenarioRun(arm="a", seed=1, kpis=None, failed=False, error=None, decision_counts=tally)
    assert kept.decision_counts == tally
    assert ScenarioRun(arm="a", seed=1, kpis=None, failed=True, error="x").decision_counts is None


@st.composite
def _tallied_runs(draw: st.DrawFn) -> ScenarioRun:
    failed = draw(st.booleans())
    counts = None if failed else draw(st.none() | st.builds(DecisionCounts, *[_count] * 4))
    return ScenarioRun(
        arm=draw(st.sampled_from(["consensus", "tuned_static"])),
        seed=draw(st.integers(min_value=0, max_value=50)),
        kpis=None,
        failed=failed,
        error="x" if failed else None,
        decision_counts=counts,
    )


@given(runs=st.lists(_tallied_runs(), max_size=30))
def test_the_dispatch_totals_sum_one_arms_completed_tallies_or_are_none(
    runs: list[ScenarioRun],
) -> None:
    kept = [
        run.decision_counts
        for run in runs
        if run.arm == "consensus" and not run.failed and run.decision_counts is not None
    ]
    totals = decision_count_totals(runs, arm="consensus")
    if not kept:
        assert totals is None
        return
    assert totals is not None
    for name in _COUNT_FIELDS:
        assert getattr(totals, name) == sum(getattr(tally, name) for tally in kept)


def test_the_dispatch_totals_of_an_arm_with_no_tally_are_none_never_zero() -> None:
    runs = [
        ScenarioRun(arm="consensus", seed=i, kpis=None, failed=False, error=None) for i in range(3)
    ]
    assert decision_count_totals(runs, arm="consensus") is None
    assert decision_count_totals([], arm="consensus") is None


# ---------------------------------------------------------------------------
# NamedPolicy: delegates, renames, and is run-scoped exactly when what it wraps is
# ---------------------------------------------------------------------------
_names = st.text(min_size=1, max_size=20).filter(lambda name: bool(name.strip()))


@given(name=_names)
def test_a_named_policy_delegates_and_renames(name: str) -> None:
    action = PolicyAction(reorder_quantities={"sku_0": 3.0})
    inner = _FixedPolicy("inner", action)
    named = NamedPolicy(inner, name)
    assert named.name == name
    assert named.inner is inner
    assert named.decide(_observation()) is action
    assert type(named) is NamedPolicy
    assert not isinstance(named, RunScoped)
    assert isinstance(named, DecisionPolicy)


@given(name=_names, seed=st.integers(min_value=0, max_value=2**32))
def test_a_named_policy_is_run_scoped_exactly_when_its_policy_is(name: str, seed: int) -> None:
    inner = _TallyingPolicy()
    named = NamedPolicy(inner, name)
    assert type(named) is RunScopedNamedPolicy
    assert isinstance(named, RunScoped)
    assert isinstance(named, RunScopedNamedPolicy)
    named.begin_run(seed)
    named.decide(_observation())
    assert named.end_run() == DecisionCounts(1, 0, 0, 0)
    assert inner.opened == [seed]
    assert inner.closed == 1


@given(blank=st.text(alphabet=" \t\n", max_size=4))
def test_a_blank_arm_name_is_refused(blank: str) -> None:
    with pytest.raises(ValueError, match="non-blank"):
        NamedPolicy(_FixedPolicy("inner"), blank)


def test_a_wrapper_over_no_policy_or_a_false_run_scope_is_refused() -> None:
    with pytest.raises(ValueError, match="not a DecisionPolicy"):
        NamedPolicy(cast("DecisionPolicy", object()), "arm")
    with pytest.raises(ValueError, match="not RunScoped"):
        RunScopedNamedPolicy(_FixedPolicy("inner"), "arm")


def test_a_named_policy_crosses_a_process_boundary_as_the_same_class() -> None:
    plain = pickle.loads(pickle.dumps(NamedPolicy(_FixedPolicy("inner"), "renamed")))
    assert type(plain) is NamedPolicy
    assert plain.name == "renamed"
    assert plain.decide(_observation()) == PolicyAction()

    scoped = pickle.loads(pickle.dumps(NamedPolicy(_TallyingPolicy(), "scoped")))
    assert type(scoped) is RunScopedNamedPolicy
    assert isinstance(scoped, RunScoped)
    scoped.begin_run(3)
    assert scoped.end_run() == DecisionCounts(0, 0, 0, 0)


# ---------------------------------------------------------------------------
# The record: built by hand, it obeys the reader's rules; its levels are arm E's and E-prime's
# ---------------------------------------------------------------------------
def test_b_primes_record_names_arm_e_and_e_prime_and_they_differ_only_at_sup_a() -> None:
    record = _record()
    arm_e, arm_e_prime = record.arm_e_levels(), record.arm_e_prime_levels()
    assert {g: (p.s, p.S) for g, p in arm_e.levels.items()} == {
        "sup_a": (118, 127),
        "sup_b": (155, 163),
        "sup_c": (173, 183),
    }
    differing = {g for g in arm_e.levels if arm_e.levels[g] != arm_e_prime.levels[g]}
    assert differing == {"sup_a"}
    assert (arm_e_prime.levels["sup_a"].s, arm_e_prime.levels["sup_a"].S) == (119, 127)


_pairs = st.integers(min_value=0, max_value=300).flatmap(
    lambda s: st.tuples(st.just(s), st.integers(min_value=s + 1, max_value=s + 300))
)


@given(
    groups=st.lists(st.sampled_from(["sup_a", "sup_b", "sup_c"]), min_size=1, unique=True),
    data=st.data(),
)
def test_e_and_e_prime_differ_exactly_where_the_record_says(
    groups: list[str], data: st.DataObject
) -> None:
    tuned = {group: data.draw(_pairs) for group in groups}
    in_sample = {group: data.draw(st.just(tuned[group]) | _pairs) for group in groups}
    record = _record(
        tuned_static_levels={g: {"S": big, "s": small} for g, (small, big) in tuned.items()},
        in_sample_levels={g: {"S": big, "s": small} for g, (small, big) in in_sample.items()},
    )

    def _as_pairs(levels: GroupLevels) -> dict[str, tuple[int, int]]:
        return {group: (point.s, point.S) for group, point in levels.levels.items()}

    assert _as_pairs(record.arm_e_levels()) == tuned
    assert _as_pairs(record.arm_e_prime_levels()) == in_sample
    e, e_prime = _as_pairs(record.arm_e_levels()), _as_pairs(record.arm_e_prime_levels())
    assert {g for g in groups if e[g] != e_prime[g]} == {
        g for g in groups if tuned[g] != in_sample[g]
    }


_HAND_BUILT_DEFECTS: Final[dict[str, tuple[dict[str, object], str]]] = {
    "tuning seeds inside the measurement range": (
        {"tuning_seeds": (5, 1000)},
        "inside the measurement range",
    ),
    "a seed range that is not the replicate count": (
        {"measurement_seeds": SeedRange(start=0, count=199)},
        "replicates",
    ),
    "two worlds' groups": (
        {"in_sample_levels": {"sup_a": {"S": 127, "s": 119}}},
        "groups",
    ),
    "an inadmissible pair": (
        {"tuned_static_levels": {**_ARM_E_LEVELS, "sup_a": {"S": 100, "s": 100}}},
        "not admissible",
    ),
    "a pair with a third key": (
        {"tuned_static_levels": {**_ARM_E_LEVELS, "sup_a": {"S": 127, "s": 118, "q": 1}}},
        "not exactly",
    ),
    "a boolean replicate count": ({"replicates": True}, "replicates"),
    "a short revision": ({"source_revision_sha": "ec0eb91"}, "source_revision_sha"),
    "an alpha of one": ({"alpha": 1.0}, "alpha"),
    "no tuning seeds": ({"tuning_seeds": ()}, "no tuning seeds"),
    "a non-finite measured mean": (
        {"mean_structure_aware_cost": float("nan")},
        "mean_structure_aware_cost=nan is not finite",
    ),
}


@pytest.mark.parametrize("defect", sorted(_HAND_BUILT_DEFECTS))
def test_a_hand_built_record_obeys_the_readers_rules(defect: str) -> None:
    overrides, needle = _HAND_BUILT_DEFECTS[defect]
    with pytest.raises(ValueError, match=needle):
        _record(**overrides)


# ---------------------------------------------------------------------------
# The reader: refuses each named defect by name, never defaulting
# ---------------------------------------------------------------------------
def test_the_committed_shape_reads_back_as_b_primes_record(tmp_path: Path) -> None:
    artifact_bytes = _write_tree(tmp_path, _artifact_payload())
    record = read_bprime_record(tmp_path)
    assert record.artifact_sha256 == hashlib.sha256(artifact_bytes).hexdigest()
    assert record.source_run_id == _RUN_ID
    assert record.source_revision_sha == _FIXTURE_REVISION
    assert record.cell == BPRIME_CELL
    assert record.replicates == _REPLICATES
    assert record.measurement_seeds == SeedRange(start=0, count=_REPLICATES)
    assert record.tuning_seeds == _TUNING_SEEDS
    assert record.tuned_static_levels == _ARM_E_LEVELS
    assert record.in_sample_levels == _ARM_E_PRIME_LEVELS
    assert record.e_minus_o == IntervalRecord(**_E_MINUS_O)
    assert record.e_minus_d == IntervalRecord(**_E_MINUS_D)
    assert record.alpha == 0.05
    assert record.hours_per_replicate == 24.0
    measured_means = (
        record.mean_tuned_static_cost,
        record.mean_in_sample_tuned_static_cost,
        record.mean_structure_aware_cost,
    )
    assert measured_means == (_MEAN_E, _MEAN_E_PRIME, _MEAN_O)
    # The digest the record was admitted against is the real one, over every declared pattern.
    provenance = _provenance_payload(tmp_path)
    assert provenance["physics_digest"] == source_set_digest(tmp_path, BPRIME_PHYSICS_SET)
    assert provenance["physics_set"] == list(BPRIME_PHYSICS_SET)


def _drop_artifact(root: Path) -> None:
    (root / BPRIME_ARTIFACT_PATH).unlink()


def _drop_provenance(root: Path) -> None:
    (root / BPRIME_PROVENANCE_PATH).unlink()


def _artifact_as_directory(root: Path) -> None:
    path = root / BPRIME_ARTIFACT_PATH
    path.unlink()
    path.mkdir()


def _alter_artifact_bytes(root: Path) -> None:
    path = root / BPRIME_ARTIFACT_PATH
    path.write_bytes(path.read_bytes() + b" ")


def _alter_physics(root: Path) -> None:
    path = root / "uplift" / "harness.py"
    path.write_bytes(path.read_bytes() + b"# one more line of physics\n")


def _drop_physics_file(root: Path) -> None:
    (root / "uplift" / "oracle_arm.py").unlink()


_TREE_DEFECTS: Final[dict[str, tuple[Callable[[Path], None], str]]] = {
    "the artifact is missing": (_drop_artifact, "artifact is missing"),
    "the provenance is missing": (_drop_provenance, "provenance is missing"),
    "the artifact is unreadable": (_artifact_as_directory, "unreadable"),
    "the artifact is not the pinned bytes": (_alter_artifact_bytes, "sha256"),
    "the physics changed": (_alter_physics, "another physics"),
    "a physics file is gone": (_drop_physics_file, "cannot be digested"),
}


@pytest.mark.parametrize("defect", sorted(_TREE_DEFECTS))
def test_the_reader_refuses_a_tree_that_cannot_evidence_the_record(
    defect: str, tmp_path: Path
) -> None:
    _write_tree(tmp_path, _artifact_payload())
    damage, needle = _TREE_DEFECTS[defect]
    damage(tmp_path)
    with pytest.raises(BprimeRecordError, match=needle):
        read_bprime_record(tmp_path)


_CONTENT_DEFECTS: Final[dict[str, tuple[dict[str, object], str]]] = {
    "another cell": ({"cell": "s3_only"}, "cell"),
    "not the binding cell": ({"primary_cell": False}, "primary_cell"),
    "a truthy, not true, binding flag": ({"primary_cell": 1}, "primary_cell"),
    "not measured": ({"status": "unavailable"}, "status"),
    "an unusable replicate": ({"replicates_unusable": 1}, "replicates_unusable"),
    "a boolean unusable count": ({"replicates_unusable": False}, "replicates_unusable"),
    "an unconverged search": ({"tuned_static_converged": False}, "tuned_static_converged"),
    "an inadmissible split": ({"split_admissible": False}, "split_admissible"),
    "injected tuning seeds": ({"tuning_seeds_injected": True}, "tuning_seeds_injected"),
    "injected candidates": (
        {"tuned_static_candidates_injected": True},
        "tuned_static_candidates_injected",
    ),
    "an inverted interval": (
        {"information_ceiling_interval": {"high": 0.6, "low": 0.7, "point": 0.65}},
        "information_ceiling_interval",
    ),
    "a fractional level": (
        {"tuned_static_levels": {**_ARM_E_LEVELS, "sup_a": {"S": 127.0, "s": 118}}},
        "tuned_static_levels",
    ),
    "a seed that is not an integer": ({"tuning_seeds": [1000, "1001"]}, "tuning_seeds"),
}


@pytest.mark.parametrize("defect", sorted(_CONTENT_DEFECTS))
def test_the_reader_refuses_an_artifact_that_is_not_b_primes_measurement(
    defect: str, tmp_path: Path
) -> None:
    overrides, needle = _CONTENT_DEFECTS[defect]
    # The provenance is built over the defective artifact, so sha and digest both match: the
    # refusal can only come from the content clause under test.
    _write_tree(tmp_path, _artifact_payload(**overrides))
    with pytest.raises(BprimeRecordError, match=needle):
        read_bprime_record(tmp_path)


_READ_KEYS: Final[tuple[str, ...]] = (
    "cell",
    "primary_cell",
    "status",
    "replicates_unusable",
    "tuned_static_converged",
    "split_admissible",
    "tuning_seeds_injected",
    "tuned_static_candidates_injected",
    "replicates_usable",
    "hours_per_replicate",
    "tuning_seeds",
    "tuned_static_levels",
    "in_sample_tuned_static_levels",
    "achievable_information_value_interval",
    "information_ceiling_interval",
    "interval_alpha",
    "mean_tuned_static_cost",
    "mean_in_sample_tuned_static_cost",
    "mean_structure_aware_cost",
)


@pytest.mark.parametrize("key", _READ_KEYS)
def test_the_reader_refuses_an_artifact_missing_a_key_it_reads(key: str, tmp_path: Path) -> None:
    payload = _artifact_payload()
    del payload[key]
    _write_tree(tmp_path, payload)
    with pytest.raises(BprimeRecordError, match=f"carries no '{key}'"):
        read_bprime_record(tmp_path)


#: Each way a recorded mean can fail to be one, beside the words its refusal names it by. JSON's
#: ``NaN`` and ``Infinity`` tokens decode to floats, so a non-finite mean is a real artifact.
_MEAN_DEFECTS: Final[dict[str, tuple[object, str]]] = {
    "null": (None, "is null"),
    "NaN": (float("nan"), "=nan is not finite"),
    "positive infinity": (float("inf"), "=inf is not finite"),
    "negative infinity": (float("-inf"), "=-inf is not finite"),
    "a string": ("2.4585", "is not a number"),
    "a boolean": (True, "=True is not a number"),
}


@pytest.mark.parametrize("key", sorted(_MEANS))
@pytest.mark.parametrize("defect", sorted(_MEAN_DEFECTS))
def test_the_reader_refuses_a_recorded_mean_that_is_null_or_not_finite(
    key: str, defect: str, tmp_path: Path
) -> None:
    value, needle = _MEAN_DEFECTS[defect]
    _write_tree(tmp_path, _artifact_payload(**{key: value}))
    with pytest.raises(BprimeRecordError, match=f"artifact's {key}.*{needle}"):
        read_bprime_record(tmp_path)


_PROVENANCE_DEFECTS: Final[dict[str, tuple[Callable[[dict[str, object]], object], str]]] = {
    "an unknown key": (lambda p: {**p, "note": "x"}, "schema"),
    "a missing key": (lambda p: {k: v for k, v in p.items() if k != "attestation"}, "schema"),
    "another kind": (lambda p: {**p, "kind": "power-report"}, "schema"),
    "schema version 2": (lambda p: {**p, "schema_version": 2}, "schema"),
    "a boolean schema version": (lambda p: {**p, "schema_version": True}, "schema"),
    "a short revision": (lambda p: {**p, "source_revision_sha": "ec0eb91"}, "schema"),
    "an upper-case digest": (
        lambda p: {**p, "artifact_sha256": str(p["artifact_sha256"]).upper()},
        "schema",
    ),
    "a blank attestation": (lambda p: {**p, "attestation": "   "}, "schema"),
    "a physics set other than the declared one": (
        lambda p: {**p, "physics_set": list(BPRIME_PHYSICS_SET[:-1])},
        "physics_set",
    ),
    "an array, not an object": (lambda p: [p], "not an object"),
}


@pytest.mark.parametrize("defect", sorted(_PROVENANCE_DEFECTS))
def test_the_reader_refuses_a_provenance_that_is_not_exactly_its_schema(
    defect: str, tmp_path: Path
) -> None:
    _write_tree(tmp_path, _artifact_payload())
    edit, needle = _PROVENANCE_DEFECTS[defect]
    _write_provenance(tmp_path, edit(_provenance_payload(tmp_path)))
    with pytest.raises(BprimeRecordError, match=needle):
        read_bprime_record(tmp_path)


def test_the_reader_refuses_a_provenance_that_is_not_canonical_or_not_json(
    tmp_path: Path,
) -> None:
    _write_tree(tmp_path, _artifact_payload())
    payload = _provenance_payload(tmp_path)
    assert read_bprime_record(tmp_path).source_run_id == _RUN_ID  # admissible as written

    _write_provenance(tmp_path, payload, canonical=False)
    with pytest.raises(BprimeRecordError, match="not canonical"):
        read_bprime_record(tmp_path)

    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    (tmp_path / BPRIME_PROVENANCE_PATH).write_bytes((canonical + "\n").encode())
    with pytest.raises(BprimeRecordError, match="not canonical"):
        read_bprime_record(tmp_path)

    (tmp_path / BPRIME_PROVENANCE_PATH).write_bytes(b"{not json")
    with pytest.raises(BprimeRecordError, match="not UTF-8 JSON"):
        read_bprime_record(tmp_path)


# ---------------------------------------------------------------------------
# The suite: loop, scenario, world threading, seeds, arms
# ---------------------------------------------------------------------------
def test_the_e5_loop_is_regrets_24_hour_cadence_applying_reorders_only() -> None:
    slices, slice_hours = _cadence(24.0)
    assert (slices, slice_hours) == (24, 1.0)
    assert E5_HOURS == 24.0
    assert E5_LOOP.duration_hours == E5_HOURS
    assert E5_LOOP.step_hours == slice_hours
    assert E5_LOOP.n_steps == slices
    assert E5_LOOP.levers == "reorders_only"


def test_a_lever_set_the_loop_does_not_implement_is_refused() -> None:
    assert LOOP_LEVERS == ("all", "reorders_only")
    assert LoopConfig().levers == "all"
    assert LoopConfig(2.0, 1.0) == LoopConfig(duration_hours=2.0, step_hours=1.0, levers="all")
    with pytest.raises(ValueError, match="levers"):
        LoopConfig(levers=cast("Literal['all']", "price_only"))


def test_the_e5_scenario_is_the_primary_cell_unshocked() -> None:
    scenario = e5_scenario()
    world = load_world()
    assert scenario.name == E5_SCENARIO_NAME == "e5_primary_unshocked"
    assert scenario.seed == E5_SCENARIO_SEED
    assert scenario.shock == ShockParams()
    assert scenario.cold_start is False
    assert scenario.world == world.resolve(world.primary_cell)
    assert scenario.world is not None
    assert scenario.world.cell == BPRIME_CELL
    assert scenario.world.structure_1_on
    assert scenario.world.structure_3_on


def test_the_twin_is_built_in_the_scenarios_world_and_none_means_none() -> None:
    scenario = e5_scenario()
    assert _build_twin(scenario, 7).world == scenario.world
    assert _build_twin(Scenario(name="worldless", seed=7, shock=ShockParams()), 7).world is None


def test_e5_seeds_are_the_harness_derivation_and_avoid_every_b_prime_seed() -> None:
    record = _record()
    seeds = e5_replicate_seeds(MIN_SCENARIOS, record)
    assert seeds == tuple(replicate_seed(e5_scenario().seed, i) for i in range(MIN_SCENARIOS))
    assert len(set(seeds)) == MIN_SCENARIOS
    assert set(seeds).isdisjoint(_TUNING_SEEDS)
    assert set(seeds).isdisjoint(range(_REPLICATES))


@given(n=st.integers(min_value=1, max_value=64), data=st.data())
def test_an_e5_seed_on_a_b_prime_seed_is_refused(n: int, data: st.DataObject) -> None:
    seeds = tuple(replicate_seed(E5_SCENARIO_SEED, i) for i in range(n))
    colliding = seeds[data.draw(st.integers(min_value=0, max_value=n - 1))]
    if data.draw(st.booleans()):
        record = _record(
            tuning_seeds=(colliding,),
            measurement_seeds=SeedRange(start=colliding + 1, count=_REPLICATES),
        )
        needle = "tuning seeds \\[" + str(colliding)
    else:
        record = _record(
            replicates=1,
            measurement_seeds=SeedRange(start=colliding, count=1),
            tuning_seeds=(colliding + 1,),
        )
        needle = "measurement seeds \\[" + str(colliding)
    with pytest.raises(ValueError, match=needle):
        e5_replicate_seeds(n, record)


@pytest.mark.parametrize("n", [0, -1, True])
def test_a_non_positive_replicate_count_is_refused(n: int) -> None:
    with pytest.raises(ValueError, match="positive replicate count"):
        e5_replicate_seeds(n, _record())


def test_arms_e_and_e_prime_are_b_primes_levels_registered_as_baselines() -> None:
    record = _record()
    arm_e_spec, arm_e_prime_spec = e5_baseline_arms(record)
    assert (arm_e_spec.name, arm_e_spec.role) == (E5_COMPARATOR, "baseline")
    assert (arm_e_prime_spec.name, arm_e_prime_spec.role) == (E5_IN_SAMPLE_ARM, "baseline")

    arm_e = arm_e_spec.policy
    assert isinstance(arm_e, GroupParLevelReorder)
    assert arm_e.levels == record.arm_e_levels()
    arm_e_prime = arm_e_prime_spec.policy
    assert type(arm_e_prime) is NamedPolicy
    inner = arm_e_prime.inner
    assert isinstance(inner, GroupParLevelReorder)
    assert inner.levels == record.arm_e_prime_levels()

    world = e5_scenario().world
    expected = sku_groups(world, stocked_skus(0, world=world))
    assert dict(arm_e.sku_group) == expected
    assert dict(inner.sku_group) == expected
    assert set(expected.values()) == set(record.tuned_static_levels) == {"sup_a", "sup_b", "sup_c"}


def test_a_record_for_another_cell_or_horizon_is_not_arm_e_here() -> None:
    with pytest.raises(ValueError, match="cell"):
        e5_baseline_arms(_record(cell="s3_only"))
    with pytest.raises(ValueError, match="horizon"):
        e5_baseline_arms(_record(hours_per_replicate=12.0))


def test_the_e5_arms_are_consensus_then_e_then_e_prime(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(e5_suite, "e5_consensus_policy", lambda: _FixedPolicy("consensus"))
    arms = build_e5_arms(_record())
    assert [(spec.name, spec.role) for spec in arms] == [
        (DEFAULT_CONSENSUS_ARM, "consensus"),
        (E5_COMPARATOR, "baseline"),
        (E5_IN_SAMPLE_ARM, "baseline"),
    ]
    assert registered_roles(arms) == {
        DEFAULT_CONSENSUS_ARM: "consensus",
        E5_COMPARATOR: "baseline",
        E5_IN_SAMPLE_ARM: "baseline",
    }
    monkeypatch.setattr(e5_suite, "e5_consensus_policy", lambda: _FixedPolicy("other"))
    with pytest.raises(ValueError, match="named 'other'"):
        build_e5_arms(_record())


def test_the_consensus_arm_moves_reorders_only_or_degrades_honestly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requested: list[object] = []

    def _builder(**kwargs: object) -> DecisionPolicy:
        requested.append(kwargs.get("levers"))
        return _FixedPolicy(DEFAULT_CONSENSUS_ARM)

    monkeypatch.setattr(e5_suite, "build_consensus_arm", _builder)
    assert e5_consensus_policy().name == DEFAULT_CONSENSUS_ARM
    assert requested == [E5_CONSENSUS_LEVERS] == [frozenset({"reorder"})]

    def _unassemblable(**kwargs: object) -> DecisionPolicy:
        raise RuntimeError("no network here")

    monkeypatch.setattr(e5_suite, "build_consensus_arm", _unassemblable)
    stand_in = e5_consensus_policy()
    assert isinstance(stand_in, UnavailableConsensusArm)
    assert stand_in.name == DEFAULT_CONSENSUS_ARM
    assert not isinstance(stand_in, RunScoped)
    with pytest.raises(ConsensusArmUnavailable, match="no network here"):
        stand_in.decide(_observation())


# ---------------------------------------------------------------------------
# run_arm_on_seeds: identity seeding, refused before any twin
# ---------------------------------------------------------------------------
class _SeamRecordingHarness(UpliftHarness):
    """Both execution seams stubbed: records the seeds that reach them and builds no twin."""

    def __init__(self) -> None:
        super().__init__(max_workers=2)
        self.reached: list[tuple[str, list[int]]] = []

    def _run_parallel(
        self,
        scenario: Scenario,
        policy: DecisionPolicy | None,
        policy_factory: Callable[[], DecisionPolicy] | None,
        arm_name: str,
        seeds: Sequence[int],
    ) -> list[ScenarioRun]:
        self.reached.append(("parallel", list(seeds)))
        return []

    def _run_sequential(
        self,
        scenario: Scenario,
        policy: DecisionPolicy | None,
        policy_factory: Callable[[], DecisionPolicy] | None,
        arm_name: str,
        seeds: Sequence[int],
    ) -> list[ScenarioRun]:
        self.reached.append(("sequential", list(seeds)))
        return []


_SEAM_SCENARIO: Final[Scenario] = Scenario(name="seams", seed=3, shock=ShockParams())
_SPEC: Final[ArmSpec] = ArmSpec(_FixedPolicy("arm"), "baseline")


@given(base=st.integers(min_value=0, max_value=2**40), order=st.permutations(range(MIN_SCENARIOS)))
def test_run_arm_on_seeds_hands_each_seed_to_the_twin_unchanged_and_in_order(
    base: int, order: list[int]
) -> None:
    seeds = [base + index for index in order]
    harness = _SeamRecordingHarness()
    harness.run_arm_on_seeds(_SEAM_SCENARIO, _SPEC, seeds)
    harness.run_arm_on_seeds(_SEAM_SCENARIO, _SPEC, seeds, parallel=False)
    assert harness.reached == [("parallel", seeds), ("sequential", seeds)]


_SEED_DEFECTS: Final[dict[str, tuple[list[object], str]]] = {
    "a repeated seed": ([*range(MIN_SCENARIOS), 0], "more than once"),
    "a negative seed": ([-1, *range(MIN_SCENARIOS)], "non-negative"),
    "a boolean seed": ([True, *range(2, MIN_SCENARIOS + 2)], "integers"),
    "a fractional seed": ([0.5, *range(1, MIN_SCENARIOS + 1)], "integers"),
    "too few seeds": (list(range(MIN_SCENARIOS - 1)), "INV-TW-002"),
}


@pytest.mark.parametrize("defect", sorted(_SEED_DEFECTS))
def test_run_arm_on_seeds_refuses_before_any_twin_is_built(defect: str) -> None:
    seeds, needle = _SEED_DEFECTS[defect]
    harness = _SeamRecordingHarness()
    with pytest.raises(ValueError, match=needle):
        harness.run_arm_on_seeds(_SEAM_SCENARIO, _SPEC, cast("list[int]", seeds))
    assert harness.reached == []


def test_run_arm_on_seeds_refuses_an_arm_registered_without_a_role() -> None:
    harness = _SeamRecordingHarness()
    with pytest.raises(ValueError, match="without a role"):
        harness.run_arm_on_seeds(
            _SEAM_SCENARIO, cast("ArmSpec", _FixedPolicy("bare")), list(range(MIN_SCENARIOS))
        )
    assert harness.reached == []


# ---------------------------------------------------------------------------
# The reproduction of B-prime's comparator (API2 amendment 2), priced by an injected cost
# ---------------------------------------------------------------------------
#: A stand-in cost per arm, dyadic so every sum the aggregate takes is exact: over B-prime's
#: seeds 0..199 arm E's mean is 2.375, arm E-prime's 3.375 and arm O's 1.375.
_STUB_BASE_COST: Final[dict[str, float]] = {
    TUNED_STATIC_ARM: 2.0,
    E5_IN_SAMPLE_ARM: 3.0,
    STRUCTURE_AWARE_ARM: 1.0,
}


class _RecordingCost:
    """``cost_of`` for a reproduction: records every call and prices it without a twin."""

    def __init__(self) -> None:
        self.calls: list[tuple[int, DecisionPolicy]] = []
        self.worlds: list[ResolvedWorld] = []

    def __call__(self, seed: int, policy: DecisionPolicy, world: ResolvedWorld) -> float:
        self.calls.append((seed, policy))
        self.worlds.append(world)
        return _STUB_BASE_COST[policy.name] + (seed % 4) * 0.25

    def seeds_of(self, arm: str) -> list[int]:
        """The seeds ``arm`` was priced at, in the order it was priced."""
        return [seed for seed, policy in self.calls if policy.name == arm]


def _forbidden_cost(seed: int, policy: DecisionPolicy, world: ResolvedWorld) -> float:
    raise AssertionError(f"a refused reproduction priced {policy.name!r} at seed {seed}")


def test_the_reproducible_arms_are_the_arms_b_prime_measured_by_their_own_names() -> None:
    assert REPRODUCED_ARMS == (TUNED_STATIC_ARM, E5_IN_SAMPLE_ARM, STRUCTURE_AWARE_ARM)
    assert E5_REPRODUCED_ARMS == (E5_COMPARATOR, E5_IN_SAMPLE_ARM)
    assert BPRIME_REPRODUCTION_KIND == "bprime-reproduction"


def test_the_reproduction_prices_arms_e_and_e_prime_at_b_primes_seeds_in_order() -> None:
    record = _record()
    cost = _RecordingCost()
    reproduction = measure_bprime_reproduction(record, E5_REPRODUCED_ARMS, cost_of=cost)

    measured_seeds = list(range(_REPLICATES))
    assert cost.seeds_of(E5_COMPARATOR) == cost.seeds_of(E5_IN_SAMPLE_ARM) == measured_seeds
    names = [policy.name for _, policy in cost.calls]
    assert names == [TUNED_STATIC_ARM] * _REPLICATES + [E5_IN_SAMPLE_ARM] * _REPLICATES
    world = e5_scenario().world
    assert world is not None
    assert len(cost.worlds) == 2 * _REPLICATES
    assert all(seen == world for seen in cost.worlds)
    arm_e = cost.calls[0][1]
    assert isinstance(arm_e, GroupParLevelReorder)
    assert arm_e.levels == record.arm_e_levels()
    arm_e_prime = cost.calls[-1][1]
    assert isinstance(arm_e_prime, NamedPolicy)
    inner = arm_e_prime.inner
    assert isinstance(inner, GroupParLevelReorder)
    assert inner.levels == record.arm_e_prime_levels()

    assert reproduction.kind == BPRIME_REPRODUCTION_KIND
    assert reproduction.seeds == record.measurement_seeds
    assert reproduction.bprime_artifact_sha256 == record.artifact_sha256
    assert [arm.arm for arm in reproduction.arms] == list(E5_REPRODUCED_ARMS)
    assert [arm.replicates for arm in reproduction.arms] == [_REPLICATES, _REPLICATES]
    assert [arm.recorded_mean for arm in reproduction.arms] == [_MEAN_E, _MEAN_E_PRIME]
    assert [arm.measured_mean for arm in reproduction.arms] == [2.375, 3.375]
    assert not reproduction.all_reproduce


@pytest.mark.parametrize(("start", "count"), [(0, 1), (300, 7), (899, 40)])
def test_the_reproduction_reads_its_seed_range_from_the_record(start: int, count: int) -> None:
    record = _record(replicates=count, measurement_seeds=SeedRange(start=start, count=count))
    cost = _RecordingCost()
    reproduction = measure_bprime_reproduction(record, ("tuned_static",), cost_of=cost)
    assert cost.seeds_of(TUNED_STATIC_ARM) == list(range(start, start + count))
    assert reproduction.seeds == SeedRange(start=start, count=count)
    assert [arm.replicates for arm in reproduction.arms] == [count]


def test_a_mean_reproduces_only_at_exact_equality_one_ulp_away_it_does_not() -> None:
    exact = _record(mean_tuned_static_cost=2.375, mean_in_sample_tuned_static_cost=3.375)
    one_ulp_off = math.nextafter(3.375, math.inf)
    near = _record(mean_tuned_static_cost=2.375, mean_in_sample_tuned_static_cost=one_ulp_off)
    same = measure_bprime_reproduction(exact, E5_REPRODUCED_ARMS, cost_of=_RecordingCost())
    off = measure_bprime_reproduction(near, E5_REPRODUCED_ARMS, cost_of=_RecordingCost())
    assert [arm.measured_mean for arm in same.arms] == [2.375, 3.375]
    assert [arm.measured_mean for arm in off.arms] == [2.375, 3.375]
    assert [arm.reproduces for arm in same.arms] == [True, True]
    assert same.all_reproduce
    assert [arm.reproduces for arm in off.arms] == [True, False]
    assert not off.all_reproduce
    assert off.arms[1].recorded_mean == one_ulp_off != 3.375


def _arm_reproduction(**overrides: object) -> ArmReproduction:
    """One admissible arm reading, with any field overridden."""
    fields: dict[str, object] = {
        "arm": "tuned_static",
        "replicates": _REPLICATES,
        "recorded_mean": 2.5,
        "measured_mean": 2.5,
        "reproduces": True,
    }
    fields.update(overrides)
    return ArmReproduction.model_validate(fields)


@pytest.mark.parametrize(
    ("measured", "recorded"), [(2.5, 2.5), (2.5, 2.25), (2.5, math.nextafter(2.5, 0.0))]
)
def test_a_stored_reproduces_that_contradicts_its_means_is_refused(
    measured: float, recorded: float
) -> None:
    derived = measured == recorded
    kept = _arm_reproduction(measured_mean=measured, recorded_mean=recorded, reproduces=derived)
    assert kept.reproduces == derived
    with pytest.raises(ValidationError, match="derived from the two means"):
        _arm_reproduction(measured_mean=measured, recorded_mean=recorded, reproduces=not derived)


_ARM_READING_DEFECTS: Final[dict[str, tuple[dict[str, object], str]]] = {
    "an integer flag": ({"reproduces": 1}, "reproduces\n.*bool_type"),
    "a NaN measured mean": ({"measured_mean": math.nan, "reproduces": False}, "measured_mean"),
    "an infinite recorded mean": (
        {"recorded_mean": math.inf, "reproduces": False},
        "recorded_mean",
    ),
    "an arm B-prime did not measure": ({"arm": DEFAULT_CONSENSUS_ARM}, "literal_error"),
    "no replicate": ({"replicates": 0}, "replicates\n.*greater_than_equal"),
    "a fractional replicate count": ({"replicates": 2.0}, "replicates\n.*int_type"),
}


@pytest.mark.parametrize("defect", sorted(_ARM_READING_DEFECTS))
def test_an_arm_reading_is_refused_unless_every_field_is_admissible(defect: str) -> None:
    overrides, needle = _ARM_READING_DEFECTS[defect]
    with pytest.raises(ValidationError, match=needle):
        _arm_reproduction(**overrides)


def _reproduction(**overrides: object) -> BprimeReproduction:
    """An admissible two-arm reproduction over B-prime's seeds, with any field overridden."""
    fields: dict[str, object] = {
        "kind": BPRIME_REPRODUCTION_KIND,
        "bprime_artifact_sha256": "0" * 64,
        "seeds": SeedRange(start=0, count=_REPLICATES),
        "arms": (_arm_reproduction(), _arm_reproduction(arm="tuned_static_in_sample")),
    }
    fields.update(overrides)
    return BprimeReproduction.model_validate(fields)


def test_all_reproduce_is_derived_from_every_arm_and_is_never_recorded() -> None:
    assert _reproduction().all_reproduce
    missed = _arm_reproduction(arm="structure_aware", measured_mean=2.25, reproduces=False)
    assert not _reproduction(arms=(_arm_reproduction(), missed)).all_reproduce
    assert "all_reproduce" not in json.loads(_reproduction().to_canonical_json())


_REPRODUCTION_DEFECTS: Final[dict[str, tuple[dict[str, object], str]]] = {
    "an arm recorded twice": (
        {"arms": (_arm_reproduction(), _arm_reproduction())},
        "more than once",
    ),
    "an arm short of the seed range": (
        {"arms": (_arm_reproduction(replicates=_REPLICATES - 1),)},
        "every one of the 200 seeds",
    ),
    "no arm": ({"arms": ()}, "no arm"),
    "an upper-case artifact digest": ({"bprime_artifact_sha256": "A" * 64}, "64 lowercase hex"),
    "another kind": ({"kind": "bprime-record-provenance"}, "kind"),
}


@pytest.mark.parametrize("defect", sorted(_REPRODUCTION_DEFECTS))
def test_a_reproduction_records_each_arm_once_at_every_one_of_its_seeds(defect: str) -> None:
    overrides, needle = _REPRODUCTION_DEFECTS[defect]
    with pytest.raises(ValidationError, match=needle):
        _reproduction(**overrides)


_REQUEST_DEFECTS: Final[dict[str, tuple[tuple[str, ...], str]]] = {
    "an arm requested twice": (
        ("tuned_static", "tuned_static_in_sample", "tuned_static"),
        "more than once",
    ),
    "no arm": ((), "no arm was requested"),
    "an arm B-prime did not measure": (("tuned_static", "consensus"), "not measured by B-prime"),
}


@pytest.mark.parametrize("defect", sorted(_REQUEST_DEFECTS))
def test_a_reproduction_request_is_refused_before_any_arm_is_priced(defect: str) -> None:
    arms, needle = _REQUEST_DEFECTS[defect]
    with pytest.raises(BprimeReproductionError, match=needle):
        measure_bprime_reproduction(
            _record(), cast("tuple[ReproducedArm, ...]", arms), cost_of=_forbidden_cost
        )


def test_a_non_finite_cost_is_refused_naming_its_arm_and_seed() -> None:
    def _nan_at_seven(seed: int, policy: DecisionPolicy, world: ResolvedWorld) -> float:
        return math.nan if seed == 7 else 1.0

    with pytest.raises(BprimeReproductionError, match="tuned_static costs nan at seed 7"):
        measure_bprime_reproduction(_record(), ("tuned_static",), cost_of=_nan_at_seven)


def test_arm_o_is_built_afresh_per_seed_exactly_as_the_six_arm_comparator_builds_it() -> None:
    """Engines here are started and never advanced; each reads arm O's SKU count, no more."""
    record = _record(replicates=3, measurement_seeds=SeedRange(start=0, count=3))
    cost = _RecordingCost()
    reproduction = measure_bprime_reproduction(record, ("structure_aware",), cost_of=cost)

    world = e5_scenario().world
    assert world is not None
    _slices, slice_hours = _cadence(24.0)
    assert cost.seeds_of(STRUCTURE_AWARE_ARM) == [0, 1, 2]
    built = [policy for _, policy in cost.calls]
    assert len({id(policy) for policy in built}) == 3
    for seed, policy in zip((0, 1, 2), built, strict=True):
        # `run_three_pass` reads the SKU count from the arm's own `_new_arm_engine` engine.
        engine = _new_arm_engine(
            seed, restock_threshold=comparator_restock_threshold(), world=world, build=None
        )
        expected = build_structure_aware_arm(
            world,
            seed=seed,
            hours=24.0,
            review_min=slice_hours * 60.0,
            n_skus=len(engine.inventory),
        )
        assert isinstance(policy, StructureAwareBaseStock)
        assert policy.world == expected.world == world
        assert policy.cost == expected.cost
        assert policy.review_min == expected.review_min == 60.0
        assert policy.rate_per_sku_per_min == expected.rate_per_sku_per_min
        assert policy.seed == expected.seed == seed
    (arm_o,) = reproduction.arms
    assert (arm_o.arm, arm_o.replicates, arm_o.recorded_mean) == ("structure_aware", 3, _MEAN_O)
    assert arm_o.measured_mean == 1.25


def test_a_reproduction_round_trips_through_its_canonical_file(tmp_path: Path) -> None:
    record = _record(mean_tuned_static_cost=2.375)
    cost = _RecordingCost()
    reproduction = measure_bprime_reproduction(record, E5_REPRODUCED_ARMS, cost_of=cost)
    target = tmp_path / "out" / "reproduction.json"
    assert write_bprime_reproduction(target, reproduction) == target
    text = target.read_text(encoding="utf-8")
    assert text == json.dumps(json.loads(text), sort_keys=True, separators=(",", ":"))
    assert text == reproduction.to_canonical_json()
    reread = read_bprime_reproduction(target)
    assert reread == reproduction
    assert [arm.reproduces for arm in reread.arms] == [True, False]


# ---------------------------------------------------------------------------
# The CLI: --suite e5-primary refuses before any replicate runs
# ---------------------------------------------------------------------------
class _ForbiddenHarness:
    """Stands in for ``UpliftHarness``: being constructed at all means a refusal did not hold."""

    def __init__(self, **kwargs: object) -> None:
        raise AssertionError(f"a refused E5 invocation constructed the harness: {kwargs}")


def _forbidden(*args: object, **kwargs: object) -> object:
    raise AssertionError("a refused E5 invocation went past its refusal")


def _cli(argv: Sequence[str], capsys: pytest.CaptureFixture[str]) -> tuple[int, str, str]:
    code = cli.main(list(argv))
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def test_the_suite_flag_defaults_to_the_canonical_suite_and_names_two() -> None:
    parser = cli._build_parser()
    assert cli.SUITES == ("canonical", E5_SUITE)
    assert parser.parse_args([]).suite == cli.CANONICAL_SUITE == "canonical"
    assert parser.parse_args(["--suite", "e5-primary"]).suite == E5_SUITE
    with pytest.raises(SystemExit):
        parser.parse_args(["--suite", "e4"])


_E5: Final[tuple[str, ...]] = ("--suite", "e5-primary")
_FORBIDDEN_FLAGS: Final[dict[str, tuple[tuple[str, ...], str]]] = {
    "smoke": ((*_E5, "--smoke", "--baseline-arm", "tuned_static"), "--smoke"),
    "a pooled comparator": ((*_E5, "--full", "--pooled-baseline"), "--pooled-baseline"),
    "no comparator": ((*_E5, "--full"), "E5 requires --baseline-arm tuned_static"),
    "another comparator": (
        (*_E5, "--full", "--baseline-arm", "tuned_static_in_sample"),
        "E5 requires --baseline-arm tuned_static",
    ),
    "replicates below the floor": (
        (*_E5, "--n", str(MIN_SCENARIOS - 1), "--baseline-arm", "tuned_static"),
        "INV-TW-002",
    ),
    "no replicate count at all": ((*_E5, "--baseline-arm", "tuned_static"), "INV-TW-002"),
    "another cadence": (
        (*_E5, "--full", "--baseline-arm", "tuned_static", "--step-hours", "0.5"),
        "--step-hours",
    ),
    "another horizon": (
        (*_E5, "--full", "--baseline-arm", "tuned_static", "--duration-hours", "4"),
        "--duration-hours",
    ),
}


@pytest.mark.parametrize("case", sorted(_FORBIDDEN_FLAGS))
def test_the_e5_suite_refuses_each_forbidden_flag_before_reading_or_running_anything(
    case: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    argv, needle = _FORBIDDEN_FLAGS[case]
    monkeypatch.setattr(cli, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(cli, "read_bprime_record", _forbidden)
    monkeypatch.setattr(cli, "build_e5_arms", _forbidden)
    monkeypatch.setattr(cli, "production_arm_cost", _forbidden_cost)
    monkeypatch.setattr(cli, "UpliftHarness", _ForbiddenHarness)
    monkeypatch.setattr(cli, "e5_consensus_policy", _forbidden)
    monkeypatch.setattr(cli, "e5_probe_observations", _forbidden)
    monkeypatch.setattr(cli, "run_pathway_probe", _forbidden)
    output = tmp_path / "out" / "result.json"
    code, out, err = _cli([*argv, "--output", str(output)], capsys)
    assert code == cli.EXIT_MISSING_INPUT
    assert needle in err
    assert "headline uplift" not in out
    assert not output.parent.exists()


def test_the_workflows_e5_invocation_without_a_committed_record_is_a_missing_input(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(cli, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(cli, "build_e5_arms", _forbidden)
    monkeypatch.setattr(cli, "production_arm_cost", _forbidden_cost)
    monkeypatch.setattr(cli, "UpliftHarness", _ForbiddenHarness)
    monkeypatch.setattr(cli, "e5_consensus_policy", _forbidden)
    monkeypatch.setattr(cli, "e5_probe_observations", _forbidden)
    monkeypatch.setattr(cli, "run_pathway_probe", _forbidden)
    output = tmp_path / "out" / "result.json"
    code, out, err = _cli([*_WORKFLOW_ARGV, "--output", str(output)], capsys)
    assert code == cli.EXIT_MISSING_INPUT
    assert "B-prime record" in err
    assert "is missing" in err
    assert "headline uplift" not in out
    assert not output.parent.exists()

    # A present record describing another physics is refused the same way.
    _write_tree(tmp_path, _artifact_payload())
    _alter_physics(tmp_path)
    code, out, err = _cli([*_WORKFLOW_ARGV, "--output", str(output)], capsys)
    assert code == cli.EXIT_MISSING_INPUT
    assert "another physics" in err
    assert not output.parent.exists()


def _stub_e5_result(arms: Sequence[ArmSpec], runs_per_arm: int) -> HarnessResult:
    """A hand-built E5 matrix: the consensus arm cheaper, and three applied of four decisions."""
    runs_by_pair: dict[tuple[str, str], list[ScenarioRun]] = {}
    for spec in arms:
        subject = spec.role == "consensus"
        runs_by_pair[(E5_SCENARIO_NAME, spec.name)] = [
            ScenarioRun(
                arm=spec.name,
                seed=i,
                kpis=_kpi(0.5 + (i % 5) * 0.125 if subject else 1.5 + (i % 3) * 0.25),
                failed=False,
                error=None,
                decision_counts=DecisionCounts(3, 1, 0, 0) if subject else None,
            )
            for i in range(runs_per_arm)
        ]
    return HarnessResult(
        arm_results={pair: aggregate_arm(pair[1], runs) for pair, runs in runs_by_pair.items()},
        runs_by_pair=runs_by_pair,
        all_runs=[run for runs in runs_by_pair.values() for run in runs],
        results_path=None,
        scenarios=(e5_scenario(),),
        arm_names=tuple(spec.name for spec in arms),
        arm_roles=registered_roles(arms),
    )


# ---------------------------------------------------------------------------
# The CLI end to end, every CI workload stood in -- R7.21's probe step included (finding 109)
# ---------------------------------------------------------------------------
#: The lines the CLI prints beside the headline for :func:`_probe_report`, in this order.
_PROBE_LINES: Final[tuple[str, ...]] = (
    "pathway probe (R7.21): on_order changed 2/3 binding decisions",
    "pathway probe (R7.21): supplier_lead_time_history changed 0/2 binding decisions",
    "pathway probe (R7.21): demand_to_date changed 1/3 binding decisions",
    "unresponsive inputs: ['supplier_lead_time_history'] -- a finding beside the headline; "
    "no input's silence relabels it (R7.21)",
)


class _ConsultablePathway:
    """The probe step's FRESH arm in a fast clause: a ``PathwayConsultant`` never consulted.

    Wherever this arm is built the probe callable is stood in, so ``consult`` fails if it is
    reached (no protocol runs) and so does ``decide`` (the probe's arm never reaches the
    harness).
    """

    name = DEFAULT_CONSENSUS_ARM
    levers = E5_CONSENSUS_LEVERS

    def decide(self, obs: Observation) -> PolicyAction:
        raise AssertionError("the probe's fresh arm decided: it reached the harness")

    def consult(self, obs: Observation) -> ConsensusOutcome:
        raise AssertionError("a stood-in probe consulted the fresh arm")


def _probe_report() -> PathwayProbeReport:
    """A report as ``run_pathway_probe`` states one: on-order stock moved 2 of 3 decisions."""
    return PathwayProbeReport(
        kind="consensus-pathway-probe",
        schema_version=1,
        arm=DEFAULT_CONSENSUS_ARM,
        levers=("reorder",),
        observations=3,
        replay_unstable=0,
        full_request_buckets=DecisionCountsRecord(
            dispatched=2,
            withheld_for_confidence=1,
            guardrail_blocked=0,
            untranslatable=0,
            total=3,
        ),
        inputs=(
            ProbeInputResult(input_name="on_order", carried=3, pairs=3, changed=2, rate=2 / 3),
            ProbeInputResult(
                input_name="supplier_lead_time_history", carried=2, pairs=2, changed=0, rate=0.0
            ),
            ProbeInputResult(
                input_name="demand_to_date", carried=3, pairs=3, changed=1, rate=1 / 3
            ),
        ),
        unresponsive_inputs=("supplier_lead_time_history",),
    )


@dataclasses.dataclass(frozen=True)
class _StubbedE5:
    """The workflow's E5 invocation with every CI workload stood in, and what each one saw."""

    output: Path
    arms: tuple[ArmSpec, ...]
    cost: _RecordingCost
    seen: dict[str, object]
    fresh: _ConsultablePathway
    sampled: list[Observation]


def _stub_e5(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> _StubbedE5:
    """Stand in for every CI workload of the workflow's E5 invocation: no twin and no protocol.

    The fake repository's B-prime record sets arm E's mean to 2.375, which the stand-in cost
    (:class:`_RecordingCost`) reproduces exactly, and keeps arm E-prime's, which it does not.
    The harness returns :func:`_stub_e5_result`. The probe step's fresh arm is a
    :class:`_ConsultablePathway`, its sampler returns one hand-built state, and the probe returns
    :func:`_probe_report`, recording what it was handed and how much had run by then. Each is a
    global of ``uplift.cli`` read at call time, which a clause re-patches to inject its case.
    """
    root = tmp_path / "repo"
    _write_tree(root, _artifact_payload(mean_tuned_static_cost=2.375))
    arms = (
        ArmSpec(_FixedPolicy(DEFAULT_CONSENSUS_ARM), "consensus"),
        ArmSpec(_FixedPolicy(E5_COMPARATOR), "baseline"),
        ArmSpec(_FixedPolicy(E5_IN_SAMPLE_ARM), "baseline"),
    )
    stub = _stub_e5_result(arms, runs_per_arm=40)
    cost = _RecordingCost()
    seen: dict[str, object] = {}
    fresh = _ConsultablePathway()
    sampled = [_observation()]

    class _StubHarness:
        def __init__(self, **kwargs: object) -> None:
            seen["init"] = kwargs

        def run(
            self, scenarios: Sequence[Scenario], specs: Sequence[ArmSpec], n_per_arm: int
        ) -> HarnessResult:
            seen["run"] = (list(scenarios), list(specs), n_per_arm)
            seen["priced_before_the_run"] = len(cost.calls)
            return stub

    def _probe(arm: PathwayConsultant, observations: Sequence[Observation]) -> PathwayProbeReport:
        seen["probe"] = (arm, observations, len(cost.calls), "run" in seen)
        return _probe_report()

    monkeypatch.setattr(cli, "REPO_ROOT", root)
    monkeypatch.setattr(cli, "build_e5_arms", lambda record: arms)
    monkeypatch.setattr(cli, "UpliftHarness", _StubHarness)
    monkeypatch.setattr(cli, "production_arm_cost", cost)
    monkeypatch.setattr(cli, "e5_consensus_policy", lambda: fresh)
    monkeypatch.setattr(cli, "e5_probe_observations", lambda: sampled)
    monkeypatch.setattr(cli, "run_pathway_probe", _probe)
    return _StubbedE5(
        output=tmp_path / "out" / "result.json",
        arms=arms,
        cost=cost,
        seen=seen,
        fresh=fresh,
        sampled=sampled,
    )


def test_the_workflows_e5_invocation_writes_the_reproduction_artifact_and_dispatch_record(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The workflow's argv end to end, with every CI workload stood in (:func:`_stub_e5`).

    The cost is :class:`_RecordingCost`, so arm E's recorded mean (2.375 here) is reproduced
    exactly while arm E-prime's (B-prime's own) is not, and both verdicts are printed. The
    dispatch record is B2's ``uplift/dispatch.py`` over the consensus arm's runs alone (API2
    amendment 1.1): handed every arm's runs, ``summarise_dispatch`` refuses. R7.21's probe runs
    first, on a FRESH arm; its report is written beside the dispatch record and its lines print
    beside the headline (finding 109), and a refusal an earlier run left behind is removed.
    """
    stubbed = _stub_e5(tmp_path, monkeypatch)
    output, arms, cost, seen = stubbed.output, stubbed.arms, stubbed.cost, stubbed.seen
    stale = output.parent / cli.PROBE_REFUSAL_FILENAME
    stale.parent.mkdir(parents=True)
    stale.write_text("{}", encoding="utf-8")
    code, out, err = _cli([*_WORKFLOW_ARGV, "--output", str(output)], capsys)

    assert code == 0, err
    init = seen["init"]
    assert isinstance(init, dict)
    assert init["loop_config"] == E5_LOOP
    assert seen["run"] == ([e5_scenario()], list(arms), MIN_SCENARIOS)

    # The reproduction ran first and in full: arms E and E' at every one of B-prime's seeds.
    assert seen["priced_before_the_run"] == len(cost.calls) == 2 * _REPLICATES
    measured_seeds = list(range(_REPLICATES))
    assert cost.seeds_of(E5_COMPARATOR) == cost.seeds_of(E5_IN_SAMPLE_ARM) == measured_seeds
    reproduction = read_bprime_reproduction(output.parent / cli.REPRODUCTION_FILENAME)
    readings = [(arm.arm, arm.measured_mean, arm.reproduces) for arm in reproduction.arms]
    assert readings == [(E5_COMPARATOR, 2.375, True), (E5_IN_SAMPLE_ARM, 3.375, False)]
    reproduced = "  tuned_static: measured 2.375, B-prime recorded 2.375 -- reproduces"
    not_reproduced = (
        "comparator at B-prime's levels, not reproduced in this environment: "
        f"tuned_static_in_sample measured 3.375, recorded {_MEAN_E_PRIME!r}"
    )
    assert out.index(reproduced) < out.index("headline uplift:") < out.index(not_reproduced)

    assert "recommendations, if executed" in out
    dispatch_line = (
        "dispatch: 120/160 binding decisions dispatched (rate 0.7500); withheld for confidence "
        "40 (applied, Q2=a); guardrail-blocked 0, untranslatable 0 (neither applied)"
    )
    assert dispatch_line in out

    artifact = UpliftArtifact.read(output)
    assert artifact.comparator == E5_COMPARATOR
    assert artifact.replicates_per_arm == MIN_SCENARIOS
    assert artifact.provenance.arms == (DEFAULT_CONSENSUS_ARM, E5_COMPARATOR, E5_IN_SAMPLE_ARM)
    assert artifact.provenance.seeds == (E5_SCENARIO_SEED,)
    dispatch_path = output.parent / cli.DISPATCH_FILENAME
    dispatch = DispatchReport.model_validate_json(dispatch_path.read_text(encoding="utf-8"))
    assert (dispatch.arm, dispatch.runs, dispatch.failed_runs) == (DEFAULT_CONSENSUS_ARM, 40, 0)
    assert (dispatch.counts.dispatched, dispatch.counts.total) == (120, 160)
    assert dispatch.dispatch_rate == 0.75

    # R7.21 (finding 109): the probe ran FIRST -- before any arm was priced and before the
    # harness -- on the FRESH arm, never the measured one, over the sampler's states.
    assert isinstance(stubbed.fresh, PathwayConsultant)
    probed = cast("tuple[object, object, int, bool]", seen["probe"])
    probed_arm, probed_states, priced_by_then, harness_ran = probed
    assert probed_arm is stubbed.fresh
    assert probed_arm is not arms[0].policy
    assert probed_states is stubbed.sampled
    assert (priced_by_then, harness_ran) == (0, False)
    probe_path = output.parent / cli.PROBE_FILENAME
    text = probe_path.read_text(encoding="utf-8")
    assert text == json.dumps(json.loads(text), sort_keys=True, separators=(",", ":"))
    assert read_probe_report(probe_path) == _probe_report()
    assert not stale.exists()
    positions = [out.index(line) for line in _PROBE_LINES]
    assert out.index("headline uplift:") < positions[0]
    assert positions == sorted(positions)
    assert positions[-1] < out.index("applied noise tolerance")
    assert f"wrote pathway probe record: {probe_path}" in out


def test_a_probe_that_states_no_rate_is_recorded_as_a_refusal_and_the_e5_run_completes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    stubbed = _stub_e5(tmp_path, monkeypatch)
    message = "no observation carries 'on_order': withholding it changes no request"

    def _zero_pairs(
        arm: PathwayConsultant, observations: Sequence[Observation]
    ) -> PathwayProbeReport:
        raise PathwayProbeError(message)

    monkeypatch.setattr(cli, "run_pathway_probe", _zero_pairs)
    output = stubbed.output
    stale = output.parent / cli.PROBE_FILENAME
    stale.parent.mkdir(parents=True)
    stale.write_text("{}", encoding="utf-8")
    code, out, err = _cli([*_WORKFLOW_ARGV, "--output", str(output)], capsys)

    assert code == 0, err
    refusal_path = output.parent / cli.PROBE_REFUSAL_FILENAME
    text = refusal_path.read_text(encoding="utf-8")
    assert text == json.dumps(json.loads(text), sort_keys=True, separators=(",", ":"))
    refusal = read_probe_refusal(refusal_path)
    assert (refusal.kind, refusal.schema_version) == ("consensus-pathway-probe-refusal", 1)
    assert refusal.arm == DEFAULT_CONSENSUS_ARM
    assert refusal.reason == f"the probe states no rate: PathwayProbeError: {message}"
    assert not stale.exists()

    # The probe's absence refused nothing: the harness ran and every record was written, and
    # beside the headline the refusal's reason is printed where the per-input lines would be.
    assert stubbed.seen["run"] == ([e5_scenario()], list(stubbed.arms), MIN_SCENARIOS)
    assert UpliftArtifact.read(output).comparator == E5_COMPARATOR
    assert (output.parent / cli.REPRODUCTION_FILENAME).is_file()
    assert (output.parent / cli.DISPATCH_FILENAME).is_file()
    refused_line = f"pathway probe (R7.21): refused: {refusal.reason}"
    assert out.index("headline uplift:") < out.index(refused_line)
    assert "pathway probe (R7.21): on_order" not in out
    assert "unresponsive inputs:" not in out
    assert f"wrote pathway probe refusal: {refusal_path}" in out


def test_a_stand_in_consensus_arm_is_recorded_as_a_refusal_before_any_state_is_sampled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    stubbed = _stub_e5(tmp_path, monkeypatch)
    stand_in = UnavailableConsensusArm("no network here")
    reached: list[str] = []

    def _sampler() -> list[Observation]:
        reached.append("sampler")
        return list(stubbed.sampled)

    def _probe(arm: PathwayConsultant, observations: Sequence[Observation]) -> PathwayProbeReport:
        reached.append("probe")
        return _probe_report()

    monkeypatch.setattr(cli, "e5_consensus_policy", lambda: stand_in)
    monkeypatch.setattr(cli, "e5_probe_observations", _sampler)
    monkeypatch.setattr(cli, "run_pathway_probe", _probe)
    output = stubbed.output
    code, out, err = _cli([*_WORKFLOW_ARGV, "--output", str(output)], capsys)

    assert code == 0, err
    assert reached == []
    refusal = read_probe_refusal(output.parent / cli.PROBE_REFUSAL_FILENAME)
    assert refusal.arm == stand_in.name == DEFAULT_CONSENSUS_ARM
    assert refusal.reason.startswith(
        "the consensus arm built for the probe is UnavailableConsensusArm, not a pathway the "
        "probe can consult"
    )
    # The stand-in's own reason travels with the refusal: why there was no pathway, as well as
    # that there was none.
    assert refusal.reason.endswith(f"(the stand-in's own reason: {stand_in.reason})")
    assert not (output.parent / cli.PROBE_FILENAME).exists()
    assert stubbed.seen["run"] == ([e5_scenario()], list(stubbed.arms), MIN_SCENARIOS)
    assert UpliftArtifact.read(output).comparator == E5_COMPARATOR
    refused_line = f"pathway probe (R7.21): refused: {refusal.reason}"
    assert out.index("headline uplift:") < out.index(refused_line)


# ---------------------------------------------------------------------------
# The probe's refusal record (finding 109)
# ---------------------------------------------------------------------------
def _refusal_payload(**overrides: object) -> dict[str, object]:
    """An admissible refusal as its JSON carries it, with any field overridden."""
    payload: dict[str, object] = {
        "kind": "consensus-pathway-probe-refusal",
        "schema_version": 1,
        "arm": DEFAULT_CONSENSUS_ARM,
        "reason": "the probe states no rate: PathwayProbeError: zero pairs",
    }
    payload.update(overrides)
    return payload


_REFUSAL_DEFECTS: Final[dict[str, tuple[dict[str, object], str]]] = {
    "a blank reason": ({"reason": " \t\n"}, "states no reason"),
    "another kind": ({"kind": "consensus-pathway-probe"}, "kind\n.*literal_error"),
    "another schema version": ({"schema_version": 2}, "schema_version\n.*literal_error"),
    "a blank arm": ({"arm": "   "}, "does not name an arm"),
    "an arm padded with space": ({"arm": f" {DEFAULT_CONSENSUS_ARM}"}, "does not name an arm"),
    "an unrecorded field": ({"rate": 0.0}, "rate\n.*extra_forbidden"),
}


@pytest.mark.parametrize("defect", sorted(_REFUSAL_DEFECTS))
def test_a_probe_refusal_names_an_arm_and_a_reason_and_is_of_its_own_kind(defect: str) -> None:
    overrides, needle = _REFUSAL_DEFECTS[defect]
    admitted = PathwayProbeRefusal.model_validate(_refusal_payload())
    assert admitted == PathwayProbeRefusal.of(arm=DEFAULT_CONSENSUS_ARM, reason=admitted.reason)
    with pytest.raises(ValidationError, match=needle):
        PathwayProbeRefusal.model_validate(_refusal_payload(**overrides))


_stated_arms = _names.filter(lambda name: name == name.strip())
_stated_reasons = st.text(min_size=1).filter(lambda text: bool(text.strip()))


@given(arm=_stated_arms, reason=_stated_reasons)
def test_a_probe_refusal_round_trips_canonically_whatever_reason_it_states(
    arm: str, reason: str
) -> None:
    refusal = PathwayProbeRefusal.of(arm=arm, reason=reason)
    text = refusal.to_canonical_json()
    assert text == json.dumps(json.loads(text), sort_keys=True, separators=(",", ":"))
    assert json.loads(text) == {
        "arm": arm,
        "kind": "consensus-pathway-probe-refusal",
        "reason": reason,
        "schema_version": 1,
    }
    assert PathwayProbeRefusal.model_validate_json(text) == refusal


def test_the_dispatch_line_states_why_no_rate_exists_and_never_prints_a_rate_of_zero() -> None:
    failed = [
        ScenarioRun(arm=DEFAULT_CONSENSUS_ARM, seed=i, kpis=None, failed=True, error="x")
        for i in range(3)
    ]
    report = summarise_dispatch(failed, arm=DEFAULT_CONSENSUS_ARM)
    assert report.dispatch_rate is None
    reason = report.rate_unavailable_reason
    assert reason is not None
    assert reason.strip()
    scope, line = cli._dispatch_lines(report)
    assert "recommendations, if executed" in scope
    expected = f"dispatch: 0/0 binding decisions dispatched (rate unavailable: {reason});"
    assert line.startswith(expected)
    assert "rate 0" not in line


def test_beside_the_headline_a_reproduced_comparator_is_named_reproduced_exactly() -> None:
    record = _record(mean_tuned_static_cost=2.375, mean_in_sample_tuned_static_cost=3.375)
    cost = _RecordingCost()
    reproduction = measure_bprime_reproduction(record, E5_REPRODUCED_ARMS, cost_of=cost)
    assert reproduction.all_reproduce
    expected = (
        "comparator at B-prime's levels, reproduced exactly in this environment "
        "(tuned_static, tuned_static_in_sample)"
    )
    assert cli._comparator_line(reproduction) == expected


# ---------------------------------------------------------------------------
# Slow: the real SimPy twin (CI only)
# ---------------------------------------------------------------------------
class _UnflooredHarness(UpliftHarness):
    """Lifts the INV-TW-002 floor and nothing else, for a three-seed run.

    The floor is ``run_arm_on_seeds``' own refusal, proven by name in
    ``test_run_arm_on_seeds_refuses_before_any_twin_is_built``; seed identity is clause (b)'s
    subject, and three seeds at E5's own loop show it at a sliver of a powered run's cost --
    the pattern ``test_replicate_seed_arm_independence_property.py`` already uses.
    """

    @staticmethod
    def _check_power(n: int) -> None:
        return None


@pytest.mark.slow
def test_the_harness_prices_arm_e_exactly_as_the_regret_comparator_does() -> None:
    """(a) ``run_closed_loop`` under E5 and ``foresight.run_single_arm`` agree to the bit.

    The regret side restates ``uplift/regret.py::_measure``'s five engine reads (its
    ``_observation`` is a closure, not importable) and prices them with the committed
    objective. DOMAIN: exact while no ``TW_ORDER_ARRIVAL_RATE``/``TW_PICK_PACK_MEAN_MIN`` moves
    ``TwinConfig``'s defaults, which ``_build_twin`` pins and ``_new_arm_engine`` reads; the
    precondition is asserted, so a moved default fails here rather than loosening the equality.
    """
    defaults = TwinConfig()
    assert (defaults.order_arrival_rate, defaults.pick_pack_mean_min) == (2.0, 8.0)
    record = _record()
    scenario = e5_scenario()
    assert scenario.world is not None
    arm_e = e5_baseline_arms(record)[0].policy
    objective = committed_objective()
    costs: list[float] = []
    for seed in e5_replicate_seeds(3, record):
        run = run_closed_loop(scenario, arm_e, seed, arm_e.name, E5_LOOP)
        assert not run.failed, run.error
        assert run.kpis is not None
        sim = run_single_arm(
            seed,
            hours=E5_HOURS,
            restock_threshold=comparator_restock_threshold(),
            policy=arm_e,
            world=scenario.world,
        )
        metrics = sim.metrics
        regret_cost = objective.cost(
            stockout_rate=metrics.stockout_rate,
            spoilage_rate=metrics.spoilage_rate,
            fill_rate=metrics.fill_rate,
            avg_on_hand_units=metrics.avg_on_hand_units(sim.sim_time_min),
            avg_delivery_time_min=metrics.avg_delivery_time_min,
        )
        assert run.kpis.objective == regret_cost
        costs.append(regret_cost)
    assert len(costs) == 3
    assert len(set(costs)) > 1, "three seeds priced identically: the twin ignored its seed"


@pytest.mark.slow
def test_run_arm_on_seeds_uses_each_given_seed_as_the_twin_seed() -> None:
    """(b) Each run equals ``run_closed_loop`` at the given seed itself, in the given order."""
    scenario = e5_scenario()
    spec = e5_baseline_arms(_record())[0]
    seeds = [11, 3, 7]
    runs = _UnflooredHarness(loop_config=E5_LOOP).run_arm_on_seeds(
        scenario, spec, seeds, parallel=False
    )
    assert [run.seed for run in runs] == seeds
    for seed, run in zip(seeds, runs, strict=True):
        assert not run.failed, run.error
        assert run == run_closed_loop(scenario, spec.policy, seed, spec.name, E5_LOOP)
    assert len({run.kpis for run in runs}) == len(seeds)


_TALLY_LOOP: Final[LoopConfig] = LoopConfig(duration_hours=2.0, step_hours=1.0, levers="all")
_PLAIN_SCENARIO: Final[Scenario] = Scenario(name="tally", seed=9, shock=ShockParams())


@pytest.mark.slow
def test_a_run_scoped_policys_tally_reaches_its_run_and_a_failed_run_records_none() -> None:
    """(c) Completed: the tally is attached. Failed: ``None``, and the run is still closed."""
    policy = _TallyingPolicy()
    run = run_closed_loop(_PLAIN_SCENARIO, policy, 21, policy.name, _TALLY_LOOP)
    assert not run.failed, run.error
    assert run.decision_counts == DecisionCounts(_TALLY_LOOP.n_steps, 0, 0, 0)
    assert (policy.opened, policy.closed) == ([21], 1)

    failing = _TallyingPolicy(fail_at=1)
    for seed in (22, 23):
        failed = run_closed_loop(_PLAIN_SCENARIO, failing, seed, failing.name, _TALLY_LOOP)
        assert failed.failed
        assert failed.decision_counts is None
        assert failed.error is not None
        assert "stub decision failure" in failed.error
        assert "already open" not in failed.error
    # Two runs opened and both were closed: the pairing is total, failure included.
    assert (failing.opened, failing.closed) == ([22, 23], 2)

    mistallied = _MistalliedPolicy()
    refused = run_closed_loop(_PLAIN_SCENARIO, mistallied, 24, mistallied.name, _TALLY_LOOP)
    assert refused.failed
    assert refused.decision_counts is None
    assert refused.error is not None
    assert "not DecisionCounts" in refused.error

    unscoped = run_closed_loop(_PLAIN_SCENARIO, _FixedPolicy("plain"), 25, "plain", _TALLY_LOOP)
    assert not unscoped.failed, unscoped.error
    assert unscoped.decision_counts is None


@pytest.mark.slow
def test_under_reorders_only_a_price_the_policy_sets_is_never_applied() -> None:
    """(d) A price the policy sets moves the run under every lever, never under reorders-only."""
    reorders_only = dataclasses.replace(_TALLY_LOOP, levers="reorders_only")
    priced = _PricedReorderPolicy("priced", price=10.0)
    plain = _PricedReorderPolicy("plain", price=None)

    priced_ro = run_closed_loop(_PLAIN_SCENARIO, priced, 31, "arm", reorders_only)
    plain_ro = run_closed_loop(_PLAIN_SCENARIO, plain, 31, "arm", reorders_only)
    assert not priced_ro.failed, priced_ro.error
    assert priced_ro == plain_ro
    assert priced_ro.kpis is not None
    assert priced_ro.kpis.margin == 0.0

    # Non-vacuous: with every lever applied, the same price moves the run.
    priced_all = run_closed_loop(_PLAIN_SCENARIO, priced, 31, "arm", _TALLY_LOOP)
    assert priced_all.kpis is not None
    assert priced_all.kpis.margin > 0.0
    assert priced_all.kpis != priced_ro.kpis


@pytest.mark.slow
def test_production_arm_cost_is_the_committed_objective_of_one_single_arm_replicate() -> None:
    """(e) At ONE seed, B-prime's first measurement seed, the five reads are taken here.

    ``production_arm_cost`` prices what ``run_single_arm`` measures, through exactly the reads
    ``uplift/regret.py::_measure._observation`` makes; the equality is ``==`` on floats.
    """
    record = _record()
    world = e5_scenario().world
    assert world is not None
    arm_e = e5_baseline_arms(record)[0].policy
    seed = record.measurement_seeds.start
    sim = run_single_arm(
        seed,
        hours=24.0,
        restock_threshold=comparator_restock_threshold(),
        policy=arm_e,
        world=world,
    )
    metrics = sim.metrics
    expected = committed_objective().cost(
        stockout_rate=metrics.stockout_rate,
        spoilage_rate=metrics.spoilage_rate,
        fill_rate=metrics.fill_rate,
        avg_on_hand_units=metrics.avg_on_hand_units(sim.sim_time_min),
        avg_delivery_time_min=metrics.avg_delivery_time_min,
    )
    assert math.isfinite(expected)
    assert expected > 0.0
    assert production_arm_cost(seed, arm_e, world) == expected


@pytest.mark.slow
def test_the_positive_controls_arm_o_prices_exactly_as_the_reproduction_measures_it() -> None:
    """(f) Arm O through the harness, as the positive control drives it, equals B-prime's arm O.

    The R6.3 agreement rule compares the harness's E - O, from ``uplift.controls_run``'s positive
    leg, with B-prime's, measured through ``foresight.run_single_arm``. Clause (a) pins arm E
    across those two paths; this pins arm O, each side built as its own measurement builds it:
    the positive leg's ONE arm O (``structure_aware_arm`` at ``ARM_CONSTRUCTION_SEED``) driven
    through ``run_arm_on_seeds`` over the first three seeds of the positive range, sequentially
    (one instance across seeds, the stricter of the harness's two drives: a pool hands each
    worker a copy), and the reproduction's FRESH arm O per seed (``e5_suite``'s builder) priced
    by ``production_arm_cost``. Equal at every seed, a disagreement between the two estimates of
    E - O is their seed sets', not the instrument's (finding 117).
    """
    defaults = TwinConfig()
    assert (defaults.order_arrival_rate, defaults.pick_pack_mean_min) == (2.0, 8.0)
    scenario = e5_scenario()
    world = scenario.world
    assert world is not None
    arm_o = structure_aware_arm(world, stocked_skus(ARM_CONSTRUCTION_SEED, world=world), E5_LOOP)
    seeds = [POSITIVE_START + offset for offset in range(3)]
    runs = _UnflooredHarness(loop_config=E5_LOOP).run_arm_on_seeds(
        scenario, ArmSpec(arm_o, "baseline"), seeds, parallel=False
    )
    assert [run.seed for run in runs] == seeds
    harness_costs: list[float] = []
    for run in runs:
        assert not run.failed, run.error
        assert run.kpis is not None
        harness_costs.append(run.kpis.objective)
    reproduced_costs = [
        production_arm_cost(seed, _structure_aware_arm(world, seed), world) for seed in seeds
    ]
    assert harness_costs == reproduced_costs
    assert len(set(reproduced_costs)) == len(seeds), "three seeds priced alike: the seed is unread"
