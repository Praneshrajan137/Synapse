"""A spec's task counts are derived from the ledger, never transcribed from its prose.

Feature: decision-quality-proof, session-protocol revision.

Why this exists
---------------

``SESSION_PROTOCOL.md`` used to carry a ``python -c`` one-liner and a table of counts
beside the instruction "re-derive these; do not trust them". Three problems followed from
a census that lives in prose:

1. The one-liner matched sub-tasks with ``^  - \\[( |x)\\]`` -- **exactly two** spaces of
   indent -- so a leaf nested any deeper was silently absent from the denominator.
2. Its "next ten" read only sub-tasks, so a childless checkpoint parent could never be
   offered, and the set of CI-gated tasks was a hardcoded literal that disagreed with the
   prose beside it (a set of six described as "seven").
3. Every number it produced was then copied into three documents by hand.

This module is the mechanical answer. It is the census; the documents cite it.

Three marks, because the honesty contract has three states (I-7)
----------------------------------------------------------------

=========  ==================================================================
``[ ]``    open -- not started
``[~]``    authored, **discharge pending**: the work is on disk, and the proof
           that it works is owed by the job named in its ``discharge:`` line.
           Not a pass. "Authored and diagnostics-clean, not executed" is a
           legitimate result; recording it as ``[x]`` is not. **A ``[~]`` also
           owes a ``last-checked:`` sub-bullet naming the run its discharge job
           was last read at** -- see ``unharvested-pending`` below.
``[x]``    done **and** discharged
=========  ==================================================================

``[~]`` is deliberately compatible with ``scripts/audit/task_claim_truth.py``, whose
``_CHECKED_MARKS`` is ``{"x", "X"}``: a ``[~]`` record is *unchecked* there, so it lands
in that gate's ``pending`` bucket, which it explicitly does not treat as a finding.

A leaf is derived from the id tree, not from indentation: task ``12`` is a parent because
``12.1`` exists, and task ``11`` is a leaf because nothing is named ``11.<n>``.

Gating is derived, never declared twice
---------------------------------------

An open leaf carrying a ``discharge:`` line is **CI-gated** and is not offered as
authorable work. That replaces the hardcoded ``GATED`` set: the batch planner and the
census now read the same source, so they cannot disagree.

Rules, each naming its subject
------------------------------

========================  ======  ===============================================
rule                      verdict what it means
========================  ======  ===============================================
``unknown-mark``          2       a checkbox carries a mark this vocabulary does
                                  not define -- the census cannot classify it and
                                  will not guess
``duplicate-id``          2       two records share one task id, so a count over
                                  ids is not a count over records
``unharvested-pending``   2       a ``[~]`` records no ``last-checked:`` run for
                                  its discharge job. A mark whose proof has
                                  silently arrived is indistinguishable, from the
                                  ledger alone, from one still waiting -- task
                                  26.1 sat dischargeable for two sessions while
                                  every sweep reported green (steering guardrail
                                  G4). Static by design: asking GitHub instead
                                  would move this census out of the LOCAL
                                  allow-list it sits in as a ~1s file reader
``ledger-unreadable``     2       the tasks file cannot be read
========================  ======  ===============================================

Both non-passing verdicts are ``2`` (unavailable): a census that could not classify
every record is not a passing census, but neither is it a false claim by anyone.

``--files`` adds two **informational** observations and no verdict, because the paths in
a task body include ones the task names in order to reject them (task 12.1 names
``infrastructure/quality/twin-decision-relevance.yaml``, which Conflict A decided against
creating). Turning those into failures would manufacture findings:

* ``prior-art`` -- an **open** leaf whose named paths already exist on disk. This is the
  session-1 failure mode: that session opened with eight tasks implemented and unticked.
  Disk outranks the ledger, so this is the list to read before authoring.
* ``absent-artifact`` -- a **done or pending** leaf naming a path that does not exist.

I-0: this module reads Markdown and calls ``Path.exists``. It runs nothing.

Run::

    python -m scripts.audit.spec_ledger_census                    # human report
    python -m scripts.audit.spec_ledger_census --json             # canonical JSON
    python -m scripts.audit.spec_ledger_census --check            # exit 0/2
    python -m scripts.audit.spec_ledger_census --files            # + disk observations
    python -m scripts.audit.spec_ledger_census --next 40          # the next batch
    python -m scripts.audit.spec_ledger_census --spec other-spec
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from enum import Enum
from pathlib import Path
from typing import Final

import structlog
from pydantic import BaseModel, ConfigDict

logger = structlog.get_logger(__name__)

__all__ = [
    "DEFAULT_SPEC",
    "MARK_DONE",
    "MARK_OPEN",
    "MARK_PENDING",
    "RULES",
    "CensusFinding",
    "CensusOutcome",
    "LedgerCensus",
    "LedgerRecord",
    "census",
    "evaluate",
    "extract_paths",
    "format_report",
    "main",
    "parse_records",
    "run",
]

ROOT: Final[Path] = Path(__file__).resolve().parents[2]
SPECS_DIR: Final[str] = ".kiro/specs"
TASKS_FILENAME: Final[str] = "tasks.md"
DEFAULT_SPEC: Final[str] = "decision-quality-proof"
DEFAULT_BATCH: Final[int] = 40

MARK_OPEN: Final[str] = " "
MARK_PENDING: Final[str] = "~"
MARK_DONE: Final[str] = "x"

#: Mirrors ``task_claim_truth._RECORD_RE`` so both tools agree on what a record is.
_RECORD_RE: Final[re.Pattern[str]] = re.compile(
    r"^(?P<indent>[ \t]*)-\s+\[(?P<mark>[^\]])\]\s*(?P<id>\d+(?:\.\d+)*)[.)]?\s+(?P<title>\S.*)$"
)

#: ``- discharge: uplift.yml::twin-regret`` after markdown emphasis is stripped.
_DISCHARGE_RE: Final[re.Pattern[str]] = re.compile(r"^discharge:\s*(?P<job>\S.*?)\s*$", re.I)

#: A ``[~]`` leaf's harvest record: the run its discharge job was last read at (G4).
#:
#: WHY THIS IS A STATIC CONVENTION AND NOT A NETWORK CALL. The obligation is "no session
#: closes with an unharvested ``[~]``", and the tempting implementation is for this module
#: to ask GitHub whether each discharge job has reported. That would move this census out
#: of the LOCAL allow-list in `.kiro/steering/execution-routing.md`: it is a pure file
#: reader costing ~1s, and a network call would make a cheap gate an expensive one and
#: couple a local hygiene check to an API's availability.
#:
#: So the harvest leaves an ARTIFACT instead. A ``[~]`` leaf records the run it was last
#: checked against, exactly as it records the job that owes its proof, and this module
#: asserts the artifact exists. That is derivable from the file alone, and it converts
#: "remember to check" into a thing a reader can audit -- which is the difference between
#: task 26.1 sitting dischargeable for two sessions and it being caught on the next open.
_HARVEST_RE: Final[re.Pattern[str]] = re.compile(
    r"^last-checked:\s*(?P<run>\S.*?)\s*$", re.I
)

_EMPHASIS: Final[str] = "-*_` \t"

_BACKTICKED_RE: Final[re.Pattern[str]] = re.compile(r"`([^`]+)`")

#: A path a task annotates ``(new)`` is one the task expects to *create*, so finding it
#: already on disk is a strong prior-art signal. An unannotated path is usually a module
#: the task modifies in place, where existence proves nothing.
_DECLARED_NEW_RE: Final[re.Pattern[str]] = re.compile(r"`([^`]+)`\s*\(new\)", re.I)

#: Non-ASCII punctuation the source documents use, mapped for console output only. The
#: JSON payload keeps the true title; consoles on Windows do not (ASCII-only rule).
_ASCII_MAP: Final[dict[str, str]] = {
    "\u2014": "--",
    "\u2013": "-",
    "\u2018": "'",
    "\u2019": "'",
    "\u201c": '"',
    "\u201d": '"',
    "\u2026": "...",
    "\u2192": "->",
    "\u00d7": "x",
    "\u2264": "<=",
    "\u2265": ">=",
    "\u2713": "ok",
}

#: A leading dot is required, not optional: this repo's paths include ``.github/``,
#: ``.kiro/`` and ``.claude/``. ``.`` and ``..`` alone are excluded by the separate
#: requirements that a candidate contain ``/`` and end in a known suffix.
_PATH_RE: Final[re.Pattern[str]] = re.compile(r"^[A-Za-z0-9_.][A-Za-z0-9_./-]*$")

_PATH_SUFFIXES: Final[frozenset[str]] = frozenset(
    {
        ".cfg",
        ".json",
        ".lock",
        ".md",
        ".py",
        ".sh",
        ".toml",
        ".ts",
        ".tsx",
        ".txt",
        ".yaml",
        ".yml",
    }
)

RULES: Final[tuple[str, ...]] = (
    "unknown-mark",
    "duplicate-id",
    "unharvested-pending",
    "ledger-unreadable",
)


class CensusOutcome(str, Enum):
    """Two-state outcome. Only ``PASS`` is a pass (I-7)."""

    PASS = "pass"
    UNAVAILABLE = "unavailable"


_EXIT_BY_OUTCOME: Final[dict[CensusOutcome, int]] = {
    CensusOutcome.PASS: 0,
    CensusOutcome.UNAVAILABLE: 2,
}

_MARKER: Final[dict[CensusOutcome, str]] = {
    CensusOutcome.PASS: "[OK]",
    CensusOutcome.UNAVAILABLE: "[??]",
}


class LedgerRecord(BaseModel):
    """One ``- [<mark>] <id> <title>`` record and the sub-bullets that belong to it."""

    model_config = ConfigDict(frozen=True)

    task_id: str
    mark: str
    title: str
    body: tuple[str, ...]
    line: int
    #: The job owed the proof, from a ``discharge:`` sub-bullet. ``None`` = no gate.
    discharge: str | None = None
    #: The run a ``[~]``'s discharge job was last read at, from a ``last-checked:``
    #: sub-bullet. ``None`` on a ``[~]`` is the unharvested state G4 forbids at close.
    last_checked: str | None = None
    #: Populated by the id tree, not by indentation.
    is_leaf: bool = True

    @property
    def is_done(self) -> bool:
        """Done **and** discharged."""
        return self.mark.lower() == MARK_DONE

    @property
    def is_pending(self) -> bool:
        """Authored, discharge pending. Not a pass."""
        return self.mark == MARK_PENDING

    @property
    def is_open(self) -> bool:
        """Not started."""
        return self.mark == MARK_OPEN

    @property
    def is_gated(self) -> bool:
        """CI-gated: the discharge line names the job that owes the proof."""
        return self.discharge is not None

    @property
    def is_unharvested(self) -> bool:
        """A ``[~]`` that records no run its discharge job was read at (G4).

        Only ``[~]`` can be unharvested. An open leaf owes no proof yet and a done leaf
        has already had one, so neither carries the obligation.
        """
        return self.is_pending and self.last_checked is None

    @property
    def name(self) -> str:
        """How this record is named in every message about it."""
        return f'task {self.task_id} "{self.title}"'


class CensusFinding(BaseModel):
    """One reason the census could not be trusted, naming its subject."""

    model_config = ConfigDict(frozen=True)

    rule: str
    outcome: CensusOutcome
    subject: str
    detail: str


class DiskObservation(BaseModel):
    """An informational disagreement between the ledger and the tree."""

    model_config = ConfigDict(frozen=True)

    kind: str
    task_id: str
    path: str
    detail: str


class LedgerCensus(BaseModel):
    """Everything one execution of this census observed."""

    model_config = ConfigDict(frozen=True)

    spec: str
    source: str
    parents: int
    leaves: int
    done: int
    pending: int
    open_count: int
    #: Open leaves with no ``discharge:`` line, in ledger order.
    authorable: tuple[str, ...]
    #: Open leaves whose ``discharge:`` line names the job that owes the proof.
    gated: tuple[str, ...]
    #: Every open leaf id in ledger order, gated or not. Ledger *position* is what makes
    #: ``barriers_crossed`` derivable: ``authorable`` alone cannot see what it steps over.
    open_order: tuple[str, ...]
    #: ``{task_id: job}`` for every open CI-gated leaf. A barrier candidate.
    gated_jobs: dict[str, str]
    #: Every ``[~]`` leaf and the job that owes its proof.
    pending_discharges: tuple[str, ...]
    #: ``[~]`` leaves recording no run their discharge job was read at (G4). Non-passing:
    #: a mark whose discharge has silently arrived is indistinguishable, from the ledger
    #: alone, from one still waiting -- which is how task 26.1 sat dischargeable for two
    #: sessions while every sweep reported green.
    unharvested: tuple[str, ...]
    observations: tuple[DiskObservation, ...]
    findings: tuple[CensusFinding, ...]
    outcome: CensusOutcome
    detail: str

    @property
    def exit_code(self) -> int:
        """``0`` pass / ``2`` unavailable. ``2`` is non-passing."""
        return _EXIT_BY_OUTCOME[self.outcome]

    def next_batch(self, size: int) -> tuple[str, ...]:
        """The next ``size`` authorable leaves, in ledger order."""
        return self.authorable[:size]

    def barriers_crossed(self, size: int) -> tuple[str, ...]:
        """Open CI-gated leaves the ``size``-batch steps OVER, in ledger order.

        ``next_batch`` filters gated leaves out, so a batch large enough to span one
        reports nothing about it -- and a checkpoint that can cancel the work behind it
        is exactly the thing that must not be stepped over silently. Task 14's own words
        are "the consensus experiment ... **must NOT be run**. Do not proceed to E3."

        At a batch of 10 this was satisfied by accident, because ten authorable leaves
        happened not to reach past a checkpoint. At 30 it is not, so the rule stops being
        prose and becomes a derivation: a barrier is an open gated leaf with at least one
        offered id after it in ledger order.

        Advisory, not fatal. Ledger order is not execution order -- session 2r's own batch
        (27.2-27.5) legitimately sat after checkpoint A's task 11 and did not depend on
        it. So this names what is crossed and leaves the judgement where it belongs,
        rather than manufacturing a block the ledger cannot justify.
        """
        batch = self.next_batch(size)
        if not batch:
            return ()
        position = {task_id: index for index, task_id in enumerate(self.open_order)}
        last = position.get(batch[-1])
        if last is None:  # pragma: no cover - batch ids come from open_order by construction
            return ()
        return tuple(
            task_id
            for task_id in self.open_order
            if task_id in self.gated_jobs and position[task_id] < last
        )

    def canonical_json(self) -> str:
        """Canonical serialisation for a persisted payload."""
        return json.dumps(self.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------


def _indent_width(line: str) -> int:
    return len(line) - len(line.lstrip())


def _discharge_of(body: tuple[str, ...]) -> str | None:
    for entry in body:
        match = _DISCHARGE_RE.match(entry.strip(_EMPHASIS))
        if match is not None:
            return match.group("job").strip(_EMPHASIS)
    return None


def _last_checked_of(body: tuple[str, ...]) -> str | None:
    """The run a ``[~]``'s discharge job was last read at, or ``None`` (G4)."""
    for entry in body:
        match = _HARVEST_RE.match(entry.strip(_EMPHASIS))
        if match is not None:
            return match.group("run").strip(_EMPHASIS)
    return None


