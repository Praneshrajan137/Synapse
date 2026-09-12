"""A task record may not claim a landed registry entry the registry does not hold (R3.6).

Feature: purpose-achievement-audit, task 10.8 (design E5.2).

The audit's Requirement 3 found a specific, repeatable failure: ``core-purpose-uplift``
task 9.1 -- *"Replace the ``__placeholder__`` entry in
``infrastructure/ml/published_checkpoints.json`` ... Write the real
``demand_prophet_hgt_tft`` registry entry"* -- is marked ``[x]`` while that file still
holds nothing but ``__placeholder__``. Nothing in the repository objected, because
nothing had ever been asked to. This gate asks.

Its whole discipline is one sentence from R3.6: **when a task record asserts that a
Published_Checkpoint_Registry entry was landed, read the registry file, and if that file
holds no validated non-placeholder entry, fail naming the task record.** So the failure
message carries the spec, the task id, the file and line, and the record's own words --
a reader should never have to hunt for which claim broke.

**R9.10 (decision-quality-proof task 20.5): it now reads the registry it is TOLD about.**
The defect this repairs was fail-open by construction. :func:`evaluate` accepts an
injected ``checkpoint_policy`` and an injected ``root``, but it resolved the registry
through ``published_checkpoint_truth.registry_status(None, ...)``, which reads the
module-level ``REGISTRY`` constant -- ``ROOT / policy().registry_file``, bound at import
from the *committed* policy. So a caller pointed at another tree got a verdict about
**this** repository's registry: a constructed registry holding a landed entry would still
have been judged against the committed placeholder, and a constructed placeholder would
have been judged against a landed committed file and PASSED. The repair is one line at the
declaration -- :func:`read_registry` resolves ``root / active.registry_file`` -- rather
than at the call sites, which is the same shape as the recorded I-5 near-miss where 21
call sites were nearly given a default instead of one declaration being fixed. The
committed behaviour is unchanged (``root / active.registry_file`` *is* ``REGISTRY`` for the
committed policy), and what becomes possible is asserting R9.10 end to end over a tree a
test built, instead of only through the pure :func:`judge` seam.

What counts as a claim
----------------------

A record is a claim when it matches at least one declared assertion pattern **and**
mentions at least one declared subject marker. Both halves are required so that a task
which merely *discusses* the registry or this gate (this spec's own task 10.8) is not
swept up as a claim about it. Patterns, markers, and the specs root all come from
``infrastructure/quality/checkpoint-truth.yaml::task_claims`` (AD-13) -- there is no
pattern literal in this file.

Rules, each naming its subject
------------------------------

========================  ======  ===============================================
rule                      verdict what it means
========================  ======  ===============================================
``unlanded-claim``        1       a CHECKED record claims a landed entry the
                                  registry does not hold (the R3.6 finding)
``unusable-pattern``      2       a declared assertion pattern will not compile
``unresolved-record``     2       a ``must_resolve`` record no longer exists
``undetected-record``     2       a ``must_resolve`` record exists but no pattern
                                  sees it -- a scanner that has stopped seeing the
                                  record it was written against is not a passing
                                  scanner
``specs-unreadable``      2       the specs root or a tasks file cannot be read
``policy-unavailable``    2       the committed policy cannot be read
========================  ======  ===============================================

``1`` (fail) is for a claim that is actually false. ``2`` (unavailable) is for a scan
that could not be trusted to look. Both are non-passing; the split exists so an operator
can tell "a task lies" from "the scanner went blind", which are different repairs. A
record that resolves and is recognised but is **not** checked is reported ``pending`` --
an open task claiming nothing yet is not a finding.

I-0: this gate reads Markdown and one JSON file. It runs nothing.

Run::

    python -m scripts.audit.task_claim_truth            # human report
    python -m scripts.audit.task_claim_truth --json     # canonical JSON
    python -m scripts.audit.task_claim_truth --check    # exit 0/1/2
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final

import structlog
from pydantic import BaseModel, ConfigDict

from scripts.audit.published_checkpoint_truth import (
    POLICY_FILE,
    ROOT,
    CheckpointPolicy,
    PolicyUnavailableError,
    RegistryStatus,
    policy,
    registry_status,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

logger = structlog.get_logger(__name__)

__all__ = [
    "RULES",
    "ClaimFinding",
    "ClaimOutcome",
    "TaskClaimReport",
    "TaskRecord",
    "detect_claim",
    "evaluate",
    "format_report",
    "iter_task_records",
    "judge",
    "main",
    "parse_task_records",
    "read_registry",
    "run",
]

#: ``- [x] 9.1 Replace the ...`` / ``- [ ] 10. Something``, at any indentation.
_RECORD_RE: Final[re.Pattern[str]] = re.compile(
    r"^(?P<indent>[ \t]*)-\s+\[(?P<mark>[^\]])\]\s*(?P<id>\d+(?:\.\d+)*)[.)]?\s+(?P<title>\S.*)$"
)

_CHECKED_MARKS: Final[frozenset[str]] = frozenset({"x", "X"})

#: Rule ids, in report order (the real breach first).
RULES: Final[tuple[str, ...]] = (
    "unlanded-claim",
    "unusable-pattern",
    "unresolved-record",
    "undetected-record",
    "specs-unreadable",
    "policy-unavailable",
)


class ClaimOutcome(str, Enum):
    """Three-state outcome. Only ``PASS`` is a pass (I-7)."""

    PASS = "pass"
    FAIL = "fail"
    UNAVAILABLE = "unavailable"


_EXIT_BY_OUTCOME: Final[dict[ClaimOutcome, int]] = {
    ClaimOutcome.PASS: 0,
    ClaimOutcome.FAIL: 1,
    ClaimOutcome.UNAVAILABLE: 2,
}

_MARKER: Final[dict[ClaimOutcome, str]] = {
    ClaimOutcome.PASS: "[OK]",
    ClaimOutcome.FAIL: "[XX]",
    ClaimOutcome.UNAVAILABLE: "[??]",
}


class TaskRecord(BaseModel):
    """One ``- [x] <id> <title>`` record and the sub-bullets that belong to it."""

    model_config = ConfigDict(frozen=True)

    spec: str
    task_id: str
    checked: bool
    title: str
    body: tuple[str, ...]
    source: str
    line: int
    #: Ids of the assertion patterns this record matched (empty = not a claim).
    matched_patterns: tuple[str, ...] = ()
    #: Subject markers this record mentions (empty = not a claim).
    matched_subjects: tuple[str, ...] = ()

    @property
    def is_claim(self) -> bool:
        """A claim needs both halves: an assertion pattern and a subject marker."""
        return bool(self.matched_patterns) and bool(self.matched_subjects)

    @property
    def name(self) -> str:
        """How this record is named in every message about it (R3.6's obligation)."""
        return f'{self.source}:{self.line} {self.spec} task {self.task_id} "{self.title}"'

    def haystack(self) -> str:
        """The text a pattern is applied to: the title plus its sub-bullets."""
        return "\n".join((self.title, *self.body))


class ClaimFinding(BaseModel):
    """One violation, naming the rule, the requirement, and the record."""

    model_config = ConfigDict(frozen=True)

    rule: str
    requirement: str
    outcome: ClaimOutcome
    subject: str
    detail: str


class TaskClaimReport(BaseModel):
    """Everything one execution of this gate observed."""

    model_config = ConfigDict(frozen=True)

    policy_file: str
    specs_dir: str
    registry_file: str
    registry_state: str
    registry_problems: tuple[str, ...]
    records_scanned: int
    specs_scanned: tuple[str, ...]
    claims: tuple[TaskRecord, ...]
    unlanded: tuple[str, ...]
    pending: tuple[str, ...]
    findings: tuple[ClaimFinding, ...]
    outcome: ClaimOutcome
    detail: str

    @property
    def exit_code(self) -> int:
        """``0`` pass / ``1`` fail / ``2`` unavailable; ``2`` is non-passing."""
        return _EXIT_BY_OUTCOME[self.outcome]

    def canonical_json(self) -> str:
        """Canonical serialisation for a persisted payload."""
        return json.dumps(self.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))


