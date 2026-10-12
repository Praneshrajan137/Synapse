"""Property-based test for exit-status propagation in the workflow tree (design E1.5).

Feature: purpose-achievement-audit, Property 4: A declared-blocking step propagates its
exit status

    *For any* workflow file and *any* step within it, the shape checker reports the step
    as propagating iff the step contains no exit-status-discarding construct
    (``|| true``, ``|| echo``, ``; exit 0``, ``continue-on-error: true``), fails naming
    file and step for every non-propagating step in the declared-blocking set, and
    requires every other non-propagating step to carry an advisory marker in its name.

Why a property and not examples. The audit found the same condition - a gate whose exit
status is discarded is not a gate - in four separate places, each with a *different*
construct, and one of them was hidden behind a step whose name gave no hint. A fixed set
of examples pins the four constructs the audit happened to find; the failure mode is a
fifth spelling, or the same spelling in a step the checker never classified. So the
property quantifies over the whole rendered step space and asserts the classification is
**total** there: every generated step lands on exactly one side, and the side it lands on
is the construct the generator injected.

Ground truth. ``tests/verify/strategies.py`` renders real GitHub-Actions-shaped YAML in
which ``StepDraft.discarding_construct`` is the construct that was injected. The checker
reads only the rendered YAML, so agreement between the two is the checker rediscovering
a fact it was not told - not a tautology over a shared helper.

Subject: ``scripts/audit/workflow_shape_truth`` (task 2.10) - ``classify_step`` for the
per-step reading and ``evaluate`` for the three rules that consume it. Both are pure file
reads over a generated tree in a temporary directory: this test executes no workflow, no
subprocess, and no build (I-0). The last test reads the *committed* workflows statically,
which is the only way to confirm that ``ci.yml``'s two honest ``ADVISORY`` /
``informational`` labels satisfy the R11.3 name rule as they stand.

``max_examples`` is never set here - the budget comes from the root ``conftest.py``
profiles (``dev``=10, ``heavy``=100, ``ci``/``default``=500, ``nightly``=5000).

**Validates: Requirements 1.8, 6.13, 8.9, 11.3**
"""

from __future__ import annotations

import dataclasses
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Final

import yaml
from hypothesis import given
from hypothesis import strategies as st

from scripts.audit import workflow_shape_truth as wst
from tests.verify.strategies import (
    ADVISORY_MARKERS,
    DISCARDING_CONSTRUCTS,
    JobDraft,
    StepDraft,
    WorkflowDraft,
    step_drafts,
    workflow_documents,
)

if TYPE_CHECKING:
    from scripts.audit.workflow_shape_truth import ShapeReport, StepShape

#: One finding, reduced to the fields R1.8 obliges it to name.
FindingKey = tuple[str, str, str, str, str]

#: The exit status a non-passing verdict must produce. ``2`` is non-passing too (I-7).
NON_PASSING_VERDICTS: Final[tuple[str, ...]] = ("fail", "unavailable")

#: ``ci.yml``'s two honest labels, as committed. Both steps do NOT propagate; both say
#: so in their own names, which is exactly what R11.3 asks of a non-propagating step.
COMMITTED_ADVISORY_STEPS: Final[tuple[tuple[str, str, str], ...]] = (
    (
        ".github/workflows/ci.yml",
        "quality-gates",
        "MyPy strict type check (agents - informational, target=blocking)",
    ),
    (
        ".github/workflows/ci.yml",
        "quality-gates",
        "License audit (I-1 - ADVISORY, non-blocking)",
    ),
)


# ---------------------------------------------------------------------------
# Rendering the generated tree, and the independent recompute of the rules
# ---------------------------------------------------------------------------


def one_job_workflow(step: StepDraft) -> WorkflowDraft:
    """A single-job, single-step workflow carrying ``step`` verbatim."""
    return WorkflowDraft(
        path=".github/workflows/ci.yml",
        triggers=("push:main",),
        jobs=(JobDraft(job_id="job-0", needs=(), if_condition=None, steps=(step,)),),
    )


