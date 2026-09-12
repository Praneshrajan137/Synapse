"""Prove a *real, published* production checkpoint exists and is calibrated.

Feature: purpose-achievement-audit, task 10.8 (design E5.2; R3.1, R3.3, R3.4, R3.6,
R3.7, R3.9). Hardens the gate the audit found too easy to satisfy.

ADR-043's C42 boots a checkpoint through the serving path -- but in CI that is the
*smoke* artifact. This gate is the authenticity counterpart: it verifies that an
operator actually ran the free-GPU full train (``docs/runbooks/train-and-publish-
checkpoint.md``) and published a genuine, non-smoke, adequately-calibrated checkpoint
to the declared $0 serving source, and that what is published matches what the
operator recorded in the committed registry.

What task 10.8 added
--------------------

===========================  ==============================================================
clause                       obligation
===========================  ==============================================================
``classification`` (R3.1)    three-way **absent / smoke / real** (plus ``indeterminate``),
                             each told apart by a detail a reader can act on. A smoke
                             artifact is never reported as a real one, and an artifact
                             that matches neither marker set is never *promoted* to real.
``coverage`` (R3.3)          the floor comparison reports **both** the measured value and
                             the floor, so nobody has to open this file to learn what it
                             compared against.
``sha-pin`` (R3.7)           the recorded sha must appear in the published version string.
``crps-recompute`` (R3.9)    ``final_crps`` is **recomputed** from the published sidecar's
                             held-out predictions and compared within a declared
                             tolerance. A recorded number nobody recomputed is not
                             evidence, so a sidecar publishing no held-out block is
                             ``unavailable`` -- never a pass.
``fetch`` (R3.6, R3.7)       when the recorded sha cannot be fetched from the declared
                             zero-cost source the gate **refuses to substitute a locally
                             built checkpoint** and names the candidate it refused. That
                             refusal is ``unavailable``, never a pass (I-7).
``policy``                   ``source.zero_cost`` must be true (I-1) and
                             ``source.allow_local_substitution`` must be false. Either pin
                             flipped is a FAIL, so the refusal cannot be configured away.
===========================  ==============================================================

What decision-quality-proof task 18 added
-----------------------------------------

===========================  ==============================================================
clause                       obligation
===========================  ==============================================================
``coverage-recompute``       ``coverage_p90`` is **recomputed** from the published held-out
(R8.9, R8.10, R9.14)         actuals against the published **conformal-adjusted**
                             ``lower_90``/``upper_90`` bounds over at least the committed
                             minimum row count. The ``coverage`` clause above -- a *read*
                             of ``calibrator.last_coverage_p90`` -- is retained as a
                             cross-check; this is the verdict. Below the floor is a FAIL
                             reporting the measured value and the floor; a block that is
                             absent, short, or missing the adjusted bounds is
                             ``unavailable``, never a pass. The bounds are read rather
                             than derived from ``predictions``, because the declared
                             ``quantile_levels`` span a nominal **80%** raw band and
                             INV-DP-002 is about the adjusted **90%** one.
===========================  ==============================================================

Every threshold, marker, floor, and tolerance is read from
``infrastructure/quality/checkpoint-truth.yaml`` (validated against its committed
draft-07 schema) rather than inlined here (AD-13). ``COVERAGE_FLOOR`` remains
importable, but it is now *derived from that file* instead of being a literal.

Two verdict surfaces, deliberately
----------------------------------

* :func:`assess` is the hardened gate: all seven clauses, outcomes
  ``pass / fail / skip / unavailable``, exit codes ``0 / 1 / 2 / 2``. This is what
  ``python -m scripts.audit.published_checkpoint_truth --check`` runs and, since
  decision-quality-proof task 18.3 (AD-19, R9.14), what **C46 registers**
  (``verify_claims.py::check_published_checkpoint``).
* :func:`evaluate` is the **narrower legacy probe** C46 called until that re-point. Its
  verdict is exactly the R5.3-R5.6 triad of the ``core-purpose-uplift`` spec --
  non-smoke, coverage at-or-above the floor, recorded sha pinned. It shares every clause
  helper with :func:`assess`, so there is one implementation of each rule and two
  projections of it. It is **retained, not deleted**: it is the legacy triad's surface
  and static reading did not enumerate its callers. **Do not point a gate at it.** Its
  three-valued ``ok / fail / skip`` vocabulary cannot express "nothing was recomputed",
  and it resolves that ambiguity in the direction I-7 forbids: it acts on
  ``Outcome.FAIL`` alone, so an ``UNAVAILABLE`` recompute falls through to ``ok``. For a
  landed entry whose sidecar publishes no held-out block -- every artifact ``train.py``
  produced before R9.13 -- :func:`assess` reports ``unavailable`` while the legacy triad
  reports ``ok``. That divergence is the finding task 18.3 closes, not a tolerated
  difference of opinion.

It is **$0-safe and never fabricates a pass**:

  * registry still at ``__placeholder__``  -> SKIP  (no operator has published yet)
  * recorded sha unfetchable               -> UNAVAILABLE, naming the refused local file
  * ``huggingface_hub`` absent             -> UNAVAILABLE (the remote cannot be read)
  * published sidecar marked ``smoke``     -> FAIL  (a smoke artifact is not production)
  * coverage below the committed floor     -> FAIL, reporting measured and floor
  * recorded sha != published version      -> FAIL  (drift between record and remote)
  * ``final_crps`` off beyond tolerance    -> FAIL, reporting recorded and recomputed
  * no held-out block to recompute from    -> UNAVAILABLE, naming what is missing

A second, network-free entry point validates the *record* the operator commits
(``--validate-registry``): the entry must carry every required key with a sane value
before it is worth cross-checking against the remote. It reports ``placeholder`` (not a
failure) while no operator has published -- landing a real entry is a runbook step, and
an absent model is stated honestly, never faked.

I-0: this gate reads committed files and, when a record has landed, fetches one small
JSON sidecar. It trains nothing, builds nothing, and loads no weights.

Run::

    python -m scripts.audit.published_checkpoint_truth            # human report
    python -m scripts.audit.published_checkpoint_truth --json     # canonical JSON
    python -m scripts.audit.published_checkpoint_truth --check    # exit 0/1/2
    python -m scripts.audit.published_checkpoint_truth --validate-registry   # schema only
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final

import structlog
import yaml
from jsonschema import Draft7Validator  # type: ignore[import-untyped]
from jsonschema.exceptions import SchemaError  # type: ignore[import-untyped]
from pydantic import BaseModel, ConfigDict, ValidationError

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence
    from typing import TypeAlias

    #: ``(repo_id, filename) -> local path``. Injected so a property test can drive the
    #: whole gate without a socket; the production default is :func:`fetch_from_hub`.
    SidecarFetcher: TypeAlias = Callable[[str, str], str]

logger = structlog.get_logger(__name__)

ROOT: Final[Path] = Path(__file__).resolve().parents[2]
POLICY_FILE: Final[Path] = ROOT / "infrastructure" / "quality" / "checkpoint-truth.yaml"
POLICY_SCHEMA_FILE: Final[Path] = (
    ROOT / "infrastructure" / "quality" / "schemas" / "checkpoint-truth.schema.json"
)

# The record the operator must commit for a published checkpoint. Every key is produced
# by the runbook's step-5 output; a partial record cannot be cross-checked against the
# remote, so it is an invalid record, not a pass.
REQUIRED_ENTRY_KEYS: tuple[str, ...] = (
    "repo",
    "sha",
    "coverage_p90",
    "final_crps",
    "trained_at",
    "rows",
)
_SHA_RE: Final[re.Pattern[str]] = re.compile(r"^[0-9a-f]{7,64}$")
_DATE_RE: Final[re.Pattern[str]] = re.compile(r"^\d{4}-\d{2}-\d{2}")
_MIN_SHA_LEN: Final[int] = 7
_PLACEHOLDER_KEY: Final[str] = "__placeholder__"

#: The published held-out keys carrying the **conformal-adjusted 90%** band, written by
#: ``agents/demand_prophet/training/train.py::HeldoutHorizon`` (R9.13). The coverage
#: recompute reads these and never the ``predictions`` quantile columns: the declared
#: ``quantile_levels`` ``[0.1, 0.5, 0.9]`` span a nominal **80%** raw band, so comparing
#: actuals against those columns would measure a different interval from the one
#: INV-DP-002 declares. They are literals here for the same reason ``"predictions"`` and
#: ``"actuals"`` already are -- they are the block's structure, not a threshold - and
#: ``checkpoint-truth.yaml``'s committed schema is ``additionalProperties: false`` at
#: every level, so the policy file cannot carry them without a schema change.
HELDOUT_LOWER_KEY: Final[str] = "lower_90"
HELDOUT_UPPER_KEY: Final[str] = "upper_90"

__all__ = [
    "COVERAGE_FLOOR",
    "HELDOUT_LOWER_KEY",
    "HELDOUT_UPPER_KEY",
    "POLICY_FILE",
    "POLICY_SCHEMA_FILE",
    "REGISTRY",
    "REQUIRED_ENTRY_KEYS",
    "SERVING_NAME",
    "ArtifactClass",
    "CheckpointPolicy",
    "CheckpointTruthReport",
    "Clause",
    "CoverageComparison",
    "CrpsRecompute",
    "Finding",
    "Outcome",
    "PolicyUnavailableError",
    "PublishProbe",
    "RegistryStatus",
    "assess",
    "classify",
    "compare_coverage",
    "evaluate",
    "fetch_from_hub",
    "format_report",
    "load_policy",
    "main",
    "policy",
    "recompute_coverage_p90",
    "recompute_final_crps",
    "refused_local_candidates",
    "registry_status",
    "run",
    "run_validate_registry",
    "sha_is_pinned",
    "validate_entry",
]


# ---------------------------------------------------------------------------
# Committed policy (AD-13 - read, never inlined)
# ---------------------------------------------------------------------------


class PolicyUnavailableError(RuntimeError):
    """The committed checkpoint-truth policy could not be read or is not valid.

    Never a pass: without the committed floors and tolerances there is nothing
    declared to judge against, and inventing one would be exactly the ungated number
    AD-13 forbids.
    """


class SourcePolicy(BaseModel):
    """The declared zero-cost serving source, and the substitution it forbids."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    kind: str
    zero_cost: bool
    env_var: str
    sidecar_filename: str
    checkpoint_filename: str
    allow_local_substitution: bool
    local_candidate_dir: str
    note: str | None = None


