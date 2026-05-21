"""SYNAPSE FE — FE-INV registry checker.

Validates `frontend/spec/fe_invariants.yaml`:
  * every entry has at least one implementation file that exists
  * every entry has at least one test file that exists
  * statuses are drawn from a closed set

Run from the repo root::

    python frontend/spec/check_fe_invariants.py
"""

from __future__ import annotations

import sys
from pathlib import Path

try:
    import yaml  # type: ignore[import-untyped]
except ModuleNotFoundError as exc:  # pragma: no cover - hard fail in CI
    sys.stderr.write("pyyaml is required: pip install pyyaml\n")
    raise SystemExit(2) from exc

VALID_STATUS = {"enforced", "scheduled_p1", "scheduled_p2", "scheduled_p3", "scheduled_p4"}
ROOT = Path(__file__).resolve().parents[2]
SPEC = ROOT / "frontend" / "spec" / "fe_invariants.yaml"


def main() -> int:
    data = yaml.safe_load(SPEC.read_text(encoding="utf-8"))
    invariants = data.get("invariants", [])
    if not invariants:
        sys.stderr.write("No invariants found in fe_invariants.yaml\n")
        return 1

    errors: list[str] = []
    for inv in invariants:
        inv_id = inv.get("id", "<missing-id>")
        if inv.get("status") not in VALID_STATUS:
            errors.append(f"{inv_id}: invalid status {inv.get('status')!r}")
        implementations = inv.get("implementations") or []
        tests = inv.get("tests") or []
        if not implementations:
            errors.append(f"{inv_id}: no implementations listed")
        if not tests:
            errors.append(f"{inv_id}: no tests listed")
        for path in implementations + tests:
            if not (ROOT / path).exists():
                errors.append(f"{inv_id}: missing file {path}")

    if errors:
        sys.stderr.write("FE-INV registry violations:\n")
        for err in errors:
            sys.stderr.write(f"  - {err}\n")
        return 1

    print(f"FE-INV registry OK ({len(invariants)} invariants)")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