def declared_names_by_job(draft: WorkflowDraft) -> dict[str, frozenset[str]]:
    """The declared-blocking step names of each job, keyed as the gate keys them.

    The gate resolves a declaration to ``(workflow, job, step name)`` keys, so two
    steps of one job sharing a name are one key. Recomputed here with the same
    granularity, otherwise the expectation would disagree with the gate about
    something that is not the property.
    """
    declared: dict[str, set[str]] = {job.job_id: set() for job in draft.jobs}
    for job in draft.jobs:
        for step in job.steps:
            if step.declared_blocking:
                declared[job.job_id].add(step.step_name)
    return {job_id: frozenset(names) for job_id, names in declared.items()}


def render_declaration(draft: WorkflowDraft, workflow_key: str) -> str:
    """A ``blocking-steps.yaml`` body declaring this draft's blocking steps.

    One entry per job, even when the job declares no blocking step: the file must stay
    schema-valid (a declaration file with an empty ``steps:`` list is *unavailable*, a
    separate verdict), and an entry with no names must contribute no finding.
    """
    declared = declared_names_by_job(draft)
    entries = [
        {
            "workflow": workflow_key,
            "job": job.job_id,
            "step_names": sorted(declared[job.job_id]),
            "match": "exact",
            "requirement": "R1.8",
        }
        for job in draft.jobs
    ]
    return yaml.safe_dump({"version": 1, "steps": entries}, sort_keys=True, allow_unicode=False)


def expected_findings(draft: WorkflowDraft, workflow_key: str) -> set[FindingKey]:
    """The findings the three rules mandate, recomputed from the injected ground truth.

    Written out rather than imported from the gate, so the test compares two
    implementations. Two rules of E1.5 cannot fire over this generated space and are
    asserted absent instead: ``blocking-unresolved`` (every declared name is a real
    step here) and ``chain-verifier-discards`` (no generated command names the audit
    verifier).
    """
    declared = declared_names_by_job(draft)
    findings: set[FindingKey] = set()
    for job in draft.jobs:
        for step in job.steps:
            if step.propagates_exit_status:
                continue
            if step.step_name in declared[job.job_id]:
                findings.add(
                    ("blocking-discards", "R1.8", workflow_key, job.job_id, step.step_name)
                )
            elif not step.advisory_in_name:
                findings.add(
                    ("unlabelled-advisory", "R11.3", workflow_key, job.job_id, step.step_name)
                )
    return findings


def actual_findings(report: ShapeReport) -> set[FindingKey]:
    """The report's findings reduced to the same tuple shape."""
    return {
        (item.rule, item.requirement, item.workflow, item.job, item.step_name)
        for item in report.findings
    }


def evaluate_draft(draft: WorkflowDraft) -> tuple[ShapeReport, str]:
    """Run the gate over one generated workflow in a throwaway tree.

    Every root the gate reads is pointed inside the temporary directory, so the verdict
    is a statement about the generated tree and nothing else. The directory is removed
    on the way out - no example leaves a file behind.
    """
    with tempfile.TemporaryDirectory(prefix="shape-truth-") as tmp:
        root = Path(tmp)
        directory = root / "workflows"
        directory.mkdir()

        workflow_path = directory / draft.path.rsplit("/", 1)[-1]
        workflow_path.write_text(draft.to_yaml(), encoding="utf-8")
        workflow_key = wst.workflow_relative_path(workflow_path)

        declaration_path = root / "blocking-steps.yaml"
        declaration_path.write_text(
            render_declaration(draft, workflow_key), encoding="utf-8"
        )

        report = wst.evaluate(
            directory=directory,
            declaration_path=declaration_path,
            makefile=None,
            frontend_src=root / "frontend" / "src",
            frontend_dist=root / "frontend" / "dist",
        )
    return report, workflow_key


def assert_shape_matches_draft(shape: StepShape, job_id: str, draft: StepDraft) -> None:
    """The per-step reading, compared field by field against the injected truth."""
    assert shape.job == job_id
    assert shape.step_name == draft.step_name
    # Total: exactly one side, and the side is decided by the construct.
    assert shape.propagates_exit_status is draft.propagates_exit_status
    assert shape.propagates_exit_status is (shape.discarding_construct is None)
    # The construct is rediscovered from the YAML, not restated.
    assert shape.discarding_construct == draft.discarding_construct
    assert shape.advisory_in_name is draft.advisory_in_name


