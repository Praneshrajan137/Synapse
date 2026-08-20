"""Named-command resolution truth for audit-verification steps (design E4.4).

Feature: purpose-achievement-audit, task 7.4. Requirement R6.14.

What this gate answers, mechanically: *when a workflow step or a Makefile recipe
names a command, does that command exist?* The audit found the condition that makes
the question worth asking: ``Makefile:592`` and ``.github/workflows/cd-gcp.yml:542``
have both invoked ``python -m orchestrator.audit.cli verify`` for two sprints while
``orchestrator/audit/cli.py`` did not exist -- and both call sites also swallowed the
exit status, so neither the absence nor the non-zero could ever surface. A named
command that does not resolve is a gate that never ran; a resolved command whose exit
status is discarded is a gate that cannot fail.

Resolution is **static** and never executes anything. A module resolves because a
file exists in the tree; a console script resolves because an entry point is declared
in a ``pyproject.toml``. This module runs no subprocess, imports no scanned module,
and invokes none of the commands it resolves (I-0: the laptop runs nothing).

Scope: an **audit-verification step**
--------------------------------------

R6.14 is scoped to "an audit-verification step of a workflow or of the Makefile", not
to every command in the tree. A step is an audit-verification step when its command
text names one of :data:`AUDIT_VERIFICATION_PATTERNS`:

* the audit-chain verifier, via ``CHAIN_VERIFIER_PATTERNS`` imported unchanged from
  :mod:`scripts.audit.workflow_shape_truth` (``orchestrator.audit.cli verify``,
  ``synapse_cli.audit_verify``, ``synapse audit verify``, ...), and
* the audit gate family, ``scripts.audit.*`` / ``scripts/audit/*``.

Within such a step, **every** command it names is resolved -- not only the audit
subject. A step that runs the uplift harness and then the uplift gate has both of its
module paths resolved, because the step as a whole is the audit-verification step and
either half failing to resolve makes the verification a no-op.

Widening the subject set is a one-line edit to
:data:`AUDIT_VERIFICATION_PATTERNS`. It is deliberately not widened to every step in
the tree: ``mutation.yml`` alone names ``python -m pytest`` in eight places, and
sweeping those would trade a precise obligation for noise.

Two naming surfaces deliberately excluded
-----------------------------------------

**npm / pnpm script targets are out of scope.** ``frontend/package.json`` carries
``"spec:check": "tsx scripts/check-fe-invariants.ts"``, and
``frontend/scripts/check-fe-invariants.ts`` does not exist -- the frontend invariant
gate is the Python ``frontend/spec/check_fe_invariants.py``, which
``frontend.yml::fe-invariants`` runs. The stale npm target is real rot, and it is
still not this gate's business, for two independent reasons:

1. R6.14 names exactly two resolvable kinds, "module path" and "console-script
   name". A ``package.json`` ``scripts`` entry is neither: it is a third naming
   surface with its own resolution rules (``tsx``/node module resolution, workspace
   ``bin`` shims, ``pnpm exec`` path search).
2. No workflow step and no Makefile recipe invokes ``spec:check``, so no
   audit-verification step *names* it. Under R6.14's own scoping it is not reachable
   from this gate's input at all -- reporting it here would mean widening the
   requirement rather than enforcing it.

Where it belongs: a frontend script-target check alongside
``frontend/spec/check_fe_invariants.py``, or a widened "every named target resolves"
gate. Recorded here so the finding is not lost by being out of scope.

**Third-party tool names are out of scope.** ``pytest``, ``mutmut``, ``docker``,
``ssh``, ``cosign`` and friends are console-script names, but they are not *this
repository's* console scripts: resolving them would require inspecting an installed
environment, which is neither static nor reproducible. The in-scope console-script
set is exactly the names this repository owns -- the declared
``[project.scripts]`` / ``[project.entry-points."console_scripts"]`` entries, plus
each ``[project] name``. Today that set is ``{synapse, synapse-common}`` and the
entry-point tables are **empty**, which is why ``synapse audit verify``
(ADR-033 names it as a component) would not resolve if a step invoked it.

Overlap with ``workflow_shape_truth``
-------------------------------------

R6.13 (that module's ``chain-verifier-discards`` rule) already reports a discarded
exit status on steps that name the *chain verifier*. R6.14 extends the obligation to
every audit-verification step, so the two overlap on the chain-verifier call sites by
design. The discard classification itself is **not** reimplemented here: the four
constructs, the terminal-command reading, and the ``continue-on-error`` reading are
imported from that module so there is one vocabulary and one definition.

Run::

    python -m scripts.audit.command_path_truth            # human report
    python -m scripts.audit.command_path_truth --json     # machine JSON

Exit codes: ``0`` pass, ``1`` fail, ``2`` unavailable. ``2`` is non-passing (I-7:
absence of proof is never a pass). Every read uses ``encoding='utf-8'``
(E-S13-07) and all console output is ASCII.
"""

