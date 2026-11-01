"""A fix under one rule that creates a finding under another is not a fix.

Feature: decision-quality-proof, task 3.4. Requirements **R4.1, R4.2, R4.10, R4.12,
R4.13**.

Scope, and what is deliberately NOT re-tested here
-------------------------------------------------

``tests/verify/test_workflow_shape_propagation_property.py`` (Property 4 of the
predecessor feature) already covers step-classification totality, detection of each of
the four discarding constructs, the naming obligation, "a propagating step is never
flagged", the advisory-label rule for undeclared steps, and a declaration that resolves to
no step. ``test_workflow_shape_readability_note.py`` (task 3.1) covers the R4.12
disclosure's *content* and the bound on its scope with examples, and
``test_declared_step_rename_property.py`` (Property 46) covers declaration resolution at
``_declared_keys`` level. None of that is repeated. This file adds what this feature
changed and what none of those three assert:

1. **The verdict is the disjunction of every rule** (R4.1). C64's verdict is not the
   ``unlabelled-advisory`` verdict; it is ``pass`` only when *all four* rules in
   ``_RULES`` plus the AD-12 bundle assertion are clean. This mattered concretely: the
   remediation for the nine recorded advisory findings involved renaming steps, and
   ``blocking-steps.yaml`` declares step names *by string*, so a rename that clears
   ``unlabelled-advisory`` and breaks a declaration trades one finding for another. The
   gate must not accept that trade, and until now nothing asserted that it does not.

2. **``final_list_element``'s narrowed reading is correct in both directions** (R4.12).
   ``effective_command_lines`` joins line continuations into one logical line - correct,
   because a backslash-continued ``gcloud compute ssh --command="a && b || true && c"``
   really is one command. But ``terminal_discarding_construct`` then ran an *unanchored*
   ``re.search`` over that whole logical line, so a ``|| true`` **anywhere inside** it
   condemned the step. That contradicts the rule the module implements everywhere else:
   only the *last* command decides the step's exit status. In ``A || true && B`` the
   shell's status is ``B``'s.

   The live instance was ``cd-gcp.yml`` ``deploy-to-vm``::"Pull + restart stack", whose
   remote chain suppresses four intermediate housekeeping commands and then ends with a
   ``docker compose ... images | xargs docker inspect`` whose status *is* the step's.
   Attaching an ``ADVISORY`` marker to a deploy step that does propagate would have been a
   false label (I-7), so the reading was corrected and the workflow was not touched.

3. **The narrowing did not weaken R6.13**, which is the regression it could have
   introduced and the reason ``_chain_verifier_swallow`` exists. R11.3 asks whether the
   *step* propagates; R6.13 asks whether *the audit-chain verifier's own* exit code
   reaches the step's. Those are different questions with different answers: in
   ``... audit.cli verify || echo warn && something`` the step exits with ``something``'s
   status - so it propagates, and R11.3 is satisfied - while the verifier's failure has
   been discarded. Narrowing the R6.13 search the way R11.3's was narrowed would have
   turned a correctness fix into a silent loss of enforcement. This file pins the
   distinction so nobody unifies the two searches later.

4. **A label attaches by construct scope** (R4.2), which had no coverage anywhere in the
   suite - a grep for ``job_display_names``, ``_advisory_in``, ``(all steps)`` over
   ``tests/**/*.py`` returned nothing. Half of the rule was therefore unasserted: a
   job-scoped ``continue-on-error`` is excused by the **job's display name**, not the
   step's (precedent ``ci.yml``'s ``v4-compliance``, whose steps carry no marker at all),
   and it is reported **once** as ``(all steps)``. The two cross pairs are what make it a
   scoping rule rather than a search, and they are asserted in both directions.

5. **Clearing one rule by creating another is still a fail** (R4.10), asserted at the
   verdict, not at the resolver. Property 46 proves a renamed step's declaration stops
   resolving; this proves the resulting *verdict* is non-passing even though the rename
   genuinely silenced ``unlabelled-advisory``. Those are different claims: a gate could
   resolve declarations perfectly and still pass if it derived its verdict from one rule.

6. **``unavailable`` is non-passing and exits 2** (I-7). An unreadable declared-blocking
   set and an empty step set are both constructed, because both are tempting silent
   no-ops - with no declarations there is nothing to check, so a naive gate reports a
   clean tree.

What would falsify these properties
-----------------------------------

* Deriving the verdict from one rule: the disjunction property fails.
* Restoring the unanchored search in ``terminal_discarding_construct``: the
  ``discards_before_the_final_element`` property fails.
* Anchoring ``_chain_verifier_swallow`` to the final element: the R6.13 property fails.
* Making the advisory-marker match case-sensitive: the marker property fails on the
  committed ``informational`` / ``ADVISORY`` mix, which uses both cases in the tree.
* Reading the step name for a job-scoped construct, or the job name for a step-scoped
  one: the scoping property fails on the cross pairs.
* Promoting an R4.12 note to a finding: the note property's two-tree comparison fails.
* Mapping ``unavailable`` to exit 0: the exit-code table pin fails.

``max_examples`` is never set here - the budget comes from the root ``conftest.py``
profiles via ``HYPOTHESIS_PROFILE``. This file reads and writes text and calls pure
functions; it drives no browser, no SimPy twin and no subprocess, so it is deliberately
**not** ``slow``-marked and runs in ``ci.yml::uplift-verify``'s fast step.

**Validates: Requirements 4.1, 4.2, 4.10, 4.12, 4.13**
"""

from __future__ import annotations

import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Final

