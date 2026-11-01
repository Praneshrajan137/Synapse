"""Property-based test for the required-check declaration (design E1.7).

Feature: purpose-achievement-audit, Property 12: The required-check declaration resolves
to real jobs

    *For any* (declaration, workflow set) pair, every declared job name resolves to a
    job defined in a workflow file, and any renamed or removed job fails the consistency
    check naming that job.

Why a property and not examples. R14 is a *boundary* finding: a red run only blocks a
merge because of branch-protection configuration that is not in this tree, so the
declaration in `infrastructure/quality/required-checks.yaml` is the only in-repo record
of which jobs carry that weight. A declaration is worth exactly as much as its
resolution: the moment a job id drifts, the file describes an enforcement topology the
repository no longer has, and it does so silently. A handful of examples pins the jobs
that happen to be declared today; the failure mode is the *next* rename. So the property
quantifies over generated (declaration, workflow tree) pairs and asserts resolution is
**total** there - every declared entry either resolves or is named in a finding, never
neither and never both.

Two deliberate non-behaviours are asserted as firmly as the positive ones, because both
are places where a gate could quietly stop gating:

* A ``pending:`` entry is **never** resolved. Resolving a job that has not landed would
  fail for an honest reason and make the file unable to record a future obligation at
  all. That exemption must be exactly as narrow as stated: pending entries contribute no
  finding *and* no resolution. It is asserted over generated declarations, never against
  whichever obligation is outstanding today - the committed ``pending:`` list is empty as
  of task 2.17, and an exemption that only held while some entry existed would be a
  snapshot rather than a property.
* A schema-invalid declaration **FAILs**. A structurally broken file is a repository
  defect, not an absent one, and skipping it would let a malformed declaration read as
  clean. An *absent* file is the only ``unavailable`` case (I-7: a SKIP is not a PASS,
  and neither is a file nobody could read).

Ground truth. ``tests/verify/strategies.py`` renders real GitHub-Actions-shaped YAML;
the mutation applied to the tree or the entry is the injected truth, and the gate reads
only files. Agreement is the gate rediscovering a fact it was not told.

Subject: ``scripts/audit/required_checks_truth`` (task 2.14), validated against the
*committed* ``infrastructure/quality/schemas/required-checks.schema.json`` so the schema
under test is the shipped one. Every generated example runs against a throwaway tree,
following the hermetic-roots pattern task 2.11 established: ``evaluate`` threads
``declaration_path`` / ``directory`` / ``root`` as parameters with production defaults,
so nothing here monkeypatches a module global. No workflow is executed, no subprocess is
spawned, and no GitHub API is read - the live branch-protection read is a
scheduled-workflow job by design (R14.5), never a test (I-0).

``max_examples`` is never set here - the budget comes from the root ``conftest.py``
profiles (``dev``=10, ``heavy``=100, ``ci``/``default``=500, ``nightly``=5000).

**Validates: Requirements 14.2**
"""

from __future__ import annotations

import dataclasses
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Final

import yaml
from hypothesis import given
from hypothesis import strategies as st

from scripts.audit import required_checks_truth as rct
from tests.verify.strategies import WorkflowDraft, workflow_documents

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

#: One finding, reduced to the fields R14.2 obliges it to name.
FindingKey = tuple[str, str, str, str]

#: The exit-status vocabulary a non-passing verdict may use. ``2`` is non-passing too.
NON_PASSING_VERDICTS: Final[tuple[str, ...]] = ("fail", "unavailable")

#: The two rules that mean "this declared job does not exist in the tree".
UNRESOLVED_RULES: Final[frozenset[str]] = frozenset({"workflow-missing", "job-unresolved"})

#: Every rule R14.2 can produce, i.e. the resolution half of the gate.
RESOLUTION_RULES: Final[frozenset[str]] = UNRESOLVED_RULES | {"check-name-mismatch"}

#: How a generated pair diverges from a consistent declaration, one mode per example.
MUTATIONS: Final[tuple[str, ...]] = (
    "none",
    "renamed",
    "removed",
    "workflow-missing",
    "check-name-drift",
)

