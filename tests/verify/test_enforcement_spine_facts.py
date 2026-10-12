"""Example-class facts for the enforcement spine (design E1; R1.5, R11.4, R14.1).

Feature: purpose-achievement-audit, task 2.16.

The spine's universal claims are carried by property tests (Properties 1-12). Three
facts in that workstream are *examples*, not properties, and the design's own decision
guide says so: whether a single committed file exists and satisfies a single committed
schema is one file read, and whether one synthetic change set selects one job is one
YAML parse. Driving either through 500 generated examples would burn a budget to
re-answer the same question, which is exactly the anti-pattern I-0 forbids.

What is pinned here:

1. **R1.5 / R11.4 - a Markdown-only push to `main` still runs the spine.** R1's finding
   is that the Check_Registry has no CI call site; R11's is that ``ci.yml``'s
   ``paths-ignore`` (``**.md``, ``docs/**``, ``plans/**``, ``notebooks/**``) skips the
   narrative-truth gate on precisely the commits most likely to drift the narrative.
   CF-2 resolves both by splitting the triggers: a lightweight ``truth-gates`` job with
   no ``paths-ignore``, while the heavy ``quality-gates`` keeps its filter.
2. **R14.1 - the required-check declaration exists and validates.** The declaration is
   the in-repo half of R14, whose finding is a boundary: a red run only blocks a merge
   because of branch-protection configuration that is not in this tree. The companion
   property test (Property 12) asserts that every declared job *resolves*; nothing
   asserted until now that the committed file satisfies its committed schema at all.
3. **The oracle both of the above lean on.** GitHub's path-filter rule and the
   declaration's structural contract are recomputed here from the specification rather
   than imported from the gate, so agreement means two implementations agree.

**Why the Markdown-selection test is `xfail(strict=False)` and not a hard failure.**
``ci.yml::truth-gates`` is created by task **2.17**, which has not landed - and 2.16
lands before it (waves 3 and 4 of the dependency graph). ``tests/verify`` is executed by
``ci.yml::uplift-verify``, which ``infrastructure/quality/required-checks.yaml`` declares
a *required* status check, so a hard-failing assertion here would block every merge -
including the merge of 2.17 that fixes it. That is a self-inflicted merge block, not a
gate. ``xfail(strict=False)`` records the obligation, names its unblocker, and reports
``XFAIL`` - which is **not a PASS** in any pytest summary, so I-7 holds: the absence of a
Markdown-selected registry step is reported as unproven, never as proven. ``strict=False``
rather than ``strict=True`` for one reason only: when 2.17 lands, the test must XPASS, not
error, so the wiring commit is not blocked by its own success. The other tests in this
file are unconditional and pass today.

I-0: no process was executed to write this file. Nothing here runs a workflow, spawns a
subprocess, starts a browser, or reads the GitHub API - the live branch-protection read
is a scheduled-workflow job by design (R14.5), never a test. Every read uses
``encoding='utf-8'`` (E-S13-07) and every assertion message is ASCII. These tests run in
``ci.yml::uplift-verify`` alongside the property suites.

**Validates: Requirements 1.5, 11.4, 14.1**
"""

from __future__ import annotations

import copy
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Final

import pytest
import yaml
from jsonschema import Draft7Validator  # type: ignore[import-untyped]

from scripts.audit import gate_surface as gs
from scripts.audit import required_checks_truth as rct
from scripts.audit.workflow_shape_truth import (
    iter_job_steps,
    iter_jobs,
    iter_workflow_paths,
    load_workflow,
    step_run_script,
    workflow_relative_path,
)

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

#: The synthetic ``push`` to ``main``, taken from the generator's own context set so the
#: two never drift apart.
PUSH_MAIN: Final[gs.TriggerContext] = next(
    context for context in gs.TRIGGER_CONTEXTS if context.id == "push:main"
)

#: A change set touching nothing but Markdown - R1.5's and R11.4's exact hypothesis, and
#: the shape of commit ``ci.yml``'s ``paths-ignore`` currently drops.
MARKDOWN_ONLY_CHANGE_SET: Final[tuple[str, ...]] = (
    "README.md",
    "CLAUDE.md",
    "docs/state/CURRENT.md",
    "docs/adr/ADR-052-agentic-loop.md",
)

