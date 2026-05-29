"""Make the SYNAPSE *substance gap* mechanically visible (Plan v2, Phase 0).

The enforcement boundary (Sprints 11-13) proves that agent outputs satisfy
their schema, postconditions, latency SLA, and price caps. It does NOT prove
the outputs are *real*. Today every ``agents/*/inference/pipeline.py`` returns
synthetic features and fallback predictions **unconditionally** — the
``if self._dep is None:`` guard logs a warning, then the next line returns the
fallback regardless of whether a real model / Feast / Neo4j was injected.

This script AST-walks each agent inference pipeline and flags three anti-patterns:

  * ``ignored_dependency`` — a method guards ``if self._<dep> is None:`` and then
    returns the *same* fallback on the path where the dependency IS present
    (the "guard-then-ignore" shape). Detected two ways: a fallback-named return
    that is a sibling of (executes after) the None-guard, or a None-guard whose
    body has no ``return`` while the function falls through to a constant/empty
    container literal.
  * ``hardcoded_confidence`` — a numeric ``confidence=<literal>`` keyword argument
    in output construction. Confidence MUST be derived from model uncertainty
    (ADR-040), never a constant — a constant 0.85 makes I-5 (confidence-gated
    HITL escalation) impossible to ever fire.
  * ``random_model_input`` — ``np.random`` / ``default_rng`` / ``standard_normal``
    / ``torch.rand*`` used inside a non-fallback method (e.g. ``_build_observations``),
    i.e. the tensor fed to the model is noise, not derived from real features.

Run::

    python -m scripts.audit.substance_truth            # human table
    python -m scripts.audit.substance_truth --json      # machine JSON
    python -m scripts.audit.substance_truth --check      # exit 1 on any violation

Phase 0: this is informational (flags today's gaps). Phase 4 wires ``--check``
as a blocking CI gate; by then Phase 2 has driven the count to zero, so any
regression to a synthetic shortcut fails CI. Reported via ``verify_claims.py``
(C33).
"""

from __future__ import annotations

import ast
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AGENTS_DIR = ROOT / "agents"

# Method/return names that legitimately denote a degraded fallback path. A
# return of one of these is fine *inside* a None-guard; it is a violation only
# when reachable while the dependency is present.
_FALLBACK_NAME_RE = re.compile(
    r"(synthetic|fallback|heuristic|rule_based|coldstart|baseline|_ema)", re.IGNORECASE
)
# RNG calls that, outside a fallback method, mean the model is fed noise.
_RNG_ATTR_RE = re.compile(
    r"(default_rng|standard_normal|randn|rand|normal|uniform|choice|random)", re.IGNORECASE
)


@dataclass
class Violation:
    agent: str
    file: str
    line: int
    kind: str  # ignored_dependency | hardcoded_confidence | random_model_input
    detail: str


@dataclass
class AgentReport:
    agent: str
    file: str
    violations: list[Violation] = field(default_factory=list)


def _is_fallback_name(name: str | None) -> bool:
    return bool(name) and bool(_FALLBACK_NAME_RE.search(name or ""))


def _called_self_method_name(node: ast.AST) -> str | None:
    """If ``node`` is ``self._foo(...)``, return ``_foo``; else None."""
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
        target = node.func.value
        if isinstance(target, ast.Name) and target.id == "self":
            return node.func.attr
    return None


def _is_none_guard(node: ast.stmt) -> str | None:
    """If ``node`` is ``if self._<dep> is None:`` return the dep attr name."""
    if not isinstance(node, ast.If):
        return None
    test = node.test
    if (
        isinstance(test, ast.Compare)
        and len(test.ops) == 1
        and isinstance(test.ops[0], ast.Is)
        and len(test.comparators) == 1
        and isinstance(test.comparators[0], ast.Constant)
        and test.comparators[0].value is None
    ):
        left = test.left
        if isinstance(left, ast.Attribute) and isinstance(left.value, ast.Name):
            if left.value.id == "self":
                return left.attr
    return None


def _is_empty_container_literal(node: ast.AST) -> bool:
    """True for ``{}``, ``[]``, ``{"a": {}, "b": []}`` — placeholder returns."""
    if isinstance(node, ast.Dict):
        if not node.values:
            return True
        return all(_is_empty_container_literal(v) for v in node.values)
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        return all(_is_empty_container_literal(e) for e in node.elts) if node.elts else True
    return False


def _body_has_return(stmts: list[ast.stmt]) -> bool:
    return any(isinstance(n, ast.Return) for s in stmts for n in ast.walk(s))