# ---------------------------------------------------------------------------
# Parsing task records
# ---------------------------------------------------------------------------


def _indent_width(line: str) -> int:
    return len(line) - len(line.lstrip())


def parse_task_records(text: str, *, spec: str, source: str) -> tuple[TaskRecord, ...]:
    """Every task record in one ``tasks.md``, with its sub-bullets attached.

    A record's body runs until the next record or the first non-blank line indented no
    further than the record itself, which is exactly how the checklist is written.
    """
    lines = text.splitlines()
    records: list[TaskRecord] = []
    index = 0
    while index < len(lines):
        match = _RECORD_RE.match(lines[index])
        if match is None:
            index += 1
            continue
        indent = len(match.group("indent"))
        body: list[str] = []
        cursor = index + 1
        while cursor < len(lines):
            candidate = lines[cursor]
            if _RECORD_RE.match(candidate) is not None:
                break
            if candidate.strip() and _indent_width(candidate) <= indent:
                break
            if candidate.strip():
                body.append(candidate.strip())
            cursor += 1
        records.append(
            TaskRecord(
                spec=spec,
                task_id=match.group("id"),
                checked=match.group("mark") in _CHECKED_MARKS,
                title=match.group("title").strip(),
                body=tuple(body),
                source=source,
                line=index + 1,
            )
        )
        index = cursor
    return tuple(records)


