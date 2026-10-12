"""Exit-status propagation truth for the workflow tree (design E1.5).

Feature: purpose-achievement-audit, task 2.10. Requirements R1.8, R6.13, R8.9,
R11.3.

What this gate answers, mechanically: *when a step's command fails, does the run
fail?* A gate whose exit status is discarded is not a gate, and the audit found the
condition in four separate places. This module reads
``infrastructure/quality/blocking-steps.yaml`` (the committed declaration of which
steps MUST propagate) and every ``.github/workflows/*.yml``, classifies each step's
propagation shape, and reports:

* **R1.8 / R8.9** - a step in the declared-blocking set that discards its exit
  status FAILs, naming the workflow file and the step. A declaration that resolves
  to no step in the tree also FAILs: the declaration is the contract, not the label,
  so a rename cannot silently empty the blocking set.
* **R11.3** - a non-propagating step *outside* that set must carry ``ADVISORY`` or
  ``informational`` in its name. ``ci.yml``'s license-audit step and its
  ``agents/`` MyPy step already carry honest labels, so they satisfy the rule as-is.
* **R6.13** - a workflow step *or Makefile recipe line* that invokes the audit-chain
  verifier must exit with the verifier's exit code. The two deploy-time call sites
  (``Makefile::deploy-gcp-verify`` and ``cd-gcp.yml::deploy-to-vm``) discard it
  today; task 7.3 unswallows them. Until then this gate reports them, which is the
  honest state (I-7).
* **AD-12** - ``window.__atlasHarness`` must not reach the shipped bundle. See
  :func:`assert_harness_absent_from_bundle`.

Reading of "propagates its exit status". A step does not propagate when either

1. ``continue-on-error`` is set on the step or on its job (any value that is not a
   literal ``false``; an expression can evaluate true at run time), or
2. the **last effective top-level command** of its ``run:`` script carries one of
   ``|| true``, ``|| echo``, ``; exit 0`` (or is a bare ``exit 0``).

Clause 2 is deliberately about the *last* command. GitHub's default bash shell runs
with ``-e``, so a suppressed *intermediate* command hides that command's status but
not the step's: the step still fails if a later command fails. Command
substitutions (``$(... || true)``), backticks, shell comments, and lines that merely
close a block (``done`` / ``fi`` / ``esac``) are excluded for the same reason - none
of them is the step's own exit status. "Last" is read down to the last element of the
logical line's ``&&`` / ``||`` / ``;`` list (:func:`final_list_element`, R4.12): a
continuation-joined one-liner such as ``ssh --command="a || true && b"`` ends in ``b``,
so its status is ``b``'s and the ``|| true`` masked ``a`` alone. This is the reading
that makes the rule enforceable rather than a sweep over every incidental ``|| true``
in a diagnostics script.

The corrected reading is deliberately not silent (R4.12's second half). A step that
propagates *only because its final command does*, while a continuation-joined command
masks discards earlier in the same list, is reported as a **note** rather than a
finding: :data:`READABILITY_NOTE`, produced by :func:`masked_nonterminal_constructs`
and carried in ``ShapeReport.notes``. A note never moves the verdict, because the step
really does propagate - what it asks for is a readable shape, not an ``ADVISORY``
marker, which on such a step would be a false label (I-7).

Run::

    python -m scripts.audit.workflow_shape_truth            # human report
    python -m scripts.audit.workflow_shape_truth --json     # machine JSON
    python -m scripts.audit.workflow_shape_truth --require-bundle   # after a build

Exit codes: ``0`` pass, ``1`` fail, ``2`` unavailable. ``2`` is non-passing (I-7:
absence of proof is never a pass).

Reuse: the parsing section below (:func:`iter_workflow_paths`,
:func:`load_workflow`, :func:`workflow_triggers`, :func:`iter_jobs`,
:func:`iter_job_steps`, :func:`step_display_name`, :func:`job_needs`,
:func:`job_if_condition`) is the shared workflow reader. ``gate_surface.py``
(task 2.12) walks the same files and imports these instead of re-parsing. Every
read uses ``encoding='utf-8'`` (E-S13-07) and all console output is ASCII.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Final, Literal

import yaml
from pydantic import BaseModel, ConfigDict

ROOT: Final[Path] = Path(__file__).resolve().parents[2]
WORKFLOW_DIR: Final[Path] = ROOT / ".github" / "workflows"
BLOCKING_STEPS_FILE: Final[Path] = ROOT / "infrastructure" / "quality" / "blocking-steps.yaml"
MAKEFILE: Final[Path] = ROOT / "Makefile"
FRONTEND_SRC: Final[Path] = ROOT / "frontend" / "src"
FRONTEND_DIST: Final[Path] = ROOT / "frontend" / "dist"

#: The four exit-status-discarding constructs (design E1.5, Property 4).
DISCARDING_CONSTRUCTS: Final[tuple[str, ...]] = (
    "|| true",
    "|| echo",
    "; exit 0",
    "continue-on-error: true",
)

#: Markers that make a non-propagating step honest rather than a violation (R11.3).
ADVISORY_MARKERS: Final[tuple[str, ...]] = ("ADVISORY", "informational")

#: Command fragments that name the audit-chain verifier (R6.13).
CHAIN_VERIFIER_PATTERNS: Final[tuple[str, ...]] = (
    "orchestrator.audit.cli verify",
    "orchestrator/audit/cli.py verify",
    "synapse_cli.audit_verify",
    "synapse_cli/audit_verify.py",
    "synapse audit verify",
)

#: The browser-harness global that must never reach the shipped bundle (AD-12).
HARNESS_GLOBAL: Final[str] = "__atlasHarness"

_PRODUCTION_SOURCE_SUFFIXES: Final[frozenset[str]] = frozenset(
    {".ts", ".tsx", ".js", ".jsx", ".mts", ".cts", ".mjs", ".cjs", ".html"}
)
#: Shipped, executable bundle artifacts. ``.map`` is excluded on purpose: a source
#: map is not executed by the browser, so scanning it would conflate "the harness
#: source was visible to the bundler" with "the harness reached the bundle".
_BUNDLE_SUFFIXES: Final[frozenset[str]] = frozenset({".js", ".mjs", ".cjs", ".css", ".html"})

_TERMINAL_DISCARD_PATTERNS: Final[tuple[tuple[str, re.Pattern[str]], ...]] = (
    ("|| true", re.compile(r"\|\|\s*true(\s|$|;|&)")),
    ("|| echo", re.compile(r"\|\|\s*echo(\s|$)")),
    ("; exit 0", re.compile(r";\s*exit\s+0(\s|$)")),
)
_BLOCK_TERMINATORS: Final[frozenset[str]] = frozenset({"done", "fi", "esac", "}", ";;", "EOF"})
#: The control operators that end one element of a shell command list and start the
#: next. A single ``|`` is deliberately absent: a pipeline's exit status is its last
#: stage's status, so a pipe does not begin a new list element for this reading.
_LIST_SEPARATOR_RE: Final[re.Pattern[str]] = re.compile(r"&&|\|\||;")
_SUBSTITUTION_RE: Final[re.Pattern[str]] = re.compile(r"\$\([^()]*\)")
_BACKTICK_RE: Final[re.Pattern[str]] = re.compile(r"`[^`]*`")
_CONDITIONAL_HEADS: Final[tuple[str, ...]] = ("if ", "elif ", "while ", "until ", "case ", "for ")

__all__ = [
    "ADVISORY_MARKERS",
    "CHAIN_VERIFIER_PATTERNS",
    "DISCARDING_CONSTRUCTS",
    "HARNESS_GLOBAL",
    "READABILITY_NOTE",
    "WORKFLOW_DIR",
    "BlockingDeclaration",
    "BundleAssertion",
    "ShapeFinding",
    "ShapeNote",
    "ShapeReport",
    "StepShape",
    "assert_harness_absent_from_bundle",
    "classify_step",
    "collect_step_shapes",
    "effective_command_lines",
    "evaluate",
    "final_list_element",
    "iter_job_steps",
    "iter_jobs",
    "iter_workflow_paths",
    "job_if_condition",
    "job_needs",
    "load_blocking_declarations",
    "load_workflow",
    "masked_nonterminal_constructs",
    "normalize_step_name",
    "run",
    "step_display_name",
    "terminal_discarding_construct",
    "workflow_triggers",
]


# ---------------------------------------------------------------------------
# Workflow parsing (shared with gate_surface.py, task 2.12)
# ---------------------------------------------------------------------------


def iter_workflow_paths(directory: Path = WORKFLOW_DIR) -> tuple[Path, ...]:
    """Every workflow file under ``directory``, in sorted path order."""
    if not directory.is_dir():
        return ()
    return tuple(
        sorted(
            path
            for path in directory.iterdir()
            if path.is_file() and path.suffix in {".yml", ".yaml"}
        )
    )


def load_workflow(path: Path) -> dict[str, object]:
    """Parse one workflow file into a plain mapping (``{}`` when unusable)."""
    raw: object = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        return {}
    return {("on" if key is True else str(key)): value for key, value in raw.items()}


def workflow_relative_path(path: Path) -> str:
    """POSIX path relative to the repository root, as the declaration writes it."""
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def workflow_triggers(document: dict[str, object]) -> tuple[str, ...]:
    """The trigger contexts a workflow's ``on:`` block selects.

    Vocabulary matches ``tests/verify/strategies.py``: ``push:main``,
    ``pull_request``, ``tag:v*``, ``schedule``, ``workflow_dispatch``. PyYAML
    resolves the bare key ``on`` to ``True`` (YAML 1.1), which
    :func:`load_workflow` normalises back to ``"on"``.
    """
    block = document.get("on")
    if isinstance(block, str):
        events: dict[str, object] = {block: None}
    elif isinstance(block, list):
        events = {str(item): None for item in block}
    elif isinstance(block, dict):
        events = {str(key): value for key, value in block.items()}
    else:
        return ()

    triggers: list[str] = []
    for event, spec in events.items():
        if event == "push":
            detail = spec if isinstance(spec, dict) else {}
            branches = detail.get("branches")
            tags = detail.get("tags")
            if not isinstance(branches, list) or any(str(branch) == "main" for branch in branches):
                triggers.append("push:main")
            if isinstance(tags, list) and tags:
                triggers.append("tag:v*")
        elif event == "pull_request":
            triggers.append("pull_request")
        elif event == "schedule":
            triggers.append("schedule")
        elif event == "workflow_dispatch":
            triggers.append("workflow_dispatch")
        else:
            triggers.append(event)
    return tuple(dict.fromkeys(triggers))


def iter_jobs(document: dict[str, object]) -> tuple[tuple[str, dict[str, object]], ...]:
    """Every ``(job_id, job)`` pair declared by a workflow, in file order."""
    jobs = document.get("jobs")
    if not isinstance(jobs, dict):
        return ()
    return tuple(
        (str(job_id), {str(key): value for key, value in job.items()})
        for job_id, job in jobs.items()
        if isinstance(job, dict)
    )


def iter_job_steps(job: dict[str, object]) -> tuple[dict[str, object], ...]:
    """Every step of one job, in file order."""
    steps = job.get("steps")
    if not isinstance(steps, list):
        return ()
    return tuple(
        {str(key): value for key, value in step.items()} for step in steps if isinstance(step, dict)
    )


def job_needs(job: dict[str, object]) -> tuple[str, ...]:
    """The job ids this job declares a ``needs:`` edge to."""
    needs = job.get("needs")
    if isinstance(needs, str):
        return (needs,)
    if isinstance(needs, list):
        return tuple(str(item) for item in needs)
    return ()


def job_if_condition(job: dict[str, object]) -> str | None:
    """The job's ``if:`` expression, verbatim, or ``None``."""
    condition = job.get("if")
    return None if condition is None else str(condition)


