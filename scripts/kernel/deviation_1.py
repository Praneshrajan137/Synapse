"""Deviation 1: the release world calibrated by the other reading, and freeze W's numbers on it.

Truth session 6, decision S6-D-03 (the operator, 2026-11-24, after freeze W). Freeze W's driver
(``scripts/kernel/tune_incumbent.py``, frozen) stops the shelf-life calibration as soon as the
incumbent's waste share enters [2.7%, 10.9%]. The session-5 gate's words, "bisected in log scale
toward 5.46%, at most six iterations", do not say whether the bisection stops there; the operator
chose the other reading. PREREG-1 section 2 says any recalibration "happens before freeze W, never
after"; its sections 5 and 11 make a later change a deviation, reported "on both worlds, the frozen
one primary". So nothing here edits a frozen file: it writes a second world, W-d1, with its
incumbent tables and report, beside freeze W's.

The reading, fixed in the session-6 gate (stage A2) before this script first ran:

1. Start from the uncalibrated world (the fit script re-run into a new path) and check it: scaled by
   ``sqrt(0.5)``, the scale freeze W chose, it must equal freeze W's world, provenance aside.
2. Freeze W's calibration loop with one change: it does not stop on entering the band; it bisects
   the log scale toward 5.46% (a share below it moves to shorter shelf lives, above it to longer)
   for the frozen six steps after scale 1, in the frozen bracket [0.5, 2], with the same tuning
   seeds, tuner, measure and rounding. Steps 0 and 1 must reproduce freeze W's report exactly.
3. W-d1's scale is the evaluated scale whose share is closest to 5.46% (ties: the larger scale).
4. Everything else freeze W fixed is the frozen driver's own ``main`` run on W-d1, writing new
   paths; its first step measures W-d1's share inside the band and so does not recalibrate.

    python -m scripts.kernel.deviation_1 --uncalibrated PATH

writes only ``synapse_kernel/worlds/release_world_d1.json``, ``incumbent_tables_d1.json`` and
``docs/truth/world/incumbent-report-d1.json``, and refuses any path freeze W lists.
"""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import math
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final

import numpy as np

from scripts.kernel import tune_incumbent as frozen
from synapse_kernel.release import seeds
from synapse_kernel.release.harness import price, scenarios, tune_incumbent
from synapse_kernel.release.incumbent import Incumbent
from synapse_kernel.release.integrity import read_sums
from synapse_kernel.release.world import load_release_world, world_to_document

if TYPE_CHECKING:
    from collections.abc import Callable

    from synapse_kernel.release.world import ReleaseWorld

ROOT: Final[Path] = Path(__file__).resolve().parents[2]
WORLD_OUT: Final[Path] = ROOT / "synapse_kernel/worlds/release_world_d1.json"
TABLES_OUT: Final[Path] = ROOT / "synapse_kernel/worlds/incumbent_tables_d1.json"
REPORT_OUT: Final[Path] = ROOT / "docs/truth/world/incumbent-report-d1.json"
FROZEN_WORLD: Final[Path] = ROOT / "synapse_kernel/worlds/release_world.json"
FROZEN_REPORT: Final[Path] = ROOT / "docs/truth/world/incumbent-report.json"
FREEZE_W_SUMS: Final[Path] = ROOT / "docs/truth/sealed/SHA256SUMS-W"
#: The scale freeze W chose: one log-bisection step from 1 in the bracket [0.5, 2].
FREEZE_W_SCALE: Final[float] = math.sqrt(frozen.SCALE_BRACKET[0] * 1.0)
READING: Final[str] = (
    "deviation 1 (truth session 6, S6-D-03): the log bisection toward 5.46% does not stop on "
    "entering [2.7%, 10.9%]; it runs the six frozen steps after scale 1 in the bracket [0.5, 2], a "
    "share below 5.46% moving to shorter lives and above to longer, and keeps the evaluated scale "
    "whose share is closest to 5.46% (ties: the larger scale)"
)