class SmokeMarkers(BaseModel):
    """How a smoke artifact identifies itself."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    sidecar_flag: str
    version_prefixes: tuple[str, ...]


class RealMarkers(BaseModel):
    """How a production artifact identifies itself."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    version_prefixes: tuple[str, ...]


class ClassificationPolicy(BaseModel):
    """The marker sets the three-way classification reads (R3.1, R3.4)."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    smoke: SmokeMarkers
    real: RealMarkers


class CoverageFloorPolicy(BaseModel):
    """The committed ``coverage_p90`` floor and where to read the measurement."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    value: float
    unit: str
    direction: str
    invariant: str
    sidecar_path: str
    registry_key: str
    documented_in: str | None = None
    note: str | None = None


class CrpsTolerancePolicy(BaseModel):
    """The declared tolerance the ``final_crps`` recompute must fall inside (R3.9)."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    absolute: float
    relative: float
    min_samples: int
    method: str
    quantile_levels: tuple[float, ...]
    sidecar_block: str
    registry_key: str
    note: str | None = None

    def allowance(self, recorded: float) -> float:
        """``max(absolute, relative * |recorded|)`` -- the declared allowance."""
        return max(self.absolute, self.relative * abs(recorded))


class ClaimPattern(BaseModel):
    """One way a task record can assert that a registry entry landed (R3.6)."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    id: str
    pattern: str
    description: str


class MustResolveEntry(BaseModel):
    """A task record the claim scanner must still be able to see (anti-vacuity)."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    spec: str
    task_id: str
    requirement: str
    note: str


class TaskClaimsPolicy(BaseModel):
    """How a task record asserting a landed registry entry is recognised (R3.6)."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    specs_dir: str
    tasks_filename: str
    assertion_patterns: tuple[ClaimPattern, ...]
    subject_markers: tuple[str, ...]
    must_resolve: tuple[MustResolveEntry, ...]


class FloorsPolicy(BaseModel):
    """Every floor this gate compares against."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    coverage_p90: CoverageFloorPolicy


class TolerancesPolicy(BaseModel):
    """Every tolerance this gate compares against."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    final_crps: CrpsTolerancePolicy


