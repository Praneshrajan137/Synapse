"""E3's controls runner: the committed seed plan, each leg's record, and the verdict over them.

Feature: decision-quality-proof, task 16.7's second subject (R6.1-R6.5, R6.14, R6.15). Subject:
``uplift/controls_run.py``. No property number: these are the module's fast clauses, and the
property inventory is not this file's to extend.

**What would make the subject wrong**, one clause each: (a) a committed range sharing a seed with
another range, with B-prime's tuning or measurement seeds, or with E5's replicate seeds; (b) a
refusal -- an overlapping plan, an undeclared repetition, misnamed arms, a reproduction of another
B-prime record -- reached only after the runner ran; (c) a leg that pairs the survivors of a failed
replicate, or a record read back whose interval or costs were edited; (d) a verdict that exits
non-zero because a control FAILED, or that judges anything but exactly the declared records; (e)
an agreement reading formed against B-prime's split while one of B-prime's arms does not
reproduce in the leg's environment.

**Fast and pure.** Legs run through a scripted ``ArmRunner`` and a stub B-prime reproduction, so
no twin runs, and the verdict is judged over a small injected plan (the committed plan is pinned
separately, by arithmetic), so each paired interval costs milliseconds. Every cost is a dyadic
fraction, so every paired difference is exact. One clause starts an engine without advancing it
(arm E's catalogue probe). The production runner is checked with the harness class replaced by a
recorder, and against the real harness only where it refuses before any twin is built.

**No slow test, deliberately.** The only honest one is a full ``MIN_POWERED_REPLICATES`` leg, the
category-4 workload ``uplift.yml::uplift-controls`` runs; a one-seed probe would have to bypass
``_check_power``, which is forbidden. Budget inherited from the root ``conftest.py`` profile: no
example count is set or asserted.
"""

from __future__ import annotations

import hashlib
import itertools
import json
import math
import statistics
from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING, Final

import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError

from digital_twin.simulation.monte_carlo import ShockParams
from digital_twin.simulation.policy import detection_probability, negative_control_settings
from uplift import controls_run
from uplift.bprime_record import BprimeRecord
from uplift.contract import load_contract
from uplift.controls import JudgedInterval, SeedRange, classify_agreement
from uplift.controls_run import (
    AGREEMENT_VERDICT_NAME,
    EXIT_REFUSED,
    EXIT_WRITTEN,
    NEGATIVE_COMPARATOR_ARM,
    NEGATIVE_STRIDE,
    NEGATIVE_SUBJECT_ARM,
    NEGATIVE_SUBJECT_START,
    NEGATIVE_VERDICT_NAME,
    POSITIVE_RECORD_NAME,
    POSITIVE_START,
    POSITIVE_VERDICT_NAME,
    POWER_REPORT_ABSENT_NAME,
    POWER_REPORT_NAME,
    AgreementVerdictRecord,
    ControlProvenance,
    ControlSetup,
    ControlsRunError,
    HarnessArmRunner,
    LoopRecord,
    NegativeRepetitionRecord,
    NegativeVerdictRecord,
    PositiveControlRecord,
    PositiveVerdictRecord,
    PowerReportAbsence,
    SeedPlan,
    VerdictInputs,
    committed_seed_plan,
    measure_negative,
    measure_positive,
    negative_record_name,
    negative_seed_ranges,
    production_arm_runner,
    refuse_seed_overlaps,
    resolve_control_provenance,
    verdict_command,
    write_record,
)
from uplift.e5_suite import (
    E5_IN_SAMPLE_ARM,
    E5_LOOP,
    REPRODUCED_ARMS,
    ArmReproduction,
    BprimeReproduction,
    e5_baseline_arms,
    e5_replicate_seeds,
)
from uplift.harness import UNATTRIBUTED, ArtifactInterval
from uplift.interfaces import ArmSpec, KpiVector, Scenario, ScenarioRun
from uplift.oracle_arm import STRUCTURE_AWARE_ARM
from uplift.policies import NamedPolicy
from uplift.power import POWER_SOURCE_SET, describes_revision, read_power_report
from uplift.tuned_static import TUNED_STATIC_ARM, GroupParLevelReorder
from uplift.uplift_floor import MIN_POWERED_REPLICATES

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence
    from pathlib import Path

    from uplift.harness import LoopConfig
    from uplift.interfaces import Observation, PolicyAction

#: The committed Metric_Contract and ADR-055 D6's two numbers, read once, never restated.
_CONTRACT = load_contract()
_MARGIN: Final[float] = _CONTRACT.materiality_margin
_COMMITTED_SETS, _MAX_PROVEN_GAIN_RATE = negative_control_settings()

# ---------------------------------------------------------------------------
# B-prime's measured facts: run 36860454801 at ec0eb91, artifact `twin-regret-primary`
# ---------------------------------------------------------------------------
_TUNING_SEEDS: Final[tuple[int, ...]] = tuple(range(1000, 1100))
_MEASUREMENT: Final[SeedRange] = SeedRange(start=0, count=200)
#: A FIXTURE digest standing in for the B-prime artifact's sha256.
_BPRIME_SHA: Final[str] = "0" * 64
_RECORDED_MEANS: Final[dict[str, float]] = {
    TUNED_STATIC_ARM: 2.458528200722326,
    E5_IN_SAMPLE_ARM: 2.4571572385261105,
    STRUCTURE_AWARE_ARM: 2.2122412077607727,
}
_E_MINUS_O: Final[JudgedInterval] = JudgedInterval(
    low=0.21442051306302964,
    high=0.275995635964435,
    point=0.2462869929615538,
    alpha=_CONTRACT.alpha,
)
_E_MINUS_D: Final[JudgedInterval] = JudgedInterval(
    low=0.5958317971588388,
    high=0.6660569949084235,
    point=0.6295348427901005,
    alpha=_CONTRACT.alpha,
)

