"""The committed B-prime record: arm E's levels, its seeds and its split, read or refused.

Feature: decision-quality-proof, session 12 (wave 2). Checkpoint B-prime (run 36860454801, sha
ec0eb91, artifact ``twin-regret-primary``) tuned arm E in the PRIMARY cell at 200 replicates x
24 h and measured the split ``E - O`` and ``E - D`` on seeds ``0..199``. The E5 suite measures
the consensus arm against THAT arm E, and the controls read THAT split -- so this module is the
one place either learns what B-prime found, and it reads it from two committed files:

* :data:`BPRIME_ARTIFACT_PATH` -- the CI artifact itself, byte-exact (sha256 pinned);
* :data:`BPRIME_PROVENANCE_PATH` -- canonical JSON naming the run, the revision, the artifact's
  sha256, the physics source set and its digest, and a human attestation.

**Refused, never defaulted** (:class:`BprimeRecordError`): either file missing or unreadable; a
provenance file that is not exactly its schema, or not canonical JSON; an artifact whose sha256
is not the one the provenance pins; a physics digest that differs from the tree's -- **the
record then describes another physics: re-measure, never re-use**; and an artifact that is not
a converged, admissible, fully-usable measurement of the primary cell.

**The digest names a tree; only a re-measurement evidences one** (API2 amendment 1.3). The
record therefore carries the three means B-prime MEASURED -- arm E's, arm E-prime's and arm O's
over the measurement seeds, each a required finite float read from the artifact key of the same
name -- so :func:`uplift.e5_suite.measure_bprime_reproduction` can re-measure them in another
environment and compare each EXACTLY. A missing, null or non-finite mean is refused by name.

**What the digest does and does not bind (stated so it is not overclaimed).** The digest is
:func:`uplift.power.source_set_digest` over :data:`BPRIME_PHYSICS_SET` AS IT STANDS WHEN THE
RECORD IS COMMITTED. It proves that nothing arm E's physics executes has changed SINCE that
commit; it cannot prove the tree at that commit executes what ec0eb91 executed. That gap is
what ``attestation`` names, and it is a human statement, not a measurement.

**Building the provenance file.** :func:`build_bprime_provenance` computes both digests from
the tree and :func:`write_bprime_provenance` writes the canonical bytes the reader requires, so
the file is generated rather than typed.

Pure: no engine import, no RNG, no clock.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path
from typing import TYPE_CHECKING, Final, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    StrictInt,
    ValidationError,
    field_validator,
    model_validator,
)

from uplift.controls import SeedRange
from uplift.power import PowerReportError, source_set_digest
from uplift.tuned_static import GroupLevels
from uplift.tuning import GridPoint, TuningUnavailableError

if TYPE_CHECKING:  # pragma: no cover - annotations only
    from collections.abc import Mapping

__all__ = [
    "BPRIME_ARTIFACT_PATH",
    "BPRIME_CELL",
    "BPRIME_PHYSICS_SET",
    "BPRIME_PROVENANCE_KIND",
    "BPRIME_PROVENANCE_PATH",
    "BPRIME_PROVENANCE_SCHEMA_VERSION",
    "BprimeProvenance",
    "BprimeRecord",
    "BprimeRecordError",
    "IntervalRecord",
    "build_bprime_provenance",
    "read_bprime_record",
    "write_bprime_provenance",
]

#: The CI artifact B-prime wrote, committed byte-exact. Repo-relative, POSIX.
BPRIME_ARTIFACT_PATH: Final[str] = "docs/state/bprime/twin-regret-primary.json"

#: The provenance record beside it, canonical JSON. Repo-relative, POSIX.
BPRIME_PROVENANCE_PATH: Final[str] = "docs/state/bprime/provenance.json"

#: What arm E's physics executes: the twin's simulation layer and the files it reads, the tuning
#: grid, and every uplift module on the path ``regret._measure`` drives arm E through. A change
#: to any of them is a change to the physics the record describes. Over-inclusion errs in the
#: safe direction -- an unrelated edit to one of these files forces a re-measurement, while an
#: omission would let a stale record license a measurement.
BPRIME_PHYSICS_SET: Final[tuple[str, ...]] = (
    "digital_twin/simulation/*.py",
    "digital_twin/simulation/policy.yaml",
    "digital_twin/config.py",
    "infrastructure/quality/comparator-tuning.yaml",
    "uplift/foresight.py",
    "uplift/harness.py",
    "uplift/regret.py",
    "uplift/tuning.py",
    "uplift/tuned_static.py",
    "uplift/oracle_arm.py",
    "uplift/baselines/*.py",
)

#: The provenance file's declared kind; a regret artifact carries none.
BPRIME_PROVENANCE_KIND: Final[Literal["bprime-record-provenance"]] = "bprime-record-provenance"

#: Bumped, never edited in place, if a provenance field is added, removed or redefined.
BPRIME_PROVENANCE_SCHEMA_VERSION: Final[Literal[1]] = 1

#: The only cell a record may describe: E5 runs the primary cell (decision D12.2=a).
BPRIME_CELL: Final[str] = "primary"

_GIT_SHA: Final[re.Pattern[str]] = re.compile(r"[0-9a-f]{40}")
_SHA256: Final[re.Pattern[str]] = re.compile(r"[0-9a-f]{64}")
_LEVEL_KEYS: Final[frozenset[str]] = frozenset({"s", "S"})


class BprimeRecordError(ValueError):
    """No admissible B-prime record: refused, never repaired with a substituted value (I-7)."""


def _canonical(payload: object) -> str:
    """The repo-canonical serialisation: sorted keys, tight separators."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def _non_blank(value: str, what: str) -> str:
    if not value.strip():
        raise ValueError(f"{what} is blank; a record must name it")
    return value


