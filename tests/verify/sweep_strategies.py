"""Shared shapes for the Falsification_Sweep properties (38-41).

Feature: decision-quality-proof, tasks 5.7-5.10.

Four properties quantify over the same three objects -- a committed
``gate-mutations.yaml``, the per-operator probe results a sweep of it would return, and
the aggregate report ``gate_fault_injection.evaluate`` derives from the two. Constructing
those in four files would give four slightly different models of one declaration schema,
and the first schema change would leave three of them stale. They are constructed once
here instead.

**A feature-scoped module rather than an addition to** ``tests/verify/strategies.py``.
That module is the purpose-achievement-audit spine's shared generator set and is imported
by a dozen gate-integrity tests; the precedent for a domain-scoped companion is
``packages/tests/strategies_audit.py``. Keeping these shapes separate means a change to
the sweep's declaration schema cannot ripple into tests that have nothing to do with it.

**The operator is the unit** (R1.7). Every helper here is keyed by
``(check, operator_id)``, never by check alone: 14 declared checks carry 16 declared
operators, and a per-check model cannot express "which of C44's two mutations survived",
which is the question the sweep exists to answer.

Two rules this module obeys, both binding:

* **I-0** -- nothing here starts a process, copies a tree, or runs a gate. Every helper
  is pure data construction; the tests decide what to drive with it. The one thing that
  *would* spawn subprocesses -- ``gate_fault_injection.sweep`` -- is substituted by
  :func:`patched_sweep`, which replaces the harness's own orchestrator and never
  replaces any gate's evaluator (R9.5).
* **the authoring rule** -- ``max_examples`` is never set here and must never be set in
  the importing tests. The budget comes from the root ``conftest.py`` profiles
  (``dev``=10, ``heavy``=100, ``ci``/``default``=500, ``nightly``=5000).
"""

from __future__ import annotations

import contextlib
from dataclasses import dataclass, field
from pathlib import Path  # noqa: TC003 - runtime import: keeps SweepDraft.write's annotation
from typing import TYPE_CHECKING, Final  # resolvable if a runtime checker inspects it

import pytest
import yaml
from hypothesis import strategies as st

from scripts.audit import gate_fault_injection as gfi
from scripts.audit.gate_fault_injection import (
    FaultInjectionResult,
    GateRun,
    MutationDeclaration,
    OperatorKind,
)

if TYPE_CHECKING:
    from collections.abc import Iterator, Sequence

__all__ = [
    "BLOCKING_OUTCOMES",
    "PROBE_DIR",
    "SWEEP_OUTCOMES",
    "SweepDraft",
    "gate_runs",
    "patched_sweep",
    "probe_result",
    "sweep_drafts",
]

#: Every outcome one probe may reach, in the classifier's own precedence order. A fifth
#: value would fall through into ``survived``, so the set is closed and pinned here as
#: well as in ``test_declared_falsification_property.py`` -- two independent copies of a
#: closed vocabulary is the point, not duplication.
SWEEP_OUTCOMES: Final[tuple[gfi.Outcome, ...]] = (
    "falsified",
    "survived",
    "indeterminate",
    "not-applied",
)

#: The two outcomes that are a defect of the gate or of the declaration (R1.4). Both FAIL;
#: ``indeterminate`` is separately non-passing but is an absence rather than a defect.
BLOCKING_OUTCOMES: Final[tuple[str, ...]] = ("survived", "not-applied")

#: A directory that does not exist in the real tree. Every synthetic operator targets a
#: path beneath it, so ``restore``'s "re-sync from the real tree" step can never resolve
#: to a committed file.
PROBE_DIR: Final[str] = "generated_sweep_probe"


