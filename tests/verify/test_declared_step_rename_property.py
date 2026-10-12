"""A declared step's rename resolves in the tree that renamed it, or it fails loudly.

Feature: decision-quality-proof, task 3.5. Requirement **R4.3**.

Why this exists, and why it is not paranoia
-------------------------------------------

``infrastructure/quality/blocking-steps.yaml`` declares which workflow steps MUST
propagate their exit status, and it declares them **by step-name string**. The converse
rule - a non-propagating step that is *not* declared must carry ``ADVISORY`` or
``informational`` in its name (R11.3) - is a *name* rule. So the remediation for an
unlabelled advisory step is very often "rename the step", and a rename is exactly what
makes a declaration resolve to nothing.

That is not a hypothetical trade. Task 3 of this feature renamed five steps to carry
advisory markers and promoted one step (``ci.yml``'s "Contract tests") into the declared
set. Had any renamed step also been declared, clearing the ``unlabelled-advisory`` finding
would have created a ``blocking-unresolved`` finding, and the gate's verdict is the
disjunction of both rules (Property 45) - so the "fix" would not have been one. Hence the
standing instruction that **a rename and its declaration move in the same commit**, and
hence this file, which pins the mechanism that makes the instruction necessary.

The design decision worth pinning: an unresolved declaration is a FAILURE, not a no-op.
The tempting alternative - silently drop a declaration that matches nothing - is how a
blocking set empties itself. Every step could be renamed, every declaration would resolve
to nothing, and the gate would report a clean tree with nothing declared blocking at all.

Scope
-----

``tests/verify/test_workflow_shape_propagation_property.py`` already asserts that a
declaration resolving to no step fails rather than emptying the set, over a rendered
workflow tree. This file works one level down, directly on ``_declared_keys``, and covers
what that test does not: the ``exact`` / ``normalized`` distinction, which is the half that
decides *whether* a given rename breaks a declaration.

The last property is the exception - it goes through ``evaluate`` end to end, because R4.3
is stated about the *gate's verdict* and a matching rule that resolved correctly under a
verdict that ignored it would satisfy every other property here.

**Nothing in this file reads the committed ``.github/workflows/`` or the committed
``blocking-steps.yaml``.** Every tree is generated, and every root ``evaluate`` reads is
pointed inside a ``TemporaryDirectory`` - which is why those roots are parameters. The
obligation about the *real* tree is C64's, discharged by
``truth-gates.yml::truth-gates``'s ``workflow_shape_truth --check`` step, which is itself
declared blocking. Asserting it a second time here would only add a test that goes red
whenever an unrelated workflow edit lands mid-sprint, reporting someone else's rename as
this property's failure.

Why the generators are shaped this way
--------------------------------------

``_declared_keys`` is pure - it takes declarations and step shapes and returns resolved
keys plus findings - so the generator produces those two things directly rather than
rendering YAML into a temporary tree. That keeps these properties fast enough to live in
``ci.yml::uplift-verify``'s fast step, and it isolates the matching rule from the parsing
rule, which has its own failure modes and its own verdict (``unavailable``).

The renames are generated from the transformations that actually happen in review:
punctuation swaps (the em dash this repo's workflow names are full of), case changes,
whitespace changes, and suffix additions like ``(informational - best-effort)``. Random
strings would technically falsify the property too, but they would not tell a reader
*which* realistic edit is dangerous, and the em-dash case is the one that surprises people.

What would falsify these properties
-----------------------------------

* Making an unmatched declaration a no-op: the ``never_empties`` property fails.
* Making ``exact`` fold punctuation: the ``exact_breaks_on_punctuation`` and
  ``strictly_stricter`` properties fail, and the one-commit rule quietly stops being
  necessary for the wrong reason.
* Making ``normalized`` fold case or arbitrary characters: the ``normalized_folds_only``
  property fails - it would start matching steps nobody declared.
* Making ``normalized`` *reject* something ``exact`` accepts: the containment property
  fails. The two modes are one rule at two tolerances, not two rules.
* Making the fold non-idempotent, or making it fold one side only: the
  ``idempotent_and_many_to_one`` property fails, and the comparison stops being
  well-defined - which side was folded first would start to matter.
* Dropping the declaring entry's ``requirement`` from the finding, or hard-coding
  ``R1.8``: the ``requirement_propagates`` property fails and the finding loses its owner.
* Collapsing "the job does not exist" into "the step does not exist": the same property
  fails on ``step_name``. Two different repairs must not share one message.
* Letting ``all_steps`` be evaded by a rename: the ``all_steps`` property fails.
* Resolving the rule correctly while ``evaluate``'s verdict ignores it: only the
  end-to-end property fails, which is why it exists.

``max_examples`` is never set here - the budget comes from the root ``conftest.py``
profiles via ``HYPOTHESIS_PROFILE``. Not ``slow``-marked: every property but the last is a
pure function call, and the last writes two small files into a ``TemporaryDirectory`` and
spawns nothing, which is the same cost shape
``test_workflow_shape_propagation_property.py`` already carries in the same fast step.

**Validates: Requirement 4.3**
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Final

import yaml
from hypothesis import given
from hypothesis import strategies as st

from scripts.audit import workflow_shape_truth as wst

_WORKFLOW: Final[str] = ".github/workflows/ci.yml"
_JOB: Final[str] = "quality-gates"

#: Step names read off the committed tree and the committed declaration file at authoring
#: time, including the punctuation that makes the ``normalized`` mode necessary in the
#: first place. **Generator inputs, not a claim about either file's current contents** -
#: nothing here is compared against the live tree, and the tree moves.
#:
#: The two ``MyPy`` entries are the two *sides* of one step, not two steps: ``ci.yml:66``
#: writes the em dash, ``blocking-steps.yaml:45`` writes the ASCII hyphen, and
#: ``match: normalized`` is what makes those the same declaration.
_REAL_STEP_NAMES: Final[tuple[str, ...]] = (
    "Contract tests",
    "Ruff lint",
    "MyPy strict type check (packages - blocking)",
    "MyPy strict type check (packages \u2014 blocking)",
    "Per-package coverage floor (Sprint 13 Phase 2)",
    "Size budget",
    "Verify deploy truth (containers)",
    "Audit-chain integrity (Sprint 9 verifier)",
)

#: The characters ``normalize_step_name`` folds, paired with what it folds them to. Read
#: off the function's own body; asserted below so a change there fails here rather than
#: silently widening what a declaration matches.
_FOLDED: Final[tuple[tuple[str, str], ...]] = (
    ("\u2014", "-"),  # em dash
    ("\u2013", "-"),  # en dash
    ("\u2212", "-"),  # minus sign
    ("\u2010", "-"),  # hyphen
    ("\u2011", "-"),  # non-breaking hyphen
    ("\u2022", "-"),  # bullet
    ("\u00b7", "-"),  # middle dot
    ("\u00a7", ""),  # section sign
)

#: The ASCII halves of a real step name in this tree, composed pairwise below rather than
#: sampled whole, so the properties cover names nobody has written yet over the
#: punctuation the committed tree actually uses: hyphens, parentheses, ``+``, ``/``, ``:``
#: and ``;``.
#:
#: The composition deliberately produces ``"TypeScript strict"`` and ``"TypeScript strict
#: (spec/ + tests/)"`` - the two frontend type-check declarations task 3.3 left in
#: ``blocking-steps.yaml`` as commented-out entries to be pasted in later, both
#: ``match: exact``. The second is the fragile shape in full (a slash, a plus, parentheses
#: and spaces under raw comparison), so it is generated now rather than waited for.
_NAME_HEADS: Final[tuple[str, ...]] = (
    "MyPy strict type check",
    "TypeScript strict",
    "Measure per-package coverage under full ML stack",
    "M8b - Sprint 6 verification",
    "Audit-chain integrity",
    "Size budget",
    "Contract tests",
)

_NAME_SCOPES: Final[tuple[str, ...]] = (
    "",
    " (packages - blocking)",
    " (spec/ + tests/)",
    " (39 + 8 invariant tests)",
    " (informational in P0; gated in P2)",
    " (Sprint 13 Phase 2)",
    ": binds the 0.0 floors",
    " - ADVISORY - binds the 0.0 floors",
)

#: Edits a reviewer cannot see on screen, each one preserving the folded form and
#: changing the raw bytes. That combination is the whole content of "``exact`` is
#: strictly stricter than ``normalized``": every one of these breaks an ``exact`` entry
#: and none of them breaks a ``normalized`` one. ``identity`` is in the list so the
#: strictness property is stated over a space that includes "nothing changed" rather
#: than assuming the negative case is the only one.
_PERTURBATIONS: Final[tuple[str, ...]] = (
    "identity",
    "em-dash",
    "en-dash",
    "minus-sign",
    "non-breaking-hyphen",
    "unicode-hyphen",
    "bullet",
    "middot",
    "section-prefix",
    "section-infix",
    "doubled-space",
    "leading-space",
    "trailing-space",
)

#: The dash rows of :data:`_FOLDED`, keyed by perturbation name. Written out rather than
#: derived from that tuple so the two disagree loudly if the fold table changes: `_FOLDED`
#: is the table read off the function, this is the table the generators drive.
_DASH_REPLACEMENTS: Final[dict[str, str]] = {
    "em-dash": "\u2014",
    "en-dash": "\u2013",
    "minus-sign": "\u2212",
    "non-breaking-hyphen": "\u2011",
    "unicode-hyphen": "\u2010",
    "bullet": "\u2022",
    "middot": "\u00b7",
}


def _perturb(name: str, kind: str) -> str:
    """Apply one invisible edit, returning *name* unchanged when it does not apply.

    Returning the input unchanged rather than rejecting the example keeps the strictness
    property total: the assertion is ``exact resolves iff the raw bytes are equal``, and
    a perturbation that could not apply is the equal case rather than a skipped one.
    """
    if kind == "identity":
        return name
    if kind == "section-prefix":
        return f"\u00a7 {name}"
    if kind == "section-infix":
        return name.replace(" ", " \u00a7 ", 1)
    if kind == "doubled-space":
        return name.replace(" ", "  ", 1)
    if kind == "leading-space":
        return f"  {name}"
    if kind == "trailing-space":
        return f"{name}  "
    return name.replace("-", _DASH_REPLACEMENTS[kind])


def ascii_step_names() -> st.SearchStrategy[str]:
    """Step names in the ASCII form ``blocking-steps.yaml`` is allowed to hold."""
    return st.builds(
        lambda head, scope: f"{head}{scope}",
        st.sampled_from(_NAME_HEADS),
        st.sampled_from(_NAME_SCOPES),
    )


def step_names() -> st.SearchStrategy[str]:
    """Every name a tree or a declaration may carry: committed, generated, perturbed."""
    return st.one_of(
        st.sampled_from(_REAL_STEP_NAMES),
        ascii_step_names(),
        st.builds(_perturb, ascii_step_names(), st.sampled_from(_PERTURBATIONS)),
    )


def _shape(step_name: str, *, propagates: bool = True) -> wst.StepShape:
    """One classified step. Only the name and the key fields matter to resolution."""
    return wst.StepShape(
        workflow=_WORKFLOW,
        job=_JOB,
        step_name=step_name,
        triggers=("push:main",),
        propagates_exit_status=propagates,
        discarding_construct=None if propagates else "|| true",
        advisory_in_name=False,
    )


def _declaration(
    *names: str,
    match: str = "normalized",
    all_steps: bool = False,
    requirement: str | None = "R1.8",
) -> wst.BlockingDeclaration:
    return wst.BlockingDeclaration(
        workflow=_WORKFLOW,
        job=_JOB,
        step_names=tuple(names),
        all_steps=all_steps,
        match="exact" if match == "exact" else "normalized",
        requirement=requirement,
    )


def _resolve(
    declarations: tuple[wst.BlockingDeclaration, ...],
    shapes: tuple[wst.StepShape, ...],
) -> tuple[frozenset[tuple[str, str, str]], tuple[wst.ShapeFinding, ...]]:
    return wst._declared_keys(declarations, shapes)


# ---------------------------------------------------------------------------
# R4.3: resolution is iff, and a failure to resolve is a finding
# ---------------------------------------------------------------------------


# Feature: decision-quality-proof, Property 46: A declared step's rename resolves in the tree that renamed it  # noqa: E501
@given(
    declared=step_names(),
    present=st.lists(step_names(), min_size=0, max_size=4, unique=True),
    match=st.sampled_from(("exact", "normalized")),
)
def test_a_declaration_resolves_exactly_when_the_tree_holds_a_matching_step(
    declared: str,
    present: list[str],
    match: str,
) -> None:
    """The biconditional. Resolution and a finding are complementary, never both, never
    neither.

    Stated as an iff rather than two implications because the dangerous failure is the
    *neither* case: a declaration that quietly resolves to nothing and reports nothing.
    """
    shapes = tuple(_shape(name) for name in present)
    keys, findings = _resolve((_declaration(declared, match=match),), shapes)

    if match == "exact":
        should_resolve = declared in present
    else:
        folded = wst.normalize_step_name(declared)
        should_resolve = any(wst.normalize_step_name(name) == folded for name in present)

    unresolved = [f for f in findings if f.rule == "blocking-unresolved"]

    assert bool(keys) == should_resolve, (
        f"declared={declared!r} match={match} present={present!r}: resolution disagrees "
        f"with the tree's contents"
    )
    assert bool(unresolved) == (not should_resolve), (
        "an unresolved declaration must produce exactly one blocking-unresolved finding, "
        f"got {len(unresolved)} for should_resolve={should_resolve}"
    )
    for finding in unresolved:
        assert finding.workflow == _WORKFLOW
        assert finding.job == _JOB
        if not present:
            # AN ABSENT JOB IS A DIFFERENT FINDING FROM AN ABSENT STEP, and the gate says
            # so: `step_name="(job)"` and a detail about the job rather than the step. The
            # distinction is worth asserting rather than generalising away, because the two
            # have different repairs - a declaration naming a job the tree does not contain
            # is usually a workflow that was split or renamed (the recorded case:
            # `truth-gates.yml`'s job was declared under `ci.yml` for a whole sprint),
            # while an absent step is a rename inside a job that exists.
            assert finding.step_name == "(job)"
            assert "resolves to no job" in finding.detail
            assert "match=" not in finding.detail
        else:
            # R1.8: the finding has to say what to fix, and name the mode it failed under -
            # "resolves to no step" is unactionable without knowing whether the comparison
            # was exact, since that is what decides whether a punctuation swap was enough.
            assert finding.step_name == declared
            assert "resolves to no step" in finding.detail
            assert f"match={match}" in finding.detail


@given(
    present=st.lists(st.sampled_from(_REAL_STEP_NAMES), min_size=1, max_size=4, unique=True),
    ghosts=st.lists(
        st.text(alphabet="abcdefg ", min_size=1, max_size=10), min_size=1, max_size=3, unique=True
    ),
    match=st.sampled_from(("exact", "normalized")),
)
def test_an_unresolved_declaration_never_empties_the_blocking_set_silently(
    present: list[str],
    ghosts: list[str],
    match: str,
) -> None:
    """The design decision: unresolved is a FAILURE, not a no-op.

    Every ghost name is one a rename could have produced. The resolved key set must still
    contain the steps that *do* match, and every ghost must be named - so the repair is
    "move the declaration", not "work out which of eight declarations went stale".
    """
    shapes = tuple(_shape(name) for name in present)
    declarations = (_declaration(*present, *ghosts, match=match),)
    keys, findings = _resolve(declarations, shapes)

    unresolved = {f.step_name for f in findings if f.rule == "blocking-unresolved"}

    assert unresolved == set(ghosts), (
        "every declaration that resolves to nothing must be named individually; "
        f"expected {sorted(ghosts)}, got {sorted(unresolved)}"
    )
    # And the real steps are still declared blocking: one stale entry must not discard the
    # rest of the entry's claims.
    assert keys == {(_WORKFLOW, _JOB, name) for name in present}


# ---------------------------------------------------------------------------
# exact vs normalized: which renames break a declaration
# ---------------------------------------------------------------------------


@given(
    base=st.one_of(st.sampled_from(_REAL_STEP_NAMES), ascii_step_names()),
    suffix=st.sampled_from(
        (
            " (informational - best-effort, preserve credits)",
            " (ADVISORY - not yet blocking)",
            " (informational in P0; gated in P2)",
        )
    ),
)
def test_a_rename_breaks_the_declaration_under_both_modes(base: str, suffix: str) -> None:
    """This is the one-commit rule's whole justification.

    An advisory-marker suffix is precisely the rename task 3 performs, and neither matching
    mode survives it - normalization folds punctuation, not added words. So renaming a
    declared step without moving its declaration in the same commit trades an
    ``unlabelled-advisory`` finding for a ``blocking-unresolved`` one, and Property 45
    proves that is not a fix.
    """
    renamed = f"{base}{suffix}"
    shapes = (_shape(renamed),)

    for match in ("exact", "normalized"):
        keys, findings = _resolve((_declaration(base, match=match),), shapes)
        assert not keys
        unresolved = [f for f in findings if f.rule == "blocking-unresolved"]
        assert unresolved, (
            f"match={match}: a renamed step must not silently satisfy its old declaration"
        )
        # The finding has to be actionable without opening the gate's source: the file,
        # the job and the string that no longer resolves. This is the failure R4.3 exists
        # to force, so what it says is part of the requirement rather than a detail.
        assert [(f.workflow, f.job, f.step_name) for f in unresolved] == [(_WORKFLOW, _JOB, base)]

    # And moving the declaration in the same commit resolves it again, which is the
    # positive half - the rule is "move both", not "never rename".
    keys, findings = _resolve((_declaration(renamed),), shapes)
    assert keys == {(_WORKFLOW, _JOB, renamed)}
    assert not [f for f in findings if f.rule == "blocking-unresolved"]


@given(original=st.sampled_from(_REAL_STEP_NAMES), swap=st.sampled_from(_FOLDED))
def test_exact_breaks_on_punctuation_alone_while_normalized_absorbs_it(
    original: str,
    swap: tuple[str, str],
) -> None:
    """R4.3's sharp edge: ``match: exact`` breaks on a character nobody can see.

    ``blocking-steps.yaml`` is ASCII-only by the Windows-console contract, while the
    workflow step names are full of em dashes. ``normalized`` exists so the declaration
    file never has to embed a non-ASCII byte; ``exact`` exists for the cd-gcp verify steps,
    where CLAUDE.md requires that a rename fail loudly. Both are correct for their purpose
    and the difference is invisible on screen, which is why it gets a property.
    """
    folded_char, replacement = swap
    tree_name = original.replace(replacement, folded_char, 1) if replacement else original
    if tree_name == original:
        # This name has nothing to swap; the property is vacuous for it.
        return

    shapes = (_shape(tree_name),)

    exact_keys, exact_findings = _resolve((_declaration(original, match="exact"),), shapes)
    assert not exact_keys, "exact must not fold punctuation"
    assert any(f.rule == "blocking-unresolved" for f in exact_findings)

    norm_keys, norm_findings = _resolve((_declaration(original, match="normalized"),), shapes)
    assert norm_keys == {(_WORKFLOW, _JOB, tree_name)}, (
        f"normalized must absorb {folded_char!r} vs {replacement!r}: "
        f"{original!r} against {tree_name!r}"
    )
    assert not [f for f in norm_findings if f.rule == "blocking-unresolved"]


@given(declared=ascii_step_names(), kind=st.sampled_from(_PERTURBATIONS))
def test_exact_is_strictly_stricter_than_normalized_under_an_invisible_edit(
    declared: str,
    kind: str,
) -> None:
    """The task-text clause, stated as an ordering rather than two anecdotes.

    Three assertions, in the order they depend on each other:

    1. **The fold absorbs the edit.** Both sides of the comparison are folded, which is
       what makes ``normalized`` sound rather than lenient - it is not a fuzzy match, it
       is exact equality on a canonical form.
    2. **``normalized`` always resolves; ``exact`` resolves iff the raw bytes are equal.**
       Stated as an iff over a perturbation space that includes ``identity``, so the
       positive case is asserted rather than assumed.
    3. **Containment.** Whatever ``exact`` resolves, ``normalized`` resolves too. That
       ordering is why ``exact`` is the mode chosen where a rename must fail loudly (the
       ``cd-gcp`` verify steps), and why ``normalized`` is the default everywhere else.
    """
    tree_name = _perturb(declared, kind)
    shapes = (_shape(tree_name),)

    assert wst.normalize_step_name(tree_name) == wst.normalize_step_name(declared), (
        f"perturbation {kind!r} is not invisible to the fold: {declared!r} -> {tree_name!r}"
    )

    exact_keys, exact_findings = _resolve((_declaration(declared, match="exact"),), shapes)
    norm_keys, norm_findings = _resolve((_declaration(declared, match="normalized"),), shapes)

    assert norm_keys == {(_WORKFLOW, _JOB, tree_name)}, (
        f"normalized must absorb {kind!r}: {declared!r} against {tree_name!r}"
    )
    assert not [f for f in norm_findings if f.rule == "blocking-unresolved"]

    raw_equal = tree_name == declared
    assert bool(exact_keys) is raw_equal, (
        f"exact must compare raw bytes: {kind!r} made {declared!r} into {tree_name!r}"
    )
    assert bool([f for f in exact_findings if f.rule == "blocking-unresolved"]) is not raw_equal

    assert exact_keys <= norm_keys, "exact resolved a key normalized did not"


@given(
    declared=st.lists(step_names(), min_size=1, max_size=3, unique=True),
    present=st.lists(step_names(), min_size=0, max_size=4, unique=True),
)
def test_normalized_resolves_every_key_exact_resolves(
    declared: list[str],
    present: list[str],
) -> None:
    """Containment over a whole tree, not one step: ``exact`` keys are a subset.

    The single-step version above could hold by accident on a one-element tree. This is
    the general statement, and it is what licenses reading ``match: exact`` as "the same
    rule, less tolerant" rather than "a different rule".
    """
    shapes = tuple(_shape(name) for name in present)
    exact_keys, _ = _resolve((_declaration(*declared, match="exact"),), shapes)
    norm_keys, _ = _resolve((_declaration(*declared, match="normalized"),), shapes)

    assert exact_keys <= norm_keys


@given(
    name=ascii_step_names(),
    left=st.sampled_from(_PERTURBATIONS),
    right=st.sampled_from(_PERTURBATIONS),
)
def test_the_fold_is_idempotent_and_many_to_one(name: str, left: str, right: str) -> None:
    """Two algebraic facts the comparison rests on.

    **Idempotent**, so it does not matter which side was folded first or how many times -
    ``_declared_keys`` folds the declaration on every declared name and the tree name on
    every shape, and a non-idempotent fold would make the result depend on that.

    **Many-to-one**, which is the honest way to say "``normalized`` is lossy". It is the
    premise of the collision case below: a fold with a smaller image than domain admits
    two raw names sharing one normal form, and something has to happen when both are in
    the tree.
    """
    folded = wst.normalize_step_name(name)
    assert wst.normalize_step_name(folded) == folded

    perturbed_left, perturbed_right = _perturb(name, left), _perturb(name, right)
    assert wst.normalize_step_name(perturbed_left) == folded
    assert wst.normalize_step_name(perturbed_right) == folded
    assert len(
        {wst.normalize_step_name(perturbed_left), wst.normalize_step_name(perturbed_right)}
    ) <= len({perturbed_left, perturbed_right})


@given(
    base=ascii_step_names(),
    kind=st.sampled_from(("em-dash", "en-dash", "doubled-space", "section-prefix")),
)
def test_a_normalized_collision_resolves_every_raw_name_that_folds_to_it(
    base: str,
    kind: str,
) -> None:
    """The collision case, asserted so a later reader knows it was considered.

    Two distinct raw step names can fold to one normal form. **The committed tree does not
    hold such a pair today** - what it holds is one step written two ways across two files
    (``ci.yml:66``'s em dash, ``blocking-steps.yaml:45``'s ASCII hyphen), which is the
    intended use of the mode. But nothing prevents the pair: two steps in one job whose
    names differ only in a dash are legal YAML and would pass review.

    **The current behaviour is that a ``normalized`` declaration naming either one resolves
    BOTH**, because the match is a filter over the job's shapes rather than a lookup, and
    ``keys.update`` takes every shape that passes it.

    That widens the declared-blocking set beyond what the declaration file names, and the
    behaviour is recorded here rather than corrected for one reason: **the widening is in
    the safe direction for this gate.** A step in the declared set is required to
    propagate; adding a propagating step to that set produces no finding, and adding a
    *discarding* step to it produces ``blocking-discards`` - which is the finding that
    step owed anyway under the R11.3 name rule. So the collision can only ever make the
    gate stricter, never more permissive.

    The cost, stated and not swept up: a reviewer cannot enumerate the declared set by
    reading ``blocking-steps.yaml`` alone, because a single ``normalized`` entry may claim
    a step nobody wrote down. ``match: exact`` is the mode that removes that ambiguity,
    and this property pins the difference.
    """
    variant = _perturb(base, kind)
    if variant == base:
        # This name has nothing for the edit to change; the collision cannot be built.
        return

    shapes = (_shape(base), _shape(variant))

    norm_keys, norm_findings = _resolve((_declaration(base),), shapes)
    assert norm_keys == {(_WORKFLOW, _JOB, base), (_WORKFLOW, _JOB, variant)}
    assert not [f for f in norm_findings if f.rule == "blocking-unresolved"]

    exact_keys, exact_findings = _resolve((_declaration(base, match="exact"),), shapes)
    assert exact_keys == {(_WORKFLOW, _JOB, base)}, "exact must not resolve the twin"
    assert not [f for f in exact_findings if f.rule == "blocking-unresolved"]


@given(
    declared=ascii_step_names(),
    requirement=st.one_of(st.none(), st.sampled_from(("R1.8", "R4.3", "R6.13", "R8.9", "R11.3"))),
    job_exists=st.booleans(),
)
def test_the_declared_requirement_propagates_and_defaults_to_r1_8(
    declared: str,
    requirement: str | None,
    job_exists: bool,
) -> None:
    """Both unresolved shapes carry the declaring entry's requirement, or the default.

    Two things are pinned together because they are read together. The **requirement**
    is what turns a finding into an obligation with an owner - ``blocking-steps.yaml``
    declares one per entry and the finding must carry it rather than restate a constant,
    and an entry that declares none falls back to ``R1.8`` (the propagation requirement
    itself, which is the weakest honest attribution).

    The **two shapes of unresolved** are distinguished by ``step_name``: ``"(job)"`` for a
    declaration naming a job the tree does not contain, the declared string for a step
    inside a job that does exist. They have different repairs - an absent job is usually a
    workflow that was split or renamed, an absent step is a rename inside it - so a gate
    that collapsed them would name the wrong fix.
    """
    shapes = (_shape("a step no declaration names"),) if job_exists else ()
    _keys, findings = _resolve(
        (_declaration(declared, requirement=requirement),),
        shapes,
    )

    unresolved = [f for f in findings if f.rule == "blocking-unresolved"]
    assert len(unresolved) == 1
    finding = unresolved[0]

    assert finding.requirement == (requirement or "R1.8")
    assert finding.workflow == _WORKFLOW
    assert finding.job == _JOB
    assert finding.step_name == ("(job)" if not job_exists else declared)


@given(name=st.sampled_from(_REAL_STEP_NAMES))
def test_normalized_folds_punctuation_and_whitespace_but_not_case(name: str) -> None:
    """The bound on normalization. Folding case would match steps nobody declared.

    Normalization is a *transcription* allowance, not a fuzzy match: it exists because one
    file is ASCII and the other is not. Case is meaningful in a step name, and a mode that
    ignored it would let ``"contract tests"`` satisfy a declaration for ``"Contract
    tests"`` - which is a different string a reviewer would have to notice.
    """
    assert wst.normalize_step_name(name.upper()) != wst.normalize_step_name(name) or (
        name.upper() == name
    )
    # Collapsed whitespace IS folded, because YAML folding and hand-editing both introduce
    # it and neither changes which step is meant.
    assert wst.normalize_step_name(f"  {name}   tail ") == wst.normalize_step_name(f"{name} tail")
    # Idempotent: normalizing a normalized name changes nothing, so the comparison cannot
    # depend on which side was folded first.
    once = wst.normalize_step_name(name)
    assert wst.normalize_step_name(once) == once


# ---------------------------------------------------------------------------
# all_steps: the wider claim, and the one a rename cannot evade
# ---------------------------------------------------------------------------


@given(
    present=st.lists(st.sampled_from(_REAL_STEP_NAMES), min_size=1, max_size=5, unique=True),
    renamed_suffix=st.sampled_from((" (informational)", " (ADVISORY)", "")),
)
def test_all_steps_covers_every_step_and_cannot_be_evaded_by_a_rename(
    present: list[str],
    renamed_suffix: str,
) -> None:
    """Why three committed entries use ``all_steps: true`` instead of a name list.

    A name list is evadable: rename the step and the declaration resolves to nothing (a
    finding, but a finding someone might "fix" by deleting the declaration).
    ``all_steps`` names nothing, so there is nothing to desynchronise - it also
    automatically covers a gate added to the job later, which is why
    ``truth-gates.yml::truth-gates`` uses it.
    """
    shapes = tuple(_shape(f"{name}{renamed_suffix}") for name in present)
    keys, findings = _resolve((_declaration(all_steps=True),), shapes)

    assert keys == {(shape.workflow, shape.job, shape.step_name) for shape in shapes}
    assert not [f for f in findings if f.rule == "blocking-unresolved"], (
        "all_steps names no step, so it can never resolve to nothing"
    )


def test_all_steps_wins_over_a_stale_name_list_because_it_is_the_wider_claim() -> None:
    """Documented precedence, pinned: ``all_steps`` short-circuits ``step_names``.

    Committed as a single fact rather than a property because it is a branch, not a space.
    It matters here because an entry carrying both would otherwise be able to report
    ``blocking-unresolved`` for a stale name while already declaring the whole job -
    a finding with no repair, since the declaration is already as wide as it can be.
    """
    shapes = (_shape("Ruff lint"),)
    declaration = wst.BlockingDeclaration(
        workflow=_WORKFLOW,
        job=_JOB,
        step_names=("a step that was renamed away",),
        all_steps=True,
        match="exact",
        requirement="R1.8",
    )
    keys, findings = _resolve((declaration,), shapes)

    assert keys == {(_WORKFLOW, _JOB, "Ruff lint")}
    assert not [f for f in findings if f.rule == "blocking-unresolved"]


# ---------------------------------------------------------------------------
# The same rename, end to end through the gate's own verdict
# ---------------------------------------------------------------------------


def _write_generated_tree(
    root: Path,
    *,
    tree_steps: tuple[str, ...],
    declared: tuple[str, ...],
    match: str,
) -> tuple[Path, Path, str]:
    """Render one workflow and one declaration file inside *root*.

    Both are written with ``allow_unicode=False``, so the bytes on disk stay ASCII even
    when the parsed step name does not - which is the real shape of this problem: the
    tree's names carry em dashes and the declaration file may not (the Windows console
    contract). ``encoding='utf-8'`` on both writes, per E-S13-07.

    Same rendering convention as ``tests/verify/strategies.py::WorkflowDraft.to_yaml``,
    deliberately: one way to build a throwaway workflow for this gate, not two.
    """
    directory = root / "workflows"
    directory.mkdir(parents=True, exist_ok=True)
    workflow_path = directory / "ci.yml"
    workflow_path.write_text(
        yaml.safe_dump(
            {
                "name": "generated",
                "on": {"push": {"branches": ["main"]}},
                "jobs": {
                    _JOB: {
                        "runs-on": "ubuntu-latest",
                        # `echo` propagates, so no other rule can fire over this tree and
                        # the verdict is a statement about resolution alone.
                        "steps": [{"name": name, "run": "echo ok"} for name in tree_steps],
                    }
                },
            },
            sort_keys=True,
            allow_unicode=False,
        ),
        encoding="utf-8",
    )
    workflow_key = wst.workflow_relative_path(workflow_path)

    declaration_path = root / "blocking-steps.yaml"
    declaration_path.write_text(
        yaml.safe_dump(
            {
                "steps": [
                    {
                        "workflow": workflow_key,
                        "job": _JOB,
                        "step_names": list(declared),
                        "match": match,
                        "requirement": "R4.3",
                    }
                ]
            },
            sort_keys=True,
            allow_unicode=False,
        ),
        encoding="utf-8",
    )
    return workflow_path, declaration_path, workflow_key


@given(
    base=ascii_step_names(),
    suffix=st.sampled_from((" (ADVISORY - not yet blocking)", " (informational in P0)")),
    kind=st.sampled_from(("identity", "em-dash", "doubled-space")),
)
def test_the_gate_fails_a_rename_and_clears_when_the_declaration_moves_with_it(
    base: str,
    suffix: str,
    kind: str,
) -> None:
    """R4.3 through ``evaluate``: the same-commit discipline, and its absence.

    The properties above work on ``_declared_keys`` because that is where the matching
    rule lives. This one goes through the gate's whole verdict, because R4.3 is stated
    about the gate ("SHALL report zero ``blocking-unresolved`` findings on the resulting
    tree") and a rule that resolves correctly while the verdict ignores it would satisfy
    every property above.

    Every root ``evaluate`` reads is pointed inside the temporary directory - workflows,
    declaration, ``frontend_src``, ``frontend_dist``, and ``makefile=None``. The verdict
    is therefore a statement about the generated tree and nothing else; the committed
    ``.github/workflows/`` and ``blocking-steps.yaml`` are deliberately not read, because
    they move as other tasks land and the obligation about *them* belongs to C64 in
    ``truth-gates.yml`` rather than to a property test.
    """
    renamed = _perturb(f"{base}{suffix}", kind)

    with tempfile.TemporaryDirectory(prefix="declared-rename-") as tmp:
        root = Path(tmp)

        # (a) The rename landed, the declaration did not move: loud, and named.
        _wf, declaration_path, workflow_key = _write_generated_tree(
            root, tree_steps=(renamed,), declared=(base,), match="normalized"
        )
        stale = wst.evaluate(
            directory=root / "workflows",
            declaration_path=declaration_path,
            makefile=None,
            frontend_src=root / "frontend" / "src",
            frontend_dist=root / "frontend" / "dist",
        )
        unresolved = [f for f in stale.findings if f.rule == "blocking-unresolved"]
        assert stale.verdict == "fail", f"a stale declaration must fail, got {stale.reason}"
        assert [(f.workflow, f.job, f.step_name, f.requirement) for f in unresolved] == [
            (workflow_key, _JOB, base, "R4.3")
        ]
        assert "blocking-unresolved=1" in stale.reason

        # (b) Both moved in the same commit. The declaration carries the ASCII fold of
        # the new name, which is the only form it is allowed to carry, and `normalized`
        # is what makes that legal.
        _wf, declaration_path, _key = _write_generated_tree(
            root,
            tree_steps=(renamed,),
            declared=(wst.normalize_step_name(renamed),),
            match="normalized",
        )
        moved = wst.evaluate(
            directory=root / "workflows",
            declaration_path=declaration_path,
            makefile=None,
            frontend_src=root / "frontend" / "src",
            frontend_dist=root / "frontend" / "dist",
        )
        assert not [f for f in moved.findings if f.rule == "blocking-unresolved"]
        assert moved.verdict == "pass", moved.reason