from __future__ import annotations

import json
import re
import sys
import tomllib
from pathlib import Path
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict

from scripts.audit.workflow_shape_truth import (
    CHAIN_VERIFIER_PATTERNS,
    DISCARDING_CONSTRUCTS,
    MAKEFILE,
    ROOT,
    WORKFLOW_DIR,
    classify_step,
    effective_command_lines,
    iter_job_steps,
    iter_jobs,
    iter_workflow_paths,
    load_workflow,
    step_run_script,
    terminal_discarding_construct,
    workflow_relative_path,
    workflow_triggers,
)

#: The manifests whose entry-point tables define this repository's console scripts.
PYPROJECT_FILES: Final[tuple[Path, ...]] = (
    ROOT / "pyproject.toml",
    ROOT / "packages" / "pyproject.toml",
)

#: Command fragments naming the audit gate family (the chain verifier's fragments
#: come from ``CHAIN_VERIFIER_PATTERNS``, imported rather than restated).
AUDIT_GATE_PATTERNS: Final[tuple[str, ...]] = ("scripts.audit.", "scripts/audit/")

#: A step is an audit-verification step when its command text names one of these.
AUDIT_VERIFICATION_PATTERNS: Final[tuple[str, ...]] = (
    CHAIN_VERIFIER_PATTERNS + AUDIT_GATE_PATTERNS
)

#: Top-level module names that belong to an installed distribution rather than the
#: tree. A ``python -m`` root outside both this set and the tree is reported as an
#: unknown root (a FAIL) rather than assumed installed: assuming would let
#: ``python -m pytets`` pass. Adding a genuinely external root here is the fix, and
#: making that edit explicit is the point.
EXTERNAL_MODULE_ROOTS: Final[frozenset[str]] = frozenset(
    {
        "build",
        "coverage",
        "ensurepip",
        "feast",
        "http",
        "hypothesis",
        "json",
        "locust",
        "mutmut",
        "mypy",
        "pip",
        "pipdeptree",
        "piplicenses",
        "pytest",
        "ruff",
        "schemathesis",
        "site",
        "uvicorn",
        "venv",
    }
)

CommandKind = Literal["module", "console_script", "script_path"]

#: Every resolution outcome. The three ``pass`` outcomes are first; the rest FAIL.
Resolution = Literal[
    "module_file",
    "package_main",
    "script_file",
    "entry_point",
    "package_without_main",
    "entry_point_target_missing",
    "unresolved",
    "unknown_root",
    "external",
]

_PASSING_RESOLUTIONS: Final[frozenset[str]] = frozenset(
    {"module_file", "package_main", "script_file", "entry_point", "external"}
)

_MODULE_RE: Final[re.Pattern[str]] = re.compile(
    r"(?<![\w./-])(?:python|python3|python3\.\d+|py)\s+(?:-[^\s]+\s+)*-m\s+"
    r"(?P<module>[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*)"
)
_SCRIPT_RE: Final[re.Pattern[str]] = re.compile(
    r"(?<![\w./-])(?:python|python3|python3\.\d+|py)\s+(?:-[^\s]+\s+)*"
    r"(?P<path>[A-Za-z0-9_][\w./-]*\.py)"
)
#: ``echo`` / ``printf`` arguments up to the next command separator. Stripped before
#: extraction so the ``|| echo "synapse audit verify not available yet"`` at
#: ``Makefile:592`` is read as the message it is and not as an invocation.
_ECHO_RE: Final[re.Pattern[str]] = re.compile(r"(?<![\w./-])(?:echo|printf)\b[^\n;&|]*")

