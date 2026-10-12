"""The Falsification_Sweep's cost budget is a pinned arithmetic claim (AD-13, AD-22; R1.11).

Feature: decision-quality-proof, task 5.3.

``infrastructure/quality/gate-mutations.yaml::sweep_budget`` commits three numbers and one
inequality over them::

    (baselines + operators) * per_subprocess_timeout_s + install_budget_s
        <= job_timeout_minutes * 60

At the counts committed when that block landed: ``30 * 90 + 420 = 3120 <= 3600``. Those
counts are a **worked example in a comment**, and a comment is not a gate. This module is
the gate: it re-derives *both* counts from the declaration's own ``gates:`` block on every
run, so a fifteenth declaring check -- or a second operator on an existing one -- cannot
make the committed budget silently stop fitting.

**Why the counts are read through the declaration's own pointers.** ``sweep_budget``
carries a ``derivation`` block naming where each term comes from
(``baselines_from: completeness.declared_gates``, ``operators_from: gates.*.operators``).
This module resolves those pointers rather than hardcoding the two paths, which is AD-13
applied to a schedule: the number is committed, read rather than inlined, and pinned. A
pointer that resolves to nothing is a **FAIL naming the pointer**, never a term quietly
treated as absent -- the ``None == None`` failure mode task 8.3 fixes for document pins is
exactly as available here, and a budget checked against two absent terms would report
green having compared nothing.

**Four clauses, and the two that are not the inequality matter as much as the one that
is.**

1. ``budget-absent`` / ``derivation-absent`` -> ``unavailable``. The schema deliberately
   leaves ``sweep_budget`` out of its root ``required`` set, so a declaration without it
   is still structurally valid and the honest report of a missing budget belongs here.
   ``unavailable`` maps to SKIP in the registry, which is non-passing and is never a PASS
   (I-7).
2. ``derivation-pointer-unresolved`` -> ``fail``. A pointer into a restructured document
   resolves to nothing on both sides of a comparison, and two absent values agree.
3. ``baseline-count-drift`` -> ``unavailable``. When ``completeness.declared_gates``
   disagrees with the number of entries under ``gates:``, this module cannot know which
   count the budget was committed against, and it does not guess. The drift itself is
   C72's finding (``gate_fault_injection.evaluate`` FAILs on it as
   ``completeness-count-drift``); reporting it as a second FAIL here would give one fact
   two owners, so this clause names C72 and stands down.
4. ``budget-does-not-fit`` -> ``fail`` naming the worst case, the bound and the shortfall.

**A fifth clause makes the third committed number mean something.**
``job_timeout_minutes`` is documented in the declaration and in the schema as "MUST equal
``timeout-minutes`` on the job that runs the sweep". Nothing enforced that, which would
leave the inequality checked against a job budget the job does not have. This module
resolves ``timeout-minutes`` from
``.github/workflows/truth-gates.yml::falsification-sweep`` and compares:
``job-timeout-unresolved`` -> ``unavailable`` naming the workflow and the job (an absent
job is not a satisfied bound), ``job-timeout-mismatch`` -> ``fail`` naming both numbers.

**Nothing here measures anything.** The bounds are committed, not observed, and the
declaration says so in its own words. A gate that cannot answer inside
``per_subprocess_timeout_s`` reports ``indeterminate`` naming the timeout
(``gate_fault_injection.unobservable_reason``), which is non-passing and therefore
surfaces. This module's whole subject is whether the committed numbers are consistent with
each other and with the job that hosts them -- an arithmetic claim, checked as one.

Run::

    python -m scripts.audit.sweep_budget_truth            # human summary
    python -m scripts.audit.sweep_budget_truth --json     # canonical machine JSON
    python -m scripts.audit.sweep_budget_truth --check    # exit-code only mode

Exit codes: ``0`` pass, ``1`` fail, ``2`` unavailable. ``2`` is non-passing.
Every file is read with ``encoding='utf-8'`` (E-S13-07) and all console output is ASCII.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Final, Literal

import structlog
import yaml
from pydantic import BaseModel, ConfigDict

ROOT: Final[Path] = Path(__file__).resolve().parents[2]

if str(ROOT) not in sys.path:  # importable when run as a bare script
    sys.path.insert(0, str(ROOT))

from scripts.audit.gate_fault_injection import (  # noqa: E402 - after the sys.path guard
    DECLARATION_FILE,
    SWEEP_BUDGET_KEY,
    DeclarationError,
    SweepBudget,
    load_declaration,
    read_sweep_budget,
)

#: The workflow and job the committed ``job_timeout_minutes`` must agree with. Named here
#: rather than in the declaration because the declaration is the subject: a file cannot
#: pin the consumer that reads it without becoming its own authority.
SWEEP_WORKFLOW: Final[Path] = ROOT / ".github" / "workflows" / "truth-gates.yml"
SWEEP_JOB: Final[str] = "falsification-sweep"

EXIT_PASS: Final[int] = 0
EXIT_FAIL: Final[int] = 1
EXIT_UNAVAILABLE: Final[int] = 2

Verdict = Literal["pass", "fail", "unavailable"]

_EXIT_CODES: Final[Mapping[str, int]] = {
    "pass": EXIT_PASS,
    "fail": EXIT_FAIL,
    "unavailable": EXIT_UNAVAILABLE,
}
_SYMBOLS: Final[Mapping[str, str]] = {"pass": "[OK]", "fail": "[XX]", "unavailable": "[--]"}

#: The only two pointer shapes this resolver supports. Anything else is refused by name
#: rather than approximated: a pointer that quietly means something adjacent would check
#: the inequality over the wrong term, which is worse than not checking it.
_SUPPORTED_POINTERS: Final[tuple[str, ...]] = (
    "completeness.declared_gates",
    "gates.*.operators",
)

_LOG = structlog.get_logger(__name__)

__all__ = [
    "EXIT_FAIL",
    "EXIT_PASS",
    "EXIT_UNAVAILABLE",
    "ROOT",
    "SWEEP_JOB",
    "SWEEP_WORKFLOW",
    "BudgetFinding",
    "BudgetTerm",
    "SweepBudgetReport",
    "assess",
    "job_timeout_minutes",
    "main",
    "resolve_pointer",
    "run",
]


def _relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def _ascii(text: str) -> str:
    """Escape non-ASCII for the Windows console (ASCII-only output contract)."""
    return text if text.isascii() else text.encode("unicode_escape").decode("ascii")


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class BudgetTerm(BaseModel):
    """One term of the inequality, the pointer it was read through, and whether it read.

    ``resolved`` is carried separately from ``value`` on purpose. A term that could not be
    read has no value, and a default -- ``0`` most temptingly -- would make the inequality
    *easier* to satisfy, which is the direction I-7 forbids.
    """

    model_config = ConfigDict(frozen=True)

    name: str
    pointer: str
    resolved: bool
    value: int | None
    detail: str


class BudgetFinding(BaseModel):
    """One violation, naming its subject."""

    model_config = ConfigDict(frozen=True)

    rule: str
    requirement: str
    subject: str
    detail: str


class SweepBudgetReport(BaseModel):
    """Everything one execution of this gate observed."""

    model_config = ConfigDict(frozen=True)

    declaration: str
    workflow: str
    job: str
    budget_declared: bool
    per_subprocess_timeout_s: float | None
    install_budget_s: float | None
    declared_job_timeout_minutes: int | None
    workflow_job_timeout_minutes: int | None
    terms: tuple[BudgetTerm, ...]
    operational_baselines: int | None
    worst_case_s: float | None
    admitted_s: float | None
    headroom_s: float | None
    findings: tuple[BudgetFinding, ...]
    notes: tuple[str, ...]
    verdict: Verdict
    reason: str

    @property
    def exit_code(self) -> int:
        return _EXIT_CODES[self.verdict]

    @property
    def passing(self) -> bool:
        """``unavailable`` is not a pass (I-7)."""
        return self.verdict == "pass"


# ---------------------------------------------------------------------------
# Pointer resolution
# ---------------------------------------------------------------------------


def resolve_pointer(document: Mapping[str, object], pointer: str) -> tuple[int | None, str]:
    """Resolve one declared ``derivation`` pointer to a count, or say why it did not.

    Total over the supported vocabulary and closed against everything else. Two shapes:

    * ``completeness.declared_gates`` -- a dotted path to an integer.
    * ``gates.*.operators`` -- the **sum** of ``len(operators)`` over every entry under
      ``gates:``, which is the unit a sweep's cost is actually measured in (14 declared
      checks carry 16 operators today, because two declare two each).

    An unsupported pointer returns ``None`` with the supported set named, rather than a
    best-effort walk. The reason is the same one ``parse_document_path`` gives for refusing
    an approximate path: a pointer that quietly addresses a neighbouring node produces a
    number, and a number is indistinguishable from a correct one downstream.
    """
    text = pointer.strip()
    if text not in _SUPPORTED_POINTERS:
        return None, (
            f"pointer {text!r} is outside the supported set "
            f"({', '.join(_SUPPORTED_POINTERS)}), so no term can be read through it"
        )

    if text == "completeness.declared_gates":
        block = document.get("completeness")
        if not isinstance(block, Mapping):
            return None, (
                "`completeness` is absent or is not a mapping, so "
                "`completeness.declared_gates` resolves to nothing"
            )
        raw = block.get("declared_gates")
        if not isinstance(raw, int) or isinstance(raw, bool):
            return None, (
                "`completeness.declared_gates` is "
                f"{type(raw).__name__ if raw is not None else 'absent'}, not an integer"
            )
        return raw, f"{raw} read from `completeness.declared_gates`"

    gates = document.get("gates")
    if not isinstance(gates, Mapping):
        return None, (
            "`gates` is absent or is not a mapping, so `gates.*.operators` resolves to "
            "nothing"
        )
    total = 0
    for check, entry in gates.items():
        if not isinstance(entry, Mapping):
            return None, (
                f"`gates.{check}` is not a mapping, so the operator count cannot be "
                "derived from it"
            )
        operators = entry.get("operators")
        if not isinstance(operators, Sequence) or isinstance(operators, str | bytes):
            return None, (
                f"`gates.{check}.operators` is not a sequence, so the operator count "
                "cannot be derived from it"
            )
        total += len(operators)
    return total, f"{total} summed from `gates.*.operators` over {len(gates)} declared check(s)"


def job_timeout_minutes(
    workflow: Path = SWEEP_WORKFLOW, job: str = SWEEP_JOB
) -> tuple[int | None, str]:
    """``timeout-minutes`` on the job that runs the sweep, or why it could not be read.

    An absent workflow, an absent job and an absent ``timeout-minutes`` are three different
    repairs and are reported as three different details. None of them is a satisfied bound:
    a committed ``job_timeout_minutes`` with no job to constrain is a number pinned to
    nothing.
    """
    if not workflow.is_file():
        return None, f"{_relative(workflow)} is not a file"
    try:
        raw: object = yaml.safe_load(workflow.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        return None, f"{_relative(workflow)} could not be read as YAML: {_ascii(str(error))}"
    if not isinstance(raw, Mapping):
        return None, f"{_relative(workflow)} is not a mapping"
    jobs = raw.get("jobs")
    if not isinstance(jobs, Mapping):
        return None, f"{_relative(workflow)} declares no `jobs:` mapping"
    entry = jobs.get(job)
    if not isinstance(entry, Mapping):
        return None, (
            f"{_relative(workflow)} defines no job {job!r}, so the committed "
            "`job_timeout_minutes` constrains nothing"
        )
    value = entry.get("timeout-minutes")
    if not isinstance(value, int) or isinstance(value, bool):
        return None, (
            f"{_relative(workflow)}::{job} declares no integer `timeout-minutes`, so the "
            "committed bound has nothing to agree with"
        )
    return value, f"{value} read from {_relative(workflow)}::{job}.timeout-minutes"


# ---------------------------------------------------------------------------
# Assessment
# ---------------------------------------------------------------------------


def _absent_report(
    *,
    declaration_path: Path,
    reason: str,
    findings: tuple[BudgetFinding, ...],
    notes: tuple[str, ...],
    verdict: Verdict,
    budget: SweepBudget | None = None,
    terms: tuple[BudgetTerm, ...] = (),
    workflow_minutes: int | None = None,
    operational: int | None = None,
) -> SweepBudgetReport:
    """One constructor for every path that stops before the arithmetic."""
    return SweepBudgetReport(
        declaration=_relative(declaration_path),
        workflow=_relative(SWEEP_WORKFLOW),
        job=SWEEP_JOB,
        budget_declared=budget is not None,
        per_subprocess_timeout_s=budget.per_subprocess_timeout_s if budget else None,
        install_budget_s=budget.install_budget_s if budget else None,
        declared_job_timeout_minutes=budget.job_timeout_minutes if budget else None,
        workflow_job_timeout_minutes=workflow_minutes,
        terms=terms,
        operational_baselines=operational,
        worst_case_s=None,
        admitted_s=None,
        headroom_s=None,
        findings=findings,
        notes=notes,
        verdict=verdict,
        reason=reason,
    )


def assess(declaration_path: Path = DECLARATION_FILE) -> SweepBudgetReport:
    """Re-derive the committed sweep budget's inequality and report the verdict.

    Verdict order -- first match wins:

    0. the declaration commits no ``sweep_budget`` block, or no usable one ->
       ``unavailable`` naming what could not be read (R1.11)
    1. the block commits no ``derivation`` -> ``unavailable``: the counts must be read out
       of this file, and a check that picks its own paths is not reading a declaration
    2. a declared pointer resolves to nothing -> ``fail`` naming the pointer
    3. ``completeness.declared_gates`` disagrees with the number of ``gates:`` entries ->
       ``unavailable`` naming C72 as the owner of that drift
    4. the job that runs the sweep cannot be resolved, or declares no
       ``timeout-minutes`` -> ``unavailable`` naming the workflow and the job
    5. the resolved ``timeout-minutes`` differs from the committed
       ``job_timeout_minutes`` -> ``fail`` naming both numbers
    6. the worst case exceeds the admitted wall clock -> ``fail`` naming the shortfall
    7. otherwise -> ``pass``, reporting the headroom
    """
    document = load_declaration(declaration_path)
    budget, budget_reason = read_sweep_budget(document)
    notes: list[str] = [f"{SWEEP_BUDGET_KEY}: {budget_reason}"]

    if budget is None:
        return _absent_report(
            declaration_path=declaration_path,
            reason=(
                f"no usable `{SWEEP_BUDGET_KEY}` block: {budget_reason}; the sweep's cost "
                "is therefore an unchecked claim, which is non-passing and never a PASS "
                "(I-7)"
            ),
            findings=(
                BudgetFinding(
                    rule="budget-absent",
                    requirement="R1.11",
                    subject=f"{_relative(declaration_path)}::{SWEEP_BUDGET_KEY}",
                    detail=budget_reason,
                ),
            ),
            notes=tuple(notes),
            verdict="unavailable",
        )

    raw_block = document.get(SWEEP_BUDGET_KEY)
    derivation = raw_block.get("derivation") if isinstance(raw_block, Mapping) else None
    if not isinstance(derivation, Mapping):
        return _absent_report(
            declaration_path=declaration_path,
            reason=(
                f"`{SWEEP_BUDGET_KEY}` commits no `derivation` block, so the inequality's "
                "two counts would have to be chosen by this check rather than read from "
                "the declaration (AD-13)"
            ),
            findings=(
                BudgetFinding(
                    rule="derivation-absent",
                    requirement="R1.11",
                    subject=f"{_relative(declaration_path)}::{SWEEP_BUDGET_KEY}.derivation",
                    detail=(
                        "the block must name where `baselines` and `operators` come from; "
                        "a hardcoded path here would be the inlined number AD-13 forbids"
                    ),
                ),
            ),
            notes=tuple(notes),
            verdict="unavailable",
            budget=budget,
        )

    baselines_pointer = str(derivation.get("baselines_from", "")).strip()
    operators_pointer = str(derivation.get("operators_from", "")).strip()
    baselines_value, baselines_detail = resolve_pointer(document, baselines_pointer)
    operators_value, operators_detail = resolve_pointer(document, operators_pointer)
    terms = (
        BudgetTerm(
            name="baselines",
            pointer=baselines_pointer or "(absent)",
            resolved=baselines_value is not None,
            value=baselines_value,
            detail=baselines_detail,
        ),
        BudgetTerm(
            name="operators",
            pointer=operators_pointer or "(absent)",
            resolved=operators_value is not None,
            value=operators_value,
            detail=operators_detail,
        ),
    )

    gates = document.get("gates")
    operational = len(gates) if isinstance(gates, Mapping) else None
    workflow_minutes, workflow_detail = job_timeout_minutes()
    notes.append(f"job timeout: {workflow_detail}")

    unresolved = tuple(term for term in terms if not term.resolved)
    if unresolved:
        return _absent_report(
            declaration_path=declaration_path,
            reason=(
                f"{len(unresolved)} declared derivation pointer(s) resolve to nothing: "
                + "; ".join(f"{term.name} <- {term.pointer}" for term in unresolved)
                + " -- a budget checked over absent terms compares nothing and would "
                "report green"
            ),
            findings=tuple(
                BudgetFinding(
                    rule="derivation-pointer-unresolved",
                    requirement="R1.11",
                    subject=f"{SWEEP_BUDGET_KEY}.derivation.{term.name}_from",
                    detail=term.detail,
                )
                for term in unresolved
            ),
            notes=tuple(notes),
            verdict="fail",
            budget=budget,
            terms=terms,
            workflow_minutes=workflow_minutes,
            operational=operational,
        )

    baselines = terms[0].value
    operators = terms[1].value
    assert baselines is not None and operators is not None  # narrowed by `unresolved`

    if operational is not None and operational != baselines:
        return _absent_report(
            declaration_path=declaration_path,
            reason=(
                f"the declared baseline count ({baselines}) disagrees with the "
                f"{operational} entr(ies) under `gates:`, so this check cannot know which "
                "count the budget was committed against; the drift itself is C72's "
                "finding (`completeness-count-drift`) and is not re-reported here as a "
                "second FAIL"
            ),
            findings=(
                BudgetFinding(
                    rule="baseline-count-drift",
                    requirement="R1.11",
                    subject=f"{SWEEP_BUDGET_KEY}.derivation.baselines_from",
                    detail=(
                        f"`{baselines_pointer}` reads {baselines} while `gates:` holds "
                        f"{operational}; one baseline subprocess is spawned per `gates:` "
                        "entry, so the two must agree before the arithmetic means anything"
                    ),
                ),
            ),
            notes=tuple(notes),
            verdict="unavailable",
            budget=budget,
            terms=terms,
            workflow_minutes=workflow_minutes,
            operational=operational,
        )

    if workflow_minutes is None:
        return _absent_report(
            declaration_path=declaration_path,
            reason=(
                f"the committed `job_timeout_minutes` ({budget.job_timeout_minutes}) has "
                f"nothing to agree with: {workflow_detail}"
            ),
            findings=(
                BudgetFinding(
                    rule="job-timeout-unresolved",
                    requirement="R1.11",
                    subject=f"{_relative(SWEEP_WORKFLOW)}::{SWEEP_JOB}",
                    detail=workflow_detail,
                ),
            ),
            notes=tuple(notes),
            verdict="unavailable",
            budget=budget,
            terms=terms,
            operational=operational,
        )

    worst_case = budget.worst_case_s(baselines=baselines, operators=operators)
    admitted = float(budget.job_timeout_minutes * 60)
    headroom = admitted - worst_case
    findings: list[BudgetFinding] = []

    if workflow_minutes != budget.job_timeout_minutes:
        findings.append(
            BudgetFinding(
                rule="job-timeout-mismatch",
                requirement="R1.11",
                subject=f"{_relative(SWEEP_WORKFLOW)}::{SWEEP_JOB}",
                detail=(
                    f"committed `{SWEEP_BUDGET_KEY}.job_timeout_minutes` is "
                    f"{budget.job_timeout_minutes} but the job declares "
                    f"`timeout-minutes: {workflow_minutes}`; the inequality was checked "
                    "against a bound the job does not carry"
                ),
            )
        )

    if not budget.fits(baselines=baselines, operators=operators):
        findings.append(
            BudgetFinding(
                rule="budget-does-not-fit",
                requirement="R1.11",
                subject=f"{_relative(declaration_path)}::{SWEEP_BUDGET_KEY}",
                detail=(
                    f"({baselines} + {operators}) * "
                    f"{budget.per_subprocess_timeout_s:.0f}s + "
                    f"{budget.install_budget_s:.0f}s = {worst_case:.0f}s exceeds "
                    f"{budget.job_timeout_minutes} * 60 = {admitted:.0f}s by "
                    f"{-headroom:.0f}s; raise `per_subprocess_timeout_s`'s companion "
                    "`job_timeout_minutes` (and the job's own `timeout-minutes`) or shard "
                    "the sweep -- do not narrow the declared operator set to fit"
                ),
            )
        )

    notes.append(
        f"worst case {worst_case:.0f}s = ({baselines} baseline(s) + {operators} "
        f"operator(s)) * {budget.per_subprocess_timeout_s:.0f}s + "
        f"{budget.install_budget_s:.0f}s install allowance"
    )
    notes.append(
        "the bounds are committed, not measured: a gate that cannot answer inside "
        "per_subprocess_timeout_s reports `indeterminate` naming the timeout, which is "
        "non-passing and therefore surfaces (I-7)"
    )

    verdict: Verdict = "fail" if findings else "pass"
    reason = (
        "; ".join(f"{finding.rule}: {finding.detail}" for finding in findings)
        if findings
        else (
            f"worst case {worst_case:.0f}s fits inside the committed "
            f"{budget.job_timeout_minutes}-minute job bound ({admitted:.0f}s) with "
            f"{headroom:.0f}s of headroom, over {baselines} baseline(s) and {operators} "
            "declared operator(s) re-derived from the declaration"
        )
    )
    _LOG.info(
        "sweep_budget.assessed",
        verdict=verdict,
        baselines=baselines,
        operators=operators,
        worst_case_s=worst_case,
        admitted_s=admitted,
    )
    return SweepBudgetReport(
        declaration=_relative(declaration_path),
        workflow=_relative(SWEEP_WORKFLOW),
        job=SWEEP_JOB,
        budget_declared=True,
        per_subprocess_timeout_s=budget.per_subprocess_timeout_s,
        install_budget_s=budget.install_budget_s,
        declared_job_timeout_minutes=budget.job_timeout_minutes,
        workflow_job_timeout_minutes=workflow_minutes,
        terms=terms,
        operational_baselines=operational,
        worst_case_s=worst_case,
        admitted_s=admitted,
        headroom_s=headroom,
        findings=tuple(findings),
        notes=tuple(notes),
        verdict=verdict,
        reason=reason,
    )


# ---------------------------------------------------------------------------
# CLI (the only place this module prints)
# ---------------------------------------------------------------------------


def _print_report(report: SweepBudgetReport) -> None:
    print(
        f"{_SYMBOLS[report.verdict]} sweep-budget: {report.verdict.upper()} - "
        f"{_ascii(report.reason)}"
    )
    for term in report.terms:
        mark = "[OK]" if term.resolved else "[XX]"
        print(f"  {mark} {term.name:<10} {term.pointer:<34} {_ascii(term.detail)}")
    if report.worst_case_s is not None and report.admitted_s is not None:
        print(
            f"  Arithmetic: worst case {report.worst_case_s:.0f}s vs admitted "
            f"{report.admitted_s:.0f}s"
        )
    if report.findings:
        print()
        print(f"FINDINGS -- {len(report.findings)}:")
        for finding in report.findings:
            print(
                f"  [XX] {finding.subject} {finding.rule} ({finding.requirement}): "
                f"{_ascii(finding.detail)}"
            )
    print()
    for note in report.notes:
        print(f"note: {_ascii(note)}")


def run(*, as_json: bool = False, check: bool = False) -> int:
    """Evaluate and report. Returns ``0`` / ``1`` / ``2`` in both modes."""
    try:
        report = assess()
    except DeclarationError as error:
        reason = f"the declaration could not be read: {_ascii(str(error))}"
        if as_json:
            print(
                json.dumps(
                    {"verdict": "unavailable", "reason": reason},
                    sort_keys=True,
                    separators=(",", ":"),
                )
            )
        else:
            print(f"{_SYMBOLS['unavailable']} sweep-budget: UNAVAILABLE - {reason}")
        return EXIT_UNAVAILABLE

    if as_json:
        print(
            json.dumps(
                report.model_dump(mode="json"), sort_keys=True, separators=(",", ":")
            )
        )
        return report.exit_code

    _print_report(report)
    if not check:
        print(
            "(the sweep's cost is a committed arithmetic claim; a budget that stops "
            "fitting must fail here rather than time out in CI.)"
        )
    return report.exit_code


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="sweep_budget_truth",
        description=(
            "Re-derive the Falsification_Sweep's committed cost inequality from the "
            "declaration's own gates block and the job that hosts it."
        ),
    )
    parser.add_argument("--json", action="store_true", dest="as_json")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    return run(as_json=bool(args.as_json), check=bool(args.check))


if __name__ == "__main__":
    sys.exit(main())