def _scan_function(
    fn: ast.FunctionDef, agent: str, rel: str
) -> list[Violation]:
    violations: list[Violation] = []
    is_fallback_method = _is_fallback_name(fn.name)

    # --- ignored_dependency -------------------------------------------------
    guard_deps: list[str] = []
    guard_returns_inside: set[int] = set()  # line numbers of returns inside guards
    for stmt in ast.walk(fn):
        dep = _is_none_guard(stmt)
        if dep is not None:
            guard_deps.append(dep)
            assert isinstance(stmt, ast.If)
            for inner in stmt.body:
                for n in ast.walk(inner):
                    if isinstance(n, ast.Return):
                        guard_returns_inside.add(n.lineno)

    if guard_deps:
        # Top-level (sibling) statements of the function body — these run when
        # the guard's condition is False, i.e. the dependency IS present.
        guard_if_nodes = [s for s in fn.body if _is_none_guard(s) is not None]
        for stmt in fn.body:
            if isinstance(stmt, ast.Return) and stmt.value is not None:
                called = _called_self_method_name(stmt.value)
                if _is_fallback_name(called):
                    violations.append(
                        Violation(
                            agent, rel, stmt.lineno, "ignored_dependency",
                            f"{fn.name}() returns fallback self.{called}() even when "
                            f"self.{guard_deps[0]} is present",
                        )
                    )
                elif _is_empty_container_literal(stmt.value):
                    violations.append(
                        Violation(
                            agent, rel, stmt.lineno, "ignored_dependency",
                            f"{fn.name}() returns an empty placeholder literal even when "
                            f"self.{guard_deps[0]} is present",
                        )
                    )
        # Cosmetic guard: a None-guard whose body has no return (just logging)
        # — the dependency is checked but never acted upon.
        for gif in guard_if_nodes:
            assert isinstance(gif, ast.If)
            if not _body_has_return(gif.body) and not any(
                isinstance(n, ast.Raise) for s in gif.body for n in ast.walk(s)
            ):
                dep = _is_none_guard(gif)
                violations.append(
                    Violation(
                        agent, rel, gif.lineno, "ignored_dependency",
                        f"{fn.name}() guards self.{dep} is None but the branch only "
                        f"logs - behaviour does not change when the dependency is absent",
                    )
                )

    # --- hardcoded_confidence ----------------------------------------------
    for node in ast.walk(fn):
        if isinstance(node, ast.Call):
            for kw in node.keywords:
                if (
                    kw.arg == "confidence"
                    and isinstance(kw.value, ast.Constant)
                    and isinstance(kw.value.value, (int, float))
                    and not isinstance(kw.value.value, bool)
                ):
                    violations.append(
                        Violation(
                            agent, rel, node.lineno, "hardcoded_confidence",
                            f"confidence={kw.value.value!r} is a constant - derive it from "
                            f"model uncertainty (ADR-040); a constant disables I-5",
                        )
                    )

    # --- random_model_input -------------------------------------------------
    if not is_fallback_method:
        for node in ast.walk(fn):
            if isinstance(node, ast.Attribute) and _RNG_ATTR_RE.fullmatch(node.attr or ""):
                # Only count attribute accesses chained on np.random / a rng / torch.
                violations.append(
                    Violation(
                        agent, rel, getattr(node, "lineno", fn.lineno), "random_model_input",
                        f"{fn.name}() uses .{node.attr}() - model input/observation is "
                        f"random noise, not derived from real features",
                    )
                )
                break  # one per method is enough signal

    return violations


def scan_pipeline(path: Path) -> AgentReport:
    agent = path.relative_to(AGENTS_DIR).parts[0]
    rel = path.relative_to(ROOT).as_posix()
    report = AgentReport(agent=agent, file=rel)
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError, UnicodeDecodeError) as exc:
        report.violations.append(
            Violation(agent, rel, 0, "parse_error", f"could not parse: {exc}")
        )
        return report
    for cls in (n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)):
        for fn in (n for n in cls.body if isinstance(n, ast.FunctionDef)):
            report.violations.extend(_scan_function(fn, agent, rel))
    return report


def collect() -> list[AgentReport]:
    reports: list[AgentReport] = []
    for pipeline in sorted(AGENTS_DIR.glob("*/inference/pipeline.py")):
        reports.append(scan_pipeline(pipeline))
    return reports


def run(*, as_json: bool = False, check: bool = False) -> int:
    reports = collect()
    total = sum(len(r.violations) for r in reports)

    if as_json:
        payload = {
            "summary": {
                "agents_scanned": len(reports),
                "agents_with_violations": sum(1 for r in reports if r.violations),
                "total_violations": total,
            },
            "reports": [
                {
                    "agent": r.agent,
                    "file": r.file,
                    "violations": [v.__dict__ for v in r.violations],
                }
                for r in reports
            ],
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        for r in reports:
            mark = "[XX]" if r.violations else "[OK]"
            print(f"{mark} {r.agent:<22} {len(r.violations)} violation(s)  {r.file}")
            for v in r.violations:
                print(f"        {v.file}:{v.line}  {v.kind:<20} {v.detail}")
        print()
        clean = sum(1 for r in reports if not r.violations)
        print(
            f"Substance audit: {clean}/{len(reports)} agents clean, "
            f"{total} total violation(s) across {len(reports)} pipelines."
        )
        if total and not check:
            print("(informational - Phase 0. Phase 4 wires --check as a blocking gate.)")

    if check:
        return 1 if total else 0
    return 0


if __name__ == "__main__":
    sys.exit(run(as_json="--json" in sys.argv, check="--check" in sys.argv))