# ---------------------------------------------------------------------------
# A plan small enough that each interval costs milliseconds: two repetitions of four replicates
# ---------------------------------------------------------------------------
_N: Final[int] = 4
_PLAN: Final[SeedPlan] = SeedPlan(
    negative=(
        (SeedRange(start=10_000, count=_N), SeedRange(start=10_100, count=_N)),
        (SeedRange(start=10_200, count=_N), SeedRange(start=10_300, count=_N)),
    ),
    positive=SeedRange(start=10_400, count=_N),
)
#: E5's replicate seeds as this file's setups declare them: a non-empty set clear of the plan.
_E5_SEEDS: Final[tuple[int, ...]] = (30_001, 30_002, 30_003)
_PROVENANCE: Final[ControlProvenance] = ControlProvenance(
    revision="a" * 40,
    run_id="run-controls-test",
    bprime_artifact_sha256=_BPRIME_SHA,
    scenario="controls-test",
    loop=LoopRecord.of(E5_LOOP),
)
_SCENARIO: Final[Scenario] = Scenario(name="controls-test", seed=0, shock=ShockParams())
#: The records a verdict writes besides its Power_Report, or the record of why there is none.
_READINGS: Final[tuple[str, ...]] = (
    AGREEMENT_VERDICT_NAME,
    NEGATIVE_VERDICT_NAME,
    POSITIVE_VERDICT_NAME,
)

# Each script prices an arm by name and seed. The plan's ranges all start on a multiple of four.
#: Each comparator copy costs exactly 1 more: every repetition proves a gain, so the control FAILS.
_GAINFUL_NEGATIVE: Final[dict[str, Callable[[int], float]]] = {
    NEGATIVE_SUBJECT_ARM: lambda seed: 1.0 + (seed % 4) / 16,
    NEGATIVE_COMPARATOR_ARM: lambda seed: 2.0 + (seed % 4) / 16,
}
#: Paired differences of +-1/8 in turn: no repetition proves anything, so the control passes.
_NULL_NEGATIVE: Final[dict[str, Callable[[int], float]]] = {
    NEGATIVE_SUBJECT_ARM: lambda seed: 2.0 + (seed % 2) / 8,
    NEGATIVE_COMPARATOR_ARM: lambda seed: 2.0 + ((seed + 1) % 2) / 8,
}
#: E - O between 1/4 and 1/4 + 3/128, inside B-prime's E - O: detected, and in agreement.
_DETECTED_POSITIVE: Final[dict[str, Callable[[int], float]]] = {
    STRUCTURE_AWARE_ARM: lambda seed: 2.25,
    TUNED_STATIC_ARM: lambda seed: 2.5 + (seed % 4) / 128,
}
#: E - O of +-1/8 in turn: the interval contains zero, so the positive control MISSES.
_MISSED_POSITIVE: Final[dict[str, Callable[[int], float]]] = {
    STRUCTURE_AWARE_ARM: lambda seed: 2.375 + (seed % 2) / 4,
    TUNED_STATIC_ARM: lambda seed: 2.5,
}
#: Both controls pass on this script.
_PASSING: Final[dict[str, Callable[[int], float]]] = {**_NULL_NEGATIVE, **_DETECTED_POSITIVE}


# ---------------------------------------------------------------------------
# Stand-ins: no twin, no harness
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class _Arm:
    """A policy named as an arm and never asked to decide: the scripted runner prices it."""

    name: str

    def decide(self, obs: Observation) -> PolicyAction:
        raise AssertionError(f"{self.name} was asked to decide, so a fast test drove a twin")


def _kpis(objective: float) -> KpiVector:
    """A completed run's KPIs; a control leg reads ``objective`` alone."""
    return KpiVector(
        fill_rate=1.0,
        spoilage_rate=0.0,
        stockout_rate=0.0,
        avg_delivery_time_min=0.0,
        margin=0.0,
        co2_estimate=0.0,
        avg_on_hand_units=0.0,
        objective=objective,
    )


@dataclass
class _ScriptedRunner:
    """An ``ArmRunner`` that runs no twin: arm ``a`` at ``seed`` costs ``costs[a](seed)``."""

    costs: Mapping[str, Callable[[int], float]]
    fail_at: frozenset[tuple[str, int]] = frozenset()
    calls: list[tuple[str, tuple[int, ...]]] = field(default_factory=list)
    specs: list[ArmSpec] = field(default_factory=list)

    def __call__(
        self, scenario: Scenario, spec: ArmSpec, seeds: Sequence[int]
    ) -> list[ScenarioRun]:
        self.calls.append((spec.name, tuple(seeds)))
        self.specs.append(spec)
        return [self._run(spec.name, seed) for seed in seeds]

    def _run(self, arm: str, seed: int) -> ScenarioRun:
        if (arm, seed) in self.fail_at:
            return ScenarioRun(
                arm=arm, seed=seed, kpis=None, failed=True, error=f"scripted failure at {seed}"
            )
        cost = self.costs[arm](seed)
        return ScenarioRun(arm=arm, seed=seed, kpis=_kpis(cost), failed=False, error=None)


def _seeds(span: SeedRange) -> list[int]:
    return list(range(span.start, span.stop))


def _bytes(directory: Path, name: str) -> bytes:
    return (directory / name).read_bytes()


def _names(directory: Path) -> list[str]:
    return sorted(entry.name for entry in directory.iterdir())


def _sha256_of(costs: Sequence[float]) -> str:
    """sha256 of the compact JSON array of ``costs``, computed here rather than by the subject."""
    text = json.dumps(list(costs), separators=(",", ":"))
    return hashlib.sha256(text.encode("ascii")).hexdigest()


