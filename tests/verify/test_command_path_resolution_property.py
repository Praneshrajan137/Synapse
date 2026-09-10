"""Property-based test for named-command resolution (design E4.4).

Feature: purpose-achievement-audit, Property 20: Every named command resolves

    *For any* workflow or Makefile text containing an audit-verification step, the
    command-path check resolves each named module path and console-script name against
    the tree and the declared entry points, and fails naming every path that does not
    resolve and every such step whose exit status is discarded.

Why a property and not examples. The condition this gate exists for ran undetected for
two sprints: ``Makefile::deploy-gcp-verify`` and ``cd-gcp.yml::deploy-to-vm`` both
invoked ``python -m orchestrator.audit.cli verify`` while ``orchestrator/audit/cli.py``
did not exist, and both discarded the exit status so neither the absence nor a non-zero
could surface. A fixed set of examples pins *that* module at *those* two lines. The
failure mode is the next one: a different module, a console-script name ADR-033 names
but no entry point declares, a leaf package with no ``__main__.py``, a typo'd root. So
the property quantifies over generated (tree, naming surface) pairs and asserts
resolution is **total** there - every named command lands on exactly one of the nine
resolutions, and the side it lands on is the shape the generator put in the tree.

The three clauses that carry the requirement, each asserted in both directions:

* **A module resolves iff the tree can run it.** ``a/b.py`` and ``a/b/__main__.py``
  resolve; a leaf package *without* ``__main__.py`` does not, because ``python -m`` on it
  exits non-zero however real the directory looks. An absent leaf under a real root and
  an unknown root are distinguished, so the finding says which mistake was made.
* **A console-script name resolves only through a real entry point.** Not through a
  ``[project] name``, and not through a module that happens to exist: a declared
  ``module:attr`` whose module is absent is a name pointing at nothing and fails naming
  both sides. This is why ``synapse audit verify`` would not resolve today.
* **A discarded exit status is reported even when the command resolves.** The two
  halves are independent defects and the gate must not let a resolvable command excuse a
  swallow, nor a swallow hide an unresolvable command.

Scope is asserted as firmly as the findings, because R6.14 is scoped to
audit-verification steps and a gate that widened itself would drown the obligation in
``python -m pytest`` noise: an out-of-scope step contributes no command and no finding,
*even when it names an unresolvable path and discards its status* - that step belongs to
``workflow_shape_truth``'s R11.3 name rule, not here. And an in-scope step is in scope
because of what it *names*, not because of what resolves, so an absent module is still
reported rather than silently dropped for being unfindable.

Ground truth. ``tests/verify/strategies.py`` renders real GitHub-Actions-shaped YAML;
``StepDraft`` / ``JobDraft`` / ``WorkflowDraft`` and the discarding-construct vocabulary
are reused rather than restated, and ``step_drafts`` supplies the out-of-scope noise. The
shape written into the temporary tree is the injected truth and the gate reads only
files, so agreement is the gate rediscovering a fact it was not told.

Subject: ``scripts/audit/command_path_truth`` (task 7.4), over the discarding-construct
classification it imports from ``scripts/audit/workflow_shape_truth`` (task 2.10).
Resolution here is **static**, exactly as the gate's is: a module resolves because a file
exists, not because it imports. No generated command is ever invoked, no module is
imported, no subprocess is spawned, and no workflow is executed (I-0). Every generated
example runs against a throwaway tree with every root threaded as a parameter, following
the hermetic-roots pattern task 2.11 established; the last test reads the *committed*
tree, statically, because that is the only way to confirm the two call sites the audit
found now name a module that exists.

``max_examples`` is never set here - the budget comes from the root ``conftest.py``
profiles (``dev``=10, ``heavy``=100, ``ci``/``default``=500, ``nightly``=5000).

**Validates: Requirements 6.14**
"""

from __future__ import annotations

import dataclasses
import tempfile
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Final, Literal, get_args

from hypothesis import given
from hypothesis import strategies as st