class CheckpointPolicy(BaseModel):
    """``infrastructure/quality/checkpoint-truth.yaml``, parsed."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    version: int
    serving_name: str
    registry_file: str
    source: SourcePolicy
    classification: ClassificationPolicy
    floors: FloorsPolicy
    tolerances: TolerancesPolicy
    task_claims: TaskClaimsPolicy


def _rel(path: Path) -> str:
    """Repository-relative POSIX path, for messages a reader can act on."""
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def load_policy(
    path: Path = POLICY_FILE, *, schema_path: Path = POLICY_SCHEMA_FILE
) -> CheckpointPolicy:
    """Read and schema-validate the committed policy.

    Structural validity is a precondition of the checks, never a substitute for them: a
    schema-valid policy whose artifact cannot be fetched still reports UNAVAILABLE.

    Raises:
        PolicyUnavailableError: The policy or its schema is absent, unparseable, not a
            valid draft-07 schema, or does not satisfy that schema.
    """
    if not path.is_file():
        raise PolicyUnavailableError(f"checkpoint-truth policy not found: {_rel(path)}")
    try:
        document: Any = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as error:
        raise PolicyUnavailableError(
            f"checkpoint-truth policy is not readable YAML: {_rel(path)}: {error}"
        ) from error
    if not isinstance(document, dict):
        raise PolicyUnavailableError(f"checkpoint-truth policy is not a mapping: {_rel(path)}")

    if not schema_path.is_file():
        raise PolicyUnavailableError(f"policy schema not found: {_rel(schema_path)}")
    try:
        schema: Any = json.loads(schema_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise PolicyUnavailableError(
            f"policy schema is not readable JSON: {_rel(schema_path)}: {error}"
        ) from error
    try:
        Draft7Validator.check_schema(schema)
    except SchemaError as error:
        raise PolicyUnavailableError(
            f"policy schema is not a valid draft-07 schema: {_rel(schema_path)}: {error.message}"
        ) from error

    violations = sorted(
        Draft7Validator(schema).iter_errors(document), key=lambda err: list(err.absolute_path)
    )
    if violations:
        first = violations[0]
        pointer = "/" + "/".join(str(part) for part in first.absolute_path)
        raise PolicyUnavailableError(
            f"{_rel(path)} violates {_rel(schema_path)} at {pointer}: {first.message} "
            f"({len(violations)} violation(s))"
        )

    try:
        return CheckpointPolicy.model_validate(document)
    except ValidationError as error:
        raise PolicyUnavailableError(
            f"{_rel(path)} does not parse into a policy: {error.error_count()} error(s)"
        ) from error


_POLICY_CACHE: CheckpointPolicy | None = None


def policy() -> CheckpointPolicy:
    """The committed policy, read once per process."""
    global _POLICY_CACHE  # noqa: PLW0603 - a single process-lifetime read of a committed file
    if _POLICY_CACHE is None:
        _POLICY_CACHE = load_policy()
    return _POLICY_CACHE


#: The serving-resolved model name, from the committed policy.
SERVING_NAME: Final[str] = policy().serving_name
#: INV-DP-002's held-out coverage floor. Derived from the committed policy (AD-13),
#: kept importable because C46 and its tests read it by this name.
COVERAGE_FLOOR: Final[float] = policy().floors.coverage_p90.value
#: The committed registry record the operator lands.
REGISTRY: Final[Path] = ROOT / policy().registry_file


# ---------------------------------------------------------------------------
# Outcome vocabulary
# ---------------------------------------------------------------------------


class Outcome(str, Enum):
    """Four-state outcome. Only ``PASS`` is a pass; a SKIP is not a PASS (I-7)."""

    PASS = "pass"
    FAIL = "fail"
    SKIP = "skip"
    UNAVAILABLE = "unavailable"


class ArtifactClass(str, Enum):
    """The three-way classification of R3.1, plus the honest fourth state.

    ``INDETERMINATE`` exists so that an artifact matching neither marker set is never
    *promoted* to ``REAL`` by default. Silence about provenance is not production
    provenance.
    """

    ABSENT = "absent"
    SMOKE = "smoke"
    REAL = "real"
    INDETERMINATE = "indeterminate"


class Clause(str, Enum):
    """The clause a finding belongs to, so a failure names its own rule."""

    POLICY = "policy"
    REGISTRY = "registry"
    FETCH = "fetch"
    CLASSIFICATION = "classification"
    COVERAGE = "coverage"
    SHA_PIN = "sha-pin"
    CRPS_RECOMPUTE = "crps-recompute"
    #: The R8.9/R8.10 recompute of held-out coverage, kept separate from ``COVERAGE``
    #: for the same reason ``CRPS_RECOMPUTE`` is separate: reading a recorded number
    #: and recomputing it are two different claims, and a report that folded them
    #: into one clause could not say which of the two failed.
    COVERAGE_RECOMPUTE = "coverage-recompute"


_EXIT_BY_OUTCOME: Final[dict[Outcome, int]] = {
    Outcome.PASS: 0,
    Outcome.FAIL: 1,
    Outcome.SKIP: 2,
    Outcome.UNAVAILABLE: 2,
}

_MARKER: Final[dict[Outcome, str]] = {
    Outcome.PASS: "[OK]",
    Outcome.FAIL: "[XX]",
    Outcome.SKIP: "[--]",
    Outcome.UNAVAILABLE: "[??]",
}


class PublishProbe(BaseModel):
    """The narrow legacy verdict C46 consumes: ``ok`` / ``fail`` / ``skip``."""

    model_config = ConfigDict(frozen=True)

    status: str
    detail: str


class RegistryStatus(BaseModel):
    """Result of validating the committed registry record (no network involved).

    ``status`` is one of:

      * ``populated`` -- a complete, well-formed entry for the serving name.
      * ``placeholder`` -- no operator has published yet (honest, not a failure).
      * ``missing`` -- the registry file is absent or unreadable.
      * ``invalid`` -- an entry exists but its shape/values are wrong (a real error).
    """

    model_config = ConfigDict(frozen=True)

    status: str
    problems: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        """Only ``populated`` counts as a landed, validated entry."""
        return self.status == "populated"


class Finding(BaseModel):
    """One clause violation, carrying the message that names its subjects."""

    model_config = ConfigDict(frozen=True)

    clause: Clause
    requirement: str
    outcome: Outcome
    detail: str


class CoverageComparison(BaseModel):
    """The R3.3 comparison, reporting **both** the measured value and the floor.

    One model, **two bases**, named by :attr:`basis` (R8.9, AD-19):

    * ``"read"`` -- :func:`compare_coverage` reads ``calibrator.last_coverage_p90`` at
      the committed ``sidecar_path``. Retained as a **cross-check**.
    * ``"recompute"`` -- :func:`recompute_coverage_p90` recomputes empirical coverage
      from the published held-out actuals against the published conformal-adjusted
      bounds. This is the **verdict**: a recorded number nobody recomputed is not
      evidence.

    :attr:`outcome` carries what ``holds`` cannot. ``holds`` is two-valued, so it
    collapses "measured, and below the floor" into the same answer as "never measured
    at all" -- the exact three-versus-four-state collapse that let an ``UNAVAILABLE``
    read as a pass on the CRPS side (R9.14). ``outcome`` keeps them apart:
    ``FAIL`` for measured-and-below, ``UNAVAILABLE`` for nothing-to-measure.
    """

    model_config = ConfigDict(frozen=True)

    measured: float | None
    floor: float
    direction: str
    invariant: str
    sidecar_path: str
    holds: bool
    detail: str
    #: ``"read"`` or ``"recompute"`` -- which surface produced :attr:`measured`.
    basis: str
    #: Four-valued, so an unmeasurable coverage is never a pass (I-7).
    outcome: Outcome
    #: Held-out rows the recompute consumed, summed across horizons (0 for a read).
    rows: int = 0
    #: The committed minimum :attr:`rows` was judged against (0 for a read).
    min_rows: int = 0
    #: The horizons recomputed over, in sorted order (empty for a read).
    horizons: tuple[str, ...] = ()
    #: Per-horizon coverage, positionally aligned with :attr:`horizons`.
    per_horizon_coverage: tuple[float, ...] = ()
    #: The recorded value read at :attr:`sidecar_path`, for the recompute's
    #: cross-check (``None`` for a read, whose :attr:`measured` *is* that value).
    cross_check: float | None = None
    #: ``|recomputed - recorded|``. Reported, and deliberately **not** gated: the
    #: committed policy declares no coverage allowance and its schema admits no new
    #: key, so a threshold here would be the ungated number AD-13 forbids.
    divergence: float | None = None


class CrpsRecompute(BaseModel):
    """The R3.9 recompute of ``final_crps`` from the published held-out predictions."""

    model_config = ConfigDict(frozen=True)

    recorded: float | None
    recomputed: float | None
    difference: float | None
    allowance: float | None
    samples: int
    horizons: tuple[str, ...]
    quantile_levels: tuple[float, ...]
    method: str
    outcome: Outcome
    detail: str


class CheckpointTruthReport(BaseModel):
    """Everything one execution of the hardened gate observed."""

    model_config = ConfigDict(frozen=True)

    policy_file: str
    serving_name: str
    registry_file: str
    registry_state: str
    registry_problems: tuple[str, ...]
    source_kind: str
    repo: str | None
    sidecar_filename: str | None
    classification: ArtifactClass
    classification_detail: str
    version: str | None
    recorded_sha: str | None
    coverage: CoverageComparison | None
    #: The R8.9 recompute. Separate from :attr:`coverage`, which stays the *read*, so
    #: a reader can see the recorded number and the recomputed one side by side
    #: instead of one having quietly replaced the other.
    coverage_recompute: CoverageComparison | None
    crps: CrpsRecompute | None
    refused_local_candidates: tuple[str, ...]
    outcome: Outcome
    findings: tuple[Finding, ...]
    detail: str

    @property
    def exit_code(self) -> int:
        """``0`` pass / ``1`` fail / ``2`` skip-or-unavailable; ``2`` is non-passing."""
        return _EXIT_BY_OUTCOME[self.outcome]

    def canonical_json(self) -> str:
        """Canonical serialisation for a persisted payload."""
        return json.dumps(
            self.model_dump(mode="json"), sort_keys=True, separators=(",", ":")
        )


# ---------------------------------------------------------------------------
# The committed registry record
# ---------------------------------------------------------------------------


def _load_registry() -> dict[str, Any]:
    """Read the committed registry file. The seam a test replaces to stay hermetic."""
    if not REGISTRY.is_file():
        return {}
    try:
        parsed: dict[str, Any] = json.loads(REGISTRY.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {}
    return parsed


def _validate_number(
    key: str, value: Any, *, minimum: float | None = None, maximum: float | None = None
) -> str | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return f"{key} must be a number, got {type(value).__name__}"
    if not math.isfinite(float(value)):
        return f"{key} must be finite, got {value!r}"
    if minimum is not None and float(value) < minimum:
        return f"{key}={value} is below the minimum {minimum}"
    if maximum is not None and float(value) > maximum:
        return f"{key}={value} is above the maximum {maximum}"
    return None


def validate_entry(entry: Any, *, coverage_floor: float | None = None) -> list[str]:
    """Return the problems with one registry entry; empty list means well-formed.

    Checks presence of every :data:`REQUIRED_ENTRY_KEYS` key and that the values are
    the kind of value the runbook actually produces: an ``owner/name`` HF repo, a hex
    checkpoint sha, a coverage at or above the committed floor, a finite non-negative
    CRPS, an ISO-dated ``trained_at``, and a positive training row count.
    """
    floor = COVERAGE_FLOOR if coverage_floor is None else coverage_floor
    if not isinstance(entry, dict):
        return [f"entry must be a JSON object, got {type(entry).__name__}"]

    problems: list[str] = [
        f"missing required key {k!r}" for k in REQUIRED_ENTRY_KEYS if k not in entry
    ]

    repo = entry.get("repo")
    if "repo" in entry and (
        not isinstance(repo, str) or repo.count("/") != 1 or not all(repo.split("/"))
    ):
        problems.append(f"repo must be an 'owner/name' HF repo id, got {repo!r}")

    sha = entry.get("sha")
    if "sha" in entry and (not isinstance(sha, str) or not _SHA_RE.match(sha.strip().lower())):
        problems.append(f"sha must be a hex string of >= {_MIN_SHA_LEN} chars, got {sha!r}")

    if "coverage_p90" in entry:
        problem = _validate_number("coverage_p90", entry["coverage_p90"], minimum=0.0, maximum=1.0)
        if problem:
            problems.append(problem)
        elif float(entry["coverage_p90"]) < floor:
            problems.append(
                f"coverage_p90={entry['coverage_p90']} < floor {floor} (uncalibrated)"
            )

    if "final_crps" in entry:
        problem = _validate_number("final_crps", entry["final_crps"], minimum=0.0)
        if problem:
            problems.append(problem)

    trained_at = entry.get("trained_at")
    if "trained_at" in entry and (
        not isinstance(trained_at, str) or not _DATE_RE.match(trained_at.strip())
    ):
        problems.append(f"trained_at must start with an ISO date (YYYY-MM-DD), got {trained_at!r}")

    rows = entry.get("rows")
    if "rows" in entry and (isinstance(rows, bool) or not isinstance(rows, int) or rows <= 0):
        problems.append(f"rows must be a positive integer, got {rows!r}")

    return problems


def registry_status(
    registry: dict[str, Any] | None = None,
    *,
    name: str = SERVING_NAME,
    coverage_floor: float | None = None,
) -> RegistryStatus:
    """Classify the committed registry record for ``name`` without touching the network."""
    if registry is None:
        if not REGISTRY.is_file():
            return RegistryStatus(status="missing", problems=(f"{REGISTRY.name} not found",))
        registry = _load_registry()
        if not registry:
            return RegistryStatus(
                status="missing", problems=(f"{REGISTRY.name} is empty or unparseable",)
            )
    if not registry:
        return RegistryStatus(status="missing", problems=("registry is empty",))
    if _PLACEHOLDER_KEY in registry:
        return RegistryStatus(
            status="placeholder",
            problems=(
                "no checkpoint published yet - run docs/runbooks/train-and-publish-checkpoint.md",
            ),
        )
    if name not in registry:
        return RegistryStatus(
            status="invalid", problems=(f"no entry for serving name {name!r}",)
        )
    problems = validate_entry(registry[name], coverage_floor=coverage_floor)
    if problems:
        return RegistryStatus(status="invalid", problems=tuple(problems))
    return RegistryStatus(status="populated")


def run_validate_registry(*, as_json: bool = False, check: bool = False) -> int:
    """Report the registry record's shape. Exit 1 (with ``--check``) only on ``invalid``."""
    status = registry_status()
    detail = "; ".join(status.problems) or f"entry for {SERVING_NAME} is complete and well-formed"
    if as_json:
        payload = {"status": status.status, "problems": list(status.problems)}
        print(json.dumps(payload, sort_keys=True))
    else:
        sym = {"populated": "[OK]", "placeholder": "[--]", "missing": "[--]", "invalid": "[XX]"}[
            status.status
        ]
        print(f"{sym} registry-schema  {status.status}: {detail}")
    if check:
        return 1 if status.status == "invalid" else 0
    return 0


