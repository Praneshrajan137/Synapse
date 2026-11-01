"""Property-based test for the generated gate-surface record (design E1.6).

Feature: purpose-achievement-audit, Property 11: The generated gate-surface record
round-trips and respects dependencies

    *For any* set of workflow files and *any* trigger context, the record enumerates
    exactly the jobs and steps the trigger conditions select, marks each step's
    exit-status propagation, reports a job whose dependency was not selected as not
    executed, and a committed record differing from the parse fails with a printed
    difference.

Why a property and not examples. R11's finding is about an *aggregate*: no document
said which gates a merge to `main` actually runs, so a reader summing the gate
inventory overestimated the enforcement boundary. A fixed set of examples pins the
trigger shapes this repository happens to use today; the failure mode is the next
shape - a `needs:` edge added onto a tag-only job, a branch filter narrowed, a job
made conditional - silently rendering as blocking. So the property quantifies over
generated workflow trees and asserts the projection is **total** there: every job
lands in exactly one of the three states under each of the three synthetic
contexts, and the row set is exactly the one the trigger conditions mandate.

Ground truth. ``tests/verify/strategies.py`` renders real GitHub-Actions-shaped YAML
in which ``StepDraft.discarding_construct`` is the construct that was injected and
``JobDraft.needs``/``if_condition`` are the edges and conditions that were declared.
The expectation below is recomputed from those drafts through an independent reading
of the ``on:`` block and a literal truth table over the three generated ``if:``
expressions - it never calls the gate's own evaluator - so agreement is two
implementations meeting, not a tautology over a shared helper. ``needs`` only ever
points at an earlier job, so the dependency graph is acyclic by construction and a
cycle is a separate (separately specified) failure mode.

Subject: ``scripts/audit/gate_surface`` (task 2.12). Every root it reads is a
parameter defaulted to this repository's, mirroring
``workflow_shape_truth.evaluate`` (task 2.11), so each example runs against a
generated workflow tree inside a ``tempfile.TemporaryDirectory``. This test parses
YAML and writes Markdown: it executes no workflow, no subprocess, and no build
(I-0). The final test reads the *committed* tree statically, which is the only way
to confirm ``docs/state/GATE_SURFACE.md`` still matches the workflows as they stand.

``max_examples`` is never set here - the budget comes from the root ``conftest.py``
profiles (``dev``=10, ``heavy``=100, ``ci``/``default``=500, ``nightly``=5000).

**Validates: Requirements 11.1, 11.2, 11.7, 11.9**
"""

from __future__ import annotations

import tempfile
from fnmatch import fnmatchcase
from pathlib import Path
from typing import TYPE_CHECKING, Final

import yaml
from hypothesis import given
from hypothesis import strategies as st

from scripts.audit import gate_surface as gs
from tests.verify.strategies import (
    JobDraft,
    StepDraft,
    WorkflowDraft,
    step_drafts,
    workflow_documents,
)

if TYPE_CHECKING:  # pragma: no cover - annotations only
    from pytest import CaptureFixture

#: One surface row reduced to the fields R11.1 obliges it to carry.
RowKey = tuple[str, str, str, str]

#: The three synthetic trigger ids, as the generator names them.
TRIGGER_IDS: Final[tuple[str, ...]] = tuple(context.id for context in gs.TRIGGER_CONTEXTS)

#: Truth table for the three ``if:`` expressions ``workflow_documents`` generates,
#: written out per trigger rather than evaluated. This is the independent half of the
#: comparison: `gate_surface`'s expression evaluator must rediscover these values from
#: the ``github.*`` context it builds, and a disagreement is a real finding either way.
IF_TRUTH: Final[dict[str, dict[str, bool]]] = {
    "github.event_name == 'pull_request'": {
        "push:main": False,
        "pull_request": True,
        "tag:v*": False,
    },
    "github.ref == 'refs/heads/main'": {
        "push:main": True,
        # A pull request's `github.ref` is the merge ref, never `refs/heads/main` -
        # the mechanism behind `required-checks.yaml`'s branch-push-only reason.
        "pull_request": False,
        "tag:v*": False,
    },
    "startsWith(github.ref, 'refs/tags/v')": {
        "push:main": False,
        "pull_request": False,
        "tag:v*": True,
    },
}


