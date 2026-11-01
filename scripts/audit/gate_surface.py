"""The aggregate blocking surface of CI, generated (design E1.6).

Feature: purpose-achievement-audit, task 2.12. Requirements R11.1, R11.2, R11.7,
R11.9.

R11's finding is not that any individual trigger condition is dishonest - every one
of them is explicit and most carry an in-file reason. The finding is that the
*aggregate* is stated nowhere: no document says which gates a merge to `main`
actually runs, so a reader summing CLAUDE.md's gate inventory substantially
overestimates the enforcement boundary. This module removes the ambiguity
mechanically. It reads `.github/workflows/*.yml`, evaluates every job's `on:` and
`if:` against three synthetic trigger contexts (`push:main`, `pull_request`,
`tag:v*`), walks `needs:` edges transitively, and renders
`docs/state/GATE_SURFACE.md` (AD-2: every mirror of machine state is generated and
diffable, never hand-maintained).

Four states, and the distinction between them is the whole point:

* **``yes``** - the job executes in that context and the step's exit status decides
  the job's conclusion. This is the only value that may be read as "blocking".
* **``no``** - the job executes and the step runs, but a discarding construct or
  ``continue-on-error`` means its failure cannot fail the run (R11.3). The step's
  own name must say so; `workflow_shape_truth` is what enforces that.
* **``NOT EXECUTED``** - the workflow's ``on:`` does not select this context, the
  job's ``if:`` is false in it, or a job it ``needs:`` is itself not executed
  (R11.9). Under I-7 this is **not a pass**: a job that did not run cannot be
  reported successful, and this document never renders it as one.
* **``CONDITIONAL``** - the job executes only given a fact the trigger does not
  determine: a ``paths:``/``paths-ignore:`` filter (the change set), a dispatch
  input, or a run outcome such as ``failure()``. Also not a pass. This is what
  keeps a path-filtered gate - `policy.yml`'s I-4 audit-immutability job, every
  `frontend.yml` job, `mutation.yml::mutation-fast` - from reading as
  unconditionally blocking, which is exactly the overstatement R11 records and the
  same reasoning `infrastructure/quality/required-checks.yaml` uses to call those
  jobs ineligible as required status checks.

Two deliberate readings, both load-bearing:

1. **``needs:`` dominates.** A job whose dependency is ``NOT EXECUTED`` renders
   ``NOT EXECUTED``, naming the dependency, even when its own ``if:`` is
   undecidable (R11.9). ``if: always()`` does not buy an exemption: GitHub would
   still start such a job, so the note records that, but the row stays
   ``NOT EXECUTED`` because its conclusion is derived from dependencies that never
   ran rather than produced by a gate. A conditional dependency makes the dependent
   conditional - `ci.yml::uplift-verify` is only as reachable as the
   `quality-gates` job it needs.
   A path filter on a *tag* push is treated the same way, deliberately: what GitHub
   diffs a ``paths``/``paths-ignore`` filter against when a tag is pushed is not
   determinable from this working tree, so the honest value is ``CONDITIONAL``
   rather than an assertion in either direction (I-7).
2. **``paths-ignore`` is a condition, not a footnote.** `ci.yml` ignores
   ``**.md``/``docs/**`` on push, so on `push:main` its jobs are ``CONDITIONAL``,
   not ``yes``. That is R11.4's hole rendered rather than described: the
   narrative-truth gate does not run on the commits most likely to drift the
   narrative. The `truth-gates` job task 2.17 adds carries no ``paths-ignore``
   (CF-2) and will therefore render ``yes`` - the difference being visible in this
   table is the point of generating it.

Run::

    python -m scripts.audit.gate_surface            # report + drift check (diff)
    python -m scripts.audit.gate_surface --check    # explicit form of the default
    python -m scripts.audit.gate_surface --write    # regenerate the document
    python -m scripts.audit.gate_surface --json     # machine-readable record

Exit codes: ``0`` in sync, ``1`` drift (the unified diff is printed, R11.2/R11.7),
``2`` unavailable - no workflow could be read, which is never a pass (I-7).

Reuse: every workflow read goes through `scripts.audit.workflow_shape_truth`'s
shared reader (`load_workflow`, `iter_jobs`, `iter_job_steps`, `job_needs`,
`job_if_condition`, `classify_step`, ...). There is exactly one workflow parser in
this repository and it is not here. Every file read uses ``encoding='utf-8'``
(E-S13-07) and both the console output and the generated document are ASCII-only.
"""

from __future__ import annotations

import difflib
import json
import re
import sys
from fnmatch import fnmatchcase
from typing import TYPE_CHECKING, Final, Literal

from pydantic import BaseModel, ConfigDict

from scripts.audit.workflow_shape_truth import (
    ADVISORY_MARKERS,
    BLOCKING_STEPS_FILE,
    ROOT,
    WORKFLOW_DIR,
    BlockingDeclaration,
    DeclarationLoadError,
    StepShape,
    classify_step,
    iter_job_steps,
    iter_jobs,
    iter_workflow_paths,
    job_display_names,
    job_if_condition,
    job_needs,
    load_blocking_declarations,
    load_workflow,
    normalize_step_name,
    step_run_script,
    workflow_relative_path,
    workflow_triggers,
)

if TYPE_CHECKING:  # `Path` is only ever an annotation here; ROOT is already resolved.
    from pathlib import Path

SURFACE_DOC: Final[Path] = ROOT / "docs" / "state" / "GATE_SURFACE.md"

#: Delimiters of the generated region (AD-2). Prose outside them survives a rewrite.
GENERATED_BEGIN: Final[str] = "<!-- generated:begin -->"
GENERATED_END: Final[str] = "<!-- generated:end -->"

#: The four values the ``Propagates`` column may take. Nothing else is emitted.
PROPAGATES_VALUES: Final[tuple[str, ...]] = ("yes", "no", "NOT EXECUTED", "CONDITIONAL")