#: A ``path-filtered`` reason produced by ``gate_surface`` starts with this literal. A
#: job whose only conditionality is the change-set filter is decided here, because the
#: change set is the one fact the trigger context does not carry.
PATH_FILTER_PREFIX: Final[str] = "path-filtered"


@dataclass(frozen=True)
class SpineGate:
    """One gate R1.5 / R11.4 require on a Markdown-only push, and how to spot it.

    ``tokens`` are matched against a step's ``run:`` body, so the test is indifferent to
    which job task 2.17 puts the step in - it asserts the requirement (a step that
    executed this gate ran) rather than one implementation of it.
    """

    id: str
    requirement: str
    subject: str
    tokens: tuple[str, ...]


SPINE_GATES: Final[tuple[SpineGate, ...]] = (
    SpineGate(
        id="check-registry",
        requirement="R1.5",
        subject="the Check_Registry",
        tokens=(
            "scripts.audit.registry_gate",
            "scripts.audit.verify_claims --check",
            "verify-claims",
        ),
    ),
    SpineGate(
        id="narrative-truth",
        requirement="R11.4",
        subject="the narrative-truth gate (doc_truth)",
        tokens=("scripts.audit.doc_truth",),
    ),
)

#: Every way the committed declaration could break its own schema. Each is applied to a
#: deep copy of the real document, so the guard is about the *committed* schema.
SCHEMA_BREAKS: Final[tuple[str, ...]] = (
    "drop-required-key",
    "version-wrong-type",
    "unknown-top-level-property",
    "empty-required",
    "required-entry-missing-check-name",
    "workflow-ref-outside-workflows-dir",
    "job-ref-with-illegal-character",
    "ineligible-reason-outside-enum",
    "verified-status-without-a-read",
)


# ---------------------------------------------------------------------------
# GitHub's path-filter rule, recomputed from the specification
# ---------------------------------------------------------------------------


def _filter_regex(pattern: str) -> str:
    """Translate one GitHub filter pattern to a regex.

    The three wildcards GitHub defines for ``paths``/``paths-ignore``: ``**`` matches any
    characters including ``/``, ``*`` matches any characters except ``/``, and ``?``
    matches one character except ``/``. ``fnmatch`` cannot express the ``**`` / ``*``
    distinction, which is the whole reason ``**.md`` matches ``docs/state/CURRENT.md``
    while ``*.md`` does not.
    """
    parts: list[str] = []
    index = 0
    while index < len(pattern):
        if pattern.startswith("**", index):
            parts.append(".*")
            index += 2
            continue
        character = pattern[index]
        if character == "*":
            parts.append("[^/]*")
        elif character == "?":
            parts.append("[^/]")
        else:
            parts.append(re.escape(character))
        index += 1
    return "".join(parts)


def matches_filter(path: str, pattern: str) -> bool:
    """Whether one changed path matches one GitHub filter pattern."""
    return re.fullmatch(_filter_regex(pattern), path) is not None


def _set_matches(path: str, patterns: Sequence[str]) -> bool:
    """Whether a filter *list* matches a path, honouring ``!`` negation by position.

    GitHub resolves a filter list left to right and the last matching pattern wins, so a
    trailing ``!docs/state/CURRENT.md`` un-ignores a file an earlier ``**.md`` ignored.
    """
    verdict = False
    for pattern in patterns:
        negated = pattern.startswith("!")
        if matches_filter(path, pattern[1:] if negated else pattern):
            verdict = not negated
    return verdict


def _pattern_list(spec: Mapping[str, object], key: str) -> tuple[str, ...]:
    value = spec.get(key)
    return tuple(str(item) for item in value) if isinstance(value, list) else ()