# ---------------------------------------------------------------------------
# The independent expectation
# ---------------------------------------------------------------------------


def _patterns(spec: object, key: str) -> list[str] | None:
    """One ``on:`` filter list, or ``None`` when the filter is absent."""
    if not isinstance(spec, dict):
        return None
    value = spec.get(key)
    return [str(item) for item in value] if isinstance(value, list) else None


def expected_workflow_selected(on_block: object, context: gs.TriggerContext) -> bool:
    """Whether a workflow's ``on:`` block selects one synthetic context.

    Read straight off the drafted ``on:`` mapping rather than the trigger *names*,
    because ``WorkflowDraft.as_yaml_obj`` merges ``push:main`` and ``tag:v*`` into one
    ``push:`` spec and the merge order decides which filters survive. What is on disk
    is what the gate must be judged against.

    Only the filters the strategy emits (``branches``, ``tags``) are handled - a
    ``paths``/``paths-ignore`` filter would make the honest answer CONDITIONAL rather
    than a boolean, and the generator emits none.
    """
    events = on_block if isinstance(on_block, dict) else {}
    if context.event_name == "pull_request":
        if "pull_request" not in events:
            return False
        branches = _patterns(events["pull_request"], "branches")
        return branches is None or any(
            fnmatchcase(context.base_ref, pattern) for pattern in branches
        )

    if "push" not in events:
        return False
    spec = events["push"]
    branches = _patterns(spec, "branches")
    tags = _patterns(spec, "tags")
    if context.ref_type == "tag":
        # A `branches:` filter with no `tags:` filter excludes tag pushes entirely.
        if tags is None:
            return branches is None
        return any(fnmatchcase(context.ref_name, pattern) for pattern in tags)
    if branches is None:
        return tags is None
    return any(fnmatchcase(context.ref_name, pattern) for pattern in branches)


def expected_selected(draft: WorkflowDraft, context: gs.TriggerContext) -> dict[str, bool]:
    """``job_id -> does it execute`` under one context, recomputed from the draft.

    The ``needs:`` clause is the R11.9 rule stated positively: a job executes only if
    every job it depends on executes. Jobs are visited in file order and ``needs``
    only points backwards, so one pass suffices.
    """
    selected_workflow = expected_workflow_selected(draft.as_yaml_obj().get("on"), context)
    states: dict[str, bool] = {}
    for job in draft.jobs:
        if not selected_workflow:
            states[job.job_id] = False
        elif job.if_condition is not None and not IF_TRUTH[job.if_condition][context.id]:
            states[job.job_id] = False
        else:
            states[job.job_id] = all(states[need] for need in job.needs)
    return states


def expected_rows(draft: WorkflowDraft, workflow_key: str) -> tuple[RowKey, ...]:
    """The surface rows the three contexts mandate, in the order they are rendered.

    A job that does not execute contributes exactly one row, carrying
    ``NOT EXECUTED`` and no step: its steps are not rendered as anything, which is
    what stops them being counted or read as passes (R11.9, I-7). An executing job
    contributes one row per step, ``yes`` iff that step propagates its exit status.
    """
    rows: list[RowKey] = []
    for context in gs.TRIGGER_CONTEXTS:
        states = expected_selected(draft, context)
        for job in draft.jobs:
            qualified = f"{workflow_key}::{job.job_id}"
            if not states[job.job_id]:
                rows.append((context.id, qualified, "-", "NOT EXECUTED"))
                continue
            for step in job.steps:
                rows.append(
                    (
                        context.id,
                        qualified,
                        step.step_name,
                        "yes" if step.propagates_exit_status else "no",
                    )
                )
    return tuple(rows)


