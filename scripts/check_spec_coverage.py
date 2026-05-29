#!/usr/bin/env python3
"""SYNAPSE — Spec invariant → test coverage gate (Sprint 13 §Phase 5).

Iterates every `agents/*/spec.yaml`, extracts each `INV-*` invariant ID, and
checks whether the agent's `tests/test_spec.py` covers it.

Two coverage modes:
  - **substring** (legacy): the ID appears anywhere in the test file. Gameable
    by a comment. Used for backwards compatibility.
  - **assertion** (default, Sprint 13): an `assert` statement appears within
    ``NEAR_LINES`` (20) lines of the ID. Parsed via the ``ast`` module so
    string-literal occurrences of the ID also count as long as a real assert
    is nearby.

Exits 0 iff the aggregate **assertion-matched** coverage % meets the threshold
(``--threshold``, default 50). Per-agent FAILs print to stderr but are not
CI-fatal until the aggregate floor is ratcheted higher.

Usage::

    python scripts/check_spec_coverage.py                  # exit 0 if >=50% aggregate
    python scripts/check_spec_coverage.py --threshold 80   # tighter ratchet
    python scripts/check_spec_coverage.py --json           # machine-readable
    python scripts/check_spec_coverage.py --per-agent      # verbose per-agent table
    python scripts/check_spec_coverage.py --mode substring # legacy behaviour
"""

from __future__ import annotations

import argparse
import ast
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

import yaml

NEAR_LINES = 20
ROOT = Path(__file__).resolve().parents[1]
AGENTS_DIR = ROOT / "agents"


@dataclass
class AgentCoverage:
    agent: str
    declared: int
    substring_matched: int
    assertion_matched: int
    missing_assertion: list[str]

    @property
    def substring_pct(self) -> float:
        return 100.0 * self.substring_matched / self.declared if self.declared else 100.0

    @property
    def assertion_pct(self) -> float:
        return 100.0 * self.assertion_matched / self.declared if self.declared else 100.0