SelectionState = Literal["selected", "conditional", "not-executed"]

__all__ = [
    "GENERATED_BEGIN",
    "GENERATED_END",
    "PROPAGATES_VALUES",
    "SURFACE_DOC",
    "TRIGGER_CONTEXTS",
    "GateSurfaceRecord",
    "GateSurfaceRow",
    "JobSelection",
    "TriggerContext",
    "TriggerSummary",
    "collect_record",
    "compose_document",
    "diff_document",
    "evaluate_condition",
    "main",
    "render_document",
    "render_region",
    "run",
    "select_jobs",
    "workflow_trigger_state",
]


# ---------------------------------------------------------------------------
# The three synthetic trigger contexts
# ---------------------------------------------------------------------------


class TriggerContext(BaseModel):
    """One synthetic GitHub event, sufficient to decide ``on:`` and ``if:``.

    The values are the ones GitHub sets for the event being modelled: a pull
    request's ``github.ref`` is the merge ref (which is why every
    ``github.ref == 'refs/heads/main'`` condition is false on a PR - the mechanism
    behind `required-checks.yaml`'s `branch-push-only` ineligibility reason), and a
    tag push is still a ``push`` event with ``ref_type == 'tag'``.
    """

    model_config = ConfigDict(frozen=True)

    id: str
    event_name: str
    ref: str
    ref_name: str
    ref_type: Literal["branch", "tag"]
    base_ref: str = ""
    head_ref: str = ""


TRIGGER_CONTEXTS: Final[tuple[TriggerContext, ...]] = (
    TriggerContext(
        id="push:main",
        event_name="push",
        ref="refs/heads/main",
        ref_name="main",
        ref_type="branch",
    ),
    TriggerContext(
        id="pull_request",
        event_name="pull_request",
        ref="refs/pull/1/merge",
        ref_name="1/merge",
        ref_type="branch",
        base_ref="main",
        head_ref="feature",
    ),
    TriggerContext(
        id="tag:v*",
        event_name="push",
        ref="refs/tags/v1.2.3",
        ref_name="v1.2.3",
        ref_type="tag",
    ),
)


# ---------------------------------------------------------------------------
# Three-valued evaluation of a GitHub expression
# ---------------------------------------------------------------------------


class _Unknown:
    """A value the trigger context does not determine."""

    __slots__ = ()

    def __repr__(self) -> str:  # pragma: no cover - diagnostic only
        return "UNKNOWN"


UNKNOWN: Final[_Unknown] = _Unknown()

_TOKEN_RE: Final[re.Pattern[str]] = re.compile(
    r"""
    (?P<space>\s+)
  | (?P<string>'(?:[^']|'')*')
  | (?P<number>\d+(?:\.\d+)?)
  | (?P<op>&&|\|\||==|!=|>=|<=|!|>|<|\(|\)|,)
  | (?P<ident>[A-Za-z_][A-Za-z0-9_.]*)
""",
    re.VERBOSE,
)

_TRUE_FUNCTIONS: Final[frozenset[str]] = frozenset({"always", "success"})
_OUTCOME_FUNCTIONS: Final[frozenset[str]] = frozenset({"failure", "cancelled"})
_STRING_FUNCTIONS: Final[frozenset[str]] = frozenset({"startsWith", "endsWith", "contains"})


class _ExpressionError(Exception):
    """The expression could not be parsed - the condition is undecidable."""


def _strip_expression(raw: str) -> str:
    """Drop the ``${{ ... }}`` wrapper and fold whitespace."""
    text = " ".join(raw.split())
    while text.startswith("${{") and text.endswith("}}"):
        text = text[3:-2].strip()
    return text


def _tokenize(expression: str) -> list[tuple[str, str]]:
    tokens: list[tuple[str, str]] = []
    index = 0
    while index < len(expression):
        match = _TOKEN_RE.match(expression, index)
        if match is None:
            excerpt = expression[index : index + 20]
            raise _ExpressionError(f"unparsable at offset {index}: {excerpt!r}")
        index = match.end()
        kind = match.lastgroup or ""
        if kind == "space":
            continue
        tokens.append((kind, match.group()))
    return tokens


def _truthy(value: object) -> bool | None:
    """GitHub truthiness: empty string, zero, and null are false."""
    if isinstance(value, _Unknown):
        return None
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return value != ""
    return True


def _coerce(value: object) -> object:
    """GitHub's loose comparison coerces null to the empty string."""
    return "" if value is None else value


def _loose_equal(left: object, right: object) -> bool | None:
    if isinstance(left, _Unknown) or isinstance(right, _Unknown):
        return None
    first, second = _coerce(left), _coerce(right)
    if isinstance(first, str) and isinstance(second, str):
        return first.lower() == second.lower()
    if isinstance(first, bool) or isinstance(second, bool):
        return bool(first) is bool(second)
    if isinstance(first, (int, float)) and isinstance(second, (int, float)):
        return float(first) == float(second)
    return str(first) == str(second)


def _order(left: object, right: object, operator: str) -> bool | None:
    if isinstance(left, _Unknown) or isinstance(right, _Unknown):
        return None
    try:
        first, second = float(left), float(right)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    if operator == "<":
        return first < second
    if operator == "<=":
        return first <= second
    if operator == ">":
        return first > second
    return first >= second