def actual_rows(record: gs.GateSurfaceRecord) -> tuple[RowKey, ...]:
    """The record's surface rows reduced to the same tuple shape."""
    return tuple((row.trigger, row.job, row.step, row.propagates) for row in record.rows)


# ---------------------------------------------------------------------------
# The hermetic tree
# ---------------------------------------------------------------------------


def render_declaration(draft: WorkflowDraft, workflow_key: str) -> str:
    """A ``blocking-steps.yaml`` body declaring this draft's blocking steps.

    One entry per job so the file stays loadable (a declaration file with an empty
    ``steps:`` list is *unavailable*, a separate verdict); an entry with no names
    contributes no anchor.
    """
    entries = [
        {
            "workflow": workflow_key,
            "job": job.job_id,
            "step_names": sorted(
                {step.step_name for step in job.steps if step.declared_blocking}
            ),
            "match": "exact",
            "requirement": "R11.8",
        }
        for job in draft.jobs
    ]
    return yaml.safe_dump({"version": 1, "steps": entries}, sort_keys=True, allow_unicode=False)


def write_tree(root: Path, draft: WorkflowDraft) -> tuple[Path, Path, str]:
    """Materialise one generated workflow tree; return its roots and workflow key."""
    directory = root / "workflows"
    directory.mkdir(exist_ok=True)
    workflow_path = directory / draft.path.rsplit("/", 1)[-1]
    workflow_path.write_text(draft.to_yaml(), encoding="utf-8")
    workflow_key = gs.workflow_relative_path(workflow_path)
    declaration_path = root / "blocking-steps.yaml"
    declaration_path.write_text(
        render_declaration(draft, workflow_key), encoding="utf-8"
    )
    return directory, declaration_path, workflow_key


def collect_draft(draft: WorkflowDraft) -> tuple[gs.GateSurfaceRecord, str]:
    """Project the surface of one generated workflow inside a throwaway tree."""
    with tempfile.TemporaryDirectory(prefix="gate-surface-") as tmp:
        directory, declaration_path, workflow_key = write_tree(Path(tmp), draft)
        record = gs.collect_record(directory, declaration_path=declaration_path)
    return record, workflow_key


def two_job_chain(condition: str, steps: tuple[StepDraft, ...]) -> WorkflowDraft:
    """``job-1`` needs ``job-0``, and ``job-0`` runs only when ``condition`` holds."""
    return WorkflowDraft(
        path=".github/workflows/ci.yml",
        triggers=("push:main", "pull_request", "tag:v*"),
        jobs=(
            JobDraft(job_id="job-0", needs=(), if_condition=condition, steps=steps),
            JobDraft(job_id="job-1", needs=("job-0",), if_condition=None, steps=steps),
        ),
    )


# ---------------------------------------------------------------------------
# R11.1 - the record enumerates exactly what the triggers select
# ---------------------------------------------------------------------------


# Feature: purpose-achievement-audit, Property 11: The generated gate-surface record
# round-trips and respects dependencies
@given(draft=workflow_documents())
def test_the_record_enumerates_exactly_the_selected_jobs_and_steps(
    draft: WorkflowDraft,
) -> None:
    """R11.1: the row set is exactly the mandated one, and selection is total.

    Set equality is not enough here - the rows are ordered, and a drift diff is only
    readable if the order is stable - so the tuples are compared positionally. The
    "and nothing else" half is what forbids a job the trigger excludes from
    contributing step rows at all.
    """
    record, workflow_key = collect_draft(draft)

    assert record.triggers == TRIGGER_IDS
    assert actual_rows(record) == expected_rows(draft, workflow_key)

    # Selection is a total function of (trigger, job): one verdict each, no gaps, no
    # duplicates, and every verdict drawn from the three declared states.
    keys = [(item.trigger, item.workflow, item.job) for item in record.selections]
    assert len(keys) == len(set(keys)) == len(TRIGGER_IDS) * len(draft.jobs)
    for item in record.selections:
        assert item.state in {"selected", "conditional", "not-executed"}
        assert item.note

    for context in gs.TRIGGER_CONTEXTS:
        states = expected_selected(draft, context)
        by_job = {
            item.job: item for item in record.selections if item.trigger == context.id
        }
        for job in draft.jobs:
            # No `paths:` filter and no undecidable `if:` is generated, so every job
            # is decided either way; a CONDITIONAL here would be the gate inventing
            # ambiguity the trigger does not have.
            assert by_job[job.job_id].state == (
                "selected" if states[job.job_id] else "not-executed"
            )

    # Every cell is one of the four declared values, and the parse counted the tree.
    assert all(row.propagates in gs.PROPAGATES_VALUES for row in record.rows)
    assert record.workflow_count == 1
    assert record.job_count == len(draft.jobs)
    assert record.step_count == len(draft.steps())


