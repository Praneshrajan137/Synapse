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

    # Non-vacuity enforcement (R7.2 / R7.9)
    python scripts/coverage_per_package.py --xml coverage.xml --floors ... \\
        --require-measured-floors

Floor provenance (``--require-measured-floors``)
------------------------------------------------
A floor of ``0.0`` gates nothing, so under ``--require-measured-floors`` the
gate reads two provenance fields the ratchet writes (see
``scripts/coverage_ratchet.py``) alongside each floor::

  packages/<path>:
    line: 0.0
    measured_at: null          # or an ISO-8601 UTC timestamp
    source_run: null           # or the run that measured it, e.g. gh-run-123

The mapping is:

* ``line: 0.0`` **with** a recorded ``measured_at`` -> ``VACUOUS``, which FAILs
  naming the package. Something measured it and the floor was still left at
  zero (R7.2).
* ``line: 0.0`` with ``measured_at: null`` (or the key absent) -> reported
  ``SKIP-UNMEASURED`` naming the package. Nothing has measured it yet, so there
  is no honest floor to enforce. Per I-7 a SKIP is never a PASS.
* any other floor -> the ordinary measured comparison; below the floor FAILs
  naming the package, its measured value, and its recorded floor (R7.1).

The ordering this implements is CF-3 in the design: one ``ci.yml::quality-gates``
run on ``main`` publishes ``coverage.xml``, the operator runs
``scripts/coverage_ratchet.py --apply`` (which records ``measured_at`` +
``source_run``), and only then does the non-vacuity gate become registrable.
Until that happens the flag reports SKIP for every unmeasured package rather
than claiming a pass it cannot back.
"""

from __future__ import annotations

import argparse
import json
import sys
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Final

import yaml

ROOT = Path(__file__).resolve().parents[1]

# Status vocabulary. PASS / FAIL / UNMEASURED predate --require-measured-floors
# and keep their meaning; VACUOUS and SKIP-UNMEASURED are the floor-provenance
# verdicts (R7.2, R7.9). Only FAILING_STATUSES change the exit code, and
# SKIP-UNMEASURED is deliberately not among them and is never a PASS (I-7).
STATUS_PASS: Final[str] = "PASS"
STATUS_FAIL: Final[str] = "FAIL"
STATUS_UNMEASURED: Final[str] = "UNMEASURED"
STATUS_VACUOUS: Final[str] = "VACUOUS"
STATUS_SKIP_UNMEASURED: Final[str] = "SKIP-UNMEASURED"
FAILING_STATUSES: Final[frozenset[str]] = frozenset({STATUS_FAIL, STATUS_VACUOUS})


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
    status: str  # PASS | FAIL | UNMEASURED | VACUOUS | SKIP-UNMEASURED
    measured_at: str | None = None
    source_run: str | None = None
    detail: str = ""

    @property
    def gap_to_target(self) -> float:
        return max(0.0, self.target - self.measured_combined_pct)


def _source_roots(root: ET.Element) -> list[str]:
    """Return the list of <source> root paths, normalised with forward slashes."""
    return [(s.text or "").replace("\\", "/").rstrip("/") for s in root.iter("source")]


def _candidate_exists(candidate: str) -> bool:
    """Return whether a Cobertura source/filename candidate maps to a real file.

    coverage.py may emit several <source> roots for one XML. A class filename is
    relative to exactly one of those roots, but Cobertura does not annotate which
    one. Blindly joining every source to every class makes every package appear
    to contain every file. The repo still exists when this gate runs, so file
    existence is the least lossy way to select plausible candidates.
    """
    path = Path(candidate)
    if path.is_absolute():
        return path.is_file()
    return path.is_file() or (ROOT / path).is_file()


def _classes_under(root: ET.Element, prefix: str) -> list[ET.Element]:
    """Return every <class> whose full path (source-root + filename) contains
    *prefix*. Cobertura emits one <source> root per ``--cov=`` argument; the
    <class filename> is relative to exactly one of those roots. We try source
    roots that produce a real file, then fall back to raw candidates for
    synthetic XML tests or unusual reporters.

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
        candidates = [fn, *[f"{src}/{fn}" if src else fn for src in sources]]
        existing_candidates = [
            candidate for candidate in candidates if _candidate_exists(candidate)
        ]
        paths_to_match = existing_candidates or candidates
        for full in paths_to_match:
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