class _Evaluator:
    """Recursive-descent evaluator over the GitHub expression subset in use.

    Unknown propagates the way a reader expects: ``false && unknown`` is false,
    ``true || unknown`` is true, and anything else touching unknown is unknown. The
    unresolved paths and functions are recorded so the rendered note can name the
    reason a job is ``CONDITIONAL`` rather than asserting one.
    """

    def __init__(self, tokens: list[tuple[str, str]], context: TriggerContext) -> None:
        self._tokens = tokens
        self._position = 0
        self._context = context
        self.unresolved: list[str] = []
        self.outcome_dependent = False

    # -- token helpers ----------------------------------------------------
    def _peek(self) -> tuple[str, str] | None:
        return self._tokens[self._position] if self._position < len(self._tokens) else None

    def _take(self) -> tuple[str, str]:
        token = self._peek()
        if token is None:
            raise _ExpressionError("unexpected end of expression")
        self._position += 1
        return token

    def _accept(self, value: str) -> bool:
        token = self._peek()
        if token is not None and token[1] == value:
            self._position += 1
            return True
        return False

    def _expect(self, value: str) -> None:
        if not self._accept(value):
            raise _ExpressionError(f"expected {value!r}")

    # -- grammar ----------------------------------------------------------
    def parse(self) -> object:
        value = self._or_expression()
        if self._peek() is not None:
            raise _ExpressionError(f"trailing tokens from {self._peek()!r}")
        return value

    def _or_expression(self) -> object:
        value = self._and_expression()
        while self._accept("||"):
            right = self._and_expression()
            left_truth, right_truth = _truthy(value), _truthy(right)
            if left_truth is True or right_truth is True:
                value = True
            elif left_truth is None or right_truth is None:
                value = UNKNOWN
            else:
                value = False
        return value

    def _and_expression(self) -> object:
        value = self._not_expression()
        while self._accept("&&"):
            right = self._not_expression()
            left_truth, right_truth = _truthy(value), _truthy(right)
            if left_truth is False or right_truth is False:
                value = False
            elif left_truth is None or right_truth is None:
                value = UNKNOWN
            else:
                value = True
        return value

    def _not_expression(self) -> object:
        if self._accept("!"):
            inner = _truthy(self._not_expression())
            return UNKNOWN if inner is None else not inner
        return self._comparison()

    def _comparison(self) -> object:
        left = self._primary()
        token = self._peek()
        if token is None or token[0] != "op":
            return left
        operator = token[1]
        if operator in {"==", "!="}:
            self._take()
            right = self._primary()
            equal = _loose_equal(left, right)
            if equal is None:
                return UNKNOWN
            return equal if operator == "==" else not equal
        if operator in {"<", "<=", ">", ">="}:
            self._take()
            right = self._primary()
            ordered = _order(left, right, operator)
            return UNKNOWN if ordered is None else ordered
        return left

    def _primary(self) -> object:
        if self._accept("("):
            value = self._or_expression()
            self._expect(")")
            return value
        kind, text = self._take()
        if kind == "string":
            return text[1:-1].replace("''", "'")
        if kind == "number":
            return float(text) if "." in text else int(text)
        if kind != "ident":
            raise _ExpressionError(f"unexpected token {text!r}")
        if self._accept("("):
            arguments: list[object] = []
            if not self._accept(")"):
                arguments.append(self._or_expression())
                while self._accept(","):
                    arguments.append(self._or_expression())
                self._expect(")")
            return self._call(text, arguments)
        return self._lookup(text)

    # -- resolution -------------------------------------------------------
    def _call(self, name: str, arguments: list[object]) -> object:
        if name in _TRUE_FUNCTIONS:
            return True
        if name in _OUTCOME_FUNCTIONS:
            self.outcome_dependent = True
            self._record(f"{name}()")
            return UNKNOWN
        if name in _STRING_FUNCTIONS and len(arguments) == 2:
            first, second = arguments
            if isinstance(first, str) and isinstance(second, str):
                if name == "startsWith":
                    return first.lower().startswith(second.lower())
                if name == "endsWith":
                    return first.lower().endswith(second.lower())
                return second.lower() in first.lower()
        self._record(f"{name}()")
        return UNKNOWN

    def _lookup(self, path: str) -> object:
        lowered = path.lower()
        if lowered == "true":
            return True
        if lowered == "false":
            return False
        if lowered == "null":
            return None
        context = self._context
        known: dict[str, object] = {
            "github.event_name": context.event_name,
            "github.ref": context.ref,
            "github.ref_name": context.ref_name,
            "github.ref_type": context.ref_type,
            "github.base_ref": context.base_ref,
            "github.head_ref": context.head_ref,
        }
        if path in known:
            return known[path]
        # A workflow_dispatch input is absent in all three modelled contexts, so it
        # compares equal to the empty string exactly as GitHub coerces null.
        if path.startswith(("github.event.inputs.", "inputs.")):
            return ""
        self._record(path)
        return UNKNOWN

    def _record(self, name: str) -> None:
        if name not in self.unresolved:
            self.unresolved.append(name)


class ConditionVerdict(BaseModel):
    """The outcome of evaluating one ``if:`` expression in one context."""

    model_config = ConfigDict(frozen=True)

    value: bool | None
    unresolved: tuple[str, ...]
    outcome_dependent: bool
    detail: str


def evaluate_condition(expression: str, context: TriggerContext) -> ConditionVerdict:
    """Evaluate a job ``if:`` expression against one synthetic trigger context.

    ``value`` is ``True`` (the job runs), ``False`` (it does not), or ``None`` -
    undecidable from the trigger alone, which renders ``CONDITIONAL`` rather than
    an assertion either way (I-7).
    """
    text = _strip_expression(expression)
    if not text:
        return ConditionVerdict(
            value=True, unresolved=(), outcome_dependent=False, detail="empty condition"
        )
    try:
        evaluator = _Evaluator(_tokenize(text), context)
        value = evaluator.parse()
    except _ExpressionError as error:
        return ConditionVerdict(
            value=None,
            unresolved=(text,),
            outcome_dependent=False,
            detail=f"unparsable if: ({error})",
        )
    truth = _truthy(value)
    if truth is None:
        reason = ", ".join(evaluator.unresolved) or "undetermined"
        detail = (
            f"if: outcome-dependent ({reason})"
            if evaluator.outcome_dependent
            else f"if: undecidable from trigger ({reason})"
        )
    else:
        detail = f"if: {'true' if truth else 'false'}"
    return ConditionVerdict(
        value=truth,
        unresolved=tuple(evaluator.unresolved),
        outcome_dependent=evaluator.outcome_dependent,
        detail=detail,
    )


