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

A sixth, independently-verifiable signal — **binding_arbitration** — AST-asserts that the
full-path ratified action is chosen by the Pareto-knee ``select_binding_action`` and *not*
by a raw ``argmax`` over ``utility_score`` (ADR-052 / Requirements 9.1).

Plus a **ratchet**: the count of agents whose ``execute()`` is still the
``{"kafka_published": True}`` stub. ``--max-stubs`` defaults to 0 — every agent is now
converted to real actuation or an Honest No-Op — so any regression to the status-dict stub
fails the gate (parity with ``substance_truth``/coverage floors).

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
# broaden-to-8 work converted every agent to real actuation or an Honest No-Op, so the
# ceiling is now 0 and may only stay at 0 (R8.2/R8.5; ADR-052).
DEFAULT_MAX_STUBS = 0

# The five structural loop invariants the gate enforces in --check (R8.7). The
# binding-arbitration signal (R9.1) is an additional, independently-verifiable check.
STRUCTURAL_INVARIANTS = (
    "autonomous_trigger",
    "sensor_wired",
    "standing_world",
    "learn_from_world",
    "real_actuation",
)


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


def _find_function(
    tree: ast.AST, name: str
) -> ast.FunctionDef | ast.AsyncFunctionDef | None:
    """Return the first (async or sync) function definition named ``name``."""
    for node in ast.walk(tree):
        if (
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == name
        ):
            return node
    return None


def _call_name(call: ast.Call) -> str | None:
    """The simple callee name of a call (``foo`` for ``foo()`` / ``x.foo()``)."""
    func = call.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def _references_symbol(tree: ast.AST, name: str) -> bool:
    """True iff ``name`` is referenced anywhere as an identifier or import alias."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id == name:
            return True
        if isinstance(node, ast.alias) and node.name == name:
            return True
    return False


def _references_name(node: ast.AST, name: str) -> bool:
    """True iff ``name`` is referenced as an identifier within ``node``."""
    return any(isinstance(n, ast.Name) and n.id == name for n in ast.walk(node))


def _calls_with_keyword(node: ast.AST, callee: str, keyword: str) -> bool:
    """True iff ``node`` contains a call to ``callee`` passing keyword ``keyword``."""
    for n in ast.walk(node):
        if (
            isinstance(n, ast.Call)
            and _call_name(n) == callee
            and any(kw.arg == keyword for kw in n.keywords)
        ):
            return True
    return False


def _has_max_with_key(node: ast.AST) -> bool:
    """True iff ``node`` contains a ``max(..., key=...)`` argmax expression."""
    for n in ast.walk(node):
        if (
            isinstance(n, ast.Call)
            and isinstance(n.func, ast.Name)
            and n.func.id == "max"
            and any(kw.arg == "key" for kw in n.keywords)
        ):
            return True
    return False


def _binding_arbitration_check() -> Check:
    """R9.1: distinguish binding Pareto-knee arbitration from raw ``argmax``.

    AST-parse ``orchestrator/consensus/protocol.py`` and assert all of:
      (a) ``select_binding_action`` is referenced (imported/called) in protocol.py;
      (b) the ``_full_path`` function reaches binding selection — it calls
          ``select_binding_action`` and/or invokes ``_build_decision`` with a
          ``selection=`` keyword;
      (c) the ``_build_decision`` function contains NO ``max(..., key=...)`` call —
          the raw ``utility_score`` argmax no longer drives full-path selection (it may
          remain only on the Tier-1/2 fast path).
    The check is a deterministic, structural signal that is ``ok`` iff (a) ∧ (b) ∧ (c).
    """
    src = _read("orchestrator/consensus/protocol.py")
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return Check("binding_arbitration", False, "protocol.py failed to parse")

    referenced = _references_symbol(tree, "select_binding_action")

    full_path = _find_function(tree, "_full_path")
    reaches = full_path is not None and (
        _references_name(full_path, "select_binding_action")
        or _calls_with_keyword(full_path, "_build_decision", "selection")
    )

    build_decision = _find_function(tree, "_build_decision")
    no_argmax = build_decision is not None and not _has_max_with_key(build_decision)

    ok = referenced and reaches and no_argmax
    if ok:
        detail = (
            "full path selects via select_binding_action (knee-weighted); "
            "_build_decision has no raw argmax"
        )
    else:
        detail = (
            f"binding wiring incomplete: referenced={referenced}, "
            f"full_path_reaches_binding={reaches}, build_decision_no_argmax={no_argmax}"
        )
    return Check("binding_arbitration", ok, detail)


@dataclass
class Probe:
    ok: bool
    checks: list[Check]
    converted: list[str]
    stubs: list[str]
    max_stubs: int
    converted_count: int
    binding: Check

    @property
    def detail(self) -> str:
        structural = [c for c in self.checks if c.name in STRUCTURAL_INVARIANTS]
        return (
            f"{sum(c.ok for c in structural)}/{len(structural)} loop invariants; "
            f"binding_arbitration={'ok' if self.binding.ok else 'FAIL'}; "
            f"{self.converted_count} agent(s) actuate, {len(self.stubs)} stub(s) "
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
    # R9.1: binding-arbitration signal, exposed as a Check so it contributes to ok and
    # the --json checks[]. Independent of the actuation count below (R9.2).
    binding = _binding_arbitration_check()
    checks.append(binding)
    # R9.2: integer actuation count in 0..8, computed from the per-agent converted/stub
    # classification — independently of the binding-arbitration check.
    converted_count = len(converted)
    ok = all(c.ok for c in checks) and len(stubs) <= max_stubs
    return Probe(
        ok=ok,
        checks=checks,
        converted=converted,
        stubs=stubs,
        max_stubs=max_stubs,
        converted_count=converted_count,
        binding=binding,
    )


def run(*, as_json: bool = False, check: bool = False, max_stubs: int = DEFAULT_MAX_STUBS) -> int:
    probe = evaluate(max_stubs)
    checks, converted, stubs, ok = probe.checks, probe.converted, probe.stubs, probe.ok

    if as_json:
        print(json.dumps(
            {
                "ok": ok,
                "checks": [c.__dict__ for c in checks],
                "binding_arbitration": probe.binding.__dict__,
                "converted_agents": converted,
                "converted_count": probe.converted_count,
                "stub_agents": stubs,
                "max_stubs": max_stubs,
            },
            indent=2, sort_keys=True,
        ))
    else:
        for c in checks:
            print(f"[{'OK' if c.ok else 'XX'}] {c.name:<20} {c.detail}")
        structural = [c for c in checks if c.name in STRUCTURAL_INVARIANTS]
        print(
            f"\nAgentic loop: {sum(c.ok for c in structural)}/{len(structural)} structural "
            f"invariants; binding_arbitration={'ok' if probe.binding.ok else 'FAIL'}; "
            f"{probe.converted_count} agent(s) converted, {len(stubs)} stub(s) remaining "
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
