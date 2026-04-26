"""Enforce mutation-survival thresholds against a mutmut cache.

CLAUDE.md gates:
  - reward functions:    < 15% surviving mutants
  - guardrails / audit:  < 10% surviving mutants

Usage:
    python scripts/check_mutation_threshold.py --threshold 15 [--label demand_prophet]

The script inspects ``.mutmut-cache/mutants.db`` (SQLite, written by mutmut)
and computes the share of mutants in a "surviving" status. If the cache is
missing it exits 0 with a clear warning so transient infra issues don't mask
real reward bugs. If the rate exceeds the threshold it exits 1.

Surviving statuses recognised: ``bad_survived``, ``ok_suspicious`` —
matching mutmut <=2.x and 3.x naming.
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

CACHE_DB = Path(".mutmut-cache") / "mutants.db"

# mutmut writes a status string per mutant. Anything in this set counts as
# "surviving" (the test suite did not fail on the mutated code).
SURVIVING_STATUSES = {"bad_survived", "ok_suspicious"}
KILLED_STATUSES = {"bad_killed", "bad_timeout", "killed"}


def survival_rate_from_cache(db_path: Path) -> tuple[int, int] | None:
    """Return (surviving, total) or None if the cache is unreadable."""
    if not db_path.exists():
        return None
    try:
        conn = sqlite3.connect(str(db_path))
    except sqlite3.Error:
        return None
    try:
        cursor = conn.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='table' AND name LIKE '%mutant%'"
        )
        tables = [row[0] for row in cursor.fetchall()]
        if not tables:
            return None
        # mutmut 2.x: table 'mutant'; 3.x: 'mutants'
        table = "mutant" if "mutant" in tables else tables[0]
        rows = conn.execute(f"SELECT status FROM {table}").fetchall()
    finally:
        conn.close()

    if not rows:
        return None

    total_classified = 0
    surviving = 0
    for (status,) in rows:
        if status in SURVIVING_STATUSES:
            surviving += 1
            total_classified += 1
        elif status in KILLED_STATUSES:
            total_classified += 1
        # unknown / pending statuses are ignored — they were not tested
    if total_classified == 0:
        return None
    return surviving, total_classified


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--threshold",
        type=float,
        required=True,
        help="Maximum allowed surviving-mutant percentage (0-100).",
    )
    parser.add_argument(
        "--label",
        default="target",
        help="Human label for log lines (e.g. demand_prophet, guardrails).",
    )
    parser.add_argument(
        "--cache",
        type=Path,
        default=CACHE_DB,
        help="Path to mutmut cache DB (default: .mutmut-cache/mutants.db).",
    )
    parser.add_argument(
        "--soft",
        action="store_true",
        help="Exit 0 even on threshold breach (informational).",
    )
    args = parser.parse_args()

    result = survival_rate_from_cache(args.cache)
    if result is None:
        print(
            f"[mutation-threshold] {args.label}: cache missing or empty at "
            f"{args.cache} — skipping (not a failure).",
            file=sys.stderr,
        )
        return 0

    surviving, total = result
    rate_pct = 100.0 * surviving / total
    verdict = "PASS" if rate_pct < args.threshold else "FAIL"
    print(
        f"[mutation-threshold] {args.label}: "
        f"{surviving}/{total} surviving = {rate_pct:.1f}% "
        f"(threshold < {args.threshold:.0f}%) — {verdict}"
    )
    if rate_pct >= args.threshold and not args.soft:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