# ---------------------------------------------------------------------------
# Does the workflow's `on:` block select this context at all?
# ---------------------------------------------------------------------------


class TriggerMatch(BaseModel):
    """Whether a workflow's ``on:`` block selects one synthetic context."""

    model_config = ConfigDict(frozen=True)

    state: SelectionState
    reason: str


def _event_specs(document: dict[str, object]) -> dict[str, object]:
    """The ``on:`` block as ``event -> spec``.

    ``load_workflow`` has already undone PyYAML's YAML 1.1 resolution of the bare
    key ``on`` to boolean ``True``, so the key is reliably ``"on"`` here.
    """
    block = document.get("on")
    if isinstance(block, str):
        return {block: None}
    if isinstance(block, list):
        return {str(item): None for item in block}
    if isinstance(block, dict):
        return {str(key): value for key, value in block.items()}
    return {}


def _matches_any(value: str, patterns: list[object]) -> bool:
    return any(fnmatchcase(value, str(pattern)) for pattern in patterns)


def _filter_list(spec: dict[str, object], key: str) -> list[object] | None:
    value = spec.get(key)
    return value if isinstance(value, list) else None


def _path_filter_reason(spec: dict[str, object]) -> str | None:
    """The ``paths:``/``paths-ignore:`` filter that makes execution change-set dependent."""
    for key in ("paths", "paths-ignore"):
        patterns = _filter_list(spec, key)
        if patterns:
            shown = ", ".join(str(pattern) for pattern in patterns[:4])
            if len(patterns) > 4:
                shown = f"{shown}, +{len(patterns) - 4} more"
            return f"path-filtered ({key}: {shown})"
    return None


def workflow_trigger_state(document: dict[str, object], context: TriggerContext) -> TriggerMatch:
    """Evaluate a workflow's ``on:`` block against one synthetic context.

    ``conditional`` is returned when the event matches but a path filter decides
    execution, because "runs when the change set happens to touch these paths" is
    not the same claim as "runs" - the distinction `required-checks.yaml` records as
    the `path-filtered` ineligibility reason.
    """
    events = _event_specs(document)
    if context.event_name == "pull_request":
        spec_raw = events.get("pull_request", "__absent__")
        if spec_raw == "__absent__":
            return TriggerMatch(
                state="not-executed", reason="workflow on: has no pull_request trigger"
            )
        spec = spec_raw if isinstance(spec_raw, dict) else {}
        branches = _filter_list(spec, "branches")
        if branches is not None and not _matches_any(context.base_ref, branches):
            return TriggerMatch(
                state="not-executed",
                reason=(f"pull_request branches filter does not select base '{context.base_ref}'"),
            )
        ignored = _filter_list(spec, "branches-ignore")
        if ignored is not None and _matches_any(context.base_ref, ignored):
            return TriggerMatch(
                state="not-executed",
                reason=f"pull_request branches-ignore excludes base '{context.base_ref}'",
            )
        path_reason = _path_filter_reason(spec)
        if path_reason is not None:
            return TriggerMatch(state="conditional", reason=path_reason)
        return TriggerMatch(state="selected", reason="on: pull_request")

    spec_raw = events.get("push", "__absent__")
    if spec_raw == "__absent__":
        return TriggerMatch(state="not-executed", reason="workflow on: has no push trigger")
    spec = spec_raw if isinstance(spec_raw, dict) else {}
    branches = _filter_list(spec, "branches")
    branches_ignore = _filter_list(spec, "branches-ignore")
    tags = _filter_list(spec, "tags")
    tags_ignore = _filter_list(spec, "tags-ignore")

    if context.ref_type == "tag":
        if tags is None and tags_ignore is None:
            if branches is not None or branches_ignore is not None:
                # A `branches:` filter without a `tags:` filter excludes tag pushes
                # entirely: this is why every `startsWith(github.ref, 'refs/tags/v')`
                # job condition in `frontend.yml` is unreachable.
                return TriggerMatch(
                    state="not-executed",
                    reason="on: push is branch-scoped (no tags: filter), so a tag push is excluded",
                )
        elif tags is not None and not _matches_any(context.ref_name, tags):
            return TriggerMatch(
                state="not-executed",
                reason=f"on: push tags filter does not select '{context.ref_name}'",
            )
        elif tags_ignore is not None and _matches_any(context.ref_name, tags_ignore):
            return TriggerMatch(
                state="not-executed",
                reason=f"on: push tags-ignore excludes '{context.ref_name}'",
            )
    else:
        if branches is None and branches_ignore is None:
            if tags is not None or tags_ignore is not None:
                return TriggerMatch(
                    state="not-executed",
                    reason=(
                        "on: push is tag-scoped (no branches: filter), so a branch push is excluded"
                    ),
                )
        elif branches is not None and not _matches_any(context.ref_name, branches):
            return TriggerMatch(
                state="not-executed",
                reason=f"on: push branches filter does not select '{context.ref_name}'",
            )
        elif branches_ignore is not None and _matches_any(context.ref_name, branches_ignore):
            return TriggerMatch(
                state="not-executed",
                reason=f"on: push branches-ignore excludes '{context.ref_name}'",
            )

    path_reason = _path_filter_reason(spec)
    if path_reason is not None:
        return TriggerMatch(state="conditional", reason=path_reason)
    return TriggerMatch(state="selected", reason="on: push")


# ---------------------------------------------------------------------------
# Job selection: `if:` plus the transitive `needs:` walk (R11.9)
# ---------------------------------------------------------------------------


class JobSelection(BaseModel):
    """Whether one job runs under one trigger, and why."""

    model_config = ConfigDict(frozen=True)

    trigger: str
    workflow: str
    job: str
    job_name: str
    state: SelectionState
    reasons: tuple[str, ...]

    @property
    def note(self) -> str:
        """The reasons as one ASCII cell, in the order they were established."""
        return "; ".join(self.reasons) if self.reasons else "-"