def change_set_admitted(
    spec: Mapping[str, object], changed: Sequence[str]
) -> tuple[bool, str]:
    """Whether an event spec's path filters admit a change set.

    GitHub's rule, in its two halves: with ``paths:`` the event runs when **at least one**
    changed file matches; with ``paths-ignore:`` it runs unless **every** changed file
    matches. An event with neither always runs.
    """
    if not changed:
        return False, "empty change set decides nothing"

    paths = _pattern_list(spec, "paths")
    ignore = _pattern_list(spec, "paths-ignore")

    if paths and not any(_set_matches(path, paths) for path in changed):
        return False, f"no changed file matches paths: {list(paths)}"
    if ignore and all(_set_matches(path, ignore) for path in changed):
        return False, f"every changed file matches paths-ignore: {list(ignore)}"
    if not paths and not ignore:
        return True, "no path filter on this event"
    return True, "at least one changed file survives the path filter"


def push_event_spec(document: Mapping[str, object]) -> dict[str, object] | None:
    """The ``on: push`` spec of a workflow, or ``None`` when it has no push trigger.

    ``load_workflow`` has already undone PyYAML's YAML 1.1 resolution of the bare key
    ``on`` to boolean ``True``, so the key is reliably ``"on"`` here.
    """
    block = document.get("on")
    if isinstance(block, str):
        return {} if block == "push" else None
    if isinstance(block, list):
        return {} if any(str(item) == "push" for item in block) else None
    if isinstance(block, dict):
        events = {str(key): value for key, value in block.items()}
        if "push" not in events:
            return None
        spec = events["push"]
        return {str(key): value for key, value in spec.items()} if isinstance(spec, dict) else {}
    return None


# ---------------------------------------------------------------------------
# Finding the spine's steps and deciding whether they run
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class GateStep:
    """One workflow step whose ``run:`` body executes a spine gate."""

    workflow: str
    job: str
    step: str
    script: str

    @property
    def label(self) -> str:
        return f"{self.workflow}::{self.job} :: {self.step}"


def find_gate_steps(gate: SpineGate) -> tuple[GateStep, ...]:
    """Every step in the committed workflow tree that executes ``gate``."""
    found: list[GateStep] = []
    for path in iter_workflow_paths():
        document = load_workflow(path)
        workflow = workflow_relative_path(path)
        for job_id, job in iter_jobs(document):
            for index, step in enumerate(iter_job_steps(job)):
                script = step_run_script(step)
                if not any(token in script for token in gate.tokens):
                    continue
                name = step.get("name")
                named = isinstance(name, str) and bool(name.strip())
                label = str(name).strip() if named else f"step {index}"
                found.append(
                    GateStep(workflow=workflow, job=job_id, step=label, script=script)
                )
    return tuple(found)


def executes_on_change_set(
    workflow: str, job_id: str, changed: Sequence[str]
) -> tuple[bool, str]:
    """Whether ``job_id`` runs on a push to ``main`` carrying exactly ``changed``.

    Three questions, in the order GitHub answers them, and the reason the answer is
    decidable here at all: ``gate_surface`` renders a path-filtered job ``CONDITIONAL``
    because the change set is the one fact its three synthetic trigger contexts do not
    carry. Supplying the change set resolves exactly that conditionality and nothing
    else - any *other* conditional reason (a dispatch input, an outcome function, a
    conditional ``needs:``) still means the job may not run, so it is reported as not
    executing rather than assumed either way (I-7).
    """
    for path in iter_workflow_paths():
        if workflow_relative_path(path) != workflow:
            continue
        document = load_workflow(path)

        trigger = gs.workflow_trigger_state(document, PUSH_MAIN)
        if trigger.state == "not-executed":
            return False, trigger.reason

        spec = push_event_spec(document)
        if spec is None:
            return False, "workflow on: has no push trigger"
        admitted, why = change_set_admitted(spec, changed)
        if not admitted:
            return False, why

        selection = gs.select_jobs(document, workflow, PUSH_MAIN).get(job_id)
        if selection is None:
            return False, f"job '{job_id}' is not defined in {workflow}"
        if selection.state == "not-executed":
            return False, selection.note
        residual = tuple(
            reason
            for reason in selection.reasons
            if not reason.startswith(PATH_FILTER_PREFIX)
        )
        if residual:
            return False, "conditional beyond the change set: " + "; ".join(residual)
        return True, why
    return False, f"no workflow file named {workflow}"


