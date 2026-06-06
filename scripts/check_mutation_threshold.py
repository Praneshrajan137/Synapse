"""Enforce mutation-survival thresholds against a mutmut cache.

CLAUDE.md gates:
  - reward functions:    < 15% surviving mutants
  - guardrails / audit:  < 10% surviving mutants

Usage:
    python scripts/check_mutation_threshold.py --threshold 15 [--label demand_prophet]

The script inspects mutmut's SQLite cache and computes the share of mutants in
a "surviving" status. mutmut 2.x writes the DB directly to ``.mutmut-cache``;
some older/local setups used a directory containing ``mutants.db``. Both forms
are accepted. If no readable cache exists, the script fails closed: a mutation
gate that cannot evaluate mutants is not a trustworthy pass.

Surviving statuses recognised: ``bad_survived``, ``ok_suspicious`` -
matching mutmut <=2.x and 3.x naming.
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

CACHE_DB = Path(".mutmut-cache")

# mutmut writes a status string per mutant. Anything in this set counts as
# "surviving" (the test suite did not fail on the mutated code).
SURVIVING_STATUSES = {"bad_survived", "ok_suspicious"}
KILLED_STATUSES = {"bad_killed", "bad_timeout", "killed", "ok_killed"}


def _quote_identifier(identifier: str) -> str:
    """Return an SQLite identifier quoted with double quotes."""
    return '"' + identifier.replace('"', '""') + '"'


def candidate_cache_paths(cache_path: Path) -> list[Path]:
    """Return likely SQLite cache files for mutmut 2.x and directory caches."""
    if cache_path.is_file():
        return [cache_path]
    if cache_path.is_dir():
        preferred = [cache_path / "mutants.db", cache_path / "mutmut-cache.db"]
        return [path for path in preferred if path.is_file()] + [
            path
            for path in sorted(cache_path.iterdir())
            if path.is_file() and path not in preferred
        ]
    if cache_path.parent.is_file():
        return [cache_path.parent]
    return []


def _survival_rate_from_sqlite(db_path: Path) -> tuple[int, int] | None:
    """Return (surviving, total) from one SQLite DB or None if unreadable."""
    try:
        conn = sqlite3.connect(str(db_path))
    except sqlite3.Error:
        return None
    try:
        tables = [
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        ]
        rows: list[tuple[str]] = []
        for table in tables:
            columns = [
                row[1]
                for row in conn.execute(f"PRAGMA table_info({_quote_identifier(table)})").fetchall()
            ]
            if "status" not in columns:
                continue
            rows = conn.execute(f"SELECT status FROM {_quote_identifier(table)}").fetchall()
            if rows:
                break
    except sqlite3.Error:
        return None
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
        # Unknown / pending statuses are ignored: they were not tested.
    if total_classified == 0:
        return None
    return surviving, total_classified


def survival_rate_from_cache(cache_path: Path) -> tuple[int, int] | None:
    """Return (surviving, total) or None if no candidate cache is readable."""
    for db_path in candidate_cache_paths(cache_path):
        result = _survival_rate_from_sqlite(db_path)
        if result is not None:
            return result
    return None


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
        help="Path to mutmut cache DB or cache directory (default: .mutmut-cache).",
    )
    parser.add_argument(
        "--soft",
        action="store_true",
        help="Exit 0 even on threshold/cache failure (informational).",
    )
    args = parser.parse_args()

    result = survival_rate_from_cache(args.cache)
    if result is None:
        print(
            f"[mutation-threshold] {args.label}: cache missing or empty at {args.cache} - FAIL",
            file=sys.stderr,
        )
        return 0 if args.soft else 1

    surviving, total = result
    rate_pct = 100.0 * surviving / total
    verdict = "PASS" if rate_pct < args.threshold else "FAIL"
    print(
        f"[mutation-threshold] {args.label}: "
        f"{surviving}/{total} surviving = {rate_pct:.1f}% "
        f"(threshold < {args.threshold:.0f}%) - {verdict}"
    )
    if rate_pct >= args.threshold and not args.soft:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