def _always_in(condition: str | None) -> bool:
    return condition is not None and "always()" in condition


def select_jobs(
    document: dict[str, object],
    workflow: str,
    context: TriggerContext,
    *,
    job_names: dict[tuple[str, str], str] | None = None,
) -> dict[str, JobSelection]:
    """Classify every job of one workflow under one trigger context.

    The ``needs:`` walk is transitive and memoised. Precedence is fixed, strongest
    first, because more than one reason can apply at once:

    1. the workflow is not selected at all -> ``not-executed``;
    2. the job's ``if:`` is false in this context -> ``not-executed``;
    3. a job it needs is ``not-executed`` -> ``not-executed`` naming that job
       (R11.9), even when its own ``if:`` was undecidable;
    4. anything conditional (path filter, undecidable ``if:``, conditional
       dependency) -> ``conditional``;
    5. otherwise ``selected``.
    """
    trigger = workflow_trigger_state(document, context)
    jobs = dict(iter_jobs(document))
    names = job_names or {}
    memo: dict[str, JobSelection] = {}
    resolving: set[str] = set()

    def build(job_id: str, state: SelectionState, reasons: list[str]) -> JobSelection:
        return JobSelection(
            trigger=context.id,
            workflow=workflow,
            job=job_id,
            job_name=names.get((workflow, job_id), job_id),
            state=state,
            reasons=tuple(reasons),
        )

    def resolve(job_id: str) -> JobSelection:
        cached = memo.get(job_id)
        if cached is not None:
            return cached
        if job_id in resolving:
            selection = build(job_id, "not-executed", [f"needs: cycle through '{job_id}'"])
            memo[job_id] = selection
            return selection
        resolving.add(job_id)
        try:
            selection = _resolve_job(job_id)
        finally:
            resolving.discard(job_id)
        memo[job_id] = selection
        return selection

    def _resolve_job(job_id: str) -> JobSelection:
        job = jobs[job_id]
        if trigger.state == "not-executed":
            return build(job_id, "not-executed", [trigger.reason])

        reasons: list[str] = []
        state: SelectionState = trigger.state
        if trigger.state == "conditional":
            reasons.append(trigger.reason)

        condition = job_if_condition(job)
        if condition is not None:
            verdict = evaluate_condition(condition, context)
            if verdict.value is False:
                return build(job_id, "not-executed", [f"{verdict.detail} in {context.id}"])
            if verdict.value is None:
                state = "conditional"
                reasons.append(verdict.detail)

        for need in job_needs(job):
            if need not in jobs:
                return build(
                    job_id,
                    "not-executed",
                    [f"needs '{need}', which no job in this workflow defines"],
                )
            dependency = resolve(need)
            if dependency.state == "not-executed":
                reason = f"needs '{need}', which is NOT EXECUTED ({dependency.reasons[0]})"
                if _always_in(condition):
                    # `if: always()` would still start the job, but its conclusion is
                    # then derived from dependencies that never ran. R11.9 forbids
                    # reporting that as executed, so the row stays NOT EXECUTED and
                    # the note records the mechanism rather than hiding it.
                    reason = (
                        f"{reason}; if: always() would still start it, so its conclusion "
                        f"is derived from skipped needs, never an independent pass"
                    )
                return build(job_id, "not-executed", [reason])
            if dependency.state == "conditional":
                state = "conditional"
                reasons.append(f"needs '{need}', which is conditional")

        return build(job_id, state, reasons)

    return {job_id: resolve(job_id) for job_id in jobs}


# ---------------------------------------------------------------------------
# Rows
# ---------------------------------------------------------------------------

_ASCII_FOLD: Final[tuple[tuple[str, str], ...]] = (
    ("\u2192", "->"),
    ("\u21d2", "=>"),
    ("\u2190", "<-"),
    ("\u00d7", "x"),
    ("\u2265", ">="),
    ("\u2264", "<="),
    ("\u2713", "ok"),
    ("\u00a0", " "),
)


def _ascii(text: str) -> str:
    """Fold a workflow label to ASCII (Windows console + document contract)."""
    folded = normalize_step_name(text)
    for source, replacement in _ASCII_FOLD:
        folded = folded.replace(source, replacement)
    return "".join(char if ord(char) < 128 else "?" for char in folded)


def _cell(text: str) -> str:
    """One Markdown table cell: ASCII, single-line, pipes escaped."""
    return _ascii(text).replace("|", "\\|").strip() or "-"


def _advisory_in(text: str) -> bool:
    lowered = text.lower()
    return any(marker.lower() in lowered for marker in ADVISORY_MARKERS)


def _step_note(shape: StepShape, job_name: str) -> str:
    """How this step's exit status behaves, in the design's vocabulary.

    The job-level clause mirrors `workflow_shape_truth`'s R11.3 rule exactly: when
    the discarding construct sits on the *job* (`ci.yml`'s
    `v4-compliance (informational)`), the honest label lives on the job name, not on
    each step. Rendering those steps as unlabelled here would contradict the gate
    that enforces the rule.
    """
    if shape.propagates_exit_status:
        return "blocking"
    if shape.advisory_in_name:
        return "advisory (named)"
    construct = shape.discarding_construct or "unknown construct"
    if construct.endswith("(job)") and _advisory_in(job_name):
        return "advisory (named at job level)"
    return f"advisory (unlabelled: {construct})"


class GateSurfaceRow(BaseModel):
    """One row of the generated table (design E1.6)."""

    model_config = ConfigDict(frozen=True)

    trigger: str
    job: str
    step: str
    propagates: Literal["yes", "no", "NOT EXECUTED", "CONDITIONAL"]
    note: str

    def as_markdown(self) -> str:
        return (
            f"| {_cell(self.trigger)} | {_cell(self.job)} | {_cell(self.step)} "
            f"| {self.propagates} | {_cell(self.note)} |"
        )