@given(draft=workflow_documents())
def test_the_summary_counts_equal_the_rows_they_summarise(draft: WorkflowDraft) -> None:
    """R11.1: the aggregate a reader takes away is the aggregate that was projected.

    The whole point of the document is the summary line; a summary that disagreed
    with its own table would reintroduce the overstatement R11 records.
    """
    record, _ = collect_draft(draft)
    summaries = {summary.trigger: summary for summary in record.summaries}
    assert tuple(summaries) == TRIGGER_IDS

    for context in gs.TRIGGER_CONTEXTS:
        states = expected_selected(draft, context)
        summary = summaries[context.id]
        executing = [job for job in draft.jobs if states[job.job_id]]

        assert summary.jobs_selected == len(executing)
        assert summary.jobs_not_executed == len(draft.jobs) - len(executing)
        # Nothing in this generated space is conditional, so a non-zero count here
        # would mean the gate softened a decidable verdict.
        assert summary.jobs_conditional == 0
        assert summary.steps_conditional == 0
        assert summary.steps_propagating == sum(
            1 for job in executing for step in job.steps if step.propagates_exit_status
        )
        assert summary.steps_advisory == sum(
            1 for job in executing for step in job.steps if not step.propagates_exit_status
        )


# ---------------------------------------------------------------------------
# R11.9 - a job whose dependency was not selected is never reported successful
# ---------------------------------------------------------------------------


@given(draft=workflow_documents())
def test_a_job_whose_dependency_is_not_selected_is_never_reported_successful(
    draft: WorkflowDraft,
) -> None:
    """R11.9: ``needs:`` dominates, transitively, and the dependency is named.

    Two halves, and the second is the one with teeth. The dependent job must render
    ``NOT EXECUTED`` - but more than that, *no* row it contributes anywhere in the
    document may read ``yes`` or ``no``, because either value would let a reader
    count it towards the blocking surface. Under I-7 a job that did not run cannot
    be reported successful, and the anchor table is checked too: a declared-blocking
    step inside a skipped job is exactly where an unearned pass would hide.
    """
    record, workflow_key = collect_draft(draft)
    by_key = {(item.trigger, item.job): item for item in record.selections}
    skipped: set[tuple[str, str]] = set()

    for context in gs.TRIGGER_CONTEXTS:
        workflow_selected = expected_workflow_selected(
            draft.as_yaml_obj().get("on"), context
        )
        for job in draft.jobs:
            selection = by_key[(context.id, job.job_id)]
            unmet = [
                need
                for need in job.needs
                if by_key[(context.id, need)].state == "not-executed"
            ]
            if not unmet:
                continue
            assert selection.state == "not-executed"
            skipped.add((context.id, f"{workflow_key}::{job.job_id}"))

            # The *reason* is reported under E1.6's fixed precedence, strongest
            # first: the workflow not being selected outranks the job's own `if:`,
            # which outranks an unmet dependency. So the dependency is named only
            # when the dependency is what stopped this job - when the workflow is
            # excluded outright, naming the trigger is both correct and the more
            # useful reason. What R11.9 requires unconditionally is the *state*,
            # asserted above and again over every row below.
            own_if_holds = (
                job.if_condition is None or IF_TRUTH[job.if_condition][context.id]
            )
            if workflow_selected and own_if_holds:
                assert any(need in selection.note for need in unmet), selection.note
                assert "NOT EXECUTED" in selection.note

    for row in (*record.rows, *record.anchors):
        if (row.trigger, row.job) in skipped:
            assert row.propagates == "NOT EXECUTED", row