def step_display_name(step: dict[str, object], index: int) -> str:
    """The name a run log shows for a step.

    Named steps use their name. An unnamed ``uses:`` step is identified by the
    action it runs, an unnamed ``run:`` step by its first command line - the same
    identification a reader of the workflow file makes, so a finding can be located.
    """
    name = step.get("name")
    if isinstance(name, str) and name.strip():
        return name.strip()
    uses = step.get("uses")
    if isinstance(uses, str) and uses.strip():
        return f"uses: {uses.strip()}"
    run = step.get("run")
    if isinstance(run, str):
        for line in run.splitlines():
            if line.strip():
                return f"run: {line.strip()[:60]}"
    return f"step #{index}"


def normalize_step_name(name: str) -> str:
    """Fold the punctuation the workflows use into ASCII for comparison.

    ``blocking-steps.yaml`` is ASCII-only (Windows console contract) while the
    workflow step names carry em dashes and section signs. Both sides are folded
    with this function, so the comparison is exact on the folded form and the
    declaration file never has to embed a non-ASCII byte.
    """
    folded = name
    for dash in ("\u2014", "\u2013", "\u2212", "\u2010", "\u2011"):
        folded = folded.replace(dash, "-")
    folded = folded.replace("\u00a7", "")
    folded = folded.replace("\u2022", "-").replace("\u00b7", "-")
    return " ".join(folded.split())


# ---------------------------------------------------------------------------
# Shell-shape classification
# ---------------------------------------------------------------------------