from scripts.audit import command_path_truth as cpt
from tests.verify.strategies import (
    DISCARDING_CONSTRUCTS,
    JobDraft,
    StepDraft,
    WorkflowDraft,
    step_drafts,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

#: One finding, reduced to the fields R6.14 obliges it to name: the rule, the file, the
#: step, and the subject.
FindingKey = tuple[str, str, str, str, str]

#: The two rules E4.4 declares. Findings are reported in this order.
RULES: Final[tuple[str, ...]] = ("unresolvable-command", "discarded-exit-status")

#: Resolutions that mean the named command can actually run. ``external`` is a pass
#: because a declared third-party root is not resolvable from the tree by design.
PASSING_RESOLUTIONS: Final[frozenset[str]] = frozenset(
    {"module_file", "package_main", "script_file", "entry_point", "external"}
)

#: Resolutions that FAIL. Kept separate from the passing set so the union below is an
#: independent statement of the closed vocabulary rather than a restatement of it.
FAILING_RESOLUTIONS: Final[frozenset[str]] = frozenset(
    {"package_without_main", "entry_point_target_missing", "unresolved", "unknown_root"}
)

ALL_RESOLUTIONS: Final[frozenset[str]] = PASSING_RESOLUTIONS | FAILING_RESOLUTIONS

#: Resolutions that name what they resolved to. ``external`` resolves without a target -
#: there is no file in the tree to point at.
TARGETED_RESOLUTIONS: Final[frozenset[str]] = frozenset(
    {"module_file", "package_main", "script_file", "entry_point"}
)

#: The exit-status vocabulary a non-passing verdict may use. ``unavailable`` is
#: non-passing too (I-7: absence of proof is never a pass).
NON_PASSING_VERDICTS: Final[tuple[str, ...]] = ("fail", "unavailable")

ModuleShape = Literal[
    "module_file",
    "package_main",
    "package_without_main",
    "absent_leaf",
    "unknown_root",
    "external",
]

#: Every module shape, i.e. the whole resolution space of a ``python -m`` path.
MODULE_SHAPES: Final[tuple[ModuleShape, ...]] = get_args(ModuleShape)

#: Module shapes that resolve. Used when a test is about the discard half only and an
#: unresolvable command would supply the finding for the wrong reason.
RESOLVABLE_MODULE_SHAPES: Final[tuple[ModuleShape, ...]] = (
    "module_file",
    "package_main",
    "external",
)

#: An anchor's root is a real tree root (``orchestrator`` / ``scripts``), so ``external``
#: is not a shape it can take - the root would have to be a declared distribution.
ANCHOR_SHAPES: Final[tuple[ModuleShape, ...]] = (
    "module_file",
    "package_main",
    "package_without_main",
    "absent_leaf",
    "unknown_root",
)
RESOLVABLE_ANCHOR_SHAPES: Final[tuple[ModuleShape, ...]] = ("module_file", "package_main")

#: Roots declared external for the generated trees, **one per extra a case may draw**.
#: One name was not enough, and the generator's own disjointness guard is what said so:
#: ``_extra_module`` ignored its ``index`` for this shape, so two ``external`` draws both
#: claimed ``pytest`` and :func:`assert_roots_are_disjoint` fired exactly as its docstring
#: promises. The branch under test is still "root in the declared set" rather than the
#: size of the set - the set is indexed so that *naming two external modules* stays a
#: reachable case instead of being filtered out of the generator.
EXTERNAL_ROOTS_BY_INDEX: Final[tuple[str, ...]] = ("pytest", "coverage", "hypothesis")
EXTERNAL_ROOT: Final[str] = EXTERNAL_ROOTS_BY_INDEX[0]
EXTERNAL_ROOTS: Final[frozenset[str]] = frozenset(EXTERNAL_ROOTS_BY_INDEX)

#: The Make-specific construct: a leading ``-`` makes Make ignore the recipe line's exit
#: status. It was one of the three swallows removed from ``Makefile::deploy-gcp-verify``.
LEADING_DASH: Final[str] = "leading-dash"

#: The four constructs a workflow step can discard its status with, reused verbatim from
#: ``tests/verify/strategies.py`` so this test and Property 4 share one vocabulary.
WORKFLOW_CONSTRUCTS: Final[tuple[str, ...]] = DISCARDING_CONSTRUCTS

#: A Make recipe line is its own shell invocation (the Makefile sets ``SHELL`` and
#: declares no ``.ONESHELL``), so the three shell constructs apply, plus Make's own ``-``.
#: ``continue-on-error`` is a workflow key and has no Makefile spelling.
MAKE_CONSTRUCTS: Final[tuple[str, ...]] = (
    "|| true",
    "|| echo",
    "; exit 0",
    LEADING_DASH,
)

#: Console-script names for the generated manifests. ``synapse`` is the real one ADR-033
#: names; the other two prove the rule is about declaration, not about that spelling.
CONSOLE_NAMES: Final[tuple[str, ...]] = ("synapse", "clitool", "gatecli")

#: The entry-point target every generated declaration points at, and the file that makes
#: it resolve. The root is disjoint from every other root a case can create.
CONSOLE_TARGET: Final[str] = "clipkg.entry:main"
CONSOLE_TARGET_MODULE: Final[str] = "clipkg/entry.py"

#: The ``[project] name`` used when a case invokes no console script. It is owned, so the
#: gate would extract it if it appeared as a command head - and it appears nowhere, which
#: is what makes "an owned name nobody invokes contributes nothing" observable.
UNINVOKED_SCRIPT_NAME: Final[str] = "unusedcli"

#: Script-path invocations. The root is ``tools/`` so it cannot disturb an anchor's root.
SCRIPT_PRESENT: Final[str] = "tools/gate.py"
SCRIPT_ABSENT: Final[str] = "tools/missing.py"

#: Step names for the in-scope step. Disjoint from ``strategies._STEP_LABELS`` so an
#: assertion that a finding names *this* step cannot be satisfied by a noise step.
STEP_LABELS: Final[tuple[str, ...]] = (
    "Audit-chain integrity (Sprint 9 verifier)",
    "Command-path truth (R6.14)",
    "Chain verifier",
)
JOB_IDS: Final[tuple[str, ...]] = ("deploy-to-vm", "truth-gates", "verify")
WORKFLOW_FILES: Final[tuple[str, ...]] = ("cd-gcp.yml", "ci.yml", "integration.yml")
MAKE_TARGETS: Final[tuple[str, ...]] = (
    "deploy-gcp-verify",
    "verify-audit-chain",
    "verify-claims",
)

#: Written into every generated module file. Nothing reads it: resolution is a file-system
#: question, so the body is deliberately inert (I-0 - no generated module is ever imported).
_STUB: Final[str] = "# generated stub - never imported, never executed (I-0)\n"


# ---------------------------------------------------------------------------
# One generated (tree, naming surface) pair
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Anchor:
    """What makes a generated step an audit-verification step (R6.14's scope).

    ``pattern`` is the ``AUDIT_VERIFICATION_PATTERNS`` entry the rendered text matches,
    recorded so a case can assert *why* it is in scope. ``suffix`` is the extra argument
    text a pattern needs (the chain verifier is named ``... cli verify``, not ``... cli``).
    """

    dotted: str
    suffix: str
    pattern: str


#: The three ways a step comes into scope: the chain verifier by module path, the audit
#: gate family, and the ``synapse_cli`` alias. Each carries a distinct tree root.
ANCHORS: Final[tuple[Anchor, ...]] = (
    Anchor("orchestrator.audit.cli", " verify", "orchestrator.audit.cli verify"),
    Anchor("scripts.audit.anchor_truth", "", "scripts.audit."),
    Anchor("scripts.synapse_cli.audit_verify", "", "synapse_cli.audit_verify"),
)


@dataclass(frozen=True)
class ModuleDraft:
    """A ``python -m`` path and the shape the tree is given for it.

    ``shape`` is the ground truth; :attr:`expected_resolution` is what the gate must
    rediscover from the files alone.
    """

    dotted: str
    shape: ModuleShape

    @property
    def segments(self) -> tuple[str, ...]:
        return tuple(self.dotted.split("."))

    @property
    def expected_resolution(self) -> str:
        if self.shape == "absent_leaf":
            # The root exists, so the gate can say which module is missing rather than
            # only that the root is unknown.
            return "unresolved"
        return self.shape

    @property
    def expected_target(self) -> str | None:
        if self.shape == "module_file":
            return "/".join(self.segments) + ".py"
        if self.shape == "package_main":
            return "/".join(self.segments) + "/__main__.py"
        return None

    def materialise(self, root: Path) -> None:
        """Give ``root`` the shape this draft declares, and nothing more."""
        base = root.joinpath(*self.segments)
        if self.shape == "module_file":
            base.parent.mkdir(parents=True, exist_ok=True)
            base.with_suffix(".py").write_text(_STUB, encoding="utf-8")
        elif self.shape == "package_main":
            base.mkdir(parents=True, exist_ok=True)
            (base / "__main__.py").write_text(_STUB, encoding="utf-8")
        elif self.shape == "package_without_main":
            # A real directory that `python -m` still cannot run.
            base.mkdir(parents=True, exist_ok=True)
            (base / "__init__.py").write_text(_STUB, encoding="utf-8")
        elif self.shape == "absent_leaf":
            base.parent.mkdir(parents=True, exist_ok=True)
        # unknown_root and external write nothing: the first has no root in the tree,
        # the second is resolved by declaration before the tree is consulted.


@dataclass(frozen=True)
class ScriptDraft:
    """A ``python <path>.py`` invocation, present in the tree or not."""

    exists: bool

    @property
    def path_text(self) -> str:
        return SCRIPT_PRESENT if self.exists else SCRIPT_ABSENT

    @property
    def expectation(self) -> tuple[str, str | None]:
        return ("script_file", self.path_text) if self.exists else ("unresolved", None)

    def materialise(self, root: Path) -> None:
        if self.exists:
            path = root / self.path_text
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(_STUB, encoding="utf-8")


@dataclass(frozen=True)
class ConsoleDraft:
    """A console-script name, its declaration, and whether its target module exists.

    ``target_exists`` is drawn independently of ``declared`` on purpose: a target module
    sitting in the tree must not resolve a name that no entry point declares. That is the
    whole content of "resolves *only* through a real entry point".
    """

    name: str
    declared: bool
    target_exists: bool

    @property
    def expectation(self) -> tuple[str, str | None]:
        if not self.declared:
            return "unresolved", None
        if self.target_exists:
            return "entry_point", f"{CONSOLE_TARGET} -> {CONSOLE_TARGET_MODULE}"
        return "entry_point_target_missing", None

    def materialise(self, root: Path) -> None:
        if self.target_exists:
            path = root / CONSOLE_TARGET_MODULE
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(_STUB, encoding="utf-8")


@dataclass(frozen=True)
class CommandCase:
    """One audit-verification step, the tree it is resolved against, and its surface.

    Roots are disjoint by construction - the anchor owns ``orchestrator`` or ``scripts``,
    the extras own ``pkg{i}`` / ``absent{i}`` / ``pytest``, the script path owns
    ``tools``, the entry-point target owns ``clipkg`` - so no draft's materialisation can
    change another draft's resolution. :func:`assert_roots_are_disjoint` holds that.
    """

    surface: Literal["workflow", "makefile"]
    anchor_spec: Anchor
    anchor_shape: ModuleShape
    extras: tuple[ModuleDraft, ...]
    script: ScriptDraft | None
    console: ConsoleDraft | None
    construct: str | None
    label: str
    workflow_file: str
    job_id: str
    noise: tuple[StepDraft, ...]

    # -- the tree ----------------------------------------------------------

    @property
    def anchor(self) -> ModuleDraft:
        return ModuleDraft(dotted=self.anchor_spec.dotted, shape=self.anchor_shape)

    @property
    def modules(self) -> tuple[ModuleDraft, ...]:
        return (self.anchor, *self.extras)

    def materialise(self, root: Path) -> None:
        for module in self.modules:
            module.materialise(root)
        if self.script is not None:
            self.script.materialise(root)
        if self.console is not None:
            self.console.materialise(root)

    def pyproject_text(self) -> str:
        """The manifest whose entry-point table decides console-script resolution.

        A ``[project] name`` is always written, so the invoked name is *owned* (and
        therefore extracted) whether or not it is *declared* (and therefore resolvable).
        Those are the two different things R6.14 distinguishes.
        """
        name = self.console.name if self.console is not None else UNINVOKED_SCRIPT_NAME
        lines = [
            "[project]",
            f'name = "{name}"',
            'version = "0.0.0"',
            'requires-python = ">=3.11"',
        ]
        if self.console is not None and self.console.declared:
            lines += ["", "[project.scripts]", f'{self.console.name} = "{CONSOLE_TARGET}"']
        return "\n".join(lines) + "\n"

    # -- the command text --------------------------------------------------

    def command_text(self) -> str:
        """Every command the step names, on one shell line.

        One line, joined with ``&&``, because the discard classification reads the *last*
        top-level command: putting the construct anywhere else would test the shell
        reading rather than this gate. Extraction is a scan, so a nested invocation is
        found either way - which is the point, since both real call sites nest theirs
        inside ``ssh`` and ``docker compose exec``.
        """
        parts = [f"python -m {self.anchor_spec.dotted}{self.anchor_spec.suffix}"]
        parts += [f"python -m {module.dotted}" for module in self.extras]
        if self.script is not None:
            parts.append(f"python {self.script.path_text}")
        if self.console is not None:
            parts.append(f"{self.console.name} audit verify")
        return " && ".join(parts)

    def run_text(self) -> str:
        """The workflow step's ``run:`` body, carrying its construct where the shell puts it."""
        body = self.command_text()
        if self.construct is None or self.construct == "continue-on-error: true":
            return body
        if self.construct == "|| echo":
            return f'{body} || echo "non-blocking"'
        return f"{body} {self.construct}"

    def recipe_line(self) -> str:
        """The Make recipe line, carrying its construct where Make or the shell puts it."""
        body = self.command_text()
        if self.construct is None:
            return body
        if self.construct == LEADING_DASH:
            return f"-{body}"
        if self.construct == "|| echo":
            return f'{body} || echo "not available yet"'
        return f"{body} {self.construct}"

    # -- rendering ---------------------------------------------------------

    def as_step_draft(self) -> StepDraft:
        return StepDraft(
            step_name=self.label,
            run=self.run_text(),
            continue_on_error=self.construct == "continue-on-error: true",
            discarding_construct=self.construct,
            declared_blocking=False,
        )

    def as_workflow_draft(self) -> WorkflowDraft:
        return WorkflowDraft(
            path=f".github/workflows/{self.workflow_file}",
            triggers=("push:main",),
            jobs=(
                JobDraft(
                    job_id=self.job_id,
                    needs=(),
                    if_condition=None,
                    steps=(self.as_step_draft(), *self.noise),
                ),
            ),
        )

    def makefile_text(self) -> str:
        """A one-recipe Makefile. ``.PHONY`` is skipped by the reader; the target sets scope."""
        return (
            f".PHONY: {self.label}\n"
            f"\n"
            f"{self.label}: ## generated audit-verification recipe\n"
            f"\t{self.recipe_line()}\n"
        )

    # -- what the gate must report ----------------------------------------

    @property
    def scope(self) -> str:
        """The job id, or the Make target: the enclosing unit a finding is attributed to."""
        return self.job_id if self.surface == "workflow" else self.label

    @property
    def step_name(self) -> str:
        """The step identity a finding must name.

        A Make recipe line has no name, so the gate identifies it by its first 80
        characters - the same identification a reader of the Makefile makes.
        """
        return self.label if self.surface == "workflow" else self.recipe_line()[:80]

    def expected_commands(self) -> dict[tuple[str, str], tuple[str, str | None]]:
        """``(kind, name) -> (resolution, resolved_to)``, recomputed from the tree shape.

        Keyed by ``(kind, name)`` because the gate collapses a name repeated within one
        step to a single reported command.
        """
        expected: dict[tuple[str, str], tuple[str, str | None]] = {}
        for module in self.modules:
            expected[("module", module.dotted)] = (
                module.expected_resolution,
                module.expected_target,
            )
        if self.script is not None:
            expected[("script_path", self.script.path_text)] = self.script.expectation
        if self.console is not None:
            expected[("console_script", self.console.name)] = self.console.expectation
        return expected

    def expected_findings(self, source: str) -> set[FindingKey]:
        """The findings R6.14 mandates, recomputed from the injected ground truth.

        Written out rather than imported from the gate, so the test compares two
        implementations. Two clauses, and they do not interact: one finding per command
        that cannot run, plus one for the step itself when its status is discarded.
        """
        findings: set[FindingKey] = {
            ("unresolvable-command", source, self.scope, self.step_name, name)
            for (_kind, name), (resolution, _target) in self.expected_commands().items()
            if resolution not in PASSING_RESOLUTIONS
        }
        if self.construct is not None:
            findings.add(
                ("discarded-exit-status", source, self.scope, self.step_name, "(step)")
            )
        return findings


def _extra_module(index: int, shape: ModuleShape) -> ModuleDraft:
    """An extra ``python -m`` path whose root belongs to it alone."""
    if shape == "external":
        return ModuleDraft(dotted=EXTERNAL_ROOTS_BY_INDEX[index], shape=shape)
    if shape == "unknown_root":
        return ModuleDraft(dotted=f"absent{index}.mod", shape=shape)
    leaf = {
        "module_file": "mod",
        "package_main": "cli",
        "package_without_main": "bare",
        "absent_leaf": "gone",
    }[shape]
    return ModuleDraft(dotted=f"pkg{index}.{leaf}", shape=shape)


def _out_of_scope(draft: StepDraft) -> bool:
    """Whether a noise step names no audit subject.

    A literal check rather than a call to the gate's own classifier, so the noise is
    out of scope by construction and the "scope is narrow" assertions are not circular.
    ``strategies._STEP_COMMANDS`` names no chain verifier, so the audit gate family is
    the only pattern a noise step could match.
    """
    return "scripts.audit" not in draft.run and "scripts/audit" not in draft.run


@st.composite
def command_cases(
    draw: st.DrawFn,
    *,
    surface: Literal["workflow", "makefile"],
    constructs: Sequence[str | None] | None = None,
    resolvable_only: bool = False,
    require_console: bool = False,
    max_extras: int = 2,
) -> CommandCase:
    """One audit-verification step over one generated tree.

    ``constructs`` pins the discard dimension the way ``strategies.step_drafts``' own
    ``constructs`` argument does - ``(None,)`` yields only propagating steps and a
    single-element tuple pins one construct - and it is a pin rather than a filter for
    the same reason: filtering here would reject most draws and trip Hypothesis'
    ``filter_too_much`` health check.

    ``resolvable_only`` narrows every tree shape to a resolving one, for the tests about
    the discard half: an unresolvable command there would supply the finding for the
    wrong reason.
    """
    # Disjointness is promised by construction, and ``external`` is the one shape whose
    # root cannot be derived from its index. Fail here, where the cause is one line away,
    # rather than in ``assert_roots_are_disjoint`` on a mystifying duplicate.
    assert max_extras <= len(EXTERNAL_ROOTS_BY_INDEX), (
        f"max_extras={max_extras} exceeds the {len(EXTERNAL_ROOTS_BY_INDEX)} declared "
        "external root(s); add one per extra to EXTERNAL_ROOTS_BY_INDEX"
    )
    anchor_spec = draw(st.sampled_from(ANCHORS))
    anchor_shape = draw(
        st.sampled_from(RESOLVABLE_ANCHOR_SHAPES if resolvable_only else ANCHOR_SHAPES)
    )

    extra_shapes = draw(
        st.lists(
            st.sampled_from(RESOLVABLE_MODULE_SHAPES if resolvable_only else MODULE_SHAPES),
            max_size=max_extras,
        )
    )
    extras = tuple(
        _extra_module(index, shape) for index, shape in enumerate(extra_shapes)
    )

    script_strategy = st.builds(
        ScriptDraft, exists=st.just(True) if resolvable_only else st.booleans()
    )
    script = draw(st.none() | script_strategy)

    console_strategy = st.builds(
        ConsoleDraft,
        name=st.sampled_from(CONSOLE_NAMES),
        declared=st.just(True) if resolvable_only else st.booleans(),
        target_exists=st.just(True) if resolvable_only else st.booleans(),
    )
    console = draw(console_strategy if require_console else st.none() | console_strategy)

    if constructs is not None:
        pool = tuple(constructs)
    elif surface == "workflow":
        pool = (None, *WORKFLOW_CONSTRUCTS)
    else:
        pool = (None, *MAKE_CONSTRUCTS)

    return CommandCase(
        surface=surface,
        anchor_spec=anchor_spec,
        anchor_shape=anchor_shape,
        extras=extras,
        script=script,
        console=console,
        construct=draw(st.sampled_from(pool)),
        label=draw(
            st.sampled_from(STEP_LABELS if surface == "workflow" else MAKE_TARGETS)
        ),
        workflow_file=draw(st.sampled_from(WORKFLOW_FILES)),
        job_id=draw(st.sampled_from(JOB_IDS)),
        noise=(
            draw(st.lists(step_drafts().filter(_out_of_scope), max_size=2).map(tuple))
            if surface == "workflow"
            else ()
        ),
    )


def workflow_cases(**kwargs: object) -> st.SearchStrategy[CommandCase]:
    """Cases whose naming surface is a workflow step."""
    return command_cases(surface="workflow", **kwargs)  # type: ignore[arg-type]


def makefile_cases(**kwargs: object) -> st.SearchStrategy[CommandCase]:
    """Cases whose naming surface is a Make recipe line."""
    return command_cases(surface="makefile", **kwargs)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Driving the gate over a throwaway tree
# ---------------------------------------------------------------------------


def assert_roots_are_disjoint(case: CommandCase) -> None:
    """No draft's materialisation may change another draft's resolution.

    The generator guarantees this by construction; asserting it makes a future widening
    of the draft set fail here, where the cause is visible, instead of producing a
    mystifying counterexample about an ``unknown_root`` that became ``unresolved``.
    """
    roots = [module.segments[0] for module in case.modules]
    if case.script is not None:
        roots.append(case.script.path_text.split("/", 1)[0])
    if case.console is not None and case.console.target_exists:
        roots.append(CONSOLE_TARGET_MODULE.split("/", 1)[0])
    duplicated = [root for root, count in Counter(roots).items() if count > 1]
    assert not duplicated, f"generated roots collide: {duplicated}"


def evaluate_case(case: CommandCase) -> tuple[cpt.CommandPathReport, str]:
    """Run the gate over one generated case, and return its report and the source key.

    Every root the gate reads - the workflow directory, the Makefile, the tree it
    resolves modules against, the manifests it reads entry points from, and the declared
    external roots - is pointed inside the temporary directory or passed explicitly, so
    the verdict is a statement about the generated pair and nothing else. Nothing is
    monkeypatched and no module global is rebound. The directory is removed on the way
    out; no example leaves a file behind.
    """
    assert_roots_are_disjoint(case)

    with tempfile.TemporaryDirectory(prefix="command-path-") as tmp:
        root = Path(tmp)
        directory = root / ".github" / "workflows"
        directory.mkdir(parents=True)
        case.materialise(root)

        pyproject = root / "pyproject.toml"
        pyproject.write_text(case.pyproject_text(), encoding="utf-8")

        makefile: Path | None = None
        if case.surface == "workflow":
            surface_path = directory / case.workflow_file
            surface_path.write_text(case.as_workflow_draft().to_yaml(), encoding="utf-8")
        else:
            makefile = root / "Makefile"
            makefile.write_text(case.makefile_text(), encoding="utf-8")
            surface_path = makefile

        report = cpt.evaluate(
            directory=directory,
            makefile=makefile,
            tree_root=root,
            pyproject_paths=(pyproject,),
            external_roots=EXTERNAL_ROOTS,
        )
    return report, cpt.workflow_relative_path(surface_path)


def observed_commands(
    report: cpt.CommandPathReport,
) -> dict[tuple[str, str], tuple[str, str | None]]:
    """The report's commands in the same shape as :meth:`CommandCase.expected_commands`."""
    return {
        (command.kind, command.name): (command.resolution, command.resolved_to)
        for command in report.commands
    }


def actual_findings(report: cpt.CommandPathReport) -> set[FindingKey]:
    """The report's findings reduced to the fields R6.14 obliges them to name."""
    return {
        (item.rule, item.source, item.scope, item.step_name, item.subject)
        for item in report.findings
    }


def assert_report_is_well_formed(
    report: cpt.CommandPathReport, case: CommandCase, source: str
) -> None:
    """The obligations every report carries, whatever the case.

    Three of them are the requirement's own words - resolution is total, every finding
    names the file and the step, a non-passing verdict is reported as non-passing - and
    the fourth is E-S13-07's console half: a gate that cannot print its finding on a
    Windows console reports nothing.
    """
    # The closed vocabulary is closed. A widened Resolution would silently escape both
    # the passing and the failing set, and an unclassified resolution reads as a pass.
    assert set(get_args(cpt.Resolution)) == ALL_RESOLUTIONS
    assert set(get_args(cpt.CommandKind)) == {"module", "console_script", "script_path"}
    assert not (PASSING_RESOLUTIONS & FAILING_RESOLUTIONS)

    for command in report.commands:
        assert command.resolution in ALL_RESOLUTIONS
        # Total: exactly one side, and the side is decided by the resolution.
        assert command.resolves is (command.resolution in PASSING_RESOLUTIONS)
        assert (command.resolved_to is not None) is (
            command.resolution in TARGETED_RESOLUTIONS
        )
        assert command.detail
        assert command.detail.isascii()
        # Attribution: every command is attributed to the step that named it.
        assert command.source == source
        assert command.scope == case.scope
        assert command.step_name == case.step_name

    for item in report.findings:
        assert item.rule in RULES
        assert item.requirement == "R6.14"
        # Names the file and the step - the whole naming obligation of R6.14.
        assert item.source == source
        assert item.scope == case.scope
        assert item.step_name == case.step_name
        assert item.step_name
        assert item.detail
        assert item.detail.isascii()

    # Findings are grouped by rule, in the declared order, so a long report is readable.
    rules = [item.rule for item in report.findings]
    assert rules == sorted(rules, key=RULES.index)

    assert report.reason
    if report.findings:
        assert report.verdict == "fail"
        assert report.verdict in NON_PASSING_VERDICTS
        for rule, count in Counter(rules).items():
            assert f"{rule}={count}" in report.reason
    else:
        assert report.verdict == "pass"


# ---------------------------------------------------------------------------
# Property 20
# ---------------------------------------------------------------------------


# Feature: purpose-achievement-audit, Property 20: Every named command resolves
@given(case=st.one_of(workflow_cases(), makefile_cases()))
def test_every_named_command_resolves_or_is_named_on_both_naming_surfaces(
    case: CommandCase,
) -> None:
    """R6.14: resolution is total, and the findings are exactly the mandated ones.

    Totality is the point. A gate that skipped a naming it could not classify would
    satisfy every naming obligation below while resolving nothing - which is exactly the
    condition R6 describes: a command invoked for two sprints against a module that did
    not exist, with nothing reporting it.

    Set equality is what makes the "and nothing else" half meaningful: it is what forbids
    a resolvable command from being flagged, and it is why a passing case here is
    evidence rather than the absence of evidence.
    """
    report, source = evaluate_case(case)

    expected = case.expected_commands()
    assert observed_commands(report) == expected
    assert len(report.commands) == len(expected)

    assert actual_findings(report) == case.expected_findings(source)
    assert_report_is_well_formed(report, case, source)

    # The step is in scope because of what it names, not because of what resolves: the
    # anchor's pattern is present in the rendered text however absent its module is.
    assert case.anchor_spec.pattern in case.command_text()
    assert ("module", case.anchor_spec.dotted) in expected
    assert report.commands[0].kind == "module"
    assert report.commands[0].name == case.anchor_spec.dotted

    # Each unresolvable finding says which of the nine resolutions was reached, so the
    # report distinguishes "no such module" from "no __main__.py" from "unknown root".
    for item in report.findings:
        if item.rule != "unresolvable-command":
            continue
        matches = [key for key in expected if key[1] == item.subject]
        assert len(matches) == 1
        kind, _name = matches[0]
        resolution, _target = expected[matches[0]]
        assert resolution in FAILING_RESOLUTIONS
        assert kind in item.detail
        assert resolution in item.detail


@given(case=workflow_cases())
def test_an_out_of_scope_step_contributes_no_command_and_no_finding(
    case: CommandCase,
) -> None:
    """R6.14 is scoped, and the scope holds in both directions.

    The noise steps name unresolvable script paths and discard their exit status just as
    freely as the in-scope step does, and none of that is this gate's business: an
    unlabelled non-propagating step is ``workflow_shape_truth``'s R11.3 finding. Widening
    here would trade a precise obligation for noise - ``mutation.yml`` alone names
    ``python -m pytest`` in eight places.
    """
    report, source = evaluate_case(case)

    # Every command and every finding belongs to the one in-scope step. Nothing the noise
    # names is resolved, so nothing the noise gets wrong can be reported.
    assert all(command.step_name == case.step_name for command in report.commands)
    assert all(item.step_name == case.step_name for item in report.findings)

    noise_names = {draft.step_name for draft in case.noise}
    assert case.step_name not in noise_names
    assert not (noise_names & {command.step_name for command in report.commands})

    # Concretely: `python scripts/coverage_per_package.py` is in the noise vocabulary and
    # exists in no generated tree, and it is still never reported.
    assert all(
        "coverage_per_package" not in command.name for command in report.commands
    )
    assert_report_is_well_formed(report, case, source)


@given(
    case=workflow_cases(constructs=WORKFLOW_CONSTRUCTS, resolvable_only=True),
)
def test_a_discarded_exit_status_is_reported_even_when_every_command_resolves(
    case: CommandCase,
) -> None:
    """R6.14's second clause, isolated from the first.

    This is the half that hid the original defect for two sprints: the deploy step named
    a module that did not exist *and* swallowed the status, so the absence and the
    non-zero were equally invisible. The two defects are independent, so a resolvable
    command must not excuse a swallow - a gate that cannot fail is not a gate.
    """
    report, source = evaluate_case(case)

    assert report.commands
    assert all(command.resolves for command in report.commands)
    assert actual_findings(report) == {
        ("discarded-exit-status", source, case.scope, case.step_name, "(step)")
    }
    assert report.verdict == "fail"

    finding = report.findings[0]
    assert "exit status" in finding.detail
    # The report says *what* discarded the status, not only that something did.
    assert str(case.construct) in finding.detail
    assert_report_is_well_formed(report, case, source)

    # The converse guard: the same step, same tree, construct removed, passes. Without
    # it every assertion above would also hold for a gate that flags every step.
    propagating, propagating_source = evaluate_case(
        dataclasses.replace(case, construct=None)
    )
    assert propagating.findings == ()
    assert propagating.verdict == "pass"
    assert observed_commands(propagating) == observed_commands(report)
    assert_report_is_well_formed(
        propagating, dataclasses.replace(case, construct=None), propagating_source
    )


@given(case=workflow_cases(require_console=True, constructs=(None,)))
def test_a_console_script_resolves_only_through_a_real_entry_point(
    case: CommandCase,
) -> None:
    """R6.14's console half: a declaration, not a name and not a coincidence.

    Two near-misses are rejected here, and both are live conditions in this repository.
    ``pyproject.toml`` declares ``[project] name = "synapse"`` and **no** entry-point
    table, so ADR-033's ``synapse audit verify`` names something the repository owns and
    cannot run - owning a name is not declaring a command. And a declared
    ``module:attr`` whose module is absent is a name pointing at nothing, which must fail
    naming both sides rather than resolve because the declaration looked right.
    """
    console = case.console
    assert console is not None

    report, source = evaluate_case(case)
    commands = [
        command for command in report.commands if command.kind == "console_script"
    ]
    assert len(commands) == 1
    command = commands[0]

    resolution, target = console.expectation
    assert command.name == console.name
    assert command.resolution == resolution
    assert command.resolved_to == target
    # Resolvable iff declared AND the declared target exists. Nothing else resolves it.
    assert command.resolves is (console.declared and console.target_exists)
    assert command.resolves is (resolution == "entry_point")

    if not console.declared:
        # The detail says *why*: no table declares it. A tree that happens to hold the
        # target module changes nothing, which is the "only through" in the property.
        assert "project.scripts" in command.detail
        assert console.name in command.detail
    elif not console.target_exists:
        assert CONSOLE_TARGET in command.detail
        assert console.name in command.detail

    expected_findings = case.expected_findings(source)
    console_findings = {key for key in expected_findings if key[4] == console.name}
    assert bool(console_findings) is (not command.resolves)
    assert actual_findings(report) == expected_findings
    assert_report_is_well_formed(report, case, source)

    # Declaring the name and materialising its target is the only edit that resolves it,
    # and it does so without touching the step text at all.
    resolved, _ = evaluate_case(
        dataclasses.replace(
            case,
            console=ConsoleDraft(name=console.name, declared=True, target_exists=True),
        )
    )
    resolved_console = [
        command for command in resolved.commands if command.kind == "console_script"
    ]
    assert len(resolved_console) == 1
    assert resolved_console[0].resolution == "entry_point"
    assert resolved_console[0].resolves


@given(case=makefile_cases(constructs=MAKE_CONSTRUCTS))
def test_a_make_recipe_line_is_read_with_the_same_two_rules(
    case: CommandCase,
) -> None:
    """R6.14 names the Makefile as a naming surface, and Make has its own swallow.

    A Make recipe line is its own shell invocation, so it carries its own exit status and
    its own three shell constructs - plus Make's leading ``-``, which was one of the
    three swallows removed from ``Makefile::deploy-gcp-verify``. A finding attributes
    itself to the target and to the recipe line, because a Make recipe has no step name.
    """
    report, source = evaluate_case(case)

    assert source.endswith("Makefile")
    assert case.scope == case.label
    assert case.step_name == case.recipe_line()[:80]

    # Extraction is total on this surface too, and Make's own line prefixes do not
    # silence it. Without this clause the findings-set equality below passes VACUOUSLY
    # whenever every named command happens to resolve: a `-`-prefixed recipe contributed
    # ZERO commands, its only finding was the swallow, and the two sides still matched.
    # That is how the swallow came to conceal the unresolvable command it was swallowing.
    assert observed_commands(report) == case.expected_commands()
    assert report.commands

    discards = [
        item for item in report.findings if item.rule == "discarded-exit-status"
    ]
    assert len(discards) == 1
    assert discards[0].subject == "(step)"
    assert discards[0].scope == case.label
    assert discards[0].step_name == case.step_name
    if case.construct == LEADING_DASH:
        # Make's own construct, not a shell one: the recipe line still runs, and its
        # non-zero is discarded before any shell construct could be involved.
        assert case.recipe_line().startswith("-")
        assert "-" in discards[0].detail
    else:
        assert str(case.construct) in discards[0].detail

    assert actual_findings(report) == case.expected_findings(source)
    assert report.verdict == "fail"
    assert_report_is_well_formed(report, case, source)

    # The same recipe without its construct is judged on resolution alone.
    propagating_case = dataclasses.replace(case, construct=None)
    propagating, propagating_source = evaluate_case(propagating_case)
    assert [
        item for item in propagating.findings if item.rule == "discarded-exit-status"
    ] == []
    assert actual_findings(propagating) == propagating_case.expected_findings(
        propagating_source
    )


@given(
    anchor=st.sampled_from(ANCHORS),
    surface=st.sampled_from(("workflow", "makefile")),
)
def test_an_echoed_command_name_is_a_message_and_not_an_invocation(
    anchor: Anchor,
    surface: Literal["workflow", "makefile"],
) -> None:
    """A log line that mentions a command does not name one, and proves nothing either.

    ``Makefile:592`` carried ``|| echo "synapse audit verify not available yet"``, so the
    verifier's name appeared in the recipe twice - once as an invocation and once as the
    apology for it. Reading the message as an invocation would fabricate a finding
    (I-7 in the other direction: a gate must not invent one either). And a surface whose
    only mention is echoed names no audit-verification step at all, so the verdict is
    ``unavailable`` rather than ``pass``: a resolution gate that found nothing to resolve
    has proved nothing.
    """
    message = f'echo "python -m {anchor.dotted}{anchor.suffix} not available yet"'

    with tempfile.TemporaryDirectory(prefix="command-path-echo-") as tmp:
        root = Path(tmp)
        directory = root / ".github" / "workflows"
        directory.mkdir(parents=True)
        (root / "pyproject.toml").write_text(
            f'[project]\nname = "{UNINVOKED_SCRIPT_NAME}"\n', encoding="utf-8"
        )

        makefile: Path | None = None
        if surface == "workflow":
            draft = WorkflowDraft(
                path=".github/workflows/ci.yml",
                triggers=("push:main",),
                jobs=(
                    JobDraft(
                        job_id="truth-gates",
                        needs=(),
                        if_condition=None,
                        steps=(
                            StepDraft(
                                step_name="Explain why the verifier did not run",
                                run=message,
                                continue_on_error=False,
                                discarding_construct=None,
                                declared_blocking=False,
                            ),
                        ),
                    ),
                ),
            )
            (directory / "ci.yml").write_text(draft.to_yaml(), encoding="utf-8")
        else:
            makefile = root / "Makefile"
            makefile.write_text(
                f"verify-audit-chain: ## explain\n\t@{message}\n", encoding="utf-8"
            )

        report = cpt.evaluate(
            directory=directory,
            makefile=makefile,
            tree_root=root,
            pyproject_paths=(root / "pyproject.toml",),
            external_roots=EXTERNAL_ROOTS,
        )

    # The mention is stripped before the scope decision, so the step is never in scope.
    assert cpt.strip_echoed_text(message).strip() == ""
    assert not cpt.is_audit_verification_command(message)
    assert report.commands == ()
    assert report.findings == ()
    assert report.verdict == "unavailable"
    assert report.verdict in NON_PASSING_VERDICTS
    assert "no audit-verification step" in report.reason


def test_a_tree_naming_no_audit_verification_step_is_unavailable_not_a_pass() -> None:
    """I-7 at the gate's boundary: nothing checked is not the same as nothing wrong.

    An empty workflow directory and no Makefile is the degenerate input, and it must not
    report a pass. The distinction matters because this gate will be registered in the
    Check_Registry (task 12.1), where a fabricated PASS on an input it never read is
    exactly the vacuity the whole audit is about.
    """
    with tempfile.TemporaryDirectory(prefix="command-path-empty-") as tmp:
        root = Path(tmp)
        directory = root / ".github" / "workflows"
        directory.mkdir(parents=True)

        report = cpt.evaluate(
            directory=directory,
            makefile=None,
            tree_root=root,
            pyproject_paths=(),
            external_roots=EXTERNAL_ROOTS,
        )

    assert report.verdict == "unavailable"
    assert report.verdict != "pass"
    assert report.commands == ()
    assert report.findings == ()
    assert "no audit-verification step" in report.reason


# ---------------------------------------------------------------------------
# The committed tree, read statically
# ---------------------------------------------------------------------------


def test_the_committed_chain_verifier_resolves_and_no_entry_point_declares_it() -> None:
    """R6.14 against the real files: the module both call sites name now exists.

    A static read of the committed tree - no command is invoked, no module imported, no
    workflow executed. Two facts are pinned because the audit's finding was exactly their
    absence:

    * ``python -m orchestrator.audit.cli verify`` resolves to a file, so the invocation
      at ``Makefile::deploy-gcp-verify`` and ``cd-gcp.yml::deploy-to-vm`` names something
      that can run (task 7.3), and the ``scripts.synapse_cli.audit_verify`` alias does too.
    * ``synapse audit verify`` does **not** resolve: both manifests declare a ``[project]
      name`` and neither declares an entry point, so ADR-033's command name is owned and
      unrunnable. That is the honest state, and it is why the console-script rule above is
      about declarations rather than names.

    The gate's overall verdict is deliberately not asserted: the committed surface changes
    as tasks land, and pinning a colour here would make an honest red read as a test
    failure. What must hold now is narrower - the chain verifier resolves, and every
    finding the gate does report is well formed enough to act on.
    """
    resolution, target, detail = cpt.resolve_module("orchestrator.audit.cli")
    assert resolution == "module_file"
    assert target == "orchestrator/audit/cli.py"
    assert detail

    alias_resolution, alias_target, _ = cpt.resolve_module(
        "scripts.synapse_cli.audit_verify"
    )
    assert alias_resolution == "module_file"
    assert alias_target == "scripts/synapse_cli/audit_verify.py"

    # Owned, and declared by nothing: the two halves R6.14 keeps apart.
    entry_points = cpt.load_entry_points()
    assert entry_points == {}
    assert cpt.load_owned_script_names() == frozenset({"synapse", "synapse-common"})
    console_resolution, console_target, console_detail = cpt.resolve_console_script(
        "synapse", entry_points=entry_points
    )
    assert console_resolution == "unresolved"
    assert console_target is None
    assert "project.scripts" in console_detail

    report = cpt.evaluate()
    assert report.verdict in {"pass", *NON_PASSING_VERDICTS}
    assert report.commands, "no audit-verification step was found in the committed tree"

    chain = [
        command
        for command in report.commands
        if command.name == "orchestrator.audit.cli"
    ]
    assert chain, "no committed step names the chain verifier"
    for command in chain:
        assert command.kind == "module"
        assert command.resolution == "module_file"
        assert command.resolves
        assert command.resolved_to == "orchestrator/audit/cli.py"

    for item in report.findings:
        assert item.rule in RULES
        assert item.requirement == "R6.14"
        # A finding a reader cannot locate is not a finding.
        assert item.source
        assert item.step_name
        assert item.subject
        assert item.detail
        assert item.detail.isascii()