class TriggerSummary(BaseModel):
    """Per-trigger totals, so the aggregate is readable without counting rows."""

    model_config = ConfigDict(frozen=True)

    trigger: str
    jobs_selected: int
    jobs_conditional: int
    jobs_not_executed: int
    steps_propagating: int
    steps_advisory: int
    steps_conditional: int


class GateSurfaceRecord(BaseModel):
    """Everything one generation observed (design E1.6, AD-2)."""

    model_config = ConfigDict(frozen=True)

    triggers: tuple[str, ...]
    selections: tuple[JobSelection, ...]
    rows: tuple[GateSurfaceRow, ...]
    anchors: tuple[GateSurfaceRow, ...]
    summaries: tuple[TriggerSummary, ...]
    workflow_count: int
    job_count: int
    step_count: int
    anchor_detail: str


# ---------------------------------------------------------------------------
# Declared-blocking anchors (R11.8)
# ---------------------------------------------------------------------------

_COMMAND_PATTERNS: Final[tuple[re.Pattern[str], ...]] = (
    re.compile(r"python3?\s+-m\s+(?P<name>[\w.]+)"),
    re.compile(r"(?P<name>[\w./-]+\.(?:py|sh))"),
)


def _named_commands(script: str, limit: int = 2) -> tuple[str, ...]:
    """The scripts and modules a ``run:`` body names, in order of appearance.

    Used only to annotate the anchor rows. A governance document that calls a gate
    blocking names the *command* (`verify_live.py --external --expect-sha`), not the
    workflow step label, so the anchor cell has to carry the command for an AD-3
    ``blocking-gate`` pin to resolve against this document (R11.8).
    """
    found: list[str] = []
    for pattern in _COMMAND_PATTERNS:
        for match in pattern.finditer(script):
            name = match.group("name")
            if name not in found:
                found.append(name)
    return tuple(found[:limit])


def _declared_step(
    declarations: tuple[BlockingDeclaration, ...], workflow: str, job: str, step_name: str
) -> BlockingDeclaration | None:
    """The declaration that makes this step declared-blocking, if any."""
    for declaration in declarations:
        if declaration.workflow != workflow or declaration.job != job:
            continue
        if declaration.all_steps:
            return declaration
        for declared_name in declaration.step_names:
            if declaration.match == "exact":
                if declared_name == step_name:
                    return declaration
            elif normalize_step_name(declared_name) == normalize_step_name(step_name):
                return declaration
    return None


# ---------------------------------------------------------------------------
# Collection
# ---------------------------------------------------------------------------

_PROPAGATES_BY_STATE: Final[dict[SelectionState, str]] = {
    "not-executed": "NOT EXECUTED",
    "conditional": "CONDITIONAL",
}

#: How the three selection states are spelled in the generated document.
_STATE_LABELS: Final[dict[SelectionState, str]] = {
    "selected": "EXECUTES",
    "conditional": "CONDITIONAL",
    "not-executed": "NOT EXECUTED",
}


def _propagates_cell(state: SelectionState, shape: StepShape) -> str:
    if state == "selected":
        return "yes" if shape.propagates_exit_status else "no"
    return _PROPAGATES_BY_STATE[state]


def _row_note(selection: JobSelection, shape: StepShape) -> str:
    """The step row's note.

    A conditional job's *reason* is recorded once per job in the `Job selection`
    section rather than repeated on each of its steps: the same sentence copied onto
    130 rows makes a drift diff unreadable, which would work against R11.2.
    """
    shape_note = _step_note(shape, selection.job_name)
    if selection.state == "selected":
        return shape_note
    return f"conditional - {shape_note}"


def collect_record(
    directory: Path = WORKFLOW_DIR,
    *,
    declaration_path: Path = BLOCKING_STEPS_FILE,
) -> GateSurfaceRecord:
    """Parse the workflow tree and project the surface for the three contexts."""
    paths = iter_workflow_paths(directory)
    names = job_display_names(directory)
    try:
        declarations = load_blocking_declarations(declaration_path)
        anchor_detail = (
            f"{len(declarations)} declared-blocking entries from "
            f"{workflow_relative_path(declaration_path)}"
        )
    except DeclarationLoadError as error:
        declarations = ()
        anchor_detail = f"declared-blocking set unreadable: {error}"

    documents = {path: load_workflow(path) for path in paths}
    rows: list[GateSurfaceRow] = []
    anchors: list[GateSurfaceRow] = []
    selections: list[JobSelection] = []
    summaries: list[TriggerSummary] = []
    job_total = 0
    step_total = 0

    for context in TRIGGER_CONTEXTS:
        counts = {"selected": 0, "conditional": 0, "not-executed": 0}
        propagating = advisory = conditional_steps = 0
        for path in paths:
            document = documents[path]
            workflow = workflow_relative_path(path)
            triggers = workflow_triggers(document)
            job_selections = select_jobs(document, workflow, context, job_names=names)
            for job_id, job in iter_jobs(document):
                selection = job_selections[job_id]
                selections.append(selection)
                counts[selection.state] += 1
                qualified = f"{workflow}::{job_id}"
                steps = iter_job_steps(job)
                if context is TRIGGER_CONTEXTS[0]:
                    job_total += 1
                    step_total += len(steps)

                if selection.state == "not-executed":
                    rows.append(
                        GateSurfaceRow(
                            trigger=context.id,
                            job=qualified,
                            step="-",
                            propagates="NOT EXECUTED",
                            note=selection.note,
                        )
                    )

                for index, step in enumerate(steps):
                    shape = classify_step(
                        workflow=workflow,
                        job_id=job_id,
                        job=job,
                        step=step,
                        index=index,
                        triggers=triggers,
                    )
                    cell = _propagates_cell(selection.state, shape)
                    if selection.state != "not-executed":
                        rows.append(
                            GateSurfaceRow(
                                trigger=context.id,
                                job=qualified,
                                step=shape.step_name,
                                propagates=cell,  # type: ignore[arg-type]
                                note=_row_note(selection, shape),
                            )
                        )
                        if cell == "yes":
                            propagating += 1
                        elif cell == "no":
                            advisory += 1
                        else:
                            conditional_steps += 1

                    declaration = _declared_step(declarations, workflow, job_id, shape.step_name)
                    if declaration is None:
                        continue
                    commands = _named_commands(step_run_script(step))
                    label = shape.step_name
                    if commands:
                        label = f"{label} [{' '.join(commands)}]"
                    anchor_note = f"declared blocking ({declaration.requirement or 'R1.8'})"
                    if selection.state == "not-executed":
                        anchor_note = f"{anchor_note} - {selection.note}"
                    elif selection.state == "conditional":
                        anchor_note = f"{anchor_note} - conditional ({selection.note})"
                    elif not shape.propagates_exit_status:
                        anchor_note = (
                            f"{anchor_note} - DOES NOT PROPAGATE "
                            f"({shape.discarding_construct or 'unknown construct'})"
                        )
                    anchors.append(
                        GateSurfaceRow(
                            trigger=context.id,
                            job=qualified,
                            step=label,
                            propagates=cell,  # type: ignore[arg-type]
                            note=anchor_note,
                        )
                    )

        summaries.append(
            TriggerSummary(
                trigger=context.id,
                jobs_selected=counts["selected"],
                jobs_conditional=counts["conditional"],
                jobs_not_executed=counts["not-executed"],
                steps_propagating=propagating,
                steps_advisory=advisory,
                steps_conditional=conditional_steps,
            )
        )

    return GateSurfaceRecord(
        triggers=tuple(context.id for context in TRIGGER_CONTEXTS),
        selections=tuple(selections),
        rows=tuple(rows),
        anchors=tuple(anchors),
        summaries=tuple(summaries),
        workflow_count=len(paths),
        job_count=job_total,
        step_count=step_total,
        anchor_detail=anchor_detail,
    )