# ---------------------------------------------------------------------------
# Clause helpers - one implementation of each rule, shared by both projections
# ---------------------------------------------------------------------------


def _finite(value: object) -> float | None:
    """Coerce a scalar to a finite float. Booleans are never numbers here."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    numeric = float(value)
    return numeric if math.isfinite(numeric) else None


def _read_dotted(payload: Mapping[str, Any], dotted: str) -> Any:
    """Walk a dotted read path inside a sidecar. Missing anywhere yields ``None``."""
    current: Any = payload
    for part in dotted.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def _matching_prefix(version: str, prefixes: Sequence[str]) -> str | None:
    """The first declared prefix ``version`` starts with, longest first."""
    for prefix in sorted(prefixes, key=len, reverse=True):
        if version.startswith(prefix):
            return prefix
    return None


def smoke_flagged(sidecar: Mapping[str, Any], markers: ClassificationPolicy) -> bool:
    """Whether the artifact *declares itself* a smoke run via the sidecar flag.

    ``agents/demand_prophet/training/train.py`` sets this flag directly, so it is the
    strongest single marker and the only one the narrower legacy probe consults.
    :func:`classify` additionally reads the version prefix, which catches an artifact
    built by a smoke run whose flag was dropped in transit.
    """
    return sidecar.get(markers.smoke.sidecar_flag) is True


def classify(
    sidecar: Mapping[str, Any] | None,
    markers: ClassificationPolicy,
    *,
    source_description: str = "the declared zero-cost source",
) -> tuple[ArtifactClass, str]:
    """Classify a fetched artifact as absent / smoke / real (R3.1, R3.4).

    Every branch's detail names the marker that decided it, so a reader can tell a
    smoke artifact from an absent one and from a real one without opening this file.
    A smoke artifact is never reported as a real one; an artifact carrying neither
    marker set is ``INDETERMINATE`` and is never promoted to real.
    """
    if sidecar is None:
        return (
            ArtifactClass.ABSENT,
            f"ABSENT: no artifact was fetched from {source_description}, so nothing was "
            "classified; this is the absence of evidence, not a smoke artifact and not a "
            "production one",
        )

    version = str(sidecar.get("version", ""))
    flag_name = markers.smoke.sidecar_flag
    flag = sidecar.get(flag_name)

    if smoke_flagged(sidecar, markers):
        return (
            ArtifactClass.SMOKE,
            f"SMOKE: the fetched sidecar sets {flag_name}=true (version={version!r}); this is "
            "the CI training-smoke artifact, not the published production model",
        )
    smoke_prefix = _matching_prefix(version, markers.smoke.version_prefixes)
    if smoke_prefix is not None:
        return (
            ArtifactClass.SMOKE,
            f"SMOKE: the fetched sidecar's version {version!r} carries the smoke prefix "
            f"{smoke_prefix!r} ({flag_name}={flag!r}); a smoke artifact is not a production "
            "model",
        )
    real_prefix = _matching_prefix(version, markers.real.version_prefixes)
    if real_prefix is not None:
        return (
            ArtifactClass.REAL,
            f"REAL: the fetched sidecar's version {version!r} carries the production prefix "
            f"{real_prefix!r} and {flag_name} is not true",
        )
    return (
        ArtifactClass.INDETERMINATE,
        f"INDETERMINATE: the fetched sidecar's version {version!r} carries none of the "
        f"declared smoke prefixes {list(markers.smoke.version_prefixes)} or production "
        f"prefixes {list(markers.real.version_prefixes)}, and {flag_name}={flag!r}; an "
        "unmarked artifact is not promoted to a production one",
    )


def compare_coverage(
    sidecar: Mapping[str, Any] | None, floor: CoverageFloorPolicy
) -> CoverageComparison:
    """READ the published held-out ``coverage_p90`` and compare it against the floor.

    R3.3 requires the report to carry **both** numbers, so the detail states the
    measured value (or ``null``) and the floor on every branch.

    This is the **cross-check**, not the verdict (R8.9, task 18.2). It reads
    ``calibrator.last_coverage_p90`` at the committed ``sidecar_path`` -- a number the
    training run recorded about itself. :func:`recompute_coverage_p90` recomputes the
    same quantity from the published raw material and is what decides. Both are kept:
    a recorded number nobody recomputed is not evidence, and a recompute with nothing
    to disagree with cannot catch a stale record.
    """
    raw = None if sidecar is None else _read_dotted(sidecar, floor.sidecar_path)
    measured = _finite(raw)
    if measured is None:
        return CoverageComparison(
            measured=None,
            floor=floor.value,
            direction=floor.direction,
            invariant=floor.invariant,
            sidecar_path=floor.sidecar_path,
            holds=False,
            basis="read",
            outcome=Outcome.FAIL,
            detail=(
                f"measured coverage_p90=null (sidecar path {floor.sidecar_path!r} carries "
                f"{raw!r}) against floor {floor.value} ({floor.invariant}, {floor.direction}); "
                "a published artifact that declares no held-out coverage is uncalibrated as "
                "published - never a pass"
            ),
        )
    holds = measured >= floor.value
    verdict = "holds" if holds else "is BELOW the floor (uncalibrated)"
    return CoverageComparison(
        measured=measured,
        floor=floor.value,
        direction=floor.direction,
        invariant=floor.invariant,
        sidecar_path=floor.sidecar_path,
        holds=holds,
        basis="read",
        outcome=Outcome.PASS if holds else Outcome.FAIL,
        detail=(
            f"measured coverage_p90={measured} against floor {floor.value} "
            f"({floor.invariant}, {floor.direction}) {verdict}"
        ),
    )


def sha_is_pinned(recorded_sha: str, version: str) -> bool:
    """Whether the recorded sha appears in the published version string.

    An empty recorded sha imposes no pin -- the record simply did not claim one. A
    landed entry always carries a sha (:func:`validate_entry` enforces it), so this
    leniency only applies to the narrower legacy probe, which does not validate.
    """
    return recorded_sha.strip() in version


def refused_local_candidates(
    source: SourcePolicy, name: str, *, root: Path = ROOT
) -> tuple[str, ...]:
    """The locally built artifacts the gate REFUSED to substitute (R3.7).

    ``ModelRegistry._resolve_checkpoint_path`` prefers a local checkpoint over the
    remote, so a gate that resolved through it would certify the CI smoke artifact as
    the published model. Naming what was refused - and whether it was even present -
    is what makes the refusal auditable rather than merely asserted.
    """
    directory = root / source.local_candidate_dir
    listed: list[str] = []
    for filename in (
        source.checkpoint_filename.format(name=name),
        source.sidecar_filename.format(name=name),
    ):
        candidate = directory / filename
        presence = "present" if candidate.is_file() else "absent"
        listed.append(f"{source.local_candidate_dir}/{filename} ({presence})")
    return tuple(listed)


def _pinball_mean(errors: Sequence[float], level: float) -> float:
    """Mean pinball loss at one quantile level.

    Mirrors ``agents/demand_prophet/training/rewards.py::crps_loss`` exactly:
    ``q * e`` when ``e >= 0`` else ``(q - 1) * e``, averaged over samples. Written in
    plain Python so the gate needs neither torch nor numpy (I-0, I-1).
    """
    total = 0.0
    for error in errors:
        total += level * error if error >= 0.0 else (level - 1.0) * error
    return total / len(errors)


def _horizon_blocks(
    block: Mapping[str, Any], *, marker: str = "predictions"
) -> dict[str, Any] | None:
    """Normalise the two accepted held-out shapes into ``{horizon: payload}``.

    ``marker`` is the key whose presence identifies the *flat* single-horizon form.
    The CRPS recompute recognises it by ``predictions``; the coverage recompute by
    ``actuals``, since a block could in principle publish bounds and actuals without
    the raw quantile columns. One normalisation rule, two projections of it.
    """
    horizons = block.get("horizons")
    if isinstance(horizons, dict):
        return {str(key): value for key, value in horizons.items()}
    if marker in block:
        return {"*": block}
    return None


def _parse_pairs(
    payload: Any, levels: Sequence[float]
) -> tuple[list[list[float]], list[float]] | str:
    """Parse one horizon's ``(predictions, actuals)`` or return why it cannot be used."""
    if not isinstance(payload, dict):
        return f"horizon payload must be an object, got {type(payload).__name__}"
    raw_predictions = payload.get("predictions")
    raw_actuals = payload.get("actuals")
    if not isinstance(raw_predictions, list) or not isinstance(raw_actuals, list):
        return "horizon payload must carry list 'predictions' and list 'actuals'"
    if len(raw_predictions) != len(raw_actuals):
        return (
            f"predictions ({len(raw_predictions)}) and actuals ({len(raw_actuals)}) "
            "have different lengths"
        )
    if not raw_actuals:
        return "horizon payload carries no held-out rows"

    predictions: list[list[float]] = []
    for row in raw_predictions:
        if not isinstance(row, list) or len(row) != len(levels):
            return (
                f"each prediction row must hold one value per quantile level "
                f"({len(levels)}), got {row!r}"
            )
        parsed_row: list[float] = []
        for value in row:
            numeric = _finite(value)
            if numeric is None:
                return f"prediction value {value!r} is not a finite number"
            parsed_row.append(numeric)
        predictions.append(parsed_row)

    actuals: list[float] = []
    for value in raw_actuals:
        numeric = _finite(value)
        if numeric is None:
            return f"actual value {value!r} is not a finite number"
        actuals.append(numeric)
    return predictions, actuals