import yaml
from hypothesis import given
from hypothesis import strategies as st

from scripts.audit import workflow_shape_truth as wst
from tests.verify.strategies import ADVISORY_MARKERS, workflow_documents
from tests.verify.test_workflow_shape_propagation_property import actual_findings, evaluate_draft

#: Commands that decide their own exit status - i.e. carry no discarding construct.
_PROPAGATING_COMMANDS: Final[tuple[str, ...]] = (
    "pytest -q",
    "make verify-claims",
    "docker compose ps --format json | xargs docker inspect",
    "python -m scripts.audit.registry_gate --check",
    "pnpm typecheck",
)

#: The list separators the shell uses to sequence commands. Single ``|`` is excluded on
#: purpose and the exclusion is asserted below: a pipeline's status is its last stage's,
#: so a pipe does not begin a new list element.
_SEPARATORS: Final[tuple[str, ...]] = ("&&", "||", ";")

#: The **shell-level** discarding constructs, derived from the gate's own pattern table
#: rather than restated, so a new pattern is exercised the moment it is declared.
#:
#: Deliberately NOT ``strategies.DISCARDING_CONSTRUCTS``, and the difference is the point.
#: That tuple carries four members, and the fourth - ``continue-on-error: true`` - is a
#: **YAML step key**, not shell text. It discards a step's exit status at the workflow
#: level, where ``classify_step`` reads it; it is invisible to
#: ``terminal_discarding_construct``, which reads the ``run:`` script. Feeding it to a
#: shell-text property asserts that the script reader should find a construct that is not
#: in the script, which is why the first draft of this file failed. Two levels, two
#: readers, and conflating them is exactly the confusion these properties exist to
#: prevent.
_SHELL_DISCARDS: Final[tuple[str, ...]] = tuple(
    construct for construct, _pattern in wst._TERMINAL_DISCARD_PATTERNS
)


# ---------------------------------------------------------------------------
# R4.12: only the final list element decides the step's exit status
# ---------------------------------------------------------------------------


# Feature: decision-quality-proof, Property 45: The shape verdict is the disjunction of every rule, and a label attaches by construct scope  # noqa: E501
@given(
    prefix=st.lists(
        st.tuples(st.sampled_from(_PROPAGATING_COMMANDS), st.sampled_from(_SHELL_DISCARDS)),
        min_size=1,
        max_size=4,
    ),
    final=st.sampled_from(_PROPAGATING_COMMANDS),
    separator=st.sampled_from(_SEPARATORS),
)
def test_discards_before_the_final_element_do_not_condemn_the_step(
    prefix: list[tuple[str, str]],
    final: str,
    separator: str,
) -> None:
    """A masked intermediate command is not a masked step. This is the cd-gcp case.

    Built to be adversarial about the old behaviour: **every** element before the last
    carries a discarding construct, and there may be four of them. Under the unanchored
    search every one of these scripts was a finding; under the corrected reading none of
    them is, because the shell's exit status is the final element's.
    """
    masked = " ".join(f"{command} {construct}" for command, construct in prefix)
    script = f"{masked} {separator} {final}"

    assert wst.terminal_discarding_construct(script) is None, (
        f"a discard before the final element must not condemn the step; script={script!r}"
    )


@given(
    prefix=st.lists(st.sampled_from(_PROPAGATING_COMMANDS), min_size=0, max_size=3),
    construct=st.sampled_from(_SHELL_DISCARDS),
)
def test_a_discard_in_the_final_element_is_always_found(
    prefix: list[str],
    construct: str,
) -> None:
    """The other direction, and the one that keeps the gate a gate.

    Narrowing a search is only safe if it still finds what it was built to find. Without
    this clause the R4.12 fix could have been "return None always", which satisfies the
    property above perfectly.
    """
    head = "".join(f"{command} && " for command in prefix)
    script = f"{head}deploy.sh {construct}"

    assert wst.terminal_discarding_construct(script) is not None, (
        f"a discard in the final position must be found; script={script!r}"
    )


@given(st.text(max_size=120))
def test_final_list_element_is_total_and_returns_a_suffix(line: str) -> None:
    """Structural guarantees, so the narrowing cannot lose or invent text.

    A suffix and never a rewrite: if the returned tail were transformed, the discard
    patterns would be matching against something the workflow does not contain, and every
    finding's ``detail`` would be describing a string nobody wrote.
    """
    tail = wst.final_list_element(line)

    assert isinstance(tail, str)
    # The tail is a suffix of the line modulo the trailing quote/space stripping the
    # function documents, so compare against the stripped line rather than the raw one.
    assert line.rstrip("\"'").rstrip().endswith(tail.rstrip("\"'").rstrip()) or tail == line


@given(
    left=st.sampled_from(_PROPAGATING_COMMANDS),
    right=st.sampled_from(_PROPAGATING_COMMANDS),
)
def test_a_pipe_does_not_begin_a_new_list_element(left: str, right: str) -> None:
    """``a | b`` is one pipeline whose status is ``b``'s, not a two-element list.

    Asserted because ``_LIST_SEPARATOR_RE`` deliberately matches ``||`` and not ``|``, and
    a later "simplification" of that regex to include the single pipe would silently
    change which text the discard patterns see.
    """
    assert wst.final_list_element(f"{left} | {right}") == f"{left} | {right}"