# ---------------------------------------------------------------------------
# Rendering (AD-2)
# ---------------------------------------------------------------------------

_HEADER: Final[str] = """# SYNAPSE - CI blocking surface (generated)

> Generated by `scripts/audit/gate_surface.py` (design E1.6; R11.1, R11.2, R11.7,
> R11.9). Regenerate with `python -m scripts.audit.gate_surface --write`; CI runs
> `--check`, which prints a unified diff and fails on drift. Hand edits inside the
> generated markers are overwritten - prose outside them survives.
"""

_LEGEND: Final[tuple[str, ...]] = (
    "## Legend",
    "",
    "`Propagates` takes exactly one of four values, and only the first may be read as",
    '"this gate is blocking under this trigger":',
    "",
    "- `yes` - the job runs in this context and the step's exit status decides the",
    "  job's conclusion.",
    "- `no` - the job runs and the step runs, but a discarding construct or",
    "  `continue-on-error` means the step cannot fail the run. The step name must say",
    "  so (R11.3); `scripts/audit/workflow_shape_truth.py` enforces that.",
    "- `NOT EXECUTED` - the workflow's `on:` does not select this context, the job's",
    "  `if:` is false in it, or a job it `needs:` is itself not executed (R11.9).",
    "  Under I-7 this is not a pass: nothing here can be reported successful.",
    "- `CONDITIONAL` - the job runs only given a fact the trigger does not determine:",
    "  a `paths:`/`paths-ignore:` filter (the change set), a workflow-dispatch input,",
    "  or a run outcome such as `failure()`. Also not a pass.",
    "",
    "A conditional or not-executed job's reason is recorded once, per job, in the",
    "`Job selection` section; step rows carry only the step's own shape so that a",
    "drift diff stays readable (R11.2).",
    "",
    "Jobs are named `<workflow file>::<job id>` because job ids repeat across",
    "workflows (`mutation` exists in both `mutation.yml` and `frontend.yml`), and",
    "`infrastructure/quality/required-checks.yaml` and `blocking-steps.yaml` key on",
    "the same pair.",
)


def _summary_table(record: GateSurfaceRecord) -> tuple[str, ...]:
    lines = [
        "## Summary",
        "",
        (
            f"Parsed {record.workflow_count} workflow file(s), {record.job_count} job(s), "
            f"{record.step_count} step(s)."
        ),
        "",
        "| Trigger | Jobs executing | Jobs conditional | Jobs NOT EXECUTED | Steps blocking |"
        " Steps advisory | Steps conditional |",
        "|---|---|---|---|---|---|---|",
    ]
    for summary in record.summaries:
        lines.append(
            f"| {summary.trigger} | {summary.jobs_selected} | {summary.jobs_conditional} "
            f"| {summary.jobs_not_executed} | {summary.steps_propagating} "
            f"| {summary.steps_advisory} | {summary.steps_conditional} |"
        )
    return tuple(lines)


def render_region(record: GateSurfaceRecord) -> str:
    """The generated region: legend, per-trigger summary, surface, anchors."""
    lines: list[str] = []
    lines.extend(_LEGEND)
    lines.append("")
    lines.extend(_summary_table(record))
    lines.append("")
    lines.append("## Job selection")
    lines.append("")
    lines.append(
        "Why each job runs, does not run, or runs conditionally under each trigger. "
        "`needs:` edges are walked transitively, so a job whose dependency is not "
        "selected is NOT EXECUTED and names that dependency (R11.9)."
    )
    lines.append("")
    lines.append("| Trigger | Job | State | Reason |")
    lines.append("|---|---|---|---|")
    for selection in record.selections:
        state = _STATE_LABELS[selection.state]
        lines.append(
            f"| {_cell(selection.trigger)} | "
            f"{_cell(selection.workflow + '::' + selection.job)} | {state} | "
            f"{_cell(selection.note)} |"
        )
    lines.append("")
    lines.append("## Surface")
    lines.append("")
    lines.append("| Trigger | Job | Step | Propagates | Note |")
    lines.append("|---|---|---|---|---|")
    lines.extend(row.as_markdown() for row in record.rows)
    lines.append("")
    lines.append("## Declared-blocking anchors (R11.8)")
    lines.append("")
    lines.append(
        "Every step `infrastructure/quality/blocking-steps.yaml` declares blocking, "
        "annotated with the command it runs so a governance claim can be pinned to a "
        "row. Source: " + record.anchor_detail + "."
    )
    lines.append("")
    lines.append("| Trigger | Job | Step | Propagates | Note |")
    lines.append("|---|---|---|---|---|")
    lines.extend(row.as_markdown() for row in record.anchors)
    return "\n".join(lines)