@given(
    condition=st.sampled_from(sorted(IF_TRUTH)),
    steps=st.lists(step_drafts(declared_blocking=True), min_size=1, max_size=2).map(tuple),
)
def test_an_unmet_dependency_renders_not_executed_naming_the_dependency(
    condition: str,
    steps: tuple[StepDraft, ...],
) -> None:
    """R11.9 targeted: each generated ``if:`` skips ``job-0`` in exactly two contexts.

    The quantified test above only sees unmet dependencies when the generator happens
    to produce one. This constructs the case directly for all three conditions, so
    every ``if:`` shape is exercised on both sides: in the one context where
    ``job-0`` runs the dependent must be blocking, and in the other two it must be
    ``NOT EXECUTED``. A gate that reported the dependent as executing in the context
    where its dependency was skipped would pass the first half and fail here.
    """
    draft = two_job_chain(condition, steps)
    record, workflow_key = collect_draft(draft)
    dependent = f"{workflow_key}::job-1"

    for context in gs.TRIGGER_CONTEXTS:
        selection = next(
            item
            for item in record.selections
            if item.trigger == context.id and item.job == "job-1"
        )
        rows = [
            row for row in record.rows if row.trigger == context.id and row.job == dependent
        ]
        if IF_TRUTH[condition][context.id]:
            assert selection.state == "selected"
            assert {row.propagates for row in rows} <= {"yes", "no"}
            continue

        assert selection.state == "not-executed"
        assert "job-0" in selection.note
        assert "NOT EXECUTED" in selection.note
        assert [row.propagates for row in rows] == ["NOT EXECUTED"]
        assert rows[0].step == "-"


# ---------------------------------------------------------------------------
# R11.2, R11.7 - the record round-trips, and drift is printed
# ---------------------------------------------------------------------------


@given(draft=workflow_documents())
def test_the_generated_record_round_trips_and_check_reports_no_drift(
    draft: WorkflowDraft,
) -> None:
    """R11.2, R11.7: rendering is idempotent and ``--check`` agrees with ``--write``.

    Three round trips, each closing a different hole. Rendering twice from one record
    must be byte-identical, or the check would fail on its own output. Re-rendering
    *through* the written document must be identical, or every second CI run would
    report drift. And prose appended outside the markers must survive, because a
    generator that ate hand-authored context would be abandoned rather than trusted
    (AD-2).
    """
    with tempfile.TemporaryDirectory(prefix="gate-surface-") as tmp:
        root = Path(tmp)
        directory, declaration_path, _ = write_tree(root, draft)
        record = gs.collect_record(directory, declaration_path=declaration_path)
        document = root / "GATE_SURFACE.md"

        assert gs.render_document(record) == gs.render_document(record)

        assert (
            gs.run(
                write=True,
                path=document,
                directory=directory,
                declaration_path=declaration_path,
            )
            == 0
        )
        written = document.read_text(encoding="utf-8")
        assert gs.GENERATED_BEGIN in written and gs.GENERATED_END in written
        assert gs.render_document(record, written) == written
        assert gs.diff_document(written, gs.render_document(record, written)) == ""

        # The explicit --check form, over the record it just wrote.
        assert (
            gs.run(path=document, directory=directory, declaration_path=declaration_path)
            == 0
        )

        # Hand-authored prose outside the markers survives a regeneration.
        document.write_text(
            f"{written}\n## Notes\n\nHand-authored prose outside the markers.\n",
            encoding="utf-8",
        )
        assert (
            gs.run(path=document, directory=directory, declaration_path=declaration_path)
            == 0
        )