#: Job display names shaped like the committed ones. The third carries ``ci.yml``'s real
#: non-ASCII em dash, so the byte-for-byte comparison is exercised on a string the
#: console has to escape before it can print it.
DISPLAY_NAMES: Final[tuple[str, ...]] = (
    "Lint + Type Check + Unit Tests",
    "Uplift Harness + Verification Properties (tests/)",
    "Chromatic System \u2014 colour gates (ADR-025)",
)

#: Job ids for ``pending:`` entries. None of these is ever written into the tree, which
#: is the point of the section: the job does not exist yet. Every generated job id is
#: ``job-<n>`` (``tests/verify/strategies.py``), so none of these can collide with one -
#: the ids are unresolvable by construction rather than by today's workflow tree.
#:
#: ``truth-gates`` stood at the head of this tuple until task 2.17 created that job and
#: promoted it into ``required:``. It was removed rather than left in place: a name that
#: now resolves in the real tree would make this tuple - and the two docstrings that
#: cite it - describe a job-that-does-not-exist using a job that does.
PENDING_JOBS: Final[tuple[str, ...]] = (
    "future-spine-gate",
    "not-yet-landed",
    "unlanded-oracle-gate",
)

#: A workflow path the generated tree never contains (R14.2's workflow-missing half).
MISSING_WORKFLOW: Final[str] = ".github/workflows/absent.yml"

#: Reasons the schema's ``ineligible`` enum admits, split by the gate into trigger facts
#: and policy judgements. Read from the gate so a widened enum widens the generated space.
INELIGIBILITY_REASONS: Final[tuple[str, ...]] = tuple(
    sorted(rct.TRIGGER_INELIGIBILITY | rct.POLICY_INELIGIBILITY)
)

#: Ways a declaration can violate its own schema. Each applies to any valid document.
SCHEMA_BREAKS: Final[tuple[str, ...]] = (
    "drop-required-key",
    "wrong-type",
    "unknown-property",
    "empty-required",
    "bad-workflow-ref",
    "drop-check-name",
)

RECONCILE_FILE: Final[str] = "required-checks-reconcile.yml"

#: The reconciliation workflow the declaration names: scheduled, and reading the declared
#: ``api_path`` with ``gh api``. Written into every generated tree so the reconciliation
#: shape rules (R14.6) contribute nothing and the verdict is a statement about resolution
#: alone. It reads nothing during this test - it is text on disk.
RECONCILE_WORKFLOW: Final[str] = """\
name: required-checks-reconcile
on:
  schedule:
    - cron: '17 6 * * 1'
jobs:
  reconcile:
    runs-on: ubuntu-latest
    steps:
      - name: Read live branch protection
        run: gh api "repos/${{ github.repository }}/branches/main/protection" > live.json
"""


# ---------------------------------------------------------------------------
# One generated (declaration, workflow tree) pair
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DeclarationCase:
    """A workflow draft, the declaration that describes it, and the injected divergence.

    ``sections`` assigns every real job to one of the three *resolved* sections;
    ``pending_jobs`` names jobs that are deliberately absent from the tree. ``mutation``
    and ``target`` are the ground truth: what was done to the pair, and to which job.
    """

    draft: WorkflowDraft
    display_names: Mapping[str, str]
    sections: Mapping[str, str]
    ineligible_reason: str
    mutation: str
    target: str
    pending_jobs: tuple[str, ...]

    @property
    def job_ids(self) -> tuple[str, ...]:
        return tuple(job.job_id for job in self.draft.jobs)

    @property
    def renamed_target(self) -> str:
        """The id the tree uses after a rename; the declaration keeps the old one."""
        return f"{self.target}-renamed"

    def display_name(self, job_id: str) -> str:
        """GitHub's rule: the job's ``name:`` when it has one, otherwise the job id."""
        return self.display_names.get(job_id) or job_id

    def declared_workflow(self, job_id: str) -> str:
        """The workflow path the declaration writes for ``job_id``."""
        if self.mutation == "workflow-missing" and job_id == self.target:
            return MISSING_WORKFLOW
        return self.draft.path

    def declared_check_name(self, job_id: str) -> str:
        """The ``check_name`` the declaration writes for ``job_id``."""
        name = self.display_name(job_id)
        if self.mutation == "check-name-drift" and job_id == self.target:
            return f"{name} [drifted]"
        return name