def _declared_levels(
    block: Mapping[str, Any], tolerance: CrpsTolerancePolicy
) -> tuple[float, ...]:
    """The sidecar's own quantile levels when it declares usable ones, else the policy's."""
    declared = block.get("quantile_levels")
    if isinstance(declared, list) and len(declared) >= 2:
        parsed = [_finite(value) for value in declared]
        if all(value is not None and 0.0 < value < 1.0 for value in parsed):
            return tuple(value for value in parsed if value is not None)
    return tolerance.quantile_levels


def _unavailable_crps(
    tolerance: CrpsTolerancePolicy,
    *,
    recorded: float | None,
    detail: str,
    levels: tuple[float, ...] | None = None,
    samples: int = 0,
) -> CrpsRecompute:
    return CrpsRecompute(
        recorded=recorded,
        recomputed=None,
        difference=None,
        allowance=None if recorded is None else tolerance.allowance(recorded),
        samples=samples,
        horizons=(),
        quantile_levels=tolerance.quantile_levels if levels is None else levels,
        method=tolerance.method,
        outcome=Outcome.UNAVAILABLE,
        detail=detail,
    )


def recompute_final_crps(
    sidecar: Mapping[str, Any] | None,
    tolerance: CrpsTolerancePolicy,
    *,
    recorded: float | None,
) -> CrpsRecompute:
    """Recompute ``final_crps`` from the published held-out predictions (R3.9).

    The definition is the training loss's: mean pinball loss over the quantile levels,
    then the mean over horizons (``rewards.py::crps_loss`` inside
    ``train.py::_batch_loss``). The recomputed value is compared against the recorded
    one within ``max(absolute, relative * |recorded|)``.

    A recorded number nobody recomputed is not evidence, so every branch that cannot
    recompute returns ``UNAVAILABLE`` - never a pass - naming what is missing.
    """
    if sidecar is None:
        return _unavailable_crps(
            tolerance,
            recorded=recorded,
            detail=(
                "no artifact was fetched, so the recorded final_crps could not be recomputed; "
                "an unrecomputed number is not evidence"
            ),
        )
    if recorded is None:
        return _unavailable_crps(
            tolerance,
            recorded=None,
            detail=(
                f"the registry entry records no numeric {tolerance.registry_key!r}, so there is "
                "nothing to compare a recompute against"
            ),
        )

    block = sidecar.get(tolerance.sidecar_block)
    if not isinstance(block, dict):
        return _unavailable_crps(
            tolerance,
            recorded=recorded,
            detail=(
                f"the published sidecar carries no {tolerance.sidecar_block!r} block, so "
                f"{tolerance.registry_key}={recorded} cannot be recomputed; publishing the "
                "held-out predictions is a step of "
                "docs/runbooks/train-and-publish-checkpoint.md"
            ),
        )

    levels = _declared_levels(block, tolerance)
    grouped = _horizon_blocks(block)
    if grouped is None or not grouped:
        return _unavailable_crps(
            tolerance,
            recorded=recorded,
            levels=levels,
            detail=(
                f"the {tolerance.sidecar_block!r} block declares neither a 'horizons' mapping "
                "nor a flat 'predictions'/'actuals' pair, so nothing could be recomputed"
            ),
        )

    horizon_losses: dict[str, float] = {}
    samples = 0
    for horizon in sorted(grouped):
        parsed = _parse_pairs(grouped[horizon], levels)
        if isinstance(parsed, str):
            return _unavailable_crps(
                tolerance,
                recorded=recorded,
                levels=levels,
                samples=samples,
                detail=(
                    f"the {tolerance.sidecar_block!r} block is unusable at horizon "
                    f"{horizon!r}: {parsed}"
                ),
            )
        predictions, actuals = parsed
        samples += len(actuals)
        per_level = [
            _pinball_mean(
                [actual - row[index] for row, actual in zip(predictions, actuals, strict=True)],
                level,
            )
            for index, level in enumerate(levels)
        ]
        horizon_losses[horizon] = sum(per_level) / len(per_level)

    if samples < tolerance.min_samples:
        return _unavailable_crps(
            tolerance,
            recorded=recorded,
            levels=levels,
            samples=samples,
            detail=(
                f"the published held-out set holds {samples} row(s), below the declared "
                f"minimum of {tolerance.min_samples}; a recompute that noisy is not evidence"
            ),
        )

    recomputed = sum(horizon_losses.values()) / len(horizon_losses)
    difference = abs(recomputed - recorded)
    allowance = tolerance.allowance(recorded)
    within = difference <= allowance
    verdict = "within" if within else "OUTSIDE"
    return CrpsRecompute(
        recorded=recorded,
        recomputed=recomputed,
        difference=difference,
        allowance=allowance,
        samples=samples,
        horizons=tuple(sorted(horizon_losses)),
        quantile_levels=tuple(levels),
        method=tolerance.method,
        outcome=Outcome.PASS if within else Outcome.FAIL,
        detail=(
            f"recorded {tolerance.registry_key}={recorded}, recomputed {recomputed:.6f} from "
            f"{samples} held-out row(s) over horizon(s) {sorted(horizon_losses)} by "
            f"{tolerance.method}; |difference|={difference:.6f} is {verdict} the declared "
            f"allowance of {allowance:.6f} "
            f"(max({tolerance.absolute}, {tolerance.relative} * |recorded|))"
        ),
    )


# ---------------------------------------------------------------------------
# Recomputing held-out coverage (R8.9, R8.10, R9.8, R9.14 - task 18.2)
# ---------------------------------------------------------------------------


def _parse_bounds(payload: Any) -> tuple[list[float], list[float], list[float]] | str:
    """Parse one horizon's ``(actuals, lower_90, upper_90)`` or say why it cannot be used.

    The refusal to fall back to the ``predictions`` quantile columns is deliberate and
    is the whole point of reading these two keys: with levels ``[0.1, 0.5, 0.9]`` those
    columns span a nominal **80%** band, and scoring actuals against them would report
    a *different interval's* coverage against INV-DP-002's 90% floor. An absent bound
    is therefore unavailable, never a substituted number.
    """
    if not isinstance(payload, dict):
        return f"horizon payload must be an object, got {type(payload).__name__}"
    columns: dict[str, list[float]] = {}
    for key in ("actuals", HELDOUT_LOWER_KEY, HELDOUT_UPPER_KEY):
        raw = payload.get(key)
        if not isinstance(raw, list):
            return (
                f"horizon payload must carry a list {key!r}, got {type(raw).__name__}; the "
                f"conformal-adjusted {HELDOUT_LOWER_KEY!r}/{HELDOUT_UPPER_KEY!r} bounds are "
                "the interval INV-DP-002 is about, and the raw quantile columns are a "
                "narrower one, so they are never substituted for them"
            )
        parsed: list[float] = []
        for value in raw:
            numeric = _finite(value)
            if numeric is None:
                return f"{key} value {value!r} is not a finite number"
            parsed.append(numeric)
        columns[key] = parsed

    actuals = columns["actuals"]
    lower = columns[HELDOUT_LOWER_KEY]
    upper = columns[HELDOUT_UPPER_KEY]
    if not actuals:
        return "horizon payload carries no held-out rows"
    if not len(actuals) == len(lower) == len(upper):
        return (
            f"actuals ({len(actuals)}), {HELDOUT_LOWER_KEY} ({len(lower)}) and "
            f"{HELDOUT_UPPER_KEY} ({len(upper)}) have different lengths"
        )
    return actuals, lower, upper


def _unavailable_coverage(
    floor: CoverageFloorPolicy,
    *,
    detail: str,
    cross_check: float | None,
    min_rows: int,
    rows: int = 0,
) -> CoverageComparison:
    """Nothing was recomputed, so nothing is reported as measured (I-7)."""
    return CoverageComparison(
        measured=None,
        floor=floor.value,
        direction=floor.direction,
        invariant=floor.invariant,
        sidecar_path=floor.sidecar_path,
        holds=False,
        basis="recompute",
        outcome=Outcome.UNAVAILABLE,
        rows=rows,
        min_rows=min_rows,
        cross_check=cross_check,
        detail=detail,
    )