def _hex(value: str, pattern: re.Pattern[str], what: str) -> str:
    if pattern.fullmatch(value) is None:
        raise ValueError(f"{what} {value!r} is not lowercase hex of the required length")
    return value


# ---------------------------------------------------------------------------
# The provenance file
# ---------------------------------------------------------------------------
class BprimeProvenance(BaseModel):
    """The provenance file, exactly: nine keys, each checked, no other key admitted.

    ``physics_set`` must equal :data:`BPRIME_PHYSICS_SET` in order: a digest over any other set
    is a digest of some other instrument.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal["bprime-record-provenance"]
    schema_version: Literal[1]
    source_run_id: str
    source_revision_sha: str
    artifact_name: str
    artifact_sha256: str
    physics_set: tuple[str, ...]
    physics_digest: str
    attestation: str

    @field_validator("schema_version", mode="before")
    @classmethod
    def _version_one_only(cls, value: object) -> object:
        """Only the integer 1: ``True`` equals ``1`` in Python and is still not a version."""
        if type(value) is not int or value != BPRIME_PROVENANCE_SCHEMA_VERSION:
            raise ValueError(
                f"provenance schema_version {value!r} is not {BPRIME_PROVENANCE_SCHEMA_VERSION}"
            )
        return value

    @field_validator("source_run_id", "artifact_name", "attestation")
    @classmethod
    def _named(cls, value: str) -> str:
        return _non_blank(value, "a provenance field")

    @field_validator("source_revision_sha")
    @classmethod
    def _revision(cls, value: str) -> str:
        return _hex(value, _GIT_SHA, "source_revision_sha")

    @field_validator("artifact_sha256", "physics_digest")
    @classmethod
    def _digest(cls, value: str) -> str:
        return _hex(value, _SHA256, "a sha256 digest")

    @field_validator("physics_set")
    @classmethod
    def _declared_physics(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if value != BPRIME_PHYSICS_SET:
            raise ValueError(
                f"physics_set {list(value)} is not the declared BPRIME_PHYSICS_SET "
                f"{list(BPRIME_PHYSICS_SET)}; a digest over another set names another instrument"
            )
        return value

    def to_canonical_json(self) -> str:
        """The exact bytes :func:`read_bprime_record` requires of the file."""
        return _canonical(self.model_dump(mode="json"))


def build_bprime_provenance(
    root: Path,
    *,
    source_run_id: str,
    source_revision_sha: str,
    artifact_name: str,
    attestation: str,
) -> BprimeProvenance:
    """The provenance for the artifact committed under ``root``, digests computed from the tree.

    Raises:
        BprimeRecordError: The artifact is missing or unreadable, the physics set cannot be
            digested, or a supplied field is inadmissible.
    """
    base = Path(root)
    artifact = _read_bytes(base / BPRIME_ARTIFACT_PATH, "the B-prime artifact")
    try:
        physics_digest = source_set_digest(base, BPRIME_PHYSICS_SET)
    except PowerReportError as error:
        raise BprimeRecordError(f"the physics set cannot be digested: {error}") from error
    try:
        return BprimeProvenance(
            kind=BPRIME_PROVENANCE_KIND,
            schema_version=BPRIME_PROVENANCE_SCHEMA_VERSION,
            source_run_id=source_run_id,
            source_revision_sha=source_revision_sha,
            artifact_name=artifact_name,
            artifact_sha256=hashlib.sha256(artifact).hexdigest(),
            physics_set=BPRIME_PHYSICS_SET,
            physics_digest=physics_digest,
            attestation=attestation,
        )
    except ValidationError as error:
        raise BprimeRecordError(f"inadmissible provenance: {error}") from error


def write_bprime_provenance(root: Path, provenance: BprimeProvenance) -> Path:
    """Write ``provenance``'s canonical bytes to :data:`BPRIME_PROVENANCE_PATH` under ``root``."""
    target = Path(root) / BPRIME_PROVENANCE_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(provenance.to_canonical_json(), encoding="utf-8")
    return target


