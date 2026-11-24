"""Sealed files are only ever added: ``python -m scripts.audit.sealed_add_only <base ref>``.

``check_prereg.py`` and ``check_freeze_w.py`` recompute every digest against their sums files, so
they catch an edit to a frozen file, but not an edit made together with its line in the sums file.
This closes that: between ``<base ref>`` and ``HEAD``, a file under ``docs/truth/sealed/`` may be
added, never modified, renamed or deleted, with two exceptions that the seals expect to change:
``DEVIATIONS.md`` (PREREG-1 section 11 appends deviations to it) and the OpenTimestamps proofs
(``*.ots``, upgraded once their Bitcoin attestation exists). A deviation never edits a sealed or
frozen file; it adds files beside them (PREREG-1 section 5: "reported on both worlds").

Standard library and git only. Exit 0 when the rule holds, 1 when it does not, 2 on a usage error.
"""

from __future__ import annotations

import re
import subprocess
import sys
from typing import Final

SEALED: Final[str] = "docs/truth/sealed/"
EDITABLE: Final[re.Pattern[str]] = re.compile(r"^docs/truth/sealed/(DEVIATIONS\.md|[^/]+\.ots)$")


def violations(name_status: str) -> list[str]:
    """The lines of ``git diff --name-status --no-renames`` output that break the rule."""
    out: list[str] = []
    for line in name_status.splitlines():
        if not line.strip():
            continue
        status, path = line.split("\t", 1)
        if status == "A" or (status == "M" and EDITABLE.match(path)):
            continue
        out.append(line)
    return out


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print(__doc__)
        return 2
    diff = subprocess.run(
        ["git", "diff", "--name-status", "--no-renames", f"{argv[0]}...HEAD", "--", SEALED],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    found = violations(diff)
    for line in found:
        print(f"FAIL a sealed file was changed or removed: {line}")
    if found:
        print(
            "A deviation adds files beside the sealed ones; it never edits them (PREREG-1 s.5, 11)."
        )
        return 1
    print(f"OK files under {SEALED} were only added (or an allowed file was appended to)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