def iter_task_records(
    specs_root: Path, *, tasks_filename: str
) -> tuple[tuple[TaskRecord, ...], tuple[str, ...], tuple[str, ...]]:
    """Read every spec's task file.

    Returns:
        ``(records, specs_scanned, problems)``. ``problems`` names each spec directory
        whose task file could not be read - never silently skipped.
    """
    records: list[TaskRecord] = []
    scanned: list[str] = []
    problems: list[str] = []
    for spec_dir in sorted(path for path in specs_root.iterdir() if path.is_dir()):
        tasks_file = spec_dir / tasks_filename
        if not tasks_file.is_file():
            continue
        try:
            text = tasks_file.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as error:
            problems.append(f"{spec_dir.name}/{tasks_filename} is unreadable: {error}")
            continue
        relative = tasks_file.resolve()
        try:
            source = relative.relative_to(ROOT).as_posix()
        except ValueError:
            source = tasks_file.as_posix()
        scanned.append(spec_dir.name)
        records.extend(parse_task_records(text, spec=spec_dir.name, source=source))
    return tuple(records), tuple(scanned), tuple(problems)


# ---------------------------------------------------------------------------
# Claim detection
# ---------------------------------------------------------------------------


def detect_claim(
    record: TaskRecord,
    patterns: Sequence[tuple[str, re.Pattern[str]]],
    subject_markers: Sequence[str],
) -> TaskRecord:
    """Return ``record`` annotated with the patterns and subjects it matched."""
    haystack = record.haystack()
    lowered = haystack.lower()
    matched = tuple(
        identifier for identifier, pattern in patterns if pattern.search(haystack) is not None
    )
    subjects = tuple(
        marker for marker in subject_markers if marker.lower() in lowered
    )
    return record.model_copy(update={"matched_patterns": matched, "matched_subjects": subjects})


def _compile_patterns(
    active: CheckpointPolicy,
) -> tuple[list[tuple[str, re.Pattern[str]]], list[ClaimFinding]]:
    """Compile every declared assertion pattern; an uncompilable one is UNAVAILABLE."""
    compiled: list[tuple[str, re.Pattern[str]]] = []
    findings: list[ClaimFinding] = []
    for declared in active.task_claims.assertion_patterns:
        try:
            compiled.append((declared.id, re.compile(declared.pattern, re.IGNORECASE)))
        except re.error as error:
            findings.append(
                ClaimFinding(
                    rule="unusable-pattern",
                    requirement="R3.6",
                    outcome=ClaimOutcome.UNAVAILABLE,
                    subject=declared.id,
                    detail=(
                        f"assertion pattern {declared.id!r} ({declared.pattern!r}) will not "
                        f"compile: {error}; a scanner that cannot apply its own rule is not a "
                        "passing scanner"
                    ),
                )
            )
    return compiled, findings