def _strip_trailing_comment(line: str) -> str:
    """Drop a trailing ``#`` comment that is outside quotes."""
    quote: str | None = None
    for index, char in enumerate(line):
        if quote is not None:
            if char == quote:
                quote = None
            continue
        if char in {"'", '"'}:
            quote = char
        elif char == "#" and (index == 0 or line[index - 1].isspace()):
            return line[:index].rstrip()
    return line


def _strip_substitutions(line: str) -> str:
    """Remove command substitutions: their status is not the step's status."""
    previous = ""
    current = line
    while current != previous:
        previous = current
        current = _SUBSTITUTION_RE.sub(" ", current)
    return _BACKTICK_RE.sub(" ", current)


def _logical_lines(script: str) -> tuple[tuple[str, bool], ...]:
    """Each top-level command of *script*, paired with "a continuation built this".

    One join implementation, two readers. :func:`effective_command_lines` wants the
    text only; :func:`masked_nonterminal_constructs` also needs to know whether the
    logical line it is looking at was assembled from several physical lines, because
    that - and only that - is the class R4.12 reports as unreadable. A second copy of
    this loop would be a second thing to drift.
    """
    logical: list[tuple[str, bool]] = []
    buffer = ""
    joined = False
    for raw in script.splitlines():
        stripped = _strip_trailing_comment(raw.strip())
        if not buffer:
            if not stripped:
                continue
            buffer = stripped
        else:
            buffer = f"{buffer} {stripped}"
            joined = True
        if buffer.endswith("\\"):
            buffer = buffer[:-1].rstrip()
            continue
        logical.append((buffer, joined))
        buffer = ""
        joined = False
    if buffer:
        logical.append((buffer, joined))

    cleaned = [(_strip_substitutions(line).strip(), flag) for line, flag in logical]
    return tuple((line, flag) for line, flag in cleaned if line)


def effective_command_lines(script: str) -> tuple[str, ...]:
    """The top-level commands of a ``run:`` script, one per logical line.

    Line continuations are joined, comments and command substitutions are removed.
    What remains is what the shell executes at the top level, which is what decides
    the step's exit status.
    """
    return tuple(line for line, _joined in _logical_lines(script))


def _final_separator_start(line: str) -> int | None:
    """Index of the last ``&&`` / ``||`` / ``;`` in *line*, or ``None`` if it holds none.

    One split point, two readers: :func:`final_list_element` takes the text after it
    and :func:`masked_nonterminal_constructs` the text before it. Deriving the head and
    the tail from the same index is what keeps them exhaustive and disjoint.
    """
    separators = list(_LIST_SEPARATOR_RE.finditer(line))
    return separators[-1].start() if separators else None


def final_list_element(line: str) -> str:
    """The trailing element of *line*'s ``&&`` / ``||`` / ``;`` command list.

    The returned text keeps its leading operator, so the caller's patterns still see
    ``|| true`` / ``|| echo`` / ``; exit 0`` as whole constructs rather than bare words.
    A line with no control operator is returned unchanged.

    Why this exists (requirement R4.12). :func:`effective_command_lines` joins line
    continuations into one logical line, which is correct - a backslash-continued
    ``gcloud compute ssh ... --command="a && b || true && c"`` really is one command the
    shell runs once. But :func:`terminal_discarding_construct` then ran an *unanchored*
    ``re.search`` over that whole logical line, so any ``|| true`` **anywhere inside** it
    condemned the step. That reading contradicts the rule the module docstring states and
    that :func:`effective_command_lines` implements everywhere else: only the *last*
    command decides the step's exit status. In an ``A || true && B`` list the shell's
    status is ``B``'s - ``|| true`` masked ``A``, not the step.

    The concrete defect this closes: ``cd-gcp.yml`` ``deploy-to-vm``::"Pull + restart
    stack" is one continuation-joined ``gcloud compute ssh --command=...`` whose remote
    chain suppresses four intermediate housekeeping commands (``compose down``,
    ``docker image prune``, ``docker builder prune``, ``df``) and then ends with a
    ``docker compose ... images | xargs docker inspect`` whose status IS the step's. The
    step propagates; the gate reported it as an unlabelled advisory. Attaching an
    ``ADVISORY`` marker to that step to silence the finding would have been a false
    label, and relabelling a deploy step as non-blocking to make a gate green is exactly
    the trade I-7 forbids - so the reading is corrected instead and ``cd-gcp.yml`` is not
    touched.

    Same defect class as :func:`strip_js_comments` further down this module, and the same
    shape of fix: narrow the text the regex is allowed to see rather than complicate the
    regex. Third occurrence in this tree of "a checker that matches a literal textually
    cannot tell a subject from its context", so the class is named rather than patched
    silently again.

    Splitting is textual and ignores quoting, deliberately. The operators that matter
    here live inside the quoted ``--command="..."`` payload of every ``gcloud compute
    ssh`` step in ``cd-gcp.yml``: a quote-aware split would treat that payload as one
    opaque element and reproduce the very false positive this closes. The residual
    imprecision is a ``;`` or ``&&`` inside a string literal *after* a genuine terminal
    discard (``cmd || true; echo "a; b"`` reads as propagating), which no site in the
    tree exhibits. It is recorded rather than hidden, because the alternative
    imprecision - the quote-aware one - mislabels a live deploy step today.
    """
    cut = _final_separator_start(line)
    if cut is None:
        return line
    # Trailing quote characters are stripped so a payload's closing `"` cannot hide the
    # construct from the patterns' `(\s|$|;|&)` tail: `--command="cmd || true"` must read
    # as `|| true`, not as the unmatchable `true"`.
    return line[cut:].rstrip("\"'").rstrip()


def masked_nonterminal_constructs(script: str) -> tuple[str, ...]:
    """The discards a continuation-joined command hides mid-list, in declaration order.

    Empty for every other shape. This is the *disclosure* half of R4.12, and it exists
    because the corrected reading in :func:`final_list_element` is silent by
    construction: once ``cd-gcp.yml`` ``deploy-to-vm``::"Pull + restart stack" is read
    as propagating, the gate has nothing left to say about it, and a step whose exit
    status can only be worked out by joining seven physical lines and finding the end of
    an ``&&`` chain is still hard to read. R4.12 asks for exactly that disposition: such
    a step is reported as **a shape defect to be made readable rather than one to be
    labelled**, because an ``ADVISORY`` marker on a step whose final command decides its
    exit status would be a false label (I-7).

    What a note is not: a finding. It carries no rule from :data:`_RULES`, it never
    moves the verdict, and :func:`evaluate` emits one only for a step that **does**
    propagate. Making it a finding would re-create the false positive this whole
    correction removed, one rule to the left.

    Scope is deliberately narrow - only a logical line a *continuation* built. A
    multi-line script whose intermediate ``|| true`` sits on its own physical line is
    already readable as written: ``frontend.yml`` ``e2e-visual``::"Generate + commit
    Linux baselines if none are committed yet" is that case (its ``|| true`` is one
    visible line inside an ``if`` block and the script's last effective line is ``fi``),
    and it is deliberately **not** noted here. Widening the class to every incidental
    ``|| true`` in a diagnostics script would turn a disclosure into noise, and noise is
    what the recorded-debt list already showed nobody reads.
    """
    masked: list[str] = []
    for line, joined in _logical_lines(script):
        if not joined:
            continue
        cut = _final_separator_start(line)
        if cut is None:
            continue
        head = line[:cut]
        for construct, pattern in _TERMINAL_DISCARD_PATTERNS:
            if construct not in masked and pattern.search(f"{head} "):
                masked.append(construct)
    return tuple(masked)


