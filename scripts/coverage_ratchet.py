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

Floor provenance (R7.9)
-----------------------
``--apply`` writes two fields beside every bumped floor::

  packages/<path>:
    line: 61.5
    measured_at: "2026-05-30T09:14:00Z"
    source_run: "gh-run-1234567890"

``measured_at`` is what makes R7.2's non-vacuity rule decidable:
``scripts/coverage_per_package.py --require-measured-floors`` FAILs a package
whose floor is ``0.0`` *and* carries a ``measured_at``, and reports
``SKIP-UNMEASURED`` when ``measured_at`` is null. The same null-vs-recorded
semantics are used by ``infrastructure/quality/ratchets.json``
(``status: measured|unmeasured``), so the two files agree by construction.

Because the provenance record is load-bearing, ``--apply`` refuses to invent
one: it needs ``--source-run`` (or ``GITHUB_RUN_ID`` in the environment) naming
the run that produced the coverage report. Writing a floor with a fabricated
run id would be exactly the fabricated-evidence failure I-7 forbids.

Usage::

    python scripts/coverage_ratchet.py                                  # dry-run
    python scripts/coverage_ratchet.py --apply --source-run gh-run-42    # write floors back
    python scripts/coverage_ratchet.py --margin 5 --apply --source-run … # require larger gain
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]

if not __package__:
    # Executed as `python scripts/coverage_ratchet.py`, so `scripts` is not on the
    # import path yet. Put the repo root there and import the sibling under its
    # real module name -- a bare `import coverage_per_package` would bind the same
    # file to two module names and mypy rejects that.
    sys.path.insert(0, str(ROOT))

from scripts.coverage_per_package import evaluate  # noqa: E402


class ProvenanceUnavailable(RuntimeError):
    """Raised when a floor bump has no run to attribute the measurement to."""


@dataclass(frozen=True)
class FloorProvenance:
    """The record written beside a bumped floor.

    ``measured_at`` is an ISO-8601 UTC timestamp; ``source_run`` names the run
    that produced the coverage report the bump was derived from.
    """

    measured_at: str
    source_run: str


def _utc_now() -> str:
    return (
        datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    )


def _run_from_env() -> str | None:
    """Derive a run id from the GitHub Actions environment, if we are in one."""
    run_id = os.environ.get("GITHUB_RUN_ID", "").strip()
    return f"gh-run-{run_id}" if run_id else None


def resolve_provenance(
    *, measured_at: str | None = None, source_run: str | None = None
) -> FloorProvenance:
    """Build the provenance record, or refuse rather than invent one (I-7)."""
    run = (source_run or "").strip() or _run_from_env()
    if not run:
        raise ProvenanceUnavailable(
            "no run to attribute this measurement to. Pass --source-run "
            "(e.g. --source-run gh-run-1234567890) or set GITHUB_RUN_ID. R7.9 "
            "records which run measured a package; inventing one would fabricate "
            "provenance."
        )
    return FloorProvenance(measured_at=(measured_at or "").strip() or _utc_now(), source_run=run)


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


# ---------------------------------------------------------------------------
# Floors-YAML editing. We edit the text rather than round-tripping through
# PyYAML because a round-trip drops every comment, and the floors file's
# per-package `note:` provenance is the reason anyone can read it.
# ---------------------------------------------------------------------------


def _split_lines(text: str) -> tuple[list[str], str, bool]:
    """Split *text* into lines, preserving its newline style and final newline."""
    newline = "\r\n" if "\r\n" in text else "\n"
    trailing = text.endswith(newline)
    body = text[: -len(newline)] if trailing else text
    return body.split(newline), newline, trailing


def _find_package_header(lines: list[str], package: str) -> int:
    pattern = re.compile(rf"^  {re.escape(package)}:\s*$")
    hits = [i for i, line in enumerate(lines) if pattern.match(line)]
    if not hits:
        raise RuntimeError(f"Could not find `{package}:` in floors YAML")
    if len(hits) > 1:
        raise RuntimeError(f"Ambiguous match for `{package}:` in floors YAML ({len(hits)} hits)")
    return hits[0]


def _block_end(lines: list[str], header: int) -> int:
    """Index one past the last line belonging to the package block at *header*.

    A block continues over blank lines and lines indented by four spaces or
    more; a two-space-indented key or comment starts the next entry.
    """
    end = header + 1
    while end < len(lines) and (not lines[end].strip() or lines[end].startswith("    ")):
        end += 1
    return end