# ---------------------------------------------------------------------------
# Verdict (pure - the seam a property test drives)
# ---------------------------------------------------------------------------


def judge(
    records: Sequence[TaskRecord],
    *,
    active: CheckpointPolicy,
    registry: RegistryStatus,
    specs_dir: str,
    scanned: Sequence[str] = (),
    scan_problems: Sequence[str] = (),
) -> TaskClaimReport:
    """Apply R3.6 to a set of already-annotated task records. No filesystem, no network.

    ``registry.ok`` is the only landed state: ``placeholder``, ``missing``, and
    ``invalid`` all mean the registry holds no *validated* non-placeholder entry, so a
    checked claim against any of them is false.
    """
    compiled, findings = _compile_patterns(active)
    annotated = tuple(
        detect_claim(record, compiled, active.task_claims.subject_markers) for record in records
    )
    claims = tuple(record for record in annotated if record.is_claim)

    for problem in scan_problems:
        findings.append(
            ClaimFinding(
                rule="specs-unreadable",
                requirement="R3.6",
                outcome=ClaimOutcome.UNAVAILABLE,
                subject=specs_dir,
                detail=problem,
            )
        )

    unlanded: list[str] = []
    pending: list[str] = []
    for claim in claims:
        if not claim.checked:
            pending.append(claim.name)
            continue
        if registry.ok:
            continue
        unlanded.append(claim.name)
        reason = "; ".join(registry.problems) or registry.status
        findings.append(
            ClaimFinding(
                rule="unlanded-claim",
                requirement="R3.6",
                outcome=ClaimOutcome.FAIL,
                subject=claim.name,
                detail=(
                    f"{claim.name} is marked complete and asserts a landed "
                    f"{active.registry_file} entry (matched {list(claim.matched_patterns)} on "
                    f"{list(claim.matched_subjects)}), but that file holds no validated "
                    f"non-placeholder entry for {active.serving_name!r} "
                    f"({registry.status}: {reason})"
                ),
            )
        )

    # -- anti-vacuity: the records this scanner was written against must still be seen --
    by_key = {(record.spec, record.task_id): record for record in annotated}
    for required in active.task_claims.must_resolve:
        record = by_key.get((required.spec, required.task_id))
        subject = f"{required.spec} task {required.task_id}"
        if record is None:
            findings.append(
                ClaimFinding(
                    rule="unresolved-record",
                    requirement=required.requirement,
                    outcome=ClaimOutcome.UNAVAILABLE,
                    subject=subject,
                    detail=(
                        f"{subject} is declared in {POLICY_FILE.name}::task_claims.must_resolve "
                        f"but no such record exists under {specs_dir}; the scan cannot be "
                        f"trusted to look ({required.note.strip()})"
                    ),
                )
            )
            continue
        if not record.is_claim:
            findings.append(
                ClaimFinding(
                    rule="undetected-record",
                    requirement=required.requirement,
                    outcome=ClaimOutcome.UNAVAILABLE,
                    subject=record.name,
                    detail=(
                        f"{record.name} resolves but matches no declared assertion pattern "
                        f"(patterns matched: {list(record.matched_patterns)}, subjects: "
                        f"{list(record.matched_subjects)}); a scanner that has stopped seeing "
                        "the record it was written against is not a passing scanner"
                    ),
                )
            )

    ordered = tuple(
        sorted(
            findings,
            key=lambda item: (
                RULES.index(item.rule) if item.rule in RULES else len(RULES),
                item.subject,
            ),
        )
    )
    if any(item.outcome is ClaimOutcome.FAIL for item in ordered):
        outcome = ClaimOutcome.FAIL
    elif any(item.outcome is ClaimOutcome.UNAVAILABLE for item in ordered):
        outcome = ClaimOutcome.UNAVAILABLE
    else:
        outcome = ClaimOutcome.PASS

    if outcome is ClaimOutcome.PASS:
        detail = (
            f"{len(claims)} task record(s) assert a landed {active.registry_file} entry; "
            + (
                f"the registry holds a validated entry for {active.serving_name!r}"
                if registry.ok
                else f"none of them is marked complete ({len(pending)} pending)"
            )
        )
    else:
        detail = next(item.detail for item in ordered if item.outcome is outcome)

    return TaskClaimReport(
        policy_file=_relative(POLICY_FILE),
        specs_dir=specs_dir,
        registry_file=active.registry_file,
        registry_state=registry.status,
        registry_problems=registry.problems,
        records_scanned=len(annotated),
        specs_scanned=tuple(scanned),
        claims=claims,
        unlanded=tuple(unlanded),
        pending=tuple(pending),
        findings=ordered,
        outcome=outcome,
        detail=detail,
    )