# ---------------------------------------------------------------------------
# A generated declaration
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SweepDraft:
    """A generated ``gate-mutations.yaml``, keyed by operator rather than by check.

    ``operator_counts`` is parallel to ``declared`` and is what makes the multi-operator
    case reachable: C44 and C56 each declare two operators in the committed file, and a
    draft that only ever produced one per check could not exercise "a check enters the
    falsified set only when EVERY operator declared for it falsified" (R1.6).

    ``budget`` renders the ``sweep_budget`` block. Left true by default so a probing run
    exercises the aggregate rather than the missing-budget refusal; set false by the
    property that is *about* that refusal.
    """

    declared: tuple[str, ...]
    operator_counts: tuple[int, ...]
    tools: tuple[str, ...] = ()
    budget: bool = True
    declared_gates_override: int | None = None
    notes: tuple[str, ...] = field(default=(), compare=False)

    @property
    def declared_pairs(self) -> tuple[tuple[str, str], ...]:
        """``(check, operator_id)`` for every declared operator, in file order.

        File order matters: ``sweep`` iterates gates then operators, so a complete sweep's
        result order is exactly this, and a report that reordered them would be reporting
        a run that could not have happened.
        """
        return tuple(
            (check, f"{check.lower()}-op-{index}")
            for check, count in zip(self.declared, self.operator_counts, strict=True)
            for index in range(count)
        )

    @property
    def declared_operator_count(self) -> int:
        return len(self.declared_pairs)

    def document(self) -> dict[str, object]:
        """The YAML document, in the shape the committed schema requires."""
        gates: dict[str, object] = {}
        for check, count in zip(self.declared, self.operator_counts, strict=True):
            gates[check] = {
                "title": f"generated declaration for {check}",
                "operators": [
                    {
                        "id": f"{check.lower()}-op-{index}",
                        "operator": "delete_file",
                        "target": f"{PROBE_DIR}/{check.lower()}-{index}.txt",
                        "expect_names": ["NAME_ALPHA"],
                    }
                    for index in range(count)
                ],
            }
        document: dict[str, object] = {
            "version": 1,
            "gates": gates,
            "reporting_tools": [
                {"check": check, "reason": "generated: no falsifying mutation exists"}
                for check in self.tools
            ],
            "completeness": {
                "declared_gates": (
                    len(gates)
                    if self.declared_gates_override is None
                    else self.declared_gates_override
                ),
                "registry_size_at_authoring": 64,
                "enforced_by": "generated: C72",
            },
        }
        if self.budget:
            # Schema-complete: `invariant` and `derivation` are required whenever the
            # block is present, and the derivation pointers are the two the committed
            # file uses, so a draft exercises the same read path C73 does.
            document["sweep_budget"] = {
                "per_subprocess_timeout_s": 90,
                "install_budget_s": 420,
                "job_timeout_minutes": 60,
                "invariant": (
                    "(baselines + operators) * per_subprocess_timeout_s + "
                    "install_budget_s <= job_timeout_minutes * 60"
                ),
                "derivation": {
                    "baselines_from": "completeness.declared_gates",
                    "operators_from": "gates.*.operators",
                },
            }
        return document

    def write(self, directory: Path) -> Path:
        path = directory / "gate-mutations.yaml"
        path.write_text(
            yaml.safe_dump(self.document(), sort_keys=False, allow_unicode=False),
            encoding="utf-8",
        )
        return path


@st.composite
def sweep_drafts(
    draw: st.DrawFn,
    *,
    registered: Sequence[str],
    max_checks: int = 3,
    max_operators: int = 2,
    budget: bool = True,
) -> SweepDraft:
    """A declaration drawn from real registered identifiers.

    ``registered`` is threaded in rather than read here so the caller decides what
    "registered" means -- every test in this family reads it through
    ``gate_fault_injection.registered_ids()``, which is the same list ``registry_gate``
    treats as authoritative. A generated id is therefore registered because it *is*, not
    because it looks the part.

    ``tools`` is drawn independently of ``declared`` so the overlap case is reachable: a
    check that both declares an operator and is listed as a reporting tool is the one case
    where the PASS-eligibility filter has to earn its keep (R1.10).
    """
    declared = tuple(
        draw(
            st.lists(
                st.sampled_from(tuple(registered)), min_size=1, max_size=max_checks, unique=True
            )
        )
    )
    counts = tuple(
        draw(
            st.lists(
                st.integers(min_value=1, max_value=max_operators),
                min_size=len(declared),
                max_size=len(declared),
            )
        )
    )
    tools = tuple(
        draw(st.lists(st.sampled_from(tuple(registered)), max_size=2, unique=True))
    )
    return SweepDraft(
        declared=declared, operator_counts=counts, tools=tools, budget=budget
    )


