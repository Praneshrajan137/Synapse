"""E3's controls in CI: the negative and positive control legs, and the verdict that reads them.

Feature: decision-quality-proof, task 16.7's second subject (R6.1-R6.5, R6.14, R6.15; design
E3.2-E3.3; ADR-055 D2.8, D6). ``.github/workflows/uplift.yml`` runs, verbatim::

    python -m uplift.controls_run negative --repetition K --output .../negative-K.json
    python -m uplift.controls_run positive --output .../positive.json
    python -m uplift.controls_run verdict --input-dir DIR --output-dir DIR

**Two contrasts, each between two named policies** (R6.14, never a pooled comparator).
``negative`` runs arm E -- the B-prime record's tuned levels on ``uplift/tuned_static.py``'s rule
-- against itself, as two :class:`~uplift.policies.NamedPolicy` copies on DISJOINT seed ranges
paired by index: on shared seeds a deterministic arm gives ``[0, 0]``, a control that cannot fail
(finding 69). ``positive`` runs arm O, built as ``uplift/foresight.py::run_three_pass`` builds it,
against arm E on ONE shared range. Both run through ``UpliftHarness.run_arm_on_seeds`` under
``uplift.e5_suite.E5_LOOP`` (24 h at the regret driver's cadence, reorders only) in
``e5_scenario()``'s primary-cell world: the physics arm E was tuned, and B-prime's comparator
measured, under. Every interval is ``MetricContract.interval`` on the objective, comparator minus
subject, so a positive value means the subject is cheaper (``uplift/controls.py``'s orientation).

**The verdict.** ``negative.json``, ``positive.json`` and ``agreement.json`` carry the readings of
``uplift/controls.py``'s three classifiers. ``power-report.json`` is the ``uplift/power.py``
Power_Report built from the positive control's paired variance; when none can be built,
``power-report-absent.json`` records why instead. A FAILED CONTROL IS A RECORDED RESULT: every
subcommand exits :data:`EXIT_WRITTEN` once its records are written, whatever they say, and
:data:`EXIT_REFUSED` only for an input it cannot read or must not judge -- and then writes nothing.

**B-prime is read only where it reproduces.** The positive leg also re-measures every arm
B-prime measured (``REPRODUCED_ARMS``: E, E' and O) at B-prime's own measurement seeds, by
``uplift.e5_suite.measure_bprime_reproduction`` -- the one reproduction, never a second -- and
``positive.json`` records it. Unless each arm reproduces its recorded mean EXACTLY, B-prime's
``E - O`` and ``E - D`` describe another instrument than the one measured here, so
``agreement.json`` forms no reading: it is ``unavailable`` and names each arm that did not.

**Refused before any twin run** (:class:`ControlsRunError`): a seed plan whose ranges overlap one
another, B-prime's tuning or measurement seeds, or the E5 suite's replicate seeds; a repetition
outside ``0 .. independent_seed_sets - 1``. A failed replicate makes its leg unavailable with the
failed seeds named, and survivors are never paired. The verdict re-derives every stored interval
from its own record's costs and refuses one they do not reproduce.

Every leg is ``MIN_POWERED_REPLICATES`` twin replicates per arm, a category-4 workload under I-0
that runs in CI only (R6.12). The arm runner is a seam (:data:`ArmRunner`), so the fast tests
judge this module without a twin.

**Thin closure.** ``uplift.yml`` runs this module in twin-regret's thin install
(``packages/requirements.txt`` plus simpy, numpy, pyyaml, pydantic-settings and scipy), so every
module-level import on its path must resolve there. Nothing on it imports ``orchestrator`` or
``agents`` at module scope: ``uplift.consensus_arm``, which ``uplift/__init__`` loads, imports
them inside functions.
"""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import itertools
import json
import math
import os
import re
import statistics
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Final, Literal, TypeAlias, TypeVar

import structlog
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from digital_twin.simulation.policy import (
    PolicyUnavailableError,
    detection_probability,
    materiality_margin,
    negative_control_settings,
)
from digital_twin.simulation.world import MINUTES_PER_HOUR
from uplift.bprime_record import read_bprime_record
from uplift.contract import MetricContractError, load_contract
from uplift.controls import (
    AgreementReading,
    AgreementVerdict,
    JudgedInterval,
    NegativeControlReading,
    NegativeRepetition,
    PositiveControlReading,
    SeedRange,
    classify_agreement,
    classify_negative_control,
    classify_positive_control,
)
from uplift.e5_suite import (
    E5_LOOP,
    REPRODUCED_ARMS,
    BprimeReproduction,
    BprimeReproductionError,
    e5_baseline_arms,
    e5_replicate_seeds,
    e5_scenario,
    measure_bprime_reproduction,
    production_arm_cost,
)
from uplift.foresight import stocked_skus
from uplift.harness import UNATTRIBUTED, ArtifactInterval, UpliftHarness
from uplift.interfaces import ArmSpec, Scenario, ScenarioRun
from uplift.interval import IntervalUnavailableError, contract_alpha
from uplift.oracle_arm import STRUCTURE_AWARE_ARM, build_structure_aware_arm
from uplift.policies import NamedPolicy
from uplift.power import POWER_SOURCE_SET, PowerReportError, build_power_report, write_power_report
from uplift.tuned_static import TUNED_STATIC_ARM
from uplift.tuning import TuningUnavailableError
from uplift.uplift_floor import MIN_POWERED_REPLICATES

if TYPE_CHECKING:  # pragma: no cover - annotations only
    from digital_twin.simulation.world import ResolvedWorld
    from uplift.bprime_record import BprimeRecord, IntervalRecord
    from uplift.contract import MetricContract
    from uplift.e5_suite import ArmReproduction
    from uplift.harness import LoopConfig
    from uplift.interfaces import DecisionPolicy
    from uplift.oracle_arm import StructureAwareBaseStock
    from uplift.power import PowerReport

__all__ = [
    "AGREEMENT_VERDICT_NAME",
    "ARM_CONSTRUCTION_SEED",
    "EXIT_REFUSED",
    "EXIT_WRITTEN",
    "NEGATIVE_COMPARATOR_ARM",
    "NEGATIVE_COMPARATOR_START",
    "NEGATIVE_STRIDE",
    "NEGATIVE_SUBJECT_ARM",
    "NEGATIVE_SUBJECT_START",
    "NEGATIVE_VERDICT_NAME",
    "POSITIVE_RECORD_NAME",
    "POSITIVE_START",
    "POSITIVE_VERDICT_NAME",
    "POWER_REPORT_ABSENT_NAME",
    "POWER_REPORT_NAME",
    "AgreementVerdictRecord",
    "ArmLeg",
    "ArmRunner",
    "ControlProvenance",
    "ControlSetup",
    "ControlsRunError",
    "HarnessArmRunner",
    "InputDigest",
    "LoopRecord",
    "NegativeRepetitionRecord",
    "NegativeVerdictRecord",
    "PositiveControlRecord",
    "PositiveVerdictRecord",
    "PowerReportAbsence",
    "SeedPlan",
    "VerdictInputs",
    "VerdictOutcome",
    "bprime_agreement_terms",
    "committed_seed_plan",
    "cost_vector_sha256",
    "main",
    "measure_negative",
    "measure_positive",
    "negative_record_name",
    "negative_seed_ranges",
    "primary_world",
    "production_arm_runner",
    "production_verdict_inputs",
    "refuse_foreign_reproduction",
    "refuse_seed_overlaps",
    "require_repetition",
    "resolve_control_provenance",
    "structure_aware_arm",
    "tuned_static_arm",
    "unreproduced_reason",
    "verdict_command",
    "write_record",
    "write_verdict",
]

logger = structlog.get_logger(__name__)

#: The repository root: the tree the B-prime record is read from and the Power_Report digests.
ROOT: Final[Path] = Path(__file__).resolve().parents[1]

#: Records written, whatever they say. A failed control is a recorded result, not an exit code.
EXIT_WRITTEN: Final[int] = 0
#: An input that cannot be read or must not be judged; nothing was written.
EXIT_REFUSED: Final[int] = 2