def _bprime_record() -> BprimeRecord:
    """B-prime's record in memory, from its measured facts; the revision is a FIXTURE."""
    return BprimeRecord.model_validate(
        {
            "source_run_id": "36860454801",
            "source_revision_sha": "ec0eb91" + "0" * 33,
            "artifact_sha256": _BPRIME_SHA,
            "cell": "primary",
            "replicates": _MEASUREMENT.count,
            "hours_per_replicate": 24.0,
            "tuning_seeds": _TUNING_SEEDS,
            "measurement_seeds": _MEASUREMENT,
            "tuned_static_levels": {
                "sup_a": {"S": 127, "s": 118},
                "sup_b": {"S": 163, "s": 155},
                "sup_c": {"S": 183, "s": 173},
            },
            "in_sample_levels": {
                "sup_a": {"S": 127, "s": 119},
                "sup_b": {"S": 163, "s": 155},
                "sup_c": {"S": 183, "s": 173},
            },
            "e_minus_o": _E_MINUS_O.model_dump(exclude={"alpha"}),
            "e_minus_d": _E_MINUS_D.model_dump(exclude={"alpha"}),
            "alpha": 0.05,
            "mean_tuned_static_cost": _RECORDED_MEANS[TUNED_STATIC_ARM],
            "mean_in_sample_tuned_static_cost": _RECORDED_MEANS[E5_IN_SAMPLE_ARM],
            "mean_structure_aware_cost": _RECORDED_MEANS[STRUCTURE_AWARE_ARM],
        }
    )


def _reproduction(
    *,
    missing: Sequence[str] = (),
    arms: Sequence[str] = REPRODUCED_ARMS,
    seeds: SeedRange = _MEASUREMENT,
    sha256: str = _BPRIME_SHA,
) -> BprimeReproduction:
    """Stub of B-prime's arms re-measured at ``seeds``; each arm in ``missing`` misses its mean."""
    readings = tuple(
        ArmReproduction.model_validate(
            {
                "arm": arm,
                "replicates": seeds.count,
                "recorded_mean": _RECORDED_MEANS[arm],
                "measured_mean": _RECORDED_MEANS[arm] + (0.125 if arm in missing else 0.0),
                "reproduces": arm not in missing,
            }
        )
        for arm in arms
    )
    return BprimeReproduction.model_validate(
        {
            "kind": "bprime-reproduction",
            "bprime_artifact_sha256": sha256,
            "seeds": seeds,
            "arms": readings,
        }
    )


def _setup(
    *,
    plan: SeedPlan = _PLAN,
    tuning_seeds: tuple[int, ...] = _TUNING_SEEDS,
    measurement_seeds: SeedRange = _MEASUREMENT,
    e5_seeds: tuple[int, ...] = _E5_SEEDS,
) -> ControlSetup:
    """A setup over this file's plan and B-prime's seeds, with any of the four replaced."""
    return ControlSetup(
        plan=plan,
        tuning_seeds=tuning_seeds,
        measurement_seeds=measurement_seeds,
        e5_seeds=e5_seeds,
        scenario=_SCENARIO,
        contract=_CONTRACT,
        provenance=_PROVENANCE,
    )


def _positive_record(
    runner: _ScriptedRunner, reproduction: BprimeReproduction
) -> PositiveControlRecord:
    return measure_positive(
        setup=_setup(),
        arm_o=_Arm(STRUCTURE_AWARE_ARM),
        arm_e=_Arm(TUNED_STATIC_ARM),
        runner=runner,
        reproduction=reproduction,
    )


def _write_records(
    directory: Path, runner: _ScriptedRunner, reproduction: BprimeReproduction
) -> None:
    """Every record the verdict reads, measured by the subject's own legs over ``runner``."""
    setup = _setup()
    for index in range(len(_PLAN.negative)):
        record = measure_negative(index, setup=setup, arm_e=_Arm(TUNED_STATIC_ARM), runner=runner)
        write_record(directory / negative_record_name(index), record)
    write_record(directory / POSITIVE_RECORD_NAME, _positive_record(runner, reproduction))


def _source_tree(root: Path) -> Path:
    """One stand-in file per ``POWER_SOURCE_SET`` pattern: the tree a Power_Report digests here."""
    for pattern in POWER_SOURCE_SET:
        stand_in = root / pattern.replace("*", "stand_in")
        stand_in.parent.mkdir(parents=True, exist_ok=True)
        stand_in.write_text(f"# stands in for {pattern}\n", encoding="utf-8")
    return root


def _inputs(tree: Path, *, margin: float | None) -> VerdictInputs:
    """The verdict's inputs over this file's plan, B-prime's split and a stand-in source tree."""
    return VerdictInputs(
        plan=_PLAN,
        max_proven_gain_rate=_MAX_PROVEN_GAIN_RATE,
        comparator_e_minus_o=_E_MINUS_O,
        ceiling_e_minus_d=_E_MINUS_D,
        bprime_artifact_sha256=_BPRIME_SHA,
        bprime_measurement_seeds=_MEASUREMENT,
        loop=_PROVENANCE.loop,
        contract=_CONTRACT,
        alpha=_CONTRACT.alpha,
        detection_probability=detection_probability(),
        materiality_margin=margin,
        root=_source_tree(tree),
    )


def _controls_lines(printed: str) -> list[str]:
    return [line for line in printed.splitlines() if line.startswith("[controls]")]


