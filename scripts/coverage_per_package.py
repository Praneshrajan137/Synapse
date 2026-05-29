#!/usr/bin/env python3
"""SYNAPSE — Per-package coverage floor gate (Sprint 13 §Phase 2).

Reads a ``coverage.xml`` (Cobertura) report and a per-package floors YAML,
then exits non-zero if any package falls below its floor. This replaces the
single global ``--cov-fail-under`` in CI so a regression in one package
fails CI on that specific package, not the aggregate.

Why not pytest's per-package threshold? coverage.py does not expose one — its
``fail_under`` is global. We compute the per-package number from the XML.

Cobertura XML structure (the relevant bits)::

  <coverage line-rate="..." branch-rate="..." ...>
    <packages>
      <package name="packages.synapse_common" line-rate="0.6118" branch-rate="0.5031">
        <classes>
          <class name="budget.py" filename="packages/synapse_common/budget.py" ...>
          ...

We aggregate by **filename prefix match** so the report's `package name`
quirks (dots vs slashes, varying depth) don't matter.

Usage::

    python scripts/coverage_per_package.py \\
        --xml coverage.xml \\
        --floors infrastructure/quality/coverage-floors.yaml

    # Markdown table for the PR comment
    python scripts/coverage_per_package.py --xml coverage.xml --floors ... --markdown

    # JSON for CI ingestion
    python scripts/coverage_per_package.py --xml coverage.xml --floors ... --json
"""

from __future__ import annotations

import argparse
import json
import sys
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


@dataclass
class PackageResult:
    package: str
    floor: float
    target: float
    measured_combined_pct: float
    statements_covered: int
    statements_total: int
    branches_covered: int
    branches_total: int
    status: str  # PASS | FAIL | UNMEASURED

    @property
    def gap_to_target(self) -> float:
        return max(0.0, self.target - self.measured_combined_pct)


def _source_roots(root: ET.Element) -> list[str]:
    """Return the list of <source> root paths, normalised with forward slashes."""
    return [(s.text or "").replace("\\", "/").rstrip("/") for s in root.iter("source")]


def _classes_under(root: ET.Element, prefix: str) -> list[ET.Element]:
    """Return every <class> whose full path (source-root + filename) contains
    *prefix*. Cobertura emits one <source> root per ``--cov=`` argument; the
    <class filename> is relative to one of those roots. We try every source as
    the candidate root for each class to be tolerant.

    Match is by **suffix containment**: the normalised `prefix` must appear as
    a path segment in `<source>/filename`. This way `packages/synapse_common`
    matches both ``<source>=…/synapse_common</source> + filename=budget.py``
    and ``<source>=…/repo</source> + filename=packages/synapse_common/budget.py``.
    """
    norm_prefix = prefix.replace("\\", "/").strip("/")
    sources = _source_roots(root) or [""]
    out: list[ET.Element] = []
    for cls in root.iter("class"):
        fn = (cls.get("filename") or "").replace("\\", "/")
        # Try every source root; if any produces a path containing the prefix
        # as a directory segment, count this class.
        candidates = [f"{src}/{fn}" if src else fn for src in sources]
        for full in candidates:
            full_norm = full.replace("\\", "/")
            # Match as path segment: must be bordered by `/` on at least one side
            # to avoid e.g. `agents/demand_prophet_x` matching `agents/demand_prophet`.
            if f"/{norm_prefix}/" in f"/{full_norm}/":
                out.append(cls)
                break
    return out


def _aggregate(classes: list[ET.Element]) -> tuple[int, int, int, int]:
    """Sum (lines_covered, lines_total, branches_covered, branches_total) over
    a list of Cobertura <class> elements. We re-derive instead of trusting the
    package-level rate, because the XML's package grouping doesn't always match
    our filesystem-based packages."""
    lc = lt = bc = bt = 0
    for cls in classes:
        for line in cls.iter("line"):
            lt += 1
            hits = int(line.get("hits") or 0)
            if hits > 0:
                lc += 1
            # Branch metadata (when branch coverage is on)
            cond = line.get("condition-coverage")
            if cond and "(" in cond:
                # Format: "50% (1/2)" — extract the (covered/total) pair
                inside = cond[cond.index("(") + 1 : cond.index(")")]
                if "/" in inside:
                    c, t = inside.split("/", 1)
                    try:
                        bc += int(c)
                        bt += int(t)
                    except ValueError:
                        pass
    return lc, lt, bc, bt