def _assert_line_numbers(source: str) -> list[int]:
    """Return 1-indexed line numbers of every assert statement in *source*."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        # If the test file is malformed, treat as no asserts found.
        return []
    return [node.lineno for node in ast.walk(tree) if isinstance(node, ast.Assert)]


def _invariant_line_numbers(source: str, inv_id: str) -> list[int]:
    """Return 1-indexed line numbers where *inv_id* (case-insensitive,
    underscore-normalised) appears as a substring."""
    needle = inv_id.replace("-", "_").lower()
    raw = inv_id.lower()
    hits: list[int] = []
    for i, line in enumerate(source.splitlines(), 1):
        lower = line.lower()
        if needle in lower or raw in lower:
            hits.append(i)
    return hits


def _assertion_matched(source: str, inv_id: str) -> bool:
    """True iff some assert statement lies within ``NEAR_LINES`` lines of any
    occurrence of *inv_id* in the test source."""
    inv_hits = _invariant_line_numbers(source, inv_id)
    if not inv_hits:
        return False
    asserts = _assert_line_numbers(source)
    if not asserts:
        return False
    return any(
        abs(assert_line - inv_line) <= NEAR_LINES
        for assert_line in asserts
        for inv_line in inv_hits
    )


def _substring_matched(source: str, inv_id: str) -> bool:
    return bool(_invariant_line_numbers(source, inv_id))


def measure() -> list[AgentCoverage]:
    """Walk every agent spec.yaml and compute coverage against ALL tests in
    the agent's ``tests/`` directory.

    Sprint 13 (round 2): the previous version checked only ``test_spec.py``,
    which forced an artificial separation between "spec tests" and "behaviour
    tests." Real invariants are often asserted in ``test_reward.py``,
    ``test_reward_safety.py``, ``test_model.py``, etc. We now search every
    ``test_*.py`` under ``<agent>/tests/`` so an invariant is covered as long
    as SOME test in the agent asserts near its ID.
    """
    out: list[AgentCoverage] = []
    for spec_file in sorted(AGENTS_DIR.rglob("spec.yaml")):
        agent_dir = spec_file.parent
        tests_dir = agent_dir / "tests"
        # Pass encoding='utf-8' — Sprint 13 fix for a Windows cp1252 crash.
        spec = yaml.safe_load(spec_file.read_text(encoding="utf-8"))
        agent_name = spec.get("agent_name", agent_dir.name)
        invariant_ids = [inv["id"] for inv in spec.get("invariants", [])]
        if not tests_dir.is_dir():
            out.append(
                AgentCoverage(
                    agent=agent_name,
                    declared=len(invariant_ids),
                    substring_matched=0,
                    assertion_matched=0,
                    missing_assertion=list(invariant_ids),
                )
            )
            continue
        # Concatenate all test sources for this agent so the assertion-near-ID
        # search spans files (the test_spec.py file may reference the ID in a
        # docstring while the real assert lives in test_reward.py).
        sources: list[str] = []
        for f in sorted(tests_dir.glob("test_*.py")):
            try:
                sources.append(f.read_text(encoding="utf-8", errors="replace"))
            except OSError:
                continue
        # Per-file evaluation: an invariant is covered if any single file
        # satisfies the "assert within NEAR_LINES of ID" rule — concatenating
        # would wrongly bridge ID-in-file-A with assert-in-file-B.
        substring = 0
        assertion = 0
        missing: list[str] = []
        for inv_id in invariant_ids:
            sub_hit = any(_substring_matched(s, inv_id) for s in sources)
            asn_hit = any(_assertion_matched(s, inv_id) for s in sources)
            if sub_hit:
                substring += 1
            if asn_hit:
                assertion += 1
            else:
                missing.append(inv_id)
        out.append(
            AgentCoverage(
                agent=agent_name,
                declared=len(invariant_ids),
                substring_matched=substring,
                assertion_matched=assertion,
                missing_assertion=missing,
            )
        )
    return out


def aggregate(rows: list[AgentCoverage], mode: Literal["assertion", "substring"]) -> float:
    """Aggregate coverage % across all agents, weighted by invariant count."""
    declared = sum(r.declared for r in rows)
    if not declared:
        return 100.0
    if mode == "assertion":
        matched = sum(r.assertion_matched for r in rows)
    else:
        matched = sum(r.substring_matched for r in rows)
    return 100.0 * matched / declared


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--threshold", type=float, default=50.0,
        help="Minimum aggregate coverage %% to pass (default: 50)",
    )
    parser.add_argument(
        "--mode", choices=["assertion", "substring"], default="assertion",
        help="Coverage mode used for the gate (default: assertion)",
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON to stdout")
    parser.add_argument("--per-agent", action="store_true", help="Print per-agent table")
    args = parser.parse_args()

    rows = measure()
    agg_assertion = aggregate(rows, "assertion")
    agg_substring = aggregate(rows, "substring")
    gate_metric = agg_assertion if args.mode == "assertion" else agg_substring
    passed = gate_metric >= args.threshold

    if args.json:
        payload = {
            "mode": args.mode,
            "threshold": args.threshold,
            "passed": passed,
            "aggregate": {"assertion_pct": agg_assertion, "substring_pct": agg_substring},
            "agents": [asdict(r) for r in rows],
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0 if passed else 1

    declared_total = sum(r.declared for r in rows)
    assert_total = sum(r.assertion_matched for r in rows)
    sub_total = sum(r.substring_matched for r in rows)
    print(
        f"SYNAPSE spec coverage  mode={args.mode}  threshold={args.threshold:.0f}%"
    )
    print(
        f"  Aggregate: assertion-matched {assert_total}/{declared_total} ({agg_assertion:.1f}%) "
        f"| substring {sub_total}/{declared_total} ({agg_substring:.1f}%)"
    )

    if args.per_agent:
        print()
        print(f"  {'Agent':<24} {'Declared':>9} {'Substring':>10} {'Assertion':>10}")
        print(f"  {'-' * 24} {'-' * 9:>9} {'-' * 10:>10} {'-' * 10:>10}")
        for r in rows:
            print(
                f"  {r.agent:<24} {r.declared:>9} {r.substring_matched:>4} "
                f"({r.substring_pct:>5.1f}%) {r.assertion_matched:>4} ({r.assertion_pct:>5.1f}%)"
            )

    # Print missing-assertion lines for the worst offenders, useful in CI logs.
    worst = sorted(rows, key=lambda r: r.assertion_pct)[:3]
    if any(w.missing_assertion for w in worst):
        print("\n  Missing assertion coverage (top 3 weakest agents):", file=sys.stderr)
        for r in worst:
            if r.missing_assertion:
                print(f"    {r.agent}: {r.missing_assertion}", file=sys.stderr)

    status = "PASS" if passed else "FAIL"
    print(
        f"\n  {status} aggregate {args.mode}-matched {gate_metric:.1f}% "
        f"vs threshold {args.threshold:.0f}%"
    )
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
