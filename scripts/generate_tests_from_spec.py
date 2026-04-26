#!/usr/bin/env python3
"""SYNAPSE SDD — generate ``test_spec.py`` from a per-agent ``spec.yaml``.

The generator emits three classes of test:

1. **State machine transitions** — fully real assertions exercised against the
   agent's own ``StateMachine`` subclass. Every transition listed in the spec
   becomes a green test as soon as the FSM class exists.

2. **Schema-shape invariants** — a single test that loads the agent's
   ``proto/domain/<schema>.schema.json`` and asserts it parses (a sanity gate
   that the schema artefact still exists and is valid JSON Schema).

3. **Runtime-dependent invariants / pre / post / metamorphic** — emitted as
   ``@pytest.mark.integration`` skip-stubs with the exact assertion text from
   the spec, so they are *visible* in CI as deferred-with-reason rather than
   silently green. CLAUDE.md's Layer 1 (SDD) is no longer a "pretend" gate.

Files containing the marker ``# spec-tests: hand-written, do not regenerate``
are left untouched so curated test_spec.py files (e.g. demand_prophet) survive
``make regenerate-spec-tests``.

Usage:
    python scripts/generate_tests_from_spec.py agents/<agent>/spec.yaml
    python scripts/generate_tests_from_spec.py --all
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
PRESERVE_MARKER = "# SPEC_TESTS_HAND_WRITTEN"

SCHEMA_BY_AGENT = {
    "demand_prophet": "demand_forecast.schema.json",
    "inventory_sentinel": "inventory_action.schema.json",
    "routing_navigator": "route_plan.schema.json",
    "pricing_oracle": "pricing_decision.schema.json",
    "freshness_guardian": "freshness_alert.schema.json",
    "disruption_shield": "disruption_alert.schema.json",
    "supplier_trust": "supplier_score.schema.json",
    "sustainability_agent": "carbon_report.schema.json",
}

STATE_MACHINE_CLASS_BY_AGENT = {
    "demand_prophet": ("agents.demand_prophet.state_machine", "DemandProphetStateMachine"),
    "inventory_sentinel": (
        "agents.inventory_sentinel.state_machine",
        "InventorySentinelStateMachine",
    ),
    "routing_navigator": (
        "agents.routing_navigator.state_machine",
        "RoutingNavigatorStateMachine",
    ),
    "pricing_oracle": ("agents.pricing_oracle.state_machine", "PricingOracleStateMachine"),
    "freshness_guardian": (
        "agents.freshness_guardian.state_machine",
        "FreshnessGuardianStateMachine",
    ),
    "disruption_shield": (
        "agents.disruption_shield.state_machine",
        "DisruptionShieldStateMachine",
    ),
    "supplier_trust": (
        "agents.supplier_trust.state_machine",
        "SupplierTrustStateMachine",
    ),
    "sustainability_agent": (
        "agents.sustainability_agent.state_machine",
        "SustainabilityAgentStateMachine",
    ),
}


def _class_name(spec_id: str) -> str:
    return "Test" + "".join(part.capitalize() for part in spec_id.lower().split("-"))


def _slug(spec_id: str) -> str:
    return spec_id.replace("-", "_").lower()


def _emit_header(agent_name: str, schema_file: str | None) -> list[str]:
    lines = [
        f'"""Auto-generated spec tests for {agent_name} from spec.yaml.',
        "",
        "Regenerate with::",
        "",
        f"    python scripts/generate_tests_from_spec.py agents/{agent_name}/spec.yaml",
        "",
        "Add the marker token  S P E C _ T E S T S _ H A N D _ W R I T T E N",
        "(without spaces, prefixed with #) to opt out of regeneration once you",
        "have curated real assertions on top of the generated stubs.",
        '"""',
        "from __future__ import annotations",
        "",
        "import json",
        "from pathlib import Path",
        "",
        "import pytest",
        "",
        "from synapse_common.fsm import AgentState",
        "",
    ]
    sm = STATE_MACHINE_CLASS_BY_AGENT.get(agent_name)
    if sm is not None:
        module_path, class_name = sm
        lines.append(f"from {module_path} import {class_name}")
        lines.append("")
    if schema_file is not None:
        lines.extend(
            [
                "REPO_ROOT = Path(__file__).resolve().parents[3]",
                f'SCHEMA_PATH = REPO_ROOT / "proto" / "domain" / "{schema_file}"',
                "",
            ]
        )
    return lines


