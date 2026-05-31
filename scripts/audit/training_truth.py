"""Make the SYNAPSE *training gap* mechanically visible (ADR-042, C37).

``substance_truth.py`` (C33) proved the *inference* path no longer takes the
guard-then-ignore / hardcoded-confidence shortcuts. It cannot see the deeper
lie: that **no model is ever trained**. ``demand_prophet/training/train.py``
builds an ``AdamW`` + cosine scheduler, discards both, takes zero gradient
steps, and returns ``{"status": "pipeline_validated"}`` - the literal string
that was the lie. The other agents have no ``train.py`` at all.

This script AST-walks every ``agents/*/training/train.py`` and flags:

  * ``hollow_loop`` - a training entrypoint that constructs an optimizer
    (``Adam``/``AdamW``/``SGD``/``torch.optim.*``) but the module never calls
    ``.step()`` / ``.backward()`` anywhere, OR returns a ``pipeline_validated``
    sentinel. This is the active lie and must reach zero.
  * ``missing_step`` - for an agent that has *committed* to a real gradient loop
    (member of :data:`REAL_LOOP_AGENTS`, grown one-per-PR), its ``train.py`` must
    contain a genuine optimization step. A regression flags here.

The ``pipeline_validated`` string is flagged **everywhere, always** - it must
never reappear in the repo.

Run::

    python -m scripts.audit.training_truth            # human table
    python -m scripts.audit.training_truth --json      # machine JSON
    python -m scripts.audit.training_truth --check      # exit 1 if violations > baseline

Ratchet: :data:`BASELINE` is the measured count today (the one ``demand_prophet``
hollow loop). Phase 1 rewrites that loop → 0; the baseline ratchets down and any
new hollow loop fails CI. ``REAL_LOOP_AGENTS`` grows as each agent lands a real
loop, locking in the gain (parity with C33's 10→0 ratchet).
"""

from __future__ import annotations

import ast
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AGENTS_DIR = ROOT / "agents"

# Agents whose train.py is asserted to contain a real gradient loop. Grows one
# per PR as Phase 1/5 land. Phase 1: demand_prophet's loop is real.
REAL_LOOP_AGENTS: frozenset[str] = frozenset({"demand_prophet"})

# Violation count ceiling. Phase 1 drove demand_prophet's two violations
# (pipeline_validated sentinel + hollow optimizer) to zero by giving it a real
# CRPS loop. CI fails on any increase; the remaining 7 agents have no train.py
# yet (not a violation — they ratchet in one PR each).
BASELINE = 0

_PIPELINE_VALIDATED = "pipeline_validated"
_OPTIMIZER_NAMES = {"Adam", "AdamW", "SGD", "RMSprop", "Adagrad", "Adadelta", "NAdam"}
# Calls that constitute a genuine optimization / fit step.
_STEP_ATTRS = {"step", "backward", "fit", "partial_fit", "learn", "update"}


@dataclass
class Violation:
    agent: str
    file: str
    line: int
    kind: str  # hollow_loop | missing_step | pipeline_validated
    detail: str


@dataclass
class AgentReport:
    agent: str
    file: str
    exists: bool
    has_real_step: bool = False
    violations: list[Violation] = field(default_factory=list)


def _constructs_optimizer(tree: ast.AST) -> bool:
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            # torch.optim.AdamW(...)
            if isinstance(func, ast.Attribute) and func.attr in _OPTIMIZER_NAMES:
                return True
            # AdamW(...) imported directly
            if isinstance(func, ast.Name) and func.id in _OPTIMIZER_NAMES:
                return True
    return False


def _has_real_step(tree: ast.AST) -> bool:
    # ``env.step`` counts as a real step for RL training; ``.fit`` / ``.backward``
    # are unambiguous optimization calls.
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in _STEP_ATTRS
        ):
            return True
    return False


def _returns_pipeline_validated(tree: ast.AST) -> list[int]:
    lines: list[int] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and node.value == _PIPELINE_VALIDATED:
            lines.append(getattr(node, "lineno", 0))
    return lines


def scan_agent(agent_dir: Path) -> AgentReport:
    agent = agent_dir.name
    train_py = agent_dir / "training" / "train.py"
    rel = train_py.relative_to(ROOT).as_posix()
    report = AgentReport(agent=agent, file=rel, exists=train_py.is_file())

    if not report.exists:
        return report

    try:
        tree = ast.parse(train_py.read_text(encoding="utf-8"))
    except (OSError, SyntaxError, UnicodeDecodeError) as exc:
        report.violations.append(Violation(agent, rel, 0, "parse_error", str(exc)))
        return report

    report.has_real_step = _has_real_step(tree)
    constructs_opt = _constructs_optimizer(tree)

    # pipeline_validated is flagged everywhere, always.
    for ln in _returns_pipeline_validated(tree):
        report.violations.append(
            Violation(
                agent, rel, ln, "pipeline_validated",
                "returns the 'pipeline_validated' sentinel - the no-op-training lie (ADR-042)",
            )
        )

    # hollow_loop: builds an optimizer but never steps it.
    if constructs_opt and not report.has_real_step:
        report.violations.append(
            Violation(
                agent, rel, 0, "hollow_loop",
                "constructs an optimizer but never calls .step()/.backward() - "
                "zero gradient steps are taken",
            )
        )

    # missing_step: a committed real-loop agent must have a genuine step.
    if agent in REAL_LOOP_AGENTS and not report.has_real_step:
        report.violations.append(
            Violation(
                agent, rel, 0, "missing_step",
                f"{agent} is in REAL_LOOP_AGENTS but train.py has no optimization step "
                "(regression)",
            )
        )

    return report


def collect() -> list[AgentReport]:
    reports: list[AgentReport] = []
    for agent_dir in sorted(p for p in AGENTS_DIR.iterdir() if p.is_dir()):
        if (agent_dir / "training").is_dir():
            reports.append(scan_agent(agent_dir))
    return reports


def run(*, as_json: bool = False, check: bool = False) -> int:
    reports = collect()
    total = sum(len(r.violations) for r in reports)
    real = sum(1 for r in reports if r.has_real_step)

    if as_json:
        payload = {
            "summary": {
                "agents_scanned": len(reports),
                "agents_with_real_loop": real,
                "total_violations": total,
                "baseline": BASELINE,
                "regression": total > BASELINE,
            },
            "reports": [
                {
                    "agent": r.agent,
                    "file": r.file,
                    "exists": r.exists,
                    "has_real_step": r.has_real_step,
                    "violations": [v.__dict__ for v in r.violations],
                }
                for r in reports
            ],
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        for r in reports:
            mark = "[XX]" if r.violations else ("[OK]" if r.has_real_step else "[--]")
            state = "real-loop" if r.has_real_step else ("hollow" if r.exists else "no-train.py")
            print(f"{mark} {r.agent:<22} {state:<12} {r.file}")
            for v in r.violations:
                print(f"        {v.file}:{v.line}  {v.kind:<20} {v.detail}")
        print()
        print(
            f"Training-truth: {real}/{len(reports)} agents have a real gradient loop; "
            f"{total} violation(s) (baseline {BASELINE})."
        )
        if total and not check:
            print("(ratchet - lower BASELINE as loops land; CI fails on any increase.)")

    if check:
        return 1 if total > BASELINE else 0
    return 0


if __name__ == "__main__":
    sys.exit(run(as_json="--json" in sys.argv, check="--check" in sys.argv))