# ---------------------------------------------------------------------------
# The committed seed plan
# ---------------------------------------------------------------------------
def test_the_committed_plan_is_every_declared_repetition_on_disjoint_powered_ranges() -> None:
    plan = committed_seed_plan(_COMMITTED_SETS)
    ranges = [span for _, span in plan.ranges()]

    assert len(plan.negative) == _COMMITTED_SETS
    assert len(ranges) == 2 * _COMMITTED_SETS + 1
    assert {span.count for span in ranges} == {MIN_POWERED_REPLICATES}
    assert plan.positive == SeedRange(start=POSITIVE_START, count=MIN_POWERED_REPLICATES)
    for index, pair in enumerate(plan.negative):
        assert pair == negative_seed_ranges(index, replicates=MIN_POWERED_REPLICATES)
    for first, second in itertools.combinations(ranges, 2):
        assert not first.overlaps(second), (first, second)


def test_the_committed_plan_holds_no_b_prime_tuning_or_measurement_seed_and_no_e5_seed() -> None:
    """E5's seeds are DERIVED by ``replicate_seed``, so their clearance is computed here."""
    plan = committed_seed_plan(_COMMITTED_SETS)
    e5_seeds = e5_replicate_seeds(MIN_POWERED_REPLICATES, _bprime_record())
    measured = range(_MEASUREMENT.start, _MEASUREMENT.stop)
    others = {*_TUNING_SEEDS, *measured, *e5_seeds}

    assert len(e5_seeds) == MIN_POWERED_REPLICATES
    assert len(others) == len(_TUNING_SEEDS) + _MEASUREMENT.count + MIN_POWERED_REPLICATES
    for label, span in plan.ranges():
        held = sorted(seed for seed in others if span.start <= seed < span.stop)
        assert held == [], (label, held[:5])
    refuse_seed_overlaps(
        plan, tuning_seeds=_TUNING_SEEDS, measurement_seeds=_MEASUREMENT, e5_seeds=e5_seeds
    )


def test_the_bases_hold_the_committed_count_and_refuse_one_repetition_past_capacity() -> None:
    capacity = (POSITIVE_START - NEGATIVE_SUBJECT_START) // NEGATIVE_STRIDE

    assert capacity >= _COMMITTED_SETS
    assert len(committed_seed_plan(capacity).negative) == capacity
    with pytest.raises(ControlsRunError, match="share seeds"):
        committed_seed_plan(capacity + 1)


@pytest.mark.parametrize("sets", [0, -1, True])
def test_a_plan_of_no_declared_repetition_is_refused(sets: int) -> None:
    with pytest.raises(ControlsRunError, match="at least one repetition"):
        committed_seed_plan(sets)


@given(
    start=st.integers(min_value=0, max_value=1_000_000),
    count=st.integers(min_value=1, max_value=50),
    shift=st.integers(min_value=0, max_value=49),
    slots=st.sampled_from(tuple(itertools.combinations(range(5), 2))),
)
def test_a_plan_with_any_two_ranges_sharing_a_seed_is_refused(
    start: int, count: int, shift: int, slots: tuple[int, int]
) -> None:
    """Any two of a two-repetition plan's five ranges: within, across, or with the positive."""
    spans = [SeedRange(start=2_000_000 + 1_000 * slot, count=count) for slot in range(5)]
    spans[slots[0]] = SeedRange(start=start, count=count)
    spans[slots[1]] = SeedRange(start=start + shift % count, count=count)

    with pytest.raises(ControlsRunError, match="share seeds"):
        SeedPlan(negative=((spans[0], spans[1]), (spans[2], spans[3])), positive=spans[4])


def test_a_plan_whose_ranges_run_different_counts_is_refused() -> None:
    pair = (SeedRange(start=0, count=4), SeedRange(start=10, count=5))
    with pytest.raises(ControlsRunError, match="one count per arm"):
        SeedPlan(negative=(pair,), positive=SeedRange(start=20, count=4))


def _touching_setup(touching: str) -> ControlSetup:
    inside = _PLAN.positive.start + 1
    if touching == "a tuning seed":
        return _setup(tuning_seeds=(*_TUNING_SEEDS, inside))
    if touching == "the measurement range":
        return _setup(measurement_seeds=SeedRange(start=inside, count=_MEASUREMENT.count))
    if touching == "an E5 seed":
        return _setup(e5_seeds=(*_E5_SEEDS, inside))
    if touching == "no tuning seed":
        return _setup(tuning_seeds=())
    if touching == "no E5 seed":
        return _setup(e5_seeds=())
    raise AssertionError(f"no setup is declared for {touching!r}")


@pytest.mark.parametrize(
    ("touching", "needle"),
    [
        ("a tuning seed", "B-prime's tuning seeds"),
        ("the measurement range", "B-prime's measurement"),
        ("an E5 seed", "E5 suite's replicate seeds"),
        ("no tuning seed", "vacuous"),
        ("no E5 seed", "vacuous"),
    ],
)
def test_a_setup_touching_the_seeds_it_is_read_beside_is_refused_on_construction(
    touching: str, needle: str
) -> None:
    """No setup exists for such a plan, so no leg can: the refusal precedes every arm."""
    with pytest.raises(ControlsRunError, match=needle):
        _touching_setup(touching)


# ---------------------------------------------------------------------------
# The legs
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("repetition", [-1, 2, True])
def test_an_undeclared_repetition_is_refused_before_the_runner_is_called(repetition: int) -> None:
    runner = _ScriptedRunner(_NULL_NEGATIVE)
    with pytest.raises(ControlsRunError, match="repetition"):
        measure_negative(repetition, setup=_setup(), arm_e=_Arm(TUNED_STATIC_ARM), runner=runner)
    assert runner.calls == []