# ---------------------------------------------------------------------------
# The generated step space
# ---------------------------------------------------------------------------


def one_draft_per_construct() -> st.SearchStrategy[tuple[StepDraft, ...]]:
    """One step per discarding construct, so every example exercises all four."""
    return st.tuples(
        *(step_drafts(constructs=(construct,)) for construct in DISCARDING_CONSTRUCTS)
    )


# Feature: purpose-achievement-audit, Property 4: A declared-blocking step propagates
# its exit status
@given(draft=step_drafts())
def test_the_step_classification_is_total_over_the_rendered_step_space(
    draft: StepDraft,
) -> None:
    """R1.8: every step lands on exactly one side, and on the side its construct puts it.

    Totality is the point. A checker that returned "propagating" for anything it failed
    to understand would satisfy every naming obligation below and gate nothing.
    """
    shape = wst.classify_step(
        workflow=".github/workflows/ci.yml",
        job_id="job-0",
        job={"runs-on": "ubuntu-latest"},
        step=draft.as_yaml_obj(),
        index=0,
        triggers=("push:main",),
    )

    assert_shape_matches_draft(shape, "job-0", draft)

    # A function of the step: no file read, no order dependence, so a re-read agrees.
    assert (
        wst.classify_step(
            workflow=".github/workflows/ci.yml",
            job_id="job-0",
            job={"runs-on": "ubuntu-latest"},
            step=draft.as_yaml_obj(),
            index=0,
            triggers=("push:main",),
        )
        == shape
    )


@given(drafts=one_draft_per_construct())
def test_each_of_the_four_discarding_constructs_is_detected(
    drafts: tuple[StepDraft, ...],
) -> None:
    """R1.8: all four constructs of design E1.5, in one example each.

    The rendered YAML is asserted to actually contain the construct, so a construct that
    the generator failed to inject cannot be mistaken for a construct the checker
    detected.
    """
    assert len(drafts) == len(DISCARDING_CONSTRUCTS)

    for construct, draft in zip(DISCARDING_CONSTRUCTS, drafts, strict=True):
        rendered = yaml.safe_dump(draft.as_yaml_obj(), sort_keys=True, allow_unicode=False)
        assert construct in rendered, f"generator did not inject {construct!r}"

        shape = wst.classify_step(
            workflow=".github/workflows/ci.yml",
            job_id="job-0",
            job={"runs-on": "ubuntu-latest"},
            step=draft.as_yaml_obj(),
            index=0,
            triggers=("push:main",),
        )
        assert not shape.propagates_exit_status
        assert shape.discarding_construct == construct

    # The vocabulary the strategies inject is the vocabulary the gate classifies. These
    # are two independent constant tuples; a divergence would silently shrink the space.
    assert set(DISCARDING_CONSTRUCTS) == set(wst.DISCARDING_CONSTRUCTS)
    assert set(ADVISORY_MARKERS) == set(wst.ADVISORY_MARKERS)


# ---------------------------------------------------------------------------
# The three rules, over whole workflow files
# ---------------------------------------------------------------------------