@st.composite
def resolution_cases(
    draw: st.DrawFn,
    *,
    mutations: Sequence[str] = MUTATIONS,
    max_pending: int = 2,
) -> DeclarationCase:
    """A (declaration, workflow tree) pair carrying exactly one divergence.

    One mutation per example keeps the counterexample readable: a failure names the
    single rename, removal, absent file, or drifted check name that caused it.

    The first job is always declared ``required`` because the schema demands a non-empty
    required set - an empty one is a schema violation, which is a different property
    (and is covered below).
    """
    draft = draw(workflow_documents())
    job_ids = tuple(job.job_id for job in draft.jobs)

    display_names: dict[str, str] = {}
    for job_id in job_ids:
        label = draw(st.none() | st.sampled_from(DISPLAY_NAMES))
        if label is not None:
            display_names[job_id] = label

    sections: dict[str, str] = {job_ids[0]: "required"}
    for job_id in job_ids[1:]:
        sections[job_id] = draw(st.sampled_from(rct.RESOLVED_SECTIONS))

    mutation: str = draw(st.sampled_from(tuple(mutations)))
    if mutation == "check-name-drift":
        # ``ineligible`` entries declare no ``check_name``, so there is nothing to drift.
        eligible = tuple(job_id for job_id in job_ids if sections[job_id] != "ineligible")
        target = draw(st.sampled_from(eligible))
    else:
        target = draw(st.sampled_from(job_ids))

    return DeclarationCase(
        draft=draft,
        display_names=display_names,
        sections=sections,
        ineligible_reason=draw(st.sampled_from(INELIGIBILITY_REASONS)),
        mutation=mutation,
        target=target,
        pending_jobs=draw(
            st.lists(st.sampled_from(PENDING_JOBS), max_size=max_pending, unique=True).map(tuple)
        ),
    )


# ---------------------------------------------------------------------------
# Rendering the pair
# ---------------------------------------------------------------------------


def render_workflow(case: DeclarationCase) -> str:
    """The generated workflow YAML, with display names attached and the mutation applied.

    ``JobDraft`` renders no ``name:``, so a job's display name is its id unless one is
    injected here - which is exactly the fallback GitHub applies and the gate mirrors.
    A removed or renamed job is also dropped from every ``needs:`` list, so the file
    stays a workflow a reader would accept; this gate never reads ``needs:`` (that is
    ``gate_surface``'s Property 11), so the fix-up is tidiness, not test scaffolding.
    """
    document = case.draft.as_yaml_obj()
    jobs = document["jobs"]
    assert isinstance(jobs, dict)

    for job_id, label in case.display_names.items():
        job = jobs[job_id]
        assert isinstance(job, dict)
        job["name"] = label

    if case.mutation in {"renamed", "removed"}:
        body = jobs.pop(case.target)
        if case.mutation == "renamed":
            jobs[case.renamed_target] = body
        for job in jobs.values():
            if not isinstance(job, dict):  # pragma: no cover - defensive
                continue
            needs = job.get("needs")
            if isinstance(needs, list):
                job["needs"] = [item for item in needs if item != case.target]

    return yaml.safe_dump(document, sort_keys=True, allow_unicode=False)


def reconciliation_block() -> dict[str, object]:
    """The honest reconciliation state: nothing has been read, so nothing is verified.

    ``status: unverified`` with a null ``live_read`` is what I-7 requires of a gate that
    performed no read. It must never contribute a passing reconciliation, and it must
    never make the in-repo resolution verdict non-passing either.
    """
    return {
        "workflow": f".github/workflows/{RECONCILE_FILE}",
        "api_path": "repos/{owner}/{repo}/branches/main/protection",
        "artifact": "required-checks-live",
        "status": "unverified",
        "live_read": {"read_at": None, "contexts": None, "strict": None},
        "policy": "generated declaration; no run has read the live configuration",
    }