def terminal_discarding_construct(script: str) -> str | None:
    """The construct that discards a ``run:`` script's own exit status, if any.

    ``None`` means the script's last top-level command decides the step's status.
    """
    lines = effective_command_lines(script)
    if not lines:
        return None
    last = lines[-1]
    if last in _BLOCK_TERMINATORS or any(last.startswith(head) for head in _CONDITIONAL_HEADS):
        return None
    # The block-terminator and conditional-head tests above read the WHOLE logical line,
    # because it is the line as a whole that is a `fi` or opens an `if`. Only the search
    # for a discarding construct narrows to the final list element (R4.12).
    tail = final_list_element(last)
    if tail == "exit 0":
        return "; exit 0"
    for construct, pattern in _TERMINAL_DISCARD_PATTERNS:
        if pattern.search(f"{tail} "):
            return construct
    return None


def _continue_on_error_construct(container: dict[str, object], scope: str) -> str | None:
    """``continue-on-error`` as a discarding construct, or ``None``.

    Any value other than a literal ``false`` counts: an expression such as
    ``${{ contains(matrix.module, 'oracle') }}`` can evaluate true at run time, and
    a step that *might* not propagate does not propagate as a guarantee.
    """
    if "continue-on-error" not in container:
        return None
    value = container["continue-on-error"]
    if value is False:
        return None
    if value is True:
        base = "continue-on-error: true"
    elif isinstance(value, str) and value.strip().lower() == "false":
        return None
    else:
        base = f"continue-on-error: {value}"
    return base if scope == "step" else f"{base} (job)"


def _advisory_in(text: str) -> bool:
    lowered = text.lower()
    return any(marker.lower() in lowered for marker in ADVISORY_MARKERS)


class StepShape(BaseModel):
    """One workflow step's propagation shape (design E1.5)."""

    model_config = ConfigDict(frozen=True)

    workflow: str
    job: str
    step_name: str
    triggers: tuple[str, ...]
    propagates_exit_status: bool
    discarding_construct: str | None
    advisory_in_name: bool
    #: R4.12: discards this step's own continuation-joined command masks mid-list while
    #: its final command still decides the exit status. Populated only when the step
    #: propagates, so it is never a second name for `discarding_construct`.
    masked_nonterminal_constructs: tuple[str, ...] = ()


def classify_step(
    *,
    workflow: str,
    job_id: str,
    job: dict[str, object],
    step: dict[str, object],
    index: int,
    triggers: tuple[str, ...],
) -> StepShape:
    """Classify one step against the four discarding constructs."""
    run = step.get("run")
    script = run if isinstance(run, str) else ""
    construct = _continue_on_error_construct(step, "step")
    if construct is None:
        construct = _continue_on_error_construct(job, "job")
    if construct is None and script:
        construct = terminal_discarding_construct(script)

    step_name = step_display_name(step, index)
    return StepShape(
        workflow=workflow,
        job=job_id,
        step_name=step_name,
        triggers=triggers,
        propagates_exit_status=construct is None,
        discarding_construct=construct,
        advisory_in_name=_advisory_in(step_name),
        # Read only for a step that propagates (R4.12). A step that does not propagate
        # owes a declaration or an honest label, and reporting a readability note beside
        # that obligation would blur the two dispositions the requirement separates.
        masked_nonterminal_constructs=(
            masked_nonterminal_constructs(script) if construct is None and script else ()
        ),
    )


def collect_step_shapes(directory: Path = WORKFLOW_DIR) -> tuple[StepShape, ...]:
    """Classify every step of every workflow under ``directory``."""
    shapes: list[StepShape] = []
    for path in iter_workflow_paths(directory):
        document = load_workflow(path)
        triggers = workflow_triggers(document)
        workflow = workflow_relative_path(path)
        for job_id, job in iter_jobs(document):
            for index, step in enumerate(iter_job_steps(job)):
                shapes.append(
                    classify_step(
                        workflow=workflow,
                        job_id=job_id,
                        job=job,
                        step=step,
                        index=index,
                        triggers=triggers,
                    )
                )
    return tuple(shapes)


def step_run_script(step: dict[str, object]) -> str:
    """The step's ``run:`` body, or an empty string for a ``uses:`` step."""
    run = step.get("run")
    return run if isinstance(run, str) else ""


# ---------------------------------------------------------------------------
# The committed declaration (infrastructure/quality/blocking-steps.yaml)
# ---------------------------------------------------------------------------


class BlockingDeclaration(BaseModel):
    """One ``steps:`` entry of ``blocking-steps.yaml``.

    ``all_steps`` declares a whole job blocking (R8.9 declares two frontend jobs
    that way). ``step_names`` declares named steps. The two are exclusive in
    practice; if both are present, ``all_steps`` wins because it is the wider claim.
    """

    model_config = ConfigDict(frozen=True)

    workflow: str
    job: str
    step_names: tuple[str, ...] = ()
    all_steps: bool = False
    match: Literal["exact", "normalized"] = "normalized"
    requirement: str | None = None


class DeclarationLoadError(Exception):
    """The declaration file is absent or unusable - the gate is unavailable."""


def load_blocking_declarations(
    path: Path = BLOCKING_STEPS_FILE,
) -> tuple[BlockingDeclaration, ...]:
    """Read the declared-blocking set.

    Only the ``steps:`` key is read. ``pending:`` and
    ``unlabelled_discarding_steps:`` are documentation of known obligations - by
    design, listing a step there neither makes it blocking nor exempts it.
    """
    if not path.is_file():
        raise DeclarationLoadError(f"declaration file not found: {workflow_relative_path(path)}")
    raw: object = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise DeclarationLoadError(
            f"declaration file is not a mapping: {workflow_relative_path(path)}"
        )
    entries = raw.get("steps")
    if not isinstance(entries, list) or not entries:
        raise DeclarationLoadError(
            f"declaration file declares no blocking steps: {workflow_relative_path(path)}"
        )

    declarations: list[BlockingDeclaration] = []
    for entry in entries:
        if not isinstance(entry, dict):
            raise DeclarationLoadError(f"declaration entry is not a mapping: {entry!r}")
        names = entry.get("step_names")
        declarations.append(
            BlockingDeclaration(
                workflow=str(entry.get("workflow", "")),
                job=str(entry.get("job", "")),
                step_names=tuple(str(name) for name in names) if isinstance(names, list) else (),
                all_steps=entry.get("all_steps") is True,
                match="exact" if str(entry.get("match", "normalized")) == "exact" else "normalized",
                requirement=(
                    str(entry["requirement"]) if entry.get("requirement") is not None else None
                ),
            )
        )
    return tuple(declarations)


