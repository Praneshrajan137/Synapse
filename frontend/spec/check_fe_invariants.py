"""SYNAPSE FE - the FE-INV registry checker (design E2.4 / RC-3, R8.7 + R12.4).

This gate used to prove that a *file exists*::

    for path in implementations + tests:
        if not (ROOT / path).exists():
            errors.append(...)

Existence is not evidence. ``FE-INV-056`` ("Operator Jobs-To-Be-Done reach the
correct terminal outcome") was registered ``status: enforced`` on the strength of
one listed test file whose first statement is
``test.skip(true, "Task_Completion harness ... not wired yet")`` - so the gate was
green while nothing about the invariant had ever been asserted. That is the
Requirement 12 shape in its purest form: *the registry gate was validating the
registry*.

What this module now does instead:

* **Reads executed assertions.** It consumes the Vitest and Playwright JSON
  reporter output and normalises both into one :class:`ExecutedTest` stream, each
  carrying the suite file it came from, its full title, and a collapsed
  ``passed`` / ``failed`` / ``skipped`` status.
* **Requires one for every ``enforced`` invariant.** An invariant is ``attested``
  only when at least one executed, non-skipped assertion is attributable to it -
  by an ``FE-INV-###`` tag in the test's own title, or by the test's file being a
  suite file the registry lists for that invariant. File existence and an
  all-skipped run are both rejected (R8.7).
* **Never turns absence into a pass (I-7).** A missing, unreadable, or
  unparseable reporter file is ``unavailable`` (exit ``2``), never a pass. A
  reporter set in which nothing executed is ``unavailable`` too.
* **Keeps registry hygiene.** The old closed-status / listed-implementation /
  listed-test / files-exist checks are retained, because a registry pointing at
  a deleted file is broken - but existence is now a *necessary* condition, never
  a sufficient one.
* **Decides one verdict per declared console property file** (R2.6-R2.9, R2.12-R2.14,
  R2.16). Independent of the FE-INV clause above: an attestation asks "did SOME
  assertion prove this invariant", a suite verdict asks "did THIS FILE run at all".
  The five files are named in ``fe-invariant-attestation.yaml``'s ``declared_suites``
  block. Six states, one of which is a pass - see :data:`SuiteClassification`. A file
  with no usable entry is reported **AUTHORED BUT NOT EXECUTED**, and a local editor
  or ``getDiagnostics`` probe is recorded as inconclusive rather than as evidence
  (R2.12, R2.13). ``artifacts/test-reports/`` is gitignored and is a CI product, so
  **on a developer box the honest report is all five files authored but not executed**;
  that is the state today, and it is a report rather than a defect.

**What this gate does NOT observe about the declared files.** The run record carries a
per-file fast-check budget attestation under the ``fcBudget`` meta key
(``frontend/src/test/fc-budget.ts::FC_BUDGET_META_KEY``, stamped once per file by
``frontend/src/test/setup.ts``), which would be a second, independent signal that a
file ran with the budget mechanism in force. Nothing here reads it yet: that clause
belongs to R3.9, whose owning task is the budget resolver's, and consuming it needs the
key mirrored into a committed declaration (AD-13) with a test pinning the two spellings
equal - the ``ADVISORY_MARKERS`` precedent. Recorded here so the gap is visible rather
than discovered.

Exit codes, matching ``scripts/audit/registry_gate.py``::

    0  pass          every enforced invariant has an executed, non-skipped assertion
    1  fail          an enforced invariant's assertions skipped, failed, or never ran
    2  unavailable   the reporter evidence could not be read (a SKIP is not a PASS)

``FE-INV-056`` fails until the browser harness lands (design E6, task 11.1). That
failure is the correct state, and it cannot be declared away: the out-of-suite
declaration in ``infrastructure/quality/fe-invariant-attestation.yaml`` rejects any
entry for an invariant that lists a suite file.

Run from the repo root::

    python frontend/spec/check_fe_invariants.py
    python frontend/spec/check_fe_invariants.py --json
    python frontend/spec/check_fe_invariants.py --report frontend/artifacts/test-reports/vitest.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path, PurePosixPath
from typing import Any, Final, Literal

try:
    import yaml
except ModuleNotFoundError as exc:  # pragma: no cover - hard fail in CI
    sys.stderr.write("pyyaml is required: pip install pyyaml\n")
    raise SystemExit(2) from exc  # 2 == EXIT_UNAVAILABLE, defined below

try:
    from pydantic import BaseModel, ConfigDict, ValidationError
except ModuleNotFoundError as exc:  # pragma: no cover - hard fail in CI
    sys.stderr.write("pydantic is required: pip install pydantic\n")
    raise SystemExit(2) from exc  # 2 == EXIT_UNAVAILABLE, defined below

# Exit codes. ``2`` is distinct from ``1`` so a CI log can tell "an enforced
# invariant is not asserted" from "the evidence could not be read". Both are
# non-passing statuses for the step.
EXIT_PASS: Final = 0
EXIT_FAIL: Final = 1
EXIT_UNAVAILABLE: Final = 2

ROOT: Final = Path(__file__).resolve().parents[2]
SPEC: Final = ROOT / "frontend" / "spec" / "fe_invariants.yaml"
DECLARATION: Final = ROOT / "infrastructure" / "quality" / "fe-invariant-attestation.yaml"

#: Reporter output the gate consumes by default. Emitted by
#: ``frontend/vitest.config.ts`` (``outputFile.json``) and
#: ``frontend/playwright.config.ts`` (the ``json`` reporter). CI must run the
#: suites and make both files available to this step; this gate never runs them.
DEFAULT_REPORTS: Final = (
    "frontend/artifacts/test-reports/vitest.json",
    "frontend/artifacts/test-reports/playwright.json",
)

VALID_STATUS: Final = frozenset(
    {"enforced", "scheduled_p1", "scheduled_p2", "scheduled_p3", "scheduled_p4"}
)
ENFORCED: Final = "enforced"

#: The tag form that attributes a test to an invariant, e.g. ``FE-INV-033``.
TAG_PATTERN: Final = re.compile(r"FE-INV-\d{3}")

TestStatus = Literal["passed", "failed", "skipped"]

Classification = Literal[
    "attested",  # >=1 executed, non-skipped, passing assertion (the only passing class)
    "violated",  # attributable assertions ran and at least one failed
    "skipped_only",  # attributable assertions exist in the report, every one skipped
    "not_executed",  # suite files are listed, but no assertion from them was reported
    "out_of_suite",  # no suite file is listed; declared enforced by a named CI job
    "unattributable",  # no suite file is listed and no declared enforcer
    "not_enforced",  # status is scheduled_p*, so no assertion is owed yet
]

#: What the machine-readable run record proves about ONE declared console property
#: file (R2.8, R2.14). Five states, exactly one of which is a pass.
#:
#: The distinction between ``absent`` and ``no_cases`` is the whole point of stating
#: R2.8 against the record rather than against the vitest config: ``absent`` means the
#: record has no entry for the file, ``no_cases`` means it has an entry that reported
#: nothing. A checker that only asked "count >= 1" would see the same answer for both,
#: and the same answer again for a file deleted from the tree.
#:
#: ``partially_skipped`` is the second distinction that cannot be folded away. R2.14
#: reads on **any** test reported ``skipped`` or ``todo`` in a declared file, not only
#: on a file whose every case skipped, so a file with four passes and one ``it.skip``
#: is non-passing. Labelling that file ``skipped_only`` would be a false label and
#: labelling it ``executed`` would be a false pass; it gets its own state (I-7).
SuiteClassification = Literal[
    "executed",  # >=1 case ran, none failed, none skipped (the only passing state)
    "violated",  # cases ran and at least one failed
    "partially_skipped",  # cases ran and passed, and at least one skipped/todo (R2.14)
    "skipped_only",  # every reported case was skipped/todo
    "no_cases",  # the record has an entry for the file and it reported no case
    "absent",  # the record has no entry for the file at all
]

#: Suite states that make the aggregate FAIL: the record was read and it shows the
#: property either contradicted or not run. Distinguished from ``absent``/``no_cases``,
#: which are ``unavailable`` -- the gate observed no evidence either way, which is
#: still non-passing but is a different claim (I-7).
FAILING_SUITE_CLASSES: Final[tuple[str, ...]] = (
    "violated",
    "partially_skipped",
    "skipped_only",
)
UNAVAILABLE_SUITE_CLASSES: Final[tuple[str, ...]] = ("absent", "no_cases")

Verdict = Literal["pass", "fail", "unavailable"]

_EXIT_CODES: Final[dict[str, int]] = {
    "pass": EXIT_PASS,
    "fail": EXIT_FAIL,
    "unavailable": EXIT_UNAVAILABLE,
}

_SYMBOLS: Final[dict[str, str]] = {"pass": "[OK]", "fail": "[XX]", "unavailable": "[??]"}

#: Classifications that fail the gate: an assertion was owed and did not run,
#: skipped, or failed.
FAILING_CLASSES: Final[tuple[Classification, ...]] = (
    "violated",
    "skipped_only",
    "not_executed",
)


# --------------------------------------------------------------------------- #
# Models
# --------------------------------------------------------------------------- #


class ExecutedTest(BaseModel):
    """One test case as a JSON reporter recorded it, normalised across runners."""

    model_config = ConfigDict(frozen=True)

    report: str  # the reporter file this came from
    suite_file: str  # the spec/test file, as the reporter spelled it
    title: str  # full title: ancestor titles joined with the test title
    status: TestStatus
    tags: tuple[str, ...] = ()  # FE-INV-### tags found in the title (or PW tags)
    #: The runner's failure text, verbatim and untruncated by this model. For a
    #: fast-check property this is where the SHRUNK COUNTEREXAMPLE lives, which is
    #: what R2.9 requires a failure to name alongside the file and the property
    #: title. Empty for a passing or skipped case, and empty for Playwright, whose
    #: reporter shape this gate does not mine for messages (no declared console
    #: property suite is a Playwright spec).
    failure_detail: str = ""

    @property
    def executed(self) -> bool:
        """True when the case actually ran. ``skipped`` never counts (I-7)."""
        return self.status != "skipped"


class InvariantAttestation(BaseModel):
    """What the reporter output does - and does not - prove about one invariant."""

    model_config = ConfigDict(frozen=True)

    invariant_id: str
    registry_status: str
    classification: Classification
    suite_files: tuple[str, ...]  # registry-listed tests that a JS runner can execute
    attesting: tuple[str, ...]  # titles of executed, non-skipped, passing assertions
    failed: tuple[str, ...]
    skipped: tuple[str, ...]
    detail: str

    @property
    def attested(self) -> bool:
        """Only ``attested`` is proof. ``out_of_suite`` is a disclosed label."""
        return self.classification == "attested"


class DeclaredSuite(BaseModel):
    """One console property file the run record is required to account for (R2.6)."""

    model_config = ConfigDict(frozen=True)

    path: str
    #: The design property number this file carries. Named ``property_number`` rather
    #: than ``property`` so the field can never be confused with the builtin the
    #: sibling model decorates methods with.
    property_number: int
    title: str
    #: The tsconfig project that type-checks this file. Carried so R2.15's reporting
    #: obligation has a subject: while that project is red, this file is described as
    #: authored but NOT type-checked.
    type_check_project: str


class SuiteExecution(BaseModel):
    """What the run record proves about one declared console property file.

    The states R2.8 needs kept apart, and why ``absent`` cannot be folded into
    ``no_cases``: a file that matches no ``include`` pattern, or that throws while
    being collected, produces **no entry in the record at all**. That is a different
    fact from an entry whose case count is zero, and only the second is visible to a
    check that asks "is the count >= 1".
    """

    model_config = ConfigDict(frozen=True)

    path: str
    property_number: int
    title: str
    type_check_project: str
    classification: SuiteClassification
    executed: int  # cases that ran (passed or failed)
    passed: int
    failed: int
    skipped: int
    #: Titles of the cases the record reported as ``skipped``/``pending``/``todo``.
    #: Carried rather than counted because R2.14 obliges the gate to NAME each skipped
    #: test: a count tells a reader that something did not run and not which thing.
    skipped_titles: tuple[str, ...] = ()
    #: Failure text for the failing cases, verbatim. For a fast-check property this
    #: carries the shrunk counterexample (R2.9).
    counterexamples: tuple[str, ...]
    #: Titles of the failing cases, in the same order as ``counterexamples`` when every
    #: failure carried a message. R2.9 wants the property title alongside the minimal
    #: failing input, and the runner's message alone does not carry it.
    failing_titles: tuple[str, ...] = ()
    detail: str

    @property
    def attested(self) -> bool:
        """Only ``executed`` is evidence. Every other state is non-passing (I-7)."""
        return self.classification == "executed"


class OutOfSuiteEntry(BaseModel):
    """One declared out-of-suite enforcer, with the condition that retires it."""

    model_config = ConfigDict(frozen=True)

    invariant_id: str
    workflow: str
    job: str
    rationale: str
    dated: date
    removal_condition: str


class AttestationDeclaration(BaseModel):
    """The pinned configuration this gate derives its vocabulary from (AD-13)."""

    model_config = ConfigDict(frozen=True)

    suite_extensions: tuple[str, ...]
    out_of_suite: tuple[OutOfSuiteEntry, ...]
    #: The five console property files the run record must account for. Empty is a
    #: legal declaration (the clause simply reports nothing), because an absent
    #: block must not synthesise a pass for files nobody declared.
    declared_suites: tuple[DeclaredSuite, ...] = ()

    def entry_for(self, invariant_id: str) -> OutOfSuiteEntry | None:
        for entry in self.out_of_suite:
            if entry.invariant_id == invariant_id:
                return entry
        return None


class FeInvariantVerdict(BaseModel):
    """The gate's verdict over one (registry, declaration, reporter output) triple."""

    model_config = ConfigDict(frozen=True)

    reports_read: tuple[str, ...]
    reports_unavailable: tuple[str, ...]  # "<path>: <reason>"
    executed_count: int
    skipped_count: int
    attestations: tuple[InvariantAttestation, ...]
    #: One verdict per declared console property file (R2.6). Independent of
    #: ``attestations``: an FE-INV attestation asks "did SOME assertion prove this
    #: invariant", a suite verdict asks "did THIS FILE run at all".
    declared_suites: tuple[SuiteExecution, ...]
    hygiene_errors: tuple[str, ...]
    verdict: Verdict
    reason: str

    @property
    def exit_code(self) -> int:
        """The process exit status this verdict mandates (0 / 1 / 2)."""
        return _EXIT_CODES[self.verdict]

    @property
    def passing(self) -> bool:
        """True only for ``pass``. ``unavailable`` is not a pass (I-7)."""
        return self.verdict == "pass"

    def by_class(self, classification: Classification) -> tuple[InvariantAttestation, ...]:
        return tuple(a for a in self.attestations if a.classification == classification)