def test_a_negative_leg_runs_two_named_copies_of_arm_e_on_its_ranges_paired_by_index() -> None:
    runner = _ScriptedRunner(_NULL_NEGATIVE)
    arm_e = _Arm(TUNED_STATIC_ARM)
    record = measure_negative(1, setup=_setup(), arm_e=arm_e, runner=runner)
    subject_seeds, comparator_seeds = _PLAN.negative[1]
    subject = [_NULL_NEGATIVE[NEGATIVE_SUBJECT_ARM](seed) for seed in _seeds(subject_seeds)]
    comparator = [
        _NULL_NEGATIVE[NEGATIVE_COMPARATOR_ARM](seed) for seed in _seeds(comparator_seeds)
    ]
    expected = ArtifactInterval.from_interval(_CONTRACT.interval(subject, comparator))

    assert runner.calls == [
        (NEGATIVE_SUBJECT_ARM, tuple(_seeds(subject_seeds))),
        (NEGATIVE_COMPARATOR_ARM, tuple(_seeds(comparator_seeds))),
    ]
    assert len(runner.specs) == 2
    for spec in runner.specs:
        assert isinstance(spec.policy, NamedPolicy)
        assert spec.policy.inner is arm_e
        assert spec.role == "baseline"
    assert record.repetition == 1
    assert record.independent_seed_sets == len(_PLAN.negative)
    assert record.subject.costs == tuple(subject)
    assert record.comparator.costs == tuple(comparator)
    assert record.subject.costs_sha256 == _sha256_of(subject)
    assert record.interval == expected
    assert record.unavailable_reason is None


@pytest.mark.parametrize(
    ("failure", "needle"),
    [("a failed run", "scripted failure"), ("a non-finite objective", "non-finite objective")],
)
def test_a_failed_replicate_leaves_the_repetition_unavailable_and_its_survivors_unpaired(
    failure: str, needle: str
) -> None:
    _, comparator_seeds = _PLAN.negative[0]
    broken = comparator_seeds.start + 2
    costs = dict(_NULL_NEGATIVE)
    fail_at: frozenset[tuple[str, int]] = frozenset()
    if failure == "a failed run":
        fail_at = frozenset({(NEGATIVE_COMPARATOR_ARM, broken)})
    else:
        honest = _NULL_NEGATIVE[NEGATIVE_COMPARATOR_ARM]
        costs[NEGATIVE_COMPARATOR_ARM] = lambda seed: math.nan if seed == broken else honest(seed)
    runner = _ScriptedRunner(costs, fail_at=fail_at)
    record = measure_negative(0, setup=_setup(), arm_e=_Arm(TUNED_STATIC_ARM), runner=runner)

    assert record.interval is None
    assert record.unavailable_reason is not None
    assert record.unavailable_reason.startswith("incomplete")
    assert record.comparator.costs is None
    assert record.comparator.costs_sha256 is None
    assert record.comparator.failed_seeds == (broken,)
    assert record.comparator.first_error is not None
    assert needle in record.comparator.first_error
    # The complete leg keeps its costs, and is still never paired with the survivors.
    assert record.subject.costs is not None


def _misanswering(defect: str) -> Callable[[Scenario, ArmSpec, Sequence[int]], list[ScenarioRun]]:
    honest = _ScriptedRunner(_NULL_NEGATIVE)

    def runner(scenario: Scenario, spec: ArmSpec, seeds: Sequence[int]) -> list[ScenarioRun]:
        runs = honest(scenario, spec, seeds)
        if defect == "reversed":
            return runs[::-1]
        if defect == "one short":
            return runs[:-1]
        if defect == "under another name":
            return [replace(run, arm="someone_else") for run in runs]
        raise AssertionError(f"no answer is declared for {defect!r}")

    return runner


@pytest.mark.parametrize("defect", ["reversed", "one short", "under another name"])
def test_a_runner_answer_that_cannot_be_paired_by_index_is_refused(defect: str) -> None:
    with pytest.raises(ControlsRunError, match="pairing by index"):
        measure_negative(
            0, setup=_setup(), arm_e=_Arm(TUNED_STATIC_ARM), runner=_misanswering(defect)
        )


def test_the_positive_leg_pairs_arm_o_with_arm_e_and_records_its_reproduction() -> None:
    runner = _ScriptedRunner(_DETECTED_POSITIVE)
    reproduction = _reproduction()
    record = _positive_record(runner, reproduction)
    seeds = tuple(_seeds(_PLAN.positive))
    o_costs = [_DETECTED_POSITIVE[STRUCTURE_AWARE_ARM](seed) for seed in seeds]
    e_costs = [_DETECTED_POSITIVE[TUNED_STATIC_ARM](seed) for seed in seeds]

    assert runner.calls == [(STRUCTURE_AWARE_ARM, seeds), (TUNED_STATIC_ARM, seeds)]
    assert [spec.role for spec in runner.specs] == ["oracle", "baseline"]
    assert record.reproduction == reproduction
    assert record.interval == ArtifactInterval.from_interval(_CONTRACT.interval(o_costs, e_costs))
    assert record.interval is not None
    # Arm O is cheaper at every seed here, so E - O lies above zero: the orientation, pinned.
    assert record.interval.low > 0.0


def _foreign_reproduction(foreign: str) -> BprimeReproduction:
    if foreign == "another artifact":
        return _reproduction(sha256="f" * 64)
    if foreign == "other seeds":
        return _reproduction(seeds=SeedRange(start=200, count=_MEASUREMENT.count))
    if foreign == "fewer arms":
        return _reproduction(arms=REPRODUCED_ARMS[:2])
    if foreign == "reordered":
        return _reproduction(arms=REPRODUCED_ARMS[::-1])
    raise AssertionError(f"no reproduction is declared for {foreign!r}")