def _provenance_field(raw: object) -> str | None:
    """Normalise a `measured_at` / `source_run` value to a string or None.

    PyYAML resolves an unquoted `2026-05-29` to a `datetime.date` and an
    unquoted ISO timestamp to a `datetime`, so a floors file written by hand and
    one written by the ratchet must both read the same way. An empty or
    whitespace-only string is treated as absent -- a blank field records no
    measurement, and pretending otherwise would invert the R7.2 verdict.
    """
    if raw is None:
        return None
    if isinstance(raw, str):
        return raw.strip() or None
    if isinstance(raw, (datetime, date)):
        return raw.isoformat()
    return str(raw)


def _measured_verdict(
    pct: float, floor: float, lines_total: int, branches_total: int
) -> tuple[str, str]:
    """The ordinary measured-vs-floor comparison (R7.1)."""
    if lines_total == 0 and branches_total == 0:
        return STATUS_UNMEASURED, "the coverage report carried no measurable lines"
    if pct + 1e-9 >= floor:
        return STATUS_PASS, ""
    return STATUS_FAIL, f"measured {pct:.2f}% is below the recorded floor {floor:.1f}%"


def _floor_verdict(measured_at: str | None, source_run: str | None) -> tuple[str, str]:
    """The provenance verdict for a zero floor (R7.2, R7.9).

    A zero floor with a recorded measurement is vacuous: a run measured the
    package and the floor was still left at zero, so the gate asserts nothing.
    A zero floor with no recorded measurement has never been measured; that is a
    SKIP naming the package, never a PASS.
    """
    if measured_at is None:
        return (
            STATUS_SKIP_UNMEASURED,
            "zero floor with no recorded measurement; no run has measured this "
            "package yet, so there is no floor to enforce (SKIP is not a PASS)",
        )
    attribution = f" by {source_run}" if source_run else " by an unrecorded run"
    return (
        STATUS_VACUOUS,
        f"zero floor recorded as measured at {measured_at}{attribution}; a "
        "measured package must carry a floor above zero",
    )


def evaluate(
    xml_path: Path,
    floors_path: Path,
    *,
    require_measured_floors: bool = False,
) -> list[PackageResult]:
    """Evaluate every gated package in *floors_path* against *xml_path*.

    With ``require_measured_floors`` the zero-floor provenance rules above are
    applied. Without it the behaviour is exactly what it was before task 4.1, so
    the existing `ci.yml` step is unchanged until the ordering in CF-3 allows the
    non-vacuity gate to be registered.
    """
    tree = ET.parse(xml_path)
    root = tree.getroot()
    floors_doc = yaml.safe_load(floors_path.read_text(encoding="utf-8"))
    out: list[PackageResult] = []
    for pkg_path, cfg in floors_doc.get("packages", {}).items():
        floor = float(cfg.get("line", 0.0))
        target = float(cfg.get("target", floors_doc.get("target", 84.0)))
        measured_at = _provenance_field(cfg.get("measured_at"))
        source_run = _provenance_field(cfg.get("source_run"))
        classes = _classes_under(root, pkg_path)
        lc, lt, bc, bt = _aggregate(classes)
        pct = _combined_pct(lc, lt, bc, bt)
        if require_measured_floors and floor == 0.0:
            status, detail = _floor_verdict(measured_at, source_run)
        else:
            status, detail = _measured_verdict(pct, floor, lt, bt)
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
                measured_at=measured_at,
                source_run=source_run,
                detail=detail,
            )
        )
    return out


_MARKERS: Final[dict[str, str]] = {
    STATUS_PASS: "[PASS]",
    STATUS_FAIL: "[FAIL]",
    STATUS_UNMEASURED: "[----]",
    STATUS_VACUOUS: "[FAIL]",
    STATUS_SKIP_UNMEASURED: "[SKIP]",
}


