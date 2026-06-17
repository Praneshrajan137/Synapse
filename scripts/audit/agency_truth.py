"""Make SYNAPSE's *agency* mechanically verifiable (ADR-052).

Sprints 11-19 proved the enforcement boundary; the Substance Mandate proved agent
outputs are real. This gate proves the system is *agentic* — that the perceive → decide
→ act → learn loop actually exists in the source and cannot silently regress to the
request-response pipeline the 2026-06-17 audit found.

Five structural invariants (a regression on any one fails ``--check``):

  * **A. autonomous_trigger** — ``orchestrator/sensor/loop.py`` defines ``SensorLoop`` and
    it calls ``run_consensus`` (the system initiates decisions itself, not only on POST).
  * **B. sensor_wired** — the orchestrator lifespan starts the SensorLoop.
  * **C. standing_world** — ``digital_twin/world/runtime.py`` defines ``WorldRuntime`` with
    ``perceive`` + ``apply_action`` (a world to sense and change).
  * **D. real_actuation** — at least one agent ``execute()`` actuates the world / event-
    sources for real (not a status-dict-only stub).
  * **E. learn_from_world** — the consensus learns from the realized world
    (``world_observer`` / ``_build_learning_outcome``), not the predicted utility.

Plus a **ratchet**: the count of agents whose ``execute()`` is still the
``{"kafka_published": True}`` stub. ``--max-stubs`` defaults to today's count so CI is
green; it ratchets to 0 as the remaining agents are converted (parity with
``substance_truth``/coverage floors).

Run::

    python -m scripts.audit.agency_truth            # human table
    python -m scripts.audit.agency_truth --json
    python -m scripts.audit.agency_truth --check     # exit 1 on a regression
"""

from __future__ import annotations

import ast
import json
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AGENTS_DIR = ROOT / "agents"

# Default ratchet ceiling: agents still on the status-dict-only execute() stub. The
# vertical slice converted inventory_sentinel + supplier_trust; 6 remain (ADR-052).
DEFAULT_MAX_STUBS = 6


@dataclass
class Check:
    name: str
    ok: bool
    detail: str


def _read(rel: str) -> str:
    path = ROOT / rel
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def _structural_checks() -> list[Check]:
    sensor = _read("orchestrator/sensor/loop.py")
    serve = _read("orchestrator/inference/serve.py")
    world = _read("digital_twin/world/runtime.py")
    protocol = _read("orchestrator/consensus/protocol.py")
    return [
        Check(
            "autonomous_trigger",
            "class SensorLoop" in sensor and "run_consensus(" in sensor,
            "SensorLoop convenes run_consensus on its own initiative",
        ),
        Check(
            "sensor_wired",
            "SensorLoop(" in serve and "_sensor_loop" in serve,
            "orchestrator lifespan starts the SensorLoop",
        ),
        Check(
            "standing_world",
            all(s in world for s in ("class WorldRuntime", "def perceive", "def apply_action")),
            "WorldRuntime perceives + is actuated",
        ),
        Check(
            "learn_from_world",
            "world_observer" in protocol and "_build_learning_outcome" in protocol,
            "consensus learns from the realized world, not predicted utility",
        ),
    ]


def _execute_returns_stub(fn: ast.AST) -> bool:
    """True iff a function returns a dict literal with ``kafka_published`` = constant True
    and never actuates (no call to an actuator / producer). That is the old stub shape."""
    if not isinstance(fn, ast.FunctionDef):
        return False
    actuates = False
    stub_return = False
    for node in ast.walk(fn):
        # any apply()/produce() call ⇒ this execute does real work
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in ("apply", "produce")
        ):
            actuates = True
        if isinstance(node, ast.Return) and isinstance(node.value, ast.Dict):
            for key, val in zip(node.value.keys, node.value.values, strict=False):
                if (
                    isinstance(key, ast.Constant)
                    and key.value == "kafka_published"
                    and isinstance(val, ast.Constant)
                    and val.value is True
                ):
                    stub_return = True
    return stub_return and not actuates


def _agent_actuation() -> tuple[list[str], list[str]]:
    """Return (converted_agents, stub_agents) by AST-scanning each handler's execute path."""
    converted: list[str] = []
    stubs: list[str] = []
    for handler in sorted(AGENTS_DIR.glob("*/a2a/handler.py")):
        agent = handler.relative_to(AGENTS_DIR).parts[0]
        src = handler.read_text(encoding="utf-8")
        try:
            tree = ast.parse(src)
        except SyntaxError:
            continue
        is_stub = any(
            _execute_returns_stub(fn)
            for fn in ast.walk(tree)
            if isinstance(fn, ast.FunctionDef)
        )
        # An execute that calls an actuator / kafka producer is converted. Detect via the
        # source markers the slice agents use (real world action / real publish).
        actuates = any(
            marker in src for marker in ("WorldAction", "self._actuator", "self._kafka.produce")
        )
        if is_stub:
            stubs.append(agent)
        elif actuates:
            converted.append(agent)
    return converted, stubs


@dataclass
class Probe:
    ok: bool
    checks: list[Check]
    converted: list[str]
    stubs: list[str]
    max_stubs: int

    @property
    def detail(self) -> str:
        return (
            f"{sum(c.ok for c in self.checks)}/{len(self.checks)} loop invariants; "
            f"{len(self.converted)} agent(s) actuate, {len(self.stubs)} stub(s) "
            f"(ratchet ceiling {self.max_stubs})"
        )


def evaluate(max_stubs: int = DEFAULT_MAX_STUBS) -> Probe:
    """Structured verdict for verify_claims (mirrors doc_truth.evaluate)."""
    checks = _structural_checks()
    converted, stubs = _agent_actuation()
    checks.append(
        Check(
            "real_actuation",
            len(converted) >= 1,
            f"{len(converted)} agent(s) actuate the world: {', '.join(converted) or 'none'}",
        )
    )
    ok = all(c.ok for c in checks) and len(stubs) <= max_stubs
    return Probe(ok=ok, checks=checks, converted=converted, stubs=stubs, max_stubs=max_stubs)


def run(*, as_json: bool = False, check: bool = False, max_stubs: int = DEFAULT_MAX_STUBS) -> int:
    probe = evaluate(max_stubs)
    checks, converted, stubs, ok = probe.checks, probe.converted, probe.stubs, probe.ok

    if as_json:
        print(json.dumps(
            {
                "ok": ok,
                "checks": [c.__dict__ for c in checks],
                "converted_agents": converted,
                "stub_agents": stubs,
                "max_stubs": max_stubs,
            },
            indent=2, sort_keys=True,
        ))
    else:
        for c in checks:
            print(f"[{'OK' if c.ok else 'XX'}] {c.name:<20} {c.detail}")
        print(
            f"\nAgentic loop: {sum(c.ok for c in checks)}/{len(checks)} structural invariants; "
            f"{len(converted)} agent(s) converted, {len(stubs)} stub(s) remaining "
            f"(ratchet ceiling {max_stubs}: {', '.join(stubs) or 'none'})."
        )
        if not ok:
            print("AGENCY REGRESSION: a loop invariant is missing or stubs exceeded the ceiling.")

    if check:
        return 0 if ok else 1
    return 0


if __name__ == "__main__":
    argv = sys.argv[1:]
    max_stubs = DEFAULT_MAX_STUBS
    if "--max-stubs" in argv:
        max_stubs = int(argv[argv.index("--max-stubs") + 1])
    sys.exit(run(as_json="--json" in argv, check="--check" in argv, max_stubs=max_stubs))