@given(draft=workflow_documents())
def test_the_gate_names_file_and_step_for_every_violation_and_nothing_else(
    draft: WorkflowDraft,
) -> None:
    """R1.8, R8.9, R11.3: the findings are exactly the mandated ones, each named.

    One assertion covers all three rules because they partition the non-propagating
    steps: declared-blocking ones FAIL under ``blocking-discards``, the rest FAIL under
    ``unlabelled-advisory`` unless their name says they are advisory. Set equality is
    what makes the "and nothing else" half meaningful - it is what forbids a propagating
    step from being flagged.
    """
    report, workflow_key = evaluate_draft(draft)
    expected = expected_findings(draft, workflow_key)

    # Every step of every job was classified, in file order, as its draft says.
    pairs = draft.steps()
    assert len(report.shapes) == len(pairs)
    for shape, (job_id, step) in zip(report.shapes, pairs, strict=True):
        assert_shape_matches_draft(shape, job_id, step)

    assert actual_findings(report) == expected

    non_propagating_names = {
        step.step_name for _, step in pairs if not step.propagates_exit_status
    }
    for item in report.findings:
        # Names the file and the step - the whole naming obligation of R1.8.
        assert item.workflow == workflow_key
        assert item.step_name in non_propagating_names
        assert item.detail
        # Two rules of E1.5 cannot fire over this space; if one does, the expectation
        # above is wrong rather than merely incomplete.
        assert item.rule in {"blocking-discards", "unlabelled-advisory"}
        # The report says *what* discarded the status, not only that something did. A
        # step is identified by name (R1.8's naming obligation), so when one job holds
        # two same-named non-propagating steps the detail may name either one's
        # construct - what must hold is that it names a construct actually present
        # under that name, never an invented one.
        constructs = {
            candidate.discarding_construct
            for candidate in report.shapes
            if (candidate.job, candidate.step_name) == (item.job, item.step_name)
            and not candidate.propagates_exit_status
        }
        assert constructs
        assert any(str(construct) in item.detail for construct in constructs)

    # A declaration that resolves is never itself a finding, and the bundle assertion is
    # honestly skipped over a tree that ships no bundle (non-passing, but not a failure).
    assert len(report.declarations) == len(draft.jobs)
    assert report.bundle.status == "skip"

    if expected:
        assert report.verdict == "fail"
        assert report.verdict in NON_PASSING_VERDICTS
        assert report.reason
    else:
        assert report.verdict == "pass"


@given(
    steps=st.lists(step_drafts(constructs=(None,)), min_size=1, max_size=4).map(tuple),
    declared=st.booleans(),
)
def test_a_propagating_step_is_never_flagged(
    steps: tuple[StepDraft, ...],
    declared: bool,
) -> None:
    """The converse guard: a workflow whose every step propagates passes.

    Without this every assertion above would hold for a gate that flags everything, or
    for one that flags nothing. Declaring the steps blocking must not change the verdict:
    a declared step that *does* propagate is the case the declaration exists to protect.
    """
    marked = tuple(dataclasses.replace(step, declared_blocking=declared) for step in steps)
    draft = WorkflowDraft(
        path=".github/workflows/ci.yml",
        triggers=("push:main",),
        jobs=(JobDraft(job_id="job-0", needs=(), if_condition=None, steps=marked),),
    )

    report, _ = evaluate_draft(draft)

    assert report.findings == ()
    assert report.verdict == "pass"
    assert all(shape.propagates_exit_status for shape in report.shapes)
    assert all(shape.discarding_construct is None for shape in report.shapes)


@given(draft=step_drafts(declared_blocking=False, constructs=DISCARDING_CONSTRUCTS))
def test_an_undeclared_non_propagating_step_is_accepted_iff_it_is_labelled_advisory(
    draft: StepDraft,
) -> None:
    """R11.3: the name rule, in both directions.

    Labelled advisory work is not a dishonest gate - the audit says so explicitly - so
    the rule must accept an honest label. It must equally refuse an unlabelled one, which
    is the ``ci.yml`` "Contract tests" condition. Appending a marker to the *same* step
    flips the verdict, which is what makes the marker load-bearing rather than decorative.
    """
    report, workflow_key = evaluate_draft(one_job_workflow(draft))
    key: FindingKey = (
        "unlabelled-advisory",
        "R11.3",
        workflow_key,
        "job-0",
        draft.step_name,
    )

    assert actual_findings(report) == (set() if draft.advisory_in_name else {key})
    assert report.verdict == ("pass" if draft.advisory_in_name else "fail")

    labelled = dataclasses.replace(
        draft, step_name=f"{draft.step_name} [{ADVISORY_MARKERS[0]}]"
    )
    assert labelled.advisory_in_name
    labelled_report, _ = evaluate_draft(one_job_workflow(labelled))
    assert labelled_report.findings == ()
    assert labelled_report.verdict == "pass"


@given(draft=step_drafts(declared_blocking=True, constructs=DISCARDING_CONSTRUCTS))
def test_a_declared_blocking_step_that_discards_fails_under_the_blocking_rule(
    draft: StepDraft,
) -> None:
    """R1.8, R8.9: the declaration outranks the name.

    R8.9's ``frontend.yml`` entries are the live case: the e2e step's own name already
    carries ``informational``, so the R11.3 name rule alone would excuse it. Only the
    declaration makes R8.9 bite, which means an advisory marker must NOT downgrade a
    declared-blocking violation.
    """
    report, workflow_key = evaluate_draft(one_job_workflow(draft))

    assert actual_findings(report) == {
        ("blocking-discards", "R1.8", workflow_key, "job-0", draft.step_name)
    }
    assert report.verdict == "fail"
    assert report.findings[0].step_name == draft.step_name
    assert report.findings[0].workflow == workflow_key
    assert str(draft.discarding_construct) in report.findings[0].detail