# ---------------------------------------------------------------------------
# Findings and the report
# ---------------------------------------------------------------------------

_RULES: Final[tuple[str, ...]] = (
    "blocking-discards",
    "blocking-unresolved",
    "chain-verifier-discards",
    "unlabelled-advisory",
)


#: The one disclosure class this gate reports without failing on it (R4.12).
READABILITY_NOTE: Final[str] = "masked-nonterminal-discard"


class ShapeFinding(BaseModel):
    """One violation, naming the file and the step (R1.8's naming obligation)."""

    model_config = ConfigDict(frozen=True)

    rule: str
    requirement: str
    workflow: str
    job: str
    step_name: str
    detail: str


class ShapeNote(BaseModel):
    """One disclosed shape defect that is NOT a rule finding (R4.12).

    Separate model, and the field is ``note`` rather than ``rule``, so nothing can read
    a note as a finding: the verdict is the disjunction of :data:`_RULES` and a note
    belongs to none of them. What a note says is "this step propagates, and you had to
    join its lines to know that" - a readability obligation on the workflow author, not
    a label obligation and not a red gate.
    """

    model_config = ConfigDict(frozen=True)

    note: str
    requirement: str
    workflow: str
    job: str
    step_name: str
    detail: str


class BundleAssertion(BaseModel):
    """The AD-12 production-bundle assertion outcome."""

    model_config = ConfigDict(frozen=True)

    status: Literal["pass", "fail", "skip"]
    files_scanned: int
    offending_files: tuple[str, ...]
    detail: str


class ShapeReport(BaseModel):
    """Everything one execution of this gate observed."""

    model_config = ConfigDict(frozen=True)

    shapes: tuple[StepShape, ...]
    declarations: tuple[BlockingDeclaration, ...]
    findings: tuple[ShapeFinding, ...]
    bundle: BundleAssertion
    verdict: Literal["pass", "fail", "unavailable"]
    reason: str
    #: R4.12 disclosures. Never affect `verdict`; see :class:`ShapeNote`.
    notes: tuple[ShapeNote, ...] = ()


def _declared_keys(
    declarations: tuple[BlockingDeclaration, ...],
    shapes: tuple[StepShape, ...],
) -> tuple[frozenset[tuple[str, str, str]], tuple[ShapeFinding, ...]]:
    """Resolve declarations against the tree.

    Returns the resolved ``(workflow, job, step)`` keys plus one
    ``blocking-unresolved`` finding per declaration that names something the tree
    does not contain. An unresolvable declaration is a failure, not a no-op: the
    declaration is the contract, so a renamed or deleted step must be loud.
    """
    by_job: dict[tuple[str, str], tuple[StepShape, ...]] = {}
    for shape in shapes:
        by_job.setdefault((shape.workflow, shape.job), ())
        by_job[(shape.workflow, shape.job)] += (shape,)

    keys: set[tuple[str, str, str]] = set()
    findings: list[ShapeFinding] = []
    for declaration in declarations:
        requirement = declaration.requirement or "R1.8"
        job_shapes = by_job.get((declaration.workflow, declaration.job))
        if job_shapes is None:
            findings.append(
                ShapeFinding(
                    rule="blocking-unresolved",
                    requirement=requirement,
                    workflow=declaration.workflow,
                    job=declaration.job,
                    step_name="(job)",
                    detail=(
                        "declared-blocking job resolves to no job in the workflow tree; "
                        "the declaration is the contract, so this cannot pass silently"
                    ),
                )
            )
            continue

        if declaration.all_steps:
            keys.update((shape.workflow, shape.job, shape.step_name) for shape in job_shapes)
            continue

        for declared_name in declaration.step_names:
            matched = [
                shape
                for shape in job_shapes
                if (
                    shape.step_name == declared_name
                    if declaration.match == "exact"
                    else normalize_step_name(shape.step_name) == normalize_step_name(declared_name)
                )
            ]
            if not matched:
                findings.append(
                    ShapeFinding(
                        rule="blocking-unresolved",
                        requirement=requirement,
                        workflow=declaration.workflow,
                        job=declaration.job,
                        step_name=declared_name,
                        detail=(
                            f"declared-blocking step resolves to no step in job "
                            f"'{declaration.job}' (match={declaration.match})"
                        ),
                    )
                )
                continue
            keys.update((shape.workflow, shape.job, shape.step_name) for shape in matched)
    return frozenset(keys), tuple(findings)


def _names_chain_verifier(script: str) -> bool:
    return any(pattern in script for pattern in CHAIN_VERIFIER_PATTERNS)


def _chain_verifier_swallow(script: str) -> str | None:
    """The construct that discards the chain verifier's OWN exit code inside *script*.

    Kept separate from :func:`terminal_discarding_construct` because R6.13 and R11.3 ask
    different questions. R11.3 asks whether the *step* propagates, which
    :func:`final_list_element` correctly reads off the last element of the command list.
    R6.13 asks whether *the verifier's* exit code reaches the step's, and that can be
    discarded by a construct that is not terminal: in
    ``... audit.cli verify || echo warn && something`` the step exits with
    ``something``'s status while the verifier's failure is gone. Narrowing this search
    the way R11.3's was narrowed would therefore have turned the R4.12 correction into a
    silent weakening of R6.13 - so the search here stays unanchored, and is only bounded
    to the text *after* the verifier fragment, since a discard that precedes the verifier
    cannot suppress it.
    """
    for line in effective_command_lines(script):
        offsets = [line.find(fragment) for fragment in CHAIN_VERIFIER_PATTERNS]
        reached = [offset for offset in offsets if offset >= 0]
        if not reached:
            continue
        after_verifier = line[min(reached) :]
        for construct, pattern in _TERMINAL_DISCARD_PATTERNS:
            if pattern.search(f"{after_verifier} "):
                return construct
    return None