#: One calibration step: ``(scale, better version, its waste share, per-version tuning record)``.
Step = dict[str, Any]


def refuse_frozen(paths: list[Path], sums: Path = FREEZE_W_SUMS) -> None:
    """Refuse to write any file freeze W lists (a deviation adds files; it never edits them).

    Raises:
        SystemExit: A path is one of freeze W's frozen files.
    """
    frozen_files = {(ROOT / name).resolve() for name in read_sums(sums)}
    for path in paths:
        if path.resolve() in frozen_files:
            raise SystemExit(f"REFUSED: {path} is a frozen file of freeze W")


def frozen_world_check(uncalibrated: ReleaseWorld, frozen_world: ReleaseWorld) -> bool:
    """Whether scaling the uncalibrated world by freeze W's scale gives freeze W's world.

    Compared as documents, every field but ``provenance`` (which freeze W's driver rewrote).
    """
    mine = world_to_document(frozen.scaled(uncalibrated, FREEZE_W_SCALE))
    theirs = world_to_document(frozen_world)
    mine.pop("provenance")
    theirs.pop("provenance")
    return mine == theirs


def measure_share(world: ReleaseWorld, scale: float) -> Step:
    """Freeze W's calibration measure at ``scale``, exactly as its driver computes it.

    I1-N and I2-N tuned on cell N's tuning seeds; the better (lower mean J, ties to the name) gives
    the share: units discarded over units sold, the mean over the tuning replicates.
    """
    tuning = seeds.explore_seeds(seeds.TUNING)
    current = frozen.scaled(world, scale) if scale != 1.0 else world
    batch = scenarios(current, "N", tuning)
    trial: dict[str, tuple[float, float, int]] = {}
    for aware, tag in ((False, "I1"), (True, "I2")):
        trial_tables, trial_result = tune_incumbent(current, f"{tag}-N", aware, [batch])
        trial_priced = price(current, batch, Incumbent(current, trial_tables))
        trial[tag] = (
            trial_priced.mean_cost,
            float(np.mean(trial_priced.waste)),
            trial_result.replicate_evaluations,
        )
    better = min(trial, key=lambda t: (trial[t][0], t))
    return {"scale": scale, "better": better, "waste_share": trial[better][1], "tuned": trial}


def bisect_toward_target(
    measure: Callable[[float], Step],
    target: float = frozen.IFPA_SHRINK,
    steps: int = frozen.MAX_CALIBRATIONS,
    bracket: tuple[float, float] = frozen.SCALE_BRACKET,
) -> list[Step]:
    """The frozen loop's bisection, pivoting on ``target`` and never stopping early.

    Scale 1 first, then ``steps`` log-bisection steps in ``bracket``: a share above ``target``
    makes the current scale the lower end (longer lives next), below it the upper end.
    """
    out: list[Step] = []
    scale, lo, hi = 1.0, None, None
    for attempt in range(steps + 1):
        step = measure(scale)
        out.append(step)
        print(
            f"deviation 1, step {attempt}: scale {scale:.6f} -> {step['better']} "
            f"waste share {step['waste_share']:.4f}",
            flush=True,
        )
        if attempt == steps:
            break
        if step["waste_share"] > target:
            lo = scale
            hi = hi if hi is not None else bracket[1]
        else:
            hi = scale
            lo = lo if lo is not None else bracket[0]
        scale = math.sqrt(lo * hi)
    return out


def closest(steps: list[Step], target: float = frozen.IFPA_SHRINK) -> Step:
    """The evaluated step whose share is closest to ``target``; ties go to the larger scale."""
    return min(steps, key=lambda s: (abs(s["waste_share"] - target), -s["scale"]))


def reproduces_freeze_w(steps: list[Step], report: dict[str, Any]) -> bool:
    """Whether the first two steps equal freeze W's recorded calibration, number for number."""
    recorded = report["calibration"]
    if len(recorded) != 2 or len(steps) < 2:
        return False
    for mine, theirs in zip(steps[:2], recorded, strict=True):
        if mine["scale"] != theirs["scale"] or mine["better"] != theirs["better"]:
            return False
        if mine["waste_share"] != theirs["waste_share"]:
            return False
        for tag, values in mine["tuned"].items():
            if [float(values[0]), float(values[1]), int(values[2])] != theirs["tuned"][tag]:
                return False
    return True


