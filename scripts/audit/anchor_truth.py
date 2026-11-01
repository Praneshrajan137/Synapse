"""Anchor-freshness truth: an unanchored chain is unverifiable (design E4.3; R6.11).

Feature: purpose-achievement-audit, task 7.6.

The audit found that the daily anchor - the one artifact a third party can hold
independently of this repository's database - had no scheduled caller
(``orchestrator/audit/anchorer.py:63``, Requirement 6). Nothing failed when it stopped
being published, because nothing ever asked whether it had been. This gate asks.

Its whole discipline is one sentence from R6.11: **if no anchor exists, or the newest
anchor is older than the declared freshness bound, the chain is reported
UNVERIFIABLE - never verified.** So this module has no ``verified`` outcome at all. Its
best possible finding is ``anchored``: a fresh commitment to a head exists, which makes
the chain *verifiable* by ``python -m orchestrator.audit.cli verify --head <hash>``.
The walk is what verifies; the anchor is what makes the walk's head independent. A gate
that blurred those two would hand an operator a green tick for evidence nobody checked
(I-7).

Rules, each naming its subject
------------------------------

============================  ======  ==============================================
rule                          verdict what it means
============================  ======  ==============================================
``no-anchor``                 2       the anchor directory holds no anchor at all
``stale-anchor``              2       the newest anchor is older than the bound
``unreadable-anchor``         1       a published file is not a readable commitment
``non-canonical-anchor``      1       published bytes are not compact canonical JSON
``anchor-dir-drift``          1       committed directory != the anchorer's constant
============================  ======  ==============================================

``1`` (fail) is for a *published* anchor that is defective - somebody wrote a file that
does not do the job. ``2`` (unavailable) is for the absence or the staleness of
evidence. Both are non-passing; the split exists so an operator can tell "nobody
anchored" from "the anchor we have is broken", which are different repairs.

The freshness bound is **never hardcoded**: ``max_age_hours`` comes from
``infrastructure/quality/audit-chain-bounds.yaml`` through
``orchestrator.audit.chain_walk.load_chain_bounds`` (AD-13), the same reader the walker
uses, and the anchor directory comes from ``anchor_freshness.anchor_dir`` in that same
committed file. If the two sides of that path ever disagree - the committed directory
and ``anchorer.ANCHOR_DIR`` - this gate says so rather than quietly reading one of them.

Run::

    python -m scripts.audit.anchor_truth            # human report
    python -m scripts.audit.anchor_truth --json     # machine JSON

Exit codes: ``0`` pass, ``1`` fail, ``2`` unavailable; ``2`` is non-passing. Every read
uses ``encoding='utf-8'`` (E-S13-07) and all console output is ASCII.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final, Literal

import structlog
import yaml
from pydantic import BaseModel, ConfigDict

# Runtime import: ``AnchorRecord`` appears in a Pydantic field annotation.
from orchestrator.audit.anchorer import ANCHOR_DIR, AnchorFormatError, AnchorRecord
from orchestrator.audit.chain_walk import BOUNDS_PATH, load_chain_bounds

if TYPE_CHECKING:
    from collections.abc import Sequence

logger = structlog.get_logger(__name__)

__all__ = [
    "AnchorFile",
    "AnchorFinding",
    "AnchorSettings",
    "AnchorTruthReport",
    "evaluate",
    "evaluate_anchors",
    "load_anchor_settings",
    "load_anchors",
    "main",
    "read_anchor_file",
    "run",
]

REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[2]

_EXIT_CODES: Final[dict[str, int]] = {"pass": 0, "fail": 1, "unavailable": 2}

#: Rule order in the printed report, worst repair first.
_RULES: Final[tuple[str, ...]] = (
    "no-anchor",
    "stale-anchor",
    "unreadable-anchor",
    "non-canonical-anchor",
    "anchor-dir-drift",
)

_PREFIX: Final[int] = 12


class SettingsUnavailableError(RuntimeError):
    """The committed anchor settings could not be read.

    Never a pass: without the committed bound there is no declared freshness to judge
    against, and inventing one would be exactly the ungated number AD-13 forbids.
    """


# ---------------------------------------------------------------------------
# Committed settings (AD-13 - read, never inlined)
# ---------------------------------------------------------------------------


class AnchorSettings(BaseModel):
    """The committed anchor directory and freshness bound."""

    model_config = ConfigDict(frozen=True)

    anchor_dir: Path
    max_age_hours: int
    declared_dir: str


def load_anchor_settings(path: Path | None = None) -> AnchorSettings:
    """Load ``anchor_freshness`` from the committed bounds file.

    ``max_age_hours`` is taken from :func:`load_chain_bounds` so the walker and this
    gate cannot read different bounds from the same file.

    Raises:
        SettingsUnavailableError: The file is missing, unparseable, or names no
            anchor directory.
    """
    source = path if path is not None else BOUNDS_PATH
    try:
        payload: Any = yaml.safe_load(source.read_text(encoding="utf-8"))
        bounds = load_chain_bounds(source)
    except (OSError, KeyError, ValueError, yaml.YAMLError) as exc:
        raise SettingsUnavailableError(
            f"cannot read the committed anchor settings from {source.name}: {exc}"
        ) from exc

    freshness = payload.get("anchor_freshness") if isinstance(payload, dict) else None
    if not isinstance(freshness, dict):
        raise SettingsUnavailableError(
            f"{source.name} declares no 'anchor_freshness' section"
        )
    declared = freshness.get("anchor_dir")
    if not isinstance(declared, str) or not declared.strip():
        raise SettingsUnavailableError(
            f"{source.name}::anchor_freshness declares no 'anchor_dir'"
        )
    return AnchorSettings(
        anchor_dir=REPO_ROOT / Path(declared.strip()),
        max_age_hours=bounds.anchor_max_age_hours,
        declared_dir=declared.strip(),
    )


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class AnchorFile(BaseModel):
    """One file in the anchor directory, and what could be read from it."""

    model_config = ConfigDict(frozen=True)

    name: str
    record: AnchorRecord | None
    canonical: bool
    error: str | None

    @property
    def usable(self) -> bool:
        """Whether this file yielded a commitment to a head hash.

        Non-canonical bytes are a defect (E-S9-03) but not an unusable anchor: the
        head hash is still there, and discarding real evidence over its formatting
        would make the gate less honest, not more.
        """
        return self.record is not None


class AnchorFinding(BaseModel):
    """One violation, naming the rule, the requirement, and the subject."""

    model_config = ConfigDict(frozen=True)

    rule: str
    requirement: str
    subject: str
    detail: str


class AnchorTruthReport(BaseModel):
    """Everything one execution of this gate observed.

    ``chain_status`` has exactly two values and neither of them is ``verified``:

    * ``anchored`` - a fresh commitment to a head exists, so the chain can be walked
      against an independent head (R6.12's guarantee is available to a third party).
    * ``unverifiable`` - no anchor, or the newest is staler than the committed bound
      (R6.11). Whatever else is green, the chain is not verifiable from outside.
    """

    model_config = ConfigDict(frozen=True)

    anchor_dir: str
    max_age_hours: int
    evaluated_at: datetime
    anchors: tuple[AnchorFile, ...]
    newest_head: str | None
    newest_anchored_at: datetime | None
    newest_age_hours: float | None
    chain_status: Literal["anchored", "unverifiable"]
    verdict: Literal["pass", "fail", "unavailable"]
    reason: str
    findings: tuple[AnchorFinding, ...]

    @property
    def exit_code(self) -> int:
        """``0`` pass / ``1`` fail / ``2`` unavailable; ``2`` is non-passing."""
        return _EXIT_CODES[self.verdict]


# ---------------------------------------------------------------------------
# Reading the published anchors
# ---------------------------------------------------------------------------


def read_anchor_file(path: Path) -> AnchorFile:
    """Read one anchor file: its record, and whether its bytes are canonical.

    Canonicality is judged against the *parsed payload* re-serialised compactly, not
    against the model, so a legacy-shaped anchor is not accused of bad formatting for
    using the pre-task-7.6 key names (E-S9-03 is about the bytes, not the schema).
    """
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return AnchorFile(name=path.name, record=None, canonical=False, error=str(exc))

    canonical = False
    try:
        payload: Any = json.loads(text)
        canonical = (
            json.dumps(payload, sort_keys=True, separators=(",", ":")) == text.strip()
        )
    except json.JSONDecodeError:
        canonical = False

    try:
        record = AnchorRecord.from_json(text)
    except AnchorFormatError as exc:
        return AnchorFile(name=path.name, record=None, canonical=canonical, error=str(exc))
    return AnchorFile(name=path.name, record=record, canonical=canonical, error=None)


def load_anchors(directory: Path) -> tuple[AnchorFile, ...]:
    """Every ``*.json`` anchor in ``directory``, in name order.

    A missing directory yields an empty tuple, which :func:`evaluate_anchors` reports
    as ``no-anchor`` - the same verdict as an empty directory, because to a third party
    they are the same thing: no commitment exists.
    """
    if not directory.is_dir():
        return ()
    return tuple(read_anchor_file(path) for path in sorted(directory.glob("*.json")))


# ---------------------------------------------------------------------------
# Verdict (pure - the seam a property test drives)
# ---------------------------------------------------------------------------


def _as_utc(value: datetime) -> datetime:
    """Normalise to UTC, treating a naive timestamp as UTC."""
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def evaluate_anchors(
    anchors: Sequence[AnchorFile],
    *,
    now: datetime,
    max_age_hours: int,
    anchor_dir: str,
    dir_drift: str | None = None,
) -> AnchorTruthReport:
    """Apply R6.11 to a set of published anchors. No filesystem, no clock, no network.

    Args:
        anchors: The published anchors as read.
        now: The evaluation instant, injected so the verdict is reproducible.
        max_age_hours: The committed freshness bound.
        anchor_dir: The directory, for the report only.
        dir_drift: A description of a committed-vs-constant directory disagreement, or
            ``None``.

    Returns:
        A report whose ``chain_status`` is ``unverifiable`` whenever no usable anchor
        exists or the newest usable anchor is staler than the bound.
    """
    stamped = _as_utc(now)
    findings: list[AnchorFinding] = []

    if dir_drift is not None:
        findings.append(
            AnchorFinding(
                rule="anchor-dir-drift",
                requirement="R6.11",
                subject=anchor_dir,
                detail=dir_drift,
            )
        )

    for anchor in anchors:
        if anchor.record is None:
            findings.append(
                AnchorFinding(
                    rule="unreadable-anchor",
                    requirement="R6.12",
                    subject=anchor.name,
                    detail=(
                        "published file is not a readable commitment to a head hash: "
                        f"{anchor.error or 'unknown reason'}"
                    ),
                )
            )
            continue
        if not anchor.canonical:
            findings.append(
                AnchorFinding(
                    rule="non-canonical-anchor",
                    requirement="E-S9-03",
                    subject=anchor.name,
                    detail=(
                        "published bytes are not compact canonical JSON "
                        "(json.dumps(payload, sort_keys=True, separators=(',',':')))"
                    ),
                )
            )

    usable: list[AnchorRecord] = [
        anchor.record for anchor in anchors if anchor.record is not None
    ]
    newest: AnchorRecord | None = max(
        usable, key=lambda record: record.anchored_at, default=None
    )

    if newest is None:
        findings.append(
            AnchorFinding(
                rule="no-anchor",
                requirement="R6.11",
                subject=anchor_dir,
                detail=(
                    f"no anchor exists ({len(anchors)} file(s) present, none readable as a "
                    "commitment to a head hash); the chain is UNVERIFIABLE from outside "
                    "this repository"
                ),
            )
        )
        return _report(
            anchor_dir=anchor_dir,
            max_age_hours=max_age_hours,
            evaluated_at=stamped,
            anchors=tuple(anchors),
            newest=None,
            age_hours=None,
            chain_status="unverifiable",
            verdict="unavailable",
            reason="no anchor exists; the chain is unverifiable (R6.11)",
            findings=findings,
        )

    age_hours = newest.age_hours(stamped)
    if newest.is_stale(stamped, max_age_hours=max_age_hours):
        findings.append(
            AnchorFinding(
                rule="stale-anchor",
                requirement="R6.11",
                subject=newest.date,
                detail=(
                    f"newest anchor is {age_hours:.1f}h old, older than the committed "
                    f"bound of {max_age_hours}h; the chain is UNVERIFIABLE"
                ),
            )
        )
        return _report(
            anchor_dir=anchor_dir,
            max_age_hours=max_age_hours,
            evaluated_at=stamped,
            anchors=tuple(anchors),
            newest=newest,
            age_hours=age_hours,
            chain_status="unverifiable",
            verdict="unavailable",
            reason=(
                f"newest anchor is {age_hours:.1f}h old against a {max_age_hours}h bound; "
                "the chain is unverifiable (R6.11)"
            ),
            findings=findings,
        )

    defective = tuple(finding for finding in findings if finding.rule != "stale-anchor")
    if defective:
        return _report(
            anchor_dir=anchor_dir,
            max_age_hours=max_age_hours,
            evaluated_at=stamped,
            anchors=tuple(anchors),
            newest=newest,
            age_hours=age_hours,
            chain_status="anchored",
            verdict="fail",
            reason=(
                f"{len(defective)} published anchor defect(s); a fresh commitment exists "
                f"({age_hours:.1f}h old) but the directory holds files that do not do the job"
            ),
            findings=findings,
        )

    return _report(
        anchor_dir=anchor_dir,
        max_age_hours=max_age_hours,
        evaluated_at=stamped,
        anchors=tuple(anchors),
        newest=newest,
        age_hours=age_hours,
        chain_status="anchored",
        verdict="pass",
        reason=(
            f"newest anchor commits to head {newest.head_hash[:_PREFIX]} and is "
            f"{age_hours:.1f}h old, within the committed {max_age_hours}h bound; the chain "
            "is verifiable against it (not yet verified - that is the walk's job)"
        ),
        findings=(),
    )


def _report(
    *,
    anchor_dir: str,
    max_age_hours: int,
    evaluated_at: datetime,
    anchors: tuple[AnchorFile, ...],
    newest: AnchorRecord | None,
    age_hours: float | None,
    chain_status: Literal["anchored", "unverifiable"],
    verdict: Literal["pass", "fail", "unavailable"],
    reason: str,
    findings: Sequence[AnchorFinding],
) -> AnchorTruthReport:
    """Assemble a report with findings in a stable rule order."""
    ordered = tuple(
        sorted(
            findings,
            key=lambda item: (
                _RULES.index(item.rule) if item.rule in _RULES else len(_RULES),
                item.subject,
            ),
        )
    )
    return AnchorTruthReport(
        anchor_dir=anchor_dir,
        max_age_hours=max_age_hours,
        evaluated_at=evaluated_at,
        anchors=anchors,
        newest_head=None if newest is None else newest.head_hash,
        newest_anchored_at=None if newest is None else newest.anchored_at,
        newest_age_hours=age_hours,
        chain_status=chain_status,
        verdict=verdict,
        reason=reason,
        findings=ordered,
    )


def evaluate(
    *,
    directory: Path | None = None,
    settings_path: Path | None = None,
    now: datetime | None = None,
) -> AnchorTruthReport:
    """Read the committed settings and the published anchors, then apply R6.11.

    Raises:
        SettingsUnavailableError: The committed settings could not be read.
    """
    settings = load_anchor_settings(settings_path)
    target = directory if directory is not None else settings.anchor_dir
    drift: str | None = None
    if directory is None and settings.anchor_dir.resolve() != ANCHOR_DIR.resolve():
        drift = (
            f"committed anchor_dir '{settings.declared_dir}' does not resolve to "
            f"orchestrator.audit.anchorer.ANCHOR_DIR ('{ANCHOR_DIR.name}'); the publisher and "
            "the gate would read different directories"
        )
    return evaluate_anchors(
        load_anchors(target),
        now=now if now is not None else datetime.now(UTC),
        max_age_hours=settings.max_age_hours,
        anchor_dir=settings.declared_dir if directory is None else target.as_posix(),
        dir_drift=drift,
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def run(*, as_json: bool = False, directory: Path | None = None) -> int:
    """CLI entry point. ``print`` is acceptable here and nowhere else in this module."""
    try:
        report = evaluate(directory=directory)
    except SettingsUnavailableError as exc:
        logger.error("anchor_truth_unavailable", reason=str(exc))
        print("Anchor freshness (E4.3 - R6.11/R6.12)")
        print("  chain          : UNVERIFIABLE")
        print("  status         : unavailable  (exit 2)")
        print(f"  reason         : {exc}", file=sys.stderr)
        return _EXIT_CODES["unavailable"]

    if as_json:
        print(json.dumps(report.model_dump(mode="json"), sort_keys=True, indent=2))
        return report.exit_code

    age = (
        "n/a"
        if report.newest_age_hours is None
        else f"{report.newest_age_hours:.1f}h (bound {report.max_age_hours}h)"
    )
    print("Anchor freshness (E4.3 - R6.11/R6.12)")
    print(f"  anchor dir     : {report.anchor_dir}")
    print(f"  anchors found  : {len(report.anchors)}")
    print(f"  newest head    : {report.newest_head[:_PREFIX] if report.newest_head else 'none'}")
    print(f"  newest age     : {age}")
    print(f"  chain          : {report.chain_status.upper()}")
    print(f"  status         : {report.verdict}  (exit {report.exit_code})")
    print(f"  reason         : {report.reason}")
    for finding in report.findings:
        print(
            f"  {finding.rule} [{finding.requirement}] {finding.subject}: {finding.detail}",
            file=sys.stderr,
        )
    return report.exit_code


def main(argv: list[str] | None = None) -> int:
    """``python -m scripts.audit.anchor_truth [--json] [--anchor-dir DIR]``."""
    parser = argparse.ArgumentParser(
        prog="python -m scripts.audit.anchor_truth",
        description=(
            "Report whether a fresh anchor commits to the audit-chain head. No anchor, "
            "or a stale one, means the chain is UNVERIFIABLE (R6.11)."
        ),
    )
    parser.add_argument("--json", action="store_true", help="Emit the report as JSON.")
    parser.add_argument(
        "--anchor-dir",
        type=Path,
        default=None,
        help="Directory of published anchors (default: the committed anchor_dir).",
    )
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])
    return run(as_json=bool(args.json), directory=args.anchor_dir)


if __name__ == "__main__":
    raise SystemExit(main())