def _chain_verifier_workflow_findings(
    directory: Path = WORKFLOW_DIR,
) -> tuple[ShapeFinding, ...]:
    """R6.13 for workflow steps that invoke the chain verifier."""
    findings: list[ShapeFinding] = []
    for path in iter_workflow_paths(directory):
        document = load_workflow(path)
        triggers = workflow_triggers(document)
        workflow = workflow_relative_path(path)
        for job_id, job in iter_jobs(document):
            for index, step in enumerate(iter_job_steps(job)):
                script = step_run_script(step)
                if not script or not _names_chain_verifier(script):
                    continue
                shape = classify_step(
                    workflow=workflow,
                    job_id=job_id,
                    job=job,
                    step=step,
                    index=index,
                    triggers=triggers,
                )
                # Two ways the verifier's code can be lost: the STEP does not propagate
                # (`continue-on-error`, or a terminal discard), or the step propagates
                # something else while the verifier's own status is swallowed mid-list.
                # The second is what `_chain_verifier_swallow` adds; without it the
                # R4.12 narrowing of `terminal_discarding_construct` would have relaxed
                # R6.13 as a side effect.
                construct = shape.discarding_construct or _chain_verifier_swallow(script)
                if construct is None:
                    continue
                findings.append(
                    ShapeFinding(
                        rule="chain-verifier-discards",
                        requirement="R6.13",
                        workflow=workflow,
                        job=job_id,
                        step_name=shape.step_name,
                        detail=(
                            f"step invokes the audit-chain verifier but discards its exit "
                            f"status via `{construct}`"
                        ),
                    )
                )
    return tuple(findings)


def _chain_verifier_makefile_findings(path: Path | None = MAKEFILE) -> tuple[ShapeFinding, ...]:
    """R6.13 for Makefile recipe lines that invoke the chain verifier.

    Two Make-specific discarding constructs are recognised: a leading ``-`` on the
    recipe line (Make ignores the command's status) and the shell constructs the
    workflow rule already covers.

    This search stays UNANCHORED and deliberately does not use
    :func:`final_list_element`. R6.13 asks whether *the verifier's* exit code survives,
    not whether the recipe line as a whole ends in a discard - so in
    ``python -m orchestrator.audit.cli verify || echo warn && something`` the verifier's
    status is discarded even though the line's status is ``something``'s. The narrowing
    that is correct for R11.3 (the step's own status) would be a false negative here.

    ``None`` (or an absent path) means there is no Makefile in scope, which is what
    :func:`evaluate` passes when it is pointed at a workflow tree other than this
    repository's - a recipe line in *this* Makefile is not a finding about *that*
    tree.
    """
    if path is None or not path.is_file():
        return ()
    findings: list[ShapeFinding] = []
    target = "(no target)"
    for raw in path.read_text(encoding="utf-8").splitlines():
        if raw and not raw.startswith(("\t", " ", "#")) and ":" in raw:
            target = raw.split(":", 1)[0].strip() or target
            continue
        if not raw.startswith("\t"):
            continue
        line = raw.lstrip("\t").strip()
        if not _names_chain_verifier(line):
            continue
        constructs: list[str] = []
        if line.startswith("-"):
            constructs.append("leading `-` (Make ignores errors)")
        body = line.lstrip("-@").strip()
        for construct, pattern in _TERMINAL_DISCARD_PATTERNS:
            if pattern.search(f"{body} "):
                constructs.append(construct)
        if not constructs:
            continue
        findings.append(
            ShapeFinding(
                rule="chain-verifier-discards",
                requirement="R6.13",
                workflow=workflow_relative_path(path),
                job=target,
                step_name=line[:80],
                detail=(
                    "Makefile recipe invokes the audit-chain verifier but discards its "
                    f"exit status via {', '.join(constructs)}"
                ),
            )
        )
    return tuple(findings)


# ---------------------------------------------------------------------------
# AD-12 - the production-bundle assertion
# ---------------------------------------------------------------------------


#: A ``//`` that opens a line comment rather than closing a URL scheme. Requiring the
#: slashes not to be preceded by ``:`` keeps ``https://example.com`` from truncating a
#: line that also carries real code.
_LINE_COMMENT_RE: Final[re.Pattern[str]] = re.compile(r"(?<!:)//")

#: A ``/* ... */`` block, including the JSDoc headers every module in this tree opens
#: with. Non-greedy and DOTALL so consecutive blocks are removed independently.
_BLOCK_COMMENT_RE: Final[re.Pattern[str]] = re.compile(r"/\*.*?\*/", re.DOTALL)


def strip_js_comments(text: str) -> str:
    """*text* with ``/* ... */`` and ``// ...`` comment bodies removed.

    Why the AD-12 scan needs this at all. The scan used to be a bare
    ``HARNESS_GLOBAL in text``, and `frontend/src/lib/interruption-precision.ts:101`
    carries the line::

        // touches `window.__atlasHarness` (AD-12); every function is pure and total

    - a comment stating the module does **not** touch the global. The gate read its own
    subject matter as a violation and reported ``bundle-assertion=fail``, which is the
    same defect class ``ledger_gen`` carried until task 12.5: a checker that counts a
    literal textually cannot tell prose *about* the thing from the thing. Second
    occurrence in this repo, so it is worth naming as a class rather than patching twice.

    This stays fail-closed with respect to executable code: a mention inside a comment
    cannot execute and cannot reach a bundle's runtime surface, so removing comment
    bodies can only drop occurrences that were never violations. The residual imprecision
    is the other way round - a ``//`` inside a string literal (other than a URL scheme,
    which is guarded) would truncate the rest of that line and could hide a real
    occurrence. Callers therefore report documentation-only mentions rather than
    discarding them silently (I-7), so a mention that *is* a violation still surfaces as
    a named row for a human to judge.

    Block comments are removed first: a ``//`` inside a JSDoc header would otherwise
    truncate the header's own line and leave the rest of the block unstripped.
    """
    without_blocks = _BLOCK_COMMENT_RE.sub(" ", text)
    return "\n".join(
        _LINE_COMMENT_RE.split(line, maxsplit=1)[0] for line in without_blocks.splitlines()
    )


def _scan_for_harness(
    root: Path, suffixes: frozenset[str]
) -> tuple[int, tuple[str, ...], tuple[str, ...]]:
    """Scan *root* for the harness global.

    Returns ``(scanned, offenders, documented_only)``. ``offenders`` name the global in
    executable code and are the AD-12 failure. ``documented_only`` name it solely inside
    a comment - reported, never failed, and never silently dropped (I-7).
    """
    if not root.is_dir():
        return 0, (), ()
    scanned = 0
    offenders: list[str] = []
    documented_only: list[str] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix not in suffixes:
            continue
        scanned += 1
        text = path.read_text(encoding="utf-8", errors="ignore")
        if HARNESS_GLOBAL not in text:
            continue
        if HARNESS_GLOBAL in strip_js_comments(text):
            offenders.append(workflow_relative_path(path))
        else:
            documented_only.append(workflow_relative_path(path))
    return scanned, tuple(offenders), tuple(documented_only)