def recompute_coverage_p90(
    sidecar: Mapping[str, Any] | None,
    floor: CoverageFloorPolicy,
    *,
    block: str,
    min_rows: int,
) -> CoverageComparison:
    """RECOMPUTE held-out ``coverage_p90`` from the published block (R8.9, R8.10).

    The fraction of published held-out actuals falling inside the published
    **conformal-adjusted** ``lower_90``/``upper_90`` bounds, per horizon, then the mean
    over horizons. That aggregation is not a choice made here: it mirrors
    ``ConformalCalibrator.fit``, which sets ``last_coverage_p90`` to the mean of its
    per-horizon coverages. The two therefore measure the same quantity, which is what
    makes the cross-check below meaningful rather than a comparison of two definitions.

    Args:
        sidecar: The fetched serving sidecar, or ``None`` when nothing was fetched.
        floor: The committed ``coverage_p90`` floor (value, direction, invariant, and
            the dotted path the cross-check is read from).
        block: The sidecar key holding the held-out block. Read by the caller from
            ``checkpoint-truth.yaml::tolerances.final_crps.sidecar_block``.
        min_rows: The committed minimum published row count, summed across horizons.
            Read by the caller from ``tolerances.final_crps.min_samples``. Both facts
            live under the CRPS tolerance because that file's committed schema is
            ``additionalProperties: false`` at every level and so admits no coverage-
            side sibling; they are passed explicitly rather than re-read here so this
            function states exactly what it consumes.

    Returns:
        A comparison whose :attr:`~CoverageComparison.outcome` is ``PASS`` only when the
        coverage was actually recomputed from at least ``min_rows`` rows **and** lands
        at or above the floor; ``FAIL`` when it was recomputed and is below the floor,
        reporting the measured value and the floor (R8.10); and ``UNAVAILABLE`` when
        the block is absent, malformed, shorter than ``min_rows``, or omits the
        adjusted bounds -- a number nobody could recompute is not evidence, and
        UNAVAILABLE is never a pass (I-7).
    """
    cross_check = None if sidecar is None else _finite(_read_dotted(sidecar, floor.sidecar_path))
    if sidecar is None:
        return _unavailable_coverage(
            floor,
            cross_check=None,
            min_rows=min_rows,
            detail=(
                f"no artifact was fetched, so coverage_p90 could not be recomputed against "
                f"floor {floor.value} ({floor.invariant}); an unrecomputed number is not "
                "evidence"
            ),
        )

    payload = sidecar.get(block)
    if not isinstance(payload, dict):
        return _unavailable_coverage(
            floor,
            cross_check=cross_check,
            min_rows=min_rows,
            detail=(
                f"the published sidecar carries no {block!r} block, so coverage_p90 could not "
                f"be recomputed against floor {floor.value} ({floor.invariant}); the recorded "
                f"read at {floor.sidecar_path!r} is {cross_check!r} and stands uncorroborated. "
                "Publishing the held-out block is a step of "
                "docs/runbooks/train-and-publish-checkpoint.md"
            ),
        )

    grouped = _horizon_blocks(payload, marker="actuals")
    if not grouped:
        return _unavailable_coverage(
            floor,
            cross_check=cross_check,
            min_rows=min_rows,
            detail=(
                f"the {block!r} block declares neither a 'horizons' mapping nor a flat "
                "'actuals' list, so no coverage could be recomputed against floor "
                f"{floor.value} ({floor.invariant})"
            ),
        )

    per_horizon: dict[str, float] = {}
    rows = 0
    for horizon in sorted(grouped):
        parsed = _parse_bounds(grouped[horizon])
        if isinstance(parsed, str):
            return _unavailable_coverage(
                floor,
                cross_check=cross_check,
                min_rows=min_rows,
                rows=rows,
                detail=(
                    f"the {block!r} block is unusable at horizon {horizon!r}: {parsed}; "
                    f"coverage_p90 was not recomputed against floor {floor.value} "
                    f"({floor.invariant})"
                ),
            )
        actuals, lower, upper = parsed
        covered = sum(
            1
            for actual, low, high in zip(actuals, lower, upper, strict=True)
            if low <= actual <= high
        )
        per_horizon[horizon] = covered / len(actuals)
        rows += len(actuals)

    if rows < min_rows:
        return _unavailable_coverage(
            floor,
            cross_check=cross_check,
            min_rows=min_rows,
            rows=rows,
            detail=(
                f"the published held-out set holds {rows} row(s), below the committed minimum "
                f"of {min_rows}; a coverage estimate that noisy is not evidence against floor "
                f"{floor.value} ({floor.invariant})"
            ),
        )

    horizons = tuple(sorted(per_horizon))
    recomputed = sum(per_horizon.values()) / len(per_horizon)
    holds = recomputed >= floor.value
    divergence = None if cross_check is None else abs(recomputed - cross_check)
    verdict = "holds" if holds else "is BELOW the floor (uncalibrated as published)"
    if cross_check is None:
        agreement = (
            f"the recorded read at {floor.sidecar_path!r} is null, so the recompute stands "
            "alone"
        )
    else:
        agreement = (
            f"the recorded read at {floor.sidecar_path!r} is {cross_check}, a divergence of "
            f"{divergence:.6f} from the recompute (reported, not gated: the committed policy "
            "declares no coverage allowance)"
        )
    return CoverageComparison(
        measured=recomputed,
        floor=floor.value,
        direction=floor.direction,
        invariant=floor.invariant,
        sidecar_path=floor.sidecar_path,
        holds=holds,
        basis="recompute",
        outcome=Outcome.PASS if holds else Outcome.FAIL,
        rows=rows,
        min_rows=min_rows,
        horizons=horizons,
        per_horizon_coverage=tuple(per_horizon[horizon] for horizon in horizons),
        cross_check=cross_check,
        divergence=divergence,
        detail=(
            f"recomputed coverage_p90={recomputed:.6f} from {rows} published held-out row(s) "
            f"over horizon(s) {list(horizons)}, scoring actuals against the conformal-adjusted "
            f"{HELDOUT_LOWER_KEY}/{HELDOUT_UPPER_KEY} bounds, against floor {floor.value} "
            f"({floor.invariant}, {floor.direction}) {verdict}; {agreement}"
        ),
    )


# ---------------------------------------------------------------------------
# Fetching the published sidecar from the declared zero-cost source
# ---------------------------------------------------------------------------


class _FetchError(Exception):
    """The recorded artifact could not be fetched. Never a pass."""


def fetch_from_hub(repo_id: str, filename: str) -> str:
    """Download one small JSON sidecar from the declared $0 source; return its path.

    ``huggingface_hub`` is imported lazily so the gate imports (and its property test
    runs) without it, and so an injected fake in ``sys.modules`` is honoured.
    """
    try:
        from huggingface_hub import hf_hub_download  # noqa: PLC0415
    except ImportError as error:
        raise _FetchError(f"huggingface_hub absent - cannot read the remote: {error}") from error
    try:
        path: str = hf_hub_download(repo_id=repo_id, filename=filename)
    except Exception as error:  # noqa: BLE001 - any remote failure is honest unavailability
        raise _FetchError(str(error)) from error
    return path


def _read_sidecar(fetcher: SidecarFetcher, repo_id: str, filename: str) -> dict[str, Any]:
    """Fetch and parse the published sidecar.

    **The fetch is wrapped, and this is a repair rather than defensiveness.**
    :func:`fetch_from_hub` already converts every remote failure into
    :class:`_FetchError` -- its own comment says "any remote failure is honest
    unavailability" -- but that conversion lived in the DEFAULT fetcher only, so an
    injected fetcher, or a future `huggingface_hub` that raised below that wrapper,
    escaped it and the exception propagated out of :func:`assess`. A gate that RAISES
    is not a gate that REPORTS: C46 would have surfaced a traceback where a verdict
    belongs, which is the C44 defect (a `FileNotFoundError` standing in for a check's
    finding) in a new place. I-7 requires unavailability to be a reported state.
    Found by ``tests/verify/test_smoke_artifact_distinction_property.py``'s
    unfetchable-sha clause, which is the point of asserting the refusal path by
    construction rather than waiting for a generated example to reach it.
    """
    try:
        path = fetcher(repo_id, filename)
    except _FetchError:
        raise
    except Exception as error:  # noqa: BLE001 - any remote failure is honest unavailability
        raise _FetchError(f"cannot fetch {filename} from {repo_id}: {error}") from error
    try:
        parsed: Any = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise _FetchError(f"fetched {filename} is not readable JSON: {error}") from error
    if not isinstance(parsed, dict):
        raise _FetchError(f"fetched {filename} is not a JSON object")
    return parsed


# ---------------------------------------------------------------------------
# The hardened gate (R3.1, R3.3, R3.4, R3.7, R3.9)
# ---------------------------------------------------------------------------


def _aggregate(findings: Sequence[Finding]) -> Outcome:
    """FAIL > UNAVAILABLE > SKIP > PASS. A skip is never a pass (I-7)."""
    for outcome in (Outcome.FAIL, Outcome.UNAVAILABLE, Outcome.SKIP):
        if any(finding.outcome is outcome for finding in findings):
            return outcome
    return Outcome.PASS


