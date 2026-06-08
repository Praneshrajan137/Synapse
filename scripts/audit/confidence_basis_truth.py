"""Make the SYNAPSE *confidence-basis lie* mechanically visible (ADR-042, C41).

``substance_truth.py`` (C33) catches a *constant* confidence. It cannot catch a
subtler lie: a confidence that is genuinely *derived* but stamped with the wrong
:class:`~synapse_common.provenance.ConfidenceBasis`. ``pricing_oracle`` stamps
``Provenance.real(confidence_basis=CRITIC_VALUE_SPREAD)`` while
``_derive_confidence`` actually computes ``tanh(|elasticity|)`` - an elasticity
strength, not a critic-value spread. ``routing_navigator`` emits **no**
confidence at all. The *declared* basis must equal the *computed* one, or the
audit trail (I-4) and any downstream uncertainty-aware consensus are misled.

This gate has two parts that together pin stamp ↔ computation:

  1. **AST (here):** extract the ``confidence_basis`` literal stamped on every
     ``Provenance.real(...)`` path and compare it against :data:`EXPECTED_BASIS`
     - the maintained ground-truth of what each agent's confidence *actually*
     represents (determined by reading the derivation). A disagreement is
     ``basis_mismatch``; an agent that should stamp a basis but emits none is
     ``basis_missing``.
  2. **Runtime (per-agent tests):** each agent's test asserts the confidence
     value *moves with* its uncertainty input (e.g. wider conformal interval ->
     lower confidence). That closes the table ↔ computation half.

Updating :data:`EXPECTED_BASIS` for an agent requires changing both the stamp in
code and the entry here in the same PR - code review keeps the table honest, the
gate keeps the stamp honest, the runtime test keeps the computation honest.

Run::

    python -m scripts.audit.confidence_basis_truth [--json|--check]
"""

from __future__ import annotations

import ast
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AGENTS_DIR = ROOT / "agents"

# Ground-truth basis per agent - the enum member name the agent SHOULD stamp,
# given what its confidence computation actually measures. ``None`` means "not
# yet adjudicated" (added in that agent's ratchet PR; not a violation meanwhile).
# Entries here are asserted; a stamp that disagrees is a violation.
EXPECTED_BASIS: dict[str, str | None] = {
    "demand_prophet": "CONFORMAL_INTERVAL",     # 1/(1+rel_width) over conformal PIs [ok]
    "supplier_trust": "POSTERIOR_SPREAD",        # 1/(1+posterior.std) [ok]
    "pricing_oracle": "ELASTICITY_STRENGTH",     # tanh(|elasticity|) - NOT critic spread
    "routing_navigator": "OPTIMALITY_GAP",       # solver optimality-gap percentile
    "disruption_shield": "ANOMALY_SCORE_MARGIN",  # |score − threshold| decisiveness (Phase 7)
    "freshness_guardian": "SURVIVAL_CI_WIDTH",     # 1/(1+rel CI width) of the Weibull life (Phase 7)
    "sustainability_agent": "PREDICTIVE_ENTROPY",  # 1 − H(waste_prob) (Phase 7; was mislabelled)
    "inventory_sentinel": "RESIDUAL_VARIANCE",     # 1 − forecast volatility, conformal-calibrated
}

# Phase 4 closed both known mismatches: pricing_oracle now stamps ELASTICITY_STRENGTH
# (matching its tanh(|elasticity|) computation) and routing_navigator emits a real
# OPTIMALITY_GAP confidence. All adjudicated agents agree stamp == computation.
BASELINE = 0


@dataclass
class Violation:
    agent: str
    file: str
    line: int
    kind: str  # basis_mismatch | basis_missing
    detail: str


@dataclass
class AgentReport:
    agent: str
    file: str
    stamped: list[str] = field(default_factory=list)  # basis enum names stamped on real paths
    violations: list[Violation] = field(default_factory=list)


def _basis_arg_name(call: ast.Call) -> tuple[str | None, int]:
    """For ``Provenance.real(confidence_basis=ConfidenceBasis.X)`` return ('X', lineno)."""
    for kw in call.keywords:
        if kw.arg == "confidence_basis":
            v = kw.value
            if isinstance(v, ast.Attribute):  # ConfidenceBasis.X
                return v.attr, getattr(call, "lineno", 0)
            if isinstance(v, ast.Name):
                return v.id, getattr(call, "lineno", 0)
    return None, getattr(call, "lineno", 0)


def _is_provenance_real(call: ast.Call) -> bool:
    func = call.func
    return isinstance(func, ast.Attribute) and func.attr == "real" and (
        isinstance(func.value, ast.Name) and func.value.id == "Provenance"
    )


def scan_pipeline(path: Path) -> AgentReport:
    agent = path.relative_to(AGENTS_DIR).parts[0]
    rel = path.relative_to(ROOT).as_posix()
    report = AgentReport(agent=agent, file=rel)
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError, UnicodeDecodeError) as exc:
        report.violations.append(Violation(agent, rel, 0, "parse_error", str(exc)))
        return report

    expected = EXPECTED_BASIS.get(agent)
    stamp_lines: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and _is_provenance_real(node):
            name, ln = _basis_arg_name(node)
            if name is not None:
                report.stamped.append(name)
                stamp_lines.append((name, ln))

    if expected is None:
        return report  # not yet adjudicated - informational

    if not stamp_lines:
        report.violations.append(
            Violation(
                agent, rel, 0, "basis_missing",
                f"expects confidence_basis={expected} on the real path but the pipeline "
                "stamps no Provenance.real(confidence_basis=...) (or emits no confidence)",
            )
        )
        return report

    for name, ln in stamp_lines:
        if name != expected:
            report.violations.append(
                Violation(
                    agent, rel, ln, "basis_mismatch",
                    f"stamps ConfidenceBasis.{name} but the confidence is actually a "
                    f"{expected} (declared basis != computed basis)",
                )
            )
    return report


def collect() -> list[AgentReport]:
    return [scan_pipeline(p) for p in sorted(AGENTS_DIR.glob("*/inference/pipeline.py"))]


def run(*, as_json: bool = False, check: bool = False) -> int:
    reports = collect()
    total = sum(len(r.violations) for r in reports)

    if as_json:
        payload = {
            "summary": {
                "agents_scanned": len(reports),
                "total_violations": total,
                "baseline": BASELINE,
                "regression": total > BASELINE,
            },
            "reports": [
                {
                    "agent": r.agent,
                    "file": r.file,
                    "stamped": r.stamped,
                    "expected": EXPECTED_BASIS.get(r.agent),
                    "violations": [v.__dict__ for v in r.violations],
                }
                for r in reports
            ],
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        for r in reports:
            mark = "[XX]" if r.violations else "[OK]"
            exp = EXPECTED_BASIS.get(r.agent) or "(unadjudicated)"
            stamp = ",".join(r.stamped) or "(none)"
            print(f"{mark} {r.agent:<22} stamped={stamp:<22} expected={exp}")
            for v in r.violations:
                print(f"        {v.file}:{v.line}  {v.kind:<16} {v.detail}")
        print()
        print(f"Confidence-basis-truth: {total} violation(s) (baseline {BASELINE}).")
        if total and not check:
            print("(ratchet - drive to 0 in Phase 4/5; CI fails on any increase.)")

    if check:
        return 1 if total > BASELINE else 0
    return 0


if __name__ == "__main__":
    sys.exit(run(as_json="--json" in sys.argv, check="--check" in sys.argv))