def build_declaration(case: DeclarationCase) -> dict[str, object]:
    """The declaration document for one case, in the shape the committed schema fixes."""
    required: list[dict[str, object]] = []
    candidates: list[dict[str, object]] = []
    ineligible: list[dict[str, object]] = []

    for index, job_id in enumerate(case.job_ids):
        workflow = case.declared_workflow(job_id)
        section = case.sections[job_id]
        if section == "required":
            required.append(
                {
                    "job": job_id,
                    "workflow": workflow,
                    "check_name": case.declared_check_name(job_id),
                    "gates": [f"synthetic gate {index}"],
                    "rationale": "generated required entry",
                }
            )
        elif section == "candidates":
            candidates.append(
                {
                    "job": job_id,
                    "workflow": workflow,
                    "check_name": case.declared_check_name(job_id),
                    "reason": "generated candidate entry",
                }
            )
        else:
            ineligible.append(
                {
                    "job": job_id,
                    "workflow": workflow,
                    "reason": case.ineligible_reason,
                    "detail": "generated ineligible entry",
                }
            )

    document: dict[str, object] = {
        "version": 1,
        "branch": "main",
        "declared_by": "tests/verify/test_required_checks_resolution_property.py",
        "required": required,
        "reconciliation": reconciliation_block(),
    }
    if candidates:
        document["candidates"] = candidates
    if ineligible:
        document["ineligible"] = ineligible
    if case.pending_jobs:
        document["pending"] = [
            {
                "job": job_id,
                "workflow": case.draft.path,
                "check_name": None,
                "lands_in": "a later task",
                "requirement": "R14.2",
                "reason": "generated pending entry; this job does not exist yet",
            }
            for job_id in case.pending_jobs
        ]
    return document


def evaluate_case(
    case: DeclarationCase,
    *,
    document: Mapping[str, object] | None = None,
    write_declaration: bool = True,
) -> rct.RequiredChecksReport:
    """Run the gate over one generated pair in a throwaway tree.

    Every root the gate reads is pointed inside the temporary directory except the
    schema, which is deliberately the *committed* one: the structural contract under
    test is the shipped file, not a copy. The directory is removed on the way out - no
    example leaves a file behind.
    """
    with tempfile.TemporaryDirectory(prefix="required-checks-") as tmp:
        root = Path(tmp)
        directory = root / ".github" / "workflows"
        directory.mkdir(parents=True)
        (directory / case.draft.path.rsplit("/", 1)[-1]).write_text(
            render_workflow(case), encoding="utf-8"
        )
        (directory / RECONCILE_FILE).write_text(RECONCILE_WORKFLOW, encoding="utf-8")

        declaration_path = root / "required-checks.yaml"
        if write_declaration:
            payload = build_declaration(case) if document is None else dict(document)
            declaration_path.write_text(
                yaml.safe_dump(payload, sort_keys=True, allow_unicode=False), encoding="utf-8"
            )

        return rct.evaluate(declaration_path=declaration_path, directory=directory, root=root)


# ---------------------------------------------------------------------------
# The independent recompute of R14.2
# ---------------------------------------------------------------------------


def expected_findings(case: DeclarationCase) -> set[FindingKey]:
    """The findings R14.2 mandates for one case, recomputed from the injected mutation.

    Written out rather than imported from the gate, so the test compares two
    implementations. ``pending`` contributes nothing here by construction - that is the
    non-behaviour under test, not an omission.
    """
    section = case.sections[case.target]
    if case.mutation == "workflow-missing":
        return {("workflow-missing", section, MISSING_WORKFLOW, case.target)}
    if case.mutation in {"renamed", "removed"}:
        return {("job-unresolved", section, case.draft.path, case.target)}
    if case.mutation == "check-name-drift":
        return {("check-name-mismatch", section, case.draft.path, case.target)}
    return set()


def expected_resolved(case: DeclarationCase) -> set[str]:
    """The ``workflow::job`` labels that must resolve.

    A drifted ``check_name`` still resolves: the job exists, so the finding is about the
    string branch protection matches on, not about the job's existence.
    """
    return {
        f"{case.draft.path}::{job_id}"
        for job_id in case.job_ids
        if not (
            job_id == case.target
            and case.mutation in {"renamed", "removed", "workflow-missing"}
        )
    }