def _relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def read_registry(path: Path) -> tuple[dict[str, Any] | None, str]:
    """Read the Published_Checkpoint_Registry file this gate was TOLD to read (R9.10).

    The declaration is the only source of the path: callers pass ``root /
    active.registry_file``, so a gate pointed at another tree judges *that* tree's
    registry. Reading a module-level constant instead was fail-open by construction --
    see this module's docstring.

    Returns:
        ``(payload, problem)``. ``payload`` is ``None`` exactly when ``problem`` is
        non-empty. A problem names the resolved path, because "the registry holds no
        validated entry" and "the file the declaration names could not be read" are
        different repairs and an operator must be able to tell them apart (I-7).
        ``encoding='utf-8'`` on the read (E-S13-07).
    """
    if not path.is_file():
        return None, f"the declared registry file {_relative(path)} does not exist"
    try:
        parsed: Any = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        return None, f"the declared registry file {_relative(path)} is unreadable: {error}"
    if not isinstance(parsed, dict):
        return None, (
            f"the declared registry file {_relative(path)} is not a JSON object "
            f"(got {type(parsed).__name__}), so it holds no entry to validate"
        )
    return parsed, ""


def _unavailable(
    *, specs_dir: str, registry_file: str, rule: str, subject: str, detail: str
) -> TaskClaimReport:
    return TaskClaimReport(
        policy_file=_relative(POLICY_FILE),
        specs_dir=specs_dir,
        registry_file=registry_file,
        registry_state="unknown",
        registry_problems=(),
        records_scanned=0,
        specs_scanned=(),
        claims=(),
        unlanded=(),
        pending=(),
        findings=(
            ClaimFinding(
                rule=rule,
                requirement="R3.6",
                outcome=ClaimOutcome.UNAVAILABLE,
                subject=subject,
                detail=detail,
            ),
        ),
        outcome=ClaimOutcome.UNAVAILABLE,
        detail=detail,
    )


def evaluate(
    *,
    checkpoint_policy: CheckpointPolicy | None = None,
    specs_root: Path | None = None,
    registry: dict[str, Any] | None = None,
    root: Path = ROOT,
) -> TaskClaimReport:
    """Read the committed policy, scan every spec's task file, and apply R3.6.

    Args:
        checkpoint_policy: Injected policy (default: the committed one).
        specs_root: Injected specs root (default: the policy's ``specs_dir``).
        registry: Injected registry payload (default: read from the file the ACTIVE
            policy declares, resolved against ``root`` -- see :func:`read_registry`).
        root: Tree root the policy's relative paths resolve against.
    """
    try:
        active = policy() if checkpoint_policy is None else checkpoint_policy
    except PolicyUnavailableError as error:
        return _unavailable(
            specs_dir="(unknown)",
            registry_file="(unknown)",
            rule="policy-unavailable",
            subject=_relative(POLICY_FILE),
            detail=str(error),
        )

    target = (root / active.task_claims.specs_dir) if specs_root is None else specs_root
    specs_dir = active.task_claims.specs_dir if specs_root is None else specs_root.as_posix()
    if not target.is_dir():
        return _unavailable(
            specs_dir=specs_dir,
            registry_file=active.registry_file,
            rule="specs-unreadable",
            subject=specs_dir,
            detail=(
                f"the declared specs root {specs_dir} is not a directory, so no task record "
                "could be scanned; absence of a scan is not a pass"
            ),
        )

    try:
        records, scanned, problems = iter_task_records(
            target, tasks_filename=active.task_claims.tasks_filename
        )
    except OSError as error:
        return _unavailable(
            specs_dir=specs_dir,
            registry_file=active.registry_file,
            rule="specs-unreadable",
            subject=specs_dir,
            detail=f"the declared specs root {specs_dir} could not be listed: {error}",
        )

    # R9.10: read the registry the ACTIVE policy declares, resolved against `root`.
    # `registry_status`'s own default would read the committed module-level constant
    # instead, which is a verdict about a file this call may not be about.
    if registry is not None:
        status = registry_status(
            registry,
            name=active.serving_name,
            coverage_floor=active.floors.coverage_p90.value,
        )
    else:
        payload, problem = read_registry(root / active.registry_file)
        if payload is None:
            status = RegistryStatus(status="missing", problems=(problem,))
        else:
            status = registry_status(
                payload,
                name=active.serving_name,
                coverage_floor=active.floors.coverage_p90.value,
            )
    return judge(
        records,
        active=active,
        registry=status,
        specs_dir=specs_dir,
        scanned=scanned,
        scan_problems=problems,
    )


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