#: What may precede a console-script name for it to be a command *head*: a line
#: start or a command separator. A plain space does not qualify, deliberately -
#: ``psql -h localhost -U synapse -d synapse_audit`` names a database role, not a
#: command, and reading an argument as an invocation would fabricate a finding (I-7).
_HEAD_PREFIX: Final[str] = r"(?:^|(?<=[\n;&|(`'\"]))\s*"

_RULES: Final[tuple[str, ...]] = ("unresolvable-command", "discarded-exit-status")

_EXIT_CODES: Final[dict[str, int]] = {"pass": 0, "fail": 1, "unavailable": 2}

__all__ = [
    "AUDIT_GATE_PATTERNS",
    "AUDIT_VERIFICATION_PATTERNS",
    "EXTERNAL_MODULE_ROOTS",
    "PYPROJECT_FILES",
    "CommandFinding",
    "CommandPathReport",
    "NamedCommand",
    "collect_named_commands",
    "evaluate",
    "is_audit_verification_command",
    "load_entry_points",
    "load_owned_script_names",
    "main",
    "named_commands_in",
    "resolve_console_script",
    "resolve_module",
    "resolve_script_path",
    "run",
    "strip_echoed_text",
]


# ---------------------------------------------------------------------------
# Command-text reading
# ---------------------------------------------------------------------------


def strip_echoed_text(text: str) -> str:
    """Remove ``echo`` / ``printf`` arguments from command text.

    An echoed command name is a message, not an invocation. Stripping happens
    before both subject classification and extraction, so a step that only *mentions*
    an audit module in a log line is not treated as an audit-verification step.
    """
    return _ECHO_RE.sub(" ", text)


def is_audit_verification_command(text: str) -> bool:
    """Whether command text names an audit-verification subject (R6.14 scope)."""
    stripped = strip_echoed_text(text)
    return any(pattern in stripped for pattern in AUDIT_VERIFICATION_PATTERNS)


class NamedCommand(BaseModel):
    """One command named by one audit-verification step, and how it resolved."""

    model_config = ConfigDict(frozen=True)

    kind: CommandKind
    name: str
    source: str
    scope: str
    step_name: str
    resolution: Resolution
    resolved_to: str | None
    detail: str

    @property
    def resolves(self) -> bool:
        """Whether this naming resolved to something that can actually run."""
        return self.resolution in _PASSING_RESOLUTIONS


def named_commands_in(text: str, *, owned_script_names: frozenset[str]) -> tuple[
    tuple[CommandKind, str], ...
]:
    """Every ``(kind, name)`` an audit-verification step's command text names.

    Extraction is a scan over the whole text rather than a parse of the command
    pipeline, because the two committed call sites nest the invocation inside a
    payload: ``ssh ... 'cd ~/synapse && python -m orchestrator.audit.cli verify'``
    and ``docker compose ... exec -T orchestrator python -m orchestrator.audit.cli
    verify``. A pipeline parse would stop at ``ssh`` and ``docker`` and miss the
    module -- which is precisely the module R6.14 exists to catch.

    Order is module paths, then script paths, then console scripts; duplicates are
    collapsed so a name repeated in one step is reported once.
    """
    stripped = strip_echoed_text(text)
    found: list[tuple[CommandKind, str]] = []

    for match in _MODULE_RE.finditer(stripped):
        found.append(("module", match.group("module")))
    for match in _SCRIPT_RE.finditer(stripped):
        found.append(("script_path", match.group("path")))
    for name in sorted(owned_script_names):
        head = re.compile(rf"(?:^|[\s;&|(\"']){re.escape(name)}(?=\s|$)")
        if head.search(stripped):
            found.append(("console_script", name))

    return tuple(dict.fromkeys(found))


# ---------------------------------------------------------------------------
# Static resolution
# ---------------------------------------------------------------------------