@pytest.mark.parametrize("foreign", ["another artifact", "other seeds", "fewer arms", "reordered"])
def test_a_reproduction_of_anything_but_this_record_is_refused_before_the_leg_runs(
    foreign: str,
) -> None:
    runner = _ScriptedRunner(_DETECTED_POSITIVE)
    with pytest.raises(ControlsRunError, match="reproduction"):
        _positive_record(runner, _foreign_reproduction(foreign))
    assert runner.calls == []


def test_the_positive_leg_refuses_arms_not_named_as_arms_o_and_e_before_it_runs() -> None:
    runner = _ScriptedRunner(_DETECTED_POSITIVE)
    with pytest.raises(ControlsRunError, match="contrasts"):
        measure_positive(
            setup=_setup(),
            arm_o=_Arm("hindsight"),
            arm_e=_Arm(TUNED_STATIC_ARM),
            runner=runner,
            reproduction=_reproduction(),
        )
    assert runner.calls == []


def test_a_leg_record_is_canonical_json_that_reads_back_equal_and_refuses_an_edited_cost(
    tmp_path: Path,
) -> None:
    record = _positive_record(_ScriptedRunner(_DETECTED_POSITIVE), _reproduction())
    raw = write_record(tmp_path / POSITIVE_RECORD_NAME, record).read_bytes()
    edited = json.loads(raw)
    edited["comparator"]["costs"][0] += 1.0

    assert raw.isascii()
    assert raw == json.dumps(json.loads(raw), sort_keys=True, separators=(",", ":")).encode()
    assert PositiveControlRecord.model_validate_json(raw) == record
    with pytest.raises(ValidationError, match="costs_sha256"):
        PositiveControlRecord.model_validate(edited)


def test_the_controls_run_the_e5_suites_own_arm_e_at_b_primes_levels() -> None:
    """One construction of arm E (G2). Starts an engine for the catalogue; advances none."""
    record = _bprime_record()
    arm_e = controls_run.tuned_static_arm(record)
    e5_arm_e, _ = e5_baseline_arms(record)

    assert arm_e.name == TUNED_STATIC_ARM
    assert isinstance(arm_e, GroupParLevelReorder)
    assert isinstance(e5_arm_e.policy, GroupParLevelReorder)
    assert arm_e.levels == record.arm_e_levels() == e5_arm_e.policy.levels


