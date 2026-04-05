#!/usr/bin/env python3
"""
SYNAPSE — Verify every spec.yaml invariant has a corresponding test.
Usage: python scripts/check_spec_coverage.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import yaml


def check_coverage() -> bool:
    errors: list[str] = []
    agents_dir = Path("agents")

    for spec_file in agents_dir.rglob("spec.yaml"):
        agent_dir = spec_file.parent
        test_file = agent_dir / "tests" / "test_spec.py"

        with open(spec_file) as f:
            spec = yaml.safe_load(f)

        agent_name = spec.get("agent_name", spec_file.parent.name)
        invariant_ids = [inv["id"] for inv in spec.get("invariants", [])]

        if not test_file.exists():
            errors.append(f"  FAIL {agent_name}: test_spec.py not found")
            continue

        test_content = test_file.read_text()
        missing = [
            inv_id for inv_id in invariant_ids
            if inv_id.replace("-", "_").lower() not in test_content.lower()
        ]

        if missing:
            errors.append(f"  FAIL {agent_name}: missing tests for {missing}")
        else:
            print(f"  OK {agent_name}: {len(invariant_ids)} invariants covered")

    if errors:
        print("\nCOVERAGE GAPS:")
        for err in errors:
            print(err)
        return False
    print("\nAll spec invariants have corresponding tests.")
    return True


if __name__ == "__main__":
    sys.exit(0 if check_coverage() else 1)