# --------------------------------------------------------------------------- #
# Reporter parsing
# --------------------------------------------------------------------------- #


class ReportFormatError(ValueError):
    """The file parsed as JSON but is not a reporter output this gate knows."""


def _as_mapping(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_sequence(value: object) -> list[Any]:
    return value if isinstance(value, list) else []


def _int_field(item: dict[str, Any], key: str, *, context: str) -> int:
    """Read a required integer field, naming the key and the block when it is not one.

    Not defaulted. A declared suite whose ``property`` silently became ``0`` would
    produce a verdict that looks complete over a declaration that is not, which is the
    exact class of defect this gate exists to remove. The raise is mapped to exit ``2``
    (``unavailable``) by ``run``, never to a pass.
    """
    raw = item.get(key)
    try:
        return int(str(raw).strip())
    except (TypeError, ValueError) as exc:
        where = item.get("path", "<no path>")
        message = f"{context}: entry {where!r} has non-integer {key}={raw!r}"
        raise ReportFormatError(message) from exc


def _text(value: object) -> str:
    return value if isinstance(value, str) else ""


def tags_in(title: str) -> tuple[str, ...]:
    """Every distinct ``FE-INV-###`` tag in ``title``, in first-seen order."""
    return tuple(dict.fromkeys(TAG_PATTERN.findall(title)))


def _vitest_status(raw: str) -> TestStatus:
    """Map a Jest-format assertion status onto the three states that matter.

    Vitest emits ``passed`` / ``failed`` / ``skipped`` / ``pending`` / ``todo``.
    Everything that is not a real execution collapses to ``skipped``: a ``todo``
    proves exactly as much as a ``skip`` does, which is nothing (I-7).
    """
    if raw == "passed":
        return "passed"
    if raw == "failed":
        return "failed"
    return "skipped"


def parse_vitest(payload: dict[str, Any], source: str) -> tuple[ExecutedTest, ...]:
    """Normalise Vitest's (Jest-shaped) JSON reporter output."""
    executed: list[ExecutedTest] = []
    for raw_file in _as_sequence(payload.get("testResults")):
        file_result = _as_mapping(raw_file)
        suite_file = _text(file_result.get("name"))
        for raw_case in _as_sequence(file_result.get("assertionResults")):
            case = _as_mapping(raw_case)
            ancestors = [_text(a) for a in _as_sequence(case.get("ancestorTitles"))]
            title = _text(case.get("fullName")) or " > ".join(
                [*[a for a in ancestors if a], _text(case.get("title"))]
            )
            messages = [_text(m) for m in _as_sequence(case.get("failureMessages"))]
            executed.append(
                ExecutedTest(
                    report=source,
                    suite_file=suite_file,
                    title=title,
                    status=_vitest_status(_text(case.get("status"))),
                    tags=tags_in(title),
                    failure_detail="\n".join(m for m in messages if m),
                )
            )
    return tuple(executed)


def _collapse_playwright_spec(spec: dict[str, Any]) -> TestStatus:
    """Collapse a Playwright spec's tests/retries into one status.

    Mirrors ``frontend/spec/effectiveness/real-stack-fidelity.ts::collapseSpec`` so
    the two consumers of the same reporter output agree on what happened. A
    runtime ``test.skip(true, ...)`` - the construct that made ``FE-INV-056``
    vacuous - lands here as ``skipped``.
    """
    any_failed = False
    any_passed = False
    for raw_test in _as_sequence(spec.get("tests")):
        test = _as_mapping(raw_test)
        status = _text(test.get("status"))
        if status in {"unexpected", "flaky"}:
            any_failed = True
        if status == "expected":
            any_passed = True
        for raw_result in _as_sequence(test.get("results")):
            result_status = _text(_as_mapping(raw_result).get("status"))
            if result_status in {"failed", "timedOut", "interrupted"}:
                any_failed = True
            if result_status == "passed":
                any_passed = True
    if any_failed:
        return "failed"
    return "passed" if any_passed else "skipped"


def _walk_playwright(
    node: dict[str, Any],
    inherited_file: str,
    source: str,
    inherited_titles: tuple[str, ...],
    out: list[ExecutedTest],
) -> None:
    suite_file = _text(node.get("file")) or inherited_file
    suite_title = _text(node.get("title"))
    # The outermost suite's title is the spec file path; keep it out of the
    # composed test title so a tag search reads titles, not paths.
    titles = inherited_titles
    if suite_title and suite_title != suite_file:
        titles = (*inherited_titles, suite_title)

    for raw_spec in _as_sequence(node.get("specs")):
        spec = _as_mapping(raw_spec)
        spec_file = _text(spec.get("file")) or suite_file
        spec_title = _text(spec.get("title"))
        title = " > ".join([*titles, spec_title]) if titles else spec_title
        declared = tuple(
            _text(tag)
            for tag in _as_sequence(spec.get("tags"))
            if TAG_PATTERN.fullmatch(_text(tag))
        )
        out.append(
            ExecutedTest(
                report=source,
                suite_file=spec_file,
                title=title,
                status=_collapse_playwright_spec(spec),
                tags=tuple(dict.fromkeys((*tags_in(title), *declared))),
            )
        )

    for raw_child in _as_sequence(node.get("suites")):
        _walk_playwright(_as_mapping(raw_child), suite_file, source, titles, out)


def parse_playwright(payload: dict[str, Any], source: str) -> tuple[ExecutedTest, ...]:
    """Normalise Playwright's JSON reporter output (nested suites -> specs)."""
    out: list[ExecutedTest] = []
    _walk_playwright(payload, "", source, (), out)
    return tuple(out)


def parse_report(payload: object, source: str) -> tuple[ExecutedTest, ...]:
    """Dispatch on reporter shape. Unknown shapes raise rather than return empty.

    Returning an empty tuple for an unrecognised file would let a typo in a CI
    path read as "nothing to attest" - the exact absence-as-proof move this gate
    exists to stop.
    """
    mapping = _as_mapping(payload)
    if "testResults" in mapping:
        return parse_vitest(mapping, source)
    if "suites" in mapping:
        return parse_playwright(mapping, source)
    raise ReportFormatError(
        "not a Vitest ('testResults') or Playwright ('suites') JSON reporter output"
    )


def _walk_playwright_files(node: dict[str, Any], out: list[str]) -> None:
    """Collect every ``file`` a Playwright suite tree names, at any depth."""
    listed = _text(node.get("file"))
    if listed:
        out.append(listed)
    for raw_spec in _as_sequence(node.get("specs")):
        spec_file = _text(_as_mapping(raw_spec).get("file"))
        if spec_file:
            out.append(spec_file)
    for raw_child in _as_sequence(node.get("suites")):
        _walk_playwright_files(_as_mapping(raw_child), out)


def recorded_suite_files(payload: object) -> tuple[str, ...]:
    """Every suite file the record LISTED, whether or not it reported a case.

    Read as its own signal rather than inferred from :func:`parse_report`'s cases,
    because the two are not the same fact. A Vitest ``testResults`` block whose
    ``assertionResults`` array is empty yields **no case**, so from the cases alone a
    file the runner collected and reported nothing for is indistinguishable from a file
    the record never mentioned. R2.8 is stated on exactly that distinction, and
    ``evaluate_declared_suites``' ``no_cases`` state is unreachable without this.

    An unrecognised shape yields ``()`` rather than raising: ``parse_report`` already
    raises on the same payload and routes it to ``unavailable``, so a second raise here
    would only duplicate the message.
    """
    mapping = _as_mapping(payload)
    if "testResults" in mapping:
        return tuple(
            name
            for name in (
                _text(_as_mapping(raw).get("name"))
                for raw in _as_sequence(mapping.get("testResults"))
            )
            if name
        )
    if "suites" in mapping:
        out: list[str] = []
        _walk_playwright_files(mapping, out)
        return tuple(dict.fromkeys(out))
    return ()


def load_reports(
    paths: tuple[str, ...],
) -> tuple[tuple[ExecutedTest, ...], tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    """Read every reporter file.

    Returns ``(tests, recorded_files, read, unavailable-with-reason)``. ``recorded_files``
    is carried alongside the cases because a listed-but-caseless file is a distinct fact
    from an unlisted one (R2.8); see :func:`recorded_suite_files`.
    """
    tests: list[ExecutedTest] = []
    recorded: list[str] = []
    read: list[str] = []
    unavailable: list[str] = []
    for rel in paths:
        path = ROOT / rel
        if not path.is_file():
            unavailable.append(f"{rel}: no reporter output at this path")
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            unavailable.append(f"{rel}: unreadable reporter output ({exc})")
            continue
        try:
            tests.extend(parse_report(payload, rel))
        except ReportFormatError as exc:
            unavailable.append(f"{rel}: {exc}")
            continue
        recorded.extend(recorded_suite_files(payload))
        read.append(rel)
    return tuple(tests), tuple(dict.fromkeys(recorded)), tuple(read), tuple(unavailable)


# --------------------------------------------------------------------------- #
# Attribution
# --------------------------------------------------------------------------- #


def _segments(path: str) -> tuple[str, ...]:
    return tuple(p for p in PurePosixPath(path.replace("\\", "/")).parts if p not in {".", "/"})


def paths_match(registry_path: str, report_path: str) -> bool:
    """True when two spellings of a path denote the same file.

    Vitest reports an absolute path; Playwright reports one relative to its
    ``rootDir`` (``frontend/``); the registry lists repo-relative paths. Rather
    than guess a base for each runner, compare the shared trailing segments. At
    least two segments must match, so a bare basename can never collide two
    different suites onto one invariant.
    """
    left, right = _segments(registry_path), _segments(report_path)
    shared = min(len(left), len(right))
    if shared < 2:
        return False
    return left[-shared:] == right[-shared:]


def is_suite_file(path: str, extensions: tuple[str, ...]) -> bool:
    """True for a file a JS test runner can execute (and therefore report)."""
    return any(path.endswith(ext) for ext in extensions)


def attribute(
    invariant_id: str,
    suite_files: tuple[str, ...],
    tests: tuple[ExecutedTest, ...],
) -> tuple[ExecutedTest, ...]:
    """Every reported test attributable to ``invariant_id``.

    Two attribution routes, both required:

    * the test's own title carries the ``FE-INV-###`` tag (design E2.4's stated
      mechanism - it survives a test moving between files); or
    * the test came from a suite file the registry lists for that invariant.

    A tag inside a *comment* is invisible here, which is correct: a comment is
    not an assertion. The file route is what keeps the many invariants whose
    tests are tagged only in a header comment attributable.
    """
    matched: list[ExecutedTest] = []
    for test in tests:
        if invariant_id in test.tags:
            matched.append(test)
            continue
        if any(paths_match(listed, test.suite_file) for listed in suite_files):
            matched.append(test)
    return tuple(matched)


def classify(
    invariant_id: str,
    registry_status: str,
    listed_tests: tuple[str, ...],
    tests: tuple[ExecutedTest, ...],
    declaration: AttestationDeclaration,
) -> InvariantAttestation:
    """Derive one invariant's attestation from the reporter output."""
    suite_files = tuple(
        path for path in listed_tests if is_suite_file(path, declaration.suite_extensions)
    )
    attributed = attribute(invariant_id, suite_files, tests)
    attesting = tuple(t.title for t in attributed if t.status == "passed")
    failed = tuple(t.title for t in attributed if t.status == "failed")
    skipped = tuple(t.title for t in attributed if t.status == "skipped")

    classification: Classification
    if registry_status != ENFORCED:
        classification = "not_enforced"
        detail = f"status {registry_status} owes no assertion yet"
    elif attesting:
        classification = "attested"
        detail = f"{len(attesting)} executed, non-skipped assertion(s); first: {attesting[0]}"
    elif failed:
        classification = "violated"
        detail = f"{len(failed)} attributable assertion(s) ran and FAILED: {failed[0]}"
    elif skipped:
        classification = "skipped_only"
        detail = (
            f"{len(skipped)} attributable assertion(s) reported, every one skipped - "
            "an all-skipped run is not a pass (I-7)"
        )
    elif suite_files:
        classification = "not_executed"
        detail = (
            "no assertion was reported from "
            f"{', '.join(suite_files)} - the file existing is not the assertion running"
        )
    else:
        entry = declaration.entry_for(invariant_id)
        if entry is not None:
            classification = "out_of_suite"
            detail = (
                f"no suite file listed; declared enforced by {entry.workflow}::{entry.job} "
                f"(dated {entry.dated.isoformat()})"
            )
        else:
            classification = "unattributable"
            detail = (
                "enforced, but no listed test is a suite file a JS runner can execute "
                "and no out-of-suite enforcer is declared - nothing observes this invariant"
            )

    return InvariantAttestation(
        invariant_id=invariant_id,
        registry_status=registry_status,
        classification=classification,
        suite_files=suite_files,
        attesting=attesting,
        failed=failed,
        skipped=skipped,
        detail=detail,
    )


# --------------------------------------------------------------------------- #
# Registry + declaration loading
# --------------------------------------------------------------------------- #


def registry_hygiene(invariants: tuple[dict[str, Any], ...]) -> tuple[str, ...]:
    """The pre-existing structural checks, kept as *necessary* conditions.

    A registry that points at a deleted file is broken however well its tests
    run, so these stay. What changed is that passing them is no longer
    sufficient for an ``enforced`` entry (R8.7).
    """
    errors: list[str] = []
    for inv in invariants:
        inv_id = _text(inv.get("id")) or "<missing-id>"
        if inv.get("status") not in VALID_STATUS:
            errors.append(f"{inv_id}: invalid status {inv.get('status')!r}")
        implementations = [_text(p) for p in _as_sequence(inv.get("implementations"))]
        tests = [_text(p) for p in _as_sequence(inv.get("tests"))]
        if not implementations:
            errors.append(f"{inv_id}: no implementations listed")
        if not tests:
            errors.append(f"{inv_id}: no tests listed")
        for path in [*implementations, *tests]:
            if not (ROOT / path).exists():
                errors.append(f"{inv_id}: missing file {path}")
    return tuple(errors)


def declaration_hygiene(
    declaration: AttestationDeclaration,
    invariants: tuple[dict[str, Any], ...],
    suite_extensions: tuple[str, ...],
) -> tuple[str, ...]:
    """Validate the out-of-suite declaration before it excuses anything (R12.5).

    An entry must (a) name a known invariant, (b) name a workflow file that
    exists and defines the job it names, and (c) not shadow an invariant that
    lists a suite file. Rule (c) is what makes "allowlist ``FE-INV-056`` away"
    mechanically impossible: it lists a Playwright spec, so it is observable and
    can only be attested by an assertion that ran.
    """
    errors: list[str] = []
    known = {_text(inv.get("id")): inv for inv in invariants}
    for entry in declaration.out_of_suite:
        inv = known.get(entry.invariant_id)
        if inv is None:
            errors.append(
                f"declaration: {entry.invariant_id} is not registered in fe_invariants.yaml"
            )
            continue
        listed = [_text(p) for p in _as_sequence(inv.get("tests"))]
        shadowed = [path for path in listed if is_suite_file(path, suite_extensions)]
        if shadowed:
            errors.append(
                f"declaration: {entry.invariant_id} lists executable suite file(s) "
                f"{', '.join(shadowed)}, so it must be proven by an executed assertion "
                "and cannot be declared out-of-suite"
            )
        workflow = ROOT / entry.workflow
        if not workflow.is_file():
            errors.append(
                f"declaration: {entry.invariant_id} names workflow {entry.workflow}, "
                "which does not exist"
            )
            continue
        try:
            parsed = yaml.safe_load(workflow.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError) as exc:
            errors.append(
                f"declaration: {entry.invariant_id} names workflow {entry.workflow}, "
                f"which could not be parsed ({exc})"
            )
            continue
        jobs = _as_mapping(_as_mapping(parsed).get("jobs"))
        if entry.job not in jobs:
            errors.append(
                f"declaration: {entry.invariant_id} names job {entry.job} in "
                f"{entry.workflow}, which defines no such job"
            )
    return tuple(errors)


def load_invariants(path: Path) -> tuple[dict[str, Any], ...]:
    """Read the FE-INV registry. ``encoding='utf-8'`` per E-S13-07."""
    data = _as_mapping(yaml.safe_load(path.read_text(encoding="utf-8")))
    return tuple(_as_mapping(inv) for inv in _as_sequence(data.get("invariants")))


def load_declaration(path: Path) -> AttestationDeclaration:
    """Read the pinned attestation configuration. ``encoding='utf-8'`` (E-S13-07)."""
    data = _as_mapping(yaml.safe_load(path.read_text(encoding="utf-8")))
    extensions = tuple(_text(ext) for ext in _as_sequence(data.get("suite_extensions")))
    entries: list[OutOfSuiteEntry] = []
    for raw in _as_sequence(data.get("out_of_suite")):
        item = _as_mapping(raw)
        entries.append(
            OutOfSuiteEntry(
                invariant_id=_text(item.get("id")),
                workflow=_text(item.get("workflow")),
                job=_text(item.get("job")),
                rationale=_text(item.get("rationale")).strip(),
                dated=date.fromisoformat(_text(item.get("dated"))),
                removal_condition=_text(item.get("removal_condition")).strip(),
            )
        )
    suites: list[DeclaredSuite] = []
    for raw in _as_sequence(data.get("declared_suites")):
        item = _as_mapping(raw)
        # Every field is required and none is defaulted. A declared suite whose
        # `property` or `type_check_project` were allowed to default would let a
        # malformed declaration produce a verdict that looks complete, which is the
        # class of defect this whole block exists to remove: Pydantic raises here and
        # the raise becomes exit 2 (`unavailable`), never a pass.
        suites.append(
            DeclaredSuite(
                path=_text(item.get("path")),
                property_number=_int_field(item, "property", context="declared_suites"),
                title=_text(item.get("title")).strip(),
                type_check_project=_text(item.get("type_check_project")),
            )
        )
    return AttestationDeclaration(
        suite_extensions=extensions,
        out_of_suite=tuple(entries),
        declared_suites=tuple(suites),
    )


# --------------------------------------------------------------------------- #
# Declared console property suites: one verdict per file
# --------------------------------------------------------------------------- #


def _first_lines(text: str, *, limit: int = 6) -> str:
    """The first ``limit`` non-empty lines of ``text``, joined for a report.

    Failure text is truncated for DISPLAY only; ``SuiteExecution.counterexamples``
    keeps the runner's message verbatim so ``--json`` consumers see all of it. A
    shrunk counterexample is usually on the first line or two of a fast-check
    failure, and a gate that printed a full stack per property would bury it.
    """
    lines = [line for line in text.splitlines() if line.strip()]
    head = lines[:limit]
    if len(lines) > limit:
        head.append(f"... ({len(lines) - limit} more line(s); use --json for the full text)")
    return "\n      ".join(head)


#: What a failing case carries when the runner reported no message for it. The shrunk
#: counterexample lives ONLY in that message, so its absence is stated rather than
#: elided: an empty string in the report would read as "no counterexample", which is a
#: different and stronger claim than "the record did not carry one" (I-7).
NO_FAILURE_MESSAGE: Final = (
    "the run record carried no failure message for this case, so the minimal failing "
    "input is unavailable"
)


def evaluate_declared_suites(
    declared: tuple[DeclaredSuite, ...],
    tests: tuple[ExecutedTest, ...],
    *,
    recorded_files: tuple[str, ...] = (),
) -> tuple[SuiteExecution, ...]:
    """Judge each declared console property file against the run record. Pure.

    ``paths_match`` is reused rather than reimplemented, because the reporter spells
    a suite file however the runner's working directory made it spell it -- absolute
    on one runner, `frontend/`-relative on another -- and the registry clause already
    solved that comparison.

    ``recorded_files`` is the set of suite files the record LISTED, from
    :func:`recorded_suite_files`. It is a separate input because it cannot be derived
    from ``tests``: a record block with an empty case list yields no case, so without
    the listing a file the runner collected and reported nothing for is
    indistinguishable from a file the record never mentioned. Keeping ``no_cases``
    apart from ``absent`` is R2.8's whole subject, and before this input existed the
    ``no_cases`` branch was unreachable. It defaults to ``()``, which resolves every
    caseless declaration to ``absent`` -- the weaker, safer claim.

    The non-passing states are kept apart deliberately (R2.8, R2.14):

    * ``absent`` -- no entry at all. What a collection-time throw produces, and the
      state that let Property 36 read as fine while never having run.
    * ``no_cases`` -- listed, and reported nothing.
    * ``skipped_only`` -- every reported case skipped or todo.
    * ``partially_skipped`` -- ran, passed, and skipped at least one case. R2.14 reads
      on ANY skipped or todo test, not only on a wholly skipped file.
    * ``violated`` -- ran and at least one case failed.
    """
    verdicts: list[SuiteExecution] = []
    for suite in declared:
        cases = tuple(test for test in tests if paths_match(suite.path, test.suite_file))
        passed = tuple(c for c in cases if c.status == "passed")
        failed = tuple(c for c in cases if c.status == "failed")
        skipped = tuple(c for c in cases if c.status == "skipped")
        executed = len(passed) + len(failed)
        listed = any(paths_match(suite.path, recorded) for recorded in recorded_files)

        classification: SuiteClassification
        if not cases and listed:
            # The runner SAW the file and produced nothing: a different defect from
            # never looking at it, and a different repair.
            classification = "no_cases"
            detail = (
                f"the run record lists this file and reports no case at all, so Property "
                f"{suite.property_number} is AUTHORED BUT NOT EXECUTED: the runner "
                "collected it and produced nothing. A local getDiagnostics or editor probe "
                "is inconclusive here, not evidence (R2.13)"
            )
        elif not cases:
            classification = "absent"
            detail = (
                f"no entry in any run record for this file, so Property "
                f"{suite.property_number} is "
                "AUTHORED BUT NOT EXECUTED. Absence is not a zero count: a file that matches "
                "no include pattern, or that throws during collection, produces no entry at "
                "all. A local getDiagnostics or editor probe is inconclusive here, not "
                "evidence (R2.13)"
            )
        elif failed:
            classification = "violated"
            detail = (
                f"{len(failed)} of {len(cases)} case(s) FAILED: "
                + "; ".join(c.title for c in failed)
                + ". Repair the subject or the assertion; weakening the generator to stop "
                "the counterexample arising is forbidden (R2.10)"
            )
        elif executed == 0:
            classification = "skipped_only"
            detail = (
                f"all {len(skipped)} reported case(s) skipped or todo, so nothing was "
                "proven; a skip is not a pass (I-7): " + "; ".join(c.title for c in skipped)
            )
        elif skipped:
            # R2.14 is stated on ANY skipped or todo test in a declared file, not only on
            # a file whose every case skipped. A file that proves four of its five
            # obligations has not proven the fifth, and the count alone would not say
            # which one, so each skipped case is named.
            classification = "partially_skipped"
            detail = (
                f"{len(passed)} case(s) executed and passed, and {len(skipped)} case(s) "
                "skipped or todo. A skipped assertion is never a pass (I-7, R2.14): "
                + "; ".join(c.title for c in skipped)
            )
        else:
            classification = "executed"
            detail = f"all {len(passed)} reported case(s) executed and passed"

        verdicts.append(
            SuiteExecution(
                path=suite.path,
                property_number=suite.property_number,
                title=suite.title,
                type_check_project=suite.type_check_project,
                classification=classification,
                executed=executed,
                passed=len(passed),
                failed=len(failed),
                skipped=len(skipped),
                skipped_titles=tuple(c.title for c in skipped),
                # One entry per failing case, positionally paired with
                # ``failing_titles``, so R2.9's triple -- file, property title, minimal
                # failing input -- is reconstructible from the verdict alone. Dropping
                # message-less failures would silently break that pairing.
                counterexamples=tuple(c.failure_detail or NO_FAILURE_MESSAGE for c in failed),
                failing_titles=tuple(c.title for c in failed),
                detail=detail,
            )
        )
    return tuple(verdicts)


# --------------------------------------------------------------------------- #
# Verdict
# --------------------------------------------------------------------------- #


def evaluate_reports(
    invariants: tuple[dict[str, Any], ...],
    declaration: AttestationDeclaration,
    tests: tuple[ExecutedTest, ...],
    reports_read: tuple[str, ...],
    reports_unavailable: tuple[str, ...],
    hygiene_errors: tuple[str, ...],
    *,
    recorded_files: tuple[str, ...] = (),
) -> FeInvariantVerdict:
    """Derive the verdict. Pure: no file is read and no suite is run here.

    Precedence - first match wins:

    1. no reporter output could be read       -> ``unavailable`` (R8.7, I-7)
    2. the registry is empty                  -> ``fail``
    3. a registry/declaration hygiene defect  -> ``fail``
    4. nothing executed in any report         -> ``unavailable`` (all-skipped run)
    5. an enforced invariant is violated,
       skipped-only, or never executed        -> ``fail``, naming each
    6. a declared console property file ran
       and failed, or skipped any case        -> ``fail``, naming each (R2.6, R2.14)
    7. an enforced invariant is
       unattributable                         -> ``unavailable``, naming each
    8. a declared console property file has
       no usable entry in the run record      -> ``unavailable``, naming each (R2.8)
    9. otherwise                              -> ``pass``

    Rules 4, 7 and 8 are ``unavailable`` rather than ``fail`` because the gate did
    not observe a broken invariant, it observed *no evidence either way*. Both
    exit non-zero: absence of proof is never a pass. Finally, a ``pass`` reached
    while any declared reporter output was missing is downgraded to
    ``unavailable`` - a partial read must not read as a clean pass.

    Why 6 outranks 7, and 8 sits below both. A file that RAN and failed is a
    stronger, more actionable fact than an invariant nobody could attribute, so it
    is reported first. A file with no record entry is reported last among the
    non-passing states because it is the weakest claim available -- "nothing was
    observed" -- and it must not mask a real failure that was observed elsewhere.
    """
    attestations = tuple(
        classify(
            _text(inv.get("id")) or "<missing-id>",
            _text(inv.get("status")),
            tuple(_text(p) for p in _as_sequence(inv.get("tests"))),
            tests,
            declaration,
        )
        for inv in invariants
    )
    suites = evaluate_declared_suites(
        declaration.declared_suites, tests, recorded_files=recorded_files
    )
    executed = tuple(t for t in tests if t.executed)
    skipped = tuple(t for t in tests if not t.executed)
    failing = tuple(a for a in attestations if a.classification in FAILING_CLASSES)
    unattributable = tuple(a for a in attestations if a.classification == "unattributable")
    enforced = tuple(a for a in attestations if a.registry_status == ENFORCED)
    attested = tuple(a for a in enforced if a.attested)
    failing_suites = tuple(s for s in suites if s.classification in FAILING_SUITE_CLASSES)
    unavailable_suites = tuple(s for s in suites if s.classification in UNAVAILABLE_SUITE_CLASSES)

    verdict: Verdict
    if not reports_read:
        verdict = "unavailable"
        reason = (
            "no reporter output could be read, so no assertion could be observed: "
            + "; ".join(reports_unavailable)
        )
    elif not invariants:
        verdict = "fail"
        reason = "no invariants found in fe_invariants.yaml"
    elif hygiene_errors:
        verdict = "fail"
        reason = f"{len(hygiene_errors)} registry/declaration defect(s)"
    elif not executed:
        verdict = "unavailable"
        reason = (
            f"all {len(skipped)} reported test(s) skipped across {len(reports_read)} report(s); "
            "an all-skipped run proves nothing (I-7)"
        )
    elif failing:
        verdict = "fail"
        named = ", ".join(f"{a.invariant_id}={a.classification}" for a in failing)
        reason = (
            f"{len(failing)} enforced invariant(s) have no executed, non-skipped assertion: {named}"
        )
    elif failing_suites:
        verdict = "fail"
        named = ", ".join(
            f"Property {s.property_number}={s.classification}" for s in failing_suites
        )
        reason = (
            f"{len(failing_suites)} declared console property file(s) ran without proving "
            f"anything: {named}"
        )
    elif unattributable:
        verdict = "unavailable"
        reason = f"{len(unattributable)} enforced invariant(s) are unobservable: " + ", ".join(
            a.invariant_id for a in unattributable
        )
    elif unavailable_suites:
        verdict = "unavailable"
        reason = (
            f"{len(unavailable_suites)} declared console property file(s) have no usable run "
            "record and are AUTHORED BUT NOT EXECUTED: "
            + ", ".join(
                f"Property {s.property_number}={s.classification}" for s in unavailable_suites
            )
        )
    else:
        verdict = "pass"
        reason = (
            f"{len(attested)} of {len(enforced)} enforced invariant(s) attested by an "
            f"executed, non-skipped assertion; "
            f"{len(suites)} declared console property file(s) executed; "
            f"{len(executed)} test(s) executed, {len(skipped)} skipped"
        )

    if reports_unavailable and verdict == "pass":
        # Every enforced invariant was attested by the reports that *were* read,
        # but a declared report was missing. Do not upgrade a partial read to a
        # clean pass.
        verdict = "unavailable"
        reason = (
            f"{len(reports_unavailable)} declared reporter output(s) unavailable: "
            + "; ".join(reports_unavailable)
        )

    return FeInvariantVerdict(
        reports_read=reports_read,
        reports_unavailable=reports_unavailable,
        executed_count=len(executed),
        skipped_count=len(skipped),
        attestations=attestations,
        declared_suites=suites,
        hygiene_errors=hygiene_errors,
        verdict=verdict,
        reason=reason,
    )


def evaluate(reports: tuple[str, ...]) -> FeInvariantVerdict:
    """Read the registry, the declaration, and the reporter output; then judge."""
    invariants = load_invariants(SPEC)
    declaration = load_declaration(DECLARATION)
    tests, recorded, read, unavailable = load_reports(reports)
    hygiene = (
        *registry_hygiene(invariants),
        *declaration_hygiene(declaration, invariants, declaration.suite_extensions),
    )
    return evaluate_reports(
        invariants,
        declaration,
        tests,
        read,
        unavailable,
        hygiene,
        recorded_files=recorded,
    )


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def _print_group(heading: str, symbol: str, items: tuple[InvariantAttestation, ...]) -> None:
    if not items:
        return
    print()
    print(heading)
    for item in items:
        print(f"  {symbol} {item.invariant_id} {item.detail}")


def _print_declared_suites(suites: tuple[SuiteExecution, ...]) -> None:
    """Print one line per declared console property file, plus any counterexample.

    Always printed, including when every file executed. This is the R2.12 surface: a
    reader must be able to see which properties are evidence and which are only
    authored, without inferring it from the absence of a complaint.
    """
    if not suites:
        return
    print()
    print(f"DECLARED CONSOLE PROPERTY FILES -- {len(suites)}:")
    for suite in suites:
        symbol = "[OK]" if suite.attested else ("[XX]" if suite.failed else "[??]")
        print(f"  {symbol} Property {suite.property_number} ({suite.classification}) {suite.path}")
        print(f"       {suite.title}")
        print(f"       {suite.detail}")
        # R2.9's triple, printed as a triple: the file is the line above, the property
        # title is the failing case's own title, and the minimal failing input is inside
        # the runner's message. `failing_titles` and `counterexamples` are positionally
        # paired by `evaluate_declared_suites`, so zip is exact rather than best-effort.
        for title, counterexample in zip(suite.failing_titles, suite.counterexamples, strict=True):
            print(f"       counterexample in {title!r}:")
            print(f"      {_first_lines(counterexample)}")
        for title in suite.skipped_titles:
            print(f"       skipped or todo (never a pass, I-7): {title}")


def run(reports: tuple[str, ...], *, as_json: bool = False) -> int:
    """Evaluate and report. Returns ``0`` / ``1`` / ``2``.

    A registry or declaration that cannot be read or validated is ``unavailable``
    (exit 2), matching the contract stated in the declaration file's own header: a
    missing or unparseable configuration is never a pass (I-7). The catch is scoped to
    parse and validation failures so a genuine defect in this gate still surfaces as a
    traceback rather than being laundered into "could not read".
    """
    try:
        verdict = evaluate(reports)
    except (OSError, ReportFormatError, ValidationError, yaml.YAMLError) as exc:
        print(
            f"{_SYMBOLS['unavailable']} fe-invariants: UNAVAILABLE - configuration could "
            f"not be read: {type(exc).__name__}: {exc}"
        )
        return EXIT_UNAVAILABLE

    if as_json:
        print(json.dumps(verdict.model_dump(mode="json"), sort_keys=True, separators=(",", ":")))
        return verdict.exit_code

    enforced = tuple(a for a in verdict.attestations if a.registry_status == ENFORCED)
    print(
        f"{_SYMBOLS[verdict.verdict]} fe-invariants: {verdict.verdict.upper()} - {verdict.reason}"
    )
    print(
        f"Summary: INVARIANTS={len(verdict.attestations)} ENFORCED={len(enforced)} "
        f"ATTESTED={len(tuple(a for a in enforced if a.attested))} "
        f"EXECUTED={verdict.executed_count} SKIPPED={verdict.skipped_count} "
        f"REPORTS={len(verdict.reports_read)}"
    )
    if verdict.reports_unavailable:
        print()
        print(f"REPORTER OUTPUT UNAVAILABLE -- {len(verdict.reports_unavailable)}:")
        for item in verdict.reports_unavailable:
            print(f"  [??] {item}")
    if verdict.hygiene_errors:
        print()
        print(f"REGISTRY/DECLARATION DEFECTS -- {len(verdict.hygiene_errors)}:")
        for error in verdict.hygiene_errors:
            print(f"  [XX] {error}")
    _print_group(
        "ASSERTION FAILED -- the invariant is contradicted:",
        "[XX]",
        verdict.by_class("violated"),
    )
    _print_group(
        "ALL-SKIPPED -- the assertion exists and never ran:",
        "[XX]",
        verdict.by_class("skipped_only"),
    )
    _print_group(
        "NEVER EXECUTED -- the file exists, the assertion was not reported:",
        "[XX]",
        verdict.by_class("not_executed"),
    )
    _print_group(
        "UNOBSERVABLE -- enforced with nothing a runner can execute:",
        "[??]",
        verdict.by_class("unattributable"),
    )
    _print_group(
        "OUT OF SUITE -- declared, dated, enforced by a named CI job (not proof here):",
        "[--]",
        verdict.by_class("out_of_suite"),
    )
    _print_declared_suites(verdict.declared_suites)
    return verdict.exit_code


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="check_fe_invariants",
        description=(
            "Gate the FE-INV registry on executed, non-skipped assertions read from "
            "the Vitest/Playwright JSON reporter output."
        ),
    )
    parser.add_argument(
        "--report",
        action="append",
        dest="reports",
        metavar="PATH",
        help=(
            "repo-relative path to a Vitest or Playwright JSON reporter file "
            "(repeatable; defaults to " + ", ".join(DEFAULT_REPORTS) + ")"
        ),
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help="emit the verdict as canonical JSON instead of a human summary",
    )
    args = parser.parse_args(argv)
    reports = tuple(args.reports) if args.reports else DEFAULT_REPORTS
    return run(reports, as_json=bool(args.as_json))


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