# ---------------------------------------------------------------------------
# Probe results and gate runs
# ---------------------------------------------------------------------------


def probe_result(
    check: str,
    operator_id: str,
    outcome: gfi.Outcome,
    *,
    detail: str | None = None,
    baseline_exit_code: int | None = 0,
) -> FaultInjectionResult:
    """A probe result whose every field is consistent with the outcome it reports.

    Internal consistency matters even where the classifier is not the subject: a result
    carrying ``outcome="survived"`` with ``applied=False`` is a shape the classifier cannot
    emit, and an aggregation bug could hide behind it.
    """
    applied = outcome != "not-applied"
    timed_out = outcome == "indeterminate"
    exit_code: int | None
    if outcome == "falsified":
        exit_code = 1
    elif outcome == "survived":
        exit_code = 0
    else:
        exit_code = None
    return FaultInjectionResult(
        check=check,
        operator_id=operator_id,
        operator=OperatorKind.DELETE_FILE,
        target=f"{PROBE_DIR}/{check.lower()}.txt",
        expect_names=("NAME_ALPHA",),
        applied=applied,
        exit_code=exit_code,
        non_zero_exit=exit_code not in (0, None),
        names_present=("NAME_ALPHA",) if outcome == "falsified" else (),
        missing_names=() if outcome == "falsified" else ("NAME_ALPHA",),
        baseline_exit_code=baseline_exit_code if applied else None,
        baseline_probed=applied,
        timed_out=timed_out,
        outcome=outcome,
        detail=detail or f"generated {outcome} for {check}/{operator_id}",
    )


def gate_runs(
    check: str,
    *,
    exit_code: int | None,
    timed_out: bool = False,
    output: str = "",
) -> GateRun:
    """One synthesised out-of-process gate execution.

    ``exit_code=None`` with ``timed_out=False`` is the unstartable-process case, which is
    what ``run_gate`` returns on ``OSError``; ``timed_out=True`` always carries
    ``exit_code=None``, because that is what it returns on ``TimeoutExpired``. Both are
    reachable here on purpose: R1.5 requires the three indeterminate conditions to be
    named separately, so all three must be constructible.
    """
    return GateRun(
        check=check,
        command=("synthetic", "launcher", check),
        exit_code=exit_code,
        output=output or f"[--] {check} synthetic gate output",
        timed_out=timed_out,
    )


@contextlib.contextmanager
def patched_sweep(
    results: Sequence[FaultInjectionResult],
) -> Iterator[list[tuple[MutationDeclaration, str | None, str | None, float, bool]]]:
    """Replace the harness's *own* sweep orchestrator, never a gate's evaluator.

    ``sweep`` copies the whole tree and spawns one subprocess per declared check plus one
    per declared operator. Driving the aggregate over generated result sets is the only way
    to quantify over it at zero process cost (I-0), and it substitutes nothing any gate
    owns -- the distinction R9.5 draws is that the harness may be driven while the thing
    being judged may not be replaced.

    The recorded call arguments are yielded so a test can assert what the aggregate asked
    for: the selection arguments in particular, because the unproven-operator rule is
    scoped to a sweep that was asked for everything.
    """
    seen: list[tuple[MutationDeclaration, str | None, str | None, float, bool]] = []

    def fake_sweep(
        declaration: MutationDeclaration,
        *,
        only: str | None = None,
        operator_id: str | None = None,
        timeout: float = gfi.DEFAULT_TIMEOUT_S,
        with_baseline: bool = True,
    ) -> tuple[FaultInjectionResult, ...]:
        seen.append((declaration, only, operator_id, timeout, with_baseline))
        return tuple(results)

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(gfi, "sweep", fake_sweep)
        yield seen