def ascii_display(text: str) -> str:
    """The escaping a non-ASCII display name needs before a Windows console can print it.

    Re-implemented here rather than imported, so the assertion that a finding quotes both
    names compares two implementations of the same rule (E-S13-07's console half).
    """
    return text if text.isascii() else text.encode("unicode_escape").decode("ascii")


def actual_findings(report: rct.RequiredChecksReport) -> set[FindingKey]:
    """The report's resolution findings reduced to the same tuple shape."""
    return {
        (item.rule, item.section, item.workflow, item.job)
        for item in report.findings
        if item.rule in RESOLUTION_RULES
    }


# ---------------------------------------------------------------------------
# Property 12
# ---------------------------------------------------------------------------


# Feature: purpose-achievement-audit, Property 12: The required-check declaration
# resolves to real jobs
@given(case=resolution_cases())
def test_resolution_is_total_and_names_exactly_the_divergent_jobs(
    case: DeclarationCase,
) -> None:
    """R14.2: every declared job either resolves or is named, and never both or neither.

    Totality is the point. A gate that silently dropped an entry it could not classify
    would satisfy every naming obligation below and would resolve nothing, which is
    precisely the failure R14 describes: a declaration that reads as enforcement while
    enforcing nothing.
    """
    report = evaluate_case(case)
    expected = expected_findings(case)

    assert actual_findings(report) == expected
    assert set(report.resolved) == expected_resolved(case)

    # Total: each of the three resolved sections' entries lands on exactly one side.
    declared_labels = [f"{entry.workflow}::{entry.job}" for entry in report.declared]
    unresolved = [item for item in report.findings if item.rule in UNRESOLVED_RULES]
    assert len(report.declared) == len(case.job_ids)
    assert len(report.resolved) + len(unresolved) == len(report.declared)
    assert set(declared_labels) == set(report.resolved) | {
        f"{item.workflow}::{item.job}" for item in unresolved
    }

    for item in report.findings:
        # Names the job - the whole naming obligation of R14.2 - and says what is wrong.
        assert item.job in case.job_ids
        assert item.section in rct.RESOLVED_SECTIONS
        assert item.detail
        assert item.detail.isascii()
        assert item.requirement == "R14.2"
        assert item.rule in RESOLUTION_RULES

    if expected:
        assert report.verdict == "fail"
        assert report.verdict in NON_PASSING_VERDICTS
    else:
        assert report.verdict == "pass"
    assert report.reason


@given(case=resolution_cases(mutations=("none",)))
def test_a_declaration_whose_every_job_resolves_fails_nothing(
    case: DeclarationCase,
) -> None:
    """The converse guard: a consistent pair passes, whatever its shape.

    Without this every assertion above would also hold for a gate that flags everything.
    An unverified reconciliation block must not change that - the in-repo half makes no
    claim about the live configuration, so it cannot be dragged non-passing by its
    absence (R14.5 is about the reconciliation job's own conclusion).
    """
    report = evaluate_case(case)

    assert report.findings == ()
    assert report.verdict == "pass"
    assert len(report.resolved) == len(case.job_ids)
    assert report.committed_status == "unverified"
    # An unverified committed status is never a verified match (I-7); with no reconcile
    # inputs the gate reports no reconciliation at all rather than inventing one.
    assert report.reconciliation is None


@given(case=resolution_cases(mutations=("renamed", "removed")))
def test_a_renamed_or_removed_job_fails_naming_that_job(case: DeclarationCase) -> None:
    """R14.2's core clause, in both of its spellings.

    A rename leaves the work in place under a new id; a removal takes it away. Branch
    protection cannot tell the difference - both leave it waiting for a check that will
    never report - so the gate must not either.
    """
    report = evaluate_case(case)

    unresolved = [item for item in report.findings if item.rule == "job-unresolved"]
    assert len(unresolved) == 1
    finding = unresolved[0]
    assert finding.job == case.target
    assert finding.workflow == case.draft.path
    assert finding.section == case.sections[case.target]
    assert "renamed or removed" in finding.detail
    assert report.verdict == "fail"
    assert report.verdict in NON_PASSING_VERDICTS
    assert f"{case.draft.path}::{case.target}" not in report.resolved

    # The renamed job is present in the tree under its new id, so the failure is about
    # the declaration having drifted from the tree, not about the tree having lost work.
    if case.mutation == "renamed":
        assert case.renamed_target in render_workflow(case)