def assert_harness_absent_from_bundle(
    *,
    require_bundle: bool = False,
    source_root: Path = FRONTEND_SRC,
    bundle_root: Path = FRONTEND_DIST,
) -> BundleAssertion:
    """AD-12: ``window.__atlasHarness`` must not reach the shipped console.

    Two independent reads, both pure file reads (I-0: this never builds anything):

    1. **Production source** - no file under ``frontend/src/`` may mention the
       global. The harness lives in ``frontend/spec/effectiveness/`` and is imported
       only by an ``import.meta.env``-guarded e2e-only entry (task 11.1), so a
       mention inside the production entry graph is the failure this catches.
    2. **Shipped bundle** - no emitted ``.js`` / ``.mjs`` / ``.cjs`` / ``.css`` /
       ``.html`` artifact under ``frontend/dist/`` may contain the global.

    When ``frontend/dist/`` holds no build the second read reports ``skip`` with the
    reason, which is non-passing but not a failure: locally there is nothing to
    inspect. In CI the assertion runs *after* ``pnpm build`` in the same job and is
    invoked with ``--require-bundle``, which turns a missing bundle into
    unavailable - absence of proof is never a pass (I-7).
    """
    src_scanned, src_offenders, src_documented = _scan_for_harness(
        source_root, _PRODUCTION_SOURCE_SUFFIXES
    )
    dist_scanned, dist_offenders, dist_documented = _scan_for_harness(bundle_root, _BUNDLE_SUFFIXES)
    offenders = src_offenders + dist_offenders
    documented_only = src_documented + dist_documented
    scanned = src_scanned + dist_scanned
    # A mention that survives comment-stripping is the violation; one that does not is
    # prose about AD-12 and is carried into the detail rather than dropped (I-7).
    documented_note = (
        f"; {len(documented_only)} file(s) mention it in comments only "
        f"({', '.join(documented_only)})"
        if documented_only
        else ""
    )

    if offenders:
        return BundleAssertion(
            status="fail",
            files_scanned=scanned,
            offending_files=offenders,
            detail=(
                f"`window.{HARNESS_GLOBAL}` reaches the production surface in "
                f"{len(offenders)} file(s) (AD-12)"
            ),
        )
    if dist_scanned == 0:
        return BundleAssertion(
            status="skip",
            files_scanned=scanned,
            offending_files=(),
            detail=(
                f"no built bundle under {workflow_relative_path(bundle_root)}; "
                f"{src_scanned} production source file(s) are clean. Run with "
                "--require-bundle in the job that builds the bundle"
                + (" (required: reported unavailable)" if require_bundle else "")
                + documented_note
            ),
        )
    return BundleAssertion(
        status="pass",
        files_scanned=scanned,
        offending_files=(),
        detail=(
            f"`window.{HARNESS_GLOBAL}` absent from {src_scanned} production source "
            f"file(s) and {dist_scanned} shipped bundle artifact(s)" + documented_note
        ),
    )


# ---------------------------------------------------------------------------
# Verdict
# ---------------------------------------------------------------------------


def job_display_names(directory: Path = WORKFLOW_DIR) -> dict[tuple[str, str], str]:
    """``(workflow, job_id) -> job display name`` for every job in the tree."""
    names: dict[tuple[str, str], str] = {}
    for path in iter_workflow_paths(directory):
        workflow = workflow_relative_path(path)
        for job_id, job in iter_jobs(load_workflow(path)):
            label = job.get("name")
            names[(workflow, job_id)] = (
                label.strip() if isinstance(label, str) and label.strip() else job_id
            )
    return names


def _readability_notes(shapes: tuple[StepShape, ...]) -> tuple[ShapeNote, ...]:
    """R4.12's disclosures, in tree order: propagating steps that read as if they do not.

    Independent of every rule and of the declared-blocking set. A note is attached to a
    step that propagates, so the step owes no declaration and no label - the whole point
    of the requirement is that labelling it would be the false statement (I-7).
    """
    return tuple(
        ShapeNote(
            note=READABILITY_NOTE,
            requirement="R4.12",
            workflow=shape.workflow,
            job=shape.job,
            step_name=shape.step_name,
            detail=(
                "step propagates its exit status - its final command decides it - but a "
                "continuation-joined command masks "
                f"{', '.join(shape.masked_nonterminal_constructs)} mid-list, so the "
                "shape is unreadable as written. Make it readable (split the chain, or "
                "move the best-effort commands to their own step); do NOT label it "
                "advisory, which would be a false label"
            ),
        )
        for shape in shapes
        if shape.propagates_exit_status and shape.masked_nonterminal_constructs
    )


def _requirement_index(
    declarations: tuple[BlockingDeclaration, ...],
) -> dict[tuple[str, str], str]:
    return {
        (declaration.workflow, declaration.job): declaration.requirement or "R1.8"
        for declaration in declarations
    }