def _print_text(results: list[PackageResult], *, threshold_target: float) -> None:
    print(f"SYNAPSE per-package coverage gate -- target {threshold_target:.1f}%")
    print(f"  {'Package':<30} {'Floor':>7} {'Measured':>9} {'Status':>16} {'Gap->target':>12}")
    print(f"  {'-' * 30} {'-' * 7:>7} {'-' * 9:>9} {'-' * 16:>16} {'-' * 11:>11}")
    for r in results:
        print(
            f"  {r.package:<30} {r.floor:>6.1f}% {r.measured_combined_pct:>8.2f}% "
            f"{r.status:>16} {r.gap_to_target:>10.1f}%"
        )
    passing = sum(1 for r in results if r.status == STATUS_PASS)
    failing = sum(1 for r in results if r.status == STATUS_FAIL)
    unmeasured = sum(1 for r in results if r.status == STATUS_UNMEASURED)
    vacuous = [r for r in results if r.status == STATUS_VACUOUS]
    skipped = [r for r in results if r.status == STATUS_SKIP_UNMEASURED]
    print(
        f"\n  Summary: PASS={passing} FAIL={failing} UNMEASURED={unmeasured} "
        f"VACUOUS={len(vacuous)} SKIP-UNMEASURED={len(skipped)} TOTAL={len(results)}"
    )
    _print_findings(results)
    if skipped:
        print(
            "\n  SKIP-UNMEASURED is not a PASS. These packages are unproven until one "
            "CI run measures\n  them and `scripts/coverage_ratchet.py --apply` records "
            "the measured floor (CF-3)."
        )


def _print_findings(results: list[PackageResult]) -> None:
    """Name every package that did not pass, with the reason (R7.1, R7.2, R7.9)."""
    findings = [r for r in results if r.status != STATUS_PASS]
    if not findings:
        return
    print("")
    for r in findings:
        detail = f" -- {r.detail}" if r.detail else ""
        print(f"  {r.status}: {r.package} (floor {r.floor:.1f}%){detail}")


def _print_markdown(results: list[PackageResult]) -> None:
    print("| Package | Floor | Measured | Status | Gap to 84% |")
    print("| --- | ---: | ---: | :---: | ---: |")
    for r in results:
        marker = _MARKERS[r.status]
        print(
            f"| `{r.package}` | {r.floor:.1f}% | **{r.measured_combined_pct:.2f}%** "
            f"| {marker} | {r.gap_to_target:.1f}% |"
        )
    for r in results:
        if r.status in (STATUS_VACUOUS, STATUS_SKIP_UNMEASURED):
            print(f"\n- **{r.status}** `{r.package}` -- {r.detail}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--xml", required=True, type=Path, help="Path to coverage.xml")
    parser.add_argument(
        "--floors",
        required=True,
        type=Path,
        help="Path to infrastructure/quality/coverage-floors.yaml",
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON to stdout")
    parser.add_argument("--markdown", action="store_true", help="Emit Markdown table to stdout")
    parser.add_argument(
        "--allow-unmeasured",
        action="store_true",
        help="UNMEASURED packages do not fail the gate (default: do not fail)",
    )
    parser.add_argument(
        "--require-measured-floors",
        action="store_true",
        help=(
            "Enforce floor non-vacuity (R7.2): a gated package whose floor is 0.0 "
            "with a recorded measured_at FAILs naming it; one with measured_at null "
            "is reported SKIP-UNMEASURED naming it, never PASS"
        ),
    )
    args = parser.parse_args()

    if not args.xml.is_file():
        print(f"ERROR: coverage XML not found at {args.xml}", file=sys.stderr)
        return 2
    if not args.floors.is_file():
        print(f"ERROR: floors YAML not found at {args.floors}", file=sys.stderr)
        return 2

    results = evaluate(
        args.xml, args.floors, require_measured_floors=args.require_measured_floors
    )
    target_pct = float(yaml.safe_load(args.floors.read_text(encoding="utf-8")).get("target", 84.0))

    if args.json:
        print(
            json.dumps(
                {
                    "target": target_pct,
                    "require_measured_floors": bool(args.require_measured_floors),
                    "packages": [asdict(r) for r in results],
                    "vacuous_floors": sorted(
                        r.package for r in results if r.status == STATUS_VACUOUS
                    ),
                    "unmeasured_floors": sorted(
                        r.package for r in results if r.status == STATUS_SKIP_UNMEASURED
                    ),
                },
                indent=2,
                sort_keys=True,
            )
        )
    elif args.markdown:
        _print_markdown(results)
    else:
        _print_text(results, threshold_target=target_pct)

    failing = any(r.status in FAILING_STATUSES for r in results)
    return 1 if failing else 0


if __name__ == "__main__":
    sys.exit(main())