@given(terminator=st.sampled_from(sorted(wst._BLOCK_TERMINATORS)))
def test_a_block_terminator_is_read_from_the_whole_line_not_the_tail(terminator: str) -> None:
    """``fi`` is a property of the line, not of its final list element.

    The narrowing applies **only** to the discard search. The block-terminator and
    conditional-head tests still read the whole logical line, which is what keeps the
    ``frontend.yml::e2e-visual`` case classified as propagating: its ``|| true`` sits on a
    command inside an ``if`` block and the script's last effective line is ``fi``. That is
    the entry the recorded debt list over-stated by one, and this clause is why.
    """
    script = f"if [ -d baselines ]; then\n  pnpm test:visual:update || true\n{terminator}"

    assert wst.terminal_discarding_construct(script) is None


# ---------------------------------------------------------------------------
# R6.13 is not collateral damage of the R4.12 narrowing
# ---------------------------------------------------------------------------


@given(
    verifier=st.sampled_from(wst.CHAIN_VERIFIER_PATTERNS),
    construct=st.sampled_from(_SHELL_DISCARDS),
    trailing=st.sampled_from(_PROPAGATING_COMMANDS),
)
def test_a_swallowed_verifier_is_found_even_when_the_step_propagates(
    verifier: str,
    construct: str,
    trailing: str,
) -> None:
    """The distinction R11.3 and R6.13 do not share, made mechanical.

    The script below **propagates**: its final element is ``trailing``, which decides the
    exit status, so ``terminal_discarding_construct`` correctly returns ``None`` and R11.3
    is satisfied. And the verifier's own failure is nonetheless gone. Both halves are
    asserted together, because it is precisely their coexistence that a unified search
    would destroy.
    """
    script = f"{verifier} {construct} && {trailing}"

    assert wst.terminal_discarding_construct(script) is None, (
        "the step's own exit status is the trailing command's"
    )
    assert wst._chain_verifier_swallow(script) is not None, (
        "R6.13: the verifier's exit code was discarded mid-list and must still be found; "
        f"script={script!r}"
    )


@given(
    verifier=st.sampled_from(wst.CHAIN_VERIFIER_PATTERNS),
    construct=st.sampled_from(_SHELL_DISCARDS),
)
def test_a_discard_before_the_verifier_does_not_implicate_it(
    verifier: str,
    construct: str,
) -> None:
    """The bound on the R6.13 search: a discard that precedes the verifier cannot mask it.

    Without the bound the rule would be "any discard anywhere in a script that mentions
    the verifier", which would flag the honest case where an unrelated preparatory command
    is best-effort and the verifier itself is blocking.
    """
    script = f"mkdir -p artifacts {construct} && {verifier}"

    assert wst._chain_verifier_swallow(script) is None


# ---------------------------------------------------------------------------
# R4.1: the verdict is the disjunction of every rule
# ---------------------------------------------------------------------------


@given(workflow_documents())
def test_the_verdict_is_pass_exactly_when_no_rule_reports_a_finding(draft: object) -> None:
    """R4.1: one clean rule is not a clean gate.

    ``evaluate_draft`` is imported from the predecessor's property test rather than
    reimplemented: it renders the draft and its declaration into a temporary tree and
    calls ``wst.evaluate`` with every path pointed at that tree. A second copy of that
    machinery would be a second thing to drift, and the point of this property is the
    verdict, not the plumbing.
    """
    report, workflow_key = evaluate_draft(draft)  # type: ignore[arg-type]

    if report.verdict == "unavailable":
        # A tree the gate could not read is a separate verdict with its own reason, and
        # it is non-passing either way (I-7). It is not evidence about the rules. This
        # space cannot actually produce it - `workflow_documents` draws at least one job
        # with at least one step, and `render_declaration` always emits a resolvable
        # entry - so the verdict is constructed and asserted explicitly further down
        # rather than left to a branch that never runs.
        assert report.reason
        return

    assert (report.verdict == "pass") == (report.findings == ()), (
        f"verdict={report.verdict} with {len(report.findings)} finding(s): the verdict must "
        "be the disjunction of every rule, so a fix under one rule that creates a finding "
        f"under another is not a fix; rules seen={sorted({f.rule for f in report.findings})}"
    )
    # Every finding attributes itself to a declared rule. An unrecognised rule name would
    # make a finding unattributable, which R4.13's per-rule accounting cannot survive.
    for finding in report.findings:
        assert finding.rule in wst._RULES, f"finding under unknown rule {finding.rule!r}"
        assert finding.step_name is not None
        assert finding.detail, "R1.8: every finding names what is wrong"
        # Attribution: `evaluate` takes every root as a parameter precisely so a caller
        # pointing at a generated tree gets a verdict about THAT tree. A finding naming
        # this repository's own `Makefile` or a committed workflow would be a verdict
        # about the wrong subject, and no amount of fixing the generated tree would clear
        # it.
        assert finding.workflow == workflow_key, (
            f"finding names {finding.workflow!r}, which is outside the generated tree "
            f"({workflow_key!r}) - the verdict would be unattributable"
        )
    # The generated tree ships no bundle, so the AD-12 assertion is honestly skipped:
    # non-passing, but not a failure, and never a contributor to these findings.
    assert report.bundle.status == "skip"


def test_every_declared_rule_can_be_reported_and_none_is_vestigial() -> None:
    """The rule set is exactly four, and the disjunction covers all of them.

    Pinned as a committed fact because ``_RULES`` is what the property above quantifies
    over: a fifth rule added without extending the verdict derivation would be a rule
    nothing enforces, and a rule deleted without removing its findings would make them
    unattributable.
    """
    assert wst._RULES == (
        "blocking-discards",
        "blocking-unresolved",
        "chain-verifier-discards",
        "unlabelled-advisory",
    )