@pytest.mark.parametrize(
    ("env", "named"),
    [
        (
            {
                "SYNAPSE_REVISION": "r",
                "SYNAPSE_RUN_ID": "7",
                "GITHUB_SHA": "g",
                "GITHUB_RUN_ID": "8",
            },
            ("r", "7"),
        ),
        ({"GITHUB_SHA": "g", "GITHUB_RUN_ID": "8"}, ("g", "8")),
        ({"SYNAPSE_REVISION": "  ", "GITHUB_SHA": "g"}, ("g", UNATTRIBUTED)),
        ({}, (UNATTRIBUTED, UNATTRIBUTED)),
    ],
)
def test_a_leg_names_its_run_from_the_environment_or_records_it_as_unknown(
    env: dict[str, str], named: tuple[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    for key in ("SYNAPSE_REVISION", "SYNAPSE_RUN_ID", "GITHUB_SHA", "GITHUB_RUN_ID"):
        monkeypatch.delenv(key, raising=False)
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    provenance = resolve_control_provenance(_BPRIME_SHA, scenario="s", loop=E5_LOOP)

    assert (provenance.revision, provenance.run_id) == named
    assert provenance.loop == LoopRecord.of(E5_LOOP)


# ---------------------------------------------------------------------------
# The production runner
# ---------------------------------------------------------------------------
def test_the_production_runner_hands_run_arm_on_seeds_the_plans_seeds_under_e5_loop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[tuple[LoopConfig | None, str, tuple[int, ...]]] = []

    class _RecordingHarness:
        """Stands in for ``UpliftHarness``: records what it is handed and runs no twin."""

        def __init__(self, *, loop_config: LoopConfig | None = None) -> None:
            self._loop = loop_config

        def run_arm_on_seeds(
            self, scenario: Scenario, spec: ArmSpec, seeds: Sequence[int]
        ) -> list[ScenarioRun]:
            seen.append((self._loop, spec.name, tuple(seeds)))
            return _ScriptedRunner(_DETECTED_POSITIVE)(scenario, spec, seeds)

    monkeypatch.setattr(controls_run, "UpliftHarness", _RecordingHarness)
    runner = production_arm_runner()
    measure_positive(
        setup=_setup(),
        arm_o=_Arm(STRUCTURE_AWARE_ARM),
        arm_e=_Arm(TUNED_STATIC_ARM),
        runner=runner,
        reproduction=_reproduction(),
    )
    seeds = tuple(_seeds(_PLAN.positive))

    assert runner == HarnessArmRunner(loop=E5_LOOP)
    assert seen == [(E5_LOOP, STRUCTURE_AWARE_ARM, seeds), (E5_LOOP, TUNED_STATIC_ARM, seeds)]


def test_the_production_runner_refuses_a_probe_below_the_powered_count_before_any_twin() -> None:
    """The real harness: INV-TW-002 refuses one seed before a twin is built or a decision taken."""
    probe = ArmSpec(policy=_Arm(TUNED_STATIC_ARM), role="baseline")
    with pytest.raises(ValueError, match="INV-TW-002"):
        production_arm_runner()(_SCENARIO, probe, [POSITIVE_START])


# ---------------------------------------------------------------------------
# The verdict
# ---------------------------------------------------------------------------
_SCRIPTS: Final[dict[str, tuple[dict[str, Callable[[int], float]], str, str, str]]] = {
    "the negative control fails": (
        {**_GAINFUL_NEGATIVE, **_DETECTED_POSITIVE},
        "fail",
        "detected",
        "agrees",
    ),
    "the positive control misses": (
        {**_NULL_NEGATIVE, **_MISSED_POSITIVE},
        "pass",
        "not_detected",
        "harness_mis_measuring",
    ),
}


@pytest.mark.parametrize("script", sorted(_SCRIPTS))
def test_the_verdict_writes_all_four_records_and_exits_zero_whatever_the_controls_say(
    script: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    costs, negative_verdict, positive_verdict, agreement_verdict = _SCRIPTS[script]
    records, output = tmp_path / "controls", tmp_path / "verdict"
    _write_records(records, _ScriptedRunner(costs), _reproduction())
    inputs = _inputs(tmp_path / "tree", margin=_MARGIN)

    code = verdict_command(records, output, inputs)
    lines = _controls_lines(capsys.readouterr().out)
    negative = NegativeVerdictRecord.model_validate_json(_bytes(output, NEGATIVE_VERDICT_NAME))
    positive = PositiveVerdictRecord.model_validate_json(_bytes(output, POSITIVE_VERDICT_NAME))
    agreement = AgreementVerdictRecord.model_validate_json(_bytes(output, AGREEMENT_VERDICT_NAME))
    report = read_power_report(output / POWER_REPORT_NAME)
    e_cost, o_cost = costs[TUNED_STATIC_ARM], costs[STRUCTURE_AWARE_ARM]
    paired = [e_cost(seed) - o_cost(seed) for seed in _seeds(_PLAN.positive)]

    assert code == EXIT_WRITTEN
    assert _names(output) == sorted((*_READINGS, POWER_REPORT_NAME))
    assert negative.reading.verdict == negative_verdict
    assert negative.reading.required == len(_PLAN.negative)
    assert positive.reading.verdict == positive_verdict
    assert agreement.verdict == agreement_verdict
    assert report is not None
    assert report.replicates_per_arm == _N
    assert report.observed_variance == statistics.variance(paired)
    assert describes_revision(report, inputs.root, POWER_SOURCE_SET)
    assert lines
    assert all(line.isascii() for line in lines)
    assert f"[controls] negative control: {negative_verdict} - " in "\n".join(lines)


def test_without_a_committed_margin_the_verdict_records_why_no_power_report_exists(
    tmp_path: Path,
) -> None:
    records, output = tmp_path / "controls", tmp_path / "verdict"
    _write_records(records, _ScriptedRunner(_PASSING), _reproduction())

    code = verdict_command(records, output, _inputs(tmp_path / "tree", margin=None))
    absence = PowerReportAbsence.model_validate_json(_bytes(output, POWER_REPORT_ABSENT_NAME))

    assert code == EXIT_WRITTEN
    assert _names(output) == sorted((*_READINGS, POWER_REPORT_ABSENT_NAME))
    assert "materiality_margin() returned None" in absence.reason


def test_an_incomplete_repetition_is_recorded_unavailable_and_the_verdict_still_writes(
    tmp_path: Path,
) -> None:
    _, comparator_seeds = _PLAN.negative[1]
    broken = frozenset({(NEGATIVE_COMPARATOR_ARM, comparator_seeds.start)})
    records, output = tmp_path / "controls", tmp_path / "verdict"
    _write_records(records, _ScriptedRunner(_PASSING, fail_at=broken), _reproduction())

    code = verdict_command(records, output, _inputs(tmp_path / "tree", margin=_MARGIN))
    negative = NegativeVerdictRecord.model_validate_json(_bytes(output, NEGATIVE_VERDICT_NAME))

    assert code == EXIT_WRITTEN
    assert negative.repetitions[0] is not None
    assert negative.repetitions[1] is None
    assert negative.reading.verdict == "unavailable"
    assert negative.reading.supplied == len(_PLAN.negative) - 1


#: Each way the input directory is not exactly the declared records, and what its refusal names.
_INPUT_DEFECTS: Final[dict[str, str]] = {
    "a missing repetition": "missing",
    "an extra repetition": "extra repetition",
    "a repetition filed twice": "a second time",
    "a repetition under another's index": "duplicates another",
    "a missing positive record": "missing",
    "an unexpected file": "unexpected entry",
    "a cost edited after measurement": "costs_sha256",
    "an interval its costs do not reproduce": "do not reproduce",
}


def _damage(directory: Path, defect: str) -> None:
    first, second = directory / negative_record_name(0), directory / negative_record_name(1)
    if defect == "a missing repetition":
        second.unlink()
    elif defect == "an extra repetition":
        (directory / negative_record_name(2)).write_bytes(second.read_bytes())
    elif defect == "a repetition filed twice":
        (directory / "negative-01.json").write_bytes(second.read_bytes())
    elif defect == "a repetition under another's index":
        second.write_bytes(first.read_bytes())
    elif defect == "a missing positive record":
        (directory / POSITIVE_RECORD_NAME).unlink()
    elif defect == "an unexpected file":
        (directory / "notes.txt").write_text("not a record\n", encoding="utf-8")
    elif defect == "a cost edited after measurement":
        payload = json.loads(first.read_text(encoding="utf-8"))
        payload["subject"]["costs"][0] += 1.0
        text = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        first.write_text(text, encoding="utf-8")
    elif defect == "an interval its costs do not reproduce":
        record = NegativeRepetitionRecord.model_validate_json(first.read_bytes())
        other = ArtifactInterval.from_interval(_CONTRACT.interval([0.0] * _N, [1.0] * _N))
        write_record(first, record.model_copy(update={"interval": other}))
    else:
        raise AssertionError(f"no damage is declared for {defect!r}")


@pytest.mark.parametrize("defect", sorted(_INPUT_DEFECTS))
def test_the_verdict_refuses_any_input_set_but_exactly_the_declared_records_and_writes_nothing(
    defect: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    records, output = tmp_path / "controls", tmp_path / "verdict"
    _write_records(records, _ScriptedRunner(_PASSING), _reproduction())
    _damage(records, defect)

    code = verdict_command(records, output, _inputs(tmp_path / "tree", margin=_MARGIN))
    err = capsys.readouterr().err

    assert code == EXIT_REFUSED
    assert not output.exists()
    assert "[controls] verdict REFUSED" in err
    assert _INPUT_DEFECTS[defect] in err


@pytest.mark.parametrize(
    ("other", "needle"),
    [("artifact", "B-prime artifact"), ("measurement seeds", "B-prime's measurement")],
)
def test_the_verdict_refuses_records_measured_against_another_b_prime_record(
    other: str, needle: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    records, output = tmp_path / "controls", tmp_path / "verdict"
    _write_records(records, _ScriptedRunner(_PASSING), _reproduction())
    inputs = _inputs(tmp_path / "tree", margin=_MARGIN)
    if other == "artifact":
        inputs = replace(inputs, bprime_artifact_sha256="f" * 64)
    else:
        inputs = replace(inputs, bprime_measurement_seeds=SeedRange(start=0, count=100))

    code = verdict_command(records, output, inputs)

    assert code == EXIT_REFUSED
    assert not output.exists()
    assert needle in capsys.readouterr().err


def test_the_verdict_refuses_an_output_directory_that_already_holds_a_record(
    tmp_path: Path,
) -> None:
    records, output = tmp_path / "controls", tmp_path / "verdict"
    _write_records(records, _ScriptedRunner(_PASSING), _reproduction())
    output.mkdir()
    (output / "stale.json").write_text("{}", encoding="utf-8")

    code = verdict_command(records, output, _inputs(tmp_path / "tree", margin=_MARGIN))

    assert code == EXIT_REFUSED
    assert _names(output) == ["stale.json"]


# ---------------------------------------------------------------------------
# The agreement reads B-prime's split only where B-prime's arms reproduce
# ---------------------------------------------------------------------------
def test_the_agreement_is_read_against_b_prime_where_every_b_prime_arm_reproduces(
    tmp_path: Path,
) -> None:
    reproduction = _reproduction()
    records, output = tmp_path / "controls", tmp_path / "verdict"
    _write_records(records, _ScriptedRunner(_PASSING), reproduction)

    code = verdict_command(records, output, _inputs(tmp_path / "tree", margin=_MARGIN))
    agreement = AgreementVerdictRecord.model_validate_json(_bytes(output, AGREEMENT_VERDICT_NAME))

    assert code == EXIT_WRITTEN
    assert agreement.reproduction == reproduction
    assert agreement.reading is not None
    assert agreement.verdict == agreement.reading.verdict == "agrees"
    assert agreement.unavailable_reason is None
    assert (agreement.reading.comparator, agreement.reading.ceiling) == (_E_MINUS_O, _E_MINUS_D)


@pytest.mark.parametrize(
    "missing",
    [(STRUCTURE_AWARE_ARM,), (TUNED_STATIC_ARM, E5_IN_SAMPLE_ARM), REPRODUCED_ARMS],
    ids=["arm O", "arms E and E-prime", "every arm"],
)
def test_no_agreement_is_read_against_b_prime_while_one_of_its_arms_does_not_reproduce(
    missing: tuple[str, ...], tmp_path: Path
) -> None:
    reproduction = _reproduction(missing=missing)
    records, output = tmp_path / "controls", tmp_path / "verdict"
    _write_records(records, _ScriptedRunner(_PASSING), reproduction)

    code = verdict_command(records, output, _inputs(tmp_path / "tree", margin=_MARGIN))
    agreement = AgreementVerdictRecord.model_validate_json(_bytes(output, AGREEMENT_VERDICT_NAME))
    positive = PositiveVerdictRecord.model_validate_json(_bytes(output, POSITIVE_VERDICT_NAME))
    reason = agreement.unavailable_reason

    assert code == EXIT_WRITTEN
    assert agreement.reproduction == reproduction
    assert agreement.reading is None
    assert agreement.verdict == "unavailable"
    assert reason is not None
    for arm in REPRODUCED_ARMS:
        assert (f"{arm} measured" in reason) is (arm in missing), (arm, reason)
    # The reproduction decides the agreement alone: the harness's own records are unaffected.
    assert positive.reading.verdict == "detected"
    assert (output / POWER_REPORT_NAME).is_file()


def test_an_agreement_record_refuses_a_reading_its_reproduction_does_not_license() -> None:
    reading = classify_agreement(harness=_E_MINUS_O, comparator=_E_MINUS_O, ceiling=_E_MINUS_D)
    unreproduced = _reproduction(missing=(STRUCTURE_AWARE_ARM,))
    honest = AgreementVerdictRecord.judge(
        provenance=_PROVENANCE, inputs=(), reproduction=unreproduced, reading=None
    )
    forged: dict[str, object] = {
        "kind": "agreement-verdict",
        "schema_version": 1,
        "provenance": _PROVENANCE,
        "inputs": (),
        "reproduction": unreproduced,
        "verdict": "agrees",
        "reading": reading,
        "unavailable_reason": None,
    }

    assert reading.verdict == "agrees"
    assert honest.verdict == "unavailable"
    with pytest.raises(ValidationError, match="no agreement reading may be formed"):
        AgreementVerdictRecord.model_validate(forged)
    with pytest.raises(ValidationError, match="license"):
        AgreementVerdictRecord.model_validate(
            {**honest.model_dump(), "unavailable_reason": "B-prime reproduced, trust me"}
        )
    with pytest.raises(ValidationError, match="must be formed"):
        AgreementVerdictRecord.judge(
            provenance=_PROVENANCE, inputs=(), reproduction=_reproduction(), reading=None
        )
