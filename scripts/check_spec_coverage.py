#!/usr/bin/env python3
"""
SYNAPSE — Verify spec.yaml coverage across tests.

Sprint 8 (ADR-031) extends the original INV-* coverage gate to also assert:

  - every MR-* (metamorphic relation) maps to at least one test by id-grep
    across ``agents/<name>/tests/`` AND repo-wide ``tests/`` directories,
  - every key in ``reward.weights`` is present in the auto-generated
    ``agents/<name>/training/reward_config.py``.

Usage: python scripts/check_spec_coverage.py
Exit code: 0 = clean, 1 = gaps.
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
AGENTS_DIR = REPO_ROOT / "agents"
GLOBAL_TESTS_DIR = REPO_ROOT / "tests"


def _norm(token: str) -> str:
    return token.replace("-", "_").lower()


def _aggregate_test_text(agent_dir: Path) -> str:
    """Concatenate text from agent-local tests + repo-wide tests/."""
    parts: list[str] = []
    agent_tests = agent_dir / "tests"
    if agent_tests.exists():
        for path in agent_tests.rglob("*.py"):
            try:
                parts.append(path.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError):
                continue
    if GLOBAL_TESTS_DIR.exists():
        for path in GLOBAL_TESTS_DIR.rglob("*.py"):
            try:
                parts.append(path.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError):
                continue
    return "\n".join(parts).lower()


def _check_invariants(agent: str, invariants: list[dict], haystack: str) -> list[str]:
    missing: list[str] = []
    for inv in invariants:
        if _norm(inv["id"]) not in haystack:
            missing.append(inv["id"])
    if missing:
        return [f"  FAIL {agent}: missing tests for invariants {missing}"]
    return []


def _check_metamorphic(agent: str, relations: list[dict], haystack: str) -> list[str]:
    missing: list[str] = []
    for mr in relations:
        if _norm(mr["id"]) not in haystack:
            missing.append(mr["id"])
    if missing:
        return [f"  FAIL {agent}: missing metamorphic tests for {missing}"]
    return []


def _check_reward_weights(agent: str, agent_dir: Path, weights: dict[str, float]) -> list[str]:
    """Each spec-declared weight key must appear in reward_config.WEIGHTS."""
    if not weights:
        return []
    config_path = agent_dir / "training" / "reward_config.py"
    if not config_path.exists():
        return [f"  FAIL {agent}: reward.weights declared but reward_config.py missing"]
    config_text = config_path.read_text(encoding="utf-8")
    missing = [key for key in weights if f'"{key}"' not in config_text]
    if missing:
        return [f"  FAIL {agent}: reward_config.WEIGHTS missing keys {missing}"]
    return []


def check_coverage() -> bool:
    errors: list[str] = []

    for spec_file in sorted(AGENTS_DIR.rglob("spec.yaml")):
        agent_dir = spec_file.parent
        with spec_file.open(encoding="utf-8") as fp:
            spec = yaml.safe_load(fp)

        agent_name = spec.get("agent_name", agent_dir.name)
        haystack = _aggregate_test_text(agent_dir)

        invariants = spec.get("invariants", []) or []
        metamorphic = spec.get("metamorphic_relations", []) or []
        weights = (spec.get("reward") or {}).get("weights") or {}

        agent_errors: list[str] = []
        agent_errors.extend(_check_invariants(agent_name, invariants, haystack))
        agent_errors.extend(_check_metamorphic(agent_name, metamorphic, haystack))
        agent_errors.extend(_check_reward_weights(agent_name, agent_dir, weights))

        if agent_errors:
            errors.extend(agent_errors)
        else:
            print(
                f"  OK {agent_name}: {len(invariants)} invariants, "
                f"{len(metamorphic)} MRs, {len(weights)} reward keys covered"
            )

    if errors:
        print("\nCOVERAGE GAPS:")
        for err in errors:
            print(err)
        return False
    print("\nAll spec invariants + metamorphic relations + reward weights covered.")
    return True


if __name__ == "__main__":
    sys.exit(0 if check_coverage() else 1)