def _combined_pct(lc: int, lt: int, bc: int, bt: int) -> float:
    """Combined line+branch percentage (the metric coverage.py prints in
    the TOTAL row when --cov-branch is set). Falls back to 100% if a
    package has zero measurable lines (e.g., __init__.py-only)."""
    num = lc + bc
    den = lt + bt
    if den == 0:
        return 100.0
    return 100.0 * num / den


def evaluate(xml_path: Path, floors_path: Path) -> list[PackageResult]:
    tree = ET.parse(xml_path)
    root = tree.getroot()
    floors_doc = yaml.safe_load(floors_path.read_text(encoding="utf-8"))
    out: list[PackageResult] = []
    for pkg_path, cfg in floors_doc.get("packages", {}).items():
        floor = float(cfg.get("line", 0.0))
        target = float(cfg.get("target", floors_doc.get("target", 84.0)))
        classes = _classes_under(root, pkg_path)
        lc, lt, bc, bt = _aggregate(classes)
        pct = _combined_pct(lc, lt, bc, bt)
        if lt == 0 and bt == 0:
            status = "UNMEASURED"
        elif pct + 1e-9 >= floor:
            status = "PASS"
        else:
            status = "FAIL"
        out.append(
            PackageResult(
                package=pkg_path,
                floor=floor,
                target=target,
                measured_combined_pct=round(pct, 2),
                statements_covered=lc,
                statements_total=lt,
                branches_covered=bc,
                branches_total=bt,
                status=status,
            )
        )
    return out


def _print_text(results: list[PackageResult], *, threshold_target: float) -> None:
    print(f"SYNAPSE per-package coverage gate -- target {threshold_target:.1f}%")
    print(f"  {'Package':<30} {'Floor':>7} {'Measured':>9} {'Status':>10} {'Gap->target':>12}")
    print(f"  {'-' * 30} {'-' * 7:>7} {'-' * 9:>9} {'-' * 10:>10} {'-' * 11:>11}")
    for r in results:
        print(
            f"  {r.package:<30} {r.floor:>6.1f}% {r.measured_combined_pct:>8.2f}% "
            f"{r.status:>10} {r.gap_to_target:>10.1f}%"
        )
    passing = sum(1 for r in results if r.status == "PASS")
    failing = sum(1 for r in results if r.status == "FAIL")
    unmeasured = sum(1 for r in results if r.status == "UNMEASURED")
    print(
        f"\n  Summary: PASS={passing} FAIL={failing} UNMEASURED={unmeasured} "
        f"TOTAL={len(results)}"
    )


def _print_markdown(results: list[PackageResult]) -> None:
    print("| Package | Floor | Measured | Status | Gap to 84% |")
    print("| --- | ---: | ---: | :---: | ---: |")
    for r in results:
        marker = {"PASS": "[PASS]", "FAIL": "[FAIL]", "UNMEASURED": "[----]"}[r.status]
        print(
            f"| `{r.package}` | {r.floor:.1f}% | **{r.measured_combined_pct:.2f}%** "
            f"| {marker} | {r.gap_to_target:.1f}% |"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--xml", required=True, type=Path, help="Path to coverage.xml")
    parser.add_argument(
        "--floors", required=True, type=Path,
        help="Path to infrastructure/quality/coverage-floors.yaml",
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON to stdout")
    parser.add_argument("--markdown", action="store_true", help="Emit Markdown table to stdout")
    parser.add_argument(
        "--allow-unmeasured", action="store_true",
        help="UNMEASURED packages do not fail the gate (default: do not fail)",
    )
    args = parser.parse_args()

    if not args.xml.is_file():
        print(f"ERROR: coverage XML not found at {args.xml}", file=sys.stderr)
        return 2
    if not args.floors.is_file():
        print(f"ERROR: floors YAML not found at {args.floors}", file=sys.stderr)
        return 2

    results = evaluate(args.xml, args.floors)
    target_pct = float(
        yaml.safe_load(args.floors.read_text(encoding="utf-8")).get("target", 84.0)
    )

    if args.json:
        print(
            json.dumps(
                {"target": target_pct, "packages": [asdict(r) for r in results]},
                indent=2, sort_keys=True,
            )
        )
    elif args.markdown:
        _print_markdown(results)
    else:
        _print_text(results, threshold_target=target_pct)

    failing = any(r.status == "FAIL" for r in results)
    return 1 if failing else 0


if __name__ == "__main__":
    sys.exit(main())