# ---------------------------------------------------------------------------
# The committed seed plan
# ---------------------------------------------------------------------------
#: Repetition ``K``'s subject copy runs on ``[NEGATIVE_SUBJECT_START + NEGATIVE_STRIDE * K, +n)``
#: and its comparator copy on ``[NEGATIVE_COMPARATOR_START + NEGATIVE_STRIDE * K, +n)``; the
#: positive control runs arms O and E on ONE range ``[POSITIVE_START, +n)``, paired by shared
#: seed; ``n`` is ``MIN_POWERED_REPLICATES``.
#:
#: **Their values are immaterial; their fixity is the point** -- the honesty clause
#: ``uplift.interval.INTERVAL_SEED`` carries. Chosen once, before any control ran, clear of
#: B-prime's tuning seeds (1000..1099) and measurement seeds (0..199). They must never be
#: re-chosen after a control has been read: re-drawing seeds until a negative control passes, or a
#: positive control detects, is metric-shopping with extra steps.
#:
#: Capacity: the stride is twice the range, so the bases hold ``(POSITIVE_START -
#: NEGATIVE_SUBJECT_START) // NEGATIVE_STRIDE`` = 20 repetitions while ``MIN_POWERED_REPLICATES``
#: is 1000. A larger repetition count, or R6.9 raising the replicate floor, makes ranges overlap,
#: and :class:`SeedPlan` refuses the plan before any twin run: re-declare it, never shrink a range.
NEGATIVE_SUBJECT_START: Final[int] = 100_000
NEGATIVE_COMPARATOR_START: Final[int] = 101_000
NEGATIVE_STRIDE: Final[int] = 2_000
POSITIVE_START: Final[int] = 140_000

#: The negative control's two copies of arm E. Distinct, because harness results and comparator
#: labels refuse two arms of one name (tasks.md 16.4's note for this module).
NEGATIVE_SUBJECT_ARM: Final[str] = "tuned_static_copy_subject"
NEGATIVE_COMPARATOR_ARM: Final[str] = "tuned_static_copy_comparator"

#: The construction seed arm O is built with, and the catalogue probe's. Arm O never draws from it
#: (its generator is "never drawn from"), so it is held only for the R1.9 construction contract
#: and its value is immaterial. Arm E is built by ``uplift.e5_suite.e5_baseline_arms``.
ARM_CONSTRUCTION_SEED: Final[int] = 0

POSITIVE_RECORD_NAME: Final[str] = "positive.json"
NEGATIVE_VERDICT_NAME: Final[str] = "negative.json"
POSITIVE_VERDICT_NAME: Final[str] = "positive.json"
AGREEMENT_VERDICT_NAME: Final[str] = "agreement.json"
POWER_REPORT_NAME: Final[str] = "power-report.json"
POWER_REPORT_ABSENT_NAME: Final[str] = "power-report-absent.json"

_NEGATIVE_RECORD_NAME: Final[re.Pattern[str]] = re.compile(r"negative-([0-9]+)\.json")
_SHA256_HEX: Final[str] = r"^[0-9a-f]{64}$"
_ERROR_CHARS: Final[int] = 500
_REVISION_ENV_KEYS: Final[tuple[str, ...]] = ("SYNAPSE_REVISION", "GITHUB_SHA")
_RUN_ID_ENV_KEYS: Final[tuple[str, ...]] = ("SYNAPSE_RUN_ID", "GITHUB_RUN_ID")

_Model = TypeVar("_Model", bound=BaseModel)


class ControlsRunError(ValueError):
    """A control input refused: never repaired with a substituted seed, count or number (I-7)."""


def negative_record_name(repetition: int) -> str:
    """The file repetition ``repetition``'s record is written to and the verdict reads."""
    return f"negative-{repetition}.json"


def negative_seed_ranges(repetition: int, *, replicates: int) -> tuple[SeedRange, SeedRange]:
    """Repetition ``repetition``'s ``(subject, comparator)`` ranges on the committed bases."""
    offset = NEGATIVE_STRIDE * repetition
    return (
        SeedRange(start=NEGATIVE_SUBJECT_START + offset, count=replicates),
        SeedRange(start=NEGATIVE_COMPARATOR_START + offset, count=replicates),
    )


@dataclasses.dataclass(frozen=True)
class SeedPlan:
    """Every range a control leg runs on, refused on construction unless pairwise disjoint.

    ``negative[K]`` is repetition ``K``'s ``(subject, comparator)`` pair and ``positive`` the
    range arms O and E share. One length throughout -- the replicates per arm -- and no shared
    seed: a seed in two ranges is one realisation counted twice, and independence is the premise
    of the negative control's rate (R6.15).
    """

    negative: tuple[tuple[SeedRange, SeedRange], ...]
    positive: SeedRange

    def __post_init__(self) -> None:
        if not self.negative:
            raise ControlsRunError("a seed plan with no negative repetition estimates no rate")
        spans = self.ranges()
        counts = sorted({span.count for _, span in spans})
        if len(counts) != 1:
            raise ControlsRunError(
                f"the plan's ranges run {counts} replicates: one control runs one count per arm"
            )
        ordered = sorted(spans, key=lambda item: (item[1].start, item[1].stop))
        for (first_label, first), (second_label, second) in itertools.pairwise(ordered):
            if first.overlaps(second):
                raise ControlsRunError(
                    f"the {first_label} ({first.describe()}) and the {second_label} "
                    f"({second.describe()}) share seeds: a seed in two ranges is one realisation "
                    "counted twice, and independence is the premise of the rate (R6.15)"
                )

    @property
    def replicates(self) -> int:
        """Replicates per arm, the same for every range."""
        return self.positive.count

    def ranges(self) -> tuple[tuple[str, SeedRange], ...]:
        """Every range, labelled for a refusal to name."""
        labelled: list[tuple[str, SeedRange]] = []
        for index, (subject, comparator) in enumerate(self.negative):
            labelled.append((f"negative repetition {index} subject range", subject))
            labelled.append((f"negative repetition {index} comparator range", comparator))
        labelled.append(("positive control range", self.positive))
        return tuple(labelled)


def committed_seed_plan(independent_seed_sets: int) -> SeedPlan:
    """The committed plan for ``independent_seed_sets`` repetitions at ``MIN_POWERED_REPLICATES``.

    Raises:
        ControlsRunError: On a repetition count below one, or more than the bases hold.
    """
    if isinstance(independent_seed_sets, bool) or independent_seed_sets < 1:
        raise ControlsRunError(
            f"independent_seed_sets={independent_seed_sets!r}: a rate needs a declared count of "
            "at least one repetition"
        )
    return SeedPlan(
        negative=tuple(
            negative_seed_ranges(index, replicates=MIN_POWERED_REPLICATES)
            for index in range(independent_seed_sets)
        ),
        positive=SeedRange(start=POSITIVE_START, count=MIN_POWERED_REPLICATES),
    )


def refuse_seed_overlaps(
    plan: SeedPlan,
    *,
    tuning_seeds: Sequence[int],
    measurement_seeds: SeedRange,
    e5_seeds: Sequence[int],
) -> None:
    """Refuse a plan touching a seed of the measurements these controls are read beside.

    B-prime tuned arm E on ``tuning_seeds`` and measured its comparator on ``measurement_seeds``,
    and the agreement verdict treats B-prime's ``E - O`` as independent of the harness's
    (``uplift.controls.AGREEMENT_ASSUMPTION``); E5's number is read after these controls and
    never on their seeds. An empty seed set is refused rather than checked, because a check over
    nothing passes vacuously.

    Raises:
        ControlsRunError: Naming the range and the first shared seed.
    """
    if not tuning_seeds or not e5_seeds:
        raise ControlsRunError(
            f"{len(tuning_seeds)} tuning seed(s) and {len(e5_seeds)} E5 replicate seed(s) were "
            "given: an empty set makes the disjointness check vacuous, so it is refused"
        )
    for label, span in plan.ranges():
        if span.overlaps(measurement_seeds):
            raise ControlsRunError(
                f"the {label} ({span.describe()}) overlaps B-prime's measurement "
                f"{measurement_seeds.describe()}: a control on the comparator's own seeds is "
                "not independent of the estimate it is compared with"
            )
        for name, seeds in (
            ("B-prime's tuning seeds", tuning_seeds),
            ("the E5 suite's replicate seeds", e5_seeds),
        ):
            shared = sorted(seed for seed in seeds if span.start <= seed < span.stop)
            if shared:
                raise ControlsRunError(
                    f"the {label} ({span.describe()}) holds {len(shared)} of {name}, the first "
                    f"{shared[0]}: re-declare the plan before any control runs"
                )