# ---------------------------------------------------------------------------
# R4.2 / R4.10: a label attaches by construct scope, case-insensitively
# ---------------------------------------------------------------------------


@given(
    marker=st.sampled_from(wst.ADVISORY_MARKERS),
    prefix=st.text(alphabet="abc ", max_size=8),
    suffix=st.text(alphabet="abc ", max_size=8),
)
def test_an_advisory_marker_matches_case_insensitively_anywhere_in_the_name(
    marker: str,
    prefix: str,
    suffix: str,
) -> None:
    """R4.10: the committed tree uses both cases, so the match must accept both.

    ``ci.yml`` carries ``(... - informational, target=blocking)`` and
    ``(I-1 - ADVISORY, non-blocking)``; the steps labelled by this feature use
    ``(informational - best-effort, ...)`` and ``(ADVISORY - not yet blocking)``. A
    case-sensitive match would accept some honest labels and reject others, which would
    push authors toward a specific capitalisation for a reason no requirement states.

    The gate's own reader is called. An earlier draft of this clause asserted
    ``any(m.lower() in name.lower() for m in wst.ADVISORY_MARKERS)``, which restates the
    implementation inside the test and therefore holds no matter what
    :func:`~scripts.audit.workflow_shape_truth._advisory_in` does - a tautology that
    would have survived the rule being made case-sensitive. What is asserted now is that
    the gate recognises the marker, and that a name carrying none is refused.
    """
    for cased in (marker.lower(), marker.upper(), marker.capitalize()):
        name = f"{prefix}({cased}){suffix}"
        assert wst._advisory_in(name), f"marker {cased!r} must be recognised in {name!r}"

    # The other direction, which is what makes the marker load-bearing rather than
    # decorative. The alphabet these come from cannot spell either marker word.
    assert not wst._advisory_in(f"{prefix}Gate{suffix}")

    # `strategies.py:433` mirrors the gate's tuple. Pinned as an ORDERED equality, not a
    # set one: `ADVISORY_MARKERS[0]` and `[1]` are interpolated by index into the
    # `unlabelled-advisory` finding's detail, so a reordering would change published
    # output. The sibling propagation test pins the same pair as sets; keeping the
    # stronger form here means neither spelling can drift without a red test.
    assert tuple(ADVISORY_MARKERS) == tuple(wst.ADVISORY_MARKERS)


# ---------------------------------------------------------------------------
# A tree renderer for the three shapes `WorkflowDraft` cannot express
# ---------------------------------------------------------------------------
#
# `evaluate_draft` is still the right tool for the whole-tree disjunction property
# above, and it is used there. It cannot express what the rest of this file needs:
#
# * `JobDraft.as_yaml_obj` emits no `name:` key, so a generated job has no display name
#   distinct from its id - and the job display name is exactly what R4.2's scoping rule
#   reads to excuse a job-scoped construct (`ci.yml`'s `v4-compliance` precedent).
# * It emits no job-level `continue-on-error:`, so no generated step can carry a
#   job-scoped construct at all. Half of R4.2 is unreachable through it.
# * `render_declaration` derives the declaration from each draft's own
#   `declared_blocking` flag, so every declared name is a real step by construction.
#   `blocking-unresolved` therefore cannot fire, which is the rule R4.10's laundering
#   case turns on.
#
# So this is additive, not a second copy of the same machinery. Both renderers write into
# a `tempfile.TemporaryDirectory` and point every `evaluate` root inside it, because a
# verdict about a generated tree that leaked this repository's `Makefile` or `frontend/`
# state would be unattributable.


@dataclass(frozen=True)
class _Step:
    """One rendered step. ``run`` is the script verbatim - nothing is inferred from it."""

    name: str
    run: str
    continue_on_error: bool = False

    def as_yaml_obj(self) -> dict[str, object]:
        step: dict[str, object] = {"name": self.name, "run": self.run}
        if self.continue_on_error:
            step["continue-on-error"] = True
        return step


@dataclass(frozen=True)
class _Job:
    """One rendered job, with the two keys the scoping rule turns on."""

    job_id: str
    steps: tuple[_Step, ...]
    #: The job's ``name:``. ``None`` renders no key, and the gate then falls back to the
    #: job id as the display name (``job_display_names``).
    display_name: str | None = None
    continue_on_error: bool = False

    def as_yaml_obj(self) -> dict[str, object]:
        job: dict[str, object] = {"runs-on": "ubuntu-latest"}
        if self.display_name is not None:
            job["name"] = self.display_name
        if self.continue_on_error:
            job["continue-on-error"] = True
        job["steps"] = [step.as_yaml_obj() for step in self.steps]
        return job


@dataclass(frozen=True)
class _Declaration:
    """One ``blocking-steps.yaml`` ``steps:`` entry, with the workflow key filled in later."""

    job: str
    step_names: tuple[str, ...] = ()
    all_steps: bool = False
    match: str = "exact"
    requirement: str = "R1.8"