@given(case=resolution_cases(mutations=("check-name-drift",)))
def test_a_check_name_that_does_not_byte_match_the_workflow_is_caught(
    case: DeclarationCase,
) -> None:
    """R14.2's rename half at the level GitHub actually matches on.

    A required status check is matched by the display string. A job that still exists
    under a drifted ``check_name`` is the worst case in this whole requirement: the job
    is green, the declaration looks resolved, and the merge waits forever. So the job
    resolves *and* the mismatch is a finding - the two are not alternatives.
    """
    report = evaluate_case(case)

    mismatches = [item for item in report.findings if item.rule == "check-name-mismatch"]
    assert len(mismatches) == 1
    finding = mismatches[0]
    assert finding.job == case.target
    assert f"{case.draft.path}::{case.target}" in report.resolved
    assert report.verdict == "fail"

    # The detail quotes both sides, ASCII-escaped: ci.yml's real em-dashed job name is
    # in the generated space, and a gate that cannot print its own finding on Windows
    # reports nothing (E-S13-07's console half).
    assert ascii_display(case.declared_check_name(case.target)) in finding.detail
    assert ascii_display(case.display_name(case.target)) in finding.detail
    assert finding.detail.isascii()

    # Byte-for-byte: the same job with the true name resolves clean.
    honest = dataclasses.replace(case, mutation="none")
    assert evaluate_case(honest).findings == ()


@given(case=resolution_cases())
def test_a_pending_entry_is_never_resolved_and_never_a_finding(
    case: DeclarationCase,
) -> None:
    """The narrow exemption, held narrow.

    ``pending`` records an obligation for a job that does not exist yet. Resolving it
    would fail honestly and make the section useless; treating it as required would be
    worse. So it must change nothing: adding pending entries, including one naming a job
    that *does* exist, must leave the findings and the resolved set byte-identical.

    Quantified over generated declarations on purpose. The committed file's only pending
    entry - ``ci.yml::truth-gates`` - was discharged by task 2.17, and a test that had
    read the exemption off that entry would now be asserting nothing. ``PENDING_JOBS``
    holds ids no tree contains, and ``case.target`` is a job the generated tree *does*
    contain, so both sides of "pending changes nothing" are exercised on every example.
    """
    without = evaluate_case(dataclasses.replace(case, pending_jobs=()))
    with_pending = evaluate_case(
        dataclasses.replace(case, pending_jobs=(*PENDING_JOBS, case.target))
    )

    assert with_pending.findings == without.findings
    assert with_pending.resolved == without.resolved
    assert with_pending.verdict == without.verdict

    # A pending entry is recorded and named, and is not a declared (resolved) entry -
    # not even the one whose job id really is in the tree.
    assert len(with_pending.pending) == len(PENDING_JOBS) + 1
    assert set(with_pending.pending) == {
        f"{case.draft.path}::{job_id}" for job_id in (*PENDING_JOBS, case.target)
    }
    assert all(entry.section != "pending" for entry in with_pending.declared)
    assert all(item.section != "pending" for item in with_pending.findings)
    for job_id in PENDING_JOBS:
        assert f"{case.draft.path}::{job_id}" not in with_pending.resolved
    assert any("pending" in note for note in with_pending.notes)