def parse_records(text: str) -> tuple[LedgerRecord, ...]:
    """Every task record in one ``tasks.md``, with leaf status from the id tree.

    A record's body runs until the next record or the first non-blank line indented no
    further than the record itself, matching ``task_claim_truth.parse_task_records``.
    """
    lines = text.splitlines()
    parsed: list[LedgerRecord] = []
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
        frozen_body = tuple(body)
        parsed.append(
            LedgerRecord(
                task_id=match.group("id"),
                mark=match.group("mark"),
                title=match.group("title").strip(),
                body=frozen_body,
                line=index + 1,
                discharge=_discharge_of(frozen_body),
                last_checked=_last_checked_of(frozen_body),
            )
        )
        index = cursor

    identifiers = tuple(record.task_id for record in parsed)
    return tuple(
        record.model_copy(
            update={
                "is_leaf": not any(
                    other.startswith(f"{record.task_id}.") for other in identifiers
                )
            }
        )
        for record in parsed
    )


def extract_paths(body: tuple[str, ...]) -> tuple[str, ...]:
    """Backticked tokens in a record's body that look like repository paths.

    Deliberately permissive about *where* in the body a path appears and strict about
    what shape counts, because the ``Files:`` block wraps across sub-bullets. A trailing
    ``:26`` line reference and a ``::job`` workflow suffix are stripped; a token must
    contain ``/`` and end in a known suffix, or end in ``/`` for a directory.
    """
    found: list[str] = []
    for entry in body:
        for token in _BACKTICKED_RE.findall(entry):
            candidate = token.strip().rstrip(",.;:")
            candidate = candidate.split("::", 1)[0]
            candidate = re.sub(r":\d+(?:-\d+)?$", "", candidate)
            if "/" not in candidate or not _PATH_RE.match(candidate):
                continue
            suffix = Path(candidate).suffix
            named = candidate.endswith("/") or suffix in _PATH_SUFFIXES
            if named and candidate not in found:
                found.append(candidate)
    return tuple(found)