def _evaluate_tree(
    jobs: tuple[_Job, ...],
    declarations: tuple[_Declaration, ...],
    *,
    write_declaration: bool = True,
) -> tuple[wst.ShapeReport, str]:
    """Run the gate over one rendered tree in a throwaway directory.

    ``jobs=()`` renders a workflow with no jobs, which is how the empty-step-set
    ``unavailable`` verdict is reached; ``declarations=()`` renders an empty ``steps:``
    list and ``write_declaration=False`` omits the file, which are the two ways the
    declared-blocking set is unreadable. All three are non-passing states this gate owes
    an honest report on (I-7), so they are constructed rather than assumed.
    """
    document: dict[str, object] = {
        "name": "generated",
        "on": {"push": {"branches": ["main"]}},
        "jobs": {job.job_id: job.as_yaml_obj() for job in jobs},
    }
    with tempfile.TemporaryDirectory(prefix="shape-disjunction-") as tmp:
        root = Path(tmp)
        directory = root / "workflows"
        directory.mkdir()
        workflow_path = directory / "generated.yml"
        workflow_path.write_text(
            yaml.safe_dump(document, sort_keys=True, allow_unicode=False), encoding="utf-8"
        )
        workflow_key = wst.workflow_relative_path(workflow_path)

        declaration_path = root / "blocking-steps.yaml"
        if write_declaration:
            declaration_path.write_text(
                yaml.safe_dump(
                    {
                        "version": 1,
                        "steps": [
                            {
                                "workflow": workflow_key,
                                "job": declaration.job,
                                "step_names": list(declaration.step_names),
                                "all_steps": declaration.all_steps,
                                "match": declaration.match,
                                "requirement": declaration.requirement,
                            }
                            for declaration in declarations
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
    return report, workflow_key


def _rules_reported(report: wst.ShapeReport) -> set[str]:
    """The set of rules that produced at least one finding."""
    return {finding.rule for finding in report.findings}


#: A job holding one propagating, declared step. Every tree below carries it, for one
#: reason: `blocking-steps.yaml` with an empty `steps:` list is `unavailable` and a
#: declaration naming an absent step is a `blocking-unresolved` finding, so a tree that
#: means to isolate one rule still needs a declaration that resolves to something clean.
_ANCHOR_JOB: Final[str] = "anchor"
_ANCHOR_STEP: Final[str] = "Ruff lint"
_ANCHOR: Final[_Job] = _Job(
    job_id=_ANCHOR_JOB, steps=(_Step(name=_ANCHOR_STEP, run="ruff check ."),)
)
_ANCHOR_DECLARATION: Final[_Declaration] = _Declaration(job=_ANCHOR_JOB, step_names=(_ANCHOR_STEP,))

#: The step-level YAML key, which is a discarding construct at a different level from the
#: three shell ones. Kept separate from `_SHELL_DISCARDS` for the reason that tuple's
#: comment gives: two levels, two readers, and conflating them is a category error.
_STEP_KEY_DISCARD: Final[str] = "continue-on-error: true"

#: Every step-scoped construct: the three shell ones plus the step-level YAML key.
_STEP_SCOPED_DISCARDS: Final[tuple[str, ...]] = (*_SHELL_DISCARDS, _STEP_KEY_DISCARD)


def _discarding_step(name: str, construct: str) -> _Step:
    """A step that does not propagate, via *construct* at step scope."""
    if construct == _STEP_KEY_DISCARD:
        return _Step(name=name, run="pytest -q", continue_on_error=True)
    return _Step(name=name, run=f"pytest -q {construct}")


# ---------------------------------------------------------------------------
# R4.2: a label attaches in the scope that owns the construct, and nowhere else
# ---------------------------------------------------------------------------


@given(
    scope=st.sampled_from(("step", "job")),
    marker=st.sampled_from(wst.ADVISORY_MARKERS),
    casing=st.sampled_from(("lower", "upper", "capitalize")),
    marked=st.lists(st.booleans(), min_size=1, max_size=3),
    marker_in_job_name=st.booleans(),
    construct=st.sampled_from(_STEP_SCOPED_DISCARDS),
)
def test_a_marker_excuses_a_step_only_from_the_name_owning_the_construct_scope(
    scope: str,
    marker: str,
    casing: str,
    marked: list[bool],
    marker_in_job_name: bool,
    construct: str,
) -> None:
    """R4.2, R4.10: the scoping half of Property 45, which nothing asserted before.

    Two scopes, two names, and the cross pairs are the point. A step-scoped construct is
    excused by the **step's** name; a job-scoped one by the **job's display name**,
    because the job - not the individual step - is what carries the construct. The
    committed precedent is ``ci.yml``'s ``v4-compliance``: its steps carry no marker at
    all, its ``continue-on-error: true`` sits at job level, and its display name is
    ``v4.0 Definitive Edition Compliance (informational)``. Reading the step name there
    would report a job whose own label is honest.

    The two negatives are what make it a scoping rule rather than a search:

    * a marker in the **job display name** does not excuse a **step-scoped** construct -
      otherwise one word on a job would silence every step in it, and R4.2's "the name
      owning the construct's scope" would mean nothing;
    * a job-scoped construct is reported **once**, as ``(all steps)``, not once per step -
      so a 40-step job does not turn one unlabelled job into 40 unattributable reds.

    The anchor job keeps the declaration resolvable and clean, so this example isolates
    ``unlabelled-advisory``: the other three rules are asserted absent rather than
    filtered out of the comparison.
    """
    casings: dict[str, str] = {
        "lower": marker.lower(),
        "upper": marker.upper(),
        "capitalize": marker.capitalize(),
    }
    cased = casings[casing]
    # "Gate" and "Nightly sweep" spell neither marker word, so a marker in a name is
    # there because this test put it there.
    names = tuple(
        f"Gate {index} ({cased})" if flag else f"Gate {index}" for index, flag in enumerate(marked)
    )
    job_display = f"Nightly sweep ({cased})" if marker_in_job_name else "Nightly sweep"

    if scope == "step":
        steps = tuple(_discarding_step(name, construct) for name in names)
        scoped = _Job(job_id="scoped", steps=steps, display_name=job_display)
    else:
        # Job-scoped: the job carries the key and every step's script propagates, so the
        # construct's scope is unambiguous. `classify_step` reads the step key first, so a
        # step-level key would shadow the job's and change what is being tested.
        steps = tuple(_Step(name=name, run="pytest -q") for name in names)
        scoped = _Job(
            job_id="scoped", steps=steps, display_name=job_display, continue_on_error=True
        )

    report, workflow_key = _evaluate_tree((scoped, _ANCHOR), (_ANCHOR_DECLARATION,))

    unmarked = tuple(name for name, flag in zip(names, marked, strict=True) if not flag)
    if scope == "step":
        # The job's label is irrelevant here, whatever it says.
        expected = {
            ("unlabelled-advisory", "R11.3", workflow_key, "scoped", name) for name in unmarked
        }
    elif marker_in_job_name or not unmarked:
        expected = set()
    else:
        expected = {("unlabelled-advisory", "R11.3", workflow_key, "scoped", "(all steps)")}

    assert actual_findings(report) == expected, (
        f"scope={scope} marker_in_job_name={marker_in_job_name} construct={construct!r} "
        f"marked={marked}: reason={report.reason}"
    )
    assert (report.verdict == "pass") == (not expected)
    # The construct's scope is visible in the report, not only in the finding count.
    for shape in report.shapes:
        if shape.job != "scoped":
            continue
        assert shape.propagates_exit_status is False
        assert str(shape.discarding_construct).endswith("(job)") is (scope == "job")
    # Isolation: the anchor resolves and propagates, no script names the chain verifier,
    # and no script is continuation-joined.
    assert _rules_reported(report) <= {"unlabelled-advisory"}
    assert report.notes == ()


# ---------------------------------------------------------------------------
# R4.1, R4.13: every rule can fire, alone and together, and each is accounted for
# ---------------------------------------------------------------------------

#: A step that invokes the audit-chain verifier and swallows *its* status mid-list while
#: the step's own status is the trailing command's. R6.13 fires; R11.3 does not.
_SWALLOWED_VERIFIER: Final[str] = (
    "python -m orchestrator.audit.cli verify || echo warn && make audit-anchor"
)


@given(
    blocking_discards=st.booleans(),
    blocking_unresolved=st.booleans(),
    chain_verifier=st.booleans(),
    unlabelled_advisory=st.booleans(),
    construct=st.sampled_from(_STEP_SCOPED_DISCARDS),
)
def test_the_verdict_is_the_disjunction_of_all_four_rules_alone_and_in_combination(
    blocking_discards: bool,
    blocking_unresolved: bool,
    chain_verifier: bool,
    unlabelled_advisory: bool,
    construct: str,
) -> None:
    """R4.1: sixteen combinations, and only one of them is a pass.

    The whole-tree property above quantifies over ``workflow_documents()``, where only
    two of the four rules can fire: every declared name is a real step there, so
    ``blocking-unresolved`` is unreachable, and no generated command names the audit
    verifier, so ``chain-verifier-discards`` is too. Asserting the disjunction over a
    space in which half the disjuncts are always false is weaker than it reads. This
    switches each rule on independently.

    The combination cases are the ones that matter, and they are why C64's row is not the
    ``unlabelled-advisory`` row: the remediation for the nine recorded advisory findings
    renamed steps, and ``blocking-steps.yaml`` declares step names by string. A gate that
    derived its verdict from one rule would have gone green on a tree where the rename
    had emptied a declaration.

    Each rule is placed on a step of its own so the fixed precedence
    (``blocking-discards`` > ``chain-verifier-discards`` > ``unlabelled-advisory``, keyed
    by workflow/job/step) cannot absorb one finding into another - precedence is a
    separate concern from the disjunction, and mixing them would make a counterexample
    ambiguous.
    """
    steps: list[_Step] = [
        _discarding_step("Contract tests", construct)
        if blocking_discards
        else _Step(name="Contract tests", run="pytest -q"),
        _Step(
            name="Chain verify",
            run=_SWALLOWED_VERIFIER
            if chain_verifier
            else "python -m orchestrator.audit.cli verify",
        ),
        _discarding_step("Size budget", construct)
        if unlabelled_advisory
        else _Step(name="Size budget", run="node scripts/size-budget.mjs"),
    ]
    declaration = _Declaration(
        job="gates",
        step_names=("Contract tests", *(("Ghost step",) if blocking_unresolved else ())),
    )

    report, workflow_key = _evaluate_tree(
        (_Job(job_id="gates", steps=tuple(steps)), _ANCHOR),
        (declaration, _ANCHOR_DECLARATION),
    )

    expected_rules = {
        rule
        for rule, switched_on in (
            ("blocking-discards", blocking_discards),
            ("blocking-unresolved", blocking_unresolved),
            ("chain-verifier-discards", chain_verifier),
            ("unlabelled-advisory", unlabelled_advisory),
        )
        if switched_on
    }

    assert _rules_reported(report) == expected_rules, (
        f"expected exactly {sorted(expected_rules)}; reason={report.reason}"
    )
    assert (report.verdict == "pass") == (not expected_rules), (
        f"verdict={report.verdict} with rules {sorted(_rules_reported(report))}: one clean "
        "rule is not a clean gate"
    )
    assert report.verdict in {"pass", "fail"}, "this tree is readable, so never unavailable"

    # R4.13: the reason accounts for each rule separately, so a finding is attributable
    # to the rule that produced it. `gate_fault_injection` reads this string for C64 and
    # nothing else, so an unaccounted rule is a finding no downstream reader can see.
    for rule in expected_rules:
        count = sum(1 for finding in report.findings if finding.rule == rule)
        assert f"{rule}={count}" in report.reason, (
            f"reason must account for {rule} separately; reason={report.reason}"
        )
    if not expected_rules:
        for rule in wst._RULES:
            assert rule not in report.reason

    # Findings arrive grouped by rule precedence, which is what makes the per-rule
    # accounting above readable in the console output rather than interleaved.
    positions = [wst._RULES.index(finding.rule) for finding in report.findings]
    assert positions == sorted(positions)
    assert all(finding.workflow == workflow_key for finding in report.findings)
    # Nothing in this tree is continuation-joined, so R4.12's disclosure stays silent.
    assert report.notes == ()


# ---------------------------------------------------------------------------
# R4.10: clearing one rule by creating another is not a fix
# ---------------------------------------------------------------------------


@given(
    construct=st.sampled_from(_STEP_SCOPED_DISCARDS),
    marker=st.sampled_from(wst.ADVISORY_MARKERS),
    match=st.sampled_from(("exact", "normalized")),
)
def test_relabelling_a_declared_step_trades_one_finding_for_another_and_stays_a_fail(
    construct: str,
    marker: str,
    match: str,
) -> None:
    """R4.10: the laundering case, end to end through ``evaluate``.

    The four states of the same step, in the order a maintainer would reach them:

    1. **Declared and discarding.** ``blocking-discards``. This is ``ci.yml``'s
       "Contract tests" condition after the step was promoted into the declared set.
    2. **Renamed to carry a marker, declaration left behind.** The marker does clear
       ``unlabelled-advisory`` - the step's own name now says advisory - and the
       declaration now resolves to nothing, so ``blocking-discards`` cannot fire either.
       Two rules went quiet and the verdict is still ``fail``, under
       ``blocking-unresolved``. That is the whole of Property 45 in one transition, and
       it is the mechanical reason behind the standing instruction that a rename and its
       declaration move in the same commit.
    3. **Renamed with the declaration moved.** Back to ``blocking-discards``: the marker
       does not downgrade a declared-blocking violation, so relabelling never buys a pass
       for a step somebody declared must propagate.
    4. **Made to propagate, declaration moved.** ``pass`` - the only honest exit.

    ``tests/verify/test_declared_step_rename_property.py`` (Property 46) asserts the
    resolution mechanics at ``_declared_keys`` level. What is asserted here is the
    **verdict** that the trade produces, which is a different claim: a gate could resolve
    declarations perfectly and still report a pass if it derived its verdict from one
    rule.
    """
    base = "Per-package coverage floor"
    renamed = f"{base} ({marker})"
    # Both match modes must break on the rename. `normalized` folds punctuation and
    # whitespace, never added words, so appending a marker defeats it too.
    declared_old = _Declaration(job="gates", step_names=(base,), match=match)
    declared_new = _Declaration(job="gates", step_names=(renamed,), match=match)

    def _run(step: _Step, declaration: _Declaration) -> tuple[wst.ShapeReport, str]:
        return _evaluate_tree(
            (_Job(job_id="gates", steps=(step,)), _ANCHOR),
            (declaration, _ANCHOR_DECLARATION),
        )

    before, workflow_key = _run(_discarding_step(base, construct), declared_old)
    assert actual_findings(before) == {("blocking-discards", "R1.8", workflow_key, "gates", base)}
    assert before.verdict == "fail"

    laundered, _ = _run(_discarding_step(renamed, construct), declared_old)
    assert _rules_reported(laundered) == {"blocking-unresolved"}, (
        f"match={match}: renaming a declared step must surface the broken declaration; "
        f"reason={laundered.reason}"
    )
    assert "unlabelled-advisory" not in _rules_reported(laundered), (
        "the marker did clear the advisory rule - that is the trade, and it must not pay"
    )
    assert laundered.verdict == "fail", (
        "two rules went quiet and one lit up: the disjunction must still refuse this"
    )

    moved, _ = _run(_discarding_step(renamed, construct), declared_new)
    assert _rules_reported(moved) == {"blocking-discards"}, (
        "an advisory marker must not downgrade a declared-blocking violation; "
        f"reason={moved.reason}"
    )
    assert moved.verdict == "fail"

    fixed, _ = _run(_Step(name=renamed, run="pytest -q"), declared_new)
    assert fixed.findings == (), f"the honest fix must pass; reason={fixed.reason}"
    assert fixed.verdict == "pass"


# ---------------------------------------------------------------------------
# R4.12: a note is a disclosure, so it cannot move the verdict
# ---------------------------------------------------------------------------

#: The ``cd-gcp.yml`` shape reduced to what the reading depends on: one continuation-built
#: logical line whose intermediate commands are best-effort and whose FINAL command
#: decides the step's exit status.
_MASKED_CONTINUATION: Final[str] = (
    "ssh host \\\n"
    '  --command="cd app && \\\n'
    "    compose down --remove-orphans || true && \\\n"
    '    compose up -d --force-recreate"'
)


@given(with_finding=st.booleans(), construct=st.sampled_from(_STEP_SCOPED_DISCARDS))
def test_a_note_is_never_a_finding_and_adding_one_leaves_the_verdict_untouched(
    with_finding: bool,
    construct: str,
) -> None:
    """R4.12, R4.1: the disclosure is outside the disjunction, asserted by difference.

    The same tree is evaluated twice - once with the continuation-joined step present and
    once without it - and the two verdicts and rule sets must be identical. Asserting
    "notes do not move the verdict" on a single tree can only ever show that the verdict
    happens to match the findings; comparing two trees that differ **only** by the noted
    step shows the note is not a term in the derivation at all.

    ``tests/verify/test_workflow_shape_readability_note.py`` (task 3.1) covers the
    disclosure's content and the bound on its scope with examples. This clause covers the
    one thing a content test cannot: that a note is structurally incapable of being read
    as a finding. ``ShapeNote`` carries no ``rule`` field and ``READABILITY_NOTE`` is not
    a member of ``_RULES``, so no consumer that iterates the rules can pick it up.
    """
    noted = _Step(name="Pull + restart stack", run=_MASKED_CONTINUATION)
    offender = _discarding_step("Size budget", construct)

    tail: tuple[_Step, ...] = (offender,) if with_finding else ()
    with_note, workflow_key = _evaluate_tree(
        (_Job(job_id="gates", steps=(_Step(name="Ruff lint", run="ruff check ."), noted, *tail)),),
        (_Declaration(job="gates", step_names=("Ruff lint",)),),
    )
    without_note, _ = _evaluate_tree(
        (_Job(job_id="gates", steps=(_Step(name="Ruff lint", run="ruff check ."), *tail)),),
        (_Declaration(job="gates", step_names=("Ruff lint",)),),
    )

    # The noted step really is noted, and really does propagate - otherwise the
    # comparison below would be between two trees that differ by a finding.
    assert len(with_note.notes) == 1, f"expected one R4.12 note, got {with_note.notes}"
    assert without_note.notes == ()
    noted_shape = next(shape for shape in with_note.shapes if shape.step_name == noted.name)
    assert noted_shape.propagates_exit_status
    assert noted_shape.masked_nonterminal_constructs == ("|| true",)

    assert with_note.verdict == without_note.verdict, (
        f"a note moved the verdict: {without_note.verdict} -> {with_note.verdict}"
    )
    assert _rules_reported(with_note) == _rules_reported(without_note)
    assert (with_note.verdict == "pass") == (with_note.findings == ())
    assert (with_note.verdict == "pass") == (not with_finding)

    note = with_note.notes[0]
    assert note.note == wst.READABILITY_NOTE
    assert note.note not in wst._RULES, "a note that names a rule is a finding in disguise"
    assert note.workflow == workflow_key
    # Structural, not incidental: nothing that iterates findings can reach a note, and
    # nothing that reads `.rule` can read one.
    assert wst.READABILITY_NOTE not in wst._RULES
    assert "rule" not in wst.ShapeNote.model_fields
    assert "note" not in wst.ShapeFinding.model_fields
    assert all(finding.rule != wst.READABILITY_NOTE for finding in with_note.findings)


# ---------------------------------------------------------------------------
# I-7: `unavailable` is non-passing, and exits 2
# ---------------------------------------------------------------------------


def test_the_exit_code_table_makes_unavailable_non_passing() -> None:
    """I-7 as arithmetic: only ``pass`` exits 0.

    Pinned as a committed fact because every clause below leans on it. A table that
    mapped ``unavailable`` to 0 would turn "the gate could not tell" into "the gate is
    happy", which is the exact substitution I-7 forbids, and no per-verdict assertion
    elsewhere would catch it.
    """
    assert wst._EXIT_CODES == {"pass": 0, "fail": 1, "unavailable": 2}
    assert wst._EXIT_CODES["unavailable"] != wst._EXIT_CODES["pass"]


def test_an_unreadable_declared_blocking_set_is_unavailable_rather_than_a_pass() -> None:
    """A gate that cannot read its contract has proven nothing (I-7).

    Both ways the declaration can be unreadable are covered, because they take different
    branches: an absent file and a file whose ``steps:`` list is empty. Either would be a
    tempting silent no-op - with no declarations there is nothing to check, so a naive
    gate reports a clean tree - and either is how the blocking set gets emptied by
    accident.
    """
    tree = (_Job(job_id="gates", steps=(_Step(name="Ruff lint", run="ruff check ."),)),)

    for report, label in (
        (_evaluate_tree(tree, ())[0], "empty steps: list"),
        (_evaluate_tree(tree, (_ANCHOR_DECLARATION,), write_declaration=False)[0], "absent file"),
    ):
        assert report.verdict == "unavailable", f"{label}: verdict={report.verdict}"
        # Non-passing is asserted through the exit code rather than a second
        # `!= "pass"`, which the type narrowing above makes vacuous. The exit code is
        # the substantive claim anyway: it is what the invoking job reads.
        assert wst._EXIT_CODES[report.verdict] == 2
        assert report.reason, f"{label}: an unavailable verdict must name its cause"
        # The shapes were read before the declaration was; reporting them is honest, and
        # reporting no findings is honest too - the rules were never applied.
        assert report.findings == ()
        assert report.declarations == ()


def test_an_empty_step_set_is_unavailable_rather_than_a_vacuous_pass() -> None:
    """Nothing to classify is not the same as nothing wrong.

    A workflow tree the gate reads as holding zero steps satisfies "every declared step
    propagates" vacuously. The gate refuses that reading, which is what keeps a
    misconfigured path from being indistinguishable from a clean tree.
    """
    report, _ = _evaluate_tree((), (_ANCHOR_DECLARATION,))

    assert report.verdict == "unavailable"
    assert wst._EXIT_CODES[report.verdict] == 2
    assert report.shapes == ()
    assert report.findings == ()
    assert "no workflow steps" in report.reason