def _relative(path: Path, *, tree_root: Path) -> str:
    try:
        return path.resolve().relative_to(tree_root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def resolve_module(
    module: str,
    *,
    tree_root: Path = ROOT,
    external_roots: frozenset[str] = EXTERNAL_MODULE_ROOTS,
) -> tuple[Resolution, str | None, str]:
    """Resolve a ``python -m`` dotted path against the tree.

    ``python -m a.b.c`` runs ``a/b/c.py``, or ``a/b/c/__main__.py`` when the leaf is
    a package. A leaf package with **no** ``__main__.py`` is reported
    ``package_without_main`` and FAILs: ``python -m`` on it exits non-zero with
    "No module named ...__main__", so the path does not resolve to anything runnable
    even though the directory exists.

    Intermediate ``__init__.py`` files are not required (PEP 420 namespace packages
    are resolvable on 3.11, and ``scripts/`` is imported that way in CI).
    """
    segments = module.split(".")
    root = segments[0]
    if root in external_roots:
        return (
            "external",
            None,
            f"'{root}' is a declared external distribution root; not resolvable "
            "from the tree",
        )

    base = tree_root.joinpath(*segments)
    module_file = base.with_suffix(".py")
    if module_file.is_file():
        target = _relative(module_file, tree_root=tree_root)
        return "module_file", target, f"resolves to {target}"
    if base.is_dir():
        dunder_main = base / "__main__.py"
        if dunder_main.is_file():
            target = _relative(dunder_main, tree_root=tree_root)
            return "package_main", target, f"resolves to {target}"
        return (
            "package_without_main",
            None,
            f"'{module}' is a package directory "
            f"({_relative(base, tree_root=tree_root)}) with no __main__.py, so "
            "`python -m` cannot run it",
        )

    root_dir = tree_root / root
    if root_dir.is_dir() or (tree_root / f"{root}.py").is_file():
        return (
            "unresolved",
            None,
            f"'{module}' names no module in the tree: expected "
            f"{_relative(module_file, tree_root=tree_root)} or "
            f"{_relative(base / '__main__.py', tree_root=tree_root)}",
        )
    return (
        "unknown_root",
        None,
        f"'{module}' has root '{root}', which is neither a top-level module of the "
        "tree nor a declared external distribution root (add it to "
        "EXTERNAL_MODULE_ROOTS if it is third-party)",
    )


def resolve_script_path(
    path_text: str, *, tree_root: Path = ROOT
) -> tuple[Resolution, str | None, str]:
    """Resolve a ``python <path>.py`` invocation against the tree."""
    candidate = tree_root / path_text
    if candidate.is_file():
        target = _relative(candidate, tree_root=tree_root)
        return "script_file", target, f"resolves to {target}"
    return "unresolved", None, f"'{path_text}' names no file in the tree"


def load_entry_points(paths: tuple[Path, ...] = PYPROJECT_FILES) -> dict[str, str]:
    """``console-script name -> "module:attr"`` across the given manifests.

    Both ``[project.scripts]`` and ``[project.entry-points."console_scripts"]`` are
    read; a manifest that is absent or unparseable contributes nothing.
    """
    entry_points: dict[str, str] = {}
    for path in paths:
        if not path.is_file():
            continue
        try:
            document = tomllib.loads(path.read_text(encoding="utf-8"))
        except tomllib.TOMLDecodeError:
            continue
        project = document.get("project")
        if not isinstance(project, dict):
            continue
        tables: list[object] = [project.get("scripts")]
        nested = project.get("entry-points")
        if isinstance(nested, dict):
            tables.append(nested.get("console_scripts"))
        for table in tables:
            if not isinstance(table, dict):
                continue
            for name, target in table.items():
                entry_points[str(name)] = str(target)
    return entry_points


def load_owned_script_names(paths: tuple[Path, ...] = PYPROJECT_FILES) -> frozenset[str]:
    """The console-script names this repository owns.

    Declared entry points plus each ``[project] name``. A distribution name is
    included because it is the name a governance document uses when it says the
    command exists (ADR-033's ``synapse audit verify``); if a step invokes it and no
    entry point declares it, that is exactly the unresolvable naming R6.14 wants
    named.
    """
    names: set[str] = set(load_entry_points(paths))
    for path in paths:
        if not path.is_file():
            continue
        try:
            document = tomllib.loads(path.read_text(encoding="utf-8"))
        except tomllib.TOMLDecodeError:
            continue
        project = document.get("project")
        if isinstance(project, dict):
            name = project.get("name")
            if isinstance(name, str) and name.strip():
                names.add(name.strip())
    return frozenset(names)


def resolve_console_script(
    name: str,
    *,
    entry_points: dict[str, str],
    tree_root: Path = ROOT,
    external_roots: frozenset[str] = EXTERNAL_MODULE_ROOTS,
) -> tuple[Resolution, str | None, str]:
    """Resolve a console-script name against the declared entry points.

    A declared entry point is resolved one step further: its ``module:attr`` target
    module must exist in the tree, otherwise the declaration is a name pointing at
    nothing and ``entry_point_target_missing`` FAILs naming both sides.
    """
    target = entry_points.get(name)
    if target is None:
        return (
            "unresolved",
            None,
            f"'{name}' is declared by no [project.scripts] or "
            "[project.entry-points.\"console_scripts\"] table in "
            + ", ".join(_relative(path, tree_root=tree_root) for path in PYPROJECT_FILES),
        )
    module = target.split(":", 1)[0].strip()
    resolution, resolved_to, detail = resolve_module(
        module, tree_root=tree_root, external_roots=external_roots
    )
    if resolution in _PASSING_RESOLUTIONS:
        return "entry_point", f"{target} -> {resolved_to or module}", f"resolves via {target}"
    return (
        "entry_point_target_missing",
        None,
        f"'{name}' is declared as '{target}' but that target does not resolve: {detail}",
    )


def _resolve(
    kind: CommandKind,
    name: str,
    *,
    entry_points: dict[str, str],
    tree_root: Path,
    external_roots: frozenset[str],
) -> tuple[Resolution, str | None, str]:
    if kind == "module":
        return resolve_module(name, tree_root=tree_root, external_roots=external_roots)
    if kind == "script_path":
        return resolve_script_path(name, tree_root=tree_root)
    return resolve_console_script(
        name, entry_points=entry_points, tree_root=tree_root, external_roots=external_roots
    )


# ---------------------------------------------------------------------------
# Collection over the two naming surfaces
# ---------------------------------------------------------------------------


class CommandFinding(BaseModel):
    """One violation, naming the file, the step, and the subject (R6.14's naming)."""

    model_config = ConfigDict(frozen=True)

    rule: str
    requirement: str
    source: str
    scope: str
    step_name: str
    subject: str
    detail: str


def _makefile_recipe_lines(text: str) -> tuple[tuple[str, str], ...]:
    """``(target, recipe line)`` for every recipe line, continuations joined.

    The Makefile sets ``SHELL := /bin/bash`` and declares no ``.ONESHELL``, so each
    recipe line is its own shell invocation and therefore its own exit status. That
    is why classification is per line rather than per target.
    """
    lines: list[tuple[str, str]] = []
    target = "(no target)"
    buffer = ""
    for raw in text.splitlines():
        if not buffer and raw and not raw.startswith(("\t", " ", "#")) and ":" in raw:
            head = raw.split(":", 1)[0].strip()
            if head and not head.startswith("."):
                target = head
            continue
        if not buffer and not raw.startswith("\t"):
            continue
        piece = raw.lstrip("\t").rstrip()
        buffer = piece if not buffer else f"{buffer} {piece.lstrip()}"
        if buffer.endswith("\\"):
            buffer = buffer[:-1].rstrip()
            continue
        if buffer:
            lines.append((target, buffer))
        buffer = ""
    if buffer:
        lines.append((target, buffer))
    return tuple(lines)


def _makefile_discarding_construct(line: str) -> str | None:
    """The construct discarding a Make recipe line's exit status, or ``None``.

    Make's leading ``-`` (ignore errors) is Make-specific; the shell constructs are
    read with :func:`terminal_discarding_construct`, the same reading
    ``workflow_shape_truth`` applies to a ``run:`` script.
    """
    body = line.lstrip()
    if body.startswith("-") or body.startswith("@-"):
        return "leading `-` (Make ignores errors)"
    return terminal_discarding_construct(body.lstrip("@").strip())


def collect_named_commands(
    *,
    directory: Path = WORKFLOW_DIR,
    makefile: Path | None = MAKEFILE,
    tree_root: Path = ROOT,
    pyproject_paths: tuple[Path, ...] = PYPROJECT_FILES,
    external_roots: frozenset[str] = EXTERNAL_MODULE_ROOTS,
) -> tuple[tuple[NamedCommand, ...], tuple[CommandFinding, ...]]:
    """Every command named by an audit-verification step, plus discard findings."""
    entry_points = load_entry_points(pyproject_paths)
    owned = load_owned_script_names(pyproject_paths)

    commands: list[NamedCommand] = []
    discards: list[CommandFinding] = []

    def record(
        *, source: str, scope: str, step_name: str, text: str, construct: str | None
    ) -> None:
        if not is_audit_verification_command(text):
            return
        for kind, name in named_commands_in(text, owned_script_names=owned):
            resolution, resolved_to, detail = _resolve(
                kind,
                name,
                entry_points=entry_points,
                tree_root=tree_root,
                external_roots=external_roots,
            )
            commands.append(
                NamedCommand(
                    kind=kind,
                    name=name,
                    source=source,
                    scope=scope,
                    step_name=step_name,
                    resolution=resolution,
                    resolved_to=resolved_to,
                    detail=detail,
                )
            )
        if construct is not None:
            discards.append(
                CommandFinding(
                    rule="discarded-exit-status",
                    requirement="R6.14",
                    source=source,
                    scope=scope,
                    step_name=step_name,
                    subject="(step)",
                    detail=(
                        "audit-verification step discards its exit status via "
                        f"`{construct}`, so the verification it names cannot fail "
                        "the run"
                    ),
                )
            )

    for path in iter_workflow_paths(directory):
        document = load_workflow(path)
        triggers = workflow_triggers(document)
        workflow = workflow_relative_path(path)
        for job_id, job in iter_jobs(document):
            for index, step in enumerate(iter_job_steps(job)):
                script = step_run_script(step)
                if not script:
                    continue
                shape = classify_step(
                    workflow=workflow,
                    job_id=job_id,
                    job=job,
                    step=step,
                    index=index,
                    triggers=triggers,
                )
                record(
                    source=workflow,
                    scope=job_id,
                    step_name=shape.step_name,
                    text="\n".join(effective_command_lines(script)),
                    construct=shape.discarding_construct,
                )

    if makefile is not None and makefile.is_file():
        source = workflow_relative_path(makefile)
        for target, line in _makefile_recipe_lines(
            makefile.read_text(encoding="utf-8")
        ):
            record(
                source=source,
                scope=target,
                step_name=line[:80],
                text=line,
                construct=_makefile_discarding_construct(line),
            )

    return tuple(commands), tuple(discards)


# ---------------------------------------------------------------------------
# Verdict
# ---------------------------------------------------------------------------


class CommandPathReport(BaseModel):
    """Everything one execution of this gate observed."""

    model_config = ConfigDict(frozen=True)

    commands: tuple[NamedCommand, ...]
    findings: tuple[CommandFinding, ...]
    verdict: Literal["pass", "fail", "unavailable"]
    reason: str


def evaluate(
    *,
    directory: Path = WORKFLOW_DIR,
    makefile: Path | None = MAKEFILE,
    tree_root: Path = ROOT,
    pyproject_paths: tuple[Path, ...] = PYPROJECT_FILES,
    external_roots: frozenset[str] = EXTERNAL_MODULE_ROOTS,
) -> CommandPathReport:
    """Resolve every named command and apply the two rules.

    Every root this reads is a parameter, defaulted to this repository's, following
    ``workflow_shape_truth.evaluate``: a caller that points ``directory`` at another
    workflow tree must get a verdict about *that* tree, and resolving its module
    paths against this repository's files would make the verdict unattributable --
    and would make Property 20 unassertable over generated workflows.

    An input naming **no** audit-verification step yields ``unavailable``, not
    ``pass``. A resolution gate that found nothing to resolve has proved nothing, and
    absence of proof is never a pass (I-7).
    """
    commands, discards = collect_named_commands(
        directory=directory,
        makefile=makefile,
        tree_root=tree_root,
        pyproject_paths=pyproject_paths,
        external_roots=external_roots,
    )

    if not commands and not discards:
        return CommandPathReport(
            commands=(),
            findings=(),
            verdict="unavailable",
            reason=(
                "no audit-verification step was found in "
                f"{workflow_relative_path(directory)}"
                + (f" or {workflow_relative_path(makefile)}" if makefile is not None else "")
            ),
        )

    findings: list[CommandFinding] = [
        CommandFinding(
            rule="unresolvable-command",
            requirement="R6.14",
            source=command.source,
            scope=command.scope,
            step_name=command.step_name,
            subject=command.name,
            detail=f"{command.kind} does not resolve ({command.resolution}): {command.detail}",
        )
        for command in commands
        if not command.resolves
    ]
    findings.extend(discards)

    ordered = tuple(
        sorted(
            findings,
            key=lambda item: (
                _RULES.index(item.rule) if item.rule in _RULES else len(_RULES),
                item.source,
                item.scope,
                item.step_name,
                item.subject,
            ),
        )
    )

    if ordered:
        counts = {rule: sum(1 for item in ordered if item.rule == rule) for rule in _RULES}
        return CommandPathReport(
            commands=commands,
            findings=ordered,
            verdict="fail",
            reason=", ".join(f"{rule}={counts[rule]}" for rule in _RULES if counts[rule]),
        )

    return CommandPathReport(
        commands=commands,
        findings=(),
        verdict="pass",
        reason=(
            f"{len(commands)} command(s) named by audit-verification steps all resolve "
            "and every such step propagates its exit status"
        ),
    )


def run(*, as_json: bool = False) -> int:
    """CLI entry point. ``print`` is acceptable here and nowhere else in this module."""
    report = evaluate()

    if as_json:
        print(json.dumps(report.model_dump(mode="json"), sort_keys=True, indent=2))
        return _EXIT_CODES[report.verdict]

    kinds = {kind: 0 for kind in ("module", "console_script", "script_path")}
    for command in report.commands:
        kinds[command.kind] += 1
    unresolved = sum(1 for command in report.commands if not command.resolves)

    print("Command-path truth (E4.4 - R6.14)")
    print(
        f"  named commands : {len(report.commands)} "
        f"({kinds['module']} module, {kinds['console_script']} console-script, "
        f"{kinds['script_path']} script-path); {unresolved} unresolved"
    )
    print(f"  subjects       : {len(AUDIT_VERIFICATION_PATTERNS)} audit-verification patterns")
    print(f"  discard set    : {', '.join(DISCARDING_CONSTRUCTS)}")
    print()

    if report.findings:
        for rule in _RULES:
            rule_findings = [item for item in report.findings if item.rule == rule]
            if not rule_findings:
                continue
            print(f"{rule} ({len(rule_findings)}):")
            for item in rule_findings:
                print(f"  [XX] {item.source} :: {item.scope} :: {item.step_name}")
                print(f"       {item.requirement} - {item.subject}: {item.detail}")
            print()
    else:
        print("Every command named by an audit-verification step resolves.")
        print()

    symbol = {"pass": "[OK]", "fail": "[XX]", "unavailable": "[--]"}[report.verdict]
    print(f"{symbol} verdict={report.verdict} reason={report.reason}")
    return _EXIT_CODES[report.verdict]


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    unknown = [arg for arg in args if arg not in {"--json", "--check", "--help", "-h"}]
    if unknown or "--help" in args or "-h" in args:
        print(__doc__ or "")
        return 0 if not unknown else 2
    return run(as_json="--json" in args)


if __name__ == "__main__":
    sys.exit(main())