def assess(
    *,
    name: str | None = None,
    checkpoint_policy: CheckpointPolicy | None = None,
    registry: dict[str, Any] | None = None,
    fetch_sidecar: SidecarFetcher | None = None,
    root: Path = ROOT,
    env: Mapping[str, str] | None = None,
) -> CheckpointTruthReport:
    """Evaluate every clause against the committed record and the published artifact.

    Args:
        name: Serving name to judge (default: the policy's ``serving_name``).
        checkpoint_policy: Injected policy (default: the committed one).
        registry: Injected registry payload (default: read from the committed file).
        fetch_sidecar: Injected ``(repo_id, filename) -> path`` fetcher (default:
            :func:`fetch_from_hub`). Injecting it keeps a property test off the network.
        root: Tree root, so the refused-local-candidate paths can be pointed elsewhere.
        env: Environment mapping (default: ``os.environ``).

    Returns:
        A report whose outcome is ``PASS`` only when a landed record resolves to a real,
        calibrated, sha-pinned artifact whose recorded ``final_crps`` survives its own
        recompute **and** whose held-out ``coverage_p90`` was recomputed from the
        published conformal-adjusted bounds and lands at or above the committed floor.
        Every other state is ``FAIL``, ``SKIP``, or ``UNAVAILABLE``.
    """
    try:
        active = policy() if checkpoint_policy is None else checkpoint_policy
    except PolicyUnavailableError as error:
        return CheckpointTruthReport(
            policy_file=_rel(POLICY_FILE),
            serving_name=name or "(unknown)",
            registry_file="(unknown)",
            registry_problems=(),
            registry_state="unknown",
            source_kind="(unknown)",
            repo=None,
            sidecar_filename=None,
            classification=ArtifactClass.ABSENT,
            classification_detail=(
                "ABSENT: the committed checkpoint-truth policy could not be read, so no "
                "artifact was classified"
            ),
            version=None,
            recorded_sha=None,
            coverage=None,
            coverage_recompute=None,
            crps=None,
            refused_local_candidates=(),
            outcome=Outcome.UNAVAILABLE,
            findings=(
                Finding(
                    clause=Clause.POLICY,
                    requirement="AD-13",
                    outcome=Outcome.UNAVAILABLE,
                    detail=str(error),
                ),
            ),
            detail=str(error),
        )

    serving_name = active.serving_name if name is None else name
    fetcher: SidecarFetcher = fetch_from_hub if fetch_sidecar is None else fetch_sidecar
    environment = os.environ if env is None else env
    sidecar_filename = active.source.sidecar_filename.format(name=serving_name)
    refused = refused_local_candidates(active.source, serving_name, root=root)
    findings: list[Finding] = []

    # -- clause `policy`: the two pins that keep the refusal un-configurable ---------
    if not active.source.zero_cost:
        findings.append(
            Finding(
                clause=Clause.POLICY,
                requirement="I-1",
                outcome=Outcome.FAIL,
                detail=(
                    f"{_rel(POLICY_FILE)}::source.zero_cost is false; a source that is not "
                    "zero-cost is refused outright rather than consulted"
                ),
            )
        )
    if active.source.allow_local_substitution:
        findings.append(
            Finding(
                clause=Clause.POLICY,
                requirement="R3.7",
                outcome=Outcome.FAIL,
                detail=(
                    f"{_rel(POLICY_FILE)}::source.allow_local_substitution is true; "
                    "substituting a locally built checkpoint for a published one is the exact "
                    "evidence swap R3.7 forbids, so the flag is pinned false and cannot be "
                    "configured away"
                ),
            )
        )

    # -- clause `registry`: is there a landed, validated entry at all? ---------------
    status = registry_status(
        registry, name=serving_name, coverage_floor=active.floors.coverage_p90.value
    )
    if status.status != "populated":
        outcome = {
            "placeholder": Outcome.SKIP,
            "missing": Outcome.UNAVAILABLE,
            "invalid": Outcome.FAIL,
        }[status.status]
        reason = "; ".join(status.problems) or status.status
        findings.append(
            Finding(
                clause=Clause.REGISTRY,
                requirement="R3.1",
                outcome=outcome,
                detail=(
                    f"{active.registry_file} holds no validated non-placeholder entry for "
                    f"{serving_name!r} ({status.status}): {reason}"
                ),
            )
        )
        classification, classification_detail = classify(
            None,
            active.classification,
            source_description=(
                f"the declared {active.source.kind} source (no repo resolved from an unlanded "
                "record)"
            ),
        )
        aggregate = _aggregate(findings)
        # A flipped policy pin outranks an unlanded record, so the headline detail is
        # always the finding that produced the aggregate - never the last one appended.
        return CheckpointTruthReport(
            policy_file=_rel(POLICY_FILE),
            serving_name=serving_name,
            registry_file=active.registry_file,
            registry_state=status.status,
            registry_problems=status.problems,
            source_kind=active.source.kind,
            repo=None,
            sidecar_filename=sidecar_filename,
            classification=classification,
            classification_detail=classification_detail,
            version=None,
            recorded_sha=None,
            coverage=None,
            coverage_recompute=None,
            crps=None,
            refused_local_candidates=refused,
            outcome=aggregate,
            findings=tuple(findings),
            detail=next(
                finding.detail for finding in findings if finding.outcome is aggregate
            ),
        )

    landed = registry if registry is not None else _load_registry()
    raw_entry = landed.get(serving_name)
    entry: dict[str, Any] = dict(raw_entry) if isinstance(raw_entry, dict) else {}
    recorded_sha = str(entry.get("sha", "")).strip()
    recorded_crps = _finite(entry.get(active.tolerances.final_crps.registry_key))
    # The record's own repo is authoritative: a landed record must not go unverified
    # because an environment variable was left unset. The env var is an override only.
    repo = str(entry.get("repo", "")).strip() or environment.get(active.source.env_var, "").strip()
    if not repo:
        findings.append(
            Finding(
                clause=Clause.FETCH,
                requirement="R3.7",
                outcome=Outcome.UNAVAILABLE,
                detail=(
                    f"the landed entry names no repo and {active.source.env_var} is unset, so "
                    f"sha {recorded_sha!r} cannot be fetched from the declared "
                    f"{active.source.kind} source; REFUSED to resolve a local candidate in its "
                    f"place ({', '.join(refused)})"
                ),
            )
        )
        repo = ""

    sidecar: dict[str, Any] | None = None
    if repo:
        try:
            sidecar = _read_sidecar(fetcher, repo, sidecar_filename)
        except _FetchError as error:
            findings.append(
                Finding(
                    clause=Clause.FETCH,
                    requirement="R3.7",
                    outcome=Outcome.UNAVAILABLE,
                    detail=(
                        f"recorded sha {recorded_sha!r} could not be fetched from the declared "
                        f"{active.source.kind} source {repo}/{sidecar_filename}: {error}. "
                        f"REFUSED to substitute a locally built checkpoint in its place "
                        f"({', '.join(refused)}); "
                        f"{_rel(POLICY_FILE)}::source.allow_local_substitution is false, so an "
                        "unfetchable record is UNAVAILABLE, never a pass"
                    ),
                )
            )

    # -- clause `classification`: absent / smoke / real, told apart -------------------
    classification, classification_detail = classify(
        sidecar,
        active.classification,
        source_description=f"{repo or '(no repo)'}/{sidecar_filename}",
    )
    if classification is ArtifactClass.SMOKE:
        findings.append(
            Finding(
                clause=Clause.CLASSIFICATION,
                requirement="R3.4",
                outcome=Outcome.FAIL,
                detail=classification_detail,
            )
        )
    elif classification is ArtifactClass.INDETERMINATE:
        findings.append(
            Finding(
                clause=Clause.CLASSIFICATION,
                requirement="R3.1",
                outcome=Outcome.UNAVAILABLE,
                detail=classification_detail,
            )
        )

    coverage: CoverageComparison | None = None
    coverage_recompute: CoverageComparison | None = None
    crps: CrpsRecompute | None = None
    version: str | None = None

    if sidecar is not None:
        version = str(sidecar.get("version", ""))

        # -- clause `coverage`: report BOTH the measured value and the floor ----------
        coverage = compare_coverage(sidecar, active.floors.coverage_p90)
        if not coverage.holds:
            findings.append(
                Finding(
                    clause=Clause.COVERAGE,
                    requirement="R3.3",
                    outcome=Outcome.FAIL,
                    detail=coverage.detail,
                )
            )

        # -- clause `coverage-recompute`: the read above is the cross-check, this is the
        # verdict. A recorded coverage nobody recomputed is not evidence (R8.9, R8.10),
        # and a block that cannot be recomputed is UNAVAILABLE rather than a pass so the
        # coverage side cannot repeat the CRPS side's fall-through (R9.14).
        coverage_recompute = recompute_coverage_p90(
            sidecar,
            active.floors.coverage_p90,
            block=active.tolerances.final_crps.sidecar_block,
            min_rows=active.tolerances.final_crps.min_samples,
        )
        if coverage_recompute.outcome is not Outcome.PASS:
            findings.append(
                Finding(
                    clause=Clause.COVERAGE_RECOMPUTE,
                    requirement="R8.9",
                    outcome=coverage_recompute.outcome,
                    detail=coverage_recompute.detail,
                )
            )

        # -- clause `sha-pin`: the record and the remote must name the same artifact --
        if not sha_is_pinned(recorded_sha, version):
            findings.append(
                Finding(
                    clause=Clause.SHA_PIN,
                    requirement="R3.7",
                    outcome=Outcome.FAIL,
                    detail=(
                        f"recorded sha {recorded_sha!r} does not appear in the published "
                        f"version {version!r} (drift between the committed record and the "
                        f"artifact actually published at {repo})"
                    ),
                )
            )

        # -- clause `crps-recompute`: a recorded number nobody recomputed is not evidence
        crps = recompute_final_crps(
            sidecar, active.tolerances.final_crps, recorded=recorded_crps
        )
        if crps.outcome is not Outcome.PASS:
            findings.append(
                Finding(
                    clause=Clause.CRPS_RECOMPUTE,
                    requirement="R3.9",
                    outcome=crps.outcome,
                    detail=crps.detail,
                )
            )

    aggregate = _aggregate(findings)
    if aggregate is Outcome.PASS:
        measured = "unknown" if coverage is None else coverage.measured
        recomputed = "unknown" if coverage_recompute is None else coverage_recompute.measured
        detail = (
            f"published {serving_name} @ {repo}: {classification.value} artifact "
            f"version={version}, coverage_p90 recomputed as {recomputed} (recorded "
            f"{measured}) at-or-above floor {active.floors.coverage_p90.value}, recorded sha "
            f"{recorded_sha!r} pinned, final_crps recomputed within tolerance"
        )
    else:
        detail = next(
            finding.detail for finding in findings if finding.outcome is aggregate
        )

    return CheckpointTruthReport(
        policy_file=_rel(POLICY_FILE),
        serving_name=serving_name,
        registry_file=active.registry_file,
        registry_state=status.status,
        registry_problems=status.problems,
        source_kind=active.source.kind,
        repo=repo or None,
        sidecar_filename=sidecar_filename,
        classification=classification,
        classification_detail=classification_detail,
        version=version,
        recorded_sha=recorded_sha or None,
        coverage=coverage,
        coverage_recompute=coverage_recompute,
        crps=crps,
        refused_local_candidates=refused,
        outcome=aggregate,
        findings=tuple(findings),
        detail=detail,
    )