@given(draft=workflow_documents())
def test_a_mutated_committed_record_fails_with_a_printed_difference(
    draft: WorkflowDraft,
    capsys: CaptureFixture[str],
) -> None:
    """R11.2, R11.7: drift is detected and the difference is printed, not just flagged.

    Two mutations, because they fail for different reasons. Inserting a fabricated
    blocking row is the overstatement R11 is about - a row claiming a gate runs when
    the parse says nothing of the sort. Deleting the last generated line is the
    quieter direction: a record that silently loses coverage. Both must exit ``1``
    with the offending text in the diff, and an absent record must not read as a pass.
    """
    with tempfile.TemporaryDirectory(prefix="gate-surface-") as tmp:
        root = Path(tmp)
        directory, declaration_path, _ = write_tree(root, draft)
        document = root / "GATE_SURFACE.md"

        # No committed record at all is a failure, never a pass (I-7).
        assert (
            gs.run(path=document, directory=directory, declaration_path=declaration_path)
            == 1
        )
        assert (
            gs.run(
                write=True,
                path=document,
                directory=directory,
                declaration_path=declaration_path,
            )
            == 0
        )
        clean = document.read_text(encoding="utf-8")

        fabricated = "| push:main | fabricated.yml::job-9 | Fabricated gate | yes | blocking |"
        mutations = (
            clean.replace(gs.GENERATED_END, f"{fabricated}\n{gs.GENERATED_END}", 1),
            clean.replace(f"\n{gs.GENERATED_END}", "", 1),
        )
        for mutated in mutations:
            assert mutated != clean
            document.write_text(mutated, encoding="utf-8")
            capsys.readouterr()
            assert (
                gs.run(path=document, directory=directory, declaration_path=declaration_path)
                == 1
            )
            printed = capsys.readouterr().out
            assert "verdict=fail" in printed
            # A unified diff, not a bare verdict: the reader is told what moved.
            assert "@@" in printed
            assert "(committed)" in printed and "(regenerated)" in printed

        # And the diff of the fabricated row names the fabricated row.
        assert fabricated in gs.diff_document(mutations[0], clean, path=document)


# ---------------------------------------------------------------------------
# The committed tree, read statically
# ---------------------------------------------------------------------------


def test_the_committed_gate_surface_record_matches_the_parsed_workflow_tree() -> None:
    """R11.2, R11.7 against the real repository: the committed record has no drift.

    A static read of ``.github/workflows/`` - no workflow is executed. This is the
    obligation R11.2 states directly: the record is regenerated in the same change
    that moves a trigger condition. It is also the only mechanical confirmation that
    the hand-edited rows in ``docs/state/GATE_SURFACE.md`` match what the generator
    actually emits, rather than what an editor predicted it would emit.
    """
    record = gs.collect_record()
    assert record.workflow_count > 0
    assert record.step_count > 0

    committed = gs.SURFACE_DOC.read_text(encoding="utf-8")
    generated = gs.render_document(record, committed)
    assert committed == generated, (
        "docs/state/GATE_SURFACE.md differs from the parsed workflow tree; "
        "regenerate with `python -m scripts.audit.gate_surface --write`\n"
        + gs.diff_document(committed, generated)
    )


def test_no_committed_row_reports_a_skipped_job_as_blocking() -> None:
    """R11.9, I-7 against the real repository: nothing skipped is counted as a pass.

    Narrower than the drift check above and independent of it: whatever the committed
    document says, the *projection* of the real workflow tree must never mark a row
    ``yes`` or ``no`` for a job it also reports as NOT EXECUTED. That is the
    invariant a reader relies on when they add up the blocking surface.
    """
    record = gs.collect_record()
    skipped = {
        (item.trigger, f"{item.workflow}::{item.job}")
        for item in record.selections
        if item.state == "not-executed"
    }
    assert skipped, "expected at least one skipped job in the committed tree"

    for row in (*record.rows, *record.anchors):
        assert row.propagates in gs.PROPAGATES_VALUES
        if (row.trigger, row.job) in skipped:
            assert row.propagates == "NOT EXECUTED", row