def require_repetition(repetition: int, independent_seed_sets: int) -> int:
    """``repetition``, refused unless it is one of the ``independent_seed_sets`` declared."""
    if isinstance(repetition, bool) or not isinstance(repetition, int):
        raise ControlsRunError(f"repetition {repetition!r} is not an integer index")
    if not 0 <= repetition < independent_seed_sets:
        raise ControlsRunError(
            f"repetition {repetition} lies outside the {independent_seed_sets} declared "
            f"(0..{independent_seed_sets - 1}) by negative_control.independent_seed_sets: an "
            "undeclared repetition would license running until the rate looks good"
        )
    return repetition


# ---------------------------------------------------------------------------
# The records a leg writes
# ---------------------------------------------------------------------------
def cost_vector_sha256(costs: Sequence[float]) -> str:
    """sha256 of the compact JSON array of ``costs``: what an :class:`ArmLeg` records."""
    text = json.dumps([float(cost) for cost in costs], separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(text.encode("ascii")).hexdigest()


class LoopRecord(BaseModel):
    """The closed-loop cadence a leg ran under: ``uplift.harness.LoopConfig``'s three fields."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    duration_hours: float = Field(gt=0.0)
    step_hours: float = Field(gt=0.0)
    levers: Literal["all", "reorders_only"]

    @classmethod
    def of(cls, loop: LoopConfig) -> LoopRecord:
        """The record of ``loop``."""
        return cls(
            duration_hours=loop.duration_hours, step_hours=loop.step_hours, levers=loop.levers
        )


class ControlProvenance(BaseModel):
    """Which run measured a record, against which B-prime record, in which world and loop.

    ``revision`` and ``run_id`` come from ``SYNAPSE_REVISION`` / ``SYNAPSE_RUN_ID``, else
    ``GITHUB_SHA`` / ``GITHUB_RUN_ID``, and are :data:`~uplift.harness.UNATTRIBUTED` when neither
    is set -- recorded, never invented. ``PowerReport`` refuses an unnamed run, so no Power_Report
    is built from an unattributed one.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    revision: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    bprime_artifact_sha256: str = Field(pattern=_SHA256_HEX)
    scenario: str = Field(min_length=1)
    loop: LoopRecord


def _from_env(keys: tuple[str, ...]) -> str | None:
    for key in keys:
        value = os.environ.get(key, "").strip()
        if value:
            return value
    return None


def resolve_control_provenance(
    bprime_artifact_sha256: str, *, scenario: str, loop: LoopConfig
) -> ControlProvenance:
    """The provenance of a leg run now, naming the run from the environment or as unknown."""
    return ControlProvenance(
        revision=_from_env(_REVISION_ENV_KEYS) or UNATTRIBUTED,
        run_id=_from_env(_RUN_ID_ENV_KEYS) or UNATTRIBUTED,
        bprime_artifact_sha256=bprime_artifact_sha256,
        scenario=scenario,
        loop=LoopRecord.of(loop),
    )


class ArmLeg(BaseModel):
    """One arm on one seed range, in seed order: every cost, or which replicates failed.

    ``costs[i]`` is the objective of the run at seed ``seeds.start + i``. A leg with any failed
    replicate records NO costs -- only the failed seeds and the first error -- so nothing
    downstream can pair its survivors. ``costs_sha256`` is :func:`cost_vector_sha256` of the
    costs and is re-checked on every read, so a cost edited after measurement is refused.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    arm: str = Field(min_length=1)
    seeds: SeedRange
    costs: tuple[float, ...] | None
    costs_sha256: str | None
    failed_seeds: tuple[int, ...]
    first_error: str | None

    @model_validator(mode="after")
    def _complete_or_named_unavailable(self) -> ArmLeg:
        if self.failed_seeds:
            if self.costs is not None or self.costs_sha256 is not None:
                raise ValueError(
                    f"{self.arm} failed {len(self.failed_seeds)} replicate(s) yet records costs: "
                    "an incomplete leg records none, so its survivors cannot be paired"
                )
            if not self.first_error:
                raise ValueError(f"{self.arm} failed replicates and names no error")
            ascending = list(self.failed_seeds) == sorted(set(self.failed_seeds))
            own = all(self.seeds.start <= seed < self.seeds.stop for seed in self.failed_seeds)
            if not (ascending and own):
                raise ValueError(
                    f"{self.arm}'s failed seeds {list(self.failed_seeds)} are not distinct "
                    f"ascending seeds of its own range ({self.seeds.describe()})"
                )
            return self
        if self.costs is None or self.costs_sha256 is None:
            raise ValueError(f"{self.arm} failed no replicate yet records no costs")
        if len(self.costs) != self.seeds.count:
            raise ValueError(
                f"{self.arm} records {len(self.costs)} costs for {self.seeds.count} seeds"
            )
        if cost_vector_sha256(self.costs) != self.costs_sha256:
            raise ValueError(
                f"{self.arm}'s costs do not hash to their recorded costs_sha256: a cost vector "
                "edited after it was measured is refused"
            )
        if self.first_error is not None:
            raise ValueError(f"{self.arm} completed every replicate yet records an error")
        return self


class _PairedContrast(BaseModel):
    """A subject leg against a comparator leg, with the interval on ``comparator - subject``."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    provenance: ControlProvenance
    replicates: int = Field(strict=True, ge=1)
    subject: ArmLeg
    comparator: ArmLeg
    interval: ArtifactInterval | None
    unavailable_reason: str | None

    @model_validator(mode="after")
    def _paired_or_named_unavailable(self) -> _PairedContrast:
        for leg in (self.subject, self.comparator):
            if leg.seeds.count != self.replicates:
                raise ValueError(
                    f"{leg.arm} ran {leg.seeds.count} replicates, not the record's "
                    f"{self.replicates}"
                )
        if self.subject.arm == self.comparator.arm:
            raise ValueError(
                f"both legs are named {self.subject.arm!r}: a contrast is between two named arms"
            )
        if self.interval is not None:
            if self.subject.costs is None or self.comparator.costs is None:
                raise ValueError(
                    "an interval over an incomplete leg pairs survivors, which is refused"
                )
            if self.unavailable_reason is not None:
                raise ValueError("a record carrying an interval names no unavailability")
        elif self.unavailable_reason is None or not self.unavailable_reason.strip():
            raise ValueError("a record with no interval must say why none was estimated")
        return self


class NegativeRepetitionRecord(_PairedContrast):
    """``negative-K.json``: two copies of arm E on disjoint ranges, paired by index (R6.1)."""

    kind: Literal["negative-control-repetition"]
    schema_version: Literal[1]
    repetition: int = Field(strict=True, ge=0)
    independent_seed_sets: int = Field(strict=True, ge=1)

    @model_validator(mode="after")
    def _a_declared_repetition_on_disjoint_seeds(self) -> NegativeRepetitionRecord:
        if self.repetition >= self.independent_seed_sets:
            raise ValueError(
                f"repetition {self.repetition} lies outside the {self.independent_seed_sets} "
                "declared"
            )
        if self.subject.seeds.overlaps(self.comparator.seeds):
            raise ValueError(
                "the two copies of arm E share seeds: on shared seeds every paired difference "
                "is 0, a control that cannot fail (finding 69)"
            )
        return self


# ---------------------------------------------------------------------------
# B-prime's reproduction, as the positive leg records it
# ---------------------------------------------------------------------------
def _refuse_partial_reproduction(reproduction: BprimeReproduction) -> None:
    """Refuse a reproduction that is not of every arm B-prime measured, in declared order."""
    arms = tuple(arm.arm for arm in reproduction.arms)
    if arms != REPRODUCED_ARMS:
        raise ControlsRunError(
            f"the reproduction re-measures {list(arms)}, not every arm B-prime measured "
            f"{list(REPRODUCED_ARMS)}: B-prime's E - O and E - D are read only if E, E' and O "
            "all reproduce, so a reproduction of fewer arms licenses nothing"
        )


def refuse_foreign_reproduction(
    reproduction: BprimeReproduction, *, artifact_sha256: str, seeds: SeedRange
) -> None:
    """Refuse a reproduction of another B-prime artifact, at other seeds, or of other arms.

    The positive leg re-measures B-prime's arms to decide whether THIS record's ``E - O`` and
    ``E - D`` describe the instrument it runs; a reproduction of anything else decides nothing.

    Raises:
        ControlsRunError: Naming the first mismatch.
    """
    _refuse_partial_reproduction(reproduction)
    if reproduction.bprime_artifact_sha256 != artifact_sha256:
        raise ControlsRunError(
            "the reproduction re-measured B-prime artifact "
            f"{reproduction.bprime_artifact_sha256}, not {artifact_sha256}"
        )
    if reproduction.seeds != seeds:
        raise ControlsRunError(
            f"the reproduction ran {reproduction.seeds.describe()}, not B-prime's measurement "
            f"{seeds.describe()}: a mean at other seeds is not the mean B-prime recorded"
        )


def unreproduced_reason(reproduction: BprimeReproduction) -> str | None:
    """Why no agreement reading is formed -- naming each arm that did not reproduce -- or None."""
    if reproduction.all_reproduce:
        return None
    named = "; ".join(
        f"{arm.arm} measured {arm.measured_mean!r} against the recorded {arm.recorded_mean!r}"
        for arm in reproduction.arms
        if not arm.reproduces
    )
    return (
        f"B-prime's arms do not all reproduce here at its {reproduction.seeds.describe()} "
        f"({named}): its E - O and E - D then describe another instrument, so no agreement "
        "reading is formed against them (R6.3)"
    )


class PositiveControlRecord(_PairedContrast):
    """``positive.json``: arm O (subject) against arm E (comparator) on one shared range (R6.2).

    ``reproduction`` is every arm B-prime measured, re-measured at B-prime's seeds in this leg's
    own environment against the B-prime artifact the provenance names. It decides whether
    ``agreement.json`` may read B-prime's split, so the verdict copies it there.
    """

    kind: Literal["positive-control"]
    schema_version: Literal[1]
    reproduction: BprimeReproduction

    @model_validator(mode="after")
    def _paired_on_shared_seeds(self) -> PositiveControlRecord:
        if self.subject.seeds != self.comparator.seeds:
            raise ValueError(
                f"arm O ran {self.subject.seeds.describe()} and arm E "
                f"{self.comparator.seeds.describe()}: the positive control pairs by shared seed"
            )
        return self

    @model_validator(mode="after")
    def _a_reproduction_of_this_record(self) -> PositiveControlRecord:
        _refuse_partial_reproduction(self.reproduction)
        if self.reproduction.bprime_artifact_sha256 != self.provenance.bprime_artifact_sha256:
            raise ValueError(
                "the reproduction re-measured another B-prime artifact than the one this record "
                "was measured against: one record describes one B-prime"
            )
        return self


def write_record(path: Path, record: BaseModel) -> Path:
    """Write ``record`` as canonical JSON (sorted keys, compact separators, ASCII)."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = record.model_dump(mode="json")
    target.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":")), encoding="utf-8")
    return target


# ---------------------------------------------------------------------------
# One leg
# ---------------------------------------------------------------------------
@dataclasses.dataclass(frozen=True)
class ControlSetup:
    """Everything a control leg reads besides its arms, checked on construction.

    Construction runs :func:`refuse_seed_overlaps`, so no setup -- and so no leg -- exists for a
    plan touching B-prime's or the E5 suite's seeds: the refusal precedes any arm, let alone a
    twin run.
    """

    plan: SeedPlan
    tuning_seeds: tuple[int, ...]
    measurement_seeds: SeedRange
    e5_seeds: tuple[int, ...]
    scenario: Scenario
    contract: MetricContract
    provenance: ControlProvenance

    def __post_init__(self) -> None:
        refuse_seed_overlaps(
            self.plan,
            tuning_seeds=self.tuning_seeds,
            measurement_seeds=self.measurement_seeds,
            e5_seeds=self.e5_seeds,
        )


#: Runs one arm on the given seeds IN ORDER, each used as the twin seed, one run per seed.
#: Production binds :class:`HarnessArmRunner`; the fast tests bind a scripted runner, so no fast
#: test runs the twin.
ArmRunner: TypeAlias = Callable[[Scenario, ArmSpec, Sequence[int]], list[ScenarioRun]]


@dataclasses.dataclass(frozen=True)
class HarnessArmRunner:
    """The production :data:`ArmRunner`: ``UpliftHarness.run_arm_on_seeds`` under ``loop``.

    ``run_arm_on_seeds`` keeps the harness's INV-TW-002 guard, so a seed set below
    ``MIN_SCENARIOS`` is refused before any twin is built: this binding cannot run a probe.
    """

    loop: LoopConfig

    def __call__(
        self, scenario: Scenario, spec: ArmSpec, seeds: Sequence[int]
    ) -> list[ScenarioRun]:
        return UpliftHarness(loop_config=self.loop).run_arm_on_seeds(scenario, spec, seeds)


def production_arm_runner() -> HarnessArmRunner:
    """The runner every CI leg uses: the harness under ``E5_LOOP``."""
    return HarnessArmRunner(loop=E5_LOOP)


def _ascii(text: str) -> str:
    return text.encode("ascii", "backslashreplace").decode("ascii")


def _run_leg(runner: ArmRunner, scenario: Scenario, spec: ArmSpec, seeds: SeedRange) -> ArmLeg:
    """Run ``spec`` on every seed of ``seeds`` and record the leg; refuse a mis-ordered answer."""
    requested = list(range(seeds.start, seeds.stop))
    runs = runner(scenario, spec, requested)
    if [run.seed for run in runs] != requested or any(run.arm != spec.name for run in runs):
        raise ControlsRunError(
            f"the runner answered {spec.name} on {seeds.describe()} with {len(runs)} run(s) that "
            "are not one run per requested seed, in order, under the arm's own name; pairing by "
            "index needs exactly that"
        )
    costs: list[float] = []
    failures: list[tuple[int, str]] = []
    for run in runs:
        cost = None if run.failed or run.kpis is None else float(run.kpis.objective)
        if cost is None:
            failures.append((run.seed, run.error or "the run failed and recorded no error"))
        elif not math.isfinite(cost):
            failures.append((run.seed, f"the run completed with a non-finite objective {cost!r}"))
        else:
            costs.append(cost)
    if failures:
        return ArmLeg(
            arm=spec.name,
            seeds=seeds,
            costs=None,
            costs_sha256=None,
            failed_seeds=tuple(seed for seed, _ in failures),
            first_error=_ascii(failures[0][1])[:_ERROR_CHARS],
        )
    return ArmLeg(
        arm=spec.name,
        seeds=seeds,
        costs=tuple(costs),
        costs_sha256=cost_vector_sha256(costs),
        failed_seeds=(),
        first_error=None,
    )


def _estimate(
    contract: MetricContract, subject: ArmLeg, comparator: ArmLeg
) -> tuple[ArtifactInterval | None, str | None]:
    """The paired interval on ``comparator - subject``, or why none is estimated.

    The ONE estimation path a leg and the verdict share, so the verdict re-derives a stored
    interval by exactly the computation that produced it.
    """
    if subject.costs is None or comparator.costs is None:
        reason = (
            f"incomplete: {subject.arm} failed {len(subject.failed_seeds)} and {comparator.arm} "
            f"failed {len(comparator.failed_seeds)} of {subject.seeds.count} replicates; "
            "survivors are never paired, so no interval is estimated"
        )
        return None, reason
    try:
        estimated = contract.interval(subject.costs, comparator.costs)
    except IntervalUnavailableError as error:
        return None, f"no interval could be estimated from the paired costs: {error}"
    return ArtifactInterval.from_interval(estimated), None


def measure_negative(
    repetition: int, *, setup: ControlSetup, arm_e: DecisionPolicy, runner: ArmRunner
) -> NegativeRepetitionRecord:
    """Repetition ``repetition``: two named copies of ``arm_e`` on its two disjoint ranges.

    Raises:
        ControlsRunError: For a repetition outside the declared count -- before ``runner`` is
            called -- or for a runner answer that cannot be paired by index.
    """
    count = len(setup.plan.negative)
    require_repetition(repetition, count)
    subject_seeds, comparator_seeds = setup.plan.negative[repetition]
    subject = _run_leg(
        runner,
        setup.scenario,
        ArmSpec(policy=NamedPolicy(policy=arm_e, name=NEGATIVE_SUBJECT_ARM), role="baseline"),
        subject_seeds,
    )
    comparator = _run_leg(
        runner,
        setup.scenario,
        ArmSpec(policy=NamedPolicy(policy=arm_e, name=NEGATIVE_COMPARATOR_ARM), role="baseline"),
        comparator_seeds,
    )
    interval, reason = _estimate(setup.contract, subject, comparator)
    return NegativeRepetitionRecord(
        kind="negative-control-repetition",
        schema_version=1,
        repetition=repetition,
        independent_seed_sets=count,
        provenance=setup.provenance,
        replicates=setup.plan.replicates,
        subject=subject,
        comparator=comparator,
        interval=interval,
        unavailable_reason=reason,
    )


def measure_positive(
    *,
    setup: ControlSetup,
    arm_o: DecisionPolicy,
    arm_e: DecisionPolicy,
    runner: ArmRunner,
    reproduction: BprimeReproduction,
) -> PositiveControlRecord:
    """Arm O (subject) against arm E (comparator) on the plan's one shared positive range.

    ``reproduction`` is every arm B-prime measured, re-measured at B-prime's measurement seeds in
    this leg's environment (``uplift.e5_suite.measure_bprime_reproduction``); the record carries
    it, because whether B-prime's split describes this environment is decided by it.

    Raises:
        ControlsRunError: For arms not named as arms O and E, or a reproduction of another
            B-prime artifact, at other seeds or of other arms -- each before ``runner`` is
            called -- or for a runner answer that cannot be paired.
    """
    if (arm_o.name, arm_e.name) != (STRUCTURE_AWARE_ARM, TUNED_STATIC_ARM):
        raise ControlsRunError(
            f"the positive control contrasts {STRUCTURE_AWARE_ARM!r} with {TUNED_STATIC_ARM!r}; "
            f"got {arm_o.name!r} and {arm_e.name!r}"
        )
    refuse_foreign_reproduction(
        reproduction,
        artifact_sha256=setup.provenance.bprime_artifact_sha256,
        seeds=setup.measurement_seeds,
    )
    seeds = setup.plan.positive
    subject = _run_leg(runner, setup.scenario, ArmSpec(policy=arm_o, role="oracle"), seeds)
    comparator = _run_leg(runner, setup.scenario, ArmSpec(policy=arm_e, role="baseline"), seeds)
    interval, reason = _estimate(setup.contract, subject, comparator)
    return PositiveControlRecord(
        kind="positive-control",
        schema_version=1,
        provenance=setup.provenance,
        replicates=setup.plan.replicates,
        subject=subject,
        comparator=comparator,
        interval=interval,
        unavailable_reason=reason,
        reproduction=reproduction,
    )


# ---------------------------------------------------------------------------
# The production arms, in the primary cell's world
# ---------------------------------------------------------------------------
def primary_world(scenario: Scenario) -> ResolvedWorld:
    """The world ``scenario`` runs, refused when it is the world before structures 1 and 3."""
    world = scenario.world
    if world is None:
        raise ControlsRunError(
            f"scenario {scenario.name!r} carries no world: the controls run in the primary "
            "cell's world (task 16.7's re-scope), never the world before structures 1 and 3"
        )
    return world


def tuned_static_arm(record: BprimeRecord) -> DecisionPolicy:
    """Arm E as the E5 suite builds it: the first arm of ``uplift.e5_suite.e5_baseline_arms``.

    ONE construction for the arm E5 reads, the reproduction re-measures and these controls run,
    so the three cannot drift apart (G2). It refuses, as that function does, a record tuned in
    another cell or over another horizon than E5 runs.
    """
    arm_e, _ = e5_baseline_arms(record)
    return arm_e.policy


def structure_aware_arm(
    world: ResolvedWorld, skus: Sequence[str], loop: LoopConfig
) -> StructureAwareBaseStock:
    """Arm O as ``run_three_pass`` builds it, its review period the cadence it is driven at."""
    return build_structure_aware_arm(
        world,
        seed=ARM_CONSTRUCTION_SEED,
        hours=loop.duration_hours,
        review_min=loop.step_hours * MINUTES_PER_HOUR,
        n_skus=len(skus),
    )


@dataclasses.dataclass(frozen=True)
class _Production:
    setup: ControlSetup
    record: BprimeRecord
    world: ResolvedWorld


def _production() -> _Production:
    """Everything a CI leg reads from the committed tree, refused before any engine starts."""
    record = read_bprime_record(ROOT)
    independent_seed_sets, _ = negative_control_settings()
    scenario = e5_scenario()
    world = primary_world(scenario)
    setup = ControlSetup(
        plan=committed_seed_plan(independent_seed_sets),
        tuning_seeds=tuple(record.tuning_seeds),
        measurement_seeds=record.measurement_seeds,
        e5_seeds=e5_replicate_seeds(MIN_POWERED_REPLICATES, record),
        scenario=scenario,
        contract=load_contract(),
        provenance=resolve_control_provenance(
            record.artifact_sha256, scenario=scenario.name, loop=E5_LOOP
        ),
    )
    return _Production(setup=setup, record=record, world=world)


# ---------------------------------------------------------------------------
# The verdict
# ---------------------------------------------------------------------------
class InputDigest(BaseModel):
    """One record file a verdict read, by name and the sha256 of its bytes."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(min_length=1)
    sha256: str = Field(pattern=_SHA256_HEX)


class NegativeVerdictRecord(BaseModel):
    """``negative.json``: the repeated negative control's reading (R6.1, R6.15).

    ``repetitions[K]`` is repetition ``K``'s interval, or ``None`` when it was unavailable. The
    reading carries both the proven-gain and the proven-loss counts, so either reading of
    conflict S can be applied to one run; which binds is the operator's decision.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    kind: Literal["negative-control-verdict"]
    schema_version: Literal[1]
    provenance: ControlProvenance
    inputs: tuple[InputDigest, ...]
    repetitions: tuple[JudgedInterval | None, ...]
    reading: NegativeControlReading

    @model_validator(mode="after")
    def _the_reading_counts_these_repetitions(self) -> NegativeVerdictRecord:
        supplied = [interval for interval in self.repetitions if interval is not None]
        counts = (
            len(self.repetitions),
            len(supplied),
            sum(1 for interval in supplied if interval.position == "above_zero"),
            sum(1 for interval in supplied if interval.position == "below_zero"),
        )
        reading = self.reading
        recorded = (
            reading.required,
            reading.supplied,
            reading.proven_gain_count,
            reading.proven_loss_count,
        )
        if counts != recorded:
            raise ValueError(
                f"the reading counts (required, supplied, gains, losses) = {recorded}, but the "
                f"repetitions it records give {counts}: a reading of other repetitions is refused"
            )
        if len(self.inputs) != len(self.repetitions):
            raise ValueError("every repetition is read from exactly one named record file")
        return self


class PositiveVerdictRecord(BaseModel):
    """``positive.json``: arm O against arm E, detected iff the interval lies above zero (R6.2)."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    kind: Literal["positive-control-verdict"]
    schema_version: Literal[1]
    provenance: ControlProvenance
    inputs: tuple[InputDigest, ...]
    reading: PositiveControlReading


class AgreementVerdictRecord(BaseModel):
    """``agreement.json``: the harness's ``E - O`` against B-prime's ``E - O`` and ``E - D``.

    B-prime's two intervals describe this instrument only if B-prime's arms reproduce here.
    ``reproduction`` is ``positive.json``'s, copied: every arm B-prime measured, re-measured at
    its seeds in the positive leg's environment. While any arm misses its recorded mean, no
    reading is formed: ``reading`` is ``None``, ``verdict`` is ``unavailable`` and
    ``unavailable_reason`` is :func:`unreproduced_reason`, naming each such arm. Otherwise
    ``verdict`` is the reading's own. Both are re-derived on construction, so neither can be
    edited into an agreement the reproduction does not license.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    kind: Literal["agreement-verdict"]
    schema_version: Literal[1]
    provenance: ControlProvenance
    inputs: tuple[InputDigest, ...]
    reproduction: BprimeReproduction
    verdict: AgreementVerdict
    reading: AgreementReading | None
    unavailable_reason: str | None

    @model_validator(mode="after")
    def _a_reading_only_where_b_prime_reproduces(self) -> AgreementVerdictRecord:
        _refuse_partial_reproduction(self.reproduction)
        reason = unreproduced_reason(self.reproduction)
        if reason is None and self.reading is None:
            raise ValueError(
                "every B-prime arm reproduces here, so the agreement reading must be formed"
            )
        if reason is not None and self.reading is not None:
            raise ValueError(
                "a B-prime arm does not reproduce here, so no agreement reading may be formed "
                "against B-prime's split"
            )
        verdict: AgreementVerdict = "unavailable" if self.reading is None else self.reading.verdict
        if (self.verdict, self.unavailable_reason) != (verdict, reason):
            raise ValueError(
                f"the record states verdict={self.verdict!r} and unavailable_reason="
                f"{self.unavailable_reason!r}, but its reading and reproduction license "
                f"verdict={verdict!r} and unavailable_reason={reason!r}"
            )
        return self

    @classmethod
    def judge(
        cls,
        *,
        provenance: ControlProvenance,
        inputs: tuple[InputDigest, ...],
        reproduction: BprimeReproduction,
        reading: AgreementReading | None,
    ) -> AgreementVerdictRecord:
        """The record of ``reading`` -- ``None`` where B-prime does not reproduce -- and why."""
        return cls(
            kind="agreement-verdict",
            schema_version=1,
            provenance=provenance,
            inputs=inputs,
            reproduction=reproduction,
            verdict="unavailable" if reading is None else reading.verdict,
            reading=reading,
            unavailable_reason=unreproduced_reason(reproduction),
        )

    @property
    def explanation(self) -> str:
        """The reading's explanation, or why no reading was formed."""
        if self.reading is not None:
            return self.reading.explanation
        return str(self.unavailable_reason)


class PowerReportAbsence(BaseModel):
    """``power-report-absent.json``: why no Power_Report was written (absence is a state, I-7)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal["power-report-absent"]
    schema_version: Literal[1]
    provenance: ControlProvenance
    inputs: tuple[InputDigest, ...]
    reason: str = Field(min_length=1)


@dataclasses.dataclass(frozen=True)
class VerdictInputs:
    """Everything ``verdict`` reads besides the record files, passed explicitly.

    :func:`production_verdict_inputs` binds each from the committed tree; a test binds its own.
    ``comparator_e_minus_o`` and ``ceiling_e_minus_d`` are B-prime's independently measured
    ``E - O`` and ``E - D`` at the record's alpha (:func:`bprime_agreement_terms`), and
    ``bprime_measurement_seeds`` the seeds it measured them on, which the positive leg's
    reproduction must have re-measured.
    """

    plan: SeedPlan
    max_proven_gain_rate: float
    comparator_e_minus_o: JudgedInterval
    ceiling_e_minus_d: JudgedInterval
    bprime_artifact_sha256: str
    bprime_measurement_seeds: SeedRange
    loop: LoopRecord
    contract: MetricContract
    alpha: float
    detection_probability: float
    materiality_margin: float | None
    root: Path

    def __post_init__(self) -> None:
        if self.alpha != self.contract.alpha:
            raise ControlsRunError(
                f"the Metric_Contract reads alpha={self.contract.alpha!r} and its narrow reader "
                f"alpha={self.alpha!r}: one verdict is read at one committed alpha"
            )


def _at_alpha(interval: IntervalRecord, alpha: float) -> JudgedInterval:
    return JudgedInterval(low=interval.low, high=interval.high, point=interval.point, alpha=alpha)


def bprime_agreement_terms(record: BprimeRecord) -> tuple[JudgedInterval, JudgedInterval]:
    """``(comparator, ceiling)`` for ``classify_agreement``: B-prime's ``E - O`` and ``E - D``."""
    return _at_alpha(record.e_minus_o, record.alpha), _at_alpha(record.e_minus_d, record.alpha)


def production_verdict_inputs() -> VerdictInputs:
    """:class:`VerdictInputs` from the committed policy, B-prime record, contract and margin."""
    record = read_bprime_record(ROOT)
    independent_seed_sets, max_proven_gain_rate = negative_control_settings()
    plan = committed_seed_plan(independent_seed_sets)
    refuse_seed_overlaps(
        plan,
        tuning_seeds=tuple(record.tuning_seeds),
        measurement_seeds=record.measurement_seeds,
        e5_seeds=e5_replicate_seeds(MIN_POWERED_REPLICATES, record),
    )
    comparator, ceiling = bprime_agreement_terms(record)
    return VerdictInputs(
        plan=plan,
        max_proven_gain_rate=max_proven_gain_rate,
        comparator_e_minus_o=comparator,
        ceiling_e_minus_d=ceiling,
        bprime_artifact_sha256=record.artifact_sha256,
        bprime_measurement_seeds=record.measurement_seeds,
        loop=LoopRecord.of(E5_LOOP),
        contract=load_contract(),
        alpha=contract_alpha(),
        detection_probability=detection_probability(),
        materiality_margin=materiality_margin(),
        root=ROOT,
    )


def _refuse_occupied(output_dir: Path) -> None:
    if not output_dir.exists():
        return
    if not output_dir.is_dir():
        raise ControlsRunError(f"{output_dir.as_posix()} exists and is not a directory")
    if any(output_dir.iterdir()):
        raise ControlsRunError(
            f"the output directory {output_dir.as_posix()} already holds files: a verdict is "
            "written into an empty directory, so no stale record sits beside a fresh one"
        )


def _refuse_unexpected_inputs(input_dir: Path, repetitions: int) -> None:
    """Refuse unless ``input_dir`` holds exactly the declared records, by name (G5)."""
    try:
        present = sorted(entry.name for entry in input_dir.iterdir())
    except OSError as error:
        raise ControlsRunError(
            f"the input directory {input_dir.as_posix()} cannot be listed: {error}"
        ) from error
    expected = {negative_record_name(index) for index in range(repetitions)}
    expected.add(POSITIVE_RECORD_NAME)
    problems: list[str] = []
    missing = sorted(expected.difference(present))
    if missing:
        problems.append(f"missing {missing}")
    for name in present:
        if name in expected:
            continue
        match = _NEGATIVE_RECORD_NAME.fullmatch(name)
        if match is None:
            problems.append(f"unexpected entry {name!r}")
            continue
        index = int(match.group(1))
        if index < repetitions:
            problems.append(
                f"{name!r} files repetition {index} a second time, under a name other than "
                f"{negative_record_name(index)!r}"
            )
        else:
            problems.append(
                f"{name!r} is an extra repetition: only 0..{repetitions - 1} are declared"
            )
    if problems:
        raise ControlsRunError(
            "the input directory does not hold exactly the declared records (G5): "
            + "; ".join(problems)
        )


def _read(path: Path, model: type[_Model]) -> tuple[_Model, InputDigest]:
    try:
        raw = path.read_bytes()
    except OSError as error:
        raise ControlsRunError(f"{path.name} cannot be read: {error}") from error
    try:
        record = model.model_validate_json(raw)
    except ValidationError as error:
        raise ControlsRunError(
            f"{path.name} is not an admissible {model.__name__}: {error}"
        ) from error
    return record, InputDigest(name=path.name, sha256=hashlib.sha256(raw).hexdigest())


def _describe(interval: ArtifactInterval | None) -> str:
    if interval is None:
        return "none"
    return f"[{interval.low!r}, {interval.high!r}] (point {interval.point!r})"


def _refuse_off_plan(
    name: str,
    record: _PairedContrast,
    declared: tuple[SeedRange, SeedRange],
    arms: tuple[str, str],
) -> None:
    ran = (record.subject.seeds, record.comparator.seeds)
    if ran != declared:
        raise ControlsRunError(
            f"{name} ran {ran[0].describe()} against {ran[1].describe()}, not the plan's "
            f"{declared[0].describe()} against {declared[1].describe()}"
        )
    if (record.subject.arm, record.comparator.arm) != arms:
        raise ControlsRunError(
            f"{name} contrasts {record.comparator.arm!r} with {record.subject.arm!r}, not the "
            f"declared {arms[1]!r} with {arms[0]!r}"
        )


def _refuse_unreproduced_interval(
    name: str, record: _PairedContrast, contract: MetricContract
) -> None:
    expected, _ = _estimate(contract, record.subject, record.comparator)
    if expected != record.interval:
        raise ControlsRunError(
            f"{name} stores the interval {_describe(record.interval)} but its own costs give "
            f"{_describe(expected)}: an interval its costs do not reproduce is refused"
        )


@dataclasses.dataclass(frozen=True)
class _LoadedRecords:
    negatives: tuple[NegativeRepetitionRecord, ...]
    negative_inputs: tuple[InputDigest, ...]
    positive: PositiveControlRecord
    positive_input: InputDigest

    @property
    def provenance(self) -> ControlProvenance:
        return self.positive.provenance


def _load_records(input_dir: Path, inputs: VerdictInputs) -> _LoadedRecords:
    """Read and check every record against the plan, the contract and one another."""
    repetitions = len(inputs.plan.negative)
    _refuse_unexpected_inputs(input_dir, repetitions)
    negatives: list[NegativeRepetitionRecord] = []
    digests: list[InputDigest] = []
    for index, declared in enumerate(inputs.plan.negative):
        record, digest = _read(input_dir / negative_record_name(index), NegativeRepetitionRecord)
        if record.repetition != index:
            raise ControlsRunError(
                f"{digest.name} records repetition {record.repetition}: a repetition is filed "
                "once, under its own index, so this record duplicates another"
            )
        if record.independent_seed_sets != repetitions:
            raise ControlsRunError(
                f"{digest.name} was planned for {record.independent_seed_sets} repetitions, not "
                f"the {repetitions} declared"
            )
        _refuse_off_plan(
            digest.name, record, declared, (NEGATIVE_SUBJECT_ARM, NEGATIVE_COMPARATOR_ARM)
        )
        _refuse_unreproduced_interval(digest.name, record, inputs.contract)
        negatives.append(record)
        digests.append(digest)
    positive, positive_digest = _read(input_dir / POSITIVE_RECORD_NAME, PositiveControlRecord)
    _refuse_off_plan(
        positive_digest.name,
        positive,
        (inputs.plan.positive, inputs.plan.positive),
        (STRUCTURE_AWARE_ARM, TUNED_STATIC_ARM),
    )
    _refuse_unreproduced_interval(positive_digest.name, positive, inputs.contract)
    for record, digest in zip(negatives, digests, strict=True):
        if record.provenance != positive.provenance:
            raise ControlsRunError(
                f"{digest.name} and {POSITIVE_RECORD_NAME} carry different provenance (run "
                f"{record.provenance.run_id!r} at {record.provenance.revision!r} against run "
                f"{positive.provenance.run_id!r} at {positive.provenance.revision!r}): one "
                "verdict judges one run's records"
            )
    if positive.provenance.bprime_artifact_sha256 != inputs.bprime_artifact_sha256:
        raise ControlsRunError(
            "the records were measured against B-prime artifact "
            f"{positive.provenance.bprime_artifact_sha256}, not the committed "
            f"{inputs.bprime_artifact_sha256}"
        )
    if positive.provenance.loop != inputs.loop:
        raise ControlsRunError(
            f"the records ran the loop {positive.provenance.loop!r}, not {inputs.loop!r}"
        )
    refuse_foreign_reproduction(
        positive.reproduction,
        artifact_sha256=inputs.bprime_artifact_sha256,
        seeds=inputs.bprime_measurement_seeds,
    )
    return _LoadedRecords(
        negatives=tuple(negatives),
        negative_inputs=tuple(digests),
        positive=positive,
        positive_input=positive_digest,
    )


@dataclasses.dataclass(frozen=True)
class _Readings:
    negative: NegativeControlReading
    positive: PositiveControlReading
    agreement: AgreementReading | None
    repetitions: tuple[JudgedInterval | None, ...]


def _judge(records: _LoadedRecords, inputs: VerdictInputs) -> _Readings:
    """The three classifiers over the loaded records, oriented as ``uplift/controls.py`` states.

    The harness's ``E - O`` is the positive control's interval (comparator E minus subject O);
    B-prime's ``E - O`` is the comparator estimate and its ``E - D`` the ceiling. The agreement
    reading is formed only where every B-prime arm reproduced in the positive leg's environment;
    otherwise it is ``None`` and :class:`AgreementVerdictRecord` records why.
    """
    judged = tuple(
        None if record.interval is None else JudgedInterval.of(record.interval)
        for record in records.negatives
    )
    repetitions = [
        NegativeRepetition(
            index=index,
            subject_seeds=record.subject.seeds,
            comparator_seeds=record.comparator.seeds,
            interval=interval,
        )
        for index, (record, interval) in enumerate(zip(records.negatives, judged, strict=True))
        if interval is not None
    ]
    negative = classify_negative_control(
        repetitions,
        required_repetitions=len(records.negatives),
        max_proven_gain_rate=inputs.max_proven_gain_rate,
    )
    stored = records.positive.interval
    harness = None if stored is None else JudgedInterval.of(stored)
    agreement: AgreementReading | None = None
    if records.positive.reproduction.all_reproduce:
        agreement = classify_agreement(
            harness=harness,
            comparator=inputs.comparator_e_minus_o,
            ceiling=inputs.ceiling_e_minus_d,
        )
    return _Readings(
        negative=negative,
        positive=classify_positive_control(harness),
        agreement=agreement,
        repetitions=judged,
    )


def _variance_source(positive: PositiveControlRecord) -> str:
    provenance = positive.provenance
    loop = provenance.loop
    return (
        "sample variance (n - 1) of the per-replicate paired objective difference "
        f"{positive.comparator.arm} - {positive.subject.arm} (arm E minus arm O): the positive "
        f"control on {positive.subject.seeds.describe()}, scenario {provenance.scenario}, "
        f"{loop.duration_hours:g} h at {loop.step_hours:g} h steps ({loop.levers}); run "
        f"{provenance.run_id} at revision {provenance.revision}"
    )


def _power_report(records: _LoadedRecords, inputs: VerdictInputs) -> PowerReport | str:
    """The Power_Report the positive control's paired variance supports, or why there is none."""
    positive = records.positive
    if inputs.materiality_margin is None:
        return (
            "materiality_margin() returned None -- R5.2's deferral holds -- so no Power_Report "
            "can be derived against a margin"
        )
    subject, comparator = positive.subject.costs, positive.comparator.costs
    if subject is None or comparator is None:
        return (
            f"the positive control is unavailable ({positive.unavailable_reason}), so no paired "
            "variance was observed to state a power against"
        )
    differences = [e - o for o, e in zip(subject, comparator, strict=True)]
    if len(differences) < 2:
        return f"the positive control paired {len(differences)} replicate(s); a variance needs two"
    try:
        return build_power_report(
            root=inputs.root,
            source_set=POWER_SOURCE_SET,
            source_run_id=records.provenance.run_id,
            source_revision_sha=records.provenance.revision,
            replicates_per_arm=positive.replicates,
            observed_variance=statistics.variance(differences),
            variance_source=_variance_source(positive),
            alpha=inputs.alpha,
            detection_probability=inputs.detection_probability,
            materiality_margin=inputs.materiality_margin,
            comparator=TUNED_STATIC_ARM,
        )
    except PowerReportError as error:
        return f"build_power_report refused the positive control's inputs: {error}"


@dataclasses.dataclass(frozen=True)
class VerdictOutcome:
    """What one verdict wrote: the three readings, and the Power_Report or why there is none."""

    negative: NegativeControlReading
    positive: PositiveControlReading
    agreement: AgreementVerdictRecord
    power_report: PowerReport | None
    power_report_absence: str | None
    written: tuple[Path, ...]


def write_verdict(input_dir: Path, output_dir: Path, inputs: VerdictInputs) -> VerdictOutcome:
    """Judge the control records in ``input_dir`` and write the verdict into ``output_dir``.

    Every input is read and checked, and every output built, BEFORE the first file is written,
    so a refusal leaves no partial verdict behind. A failed or unavailable control is written
    like any other reading, and so is an agreement left unavailable because B-prime's arms did
    not reproduce in the positive leg's environment.

    Raises:
        ControlsRunError: The output directory is occupied; the input directory does not hold
            exactly the declared records; a record is unreadable, inadmissible, off the plan,
            from another run, B-prime record or loop, stores an interval its costs do not
            reproduce, or carries a reproduction of another B-prime artifact or other seeds.
        ValueError: A classifier refused an input, such as an interval at another alpha.
    """
    target = Path(output_dir)
    _refuse_occupied(target)
    records = _load_records(Path(input_dir), inputs)
    readings = _judge(records, inputs)
    built = _power_report(records, inputs)
    provenance = records.provenance
    positive_inputs = (records.positive_input,)
    agreement = AgreementVerdictRecord.judge(
        provenance=provenance,
        inputs=positive_inputs,
        reproduction=records.positive.reproduction,
        reading=readings.agreement,
    )
    outputs: list[tuple[Path, BaseModel]] = [
        (
            target / NEGATIVE_VERDICT_NAME,
            NegativeVerdictRecord(
                kind="negative-control-verdict",
                schema_version=1,
                provenance=provenance,
                inputs=records.negative_inputs,
                repetitions=readings.repetitions,
                reading=readings.negative,
            ),
        ),
        (
            target / POSITIVE_VERDICT_NAME,
            PositiveVerdictRecord(
                kind="positive-control-verdict",
                schema_version=1,
                provenance=provenance,
                inputs=positive_inputs,
                reading=readings.positive,
            ),
        ),
        (target / AGREEMENT_VERDICT_NAME, agreement),
    ]
    if isinstance(built, str):
        outputs.append(
            (
                target / POWER_REPORT_ABSENT_NAME,
                PowerReportAbsence(
                    kind="power-report-absent",
                    schema_version=1,
                    provenance=provenance,
                    inputs=positive_inputs,
                    reason=built,
                ),
            )
        )
    written = [write_record(path, model) for path, model in outputs]
    if not isinstance(built, str):
        written.append(write_power_report(built, target / POWER_REPORT_NAME))
    return VerdictOutcome(
        negative=readings.negative,
        positive=readings.positive,
        agreement=agreement,
        power_report=None if isinstance(built, str) else built,
        power_report_absence=built if isinstance(built, str) else None,
        written=tuple(written),
    )


# ---------------------------------------------------------------------------
# The CLI
# ---------------------------------------------------------------------------
#: What a subcommand refuses as an unreadable or inadmissible input: exit 2, never a traceback.
_REFUSALS: Final[tuple[type[Exception], ...]] = (
    ValueError,
    KeyError,
    OSError,
    PolicyUnavailableError,
    MetricContractError,
    IntervalUnavailableError,
    TuningUnavailableError,
    BprimeReproductionError,
)


def _say(line: str) -> None:
    sys.stdout.write(_ascii(line) + "\n")


def _leg_summary(label: str, record: _PairedContrast, path: Path) -> str:
    if record.interval is None:
        state = f"unavailable - {record.unavailable_reason}"
    else:
        state = JudgedInterval.of(record.interval).describe()
    return (
        f"[controls] {label}: {record.comparator.arm} - {record.subject.arm} on "
        f"{record.subject.seeds.describe()} / {record.comparator.seeds.describe()}: {state}; "
        f"wrote {path.as_posix()}"
    )


def _report_verdict(outcome: VerdictOutcome) -> None:
    readings: tuple[tuple[str, str, str], ...] = (
        ("negative control", outcome.negative.verdict, outcome.negative.explanation),
        ("positive control", outcome.positive.verdict, outcome.positive.explanation),
        ("agreement", outcome.agreement.verdict, outcome.agreement.explanation),
    )
    for label, verdict, explanation in readings:
        _say(f"[controls] {label}: {verdict} - {explanation}")
    report = outcome.power_report
    if report is None:
        _say(f"[controls] power report: NOT written - {outcome.power_report_absence}")
    else:
        _say(
            f"[controls] power report: written - minimum detectable effect "
            f"{report.minimum_detectable_effect:.6g} at {report.replicates_per_arm} replicates "
            f"per arm, derived requirement {report.derived_replicate_requirement}"
        )
    logger.info(
        "controls_verdict_written",
        negative=outcome.negative.verdict,
        positive=outcome.positive.verdict,
        agreement=outcome.agreement.verdict,
        power_report=report is not None,
        written=[path.as_posix() for path in outcome.written],
    )


def _guarded(command: str, action: Callable[[], None]) -> int:
    try:
        action()
    except _REFUSALS as error:
        detail = _ascii(f"{type(error).__name__}: {error}")
        logger.warning("controls_input_refused", command=command, error=detail)
        sys.stderr.write(f"[controls] {command} REFUSED - {detail}\n")
        return EXIT_REFUSED
    return EXIT_WRITTEN


def _negative(repetition: int, output: Path) -> None:
    production = _production()
    require_repetition(repetition, len(production.setup.plan.negative))
    record = measure_negative(
        repetition,
        setup=production.setup,
        arm_e=tuned_static_arm(production.record),
        runner=production_arm_runner(),
    )
    path = write_record(output, record)
    _say(_leg_summary(f"negative repetition {repetition}", record, path))
    logger.info(
        "controls_negative_recorded",
        repetition=repetition,
        estimated=record.interval is not None,
        path=path.as_posix(),
    )


def _reproduction_summary(arm: ArmReproduction, seeds: SeedRange) -> str:
    state = "reproduces" if arm.reproduces else "does NOT reproduce"
    return (
        f"[controls] B-prime reproduction: {arm.arm} on {seeds.describe()}: measured "
        f"{arm.measured_mean!r}, recorded {arm.recorded_mean!r} - {state}"
    )


def _positive(output: Path) -> None:
    production = _production()
    arm_e = tuned_static_arm(production.record)
    skus = stocked_skus(ARM_CONSTRUCTION_SEED, world=production.world)
    arm_o = structure_aware_arm(production.world, skus, E5_LOOP)
    # Every arm B-prime measured, at its seeds, in THIS job's environment, through the one
    # reproduction `uplift.e5_suite` owns -- never a second -- and before the harness legs, so a
    # refusal there costs the least.
    reproduction = measure_bprime_reproduction(
        production.record, REPRODUCED_ARMS, cost_of=production_arm_cost
    )
    for reproduced in reproduction.arms:
        _say(_reproduction_summary(reproduced, reproduction.seeds))
    record = measure_positive(
        setup=production.setup,
        arm_o=arm_o,
        arm_e=arm_e,
        runner=production_arm_runner(),
        reproduction=reproduction,
    )
    path = write_record(output, record)
    _say(_leg_summary("positive control", record, path))
    logger.info(
        "controls_positive_recorded",
        estimated=record.interval is not None,
        bprime_reproduces=reproduction.all_reproduce,
        path=path.as_posix(),
    )


def verdict_command(input_dir: Path, output_dir: Path, inputs: VerdictInputs) -> int:
    """``verdict`` over explicitly given inputs, with the CLI's exit semantics."""
    return _guarded(
        "verdict", lambda: _report_verdict(write_verdict(input_dir, output_dir, inputs))
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m uplift.controls_run",
        description=(
            "E3's controls (decision-quality-proof task 16.7): the negative and positive control "
            "legs, and the verdict that classifies them and writes the Power_Report."
        ),
    )
    commands = parser.add_subparsers(dest="command", required=True)
    negative = commands.add_parser(
        "negative", help="one repetition: arm E against itself on two disjoint seed ranges"
    )
    negative.add_argument("--repetition", type=int, required=True, metavar="K")
    negative.add_argument("--output", type=Path, required=True)
    positive = commands.add_parser("positive", help="arm O against arm E on one shared seed range")
    positive.add_argument("--output", type=Path, required=True)
    verdict = commands.add_parser(
        "verdict", help="classify every control record and write the Power_Report"
    )
    verdict.add_argument("--input-dir", type=Path, required=True)
    verdict.add_argument("--output-dir", type=Path, required=True)
    return parser


def main(argv: Sequence[str]) -> int:
    """Run one subcommand; :data:`EXIT_WRITTEN` once its records are written, else refused."""
    args = _parser().parse_args(list(argv))
    command: str = args.command
    if command == "negative":
        repetition: int = args.repetition
        negative_output: Path = args.output
        return _guarded(command, lambda: _negative(repetition, negative_output))
    if command == "positive":
        positive_output: Path = args.output
        return _guarded(command, lambda: _positive(positive_output))
    input_dir: Path = args.input_dir
    output_dir: Path = args.output_dir
    return _guarded(
        command,
        lambda: _report_verdict(write_verdict(input_dir, output_dir, production_verdict_inputs())),
    )


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