# ---------------------------------------------------------------------------
# The record
# ---------------------------------------------------------------------------
class IntervalRecord(BaseModel):
    """One of B-prime's split intervals, as recorded: finite and ``low <= point <= high``."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    low: float
    high: float
    point: float

    @model_validator(mode="after")
    def _admissible(self) -> IntervalRecord:
        for name, value in (("low", self.low), ("high", self.high), ("point", self.point)):
            if not math.isfinite(value):
                raise ValueError(f"interval {name}={value!r} is not finite")
        if not self.low <= self.point <= self.high:
            raise ValueError(
                f"interval [{self.low!r}, {self.high!r}] does not bracket its point {self.point!r}"
            )
        return self


def _group_levels(levels: Mapping[str, Mapping[str, int]]) -> GroupLevels:
    """The ``{group: {"S": S, "s": s}}`` mapping as the :class:`GroupLevels` arm E acts on."""
    return GroupLevels(
        {group: GridPoint(s=pair["s"], S=pair["S"]) for group, pair in levels.items()}
    )


class BprimeRecord(BaseModel):
    """What checkpoint B-prime measured, as the E5 suite and the controls read it.

    Construction re-checks what the reader checked, so a record built by hand -- in a test, or
    by the next wave -- obeys the same rules: identifiers in their formats; a positive replicate
    count that the measurement seed range spans exactly; non-empty, distinct, non-negative tuning
    seeds disjoint from the measurement seeds; two level maps over the same groups, each pair
    exactly ``{"S", "s"}`` and admissible as a ``(s, S)`` grid point; ``alpha`` in ``(0, 1)``;
    and the three measured means finite.

    The three means are what B-prime measured over its measurement seeds, under the names its
    artifact gives them: ``mean_tuned_static_cost`` (arm E), ``mean_in_sample_tuned_static_cost``
    (arm E', the in-sample re-choice) and ``mean_structure_aware_cost`` (arm O). They are the
    behavioural evidence a physics digest cannot give (API2 amendment 1.3).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    source_run_id: str
    source_revision_sha: str
    artifact_sha256: str
    cell: str
    replicates: StrictInt
    hours_per_replicate: float
    tuning_seeds: tuple[StrictInt, ...]
    measurement_seeds: SeedRange
    tuned_static_levels: dict[str, dict[str, StrictInt]]
    in_sample_levels: dict[str, dict[str, StrictInt]]
    e_minus_o: IntervalRecord
    e_minus_d: IntervalRecord
    alpha: float
    mean_tuned_static_cost: float
    mean_in_sample_tuned_static_cost: float
    mean_structure_aware_cost: float

    @field_validator("source_run_id", "cell")
    @classmethod
    def _named(cls, value: str) -> str:
        return _non_blank(value, "a record field")

    @field_validator("source_revision_sha")
    @classmethod
    def _revision(cls, value: str) -> str:
        return _hex(value, _GIT_SHA, "source_revision_sha")

    @field_validator("artifact_sha256")
    @classmethod
    def _artifact_digest(cls, value: str) -> str:
        return _hex(value, _SHA256, "artifact_sha256")

    @model_validator(mode="after")
    def _admissible(self) -> BprimeRecord:
        if self.replicates < 1:
            raise ValueError(f"replicates={self.replicates} measures nothing")
        if self.measurement_seeds.count != self.replicates:
            raise ValueError(
                f"the measurement seed range {self.measurement_seeds.describe()} spans "
                f"{self.measurement_seeds.count} seeds, not the {self.replicates} replicates"
            )
        if not (math.isfinite(self.hours_per_replicate) and self.hours_per_replicate > 0.0):
            raise ValueError(f"hours_per_replicate={self.hours_per_replicate!r} is not > 0")
        if not (math.isfinite(self.alpha) and 0.0 < self.alpha < 1.0):
            raise ValueError(f"alpha={self.alpha!r} lies outside (0, 1)")
        for name, mean in (
            ("mean_tuned_static_cost", self.mean_tuned_static_cost),
            ("mean_in_sample_tuned_static_cost", self.mean_in_sample_tuned_static_cost),
            ("mean_structure_aware_cost", self.mean_structure_aware_cost),
        ):
            if not math.isfinite(mean):
                raise ValueError(f"{name}={mean!r} is not finite, so it is no measured mean")
        self._check_seeds()
        self._check_levels()
        return self

    def _check_seeds(self) -> None:
        seeds = self.tuning_seeds
        if not seeds:
            raise ValueError("no tuning seeds are recorded, so arm E's search has no provenance")
        if any(seed < 0 for seed in seeds):
            raise ValueError("a tuning seed is negative")
        if len(set(seeds)) != len(seeds):
            raise ValueError("a tuning seed is recorded twice")
        start, stop = self.measurement_seeds.start, self.measurement_seeds.stop
        shared = sorted(seed for seed in seeds if start <= seed < stop)
        if shared:
            raise ValueError(
                f"tuning seeds {shared[:5]} lie inside the measurement range "
                f"{self.measurement_seeds.describe()}; B-prime tunes and measures on "
                "disjoint seeds"
            )

    def _check_levels(self) -> None:
        for name, levels in (
            ("tuned_static_levels", self.tuned_static_levels),
            ("in_sample_levels", self.in_sample_levels),
        ):
            if not levels:
                raise ValueError(f"{name} names no group")
            for group, pair in levels.items():
                if set(pair) != _LEVEL_KEYS:
                    raise ValueError(
                        f"{name}.{group} has keys {sorted(pair)}, not exactly {sorted(_LEVEL_KEYS)}"
                    )
            try:
                _group_levels(levels)
            except TuningUnavailableError as error:
                raise ValueError(f"{name} is not admissible: {error}") from error
        if set(self.tuned_static_levels) != set(self.in_sample_levels):
            raise ValueError(
                f"arm E names groups {sorted(self.tuned_static_levels)} and arm E' names "
                f"{sorted(self.in_sample_levels)}; both are one rule over one world's groups"
            )

    def arm_e_levels(self) -> GroupLevels:
        """Arm E's levels: the out-of-sample selection B-prime tuned on its tuning seeds."""
        return _group_levels(self.tuned_static_levels)

    def arm_e_prime_levels(self) -> GroupLevels:
        """Arm E-prime's levels: the in-sample re-choice on the measurement seeds (W2b R1)."""
        return _group_levels(self.in_sample_levels)


# ---------------------------------------------------------------------------
# The reader
# ---------------------------------------------------------------------------
def _read_bytes(path: Path, what: str) -> bytes:
    try:
        return path.read_bytes()
    except FileNotFoundError as error:
        raise BprimeRecordError(f"{what} is missing at {path.as_posix()}") from error
    except OSError as error:
        raise BprimeRecordError(f"{what} at {path.as_posix()} is unreadable: {error}") from error


def _json_object(raw: bytes, what: str) -> dict[str, object]:
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise BprimeRecordError(f"{what} is not UTF-8 JSON: {error}") from error
    if not isinstance(payload, dict):
        raise BprimeRecordError(f"{what} is a JSON {type(payload).__name__}, not an object")
    return payload


def _read_provenance(raw: bytes) -> BprimeProvenance:
    what = f"the B-prime provenance ({BPRIME_PROVENANCE_PATH})"
    payload = _json_object(raw, what)
    try:
        provenance = BprimeProvenance.model_validate(payload)
    except ValidationError as error:
        raise BprimeRecordError(f"{what} does not satisfy its schema: {error}") from error
    if raw.decode("utf-8") != provenance.to_canonical_json():
        raise BprimeRecordError(
            f"{what} is not canonical JSON (sorted keys, tight separators, no trailing "
            "newline); write it with write_bprime_provenance so its bytes are reproducible"
        )
    return provenance


def _field(artifact: Mapping[str, object], key: str) -> object:
    if key not in artifact:
        raise BprimeRecordError(f"the B-prime artifact carries no {key!r}")
    return artifact[key]


def _require_value(artifact: Mapping[str, object], key: str, expected: object, why: str) -> None:
    """Refuse unless ``artifact[key]`` IS ``expected`` (booleans) or equals it (strings)."""
    value = _field(artifact, key)
    same = value is expected if isinstance(expected, bool) else value == expected
    if not same:
        raise BprimeRecordError(
            f"the B-prime artifact records {key}={value!r}, not {expected!r}: {why}"
        )


def _int(artifact: Mapping[str, object], key: str) -> int:
    value = _field(artifact, key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise BprimeRecordError(f"the B-prime artifact's {key}={value!r} is not an integer")
    return value


def _float(artifact: Mapping[str, object], key: str) -> float:
    value = _field(artifact, key)
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise BprimeRecordError(f"the B-prime artifact's {key}={value!r} is not a number")
    return float(value)


def _finite_float(artifact: Mapping[str, object], key: str) -> float:
    """``artifact[key]`` as a finite float, or a refusal naming the key and the defect.

    A measured mean is never substituted: absent, ``null``, not a number, or not finite (JSON's
    ``NaN``/``Infinity`` tokens decode to floats) is each refused, by name.
    """
    value = _field(artifact, key)
    if value is None:
        raise BprimeRecordError(f"the B-prime artifact's {key} is null, so it measured no mean")
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise BprimeRecordError(f"the B-prime artifact's {key}={value!r} is not a number")
    try:
        number = float(value)
    except OverflowError:
        number = math.inf
    if not math.isfinite(number):
        raise BprimeRecordError(f"the B-prime artifact's {key}={value!r} is not finite")
    return number


def _seeds(artifact: Mapping[str, object], key: str) -> tuple[int, ...]:
    value = _field(artifact, key)
    if not isinstance(value, list):
        raise BprimeRecordError(f"the B-prime artifact's {key} is not a list of integers")
    seeds: list[int] = []
    for seed in value:
        if isinstance(seed, bool) or not isinstance(seed, int):
            raise BprimeRecordError(f"the B-prime artifact's {key} holds {seed!r}, not a seed")
        seeds.append(seed)
    return tuple(seeds)


def _levels(artifact: Mapping[str, object], key: str) -> dict[str, dict[str, int]]:
    value = _field(artifact, key)
    if not isinstance(value, dict):
        raise BprimeRecordError(f"the B-prime artifact's {key} is not an object")
    levels: dict[str, dict[str, int]] = {}
    for group, pair in value.items():
        if not isinstance(pair, dict):
            raise BprimeRecordError(f"the B-prime artifact's {key}.{group} is not an object")
        parsed: dict[str, int] = {}
        for name, level in pair.items():
            if isinstance(level, bool) or not isinstance(level, int):
                raise BprimeRecordError(
                    f"the B-prime artifact's {key}.{group}.{name}={level!r} is not an integer"
                )
            parsed[str(name)] = level
        levels[str(group)] = parsed
    return levels


def _interval(artifact: Mapping[str, object], key: str) -> IntervalRecord:
    value = _field(artifact, key)
    try:
        return IntervalRecord.model_validate(value)
    except ValidationError as error:
        raise BprimeRecordError(f"the B-prime artifact's {key} is inadmissible: {error}") from error


def read_bprime_record(root: Path) -> BprimeRecord:
    """The committed B-prime record under ``root``, or a :class:`BprimeRecordError` naming why.

    Checked in this order, each a refusal: both files present and readable; the provenance
    exactly its schema and canonical; the artifact's sha256 the provenance's; the physics digest
    of the tree the provenance's (otherwise the record describes another physics -- re-measure,
    never re-use); then the artifact: cell ``"primary"``, ``primary_cell`` true, ``status``
    ``"measured"``, no unusable replicate, a converged search, an admissible split, neither
    tuning seam injected, and the three measured means present, non-null and finite.

    Raises:
        BprimeRecordError: On any of the above, never returning a partial or defaulted record.
    """
    base = Path(root)
    artifact_bytes = _read_bytes(base / BPRIME_ARTIFACT_PATH, "the B-prime artifact")
    provenance = _read_provenance(
        _read_bytes(base / BPRIME_PROVENANCE_PATH, "the B-prime provenance")
    )
    measured_sha = hashlib.sha256(artifact_bytes).hexdigest()
    if measured_sha != provenance.artifact_sha256:
        raise BprimeRecordError(
            f"the B-prime artifact's sha256 is {measured_sha}, not the "
            f"{provenance.artifact_sha256} its provenance pins: it is not the CI artifact the "
            "record names"
        )
    try:
        tree_digest = source_set_digest(base, BPRIME_PHYSICS_SET)
    except PowerReportError as error:
        raise BprimeRecordError(f"the physics set cannot be digested: {error}") from error
    if tree_digest != provenance.physics_digest:
        raise BprimeRecordError(
            f"the physics digest of this tree is {tree_digest}, not the recorded "
            f"{provenance.physics_digest}: the record describes another physics, so arm E must "
            "be re-measured, never re-used"
        )
    artifact = _json_object(artifact_bytes, f"the B-prime artifact ({BPRIME_ARTIFACT_PATH})")
    _require_value(artifact, "cell", BPRIME_CELL, "E5 runs the primary cell")
    _require_value(artifact, "primary_cell", True, "the record must be the binding cell's")
    _require_value(artifact, "status", "measured", "only a measured comparator is a record")
    unusable = _int(artifact, "replicates_unusable")
    if unusable != 0:
        raise BprimeRecordError(
            f"the B-prime artifact records replicates_unusable={unusable}: its split is over a "
            "subset of its seeds, so no seed range can name what it measured"
        )
    _require_value(artifact, "tuned_static_converged", True, "arm E's search must have converged")
    _require_value(artifact, "split_admissible", True, "the split's intervals must be admissible")
    _require_value(artifact, "tuning_seeds_injected", False, "arm E's seeds must be committed")
    _require_value(
        artifact, "tuned_static_candidates_injected", False, "arm E's grid must be committed"
    )
    replicates = _int(artifact, "replicates_usable")
    try:
        return BprimeRecord(
            source_run_id=provenance.source_run_id,
            source_revision_sha=provenance.source_revision_sha,
            artifact_sha256=provenance.artifact_sha256,
            cell=BPRIME_CELL,
            replicates=replicates,
            hours_per_replicate=_float(artifact, "hours_per_replicate"),
            tuning_seeds=_seeds(artifact, "tuning_seeds"),
            # `_measure` iterates `range(replicates)`, so the measurement seeds are 0..n-1.
            measurement_seeds=SeedRange(start=0, count=replicates),
            tuned_static_levels=_levels(artifact, "tuned_static_levels"),
            in_sample_levels=_levels(artifact, "in_sample_tuned_static_levels"),
            e_minus_o=_interval(artifact, "achievable_information_value_interval"),
            e_minus_d=_interval(artifact, "information_ceiling_interval"),
            alpha=_float(artifact, "interval_alpha"),
            mean_tuned_static_cost=_finite_float(artifact, "mean_tuned_static_cost"),
            mean_in_sample_tuned_static_cost=_finite_float(
                artifact, "mean_in_sample_tuned_static_cost"
            ),
            mean_structure_aware_cost=_finite_float(artifact, "mean_structure_aware_cost"),
        )
    except ValidationError as error:
        raise BprimeRecordError(
            f"the B-prime artifact is not an admissible record: {error}"
        ) from error
