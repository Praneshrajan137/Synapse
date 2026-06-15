"""Make the SYNAPSE *outcome honesty* mechanically enforceable (Sprint 17, ADR-046).

The outcome loop is only worth anything if an outcome is never *fabricated*. A
``confirmed``/``diverged`` outcome must be DERIVED from a realized signal
(execution confirmations, twin divergence); the default, in the absence of
evidence, is ``unknown``. The dishonest shortcut this gate forbids is writing an
outcome RECORD with a hardcoded positive status — e.g. ``{"status": "confirmed"}``
or ``dict(status="diverged")`` — which would let a decision look graded without
any evidence it actually played out.

This AST-walks the outcome-writing modules and flags two anti-patterns:

  * ``fabricated_outcome_dict`` — an ``ast.Dict`` literal with a ``"status"`` key
    whose value is the constant ``"confirmed"`` or ``"diverged"``.
  * ``fabricated_outcome_kwarg`` — a ``status="confirmed"|"diverged"`` keyword
    constant in a call (the ``dict(status=...)`` / constructor shape).

A constant ``"status": "unknown"`` is ALLOWED — that is the honest default. A
``"status": status_variable`` (derived) is ALLOWED. The conditional derivation
inside ``score_decision`` (``"diverged" if ... else "confirmed"``) is a Name/IfExp,
not a constant dict value, so it is correctly not flagged.

Run::

    python -m scripts.audit.outcome_truth            # human table
    python -m scripts.audit.outcome_truth --json      # machine JSON
    python -m scripts.audit.outcome_truth --check      # exit 1 on any violation

Reported via ``verify_claims.py`` (C51). Baseline: 0 violations.
"""

from __future__ import annotations

import ast
import json
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# The modules that produce outcome records. A fabricated positive status in any
# of these would defeat the calibration premise.
TARGETS: tuple[str, ...] = (
    "packages/synapse_common/outcomes.py",
    "data_fabric/jobs/outcome_score.py",
)

_POSITIVE_STATUSES = {"confirmed", "diverged"}


@dataclass
class Violation:
    file: str
    line: int
    kind: str
    detail: str


def _is_positive_status_constant(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and node.value in _POSITIVE_STATUSES:
        return str(node.value)
    return None


def _scan_source(rel: str, src: str) -> list[Violation]:
    violations: list[Violation] = []
    try:
        tree = ast.parse(src)
    except SyntaxError as exc:
        return [Violation(rel, 0, "parse_error", f"could not parse: {exc}")]

    for node in ast.walk(tree):
        # {"status": "confirmed", ...}
        if isinstance(node, ast.Dict):
            for key, value in zip(node.keys, node.values):
                if (
                    isinstance(key, ast.Constant)
                    and key.value == "status"
                    and (status := _is_positive_status_constant(value)) is not None
                ):
                    violations.append(
                        Violation(
                            rel,
                            getattr(value, "lineno", node.lineno),
                            "fabricated_outcome_dict",
                            f'{{"status": "{status}"}} is hardcoded - a positive outcome '
                            f"must be derived from a realized signal, not asserted",
                        )
                    )
        # dict(status="confirmed") / SomeRecord(status="diverged")
        if isinstance(node, ast.Call):
            for kw in node.keywords:
                if kw.arg == "status" and (
                    status := _is_positive_status_constant(kw.value)
                ) is not None:
                    violations.append(
                        Violation(
                            rel,
                            getattr(kw.value, "lineno", node.lineno),
                            "fabricated_outcome_kwarg",
                            f'status="{status}" is a hardcoded keyword - derive it instead',
                        )
                    )
    return violations


def collect() -> list[tuple[str, list[Violation]]]:
    out: list[tuple[str, list[Violation]]] = []
    for rel in TARGETS:
        path = ROOT / rel
        if not path.exists():
            out.append((rel, [Violation(rel, 0, "missing_target", "target file not found")]))
            continue
        src = path.read_text(encoding="utf-8")
        violations = _scan_source(rel, src)
        # Positive check: the honest default MUST exist in the writer modules.
        if "unknown" not in src:
            violations.append(
                Violation(rel, 0, "no_unknown_default", "module never references the honest 'unknown' default")
            )
        out.append((rel, violations))
    return out


def run(*, as_json: bool = False, check: bool = False) -> int:
    reports = collect()
    total = sum(len(v) for _rel, v in reports)

    if as_json:
        payload = {
            "summary": {"targets": len(reports), "total_violations": total},
            "reports": [
                {"file": rel, "violations": [v.__dict__ for v in vs]} for rel, vs in reports
            ],
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        for rel, vs in reports:
            mark = "[XX]" if vs else "[OK]"
            print(f"{mark} {rel}  {len(vs)} violation(s)")
            for v in vs:
                print(f"        {v.file}:{v.line}  {v.kind:<24} {v.detail}")
        print()
        clean = sum(1 for _rel, vs in reports if not vs)
        print(f"Outcome-truth audit: {clean}/{len(reports)} modules clean, {total} violation(s).")

    if check:
        return 1 if total else 0
    return 0


if __name__ == "__main__":
    sys.exit(run(as_json="--json" in sys.argv, check="--check" in sys.argv))
