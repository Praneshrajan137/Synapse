"""The Power_Report: the effect the harness can detect at the replicate count it ran (R6.5-R6.9).

Feature: decision-quality-proof, design section **E3.3**, task 17.1 (R6.5, R6.6, R6.8). R6.7's
predicate is :func:`describes_revision`, which task 17.3 calls; R6.9 and R6.16 are applied by
:func:`uplift.uplift_floor.powered_replicate_floor`. Property 86
(``tests/uplift/test_power_report_property.py``) is the contract.

**What it states.** A paired, two-sided, normal-approximation power statement about ONE
contrast -- a policy against the primary cell's re-derived tuned control E -- from the observed
variance of its per-replicate paired difference, in the margin's units squared::

    z_alpha  = Phi^-1(1 - alpha / 2)          z_beta = Phi^-1(detection_probability)
    mde(n)   = (z_alpha + z_beta) * sqrt(variance) / sqrt(n)
    required = ceil(((z_alpha + z_beta) * sqrt(variance) / margin) ** 2)

``mde(replicates_per_arm)`` is the smallest effect the measuring run detects at the declared
detection probability (R6.5); ``mde(MIN_POWERED_REPLICATES)`` is the detectable effect at the
committed floor (R6.8); ``required`` is the count at which the materiality margin itself becomes
the minimum detectable effect. A ``required`` below the INV-TW-002 floor is recorded as
``inv_tw_002_binding`` and proposes no lower constant (R6.16).

**Re-derived, never trusted.** :class:`PowerReport` recomputes every derived field from its
inputs and refuses a stored value the formula does not produce -- the pattern
``digital_twin.simulation.policy.materiality_margin`` applies to the committed margin. Floats are
compared at a relative :data:`REDERIVATION_REL_TOL`, not bit for bit, because the inverse normal
CDF evaluates libm ``log``, which no standard requires to round identically on every platform,
and a report generated on the Linux runner must read back anywhere. Integers and the binding
flag are compared exactly, so a requirement whose real value lies within rounding of an integer
could re-derive differently elsewhere; that refuses the report, which is the safe direction.

**Distinct in kind (R6.6).** ``kind`` is ``"power-report"`` and extra keys are forbidden, so a
result-artifact payload is refused here; a Power_Report carries no ``headline_uplift``, so
``PoweredProof.from_payload`` recovers no proof from one. It is committed at
:data:`POWER_REPORT_PATH`, outside the git-ignored ``artifacts/`` tree, and C60 consults
``artifact_is_version_controlled`` only for ``uplift_truth.RESULT_ARTIFACT``.

**Revision-bound by content, not by commit (R6.7).** ``harness_revision`` is
:func:`source_set_digest` over a declared source set. A git sha cannot name the commit that adds
the report, because adding it moves the sha. A content digest is unchanged by that commit and by
any commit touching nothing the measurement reads, and changed by any commit that does.

**Against arm E and nothing else (ADR-055 D2.7).** ``comparator`` must equal
:data:`uplift.tuned_static.TUNED_STATIC_ARM`; ``Par_Level_Reorder`` and every other name are
refused, which makes tasks.md 17.2's binding note mechanical rather than a convention.

**Inputs are passed, never defaulted.** Production reads ``alpha`` from
:func:`uplift.interval.contract_alpha`, ``detection_probability`` from
``digital_twin.simulation.policy.detection_probability`` (R6's pre-registered target) and the
margin from ``digital_twin.simulation.policy.materiality_margin`` -- which returns ``None``
while R5.2's deferral holds, and then no report can be built: absence is the honest state. None
of the three is imported here, so none can be silently substituted.

**Imports.** This module's own imports are the stdlib, pydantic and two leaf constants from
``uplift`` -- no twin module and not the harness. That bounds what it depends on, not what
loading it costs: ``uplift/__init__.py`` imports ``uplift.consensus_arm``, which imports
``uplift.harness`` at module scope, so importing any ``uplift`` module loads the harness and
the twin today -- the chain ``ci.yml``'s ``uplift-verify`` closure note records. That chain no
longer reaches ``scipy``: Metric_Contract v2 (task 29.4) dropped ``contract.py``'s import of it
(F-A3-1, read, not measured).
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath
from statistics import NormalDist, StatisticsError
from typing import TYPE_CHECKING, Final, Literal

from pydantic import BaseModel, ConfigDict, ValidationError, field_validator, model_validator

from uplift.tuned_static import TUNED_STATIC_ARM
from uplift.uplift_floor import MIN_POWERED_REPLICATES

if TYPE_CHECKING:  # pragma: no cover - annotations only
    from collections.abc import Sequence

__all__ = [
    "INV_TW_002_FLOOR",
    "POWER_REPORT_KIND",
    "POWER_REPORT_PATH",
    "POWER_REPORT_SCHEMA_VERSION",
    "POWER_SOURCE_SET",
    "REDERIVATION_REL_TOL",
    "PowerQuantities",
    "PowerReport",
    "PowerReportError",
    "build_power_report",
    "declared_source_files",
    "derived_replicate_requirement",
    "describes_revision",
    "minimum_detectable_effect",
    "power_quantities",
    "read_power_report",
    "source_set_digest",
    "write_power_report",
]

#: The declared kind. A result artifact carries no ``kind``; this one always does (R6.6).
POWER_REPORT_KIND: Final[Literal["power-report"]] = "power-report"

#: Bumped, never edited in place, if a field is added, removed or redefined.
POWER_REPORT_SCHEMA_VERSION: Final[Literal[1]] = 1

#: Where the committed report lives, repo-relative and POSIX. Deliberately NOT under
#: ``artifacts/``: that tree is git-ignored, and an ignored path cannot be committed.
POWER_REPORT_PATH: Final[str] = "docs/state/uplift-power-report.json"

#: Mirrors ``digital_twin.simulation.monte_carlo.MIN_SCENARIOS``, the INV-TW-002 under-power
#: floor R6.16 names. Declared locally so this module's own imports stay off the twin -- a
#: dependency boundary, not an import-cost saving (see **Imports** in the module docstring) --
#: and pinned EQUAL to that constant by Property 86: a mirror nothing compares is the
#: ``None == None`` shape C75 exists to close.
INV_TW_002_FLOOR: Final[int] = 1000

#: Relative tolerance for re-deriving a stored float. About seven orders of magnitude above an
#: ulp, so cross-platform ``log`` rounding is absorbed; about three below any edit Property 86
#: makes, so a tampered value is still refused.
REDERIVATION_REL_TOL: Final[float] = 1e-9

#: The source set naming the harness revision: the instrument the measurement executes -- the
#: uplift package, the twin's simulation layer and the data files they read. Two entries are
#: beyond the five first declared, because the first and third globs do not reach them and the
#: measurement executes both: ``uplift/regret.py`` imports ``Par_Level_Reorder`` from
#: ``uplift/baselines/``, and with structure 1 off ``engine.py`` draws inter-arrivals at
#: ``TwinConfig.order_arrival_rate`` from ``digital_twin/config.py``. Over-inclusion errs in the
#: safe direction -- an irrelevant edit supersedes a report, while an omission would let a stale
#: one license publication. Callers pass this constant explicitly; no parameter defaults to it.
POWER_SOURCE_SET: Final[tuple[str, ...]] = (
    "uplift/*.py",
    "uplift/metric_contract.yaml",
    "digital_twin/simulation/*.py",
    "digital_twin/simulation/policy.yaml",
    "infrastructure/quality/comparator-tuning.yaml",
    "uplift/baselines/*.py",
    "digital_twin/config.py",
)

#: Mirrors ``uplift.harness.UNATTRIBUTED``, declared locally for the same boundary and pinned by
#: Property 86, which names the harness's own sentinel as a report's run and expects the refusal.
#: A run recorded under it is a run nobody can name (R6.6).
_UNATTRIBUTED: Final[str] = "unknown"

_CONTENT_DIGEST: Final[re.Pattern[str]] = re.compile(r"[0-9a-f]{64}")
_GIT_OBJECT_NAME: Final[re.Pattern[str]] = re.compile(r"[0-9a-f]{40}|[0-9a-f]{64}")


class PowerReportError(ValueError):
    """No admissible Power_Report: refused, never repaired with a substituted number (I-7).

    A ``ValueError``, so one raised inside :class:`PowerReport`'s validators surfaces as a
    pydantic ``ValidationError``; the builder, the reader and the digest raise it directly.
    """


# ---------------------------------------------------------------------------
# The formulas
# ---------------------------------------------------------------------------
def _real(name: str, value: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise PowerReportError(f"{name} must be a real number, got {value!r}")
    return float(value)


def _positive_finite(name: str, value: float) -> float:
    number = _real(name, value)
    if not math.isfinite(number) or number <= 0.0:
        raise PowerReportError(f"{name} must be finite and strictly positive, got {number!r}")
    return number


def _open_unit(name: str, value: float) -> float:
    number = _real(name, value)
    if not math.isfinite(number) or not 0.0 < number < 1.0:
        raise PowerReportError(f"{name} must lie in the open interval (0, 1), got {number!r}")
    return number


def _count(name: str, value: int, *, minimum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise PowerReportError(f"{name} must be an integer count, got {value!r}")
    if value < minimum:
        raise PowerReportError(f"{name} must be at least {minimum}, got {value}")
    return value


def _z_sum(alpha: float, detection_probability: float) -> float:
    """``z_alpha + z_beta``, refused unless it is positive."""
    size = _open_unit("alpha", alpha)
    power = _open_unit("detection_probability", detection_probability)
    standard = NormalDist()
    try:
        z_alpha = standard.inv_cdf(1.0 - size / 2.0)
        z_beta = standard.inv_cdf(power)
    except StatisticsError as error:
        raise PowerReportError(
            f"alpha={size!r} and detection_probability={power!r} have no finite normal "
            f"quantile in binary64: {error}"
        ) from error
    total = z_alpha + z_beta
    if not total > 0.0:
        raise PowerReportError(
            f"detection_probability {power!r} does not exceed alpha / 2 = {size / 2.0!r}, so "
            "z_alpha + z_beta is not positive and no positive effect is the least detectable one"
        )
    return total


def minimum_detectable_effect(
    *, variance: float, replicates: int, alpha: float, detection_probability: float
) -> float:
    """``(z_alpha + z_beta) * sqrt(variance) / sqrt(replicates)``, the paired two-sided MDE.

    Strictly decreasing in ``replicates`` and strictly increasing in ``variance`` over the reals.
    In binary64 the strict forms hold wherever the arguments differ by more than rounding can
    merge; Property 86 states the domain it asserts them over.

    Raises:
        PowerReportError: An input is not finite and positive, a probability is outside
            ``(0, 1)``, or ``detection_probability`` does not exceed ``alpha / 2``.
    """
    total = _z_sum(alpha, detection_probability)
    sigma = math.sqrt(_positive_finite("observed_variance", variance))
    count = _count("replicates", replicates, minimum=1)
    try:
        root_n = math.sqrt(count)
    except OverflowError as error:
        raise PowerReportError(f"replicates={count} exceeds the binary64 range") from error
    return total * sigma / root_n


def derived_replicate_requirement(
    *, variance: float, margin: float, alpha: float, detection_probability: float
) -> int:
    """``ceil(((z_alpha + z_beta) * sqrt(variance) / margin) ** 2)`` replicates per arm.

    The least count at which the materiality margin is itself the minimum detectable effect.
    Squared as ``ratio * ratio`` rather than ``ratio ** 2``: IEEE multiplication is correctly
    rounded and therefore monotone, which ``pow`` is not required to be, and the requirement's
    monotonicity in the variance and the margin is a declared clause of Property 86.

    Raises:
        PowerReportError: As :func:`minimum_detectable_effect`, or the requirement overflows.
    """
    total = _z_sum(alpha, detection_probability)
    sigma = math.sqrt(_positive_finite("observed_variance", variance))
    width = _positive_finite("materiality_margin", margin)
    ratio = total * sigma / width
    required = ratio * ratio
    if not math.isfinite(required):
        raise PowerReportError(
            f"the derived replicate requirement overflows binary64: a margin of {width!r} "
            f"against a variance of {variance!r} cannot be powered by any finite run"
        )
    # Every positive real needs at least one replicate; this binds only if `required` underflows.
    return max(1, math.ceil(required))


@dataclass(frozen=True)
class PowerQuantities:
    """The four fields a :class:`PowerReport` derives, computed by one function for both sides."""

    minimum_detectable_effect: float
    detectable_effect_at_min_powered: float
    derived_replicate_requirement: int
    inv_tw_002_binding: bool


def power_quantities(
    *,
    replicates_per_arm: int,
    observed_variance: float,
    alpha: float,
    detection_probability: float,
    materiality_margin: float,
) -> PowerQuantities:
    """Every derived field of a report, from its inputs -- what the builder writes and what
    :class:`PowerReport` re-derives, so the two cannot disagree about the formula.

    ``replicates_per_arm`` must be at least 2: a variance observed over fewer than two
    replicates is not an observation.

    Raises:
        PowerReportError: Any input is outside the domain the formulas state anything over.
    """
    replicates = _count("replicates_per_arm", replicates_per_arm, minimum=2)
    required = derived_replicate_requirement(
        variance=observed_variance,
        margin=materiality_margin,
        alpha=alpha,
        detection_probability=detection_probability,
    )
    return PowerQuantities(
        minimum_detectable_effect=minimum_detectable_effect(
            variance=observed_variance,
            replicates=replicates,
            alpha=alpha,
            detection_probability=detection_probability,
        ),
        detectable_effect_at_min_powered=minimum_detectable_effect(
            variance=observed_variance,
            replicates=MIN_POWERED_REPLICATES,
            alpha=alpha,
            detection_probability=detection_probability,
        ),
        derived_replicate_requirement=required,
        inv_tw_002_binding=required < INV_TW_002_FLOOR,
    )


def _float_disagreement(name: str, stored: float, derived: float) -> str | None:
    if math.isclose(stored, derived, rel_tol=REDERIVATION_REL_TOL, abs_tol=0.0):
        return None
    return f"{name}={stored!r} but the formula gives {derived!r}"


# ---------------------------------------------------------------------------
# The report
# ---------------------------------------------------------------------------
class PowerReport(BaseModel):
    """Effect size against detection probability at a committed replicate count (R6.5).

    Attributes:
        kind: Always ``"power-report"`` -- declared distinct from an uplift result (R6.6).
        schema_version: The field set's version.
        harness_revision: :func:`source_set_digest` of the instrument the variance was
            measured with. A report naming another revision licenses nothing (R6.7).
        source_run_id: The run that produced the report (R6.6).
        source_revision_sha: The git sha that run checked out. Provenance only; the
            revision binding is ``harness_revision``.
        replicates_per_arm: Replicates per arm the variance was observed over.
        observed_variance: Variance of the per-replicate paired difference against
            ``comparator``, in the margin's units squared.
        variance_source: What that variance was measured on, in words.
        alpha: The Metric_Contract's committed significance level.
        detection_probability: The pre-registered detection probability.
        materiality_margin: The committed margin the requirement is derived against.
        comparator: Always arm E, ``tuned_static`` (ADR-055 D2.7).
        minimum_detectable_effect: ``mde(replicates_per_arm)`` (R6.5).
        detectable_effect_at_min_powered: ``mde(MIN_POWERED_REPLICATES)`` (R6.8).
        derived_replicate_requirement: The count at which the margin becomes detectable.
        inv_tw_002_binding: ``derived_replicate_requirement < MIN_SCENARIOS`` (R6.16).
    """

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True, allow_inf_nan=False)

    kind: Literal["power-report"]
    schema_version: Literal[1]
    harness_revision: str
    source_run_id: str
    source_revision_sha: str
    replicates_per_arm: int
    observed_variance: float
    variance_source: str
    alpha: float
    detection_probability: float
    materiality_margin: float
    comparator: str
    minimum_detectable_effect: float
    detectable_effect_at_min_powered: float
    derived_replicate_requirement: int
    inv_tw_002_binding: bool

    @field_validator("comparator")
    @classmethod
    def _only_the_tuned_control(cls, value: str) -> str:
        if value != TUNED_STATIC_ARM:
            raise PowerReportError(
                f"comparator {value!r} is refused: a Power_Report is denominated against the "
                f"primary cell's re-derived tuned control E ({TUNED_STATIC_ARM!r}) and nothing "
                "else. ADR-055 D2.7 measured most of the regret against the incumbent as "
                "baseline mis-tuning, so a power statement against Par_Level_Reorder, the "
                "reference arm or any incumbent describes the wrong contrast (tasks.md 17.2)"
            )
        return value

    @field_validator("harness_revision")
    @classmethod
    def _a_content_digest(cls, value: str) -> str:
        if _CONTENT_DIGEST.fullmatch(value) is None:
            raise PowerReportError(
                f"harness_revision {value!r} is not a sha256 content digest of the declared "
                "source set (source_set_digest); a git sha is recorded as source_revision_sha"
            )
        return value

    @field_validator("source_revision_sha")
    @classmethod
    def _a_git_object_name(cls, value: str) -> str:
        if _GIT_OBJECT_NAME.fullmatch(value) is None:
            raise PowerReportError(
                f"source_revision_sha {value!r} is not a full lowercase git object name (40 or "
                "64 hex digits); a short or symbolic revision names no commit uniquely"
            )
        return value

    @field_validator("source_run_id")
    @classmethod
    def _names_the_producing_run(cls, value: str) -> str:
        if not value.strip() or value != value.strip() or value == _UNATTRIBUTED:
            raise PowerReportError(
                f"source_run_id {value!r} does not name the run that produced this report "
                f"(R6.6): it must be that run's identifier, never blank or {_UNATTRIBUTED!r}"
            )
        return value

    @field_validator("variance_source")
    @classmethod
    def _states_what_the_variance_was_measured_on(cls, value: str) -> str:
        if not value.strip():
            raise PowerReportError("variance_source must state what the variance was measured on")
        return value

    @model_validator(mode="after")
    def _derived_fields_are_what_the_formulas_produce(self) -> PowerReport:
        derived = power_quantities(
            replicates_per_arm=self.replicates_per_arm,
            observed_variance=self.observed_variance,
            alpha=self.alpha,
            detection_probability=self.detection_probability,
            materiality_margin=self.materiality_margin,
        )
        refusals = [
            reason
            for reason in (
                _float_disagreement(
                    "minimum_detectable_effect",
                    self.minimum_detectable_effect,
                    derived.minimum_detectable_effect,
                ),
                _float_disagreement(
                    "detectable_effect_at_min_powered",
                    self.detectable_effect_at_min_powered,
                    derived.detectable_effect_at_min_powered,
                ),
            )
            if reason is not None
        ]
        if self.derived_replicate_requirement != derived.derived_replicate_requirement:
            refusals.append(
                f"derived_replicate_requirement={self.derived_replicate_requirement} but the "
                f"formula gives {derived.derived_replicate_requirement}"
            )
        if self.inv_tw_002_binding is not derived.inv_tw_002_binding:
            refusals.append(
                f"inv_tw_002_binding={self.inv_tw_002_binding} but the formula gives "
                f"{derived.inv_tw_002_binding}"
            )
        if refusals:
            raise PowerReportError(
                "a stored Power_Report field is not the value its formula produces, so the "
                "report is refused rather than recorded: " + "; ".join(refusals)
            )
        return self

    def to_canonical_json(self) -> str:
        """``json.dumps(..., sort_keys=True, separators=(',', ':'))`` -- the repo convention."""
        return json.dumps(self.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))


def build_power_report(
    *,
    root: Path,
    source_set: Sequence[str],
    source_run_id: str,
    source_revision_sha: str,
    replicates_per_arm: int,
    observed_variance: float,
    variance_source: str,
    alpha: float,
    detection_probability: float,
    materiality_margin: float,
    comparator: str,
) -> PowerReport:
    """Build the report, deriving every derived field and the revision from the inputs.

    Every parameter is required. ``root`` and ``source_set`` name the instrument --
    production passes the repository root and :data:`POWER_SOURCE_SET`. The production sources
    of ``alpha``, ``detection_probability`` and ``materiality_margin`` are named in the module
    docstring; none is read here, so a missing one cannot be defaulted.

    Raises:
        PowerReportError: An input is outside the formulas' domain, the source set cannot be
            read, or the model refuses a field -- a comparator other than arm E included.
    """
    quantities = power_quantities(
        replicates_per_arm=replicates_per_arm,
        observed_variance=observed_variance,
        alpha=alpha,
        detection_probability=detection_probability,
        materiality_margin=materiality_margin,
    )
    revision = source_set_digest(root, source_set)
    try:
        return PowerReport(
            kind=POWER_REPORT_KIND,
            schema_version=POWER_REPORT_SCHEMA_VERSION,
            harness_revision=revision,
            source_run_id=source_run_id,
            source_revision_sha=source_revision_sha,
            replicates_per_arm=replicates_per_arm,
            observed_variance=observed_variance,
            variance_source=variance_source,
            alpha=alpha,
            detection_probability=detection_probability,
            materiality_margin=materiality_margin,
            comparator=comparator,
            minimum_detectable_effect=quantities.minimum_detectable_effect,
            detectable_effect_at_min_powered=quantities.detectable_effect_at_min_powered,
            derived_replicate_requirement=quantities.derived_replicate_requirement,
            inv_tw_002_binding=quantities.inv_tw_002_binding,
        )
    except ValidationError as error:
        raise PowerReportError(f"the Power_Report inputs were refused: {error}") from error


# ---------------------------------------------------------------------------
# The revision
# ---------------------------------------------------------------------------
def _checked_pattern(pattern: str) -> str:
    if not isinstance(pattern, str) or not pattern.strip():
        raise PowerReportError(f"a source pattern must be a non-blank string, got {pattern!r}")
    if "\\" in pattern:
        raise PowerReportError(
            f"source pattern {pattern!r} contains a backslash: patterns are POSIX, so one "
            "pattern selects the same files on every platform"
        )
    posix = PurePosixPath(pattern)
    if posix.is_absolute() or PureWindowsPath(pattern).drive or ".." in posix.parts:
        raise PowerReportError(f"source pattern {pattern!r} is not repo-relative")
    return pattern


def declared_source_files(root: Path, source_set: Sequence[str]) -> tuple[str, ...]:
    """The repo-relative POSIX paths ``source_set`` selects under ``root``, sorted.

    Each declared pattern is a repo-relative POSIX glob. Directories and anything under a
    ``__pycache__`` are never selected, a file two patterns both select is listed once, and a
    pattern that selects no file refuses -- a source set that cannot be read is not a revision.

    Raises:
        PowerReportError: ``source_set`` is a bare string or empty, a pattern is not
            repo-relative POSIX, ``root`` is not a directory, or a pattern selects nothing.
    """
    return tuple(sorted(_selected(root, source_set)))


def _selected(root: Path, source_set: Sequence[str]) -> dict[str, Path]:
    if isinstance(source_set, str):
        raise PowerReportError(
            f"source_set {source_set!r} is one string, not a sequence of patterns: pass "
            "POWER_SOURCE_SET, or another tuple of patterns, explicitly"
        )
    patterns = tuple(source_set)
    if not patterns:
        raise PowerReportError("an empty source set digests nothing, so it names no revision")
    base = Path(root).resolve()
    if not base.is_dir():
        raise PowerReportError(f"source root {base.as_posix()} is not a directory")
    files: dict[str, Path] = {}
    for pattern in patterns:
        selected = 0
        for candidate in base.glob(_checked_pattern(pattern)):
            relative = candidate.relative_to(base)
            if "__pycache__" in relative.parts or not candidate.is_file():
                continue
            files[relative.as_posix()] = candidate
            selected += 1
        if selected == 0:
            raise PowerReportError(
                f"declared source pattern {pattern!r} matches no file under "
                f"{base.as_posix()}: a source set that cannot be read is not a revision"
            )
    return files


def source_set_digest(root: Path, source_set: Sequence[str]) -> str:
    """sha256 over the files ``source_set`` selects under ``root`` -- the harness revision.

    Files are taken in sorted repo-relative POSIX order, each contributing
    ``path + b"\\0" + content + b"\\0"`` with CRLF normalised to LF, so the digest depends on
    neither the order the patterns are declared in, the order the filesystem lists files in,
    where the tree sits on disk, nor the checkout's line-ending convention -- and on every
    other byte of every selected file, and on every selected file's path. The framing is
    unambiguous while no selected file contains a NUL byte, which holds for every text source
    :data:`POWER_SOURCE_SET` declares.

    Raises:
        PowerReportError: As :func:`declared_source_files`, or a selected file is unreadable.
    """
    files = _selected(root, source_set)
    digest = hashlib.sha256()
    for relative in sorted(files):
        try:
            content = files[relative].read_bytes()
        except OSError as error:
            raise PowerReportError(
                f"declared source file {relative} is unreadable: {error}"
            ) from error
        digest.update(relative.encode("utf-8") + b"\0")
        digest.update(content.replace(b"\r\n", b"\n") + b"\0")
    return digest.hexdigest()


def describes_revision(report: PowerReport, root: Path, source_set: Sequence[str]) -> bool:
    """True iff ``report`` was generated from the instrument as it stands under ``root`` (R6.7).

    A report naming any other revision describes a superseded instrument and licenses no
    publication. An unreadable source set raises rather than answering either way, because
    then the revision under measurement could not be named at all.

    Raises:
        PowerReportError: As :func:`source_set_digest`.
    """
    return report.harness_revision == source_set_digest(root, source_set)


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------
def read_power_report(path: Path) -> PowerReport | None:
    """The committed report at ``path``, or ``None`` when there is none.

    Absence is a state, not an error: no report exists yet, and R6.7 makes that a refusal to
    publish, which is the caller's to report. A file that is present but unreadable,
    malformed, or refused by :class:`PowerReport` raises, because it claims a power statement
    it cannot support.

    Raises:
        PowerReportError: A file exists at ``path`` and is not an admissible Power_Report.
    """
    target = Path(path)
    if not target.exists():
        return None
    display = target.as_posix()
    try:
        text = target.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        raise PowerReportError(f"the Power_Report at {display} is unreadable: {error}") from error
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as error:
        raise PowerReportError(f"the Power_Report at {display} is not JSON: {error}") from error
    try:
        return PowerReport.model_validate(payload)
    except ValidationError as error:
        raise PowerReportError(
            f"the Power_Report at {display} does not satisfy the Power_Report contract: {error}"
        ) from error


def write_power_report(report: PowerReport, path: Path) -> Path:
    """Write ``report``'s canonical serialisation to ``path`` (``encoding='utf-8'``).

    The bytes are exactly :meth:`PowerReport.to_canonical_json`: sorted keys, compact
    separators, ASCII, no trailing newline -- so regenerating an unchanged report is a no-op diff.
    """
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(report.to_canonical_json(), encoding="utf-8")
    return target
