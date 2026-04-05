#!/usr/bin/env python3
"""
SYNAPSE SDD — Auto-generate pytest test stubs from spec.yaml.
Usage: python scripts/generate_tests_from_spec.py agents/demand_prophet/spec.yaml
"""
from __future__ import annotations

import sys
from pathlib import Path

import yaml


def generate_test_file(spec_path: str) -> None:
    spec_file = Path(spec_path)
    if not spec_file.exists():
        print(f"ERROR: {spec_file} not found")
        sys.exit(1)

    with open(spec_file) as f:
        spec = yaml.safe_load(f)

    agent_name = spec["agent_name"]
    agent_dir = spec_file.parent
    test_file = agent_dir / "tests" / "test_spec.py"

    lines: list[str] = [
        f'"""Auto-generated spec tests for {agent_name} from spec.yaml."""',
        "from __future__ import annotations",
        "",
        "import pytest",
        "",
        "",
    ]

    for inv in spec.get("invariants", []):
        inv_id = inv["id"].replace("-", "_").lower()
        lines.extend([
            f"class Test{inv_id.title().replace('_', '')}:",
            f'    """Invariant {inv["id"]}: {inv["description"]}"""',
            "",
            f"    def test_{inv_id}(self) -> None:",
            f'        # Assertion: {inv["assertion"]}',
            f'        pytest.skip("NOT IMPLEMENTED — implement {agent_name} to make this pass")',
            "",
            "",
        ])

    for pre in spec.get("preconditions", []):
        pre_id = pre["id"].replace("-", "_").lower()
        lines.extend([
            f"class Test{pre_id.title().replace('_', '')}:",
            f'    """Precondition {pre["id"]}: {pre["description"]}"""',
            "",
            f"    def test_{pre_id}_valid(self) -> None:",
            f'        # Check: {pre["check"]}',
            f'        pytest.skip("NOT IMPLEMENTED")',
            "",
            f"    def test_{pre_id}_invalid_raises(self) -> None:",
            f'        pytest.skip("NOT IMPLEMENTED")',
            "",
            "",
        ])

    for post in spec.get("postconditions", []):
        post_id = post["id"].replace("-", "_").lower()
        lines.extend([
            f"class Test{post_id.title().replace('_', '')}:",
            f'    """Postcondition {post["id"]}: {post["description"]}"""',
            "",
            f"    def test_{post_id}(self) -> None:",
            f'        # Check: {post["check"]}',
            f'        pytest.skip("NOT IMPLEMENTED")',
            "",
            "",
        ])

    sm = spec.get("state_machine", {})
    if sm:
        lines.extend([
            "class TestStateMachine:",
            f'    """State machine for {agent_name}"""',
            "",
            f"    def test_initial_state(self) -> None:",
            f'        # Initial state: {sm.get("initial_state", "IDLE")}',
            f'        pytest.skip("NOT IMPLEMENTED")',
            "",
        ])
        for transition in sm.get("transitions", []):
            t_name = f"{transition['from']}_to_{transition['to']}".lower()
            lines.extend([
                f"    def test_transition_{t_name}(self) -> None:",
                f'        # Trigger: {transition["trigger"]}',
                f'        # Guard: {transition.get("guard", "none")}',
                f'        pytest.skip("NOT IMPLEMENTED")',
                "",
            ])

    for mr in spec.get("metamorphic_relations", []):
        mr_id = mr["id"].replace("-", "_").lower()
        lines.extend([
            "",
            f"@pytest.mark.metamorphic",
            f"class Test{mr_id.title().replace('_', '')}:",
            f'    """Metamorphic {mr["id"]}: {mr["description"]}"""',
            "",
            f"    def test_{mr_id}(self) -> None:",
            f'        # Transform: {mr["transform"]}',
            f'        # Expected: {mr["expected"]}',
            f'        pytest.skip("NOT IMPLEMENTED")',
            "",
        ])

    test_file.parent.mkdir(parents=True, exist_ok=True)
    test_file.write_text("\n".join(lines))
    print(f"Generated {test_file} with {len(spec.get('invariants', []))} invariant tests, "
          f"{len(spec.get('preconditions', []))} precondition tests, "
          f"{len(spec.get('postconditions', []))} postcondition tests, "
          f"{len(spec.get('metamorphic_relations', []))} metamorphic tests")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python scripts/generate_tests_from_spec.py <path/to/spec.yaml>")
        sys.exit(1)
    generate_test_file(sys.argv[1])