# ---------------------------------------------------------------------------
# Verdict (pure - the seam a test drives)
# ---------------------------------------------------------------------------


def census(
    records: tuple[LedgerRecord, ...],
    *,
    spec: str,
    source: str,
    observations: tuple[DiskObservation, ...] = (),
    read_error: str | None = None,
) -> LedgerCensus:
    """Classify an already-parsed ledger. No filesystem, no network."""
    findings: list[CensusFinding] = []
    if read_error is not None:
        findings.append(
            CensusFinding(
                rule="ledger-unreadable",
                outcome=CensusOutcome.UNAVAILABLE,
                subject=source,
                detail=read_error,
            )
        )

    seen: dict[str, int] = {}
    for record in records:
        first = seen.get(record.task_id)
        if first is not None:
            findings.append(
                CensusFinding(
                    rule="duplicate-id",
                    outcome=CensusOutcome.UNAVAILABLE,
                    subject=record.task_id,
                    detail=(
                        f"task id {record.task_id} appears at line {first} and again at line "
                        f"{record.line}; a count over ids is not a count over records"
                    ),
                )
            )
        else:
            seen[record.task_id] = record.line
        if record.mark.lower() not in {MARK_DONE, MARK_PENDING, MARK_OPEN}:
            findings.append(
                CensusFinding(
                    rule="unknown-mark",
                    outcome=CensusOutcome.UNAVAILABLE,
                    subject=record.name,
                    detail=(
                        f"line {record.line} carries mark {record.mark!r}, which this "
                        f"vocabulary does not define (expected {MARK_OPEN!r}, "
                        f"{MARK_PENDING!r} or {MARK_DONE!r}); the census will not guess"
                    ),
                )
            )

    leaves = tuple(record for record in records if record.is_leaf)
    done = tuple(record for record in leaves if record.is_done)
    pending = tuple(record for record in leaves if record.is_pending)
    still_open = tuple(record for record in leaves if record.is_open)
    authorable = tuple(record.task_id for record in still_open if not record.is_gated)
    gated = tuple(
        f"{record.task_id} -> {record.discharge}" for record in still_open if record.is_gated
    )
    open_order = tuple(record.task_id for record in still_open)
    gated_jobs = {
        record.task_id: record.discharge or "(no discharge declared)"
        for record in still_open
        if record.is_gated
    }
    pending_discharges = tuple(
        f"{record.task_id} -> {record.discharge or '(no discharge declared)'}"
        for record in pending
    )
    unharvested = tuple(
        f"{record.task_id} -> {record.discharge or '(no discharge declared)'}"
        for record in pending
        if record.is_unharvested
    )
    for record in pending:
        if not record.is_unharvested:
            continue
        findings.append(
            CensusFinding(
                rule="unharvested-pending",
                outcome=CensusOutcome.UNAVAILABLE,
                subject=record.name,
                detail=(
                    f"line {record.line} is `[~]` and records no `last-checked:` run for its "
                    f"discharge job ({record.discharge or 'no discharge declared'}). A mark "
                    "whose discharge has silently arrived is indistinguishable, from the "
                    "ledger alone, from one still waiting -- task 26.1 sat dischargeable for "
                    "two sessions while every sweep reported green. Read the newest run that "
                    "names that job, then record it as a `last-checked:` sub-bullet. This is "
                    "NOT satisfied by checking and not writing it down (G4)"
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
    outcome = (
        CensusOutcome.UNAVAILABLE
        if any(item.outcome is CensusOutcome.UNAVAILABLE for item in ordered)
        else CensusOutcome.PASS
    )
    if outcome is CensusOutcome.PASS:
        detail = (
            f"{len(leaves)} leaf task(s): {len(done)} done, {len(pending)} authored "
            f"pending discharge, {len(still_open)} open "
            f"({len(authorable)} authorable, {len(gated)} CI-gated)"
        )
    else:
        detail = next(item.detail for item in ordered if item.outcome is outcome)

    return LedgerCensus(
        spec=spec,
        source=source,
        parents=len(records) - len(leaves),
        leaves=len(leaves),
        done=len(done),
        pending=len(pending),
        open_count=len(still_open),
        authorable=authorable,
        gated=gated,
        open_order=open_order,
        gated_jobs=gated_jobs,
        pending_discharges=pending_discharges,
        unharvested=unharvested,
        observations=observations,
        findings=ordered,
        outcome=outcome,
        detail=detail,
    )


# ---------------------------------------------------------------------------
# I/O
# ---------------------------------------------------------------------------


def _ascii(text: str) -> str:
    """Console-safe rendering. Applied to the human report only, never to the payload."""
    for source, replacement in _ASCII_MAP.items():
        text = text.replace(source, replacement)
    return text.encode("ascii", "replace").decode("ascii")


def _observe_disk(records: tuple[LedgerRecord, ...], *, root: Path) -> tuple[DiskObservation, ...]:
    """Informational only: where the ledger and the tree disagree."""
    strong: list[DiskObservation] = []
    weak: list[DiskObservation] = []
    for record in records:
        if not record.is_leaf:
            continue
        declared_new = {
            match for entry in record.body for match in _DECLARED_NEW_RE.findall(entry)
        }
        for path in extract_paths(record.body):
            exists = (root / path).exists()
            is_new = path in declared_new
            if record.is_open and exists:
                note = (
                    "the task declares it (new), so it should not exist yet"
                    if is_new
                    else "the task may only modify it, so existence alone proves nothing"
                )
                (strong if is_new else weak).append(
                    DiskObservation(
                        kind="prior-art",
                        task_id=record.task_id,
                        path=path,
                        detail=(
                            f"{record.name} is open, but {path} already exists; {note}. "
                            "Disk outranks the ledger -- read the cited criteria first"
                        ),
                    )
                )
            elif (record.is_done or record.is_pending) and not exists:
                strong.append(
                    DiskObservation(
                        kind="absent-artifact",
                        task_id=record.task_id,
                        path=path,
                        detail=(
                            f"{record.name} is marked {record.mark!r}, but {path} does not "
                            "exist; it may be a path the task names in order to reject it"
                        ),
                    )
                )
    return tuple(strong) + tuple(weak)


def evaluate(
    *,
    spec: str = DEFAULT_SPEC,
    root: Path = ROOT,
    check_files: bool = False,
) -> LedgerCensus:
    """Read one spec's ``tasks.md`` and classify it.

    Args:
        spec: Directory name under ``.kiro/specs``.
        root: Tree root the relative paths resolve against.
        check_files: Also report where the ledger and the tree disagree.
    """
    tasks_file = root / SPECS_DIR / spec / TASKS_FILENAME
    source = f"{SPECS_DIR}/{spec}/{TASKS_FILENAME}"
    try:
        text = tasks_file.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        return census(
            (),
            spec=spec,
            source=source,
            read_error=(
                f"{source} could not be read: {error}; absence of a census is not a pass"
            ),
        )
    records = parse_records(text)
    observations = _observe_disk(records, root=root) if check_files else ()
    return census(records, spec=spec, source=source, observations=observations)


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


def format_report(report: LedgerCensus, *, batch: int = DEFAULT_BATCH) -> list[str]:
    """ASCII-only human summary. Every number here is derived, none is transcribed."""
    lines = [
        f"Spec ledger census - {report.spec}",
        f"  source        : {report.source}",
        f"  non-leaf      : {report.parents}   (parents with sub-tasks)",
        f"  leaf tasks    : {report.leaves}",
        f"  done          : {report.done}",
        f"  pending       : {report.pending}   (authored, discharge owed - not a pass)",
        f"  open          : {report.open_count}",
        f"  authorable    : {len(report.authorable)}",
        f"  CI-gated open : {len(report.gated)}",
        f"  unharvested   : {len(report.unharvested)}   (`[~]` with no last-checked: run - G4)",
        f"  status        : {report.outcome.value}  (exit {report.exit_code})",
        f"  reason        : {report.detail}",
    ]
    batched = report.next_batch(batch)
    lines.append(f"  next {batch:<2}      : {' '.join(batched) if batched else '(none)'}")
    for barrier in report.barriers_crossed(batch):
        following = sum(
            1
            for task_id in batched
            if report.open_order.index(task_id) > report.open_order.index(barrier)
        )
        lines.append(
            f"  [!!] barrier    : {barrier} is CI-gated and {following} of the {len(batched)} "
            f"offered id(s) follow it in ledger order -> {report.gated_jobs[barrier]}. "
            "Ledger order is not execution order: confirm the batch does not DEPEND on it."
        )
    for entry in report.gated:
        lines.append(f"  [--] CI-gated : {entry}")
    for entry in report.pending_discharges:
        lines.append(f"  [~~] pending  : {entry}")
    for entry in report.unharvested:
        lines.append(
            f"  [!!] UNHARVESTED: {entry} -- read the newest run naming that job, then "
            "record it as a `last-checked:` sub-bullet (G4)"
        )
    for finding in report.findings:
        lines.append(f"  {_MARKER[finding.outcome]} {finding.rule}: {finding.detail}")
    for observation in report.observations:
        lines.append(f"  [??] {observation.kind}: {observation.detail}")
    if report.outcome is CensusOutcome.UNAVAILABLE:
        lines.append(
            "[??] spec-ledger-census: UNAVAILABLE - the ledger could not be classified. "
            "Absence of proof is not a pass (I-7)."
        )
    else:
        lines.append("[OK] spec-ledger-census: every record classified.")
    return [_ascii(line) for line in lines]


def run(
    *,
    spec: str = DEFAULT_SPEC,
    batch: int = DEFAULT_BATCH,
    as_json: bool = False,
    check: bool = False,
    check_files: bool = False,
    out: Path | None = None,
) -> int:
    """CLI entry point. ``print`` is acceptable here and nowhere else in this module."""
    report = evaluate(spec=spec, check_files=check_files)
    if as_json:
        print(report.canonical_json())
    else:
        for line in format_report(report, batch=batch):
            print(line)
    if out is not None:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(report.canonical_json(), encoding="utf-8")
    if report.outcome is not CensusOutcome.PASS:
        logger.info(
            "spec_ledger_census_non_passing",
            outcome=report.outcome.value,
            findings=len(report.findings),
            spec=report.spec,
        )
    return report.exit_code if check else _EXIT_BY_OUTCOME[CensusOutcome.PASS]


def main(argv: list[str] | None = None) -> int:
    """``python -m scripts.audit.spec_ledger_census [--spec S] [--next N] [--files] ...``."""
    parser = argparse.ArgumentParser(
        prog="python -m scripts.audit.spec_ledger_census",
        description=(
            "Derive a spec's leaf-task counts, its CI-gated set and its next authorable "
            "batch from the ledger itself, so no document has to transcribe them."
        ),
    )
    parser.add_argument("--spec", default=DEFAULT_SPEC, help="Spec directory under .kiro/specs.")
    parser.add_argument(
        "--next", type=int, default=DEFAULT_BATCH, help="Size of the next authorable batch."
    )
    parser.add_argument("--json", action="store_true", help="Emit the canonical JSON report.")
    parser.add_argument(
        "--check", action="store_true", help="Exit 0 pass / 2 unavailable (2 is non-passing)."
    )
    parser.add_argument(
        "--files",
        action="store_true",
        help="Also report where the ledger and the tree disagree (informational).",
    )
    parser.add_argument("--out", type=Path, default=None, help="Persist the canonical report.")
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])
    return run(
        spec=str(args.spec),
        batch=int(args.next),
        as_json=bool(args.json),
        check=bool(args.check),
        check_files=bool(args.files),
        out=args.out,
    )


if __name__ == "__main__":
    sys.exit(main())
