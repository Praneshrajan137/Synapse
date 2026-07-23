"""Make the SYNAPSE *decision-integrity uplift* mechanically visible (ADR-042, C60).

The other honesty gates prove SYNAPSE is honest, trained, calibrated, and
auditable. None of them proves it is *intelligent* — that its four-tier consensus
decisions actually beat a transparent baseline policy on business KPIs. The
``uplift`` harness (``python -m uplift.cli``) runs that closed-loop counterfactual
experiment and persists a headline uplift number; this gate is the ratchet that
stops a proven gain from silently rotting away.

It reads the measured headline uplift from the harness result artifact and
compares it to :data:`~uplift.uplift_floor.UPLIFT_FLOOR` — a single declared
numeric BASELINE constant in the exact ratchet style of
``scripts/audit/training_truth.py``:

  * measured uplift ``>= UPLIFT_FLOOR``  -> exit ``0`` (pass) (R6.3)
  * measured uplift ``<  UPLIFT_FLOOR``  -> exit ``1`` (regression), emitting the
    measured value, the floor, and a regression indication (R6.4)
  * measured uplift **unavailable**      -> exit ``2`` (a *distinct* non-zero code)
    — never a pass. Absence of proof is not proof (R6.5).

The measured uplift is read from a persisted harness result artifact (JSON) so the
gate is decoupled from a live twin run; :func:`read_measured_uplift` returns
``None`` when the artifact is missing, malformed, or carries no numeric
``headline_uplift`` — which drives the distinct "unavailable" exit path. The
``uplift.cli`` reproduction command (task 14.1) writes this artifact.

Run::

    python -m scripts.audit.uplift_truth            # human summary
    python -m scripts.audit.uplift_truth --json      # machine JSON
    python -m scripts.audit.uplift_truth --check      # exit 0/1/2 per the floor mapping
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# Ensure the repo root is importable when run as a bare script (not -m).
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from uplift.uplift_floor import UPLIFT_FLOOR  # noqa: E402

# Persisted harness result artifact. `uplift.cli` (task 14.1) writes the headline
# uplift here; the gate reads it. Kept under `artifacts/` alongside the other
# audit gates' inputs (parity with calibration_truth's ARTIFACTS_DIR).
RESULT_ARTIFACT = ROOT / "artifacts" / "uplift" / "result.json"

# Distinct exit codes (R6.3, R6.4, R6.5).
EXIT_PASS = 0
EXIT_REGRESSION = 1
EXIT_UNAVAILABLE = 2


def read_measured_uplift(artifact: Path = RESULT_ARTIFACT) -> float | None:
    """Read the measured headline uplift from a persisted harness result artifact.

    Returns the numeric ``headline_uplift`` on success, or ``None`` when the
    measurement is unavailable — the artifact is missing, unreadable, not valid
    JSON, has no ``headline_uplift`` field, or that field is not a finite number.
    A ``None`` here must map to the distinct "unavailable" exit code, never a pass.
    """
    if not artifact.is_file():
        return None
    try:
        data = json.loads(artifact.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    value = data.get("headline_uplift")
    # bool is an int subclass; reject it explicitly to avoid True -> 1.0 surprises.
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    measured = float(value)
    if not math.isfinite(measured):
        return None
    return measured


def run(*, as_json: bool = False, check: bool = False) -> int:
    measured = read_measured_uplift()
    available = measured is not None
    regression = available and measured < UPLIFT_FLOOR

    if as_json:
        print(json.dumps(
            {
                "measured_uplift": measured,
                "uplift_floor": UPLIFT_FLOOR,
                "regression": bool(regression),
            },
            indent=2,
            sort_keys=True,
        ))
    else:
        if not available:
            print(
                f"[??] uplift-truth: measured uplift UNAVAILABLE "
                f"(no readable headline_uplift at {RESULT_ARTIFACT.relative_to(ROOT).as_posix()}); "
                f"floor {UPLIFT_FLOOR}. Absence of proof is not a pass."
            )
        elif regression:
            print(
                f"[XX] uplift-truth: REGRESSION - measured uplift {measured} "
                f"< floor {UPLIFT_FLOOR}."
            )
        else:
            print(
                f"[OK] uplift-truth: measured uplift {measured} >= floor {UPLIFT_FLOOR}."
            )
        if available and not check:
            print("(ratchet - raise UPLIFT_FLOOR as verified gains land; CI fails on any regression.)")

    if check:
        if not available:
            return EXIT_UNAVAILABLE
        return EXIT_REGRESSION if regression else EXIT_PASS
    return EXIT_PASS


if __name__ == "__main__":
    sys.exit(run(as_json="--json" in sys.argv, check="--check" in sys.argv))
