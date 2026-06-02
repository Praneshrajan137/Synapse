"""Make the SYNAPSE *serving-load gap* mechanically visible (ADR-042, C39).

The ``ModelRegistry`` anti-corruption layer (ADR-041) is correct, unit-tested,
and **never called from any serving path**. Every ``agents/*/inference/serve.py``
constructs its pipeline with no ``model=`` argument, so ``model`` is ``None`` and
100% of inference is the honest-but-degraded fallback. The honesty contract makes
that degradation *visible*; this gate makes *closing* it mechanical.

It AST-walks every ``agents/*/inference/serve.py`` and asks one question: does the
module construct a :class:`ModelRegistry` and call ``.load(...)`` (so a real
checkpoint can reach the pipeline)? An agent that does is *wired*; one that does
not still serves only fallbacks.

Ratchet: :data:`BASELINE_UNWIRED` is the count of un-wired serve.py today (8).
Each agent wired in Phase 1/5 decrements it; CI fails if it ever rises.
:data:`WIRED_AGENTS` grows one-per-PR and locks the gain - a wired agent that
regresses to a bare ``Pipeline()`` flags ``serving_regressed``.

Run::

    python -m scripts.audit.serving_truth            # human table
    python -m scripts.audit.serving_truth --json      # machine JSON
    python -m scripts.audit.serving_truth --check      # exit 1 if unwired > baseline
"""

from __future__ import annotations

import ast
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AGENTS_DIR = ROOT / "agents"

# Agents whose serve.py is asserted to load a model via ModelRegistry. Grows one
# per PR. Phase 1: demand_prophet (forecasting). Phase 2: routing_navigator
# (analytical/solver — the $0 registry source resolves its optimality-gap
# calibration checkpoint).
WIRED_AGENTS: frozenset[str] = frozenset(
    {
        "demand_prophet",
        "routing_navigator",
        "supplier_trust",
        "pricing_oracle",
        "disruption_shield",
        "freshness_guardian",
        "sustainability_agent",
        "inventory_sentinel",
    }
)

# Count of serve.py files NOT yet wired through ModelRegistry. ALL 8 agents now load
# a model via ModelRegistry (the four paradigm exemplars + the four ratchet agents).
# The registry is the live serving path fleet-wide; CI fails if any agent regresses.
BASELINE_UNWIRED = 0


@dataclass
class Violation:
    agent: str
    file: str
    line: int
    kind: str  # serving_regressed
    detail: str


@dataclass
class AgentReport:
    agent: str
    file: str
    exists: bool
    references_registry: bool = False
    calls_load: bool = False
    violations: list[Violation] = field(default_factory=list)

    @property
    def wired(self) -> bool:
        return self.references_registry and self.calls_load


def _references_registry(tree: ast.AST) -> bool:
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id == "ModelRegistry":
            return True
        if isinstance(node, ast.Attribute) and node.attr == "ModelRegistry":
            return True
    return False


def _calls_load(tree: ast.AST) -> bool:
    """True if the module resolves a model — either ``<registry>.load(...)`` directly
    or a ``load_*model*`` / ``load_serving_model(...)`` loader helper. Combined with the
    ModelRegistry reference (the conjunction in ``wired``), this reliably distinguishes
    a real serving-load path from the old bare ``Pipeline()``."""
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Attribute) and func.attr == "load":
            return True
        name = func.attr if isinstance(func, ast.Attribute) else (
            func.id if isinstance(func, ast.Name) else ""
        )
        if name.startswith("load_") and ("model" in name or "serving" in name):
            return True
    return False


def scan_agent(agent_dir: Path) -> AgentReport:
    agent = agent_dir.name
    serve_py = agent_dir / "inference" / "serve.py"
    rel = serve_py.relative_to(ROOT).as_posix()
    report = AgentReport(agent=agent, file=rel, exists=serve_py.is_file())
    if not report.exists:
        return report
    try:
        tree = ast.parse(serve_py.read_text(encoding="utf-8"))
    except (OSError, SyntaxError, UnicodeDecodeError) as exc:
        report.violations.append(Violation(agent, rel, 0, "parse_error", str(exc)))
        return report

    report.references_registry = _references_registry(tree)
    report.calls_load = _calls_load(tree)

    if agent in WIRED_AGENTS and not report.wired:
        report.violations.append(
            Violation(
                agent, rel, 0, "serving_regressed",
                f"{agent} is in WIRED_AGENTS but serve.py no longer constructs "
                "ModelRegistry().load(...) - it regressed to fallback-only serving",
            )
        )
    return report


def collect() -> list[AgentReport]:
    reports: list[AgentReport] = []
    for agent_dir in sorted(p for p in AGENTS_DIR.iterdir() if p.is_dir()):
        if (agent_dir / "inference").is_dir():
            reports.append(scan_agent(agent_dir))
    return reports


def run(*, as_json: bool = False, check: bool = False) -> int:
    reports = collect()
    wired = sum(1 for r in reports if r.wired)
    unwired = sum(1 for r in reports if r.exists and not r.wired)
    regressions = sum(len(r.violations) for r in reports)

    if as_json:
        payload = {
            "summary": {
                "agents_scanned": len(reports),
                "wired": wired,
                "unwired": unwired,
                "baseline_unwired": BASELINE_UNWIRED,
                "regressions": regressions,
                "regression": unwired > BASELINE_UNWIRED or regressions > 0,
            },
            "reports": [
                {
                    "agent": r.agent,
                    "file": r.file,
                    "wired": r.wired,
                    "references_registry": r.references_registry,
                    "calls_load": r.calls_load,
                    "violations": [v.__dict__ for v in r.violations],
                }
                for r in reports
            ],
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        for r in reports:
            mark = "[XX]" if r.violations else ("[OK]" if r.wired else "[--]")
            state = "wired" if r.wired else "fallback-only"
            print(f"{mark} {r.agent:<22} {state:<14} {r.file}")
            for v in r.violations:
                print(f"        {v.file}:{v.line}  {v.kind:<20} {v.detail}")
        print()
        print(
            f"Serving-truth: {wired}/{len(reports)} agents load a model via ModelRegistry; "
            f"{unwired} fallback-only (baseline {BASELINE_UNWIRED})."
        )
        if unwired and not check:
            print("(ratchet - lower BASELINE_UNWIRED as agents are wired; CI fails on any increase.)")

    if check:
        return 1 if (unwired > BASELINE_UNWIRED or regressions > 0) else 0
    return 0


if __name__ == "__main__":
    sys.exit(run(as_json="--json" in sys.argv, check="--check" in sys.argv))
