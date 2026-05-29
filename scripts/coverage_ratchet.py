#!/usr/bin/env python3
"""SYNAPSE — Coverage floor ratchet (Sprint 13 §Phase 2.3).

After a coverage-improving PR, run this script. It reads `coverage.xml` and
`infrastructure/quality/coverage-floors.yaml`, finds any package whose
MEASURED coverage exceeds its floor by more than ``--margin`` (default 2.0
percentage points), and proposes a bump. With ``--apply`` the YAML is
rewritten in place so the new floor lands in the same PR.

This is an OPERATOR step (like ``scripts/check_cve_budget.py --update-registry``
per E-S9-15) — not run by CI. The floor only ever increases via this script;
to lower a floor (e.g., after a deletion that removes covered code), edit the
YAML by hand and explain in the PR description.

The principle is the WS-9 lesson: floors are mechanical, ratcheted upward, and
never aspirational. A "we'll get to 84% someday" promise that doesn't translate
into a ratchet step is the same kind of theatre that produced the 80→63 revert.

Usage::

    python scripts/coverage_ratchet.py                      # dry-run
    python scripts/coverage_ratchet.py --apply              # write floors back
    python scripts/coverage_ratchet.py --margin 5 --apply   # require larger gain
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import yaml

from coverage_per_package import evaluate  # type: ignore[import-not-found]

ROOT = Path(__file__).resolve().parents[1]


def propose_bumps(xml: Path, floors: Path, margin: float) -> list[tuple[str, float, float]]:
    """Return [(package, old_floor, new_floor)] for every package where
    measured - floor > margin."""
    results = evaluate(xml, floors)
    proposals: list[tuple[str, float, float]] = []
    for r in results:
        if r.status == "UNMEASURED":
            continue
        if r.measured_combined_pct - r.floor > margin:
            # New floor: measured - 0.5 (small buffer for floating-point jitter)
            new_floor = round(r.measured_combined_pct - 0.5, 1)
            # Cap at target so we don't overshoot
            new_floor = min(new_floor, r.target - 0.5) if r.target > 0 else new_floor
            proposals.append((r.package, r.floor, new_floor))
    return proposals


def rewrite_floor(text: str, package: str, new_floor: float) -> str:
    """Rewrite the `line:` value under `packages.<package>:` to *new_floor*.
    Preserves comments and field order by doing a regex substitution on the
    YAML text (round-trip with PyYAML would drop comments)."""
    # Find the package section and the immediately-following `line:` key.
    # Quote special chars in the package path for regex.
    quoted = re.escape(package)
    pattern = re.compile(
        rf"(  {quoted}:\s*\n(?:    [^\n]*\n)*?    line:\s*)([0-9.]+)",
        re.MULTILINE,
    )
    new_text, n = pattern.subn(rf"\g<1>{new_floor:.1f}", text)
    if n == 0:
        raise RuntimeError(f"Could not find `line:` under `{package}:` in floors YAML")
    if n > 1:
        raise RuntimeError(f"Ambiguous match for `line:` under `{package}:` ({n} hits)")
    return new_text


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--xml", type=Path, default=Path("coverage.xml"))
    parser.add_argument(
        "--floors",
        type=Path,
        default=ROOT / "infrastructure" / "quality" / "coverage-floors.yaml",
    )
    parser.add_argument(
        "--margin", type=float, default=2.0,
        help="Required measured - floor delta to propose a bump (default: 2.0)",
    )
    parser.add_argument(
        "--apply", action="store_true",
        help="Write the new floors back to the YAML in place",
    )
    args = parser.parse_args()

    if not args.xml.is_file():
        print(f"ERROR: coverage XML not found at {args.xml}", file=sys.stderr)
        return 2
    if not args.floors.is_file():
        print(f"ERROR: floors YAML not found at {args.floors}", file=sys.stderr)
        return 2

    proposals = propose_bumps(args.xml, args.floors, args.margin)
    if not proposals:
        print(
            f"No floor bumps proposed (margin={args.margin:.1f}). "
            f"Add tests to climb closer to 84% target."
        )
        return 0

    print(f"Proposed floor bumps (margin {args.margin:.1f}%):")
    for pkg, old, new in proposals:
        print(f"  {pkg:<32} {old:>5.1f}% -> {new:>5.1f}%  (+{new - old:.1f})")

    if not args.apply:
        print("\nDry-run only — rerun with --apply to write floors YAML back.")
        return 0

    text = args.floors.read_text(encoding="utf-8")
    for pkg, _old, new in proposals:
        text = rewrite_floor(text, pkg, new)
    args.floors.write_text(text, encoding="utf-8")
    # Validate the YAML still parses round-trip.
    yaml.safe_load(text)
    try:
        rel = args.floors.resolve().relative_to(ROOT)
    except ValueError:
        rel = args.floors  # absolute or off-tree — print as-is
    print(f"\nWrote {len(proposals)} bump(s) to {rel}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