def world_d1(uncalibrated: ReleaseWorld, chosen: Step, steps: list[Step]) -> ReleaseWorld:
    """The uncalibrated world scaled by the chosen step, its provenance saying how."""
    key = "items.shelf_life_hours"
    old = uncalibrated.provenance[key]
    scale = float(chosen["scale"])
    history = "; ".join(f"{s['waste_share']:.2%} at {s['scale']:.4f}" for s in steps)
    hours = sorted({max(12, round(item.shelf_life_hours * scale)) for item in uncalibrated.items})
    note = (
        f"{old.source}. Calibrated after freeze W by {READING}: the incumbent's waste share in N "
        f"(units discarded over units sold, tuning seeds) was {history}, so every shelf life is "
        f"times {scale!r}, rounded to whole hours: {', '.join(str(h) for h in hours)} hours. "
        f"Freeze W's world is the primary world; this one is reported beside it"
    )
    provenance = {**uncalibrated.provenance, key: dataclasses.replace(old, source=note)}
    scaled = frozen.scaled(uncalibrated, scale)
    return dataclasses.replace(scaled, name=f"{uncalibrated.name}-d1", provenance=provenance)


def sha256_text(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m scripts.kernel.deviation_1")
    parser.add_argument(
        "--uncalibrated",
        type=Path,
        required=True,
        help="the fit script's world, before calibration",
    )
    parser.add_argument("--world-out", type=Path, default=WORLD_OUT)
    parser.add_argument("--tables-out", type=Path, default=TABLES_OUT)
    parser.add_argument("--report-out", type=Path, default=REPORT_OUT)
    args = parser.parse_args(argv)
    refuse_frozen([args.world_out, args.tables_out, args.report_out])
    uncalibrated = load_release_world(args.uncalibrated)
    if not frozen_world_check(uncalibrated, load_release_world(FROZEN_WORLD)):
        print("REFUSED: scaling this world by freeze W's scale does not give freeze W's world")
        return 2
    freeze_w_report = json.loads(FROZEN_REPORT.read_text(encoding="utf-8"))
    steps = bisect_toward_target(lambda scale: measure_share(uncalibrated, scale))
    if not reproduces_freeze_w(steps, freeze_w_report):
        print("REFUSED: steps 0 and 1 do not reproduce freeze W's calibration")
        return 3
    chosen = closest(steps)
    world = world_d1(uncalibrated, chosen, steps)
    args.world_out.parent.mkdir(parents=True, exist_ok=True)
    args.world_out.write_text(
        json.dumps(world_to_document(world), sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    code = frozen.main(
        [
            "--world",
            str(args.world_out),
            "--tables-out",
            str(args.tables_out),
            "--report-out",
            str(args.report_out),
        ]
    )
    if code != 0:
        return code
    report = json.loads(args.report_out.read_text(encoding="utf-8"))
    if report.get("calibration_scale") != 1.0:
        print("REFUSED: the frozen driver recalibrated W-d1; its share left the band")
        return 4
    report["deviation_1"] = {
        "decision": "S6-D-03",
        "reading": READING,
        "steps": steps,
        "scale": chosen["scale"],
        "steps_0_1_reproduce_freeze_w": True,
        "uncalibrated_world_sha256": sha256_text(args.uncalibrated),
        "uncalibrated_scaled_equals_freeze_w_world": True,
        "world_d1_sha256": sha256_text(args.world_out),
    }
    args.report_out.write_text(
        json.dumps(report, sort_keys=True, indent=1) + "\n", encoding="utf-8"
    )
    print(json.dumps({"deviation_1_scale": chosen["scale"], "share": chosen["waste_share"]}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