def evaluate(
    *,
    directory: Path = WORKFLOW_DIR,
    declaration_path: Path = BLOCKING_STEPS_FILE,
    require_bundle: bool = False,
    makefile: Path | None = MAKEFILE,
    frontend_src: Path = FRONTEND_SRC,
    frontend_dist: Path = FRONTEND_DIST,
) -> ShapeReport:
    """Classify the whole workflow tree and apply the four rules.

    Rule order is fixed so a step that violates more than one rule is reported once,
    under the strongest: ``blocking-discards`` > ``chain-verifier-discards`` >
    ``unlabelled-advisory``. ``blocking-unresolved`` is independent of any step.

    Every path this reads is a parameter, defaulted to this repository's. The three
    non-workflow roots are parameters and not module constants because a caller that
    points ``directory`` at some other workflow tree must get a verdict about *that*
    tree: leaking this repository's ``Makefile`` or ``frontend/`` state into it would
    make the verdict unattributable, and would make Property 4 unassertable over
    generated workflows.
    """
    bundle = assert_harness_absent_from_bundle(
        require_bundle=require_bundle,
        source_root=frontend_src,
        bundle_root=frontend_dist,
    )
    shapes = collect_step_shapes(directory)

    if not shapes:
        return ShapeReport(
            shapes=(),
            declarations=(),
            findings=(),
            bundle=bundle,
            verdict="unavailable",
            reason=(f"no workflow steps could be read from {workflow_relative_path(directory)}"),
        )

    notes = _readability_notes(shapes)

    try:
        declarations = load_blocking_declarations(declaration_path)
    except DeclarationLoadError as error:
        return ShapeReport(
            shapes=shapes,
            declarations=(),
            findings=(),
            bundle=bundle,
            verdict="unavailable",
            reason=f"declared-blocking set unreadable: {error}",
            notes=notes,
        )

    declared, unresolved = _declared_keys(declarations, shapes)
    requirements = _requirement_index(declarations)
    job_names = job_display_names(directory)

    findings: list[ShapeFinding] = list(unresolved)
    claimed: set[tuple[str, str, str]] = set()

    for shape in shapes:
        key = (shape.workflow, shape.job, shape.step_name)
        if shape.propagates_exit_status or key not in declared:
            continue
        findings.append(
            ShapeFinding(
                rule="blocking-discards",
                requirement=requirements.get((shape.workflow, shape.job), "R1.8"),
                workflow=shape.workflow,
                job=shape.job,
                step_name=shape.step_name,
                detail=(
                    "step is declared blocking but discards its exit status via "
                    f"`{shape.discarding_construct}`"
                ),
            )
        )
        claimed.add(key)

    for finding in _chain_verifier_workflow_findings(directory):
        key = (finding.workflow, finding.job, finding.step_name)
        if key in claimed:
            continue
        findings.append(finding)
        claimed.add(key)
    findings.extend(_chain_verifier_makefile_findings(makefile))

    # R11.3: a non-propagating step outside the declared set must say so in its
    # name. A job-level `continue-on-error` is excused by a marker on the job's
    # display name as well, because the job - not the individual step - is what
    # carries the construct (ci.yml's `v4-compliance (informational)` job).
    reported_jobs: set[tuple[str, str]] = set()
    for shape in shapes:
        key = (shape.workflow, shape.job, shape.step_name)
        if shape.propagates_exit_status or key in declared or key in claimed:
            continue
        construct = shape.discarding_construct or ""
        job_scoped = construct.endswith("(job)")
        job_key = (shape.workflow, shape.job)
        if shape.advisory_in_name:
            continue
        if job_scoped:
            if _advisory_in(job_names.get(job_key, shape.job)) or job_key in reported_jobs:
                continue
            reported_jobs.add(job_key)
        findings.append(
            ShapeFinding(
                rule="unlabelled-advisory",
                requirement="R11.3",
                workflow=shape.workflow,
                job=shape.job,
                step_name="(all steps)" if job_scoped else shape.step_name,
                detail=(
                    f"step does not propagate its exit status (`{construct}`) and its "
                    f"name carries neither {ADVISORY_MARKERS[0]} nor {ADVISORY_MARKERS[1]}"
                ),
            )
        )

    ordered = tuple(
        sorted(
            findings,
            key=lambda item: (
                _RULES.index(item.rule) if item.rule in _RULES else len(_RULES),
                item.workflow,
                item.job,
                item.step_name,
            ),
        )
    )

    if ordered or bundle.status == "fail":
        counts = {rule: sum(1 for item in ordered if item.rule == rule) for rule in _RULES}
        reason = ", ".join(f"{rule}={counts[rule]}" for rule in _RULES if counts[rule])
        if bundle.status == "fail":
            reason = f"{reason}, bundle-assertion=fail" if reason else "bundle-assertion=fail"
        return ShapeReport(
            shapes=shapes,
            declarations=declarations,
            findings=ordered,
            bundle=bundle,
            verdict="fail",
            reason=reason,
            notes=notes,
        )

    if require_bundle and bundle.status != "pass":
        return ShapeReport(
            shapes=shapes,
            declarations=declarations,
            findings=(),
            bundle=bundle,
            verdict="unavailable",
            reason=f"bundle assertion could not be made: {bundle.detail}",
            notes=notes,
        )

    # The readability count rides on the PASS reason and on no other verdict's, so a
    # failing row still reads `rule=count` and nothing else (that string is the only
    # output `gate_fault_injection` sees for C64). It is appended rather than inserted,
    # and only when there is something to say, so a tree with no notes reports the same
    # sentence it always did.
    readability = f"; {len(notes)} step(s) reported for readability (R4.12)" if notes else ""
    return ShapeReport(
        shapes=shapes,
        declarations=declarations,
        findings=(),
        bundle=bundle,
        verdict="pass",
        reason=(
            f"{len(shapes)} steps classified; every declared-blocking step propagates "
            f"and every non-propagating step is labelled{readability}"
        ),
        notes=notes,
    )


_EXIT_CODES: Final[dict[str, int]] = {"pass": 0, "fail": 1, "unavailable": 2}


def run(*, as_json: bool = False, require_bundle: bool = False) -> int:
    """CLI entry point. ``print`` is acceptable here and nowhere else in this module."""
    report = evaluate(require_bundle=require_bundle)

    if as_json:
        print(json.dumps(report.model_dump(mode="json"), sort_keys=True, indent=2))
        return _EXIT_CODES[report.verdict]

    non_propagating = sum(1 for shape in report.shapes if not shape.propagates_exit_status)
    print("Workflow shape truth (E1.5 - R1.8, R6.13, R8.9, R11.3)")
    print(
        f"  steps classified : {len(report.shapes)} "
        f"({non_propagating} non-propagating) in "
        f"{len(iter_workflow_paths())} workflow file(s)"
    )
    print(f"  declarations     : {len(report.declarations)} blocking entries")
    bundle_symbol = {"pass": "[OK]", "fail": "[XX]", "skip": "[--]"}[report.bundle.status]
    print(f"  bundle assertion : {bundle_symbol} {report.bundle.detail}")
    for offender in report.bundle.offending_files:
        print(f"      - {offender}")
    print()

    if report.findings:
        for rule in _RULES:
            rule_findings = [item for item in report.findings if item.rule == rule]
            if not rule_findings:
                continue
            print(f"{rule} ({len(rule_findings)}):")
            for item in rule_findings:
                print(f"  [XX] {item.workflow} :: {item.job} :: {item.step_name}")
                print(f"       {item.requirement} - {item.detail}")
            print()
    else:
        print("No exit-status propagation violations found.")
        print()

    # Printed with `[--]`, not `[XX]`, and under a heading that says so: a note is a
    # disclosure about readability and never a violation (R4.12).
    if report.notes:
        print(f"{READABILITY_NOTE} ({len(report.notes)}) - reported, not failed:")
        for note in report.notes:
            print(f"  [--] {note.workflow} :: {note.job} :: {note.step_name}")
            print(f"       {note.requirement} - {note.detail}")
        print()

    symbol = {"pass": "[OK]", "fail": "[XX]", "unavailable": "[--]"}[report.verdict]
    print(f"{symbol} verdict={report.verdict} reason={report.reason}")
    return _EXIT_CODES[report.verdict]


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    unknown = [
        arg for arg in args if arg not in {"--json", "--check", "--require-bundle", "--help", "-h"}
    ]
    if unknown or "--help" in args or "-h" in args:
        print(__doc__ or "")
        return 0 if not unknown else 2
    return run(as_json="--json" in args, require_bundle="--require-bundle" in args)


if __name__ == "__main__":
    sys.exit(main())