def compose_document(region: str, existing: str | None) -> str:
    """Wrap the generated region, preserving hand-authored prose outside the markers."""
    if existing is not None and GENERATED_BEGIN in existing and GENERATED_END in existing:
        head = existing.split(GENERATED_BEGIN, 1)[0]
        tail = existing.split(GENERATED_END, 1)[1]
        return f"{head}{GENERATED_BEGIN}\n{region}\n{GENERATED_END}{tail}"
    return f"{_HEADER}\n{GENERATED_BEGIN}\n{region}\n{GENERATED_END}\n"


def render_document(record: GateSurfaceRecord, existing: str | None = None) -> str:
    """The full document text this record projects."""
    return compose_document(render_region(record), existing)


def diff_document(committed: str, generated: str, *, path: Path = SURFACE_DOC) -> str:
    """A unified diff of committed against generated (R11.2, R11.7)."""
    relative = workflow_relative_path(path)
    return "".join(
        difflib.unified_diff(
            committed.splitlines(keepends=True),
            generated.splitlines(keepends=True),
            fromfile=f"{relative} (committed)",
            tofile=f"{relative} (regenerated)",
            n=2,
        )
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

_EXIT_CODES: Final[dict[str, int]] = {"pass": 0, "fail": 1, "unavailable": 2}

_USAGE: Final[str] = (
    "usage: python -m scripts.audit.gate_surface [--check | --write] [--json]\n"
    "  (no flag) / --check : regenerate in memory and diff against the committed record\n"
    "  --write             : rewrite docs/state/GATE_SURFACE.md\n"
    "  --json              : print the machine-readable record\n"
)


def _read_existing(path: Path) -> str | None:
    return path.read_text(encoding="utf-8") if path.is_file() else None


def run(
    *,
    as_json: bool = False,
    write: bool = False,
    path: Path = SURFACE_DOC,
    directory: Path = WORKFLOW_DIR,
    declaration_path: Path = BLOCKING_STEPS_FILE,
) -> int:
    """CLI entry point. ``print`` is acceptable here and nowhere else in this module.

    Every root this reads is a parameter defaulted to this repository's, mirroring
    `workflow_shape_truth.evaluate`. A caller that points ``directory`` at another
    workflow tree must get a verdict about *that* tree and diff it against *its*
    ``path``: leaking this repository's workflows or declared-blocking set into the
    comparison would make the verdict unattributable, and would make Property 11
    unassertable over generated workflows.
    """
    record = collect_record(directory, declaration_path=declaration_path)

    if record.workflow_count == 0 or record.step_count == 0:
        # I-7: no parse means no verdict, not a pass.
        print(
            "[--] verdict=unavailable reason=no workflow step could be read from "
            f"{workflow_relative_path(directory)}"
        )
        return _EXIT_CODES["unavailable"]

    existing = _read_existing(path)
    generated = render_document(record, existing)

    if as_json:
        print(json.dumps(record.model_dump(mode="json"), sort_keys=True, indent=2))
        if write:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(generated, encoding="utf-8", newline="\n")
            return _EXIT_CODES["pass"]
        return _EXIT_CODES["pass"] if existing == generated else _EXIT_CODES["fail"]

    print("Gate surface (E1.6 - R11.1, R11.2, R11.7, R11.9)")
    print(
        f"  parsed           : {record.workflow_count} workflow file(s), "
        f"{record.job_count} job(s), {record.step_count} step(s)"
    )
    for summary in record.summaries:
        print(
            f"  {summary.trigger:<13}: jobs executing={summary.jobs_selected} "
            f"conditional={summary.jobs_conditional} "
            f"NOT EXECUTED={summary.jobs_not_executed}; steps blocking="
            f"{summary.steps_propagating} advisory={summary.steps_advisory} "
            f"conditional={summary.steps_conditional}"
        )
    print(f"  anchors          : {len(record.anchors)} row(s); {record.anchor_detail}")
    print()

    if write:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(generated, encoding="utf-8", newline="\n")
        state = "unchanged" if existing == generated else "rewritten"
        print(f"[OK] {workflow_relative_path(path)} {state} ({len(record.rows)} surface rows)")
        return _EXIT_CODES["pass"]

    if existing is None:
        print(
            f"[XX] verdict=fail reason=no committed record at "
            f"{workflow_relative_path(path)}; run --write"
        )
        return _EXIT_CODES["fail"]

    if existing != generated:
        print(diff_document(existing, generated, path=path), end="")
        print(
            f"[XX] verdict=fail reason={workflow_relative_path(path)} differs from the "
            "parsed workflow tree; regenerate it in the same change (R11.2, R11.7)"
        )
        return _EXIT_CODES["fail"]

    print(
        f"[OK] verdict=pass reason={workflow_relative_path(path)} matches the parsed "
        f"workflow tree ({len(record.rows)} surface rows)"
    )
    return _EXIT_CODES["pass"]


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    known = {"--check", "--write", "--json", "--help", "-h"}
    unknown = [arg for arg in args if arg not in known]
    if unknown or "--help" in args or "-h" in args:
        print(_USAGE)
        return 0 if not unknown else 2
    if "--write" in args and "--check" in args:
        print(_USAGE)
        return 2
    return run(as_json="--json" in args, write="--write" in args)


if __name__ == "__main__":
    sys.exit(main())