# ---------------------------------------------------------------------------
# The declaration and its schema, read independently of the gate
# ---------------------------------------------------------------------------


def read_declaration() -> dict[str, object]:
    """The committed declaration, parsed here rather than through the gate."""
    raw: object = yaml.safe_load(rct.DECLARATION_FILE.read_text(encoding="utf-8"))
    assert isinstance(raw, dict), "required-checks.yaml is not a YAML mapping"
    return {str(key): value for key, value in raw.items()}


def independent_schema_errors(
    document: Mapping[str, object], schema: Mapping[str, object]
) -> tuple[str, ...]:
    """Every draft-07 violation, formatted as ``pointer: message``.

    Deliberately not ``rct.schema_findings``: that is the implementation under test. Both
    are asserted below, and their agreement is the evidence.
    """
    validator = Draft7Validator(dict(schema))
    messages: list[str] = []
    for error in validator.iter_errors(dict(document)):
        pointer = "/" + "/".join(str(part) for part in error.absolute_path)
        messages.append(f"{pointer}: {error.message}")
    return tuple(sorted(messages))


def break_declaration(document: Mapping[str, object], break_kind: str) -> dict[str, object]:
    """One way the committed declaration could stop satisfying its schema."""
    broken: dict[str, Any] = copy.deepcopy(dict(document))
    if break_kind == "drop-required-key":
        del broken["reconciliation"]
    elif break_kind == "version-wrong-type":
        broken["version"] = "1"
    elif break_kind == "unknown-top-level-property":
        broken["enforced"] = True
    elif break_kind == "empty-required":
        broken["required"] = []
    elif break_kind == "required-entry-missing-check-name":
        del broken["required"][0]["check_name"]
    elif break_kind == "workflow-ref-outside-workflows-dir":
        broken["required"][0]["workflow"] = "workflows/ci.yml"
    elif break_kind == "job-ref-with-illegal-character":
        broken["required"][0]["job"] = "quality gates"
    elif break_kind == "ineligible-reason-outside-enum":
        broken["ineligible"][0]["reason"] = "because"
    elif break_kind == "verified-status-without-a-read":
        broken["reconciliation"]["status"] = "verified"
    else:  # pragma: no cover - the parametrisation is closed over SCHEMA_BREAKS
        raise AssertionError(f"unknown break kind: {break_kind}")
    return broken


# ---------------------------------------------------------------------------
# The oracle: GitHub's path-filter rule
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("path", "pattern", "expected"),
    [
        ("README.md", "**.md", True),
        ("docs/state/CURRENT.md", "**.md", True),
        ("orchestrator/consensus/protocol.py", "**.md", False),
        ("docs/state/CURRENT.md", "docs/**", True),
        ("docs", "docs/**", False),
        ("README.md", "*.md", True),
        ("docs/state/CURRENT.md", "*.md", False),
        ("docs/CURRENT.md", "docs/*.md", True),
        ("docs/state/CURRENT.md", "docs/*.md", False),
        ("frontend/src/app/Shell.tsx", "frontend/**", True),
        ("orchestrator/consensus/protocol.py", "frontend/**", False),
    ],
)
def test_one_filter_pattern_matches_what_github_says_it_matches(
    path: str, pattern: str, expected: bool
) -> None:
    """``**`` crosses ``/`` and ``*`` does not - the distinction the whole test rests on.

    ``ci.yml`` ignores ``**.md``, so a Markdown file at *any* depth is ignored. Getting
    this backwards would make the selection test below assert nothing.
    """
    assert matches_filter(path, pattern) is expected