# ---------------------------------------------------------------------------
# The narrower legacy probe C46 consumed until task 18.3 re-pointed it at `assess`
# ---------------------------------------------------------------------------


def evaluate(*, name: str = SERVING_NAME) -> PublishProbe:
    """Verify the published checkpoint on the R5.3-R5.6 triad; SKIP when unverifiable.

    **This is no longer the registered surface.** C46
    (``verify_claims.py::check_published_checkpoint``) called it until
    decision-quality-proof task 18.3 re-pointed the check at :func:`assess` (AD-19,
    R9.14). It is retained because static reading did not enumerate its callers, and it
    is pinned as a legacy projection rather than as a gate.

    With the registry populated and the remote reachable: ``ok`` iff the sidecar is
    non-smoke **and** its held-out coverage is at or above the committed floor **and**
    the recorded sha appears in the published version. It shares every clause helper
    with :func:`assess`, which is strictly stricter -- it also refuses an
    ``indeterminate`` artifact, folds a smoke version *prefix* into the smoke rule,
    carries the two policy pins, and demands both recomputes.

    **The defect this surface cannot express, stated so nobody re-points a gate at it.**
    It acts on ``Outcome.FAIL`` alone below, so an ``UNAVAILABLE`` recompute -- the
    outcome for a sidecar with no held-out block, and for an entry recording no
    ``final_crps`` at all, since this function never calls :func:`validate_entry` --
    falls through to ``ok``. A three-valued vocabulary cannot distinguish "nothing was
    recomputed" from "the subject is absent", and absence of proof is never a pass
    (I-7). Fixing it here would change a long-pinned legacy verdict; the repair was to
    move the gate, not to widen the triad.
    """
    try:
        active = policy()
    except PolicyUnavailableError as error:
        return PublishProbe(status="skip", detail=f"committed policy unreadable: {error}")

    repo = os.environ.get(active.source.env_var) or None
    if repo is None:
        return PublishProbe(
            status="skip",
            detail=(
                f"{active.source.env_var} unset - no published model claimed (operator step)"
            ),
        )

    registry = _load_registry()
    if not registry or _PLACEHOLDER_KEY in registry:
        return PublishProbe(
            status="skip",
            detail=(
                f"{REGISTRY.name} is a placeholder - run the publish runbook + record it"
            ),
        )

    entry_raw = registry.get(name) or registry.get(repo) or {}
    entry: dict[str, Any] = entry_raw if isinstance(entry_raw, dict) else {}
    sidecar_filename = active.source.sidecar_filename.format(name=name)
    try:
        sidecar = _read_sidecar(fetch_from_hub, repo, sidecar_filename)
    except _FetchError as error:
        return PublishProbe(
            status="skip",
            detail=f"could not fetch {sidecar_filename} from {repo}: {error}",
        )

    # The legacy triad's smoke rule is the sidecar flag alone. `assess` also treats a
    # smoke *version prefix* as smoke; folding that in here would change this probe's
    # long-pinned verdict for an artifact whose flag is false, so it stays in `assess`.
    if smoke_flagged(sidecar, active.classification):
        return PublishProbe(
            status="fail",
            detail=f"published {name} is a SMOKE artifact, not a production model",
        )

    coverage = compare_coverage(sidecar, active.floors.coverage_p90)
    if not coverage.holds:
        raw = _read_dotted(sidecar, active.floors.coverage_p90.sidecar_path)
        return PublishProbe(
            status="fail",
            detail=(
                f"published coverage_p90={raw} < floor {active.floors.coverage_p90.value} "
                "(uncalibrated)"
            ),
        )

    published_version = str(sidecar.get("version", ""))  # e.g. "full_<sha>"
    recorded_sha = str(entry.get("sha", "")).strip()
    if not sha_is_pinned(recorded_sha, published_version):
        return PublishProbe(
            status="fail",
            detail=(
                f"registry sha {recorded_sha!r} not in published version "
                f"{published_version!r} (drift)"
            ),
        )

    crps = recompute_final_crps(
        sidecar,
        active.tolerances.final_crps,
        recorded=_finite(entry.get(active.tolerances.final_crps.registry_key)),
    )
    if crps.outcome is Outcome.FAIL:
        return PublishProbe(status="fail", detail=crps.detail)

    return PublishProbe(
        status="ok",
        detail=(
            f"published {name} @ {repo}: version={published_version}, "
            f"coverage_p90={coverage.measured}"
        ),
    )


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


def format_report(report: CheckpointTruthReport) -> list[str]:
    """ASCII-only human summary; every clause names its own subjects."""
    lines = [
        "Published checkpoint (E5.2 - R3.1/R3.3/R3.4/R3.7/R3.9)",
        f"  policy         : {report.policy_file}",
        f"  serving name   : {report.serving_name}",
        f"  registry       : {report.registry_file} ({report.registry_state})",
        f"  source         : {report.source_kind} {report.repo or '(no repo resolved)'}",
        f"  classification : {report.classification.value}",
        f"  detail         : {report.classification_detail}",
    ]
    if report.coverage is not None:
        lines.append(f"  coverage read  : {report.coverage.detail}")
    if report.coverage_recompute is not None:
        lines.append(
            f"  coverage recomp: [{report.coverage_recompute.outcome.value}] "
            f"{report.coverage_recompute.detail}"
        )
    if report.crps is not None:
        lines.append(f"  final_crps     : [{report.crps.outcome.value}] {report.crps.detail}")
    if report.refused_local_candidates:
        lines.append(
            f"  refused local  : {', '.join(report.refused_local_candidates)} "
            "(never substituted for a published artifact)"
        )
    lines.append(f"  status         : {report.outcome.value}  (exit {report.exit_code})")
    lines.append(f"  reason         : {report.detail}")
    for finding in report.findings:
        lines.append(
            f"  {_MARKER[finding.outcome]} {finding.clause.value} [{finding.requirement}]: "
            f"{finding.detail}"
        )
    if report.outcome is Outcome.SKIP:
        lines.append(
            "[--] published-checkpoint: SKIP - no checkpoint has been published yet. "
            "A SKIP is not a PASS (I-7)."
        )
    elif report.outcome is Outcome.UNAVAILABLE:
        lines.append(
            "[??] published-checkpoint: UNAVAILABLE - the evidence could not be read or "
            "recomputed. Absence of proof is not a pass (I-7)."
        )
    return lines


def run(*, as_json: bool = False, check: bool = False, out: Path | None = None) -> int:
    """CLI entry point. ``print`` is acceptable here and nowhere else in this module."""
    report = assess()
    if as_json:
        print(report.canonical_json())
    else:
        for line in format_report(report):
            print(line)
    if out is not None:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(report.canonical_json(), encoding="utf-8")
    if report.outcome is not Outcome.PASS:
        logger.info(
            "published_checkpoint_non_passing",
            outcome=report.outcome.value,
            classification=report.classification.value,
            registry_state=report.registry_state,
        )
    return report.exit_code if check else _EXIT_BY_OUTCOME[Outcome.PASS]


def main(argv: list[str] | None = None) -> int:
    """``python -m scripts.audit.published_checkpoint_truth [--json] [--check] ...``."""
    parser = argparse.ArgumentParser(
        prog="python -m scripts.audit.published_checkpoint_truth",
        description=(
            "Report whether a real, non-smoke, calibrated checkpoint is published at $0 and "
            "matches the committed record. An unfetchable record is UNAVAILABLE, never a pass."
        ),
    )
    parser.add_argument("--json", action="store_true", help="Emit the canonical JSON report.")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit 0 pass / 1 fail / 2 skip-or-unavailable (2 is non-passing).",
    )
    parser.add_argument("--out", type=Path, default=None, help="Persist the canonical report.")
    parser.add_argument(
        "--validate-registry",
        action="store_true",
        help="Network-free: validate the committed registry record's shape only.",
    )
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])
    if args.validate_registry:
        return run_validate_registry(as_json=bool(args.json), check=bool(args.check))
    return run(as_json=bool(args.json), check=bool(args.check), out=args.out)


if __name__ == "__main__":
    sys.exit(main())
