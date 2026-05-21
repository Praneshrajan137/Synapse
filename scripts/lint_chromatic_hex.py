#!/usr/bin/env python3
"""Flag raw colour literals in frontend component source (INV-CLR-009).

Every hue must be earned: colour reaches a component only through a chromatic
token (``var(--color-*)``). This is the SYNAPSE Chromatic System's ``no-raw-hex``
guard, invoked by the pre-commit hook of the same name and by CI. A line may
opt out with a trailing ``chromatic-allow`` comment.
"""

from __future__ import annotations

import re
import sys

_HEX = re.compile(r"#[0-9a-fA-F]{3,8}\b")
_FUNC = re.compile(r"\b(?:rgba?|hsla?)\s*\(")


def scan(path: str) -> list[str]:
    """Return human-readable violation messages for one file."""
    findings: list[str] = []
    try:
        with open(path, encoding="utf-8") as handle:
            lines = handle.read().splitlines()
    except OSError:
        return findings
    for number, line in enumerate(lines, start=1):
        if "chromatic-allow" in line:
            continue
        if _HEX.search(line) or _FUNC.search(line):
            findings.append(
                f"FAIL {path}:{number}: raw colour literal — "
                f"use a chromatic token var(--color-*) (INV-CLR-009)"
            )
    return findings


def main(paths: list[str]) -> int:
    """Scan every path; exit non-zero if any raw colour literal is found."""
    violations: list[str] = []
    for path in paths:
        violations.extend(scan(path))
    for message in violations:
        print(message)
    if violations:
        print(f"\n{len(violations)} raw colour literal(s) — see INV-CLR-009 / ADR-025.")
        return 1
    print("OK no raw colour literals (INV-CLR-009)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