@pytest.mark.parametrize(
    ("spec", "changed", "expected"),
    [
        # ci.yml's committed push filter against a Markdown-only commit: dropped.
        (
            {"paths-ignore": ["**.md", "docs/**", "plans/**", "notebooks/**"]},
            MARKDOWN_ONLY_CHANGE_SET,
            False,
        ),
        # One non-Markdown file is enough to admit the same commit.
        (
            {"paths-ignore": ["**.md", "docs/**", "plans/**", "notebooks/**"]},
            ("README.md", "orchestrator/consensus/protocol.py"),
            True,
        ),
        # No filter at all - what CF-2 requires of the truth-gates trigger.
        ({}, MARKDOWN_ONLY_CHANGE_SET, True),
        # A positive filter needs one match, and a Markdown-only commit has none.
        ({"paths": ["frontend/**"]}, MARKDOWN_ONLY_CHANGE_SET, False),
        ({"paths": ["frontend/**"]}, ("frontend/src/app/Shell.tsx",), True),
        # Negation is positional: the trailing `!` un-ignores the file.
        (
            {"paths-ignore": ["**.md", "!docs/state/CURRENT.md"]},
            ("docs/state/CURRENT.md",),
            True,
        ),
        (
            {"paths-ignore": ["!docs/state/CURRENT.md", "**.md"]},
            ("docs/state/CURRENT.md",),
            False,
        ),
    ],
)
def test_a_change_set_is_admitted_exactly_when_github_would_run_the_event(
    spec: dict[str, object], changed: tuple[str, ...], expected: bool
) -> None:
    """``paths`` needs one match; ``paths-ignore`` needs one survivor.

    The first row is R11.4's hole stated mechanically: ``ci.yml``'s committed
    ``paths-ignore`` drops a commit that touches only Markdown, which is precisely the
    commit most likely to drift the narrative the gate exists to pin.
    """
    admitted, reason = change_set_admitted(spec, changed)
    assert admitted is expected
    assert reason
    assert reason.isascii()


def test_the_committed_ci_push_trigger_is_read_the_way_the_finding_describes_it() -> None:
    """A read of the real file, so the oracle above is anchored to the tree.

    Asserted as a *disjunction over the tree* rather than as "ci.yml ignores Markdown",
    because task 2.17 may satisfy CF-2 either by dropping ``ci.yml``'s workflow-level
    filter or by adding a job elsewhere. What must hold today and after is that the
    reader can tell which workflows a Markdown-only push reaches.
    """
    reachable: dict[str, bool] = {}
    for path in iter_workflow_paths():
        document = load_workflow(path)
        spec = push_event_spec(document)
        if spec is None:
            continue
        if gs.workflow_trigger_state(document, PUSH_MAIN).state == "not-executed":
            continue
        admitted, _ = change_set_admitted(spec, MARKDOWN_ONLY_CHANGE_SET)
        reachable[workflow_relative_path(path)] = admitted

    assert reachable, "no workflow declares a push trigger selecting main"
    assert ".github/workflows/ci.yml" in reachable


# ---------------------------------------------------------------------------
# R14.1 - the declaration exists and validates
# ---------------------------------------------------------------------------


def test_the_required_check_declaration_and_its_schema_are_committed() -> None:
    """R14.1: the declaration exists, as a file, in this tree.

    This is the whole of R14's in-repo half. Branch protection lives outside the
    repository, so a committed declaration is the only artifact an auditor can read to
    learn which jobs the project believes block a merge.
    """
    assert rct.DECLARATION_FILE.is_file(), f"{rct.DECLARATION_FILE} is missing"
    assert rct.SCHEMA_FILE.is_file(), f"{rct.SCHEMA_FILE} is missing"

    document = read_declaration()
    assert document["version"] == 1
    assert document["branch"] == "main"
    required = document["required"]
    assert isinstance(required, list) and required, "the declared required set is empty"


def test_the_committed_declaration_validates_against_its_committed_schema() -> None:
    """R14.1: zero structural violations, agreed by two independent validations.

    ``rct.load_schema`` also asserts the schema is a valid draft-07 schema, so a schema
    that could never reject anything is caught here rather than reading as a clean pass.
    """
    document = read_declaration()
    schema = rct.load_schema()

    independent = independent_schema_errors(document, schema)
    assert independent == (), f"declaration violates its schema: {independent}"

    through_the_gate = rct.schema_findings(document, schema)
    assert through_the_gate == (), f"gate reports schema violations: {through_the_gate}"