@given(
    draft=step_drafts(declared_blocking=True),
    absent=st.text(
        alphabet=st.characters(min_codepoint=97, max_codepoint=122), min_size=1, max_size=8
    ),
)
def test_a_declaration_that_resolves_to_no_step_fails_rather_than_emptying_the_set(
    draft: StepDraft,
    absent: str,
) -> None:
    """R1.8: the declaration is the contract, so a rename cannot silently exempt a step."""
    workflow = one_job_workflow(draft)
    missing = f"{draft.step_name} {absent}"

    with tempfile.TemporaryDirectory(prefix="shape-truth-") as tmp:
        root = Path(tmp)
        directory = root / "workflows"
        directory.mkdir()
        workflow_path = directory / "ci.yml"
        workflow_path.write_text(workflow.to_yaml(), encoding="utf-8")
        workflow_key = wst.workflow_relative_path(workflow_path)
        declaration_path = root / "blocking-steps.yaml"
        declaration_path.write_text(
            yaml.safe_dump(
                {
                    "version": 1,
                    "steps": [
                        {
                            "workflow": workflow_key,
                            "job": "job-0",
                            "step_names": [missing],
                            "match": "exact",
                            "requirement": "R1.8",
                        }
                    ],
                },
                sort_keys=True,
                allow_unicode=False,
            ),
            encoding="utf-8",
        )
        report = wst.evaluate(
            directory=directory,
            declaration_path=declaration_path,
            makefile=None,
            frontend_src=root / "frontend" / "src",
            frontend_dist=root / "frontend" / "dist",
        )

    unresolved = [item for item in report.findings if item.rule == "blocking-unresolved"]
    assert len(unresolved) == 1
    assert unresolved[0].workflow == workflow_key
    assert unresolved[0].step_name == missing
    assert report.verdict in NON_PASSING_VERDICTS


# ---------------------------------------------------------------------------
# The committed tree, read statically
# ---------------------------------------------------------------------------


def test_the_committed_honest_advisory_labels_satisfy_the_name_rule() -> None:
    """R11.3 against the real workflows: ``ci.yml``'s two honest labels pass as they are.

    A static read of ``.github/workflows/`` - no workflow is executed. The gate's overall
    verdict is deliberately not asserted here: the committed tree is red today by design
    (the two chain-verify call sites and the three declared ``frontend.yml`` entries are
    honest reds that tasks 7.3 and 11.x discharge). What must hold now is narrower and is
    the whole point of R11.3: a step that says ``ADVISORY`` or ``informational`` in its
    own name is not a violation, so neither of these two steps may be named in a finding.
    """
    report = wst.evaluate()
    assert report.verdict in {"pass", *NON_PASSING_VERDICTS}

    by_key = {
        (shape.workflow, shape.job, wst.normalize_step_name(shape.step_name)): shape
        for shape in report.shapes
    }
    named = {
        (item.workflow, item.job, wst.normalize_step_name(item.step_name))
        for item in report.findings
    }

    for workflow, job, step_name in COMMITTED_ADVISORY_STEPS:
        key = (workflow, job, wst.normalize_step_name(step_name))
        shape = by_key.get(key)
        assert shape is not None, f"committed step not found: {key}"
        # Both are non-propagating by construction (one `|| true`, one continue-on-error)
        # and both say so in their names - that is the honest state, not a violation.
        assert not shape.propagates_exit_status
        assert shape.discarding_construct in wst.DISCARDING_CONSTRUCTS
        assert shape.advisory_in_name
        assert key not in named

    # Every committed declaration resolves to a real step: the declared-blocking set is
    # non-empty in effect, not just on paper (R1.8).
    assert report.declarations
    assert [item for item in report.findings if item.rule == "blocking-unresolved"] == []