def _emit_invariant_block(inv: dict[str, str]) -> list[str]:
    cls = _class_name(inv["id"])
    slug = _slug(inv["id"])
    return [
        "",
        "@pytest.mark.integration",
        f"class {cls}:",
        f'    """Invariant {inv["id"]}: {inv["description"]}',
        "",
        f"    Assertion: {inv['assertion']}",
        '    """',
        "",
        f"    def test_{slug}(self) -> None:",
        f'        pytest.skip("INTEGRATION: assertion in spec.yaml -- '
        f'wired in tests/integration/ or tests/oracle/")',
        "",
    ]


def _emit_pre_block(pre: dict[str, str]) -> list[str]:
    cls = _class_name(pre["id"])
    slug = _slug(pre["id"])
    return [
        "",
        "@pytest.mark.integration",
        f"class {cls}:",
        f'    """Precondition {pre["id"]}: {pre["description"]}',
        "",
        f"    Check: {pre['check']}",
        '    """',
        "",
        f"    def test_{slug}_valid(self) -> None:",
        f'        pytest.skip("INTEGRATION: precondition exercised in tests/integration/")',
        "",
        f"    def test_{slug}_invalid(self) -> None:",
        f'        pytest.skip("INTEGRATION: violation path exercised in tests/integration/")',
        "",
    ]


def _emit_post_block(post: dict[str, str]) -> list[str]:
    cls = _class_name(post["id"])
    slug = _slug(post["id"])
    return [
        "",
        "@pytest.mark.integration",
        f"class {cls}:",
        f'    """Postcondition {post["id"]}: {post["description"]}',
        "",
        f"    Check: {post['check']}",
        '    """',
        "",
        f"    def test_{slug}(self) -> None:",
        f'        pytest.skip("INTEGRATION: postcondition exercised in tests/integration/")',
        "",
    ]


def _emit_state_machine_block(agent_name: str, sm_spec: dict) -> list[str]:
    sm_entry = STATE_MACHINE_CLASS_BY_AGENT.get(agent_name)
    if sm_entry is None or not sm_spec:
        return []
    _, class_name = sm_entry
    initial_state = sm_spec.get("initial_state", "IDLE")
    transitions = sm_spec.get("transitions", [])
    lines = [
        "",
        "class TestStateMachine:",
        f'    """State machine for {agent_name} (real, not skipped)."""',
        "",
        "    def test_initial_state(self) -> None:",
        f"        sm = {class_name}()",
        f"        assert sm.state == AgentState.{initial_state}",
        "",
    ]

    by_from: dict[str, list[dict]] = {}
    for t in transitions:
        by_from.setdefault(t["from"], []).append(t)

    # Build a forward path for each transition by walking from the initial
    # state, so each transition test sets up the predecessor states it needs.
    def _path_to(target_from: str) -> list[str]:
        # BFS from initial_state finding triggers along the way.
        from collections import deque

        queue: deque[tuple[str, list[str]]] = deque([(initial_state, [])])
        seen = {initial_state}
        while queue:
            state, triggers = queue.popleft()
            if state == target_from:
                return triggers
            for t in by_from.get(state, []):
                if t["to"] not in seen:
                    seen.add(t["to"])
                    queue.append((t["to"], triggers + [t["trigger"]]))
        return []

    for t in transitions:
        slug = f"{t['from']}_to_{t['to']}".lower()
        path = _path_to(t["from"])
        lines.extend(
            [
                f"    def test_transition_{slug}(self) -> None:",
                f"        sm = {class_name}()",
            ]
        )
        for prev_trigger in path:
            lines.append(f'        sm.transition("{prev_trigger}")')
        lines.extend(
            [
                f"        assert sm.state == AgentState.{t['from']}",
                f'        ok = sm.transition("{t["trigger"]}")',
                f"        assert ok is True",
                f"        assert sm.state == AgentState.{t['to']}",
                "",
            ]
        )

    lines.extend(
        [
            "    def test_invalid_trigger_returns_false(self) -> None:",
            f"        sm = {class_name}()",
            f'        assert sm.transition("__nonsense__") is False',
            f"        assert sm.state == AgentState.{initial_state}",
            "",
        ]
    )
    return lines