def format_report(report: TaskClaimReport) -> list[str]:
    """ASCII-only human summary; every finding names the record it is about."""
    lines = [
        "Task-record claims (E5.2 - R3.6)",
        f"  policy         : {report.policy_file}",
        f"  specs root     : {report.specs_dir} ({len(report.specs_scanned)} spec(s))",
        f"  registry       : {report.registry_file} ({report.registry_state})",
        f"  records scanned: {report.records_scanned}",
        f"  claims found   : {len(report.claims)} "
        f"(unlanded {len(report.unlanded)}, pending {len(report.pending)})",
        f"  status         : {report.outcome.value}  (exit {report.exit_code})",
        f"  reason         : {report.detail}",
    ]
    for finding in report.findings:
        lines.append(
            f"  {_MARKER[finding.outcome]} {finding.rule} [{finding.requirement}]: "
            f"{finding.detail}"
        )
    for name in report.pending:
        lines.append(f"  [--] pending: {name} claims nothing yet (record not marked complete)")
    if report.outcome is ClaimOutcome.UNAVAILABLE:
        lines.append(
            "[??] task-claim-truth: UNAVAILABLE - the scan could not be trusted to look. "
            "Absence of proof is not a pass (I-7)."
        )
    elif report.outcome is ClaimOutcome.FAIL:
        lines.append(
            "[XX] task-claim-truth: FAIL - a task record marked complete asserts a registry "
            "entry the registry does not hold."
        )
    else:
        lines.append("[OK] task-claim-truth: every landed-entry claim is backed by the registry.")
    return lines


def run(*, as_json: bool = False, check: bool = False, out: Path | None = None) -> int:
    """CLI entry point. ``print`` is acceptable here and nowhere else in this module."""
    report = evaluate()
    if as_json:
        print(report.canonical_json())
    else:
        for line in format_report(report):
            print(line)
    if out is not None:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(report.canonical_json(), encoding="utf-8")
    if report.outcome is not ClaimOutcome.PASS:
        logger.info(
            "task_claim_truth_non_passing",
            outcome=report.outcome.value,
            unlanded=len(report.unlanded),
            registry_state=report.registry_state,
        )
    return report.exit_code if check else _EXIT_BY_OUTCOME[ClaimOutcome.PASS]


def main(argv: list[str] | None = None) -> int:
    """``python -m scripts.audit.task_claim_truth [--json] [--check] [--out PATH]``."""
    parser = argparse.ArgumentParser(
        prog="python -m scripts.audit.task_claim_truth",
        description=(
            "Fail naming any task record that is marked complete while asserting a "
            "published-checkpoint registry entry the registry does not hold (R3.6)."
        ),
    )
    parser.add_argument("--json", action="store_true", help="Emit the canonical JSON report.")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit 0 pass / 1 false claim / 2 unavailable (2 is non-passing).",
    )
    parser.add_argument("--out", type=Path, default=None, help="Persist the canonical report.")
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])
    return run(as_json=bool(args.json), check=bool(args.check), out=args.out)


if __name__ == "__main__":
    sys.exit(main())