@pytest.mark.parametrize("break_kind", SCHEMA_BREAKS)
def test_the_committed_schema_rejects_each_way_the_declaration_could_break(
    break_kind: str,
) -> None:
    """The sensitivity guard: a schema that accepts anything validates nothing.

    Without this, the test above would pass just as happily against a schema of
    ``{}``. Each mutation is applied to a deep copy of the real document, so what is
    exercised is the shipped contract - including the ``allOf`` clause that refuses a
    ``verified`` status with no recorded read, which is I-7 written into the schema.
    """
    schema = rct.load_schema()
    broken = break_declaration(read_declaration(), break_kind)

    independent = independent_schema_errors(broken, schema)
    assert independent, f"the committed schema accepted '{break_kind}'"

    findings = rct.schema_findings(broken, schema)
    assert findings, f"the gate accepted '{break_kind}'"
    for finding in findings:
        assert finding.rule == "schema-invalid"
        assert finding.requirement == "R14.1"
        assert finding.detail
        assert finding.detail.isascii()


def test_the_declaration_stays_ascii_so_a_finding_can_be_printed() -> None:
    """E-S13-07's console half, pinned on the file that has to carry an em dash.

    ``ci.yml``'s chromatic job display name contains U+2014. The declaration records it
    as a ``\\u2014`` escape precisely so the file itself stays ASCII; the escape is
    resolved by the YAML parser, so the comparison the gate makes is still byte-for-byte
    against the workflow.
    """
    text = rct.DECLARATION_FILE.read_text(encoding="utf-8")
    assert text.isascii(), "required-checks.yaml carries non-ASCII bytes"

    document = read_declaration()
    declared_names: list[str] = []
    for section in ("required", "candidates", "pending"):
        block = document.get(section)
        if not isinstance(block, list):
            continue
        declared_names.extend(
            str(entry["check_name"])
            for entry in block
            if isinstance(entry, dict) and isinstance(entry.get("check_name"), str)
        )
    assert declared_names, "the declaration records no check_name at all"
    assert any(not name.isascii() for name in declared_names), (
        "no declared check_name resolves to a non-ASCII display name, so the YAML escape "
        "this test guards is no longer exercised - drop the assertion or restore the entry"
    )


# ---------------------------------------------------------------------------
# R1.5 / R11.4 - a Markdown-only push still runs the spine (blocked on task 2.17)
# ---------------------------------------------------------------------------


@pytest.mark.xfail(
    strict=False,
    reason=(
        "R1.5/R11.4 are unblocked by task 2.17, which adds the blocking ci.yml::truth-gates "
        "job with no paths-ignore (CF-2). Until it lands, no workflow job runs the "
        "Check_Registry or doc_truth on a Markdown-only push to main. XFAIL is not a PASS "
        "(I-7); strict=False so the 2.17 wiring commit XPASSes instead of erroring."
    ),
)
@pytest.mark.parametrize("gate", SPINE_GATES, ids=[gate.id for gate in SPINE_GATES])
def test_a_markdown_only_push_to_main_still_runs_the_spine_gate(gate: SpineGate) -> None:
    """R1.5 / R11.4: some job executing this gate is selected by a doc-only commit.

    Stated over the whole workflow tree rather than over ``ci.yml::truth-gates`` by name,
    so the assertion is the requirement and not one implementation of it: any job, in any
    workflow, that a push to ``main`` carrying only Markdown selects, and whose ``run:``
    body executes this gate, satisfies it.
    """
    steps = find_gate_steps(gate)
    assert steps, (
        f"{gate.requirement}: no workflow step executes {gate.subject} at all "
        f"(searched for {list(gate.tokens)})"
    )

    verdicts = {
        step.label: executes_on_change_set(step.workflow, step.job, MARKDOWN_ONLY_CHANGE_SET)
        for step in steps
    }
    selected = [label for label, (runs, _) in verdicts.items() if runs]
    diagnostic = "; ".join(
        f"{label} -> {reason}" for label, (runs, reason) in verdicts.items() if not runs
    )

    assert selected, (
        f"{gate.requirement}: a push to main changing only "
        f"{list(MARKDOWN_ONLY_CHANGE_SET)} selects no job executing {gate.subject}. "
        f"Candidate steps and why each is not selected: {diagnostic}"
    )