def _emit_metamorphic_block(mr: dict[str, str]) -> list[str]:
    cls = _class_name(mr["id"])
    slug = _slug(mr["id"])
    return [
        "",
        "@pytest.mark.metamorphic",
        f"class {cls}:",
        f'    """Metamorphic {mr["id"]}: {mr["description"]}',
        "",
        f"    Transform: {mr['transform']}",
        f"    Expected:  {mr['expected']}",
        '    """',
        "",
        f"    def test_{slug}(self) -> None:",
        f'        pytest.skip("Asserted in test_metamorphic.py against the trained model")',
        "",
    ]


def _emit_schema_block(agent_name: str, schema_file: str | None) -> list[str]:
    if schema_file is None:
        return []
    return [
        "",
        "class TestSchemaArtefact:",
        f'    """The {agent_name} output schema must remain a valid JSON Schema."""',
        "",
        "    def test_schema_loads(self) -> None:",
        "        data = json.loads(SCHEMA_PATH.read_text())",
        '        assert data.get("$schema", "").startswith("http")',
        '        assert "properties" in data',
        "",
    ]


def generate_test_file(spec_path: Path, force: bool = False) -> bool:
    if not spec_path.exists():
        print(f"ERROR: {spec_path} not found", file=sys.stderr)
        return False

    spec = yaml.safe_load(spec_path.read_text())
    agent_name = spec["agent_name"]
    schema_file = SCHEMA_BY_AGENT.get(agent_name)

    test_file = spec_path.parent / "tests" / "test_spec.py"
    if test_file.exists():
        existing = test_file.read_text(encoding="utf-8", errors="replace")
        # The hand-written marker is ALWAYS honored, even with --force.
        # Use --force-all to override it.
        if PRESERVE_MARKER in existing:
            print(f"SKIP {test_file}: marked do-not-regenerate (HAND_WRITTEN)")
            return True
        if not force:
            print(f"SKIP {test_file}: exists; pass --force to overwrite")
            return True

    lines = _emit_header(agent_name, schema_file)
    for inv in spec.get("invariants", []):
        lines.extend(_emit_invariant_block(inv))
    for pre in spec.get("preconditions", []):
        lines.extend(_emit_pre_block(pre))
    for post in spec.get("postconditions", []):
        lines.extend(_emit_post_block(post))
    lines.extend(_emit_state_machine_block(agent_name, spec.get("state_machine", {})))
    lines.extend(_emit_schema_block(agent_name, schema_file))
    for mr in spec.get("metamorphic_relations", []):
        lines.extend(_emit_metamorphic_block(mr))

    test_file.parent.mkdir(parents=True, exist_ok=True)
    test_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(
        f"WROTE {test_file}: "
        f"{len(spec.get('invariants', []))} inv, "
        f"{len(spec.get('preconditions', []))} pre, "
        f"{len(spec.get('postconditions', []))} post, "
        f"{len(spec.get('state_machine', {}).get('transitions', []))} transitions, "
        f"{len(spec.get('metamorphic_relations', []))} mr"
    )
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("spec", nargs="?", help="Path to spec.yaml")
    parser.add_argument("--all", action="store_true", help="Regenerate every agent.")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite even files marked do-not-regenerate.",
    )
    args = parser.parse_args()

    targets: list[Path]
    if args.all:
        targets = sorted((REPO_ROOT / "agents").glob("*/spec.yaml"))
    elif args.spec:
        targets = [Path(args.spec)]
    else:
        parser.print_help()
        return 2

    ok = True
    for path in targets:
        if not generate_test_file(path, force=args.force):
            ok = False
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