@given(case=resolution_cases(mutations=("none",)), break_kind=st.sampled_from(SCHEMA_BREAKS))
def test_a_schema_invalid_declaration_fails_rather_than_being_skipped(
    case: DeclarationCase,
    break_kind: str,
) -> None:
    """R14.1 as the precondition of R14.2: a broken declaration is a defect, not a skip.

    The file is committed to this tree, so a malformed one is something the repository
    did, and reporting it unavailable would let it read as "nothing to check here". The
    contrast case is at the bottom: an *absent* file is the only unavailable one.
    """
    document = build_declaration(case)
    required = document["required"]
    assert isinstance(required, list)

    if break_kind == "drop-required-key":
        del document["branch"]
    elif break_kind == "wrong-type":
        document["version"] = "one"
    elif break_kind == "unknown-property":
        document["enforced"] = True
    elif break_kind == "empty-required":
        document["required"] = []
    elif break_kind == "bad-workflow-ref":
        required[0]["workflow"] = "workflows/ci.yml"
    else:
        del required[0]["check_name"]

    report = evaluate_case(case, document=document)

    schema_invalid = [item for item in report.findings if item.rule == "schema-invalid"]
    assert schema_invalid, f"{break_kind} was accepted by the committed schema"
    assert report.verdict == "fail"
    assert report.verdict != "unavailable"
    for item in schema_invalid:
        assert item.requirement == "R14.1"
        assert item.detail
        assert item.detail.isascii()


@given(case=resolution_cases(mutations=("none",)))
def test_an_absent_declaration_is_unavailable_not_a_pass(case: DeclarationCase) -> None:
    """I-7's half of the same coin: a file nobody could read verifies nothing.

    ``unavailable`` rather than ``fail`` because no job was checked, and non-passing
    either way - absence of proof is never a pass.
    """
    report = evaluate_case(case, write_declaration=False)

    assert report.verdict == "unavailable"
    assert report.verdict in NON_PASSING_VERDICTS
    assert report.resolved == ()
    assert report.findings == ()
    assert "could not be checked" in report.reason


# ---------------------------------------------------------------------------
# The committed declaration, read against the committed tree
# ---------------------------------------------------------------------------


def test_the_committed_declaration_resolves_against_the_committed_workflows() -> None:
    """R14.2 against the real files: a static read of the committed pair, no execution.

    What must hold today is exactly R14.2: every job the committed declaration names in
    a resolved section exists in the workflow it names, under the display string branch
    protection would match - and the reconciliation block must still read as
    ``unverified`` with no live read, because no run has performed one (I-7).

    ``truth-gates`` is the entry this test used to pin the other way round. It stood
    under ``pending:`` at ``.github/workflows/ci.yml`` until task 2.17, which created
    the job and promoted it into ``required:``. Both halves of that entry moved: the
    job exists, so it must now RESOLVE, and it lives in
    ``.github/workflows/truth-gates.yml`` rather than ``ci.yml`` because CF-2's "split
    the triggers" is only expressible by splitting the file - ``paths-ignore`` is a
    property of ``on.push`` and a job cannot opt out of its workflow's filter. Pinning
    the transient state here was the merge-blocking half of that landing: this module
    runs in ``uplift-verify``, itself a declared required check.

    The exemption itself - a ``pending`` entry is never resolved - is not asserted
    here. It is asserted over generated pairs above, which is where it belongs: it
    must hold for any declaration, not only for whichever obligation happens to be
    outstanding today. ``pending:`` is empty in the committed file precisely because
    the one entry it carried was discharged.
    """
    report = rct.evaluate()

    resolution = [item for item in report.findings if item.rule in RESOLUTION_RULES]
    assert resolution == [], f"committed declaration does not resolve: {resolution}"
    assert report.resolved
    assert len(report.resolved) == len(report.declared)

    # The promoted job resolves, in its own workflow file, and is declared required.
    assert ".github/workflows/truth-gates.yml::truth-gates" in report.resolved
    assert ".github/workflows/truth-gates.yml::truth-gates" not in report.pending
    required = [entry for entry in report.declared if entry.job == "truth-gates"]
    assert len(required) == 1
    assert required[0].section == "required"
    assert required[0].workflow == ".github/workflows/truth-gates.yml"

    # An unverified committed status never reads as a verified match, and this gate makes
    # no live claim at all: only a run of the reconciliation workflow can (R14.5, R14.6).
    assert report.committed_status == "unverified"
    assert report.reconciliation is None
    assert any("unverified" in note for note in report.notes)
