"""Every gate declares its own falsification (design AD-4 / E2.1; R1.2, R9.5, R12.3, R12.7).

Feature: purpose-achievement-audit, task 5.1.

The audit's P1 finding is that this repository has 53 mechanical checks and almost no
evidence that any of them *bites*. The tell it names is a test that replaces the thing
it is testing: ``packages/tests/test_agency_truth_gate.py:313-322`` monkeypatches
``agency_truth.evaluate`` to return ``ok=False`` and then asserts C57 reports FAIL.
That proves ``verify_claims`` propagates a verdict. It proves nothing at all about
whether a seven-actuator repository produces that verdict. When the only way to test a
gate is to replace it, the gate is not observing anything.

This module is the generalisation that retires that pattern. For each check listed in
``infrastructure/quality/gate-mutations.yaml`` it:

1. copies the **real tree** to a temporary directory,
2. applies one declared mutation operator inside that copy,
3. runs the gate as a **real subprocess** rooted in the copy, and
4. reports whether the gate exited non-zero **naming the mutated subject**.

Four properties are load-bearing and deliberate:

* **The working tree is never mutated.** :func:`inject` refuses to operate on a tree
  that resolves to :data:`ROOT`, refuses any target that escapes the tree it was
  handed, and every write goes through a path resolved inside that tree.
* **The evaluator is never monkeypatched.** The gate runs in another operating-system
  process, importing the *mutated* tree's own ``verify_claims``. There is no seam in
  which a stub could be substituted, which is precisely the point (R9.5: "THE test
  that demonstrates this SHALL replace no function of the agency evaluator").
* **Naming the subject is half the contract.** A non-zero exit that names nothing does
  not satisfy a declaration. Every string in ``expect_names`` must appear in the
  gate's combined output; the subprocess is told only which check id to run and
  nothing about the mutation, so it cannot echo a name it was fed.
* **Absence of a falsification is never a pass (I-7).** A registered check absent from
  both ``gates`` and ``reporting_tools`` is UNDECLARED and is excluded from the
  PASS-eligible set. So is a declared check whose mutation the gate survived, and so
  is one whose baseline run does not pass on the unmutated copy (a gate that is
  already red proves nothing when it stays red). Exclusion is the honest label; it is
  never an exemption and it never contributes a PASS.

**Expect FAILs today, and read them as honest.** ``gate-mutations.yaml`` records, in
its own notes, three declarations that the current tree does not yet satisfy: C28's
zero-a-floor survives until task 4.1 lands ``--require-measured-floors``, C61's
tolerance widening survives until task 5.5 derives oracle membership, and C60's
``incomplete: true`` is already the committed value so the mutation changes no byte at
all. This harness reports each of those as it finds them rather than tolerating them:
a declaration the gate survives is a gate that does not gate.

**I-0 (local compute).** A sweep copies the tree once and runs one subprocess per
gate plus one per operator. That is a CI workload and it belongs to
``ci.yml::uplift-verify`` (task 12.2). The default invocation therefore probes
nothing: it validates the declaration, reports declared/undeclared coverage, and
exits ``2`` because nothing was falsified. ``--sweep`` is the explicit opt-in.

**The sweep's bound is committed, not defaulted (AD-22; decision-quality-proof task
5.2).** Under ``--sweep`` the per-subprocess bound is read from
``gate-mutations.yaml::sweep_budget.per_subprocess_timeout_s``. It is deliberately not
defaulted to :data:`DEFAULT_TIMEOUT_S`: 900s is ten times the committed value, and 14
baselines plus 16 operators at 900s is 7.5h against a committed 60-minute job, so a
silent fallback would schedule a sweep that cannot finish and would do it invisibly. A
declaration that commits no usable budget makes the sweep report ``unavailable`` naming
the block, having probed nothing. ``--timeout`` still overrides for diagnosis, and the
report records which of the two the run used, because "indeterminate naming the timeout"
does not say whose bound was exceeded unless the bound and its provenance travel with it.
Lowering 900 to 90 is, honestly, a reduction from a bound nobody measured to a bound
nobody measured; the first gating run is the measurement, and a gate that cannot answer
inside it is reported, not absorbed.

**A suppressed baseline proves nothing, so it may not report anything (R1.16).**
``--no-baseline`` stays available for diagnosis, but a report produced under it carries
``baseline_suppressed``, its verdict is ``unavailable`` naming the suppression, and its
falsified set is empty. Without a baseline an already-red gate stays red under mutation
and reads as ``falsified`` - which would turn this harness's own diagnostic mode into a
machine for manufacturing false proof. The per-probe outcomes are still reported, because
that is what the diagnosis is for; what they no longer do is count.

**Four ways a sweep can fail to observe, each named separately (R1.5, R1.11).** A gate
subprocess that could not be started, one that outlived the committed bound, and one a
signal terminated are each ``indeterminate`` naming which of the three happened - and so
is a baseline in any of those states, distinctly from a baseline that merely exited
non-zero, whose status is named instead. A report that cannot be serialised exits
``unavailable`` rather than printing a fragment, and an operating-system failure while
copying the tree is "the sweep could not start" rather than a traceback. None of the four
is a pass.

Run::

    python -m scripts.audit.gate_fault_injection             # declaration only, exits 2
    python -m scripts.audit.gate_fault_injection --json      # canonical machine JSON
    python -m scripts.audit.gate_fault_injection --sweep     # CI ONLY: the real probe
    python -m scripts.audit.gate_fault_injection --sweep --gate C57
    python -m scripts.audit.gate_fault_injection --run-check C57   # internal runner

Exit codes: ``0`` pass, ``1`` fail, ``2`` unavailable. ``2`` is non-passing.
Every file is read with ``encoding='utf-8'`` (E-S13-07) and all console output is
ASCII (non-ASCII check titles are escaped for display and compared unescaped).
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import re
import shutil
import subprocess  # running the gate out-of-process is the whole point of this module
import sys
import tempfile
import textwrap
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from enum import StrEnum
from pathlib import Path
from typing import Final, Literal

import structlog
import yaml
from jsonschema import Draft7Validator  # type: ignore[import-untyped]
from jsonschema.exceptions import SchemaError  # type: ignore[import-untyped]
from pydantic import BaseModel, ConfigDict, Field, ValidationError

ROOT: Final[Path] = Path(__file__).resolve().parents[2]

# Ensure the tree this file lives in is importable when run as a bare script. Inside a
# temporary copy this resolves to the copy, which is what makes the subprocess evaluate
# the *mutated* tree's registry rather than the real one.
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DECLARATION_FILE: Final[Path] = ROOT / "infrastructure" / "quality" / "gate-mutations.yaml"
SCHEMA_FILE: Final[Path] = (
    ROOT / "infrastructure" / "quality" / "schemas" / "gate-mutations.schema.json"
)

EXIT_PASS: Final[int] = 0
EXIT_FAIL: Final[int] = 1
EXIT_UNAVAILABLE: Final[int] = 2

_EXIT_CODES: Final[Mapping[str, int]] = {
    "pass": EXIT_PASS,
    "fail": EXIT_FAIL,
    "unavailable": EXIT_UNAVAILABLE,
}
_SYMBOLS: Final[Mapping[str, str]] = {"pass": "[OK]", "fail": "[XX]", "unavailable": "[--]"}

#: Wall-clock bound on one gate subprocess. A gate that cannot answer inside it is
#: reported ``indeterminate`` - never falsified, and never a pass.
#:
#: This is the bound for the single-probe paths only. Under ``--sweep`` the bound is
#: read from the declaration's ``sweep_budget`` (AD-22): 900s is ten times the committed
#: value, and 30 subprocesses at 900s is 7.5h against a committed 60-minute job, so
#: defaulting here would schedule a sweep that cannot finish.
DEFAULT_TIMEOUT_S: Final[float] = 900.0

#: The declaration key holding the committed sweep cost budget (AD-13, AD-22). Read,
#: never inlined: the bound is a committed number and a gate asserts its arithmetic.
SWEEP_BUDGET_KEY: Final[str] = "sweep_budget"

#: Directory and file names never copied into the temporary tree. None of them is read
#: by a registered check; all of them are large, regenerable, or process-local. ``.git``
#: is excluded deliberately: a fault-injected tree is not a branch and must not be
#: mistakable for one.
COPY_EXCLUDED_NAMES: Final[frozenset[str]] = frozenset(
    {
        ".git",
        ".gl_scratch",
        ".hypothesis",
        ".mypy_cache",
        ".next",
        ".pytest_cache",
        ".ruff_cache",
        ".venv",
        "__pycache__",
        "build",
        "coverage",
        "dist",
        "htmlcov",
        "node_modules",
        "playwright-report",
        "test-results",
        "venv",
        "worktrees",
    }
)

#: Suffixes never copied (process-local build residue).
COPY_EXCLUDED_SUFFIXES: Final[tuple[str, ...]] = (".pyc", ".pyo", ".egg-info")

_LOG = structlog.get_logger(__name__)

JsonScalar = str | bool | int | float | None

__all__ = [
    "COPY_EXCLUDED_NAMES",
    "DECLARATION_FILE",
    "DEFAULT_TIMEOUT_S",
    "EXIT_FAIL",
    "EXIT_PASS",
    "EXIT_UNAVAILABLE",
    "ROOT",
    "SCHEMA_FILE",
    "SWEEP_BUDGET_KEY",
    "Completeness",
    "DeclarationError",
    "FaultInjectionReport",
    "FaultInjectionResult",
    "Finding",
    "GateDeclaration",
    "GateRun",
    "InjectionError",
    "MutationDeclaration",
    "MutationOperator",
    "OperatorKind",
    "PathSyntaxError",
    "ReportingTool",
    "SweepBudget",
    "evaluate",
    "falsifies",
    "inject",
    "load_declaration",
    "load_schema",
    "main",
    "mutated_path",
    "parse_declaration",
    "parse_document_path",
    "read_sweep_budget",
    "registered_ids",
    "restore",
    "run",
    "run_gate",
    "schema_findings",
    "set_at",
    "sweep",
    "tree_copy",
    "unobservable_reason",
]


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class DeclarationError(Exception):
    """The declaration or its schema is absent or unusable - the gate is unavailable."""


class InjectionError(Exception):
    """A mutation could not be applied, so nothing about the gate was learned.

    Raised rather than swallowed on purpose: an operator that silently fails to apply
    leaves the gate green and would read as "the gate survived", which is a false
    negative in the direction that hides a broken gate.
    """


class PathSyntaxError(InjectionError):
    """A ``path`` expression is outside the supported subset."""


# ---------------------------------------------------------------------------
# ASCII display
# ---------------------------------------------------------------------------


def _ascii(text: str) -> str:
    """Escape non-ASCII for the Windows console; comparison always uses this form.

    ``expect_names`` entries are ASCII by construction, so escaping the gate's output
    before the substring search cannot mask a match. C57's registered title contains a
    non-ASCII arrow, which is exactly why this exists.
    """
    if text.isascii():
        return text
    return text.encode("unicode_escape").decode("ascii")


# ---------------------------------------------------------------------------
# Models - the committed declaration
# ---------------------------------------------------------------------------


class OperatorKind(StrEnum):
    """Exactly the operator vocabulary the schema enumerates. No more, no less."""

    SET_YAML_PATH = "set_yaml_path"
    SET_JSON_PATH = "set_json_path"
    REPLACE_REGEX = "replace_regex"
    REPLACE_FUNCTION_BODY = "replace_function_body"
    CREATE_FILE = "create_file"
    DELETE_FILE = "delete_file"


class MutationOperator(BaseModel):
    """One declared mutation: what to change, and what the gate must then name."""

    model_config = ConfigDict(frozen=True)

    id: str
    operator: OperatorKind
    target: str
    expect_names: tuple[str, ...]
    path: str | None = None
    value: JsonScalar = None
    value_declared: bool = False
    pattern: str | None = None
    replacement: str | None = None
    body: str | None = None
    note: str | None = None

    @property
    def file_target(self) -> str:
        """The repo-relative file the operator writes.

        ``replace_function_body`` addresses a symbol as ``path.py::Class.func``; every
        other operator's ``target`` is already the path.
        """
        return self.target.split("::", 1)[0]

    @property
    def symbol_target(self) -> str | None:
        """``Class.func`` / ``func`` for ``replace_function_body``, else ``None``."""
        if "::" not in self.target:
            return None
        return self.target.split("::", 1)[1]


class GateDeclaration(BaseModel):
    """One check and the mutations it declares must falsify it."""

    model_config = ConfigDict(frozen=True)

    check: str
    title: str
    operators: tuple[MutationOperator, ...]


class ReportingTool(BaseModel):
    """A registered check for which no falsifying mutation can be written.

    Excluded from PASS-eligibility. The ``reason`` must describe the check's nature,
    not the cost of writing the mutation - a schema-level obligation this model carries
    forward only as documentation.
    """

    model_config = ConfigDict(frozen=True)

    check: str
    reason: str
    note: str | None = None


class Completeness(BaseModel):
    """The declared-vs-registered coverage obligation."""

    model_config = ConfigDict(frozen=True)

    declared_gates: int
    registry_size_at_authoring: int
    enforced_by: str


class SweepBudget(BaseModel):
    """The committed cost budget for a complete sweep (AD-13, AD-22).

    A complete sweep spawns one subprocess per declared check (the unmutated baseline)
    plus one per declared operator, so its worst case is a product of a committed
    per-subprocess bound and a count the declaration itself carries. Committing all
    three numbers is what lets a gate assert that the worst case still fits inside the
    job that hosts it, rather than discovering it by timing out in CI.

    :meth:`fits` is the arithmetic invariant; the check that asserts it over the live
    declaration is registered separately, because a model that both holds a number and
    judges it is a model nobody can test against a different number.

    Extra keys are ignored rather than forbidden, and that is a division of labour rather
    than laxity: the committed block also carries ``invariant`` and ``derivation``, which
    are documentation and pointers for a reader, and the schema is what validates their
    shape. Nothing here reads them, so nothing here should refuse a declaration for
    carrying them. A *misspelled* numeric term is still caught, because all three are
    required and none has a default - which is the direction that matters, since a term
    silently defaulted is a bound nobody committed.
    """

    model_config = ConfigDict(frozen=True, extra="ignore")

    per_subprocess_timeout_s: float = Field(gt=0.0)
    install_budget_s: float = Field(ge=0.0)
    job_timeout_minutes: int = Field(gt=0)

    def worst_case_s(self, *, baselines: int, operators: int) -> float:
        """The wall clock the committed bounds admit in the worst case."""
        return (baselines + operators) * self.per_subprocess_timeout_s + self.install_budget_s

    def fits(self, *, baselines: int, operators: int) -> bool:
        """Whether that worst case fits inside the committed job bound."""
        return (
            self.worst_case_s(baselines=baselines, operators=operators)
            <= self.job_timeout_minutes * 60
        )


class MutationDeclaration(BaseModel):
    """``infrastructure/quality/gate-mutations.yaml``, parsed."""

    model_config = ConfigDict(frozen=True)

    version: int
    gates: tuple[GateDeclaration, ...]
    reporting_tools: tuple[ReportingTool, ...]
    completeness: Completeness
    #: ``None`` when the declaration commits no budget. Optional on the model and
    #: optional in the schema, because the sweep is what requires it: a run that probes
    #: nothing needs no bound, and a run that probes refuses to invent one.
    sweep_budget: SweepBudget | None = None

    @property
    def declared_ids(self) -> tuple[str, ...]:
        return tuple(gate.check for gate in self.gates)

    @property
    def reporting_tool_ids(self) -> tuple[str, ...]:
        return tuple(tool.check for tool in self.reporting_tools)

    @property
    def operator_count(self) -> int:
        """Declared mutation operators, the unit a sweep's cost is measured in.

        Not the check count: 14 declared checks carry 16 operators today, because two of
        them declare two each.
        """
        return sum(len(gate.operators) for gate in self.gates)


# ---------------------------------------------------------------------------
# Models - one probe and the report it rolls into
# ---------------------------------------------------------------------------


class GateRun(BaseModel):
    """One out-of-process gate execution.

    Deliberately carries no timing: the report is serialised canonically so two runs of
    the same tree are byte-comparable, and a duration would break that.
    """

    model_config = ConfigDict(frozen=True)

    check: str
    command: tuple[str, ...]
    exit_code: int | None
    output: str
    timed_out: bool

    @property
    def passed(self) -> bool:
        return self.exit_code == 0 and not self.timed_out


Outcome = Literal["falsified", "survived", "indeterminate", "not-applied"]


class FaultInjectionResult(BaseModel):
    """What one declared operator proved, or failed to prove, about one gate."""

    model_config = ConfigDict(frozen=True)

    check: str
    operator_id: str
    operator: OperatorKind
    target: str
    expect_names: tuple[str, ...]
    applied: bool
    exit_code: int | None
    non_zero_exit: bool
    names_present: tuple[str, ...]
    missing_names: tuple[str, ...]
    baseline_exit_code: int | None
    baseline_probed: bool
    timed_out: bool
    outcome: Outcome
    detail: str

    @property
    def falsified(self) -> bool:
        """True only when the gate exited non-zero AND named every declared subject."""
        return self.outcome == "falsified"


class Finding(BaseModel):
    """One violation, naming the subject (the naming obligation applies here too)."""

    model_config = ConfigDict(frozen=True)

    rule: str
    requirement: str
    check: str
    operator_id: str
    detail: str


class FaultInjectionReport(BaseModel):
    """Everything one execution of this harness observed."""

    model_config = ConfigDict(frozen=True)

    declaration: str
    probed: bool
    #: R1.16. True when the run was asked to skip the unmutated baseline. A report
    #: carrying it true is ``unavailable`` and contributes no falsified count, because
    #: without a baseline an already-red gate reads as falsified.
    baseline_suppressed: bool = False
    #: The per-subprocess bound the probes actually ran under, and where it came from.
    #: Recorded because "indeterminate naming the timeout" (R1.5) does not say whose
    #: bound was exceeded unless the bound and its provenance are in the same report.
    sweep_timeout_s: float | None = None
    sweep_timeout_source: Literal["committed-budget", "explicit-override", "not-probed"] = (
        "not-probed"
    )
    registered_ids: tuple[str, ...]
    declared_ids: tuple[str, ...]
    reporting_tool_ids: tuple[str, ...]
    undeclared_ids: tuple[str, ...]
    unregistered_declared_ids: tuple[str, ...]
    results: tuple[FaultInjectionResult, ...]
    falsified_ids: tuple[str, ...]
    pass_eligible_ids: tuple[str, ...]
    excluded_ids: tuple[str, ...]
    findings: tuple[Finding, ...]
    notes: tuple[str, ...]
    verdict: Literal["pass", "fail", "unavailable"]
    reason: str

    @property
    def exit_code(self) -> int:
        return _EXIT_CODES[self.verdict]

    @property
    def passing(self) -> bool:
        """True only for ``pass``. ``unavailable`` is not a pass (I-7)."""
        return self.verdict == "pass"


# ---------------------------------------------------------------------------
# Loading and validating the declaration
# ---------------------------------------------------------------------------


def _relative(path: Path) -> str:
    """Repo-relative POSIX path, for stable reporting on every platform."""
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def load_declaration(path: Path = DECLARATION_FILE) -> dict[str, object]:
    """Read the committed declaration into a plain mapping."""
    if not path.is_file():
        raise DeclarationError(f"declaration not found: {_relative(path)}")
    try:
        raw: object = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as error:
        raise DeclarationError(
            f"declaration is not parseable YAML: {_relative(path)}: {error}"
        ) from error
    if not isinstance(raw, dict):
        raise DeclarationError(f"declaration is not a mapping: {_relative(path)}")
    return {str(key): value for key, value in raw.items()}


def load_schema(path: Path = SCHEMA_FILE) -> dict[str, object]:
    """Read the draft-07 schema and confirm it is itself a valid schema.

    The schema deliberately omits its ``$schema`` keyword so nothing is fetched over the
    network, so the dialect is selected explicitly here.
    """
    if not path.is_file():
        raise DeclarationError(f"schema not found: {_relative(path)}")
    try:
        raw: object = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise DeclarationError(
            f"schema is not parseable JSON: {_relative(path)}: {error}"
        ) from error
    if not isinstance(raw, dict):
        raise DeclarationError(f"schema is not a mapping: {_relative(path)}")
    schema = {str(key): value for key, value in raw.items()}
    try:
        Draft7Validator.check_schema(schema)
    except SchemaError as error:
        raise DeclarationError(
            f"schema is not a valid draft-07 schema: {_relative(path)}: {error.message}"
        ) from error
    return schema


def read_sweep_budget(document: Mapping[str, object]) -> tuple[SweepBudget | None, str]:
    """The committed sweep budget, or ``None`` and the reason it could not be read.

    Total by construction, and deliberately without a fallback. :data:`DEFAULT_TIMEOUT_S`
    is ten times the committed per-subprocess bound, so a silent fallback to it would
    schedule 30 subprocesses against a bound the committed job budget cannot hold - and
    would do so invisibly, which is the failure this reader exists to remove (AD-22).
    An absent or unusable block is a reason a log line can stand on, not a default.

    The reason is returned in both directions so a caller can report *which* of "absent",
    "not a mapping" and "present but unusable" it found: three different repairs.
    """
    raw = document.get(SWEEP_BUDGET_KEY)
    if raw is None:
        return None, (
            f"the declaration commits no `{SWEEP_BUDGET_KEY}` block, so no "
            "per-subprocess bound is declared"
        )
    if not isinstance(raw, Mapping):
        return None, (
            f"`{SWEEP_BUDGET_KEY}` is {type(raw).__name__}, not a mapping, so no "
            "per-subprocess bound can be read from it"
        )
    try:
        budget = SweepBudget.model_validate({str(key): value for key, value in raw.items()})
    except ValidationError as error:
        detail = "; ".join(
            f"{'.'.join(str(part) for part in item['loc']) or '(block)'}: {item['msg']}"
            for item in error.errors()
        )
        return None, f"`{SWEEP_BUDGET_KEY}` is not a usable budget: {_ascii(detail)}"
    return budget, (
        f"per-subprocess bound {budget.per_subprocess_timeout_s:.0f}s read from "
        f"`{SWEEP_BUDGET_KEY}.per_subprocess_timeout_s`"
    )


def _pointer(parts: Sequence[object]) -> str:
    if not parts:
        return "(document root)"
    return "/" + "/".join(str(part) for part in parts)


def _locate(document: Mapping[str, object], parts: Sequence[object]) -> tuple[str, str]:
    """``(check, operator_id)`` for a schema error, best effort.

    A schema error carries a path, not a subject. Recovering the check and operator turns
    "``/gates/C57/operators/0/body`` is wrong" into a finding a reader can act on.
    """
    if not parts or str(parts[0]) != "gates" or len(parts) < 2:
        return ("(document)", "(n/a)")
    check = str(parts[1])
    gates = document.get("gates")
    if (
        len(parts) >= 4
        and str(parts[2]) == "operators"
        and isinstance(parts[3], int)
        and isinstance(gates, dict)
    ):
        entry = gates.get(check)
        if isinstance(entry, dict):
            operators = entry.get("operators")
            if isinstance(operators, list) and 0 <= parts[3] < len(operators):
                candidate = operators[parts[3]]
                if isinstance(candidate, dict):
                    return check, str(candidate.get("id", f"(index {parts[3]})"))
        return check, f"(index {parts[3]})"
    return check, "(n/a)"


def schema_findings(
    document: Mapping[str, object], schema: Mapping[str, object]
) -> tuple[Finding, ...]:
    """Every draft-07 violation of the declaration, in a stable order.

    A malformed declaration is a repository defect, not an unavailable measurement: the
    file is committed to this tree, so it FAILs here rather than being reported
    ``unavailable``. Structural validity is a precondition of the sweep, never a
    substitute for it.
    """
    validator = Draft7Validator(dict(schema))
    findings: list[Finding] = []
    for error in validator.iter_errors(dict(document)):
        parts = list(error.absolute_path)
        check, operator_id = _locate(document, parts)
        findings.append(
            Finding(
                rule="declaration-schema-invalid",
                requirement="R1.2",
                check=check,
                operator_id=operator_id,
                detail=(
                    f"{_pointer(parts)} violates the declaration schema: "
                    f"{_ascii(error.message)}"
                ),
            )
        )
    return tuple(sorted(findings, key=lambda item: (item.check, item.operator_id, item.detail)))


def _operator(raw: Mapping[str, object]) -> MutationOperator:
    expect = raw.get("expect_names")
    names = tuple(str(item) for item in expect) if isinstance(expect, list) else ()
    value = raw.get("value")
    return MutationOperator(
        id=str(raw.get("id", "")),
        operator=OperatorKind(str(raw.get("operator", ""))),
        target=str(raw.get("target", "")),
        expect_names=names,
        path=str(raw["path"]) if isinstance(raw.get("path"), str) else None,
        value=value if isinstance(value, str | bool | int | float) or value is None else None,
        value_declared="value" in raw,
        pattern=str(raw["pattern"]) if isinstance(raw.get("pattern"), str) else None,
        replacement=(
            str(raw["replacement"]) if isinstance(raw.get("replacement"), str) else None
        ),
        body=str(raw["body"]) if isinstance(raw.get("body"), str) else None,
        note=str(raw["note"]) if isinstance(raw.get("note"), str) else None,
    )


def parse_declaration(document: Mapping[str, object]) -> MutationDeclaration:
    """Project a schema-valid document onto the models. Assumes validation ran first."""
    raw_gates = document.get("gates")
    gates: list[GateDeclaration] = []
    if isinstance(raw_gates, dict):
        for check, entry in raw_gates.items():
            if not isinstance(entry, dict):
                continue
            operators = entry.get("operators")
            gates.append(
                GateDeclaration(
                    check=str(check),
                    title=str(entry.get("title", "")),
                    operators=tuple(
                        _operator(item)
                        for item in (operators if isinstance(operators, list) else [])
                        if isinstance(item, dict)
                    ),
                )
            )

    raw_tools = document.get("reporting_tools")
    tools: list[ReportingTool] = []
    if isinstance(raw_tools, list):
        for item in raw_tools:
            if not isinstance(item, dict):
                continue
            tools.append(
                ReportingTool(
                    check=str(item.get("check", "")),
                    reason=str(item.get("reason", "")),
                    note=str(item["note"]) if isinstance(item.get("note"), str) else None,
                )
            )

    raw_completeness = document.get("completeness")
    block = raw_completeness if isinstance(raw_completeness, dict) else {}
    version = document.get("version")
    budget, _budget_reason = read_sweep_budget(document)
    return MutationDeclaration(
        version=int(version) if isinstance(version, int) else 0,
        gates=tuple(gates),
        reporting_tools=tuple(tools),
        sweep_budget=budget,
        completeness=Completeness(
            declared_gates=int(block.get("declared_gates", 0) or 0),
            registry_size_at_authoring=int(block.get("registry_size_at_authoring", 0) or 0),
            enforced_by=str(block.get("enforced_by", "")),
        ),
    )


def registered_ids() -> tuple[str, ...]:
    """Every identifier ``@register`` declared, in registration order.

    Read from ``verify_claims._CHECKS`` so the registration list stays the single source
    of truth for what "registered" means (the same rule ``registry_gate`` follows).
    Imported lazily: the declaration half of this module must be usable without paying
    for the registry import.
    """
    from scripts.audit import verify_claims

    return tuple(cid for cid, _title, _fn in verify_claims._CHECKS)


# ---------------------------------------------------------------------------
# The temporary copy of the real tree
# ---------------------------------------------------------------------------


def _ignore(directory: str, names: list[str]) -> set[str]:
    del directory  # name-based exclusion only; see COPY_EXCLUDED_NAMES
    return {
        name
        for name in names
        if name in COPY_EXCLUDED_NAMES or name.endswith(COPY_EXCLUDED_SUFFIXES)
    }


@contextmanager
def tree_copy(source: Path = ROOT) -> Iterator[Path]:
    """Yield a temporary copy of ``source``, removed on exit.

    This is the only tree a mutation is ever applied to. The copy is not a git worktree
    and carries no ``.git`` directory on purpose - a fault-injected tree must not be
    mistakable for a branch, and no registered check reads git metadata.
    """
    holder = tempfile.mkdtemp(prefix="synapse-fault-injection-")
    tree = Path(holder) / source.name
    try:
        shutil.copytree(source, tree, ignore=_ignore, symlinks=True)
        _LOG.debug("fault_injection.tree_copied", tree=str(tree), source=str(source))
        yield tree
    finally:
        shutil.rmtree(holder, ignore_errors=True)


def _resolve_in_tree(tree: Path, relative: str) -> Path:
    """Resolve ``relative`` inside ``tree``, refusing to escape it or to touch ROOT.

    Two guards, both hard. The tree must not be the working tree - ``inject`` writing to
    :data:`ROOT` would turn an audit into a code change. And the resolved target must
    stay inside the tree, so a declared ``../`` target cannot reach out of the copy.
    """
    resolved_tree = tree.resolve()
    if resolved_tree == ROOT.resolve():
        raise InjectionError(
            "refusing to mutate the working tree: inject() operates only on a temporary "
            "copy (design AD-4 / E2.1)"
        )
    target = (resolved_tree / relative).resolve()
    if not target.is_relative_to(resolved_tree):
        raise InjectionError(f"target escapes the temporary tree: {relative}")
    return target


def mutated_path(operator: MutationOperator) -> str:
    """The repo-relative file ``operator`` writes."""
    return operator.file_target


def restore(operator: MutationOperator, tree: Path, *, source: Path = ROOT) -> None:
    """Undo ``operator`` by re-syncing its single target from ``source``.

    One copy is reused across a sweep, so each operator's target is restored from the
    real tree afterwards. A file the operator created (absent from ``source``) is
    removed; anything else is overwritten byte-for-byte from ``source``, so no mutation
    can leak into the next probe.
    """
    target = _resolve_in_tree(tree, mutated_path(operator))
    origin = source / mutated_path(operator)
    if origin.is_file():
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(origin, target)
        return
    if target.exists():
        target.unlink()
    # An empty directory left behind by create_file is harmless: no check enumerates it.


# ---------------------------------------------------------------------------
# Document paths (set_yaml_path / set_json_path)
# ---------------------------------------------------------------------------


def parse_document_path(raw: str) -> tuple[str | int, ...]:
    """Parse the supported path subset into a segment tuple.

    One parser serves both operators, because the declaration uses two spellings of the
    same idea: ``$.thresholds.break`` (JSONPath) and
    ``packages['packages/synapse_common'].line`` (dotted with quoted keys). Supported:
    a leading ``$``, dotted names, ``['quoted key']``, ``["quoted key"]`` and ``[3]``.
    Anything else raises :class:`PathSyntaxError` rather than resolving to something
    approximate - a path that quietly means the wrong node would mutate the wrong value
    and misreport the gate.
    """
    text = raw.strip()
    if text.startswith("$"):
        text = text[1:]
    parts: list[str | int] = []
    index = 0
    length = len(text)
    while index < length:
        char = text[index]
        if char == ".":
            index += 1
            continue
        if char == "[":
            close = text.find("]", index)
            if close == -1:
                raise PathSyntaxError(f"unbalanced '[' in path: {raw!r}")
            token = text[index + 1 : close].strip()
            if len(token) >= 2 and token[0] == token[-1] and token[0] in {"'", '"'}:
                parts.append(token[1:-1])
            elif re.fullmatch(r"-?\d+", token):
                parts.append(int(token))
            else:
                raise PathSyntaxError(
                    f"unsupported subscript {token!r} in path {raw!r}: use a quoted key "
                    "or an integer index"
                )
            index = close + 1
            continue
        end = index
        while end < length and text[end] not in {".", "["}:
            end += 1
        segment = text[index:end].strip()
        if not segment:
            raise PathSyntaxError(f"empty segment in path: {raw!r}")
        parts.append(segment)
        index = end
    if not parts:
        raise PathSyntaxError(f"path selects nothing: {raw!r}")
    return tuple(parts)


def set_at(document: object, path: str, value: JsonScalar) -> object:
    """Write ``value`` at ``path`` in a parsed document and return the document.

    Every intermediate container must already exist: a path whose parents are absent is
    a wrong path, and creating them would mutate a shape the gate never had. The final
    key may be created, because "add a key the gate must reject" is a legitimate
    mutation (C60's ``$.replicates_per_arm`` is exactly that - the committed artifact
    carries no such key).
    """
    segments = parse_document_path(path)
    node: object = document
    for depth, segment in enumerate(segments[:-1]):
        walked = ".".join(str(part) for part in segments[: depth + 1])
        if isinstance(node, dict) and isinstance(segment, str):
            if segment not in node:
                raise InjectionError(f"path segment {walked!r} is absent from the document")
            node = node[segment]
        elif isinstance(node, list) and isinstance(segment, int):
            if not -len(node) <= segment < len(node):
                raise InjectionError(f"path index {walked!r} is out of range")
            node = node[segment]
        else:
            raise InjectionError(
                f"path segment {walked!r} does not address a mapping or sequence member"
            )
    leaf = segments[-1]
    if isinstance(node, dict) and isinstance(leaf, str):
        node[leaf] = value
        return document
    if isinstance(node, list) and isinstance(leaf, int):
        if not -len(node) <= leaf < len(node):
            raise InjectionError(f"path index {path!r} is out of range")
        node[leaf] = value
        return document
    raise InjectionError(f"path {path!r} does not address a writable member")


# ---------------------------------------------------------------------------
# The six operators
# ---------------------------------------------------------------------------


def _require(operator: MutationOperator, field: str, present: bool) -> None:
    if not present:
        raise InjectionError(
            f"operator {operator.id!r} ({operator.operator}) declares no {field}"
        )


def _read(target: Path, operator: MutationOperator) -> str:
    if not target.is_file():
        raise InjectionError(
            f"operator {operator.id!r} targets {mutated_path(operator)}, which is not a "
            "file in the copied tree"
        )
    return target.read_text(encoding="utf-8")


def _write_changed(target: Path, original: str, mutated: str, operator: MutationOperator) -> None:
    """Write ``mutated``, refusing a no-op.

    A mutation that changes no byte cannot falsify anything, so it must never be able to
    read as "the gate survived". C60's ``mark-the-artifact-incomplete`` is currently
    exactly this case: the committed artifact already carries ``incomplete: true``.
    """
    if mutated == original:
        raise InjectionError(
            f"operator {operator.id!r} changed nothing: {mutated_path(operator)} already "
            "carries the declared mutation, so no falsification can be attributed to it"
        )
    target.write_text(mutated, encoding="utf-8")


def _dump_yaml(document: object) -> str:
    return str(
        yaml.safe_dump(document, sort_keys=False, default_flow_style=False, allow_unicode=True)
    )


def _inject_set_yaml_path(operator: MutationOperator, target: Path) -> None:
    _require(operator, "path", operator.path is not None)
    _require(operator, "value", operator.value_declared)
    original = _read(target, operator)
    try:
        document: object = yaml.safe_load(original)
    except yaml.YAMLError as error:
        raise InjectionError(f"{mutated_path(operator)} is not parseable YAML: {error}") from error
    assert operator.path is not None  # narrowed by _require
    mutated = _dump_yaml(set_at(document, operator.path, operator.value))
    # Comments are not preserved by a safe_load/safe_dump round trip. That is acceptable
    # and confined: the write happens only inside the temporary copy, and every gate this
    # operator serves reads values rather than comments.
    _write_changed(target, original, mutated, operator)


def _inject_set_json_path(operator: MutationOperator, target: Path) -> None:
    _require(operator, "path", operator.path is not None)
    _require(operator, "value", operator.value_declared)
    original = _read(target, operator)
    try:
        document: object = json.loads(original)
    except json.JSONDecodeError as error:
        raise InjectionError(f"{mutated_path(operator)} is not parseable JSON: {error}") from error
    assert operator.path is not None  # narrowed by _require
    mutated = (
        json.dumps(set_at(document, operator.path, operator.value), indent=2, sort_keys=True)
        + "\n"
    )
    _write_changed(target, original, mutated, operator)


def _inject_replace_regex(operator: MutationOperator, target: Path) -> None:
    _require(operator, "pattern", operator.pattern is not None)
    _require(operator, "replacement", operator.replacement is not None)
    assert operator.pattern is not None and operator.replacement is not None
    original = _read(target, operator)
    try:
        compiled = re.compile(operator.pattern)
    except re.error as error:
        raise InjectionError(
            f"operator {operator.id!r} declares an invalid pattern: {error}"
        ) from error
    if compiled.search(original) is None:
        raise InjectionError(
            f"operator {operator.id!r} pattern {operator.pattern!r} does not match "
            f"{mutated_path(operator)}: the declaration has drifted from the tree"
        )
    _write_changed(
        target, original, compiled.sub(operator.replacement, original), operator
    )


def _find_symbol(
    module: ast.Module, symbol: str
) -> ast.FunctionDef | ast.AsyncFunctionDef | None:
    """Locate ``Class.func`` or ``func`` in a parsed module.

    A one-level qualifier is enough for the declared vocabulary and is all that is
    supported; an unresolvable symbol raises rather than mutating a same-named function
    somewhere else in the file.
    """
    owner, _, name = symbol.rpartition(".")
    if owner:
        for node in module.body:
            if isinstance(node, ast.ClassDef) and node.name == owner:
                for child in node.body:
                    if (
                        isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef)
                        and child.name == name
                    ):
                        return child
        return None
    for node in ast.walk(module):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and node.name == name:
            return node
    return None


def _inject_replace_function_body(operator: MutationOperator, target: Path) -> None:
    _require(operator, "body", operator.body is not None)
    symbol = operator.symbol_target
    if not symbol:
        raise InjectionError(
            f"operator {operator.id!r} must address a symbol as path.py::Class.func"
        )
    assert operator.body is not None
    original = _read(target, operator)
    try:
        module = ast.parse(original)
    except SyntaxError as error:
        raise InjectionError(
            f"{mutated_path(operator)} is not parseable Python: {error}"
        ) from error
    node = _find_symbol(module, symbol)
    if node is None:
        raise InjectionError(
            f"operator {operator.id!r} targets {symbol!r}, which {mutated_path(operator)} "
            "does not define"
        )
    first = node.body[0]
    last_line = max(
        (statement.end_lineno or statement.lineno) for statement in node.body
    )
    indent = " " * first.col_offset
    replacement = [
        f"{indent}{line}" if line.strip() else ""
        for line in textwrap.dedent(operator.body).rstrip("\n").splitlines()
    ]
    lines = original.splitlines()
    # The signature, its decorators and its type annotations are untouched: the point is
    # a function that still looks right and does nothing, which is the shape a
    # substring-matching gate cannot see (the canonical AD-4 example).
    mutated = "\n".join(lines[: first.lineno - 1] + replacement + lines[last_line:])
    if original.endswith("\n"):
        mutated += "\n"
    _write_changed(target, original, mutated, operator)


def _inject_create_file(operator: MutationOperator, target: Path) -> None:
    _require(operator, "body", operator.body is not None)
    assert operator.body is not None
    if target.exists():
        raise InjectionError(
            f"operator {operator.id!r} would create {mutated_path(operator)}, which "
            "already exists in the copied tree"
        )
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(operator.body, encoding="utf-8")


def _inject_delete_file(operator: MutationOperator, target: Path) -> None:
    if not target.is_file():
        raise InjectionError(
            f"operator {operator.id!r} would delete {mutated_path(operator)}, which is "
            "not a file in the copied tree"
        )
    target.unlink()


def inject(operator: MutationOperator, tree: Path) -> None:
    """Apply ``operator`` inside ``tree``, which MUST be a temporary copy.

    Raises :class:`InjectionError` when the mutation cannot be applied or would change
    nothing. Both cases are reported as ``not-applied`` rather than being treated as a
    surviving gate: the harness must not be able to convert its own defect into a
    verdict about the gate.
    """
    target = _resolve_in_tree(tree, mutated_path(operator))
    handlers = {
        OperatorKind.SET_YAML_PATH: _inject_set_yaml_path,
        OperatorKind.SET_JSON_PATH: _inject_set_json_path,
        OperatorKind.REPLACE_REGEX: _inject_replace_regex,
        OperatorKind.REPLACE_FUNCTION_BODY: _inject_replace_function_body,
        OperatorKind.CREATE_FILE: _inject_create_file,
        OperatorKind.DELETE_FILE: _inject_delete_file,
    }
    handlers[operator.operator](operator, target)
    _LOG.debug(
        "fault_injection.applied",
        operator=operator.id,
        kind=str(operator.operator),
        target=mutated_path(operator),
        tree=str(tree),
    )


# ---------------------------------------------------------------------------
# Running the gate out-of-process
# ---------------------------------------------------------------------------


def _gate_command(check: str) -> tuple[str, ...]:
    """The subprocess that evaluates one registered check inside a given tree.

    It is told the check id and nothing else. The harness never passes the mutation, the
    target, or the expected names, so a gate cannot satisfy ``expect_names`` by echoing
    something it was handed - naming the subject has to come from the gate's own
    observation of the tree.
    """
    return (sys.executable, "-m", "scripts.audit.gate_fault_injection", "--run-check", check)


def run_gate(
    check: str,
    tree: Path,
    *,
    timeout: float = DEFAULT_TIMEOUT_S,
    command: Sequence[str] | None = None,
) -> GateRun:
    """Run the gate for ``check`` as a subprocess rooted in ``tree``.

    A real process, not an in-process call: the subprocess imports the *mutated* tree's
    own ``verify_claims`` and its own check function, so there is no seam in which the
    evaluator could be replaced by a stub (R9.5). ``command`` exists for probes whose
    gate is not a registered check - a perturbed-implementation oracle test (R12.3) is
    run by handing its pytest node id here - and defaults to the registry runner.
    """
    argv = tuple(command) if command is not None else _gate_command(check)
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join([str(tree), env.get("PYTHONPATH", "")]).rstrip(os.pathsep)
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    try:
        # argv is built in this module and passed as a list: never shell-parsed.
        completed = subprocess.run(
            argv,
            cwd=str(tree),
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as expired:
        captured = "".join(
            part.decode("utf-8", "replace") if isinstance(part, bytes) else str(part or "")
            for part in (expired.stdout, expired.stderr)
        )
        return GateRun(
            check=check,
            command=argv,
            exit_code=None,
            output=_ascii(captured),
            timed_out=True,
        )
    except OSError as error:
        return GateRun(
            check=check,
            command=argv,
            exit_code=None,
            output=_ascii(f"gate subprocess could not be started: {error}"),
            timed_out=False,
        )
    return GateRun(
        check=check,
        command=argv,
        exit_code=completed.returncode,
        output=_ascii(completed.stdout + completed.stderr),
        timed_out=False,
    )


def unobservable_reason(run: GateRun, *, timeout: float) -> str | None:
    """Why ``run`` observed nothing about the gate, or ``None`` if it did observe.

    Three of R1.11's four conditions are decided here, and they are decided separately
    on purpose: a subprocess that never started, one that outlived its committed bound,
    and one a signal killed are three different repairs, and collapsing them into "the
    gate did not answer" would name none of them (R1.5).

    A negative return code is the POSIX signal convention (``-N`` for signal ``N``). Its
    status is the signal's and not the gate's, so it can never be read as a non-zero exit
    the mutation caused - which is what would otherwise let a killed subprocess report
    ``falsified`` or ``survived``.
    """
    if run.timed_out:
        return f"did not answer within its {timeout:.0f}s per-subprocess bound"
    if run.exit_code is None:
        return f"could not be started: {run.output.strip()[:200]}"
    if run.exit_code < 0:
        return (
            f"was terminated by signal {-run.exit_code} rather than exiting, so the "
            "status is the signal's and not the gate's"
        )
    return None


def falsifies(
    gate_id: str,
    operator: MutationOperator,
    *,
    tree: Path | None = None,
    baseline: GateRun | None = None,
    timeout: float = DEFAULT_TIMEOUT_S,
    command: Sequence[str] | None = None,
) -> FaultInjectionResult:
    """Apply ``operator`` to a copy of the real tree and report whether the gate bit.

    ``falsified`` requires both halves of the declared contract:

    * the gate exited **non-zero**, and
    * its output contains **every** ``expect_names`` substring.

    A non-zero exit that names nothing is ``survived``, because a gate that fails without
    saying what failed cannot be acted on and does not satisfy the declaration. When
    ``baseline`` is supplied and the gate does not pass on the unmutated copy, the result
    is ``indeterminate``: a check that is already red proves nothing by staying red. A run
    that observed nothing at all - a timeout, an unstartable process, or a
    signal-terminated one, each named separately by :func:`unobservable_reason` - is
    ``indeterminate`` too, and so is a baseline in any of those states. None of them is a
    pass (I-7).

    Note what ``baseline=None`` does *not* mean: it is the diagnostic mode, and a
    ``falsified`` outcome under it is unsound because an already-red gate stays red. The
    classifier reports what it saw; refusing to count it as proof is
    :func:`evaluate`'s job, via ``baseline_suppressed`` (R1.16).

    With no ``tree``, a temporary copy is created and removed around the probe. The
    working tree is never touched.
    """
    if tree is None:
        with tree_copy() as fresh:
            return falsifies(
                gate_id,
                operator,
                tree=fresh,
                baseline=baseline,
                timeout=timeout,
                command=command,
            )

    def result(
        *,
        applied: bool,
        gate_run: GateRun | None,
        outcome: Outcome,
        detail: str,
        names_present: tuple[str, ...] = (),
        missing_names: tuple[str, ...] = (),
    ) -> FaultInjectionResult:
        return FaultInjectionResult(
            check=gate_id,
            operator_id=operator.id,
            operator=operator.operator,
            target=operator.target,
            expect_names=operator.expect_names,
            applied=applied,
            exit_code=gate_run.exit_code if gate_run else None,
            non_zero_exit=bool(gate_run and gate_run.exit_code not in (0, None)),
            names_present=names_present,
            missing_names=missing_names,
            baseline_exit_code=baseline.exit_code if baseline else None,
            baseline_probed=baseline is not None,
            timed_out=bool(gate_run and gate_run.timed_out),
            outcome=outcome,
            detail=detail,
        )

    try:
        inject(operator, tree)
    except InjectionError as error:
        _LOG.warning("fault_injection.not_applied", check=gate_id, operator=operator.id)
        return result(applied=False, gate_run=None, outcome="not-applied", detail=str(error))

    try:
        gate_run = run_gate(gate_id, tree, timeout=timeout, command=command)
    finally:
        restore(operator, tree)

    present = tuple(name for name in operator.expect_names if name in gate_run.output)
    missing = tuple(name for name in operator.expect_names if name not in gate_run.output)

    mutated_unobservable = unobservable_reason(gate_run, timeout=timeout)
    if mutated_unobservable is not None:
        return result(
            applied=True,
            gate_run=gate_run,
            outcome="indeterminate",
            detail=f"the mutated run {mutated_unobservable}, so nothing was proven",
            names_present=present,
            missing_names=missing,
        )
    if baseline is not None and not baseline.passed:
        baseline_unobservable = unobservable_reason(baseline, timeout=timeout)
        cause = (
            f"the unmutated baseline {baseline_unobservable}"
            if baseline_unobservable is not None
            else (
                f"gate does not pass on the unmutated copy (baseline exit "
                f"{baseline.exit_code})"
            )
        )
        return result(
            applied=True,
            gate_run=gate_run,
            outcome="indeterminate",
            detail=(
                f"{cause}, so its exit {gate_run.exit_code} under mutation attributes "
                "nothing to the mutation"
            ),
            names_present=present,
            missing_names=missing,
        )
    if gate_run.exit_code != 0 and not missing:
        return result(
            applied=True,
            gate_run=gate_run,
            outcome="falsified",
            detail=(
                f"gate exited {gate_run.exit_code} naming every declared subject "
                f"({', '.join(operator.expect_names)})"
            ),
            names_present=present,
        )
    if gate_run.exit_code == 0:
        return result(
            applied=True,
            gate_run=gate_run,
            outcome="survived",
            detail="gate exited 0 under the declared mutation: it does not gate this property",
            names_present=present,
            missing_names=missing,
        )
    return result(
        applied=True,
        gate_run=gate_run,
        outcome="survived",
        detail=(
            f"gate exited {gate_run.exit_code} but named nothing for "
            f"{', '.join(missing)}: a non-zero exit that does not name the mutated "
            "subject does not satisfy the declaration"
        ),
        names_present=present,
        missing_names=missing,
    )


# ---------------------------------------------------------------------------
# The sweep
# ---------------------------------------------------------------------------


def sweep(
    declaration: MutationDeclaration,
    *,
    only: str | None = None,
    operator_id: str | None = None,
    timeout: float = DEFAULT_TIMEOUT_S,
    with_baseline: bool = True,
) -> tuple[FaultInjectionResult, ...]:
    """Probe every declared operator (or the selected subset) against a temporary copy.

    One copy serves the whole sweep and each operator's single target is restored from the
    real tree afterwards, so probes cannot contaminate one another. Baselines run in that
    same copy **before** any mutation is applied, which holds the environment constant:
    a baseline read from the working tree could differ from the copy for reasons that have
    nothing to do with the mutation.

    Heavy by construction - one subprocess per gate plus one per operator, over a full
    tree copy. It belongs to ``ci.yml::uplift-verify`` and never runs on the dev box (I-0).
    """
    gates = tuple(
        gate for gate in declaration.gates if only is None or gate.check == only
    )
    results: list[FaultInjectionResult] = []
    with tree_copy() as tree:
        baselines: dict[str, GateRun] = {}
        if with_baseline:
            for gate in gates:
                baselines[gate.check] = run_gate(gate.check, tree, timeout=timeout)
                _LOG.info(
                    "fault_injection.baseline",
                    check=gate.check,
                    exit_code=baselines[gate.check].exit_code,
                )
        for gate in gates:
            for operator in gate.operators:
                if operator_id is not None and operator.id != operator_id:
                    continue
                outcome = falsifies(
                    gate.check,
                    operator,
                    tree=tree,
                    baseline=baselines.get(gate.check),
                    timeout=timeout,
                )
                _LOG.info(
                    "fault_injection.probed",
                    check=gate.check,
                    operator=operator.id,
                    outcome=outcome.outcome,
                )
                results.append(outcome)
    return tuple(results)


# ---------------------------------------------------------------------------
# Verdict
# ---------------------------------------------------------------------------


_OUTCOME_RULES: Final[Mapping[str, tuple[str, str]]] = {
    "survived": ("gate-survived-declared-mutation", "R1.2"),
    "not-applied": ("mutation-not-applied", "R1.2"),
    "indeterminate": ("falsification-indeterminate", "R1.2"),
}


def evaluate(
    *,
    declaration_path: Path = DECLARATION_FILE,
    schema_path: Path = SCHEMA_FILE,
    probe: bool = False,
    only: str | None = None,
    operator_id: str | None = None,
    timeout: float | None = None,
    with_baseline: bool = True,
) -> FaultInjectionReport:
    """Validate the declaration, optionally probe it, and derive the verdict.

    Verdict order - first match wins:

    0. the unmutated baseline was suppressed -> ``unavailable`` naming the suppression,
       with an empty falsified set (R1.16): without a baseline an already-red gate reads
       as falsified, so no probe under it can prove a gate falsifiable
    1. any declaration finding (schema violation, a declared id nobody registered, a
       ``declared_gates`` count that disagrees with ``gates``) -> ``fail``
    2. any operator that survived or could not be applied -> ``fail`` naming each
    3. a probe was requested but the declaration commits no usable per-subprocess bound
       -> ``unavailable`` naming the block, having probed nothing (R1.11)
    4. nothing was probed -> ``unavailable`` (absence of proof is not a pass, I-7)
    5. any indeterminate probe -> ``unavailable`` naming each
    6. otherwise -> ``pass``, listing the PASS-eligible checks

    ``timeout`` is the per-subprocess bound, and ``None`` means "resolve it". Under
    ``probe`` it resolves to the declaration's
    ``sweep_budget.per_subprocess_timeout_s`` and, when that is absent or unusable, to
    nothing at all: rule 3 fires and no subprocess is started. It never falls back to
    :data:`DEFAULT_TIMEOUT_S`, which is ten times the committed bound (AD-22). An
    explicit value still wins, and the report records which of the two was used.

    Undeclared registered checks never produce a ``fail`` here: turning the
    declared-vs-registered shortfall into a gate is task 12.1's job, recorded in the
    declaration's own ``completeness.enforced_by``. They are excluded from
    ``pass_eligible_ids`` and named in the report, which is the honest label AD-4 asks
    for - an exclusion, not an exemption, and never a PASS.
    """
    document = load_declaration(declaration_path)
    schema = load_schema(schema_path)
    findings = list(schema_findings(document, schema))
    declaration = parse_declaration(document)

    registered = registered_ids()
    declared = declaration.declared_ids
    tools = declaration.reporting_tool_ids
    known = set(declared) | set(tools)
    undeclared = tuple(cid for cid in registered if cid not in known)
    unregistered = tuple(cid for cid in (*declared, *tools) if cid not in set(registered))

    for cid in unregistered:
        findings.append(
            Finding(
                rule="declared-check-not-registered",
                requirement="R1.2",
                check=cid,
                operator_id="(n/a)",
                detail=(
                    "the declaration names a check that no @register call in the "
                    "Check_Registry declares, so its mutation can never be evaluated"
                ),
            )
        )
    if declaration.completeness.declared_gates != len(declaration.gates):
        findings.append(
            Finding(
                rule="completeness-count-drift",
                requirement="R1.2",
                check="(completeness)",
                operator_id="(n/a)",
                detail=(
                    f"completeness.declared_gates is "
                    f"{declaration.completeness.declared_gates} but `gates:` holds "
                    f"{len(declaration.gates)} entr(ies); the recorded count must equal "
                    "the declared set so a hand edit is itself detectable"
                ),
            )
        )

    # The bound, resolved before anything is spawned. A sweep that cannot learn its own
    # committed bound does not run at all: it reports what it could not read (R1.11).
    budget, budget_reason = read_sweep_budget(document)
    resolved_timeout: float | None
    timeout_source: Literal["committed-budget", "explicit-override", "not-probed"]
    if timeout is not None:
        resolved_timeout = timeout
        timeout_source = "explicit-override" if probe else "not-probed"
    elif budget is not None:
        resolved_timeout = budget.per_subprocess_timeout_s
        timeout_source = "committed-budget" if probe else "not-probed"
    else:
        resolved_timeout = None
        timeout_source = "not-probed"

    budget_refused = probe and resolved_timeout is None
    probed = probe and resolved_timeout is not None
    results: tuple[FaultInjectionResult, ...] = ()
    if probed and resolved_timeout is not None:  # the second half narrows for mypy only
        results = sweep(
            declaration,
            only=only,
            operator_id=operator_id,
            timeout=resolved_timeout,
            with_baseline=with_baseline,
        )

    for outcome in results:
        rule = _OUTCOME_RULES.get(outcome.outcome)
        if rule is None:
            continue
        findings.append(
            Finding(
                rule=rule[0],
                requirement=rule[1],
                check=outcome.check,
                operator_id=outcome.operator_id,
                detail=outcome.detail,
            )
        )

    probed_ids = tuple(dict.fromkeys(outcome.check for outcome in results))
    # R1.16: a suppressed baseline contributes no falsified count. The per-probe outcomes
    # are still reported faithfully - they are what the diagnosis is for - but they are
    # not proof, because an already-red gate stays red under mutation and reads as
    # falsified. Zeroing the derived sets here is what keeps that from becoming a PASS.
    falsified_ids = (
        ()
        if not with_baseline
        else tuple(
            cid
            for cid in probed_ids
            if all(outcome.falsified for outcome in results if outcome.check == cid)
        )
    )
    pass_eligible = tuple(cid for cid in falsified_ids if cid not in set(tools))
    excluded = tuple(dict.fromkeys((*tools, *undeclared)))

    notes = [
        f"{len(declared)} of {len(registered)} registered check(s) declare a falsification",
        f"{len(tools)} reporting tool(s) and {len(undeclared)} undeclared check(s) are "
        "excluded from PASS-eligibility (I-7: absence of a falsification is absence of "
        "proof, never a pass)",
        f"completeness.enforced_by: {declaration.completeness.enforced_by}",
    ]
    if not probe:
        notes.append(
            "no mutation was applied: --sweep copies the tree and runs one subprocess per "
            "gate, which is a CI workload (ci.yml::uplift-verify), not a local one (I-0)"
        )
    notes.append(f"sweep_budget: {budget_reason}")
    if probed and resolved_timeout is not None:
        notes.append(
            f"per-subprocess bound applied: {resolved_timeout:.0f}s "
            + (
                "(--timeout override, NOT the committed budget)"
                if timeout_source == "explicit-override"
                else f"(committed `{SWEEP_BUDGET_KEY}.per_subprocess_timeout_s`)"
            )
        )
    if not with_baseline:
        notes.append(
            "--no-baseline was given: the per-probe outcomes below are diagnosis and not "
            "proof, and no check enters the falsified set (R1.16)"
        )

    blocking = tuple(
        finding
        for finding in findings
        if finding.rule != "falsification-indeterminate"
    )
    indeterminate = tuple(
        finding for finding in findings if finding.rule == "falsification-indeterminate"
    )

    verdict: Literal["pass", "fail", "unavailable"]
    if not with_baseline:
        # Ahead of every other rule, including the declaration defects, which stay
        # visible in `findings` either way. A report produced without a baseline cannot
        # support any verdict about a gate, so it reports the one thing it does know.
        verdict = "unavailable"
        reason = (
            "the unmutated baseline was suppressed (--no-baseline), so nothing was "
            "proven: without a baseline an already-red gate stays red under mutation and "
            "reads as falsified, which is manufactured proof rather than proof (R1.16). "
            "Re-run without --no-baseline to probe."
        )
    elif blocking:
        verdict = "fail"
        reason = f"{len(blocking)} declaration/falsification defect(s): " + "; ".join(
            f"{finding.check}/{finding.operator_id} {finding.rule}" for finding in blocking[:5]
        )
    elif budget_refused:
        verdict = "unavailable"
        reason = (
            f"--sweep was requested but no per-subprocess bound is committed: "
            f"{budget_reason}; nothing was probed, because defaulting to "
            f"DEFAULT_TIMEOUT_S ({DEFAULT_TIMEOUT_S:.0f}s) would schedule "
            f"{len(declaration.gates)} baseline(s) plus {declaration.operator_count} "
            "operator(s) against a bound the committed job budget cannot hold (R1.11)"
        )
    elif not probe:
        verdict = "unavailable"
        reason = (
            f"declaration is valid for {len(declared)} check(s) but no falsification was "
            "probed; absence of proof is not a pass (I-7) - run with --sweep in CI"
        )
    elif indeterminate:
        verdict = "unavailable"
        reason = f"{len(indeterminate)} probe(s) proved nothing: " + "; ".join(
            f"{finding.check}/{finding.operator_id}" for finding in indeterminate[:5]
        )
    else:
        verdict = "pass"
        reason = (
            f"{len(pass_eligible)} check(s) are falsified by every declared mutation "
            f"({len(excluded)} excluded from PASS-eligibility)"
        )

    return FaultInjectionReport(
        declaration=_relative(declaration_path),
        probed=probed,
        baseline_suppressed=not with_baseline,
        sweep_timeout_s=resolved_timeout if probed else None,
        sweep_timeout_source=timeout_source,
        registered_ids=registered,
        declared_ids=declared,
        reporting_tool_ids=tools,
        undeclared_ids=undeclared,
        unregistered_declared_ids=unregistered,
        results=results,
        falsified_ids=falsified_ids,
        pass_eligible_ids=pass_eligible,
        excluded_ids=excluded,
        findings=tuple(findings),
        notes=tuple(notes),
        verdict=verdict,
        reason=reason,
    )


# ---------------------------------------------------------------------------
# CLI (the only place this module prints)
# ---------------------------------------------------------------------------


def run_single_check(check: str) -> int:
    """Runner mode: execute exactly one registered check in **this** tree.

    This is the process :func:`run_gate` spawns inside the mutated copy. It receives the
    check id and nothing else - no operator, no target, no expected names - so the gate's
    output can only name what the gate itself observed.

    Exit ``0`` only for ``PASS``. FAIL, PARTIAL and SKIP are all non-zero, because a SKIP
    is not a PASS (I-7); the harness's baseline probe is what keeps a SKIP on the
    unmutated tree from being mistaken for a falsification.
    """
    from scripts.audit import verify_claims

    entry = next((item for item in verify_claims._CHECKS if item[0] == check), None)
    if entry is None:
        print(f"[??] {check} is not registered in this tree's Check_Registry")
        return EXIT_UNAVAILABLE
    result = verify_claims._run_check(*entry)
    print(f"[{result.status}] {result.cid} {_ascii(result.title)}: {_ascii(result.detail)}")
    return EXIT_PASS if result.status == "PASS" else EXIT_FAIL


def _print_report(report: FaultInjectionReport) -> None:
    print(
        f"{_SYMBOLS[report.verdict]} gate-fault-injection: {report.verdict.upper()} - "
        f"{report.reason}"
    )
    print(
        f"Summary: REGISTERED={len(report.registered_ids)} DECLARED={len(report.declared_ids)} "
        f"PROBED={len(report.results)} FALSIFIED={len(report.falsified_ids)} "
        f"PASS_ELIGIBLE={len(report.pass_eligible_ids)} EXCLUDED={len(report.excluded_ids)}"
    )
    if report.sweep_timeout_s is not None:
        print(
            f"Bound: {report.sweep_timeout_s:.0f}s per gate subprocess "
            f"({report.sweep_timeout_source})"
        )

    if report.baseline_suppressed:
        print()
        print(
            "BASELINE SUPPRESSED -- no check can enter the falsified set from this run: "
            "without an unmutated baseline an already-red gate reads as falsified (R1.16)."
        )

    if report.results:
        print()
        print(f"PROBES -- {len(report.results)}:")
        marks = {
            "falsified": "[OK]",
            "survived": "[XX]",
            "not-applied": "[XX]",
            "indeterminate": "[--]",
        }
        for outcome in report.results:
            label = f"{outcome.check}/{outcome.operator_id}"
            print(
                f"  {marks[outcome.outcome]} {label:<40} {outcome.outcome:<14} "
                f"{outcome.detail}"
            )

    if report.findings:
        print()
        print(f"FINDINGS -- {len(report.findings)}:")
        for finding in report.findings:
            print(
                f"  [XX] {finding.check}/{finding.operator_id} {finding.rule} "
                f"({finding.requirement}): {finding.detail}"
            )

    if report.undeclared_ids:
        print()
        print(
            f"UNDECLARED -- {len(report.undeclared_ids)} registered check(s) declare no "
            "falsification and are EXCLUDED from PASS-eligibility:"
        )
        print("  [--] " + ", ".join(report.undeclared_ids))

    if report.reporting_tool_ids:
        print()
        print(
            f"REPORTING TOOLS -- {len(report.reporting_tool_ids)} check(s) excluded from "
            "PASS-eligibility by declaration:"
        )
        print("  [--] " + ", ".join(report.reporting_tool_ids))

    print()
    for note in report.notes:
        print(f"note: {note}")


def _print_unavailable(reason: str, *, as_json: bool) -> int:
    """Report an unavailable measurement in whichever mode was asked for.

    Always exits non-passing. A step that could not observe must still emit a status the
    job can gate on, which is why no path here raises (R1.11).
    """
    if as_json:
        print(
            json.dumps(
                {"verdict": "unavailable", "reason": reason},
                sort_keys=True,
                separators=(",", ":"),
            )
        )
    else:
        print(f"{_SYMBOLS['unavailable']} gate-fault-injection: UNAVAILABLE - {reason}")
    return EXIT_UNAVAILABLE


def run(
    *,
    as_json: bool = False,
    check: bool = False,
    probe: bool = False,
    only: str | None = None,
    operator_id: str | None = None,
    timeout: float | None = None,
    with_baseline: bool = True,
) -> int:
    """Evaluate and report. Returns ``0`` / ``1`` / ``2`` in both modes.

    ``--check`` only suppresses the operator note: a gate whose default invocation cannot
    fail is the hole this feature exists to close (R1.8).

    ``timeout=None`` resolves the per-subprocess bound from the committed
    ``sweep_budget`` under ``probe``; see :func:`evaluate`. The three ways this call can
    fail to start at all - an unreadable declaration, an unimportable Check_Registry, and
    an operating-system failure while copying the tree - are each reported ``unavailable``
    naming the cause rather than raising, and so is a report that cannot be serialised
    (R1.11).
    """
    try:
        report = evaluate(
            probe=probe,
            only=only,
            operator_id=operator_id,
            timeout=timeout,
            with_baseline=with_baseline,
        )
    except (DeclarationError, ImportError) as error:
        # An unreadable declaration or an unimportable Check_Registry is an unavailable
        # measurement, not a crash: the step must still emit a non-passing exit code.
        return _print_unavailable(str(error), as_json=as_json)
    except OSError as error:
        # The sweep copies the whole tree before it probes anything. A copy that fails on
        # space, permissions or a path limit is "the sweep could not start" - non-passing
        # and named, never a traceback a log reader has to interpret (R1.11).
        return _print_unavailable(
            f"the sweep could not start: {_ascii(str(error))}", as_json=as_json
        )

    if as_json:
        try:
            payload = json.dumps(
                report.model_dump(mode="json"), sort_keys=True, separators=(",", ":")
            )
        except (TypeError, ValueError) as error:
            # A partial or unparseable payload is worse than none: a consumer that cannot
            # parse the report cannot tell a pass from a defect, so the run reports the
            # serialisation failure instead of emitting the fragment (R1.11).
            return _print_unavailable(
                f"the report could not be serialised: {_ascii(str(error))}", as_json=True
            )
        print(payload)
        return report.exit_code

    _print_report(report)
    if not check:
        print(
            "(a gate that survives its declared mutation does not gate; this exit status "
            "must not be wrapped in `|| true` or `continue-on-error`.)"
        )
    return report.exit_code


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="gate_fault_injection",
        description=(
            "Apply each gate's declared mutation inside a temporary copy of the real tree "
            "and report whether the gate exits non-zero naming the mutated subject."
        ),
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help="emit the report as canonical JSON instead of a human summary",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="suppress the operator note; the exit code is verdict-derived either way",
    )
    parser.add_argument(
        "--sweep",
        action="store_true",
        help=(
            "CI ONLY: copy the tree and run every declared mutation as a subprocess. "
            "Without it nothing is probed and the verdict is unavailable (I-0)"
        ),
    )
    parser.add_argument(
        "--gate", default=None, metavar="CID", help="probe only this check identifier"
    )
    parser.add_argument(
        "--operator", default=None, metavar="ID", help="probe only this operator id"
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=None,
        help=(
            "wall-clock bound on one gate subprocess; overrides the committed "
            f"{SWEEP_BUDGET_KEY}.per_subprocess_timeout_s. Unset, --sweep reads that "
            "committed bound and refuses to run when the declaration commits none - it "
            f"never defaults to {DEFAULT_TIMEOUT_S:.0f}s under --sweep"
        ),
    )
    parser.add_argument(
        "--no-baseline",
        action="store_true",
        help=(
            "skip the unmutated baseline run; a gate that is already red will then read "
            "as falsified, so the report is UNAVAILABLE and falsifies nothing (R1.16). "
            "For diagnosis only"
        ),
    )
    parser.add_argument(
        "--run-check",
        default=None,
        metavar="CID",
        help=argparse.SUPPRESS,  # internal runner mode, spawned inside the mutated copy
    )
    args = parser.parse_args(argv)

    if args.run_check:
        return run_single_check(str(args.run_check))

    return run(
        as_json=bool(args.as_json),
        check=bool(args.check),
        probe=bool(args.sweep),
        only=str(args.gate) if args.gate else None,
        operator_id=str(args.operator) if args.operator else None,
        timeout=None if args.timeout is None else float(args.timeout),
        with_baseline=not bool(args.no_baseline),
    )


if __name__ == "__main__":
    sys.exit(main())