def _find_key(lines: list[str], start: int, end: int, key: str) -> int | None:
    pattern = re.compile(rf"^    {re.escape(key)}:")
    for index in range(start, end):
        if pattern.match(lines[index]):
            return index
    return None


def rewrite_floor_entry(
    text: str,
    package: str,
    new_floor: float,
    provenance: FloorProvenance | None = None,
) -> str:
    """Rewrite the `line:` value under `packages.<package>:` to *new_floor* and,
    when *provenance* is given, upsert `measured_at:` and `source_run:` beside it.

    Comments and field order are preserved; the provenance keys are inserted
    immediately after `line:` when absent and overwritten in place when present.
    Both values are quoted so PyYAML reads them back as strings rather than
    resolving a bare timestamp into a `datetime`.
    """
    lines, newline, trailing = _split_lines(text)
    header = _find_package_header(lines, package)
    end = _block_end(lines, header)
    line_index = _find_key(lines, header + 1, end, "line")
    if line_index is None:
        raise RuntimeError(f"Could not find `line:` under `{package}:` in floors YAML")
    lines[line_index] = re.sub(
        r"^(\s*line:\s*)([0-9.]+)", rf"\g<1>{new_floor:.1f}", lines[line_index]
    )

    if provenance is not None:
        anchor = line_index
        fields = (
            ("measured_at", provenance.measured_at),
            ("source_run", provenance.source_run),
        )
        for key, value in fields:
            rendered = f'    {key}: "{value}"'
            existing = _find_key(lines, header + 1, end, key)
            if existing is None:
                lines.insert(anchor + 1, rendered)
                anchor += 1
                end += 1
            else:
                lines[existing] = rendered
                anchor = existing

    out = newline.join(lines)
    return out + newline if trailing else out


def rewrite_floor(text: str, package: str, new_floor: float) -> str:
    """Bump a floor without recording provenance (kept for callers that only
    move the number; ``--apply`` always records provenance)."""
    return rewrite_floor_entry(text, package, new_floor, None)


def _verify_provenance_written(
    text: str, packages: list[str], provenance: FloorProvenance
) -> list[str]:
    """Return the packages whose provenance did not land, by re-reading the YAML."""
    doc = yaml.safe_load(text) or {}
    entries = doc.get("packages", {}) or {}
    missing: list[str] = []
    for package in packages:
        entry = entries.get(package) or {}
        if (
            str(entry.get("measured_at") or "") != provenance.measured_at
            or str(entry.get("source_run") or "") != provenance.source_run
        ):
            missing.append(package)
    return missing


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
    parser.add_argument(
        "--source-run",
        default=None,
        help=(
            "Run that produced the coverage report, recorded as `source_run` "
            "beside each bumped floor (default: gh-run-$GITHUB_RUN_ID). Required "
            "by --apply"
        ),
    )
    parser.add_argument(
        "--measured-at",
        default=None,
        help=(
            "ISO-8601 UTC timestamp recorded as `measured_at` beside each bumped "
            "floor (default: now)"
        ),
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
        print(
            "\nDry-run only — rerun with --apply --source-run <run id> to write the "
            "floors YAML back."
        )
        return 0

    try:
        provenance = resolve_provenance(
            measured_at=args.measured_at, source_run=args.source_run
        )
    except ProvenanceUnavailable as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    text = args.floors.read_text(encoding="utf-8")
    for pkg, _old, new in proposals:
        text = rewrite_floor_entry(text, pkg, new, provenance)
    # Validate the YAML still parses round-trip, and that the provenance landed.
    yaml.safe_load(text)
    missing = _verify_provenance_written(text, [pkg for pkg, _o, _n in proposals], provenance)
    if missing:
        print(
            "ERROR: provenance did not land for: " + ", ".join(missing) + " -- floors "
            "not written",
            file=sys.stderr,
        )
        return 2
    args.floors.write_text(text, encoding="utf-8")
    try:
        rel = args.floors.resolve().relative_to(ROOT)
    except ValueError:
        rel = args.floors  # absolute or off-tree — print as-is
    print(
        f"\nWrote {len(proposals)} bump(s) to {rel} "
        f"(measured_at={provenance.measured_at}, source_run={provenance.source_run})"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
