"""Fit the surge threshold, then look at what it detects (truth session 6, gate item 6).

For each world (W primary, W-d1 secondary), the instrument ``surge_calibration`` (the lane incumbent
deciding while the store's surge detector watches) runs in a challenger's process of its
own, one fresh child per replicate, with both replays (:mod:`scripts.challengers.isolate`), on cells
N, S2 and S3 at the tuning seeds (k 0-31) and the first development range D1 (k 64-191). The
threshold is the smallest power of two strictly above the largest evidence seen there: at it, the
detector, fed exactly what it sees in operation (censored sales and all), raises no alarm at all in
those runs. No J enters, and no cell with a surge.

Then, on D1 only, cell S1 (a look, not a fit): the first decision at or after the onset at which the
store's evidence reaches the threshold, the delay in hours and the share of surges detected before
their end plus a day; alarms before the onset and after the surge has left the 72-hour memory; while
alarmed, the share of deciding items attributed to the surge (posterior probability at least one
half), surged and unsurged, during and after it, and the planned multiplier against the true size;
and the detection at every power of two from 2^4 to 2^40, a design curve that shows the trade-off
the rule fixes rather than chooses.

Writes ``docs/truth/challengers/surge-threshold.json`` and, per world, the parameter file the surge
component is built from in stage B's measurements, ``docs/truth/challengers/params-b-<world>.json``.

Run: ``python -m scripts.challengers.calibrate_surge`` (about 15 minutes a world on 10 workers).
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import time
from pathlib import Path
from typing import Any

import numpy as np

from scripts.challengers import child
from scripts.challengers.isolate import Spec, run_many
from synapse_kernel.challengers.shelf import LaneIncumbent
from synapse_kernel.release import integrity, seeds
from synapse_kernel.release.harness import price, scenarios
from synapse_kernel.release.scenario import build_scenario

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs" / "truth" / "challengers"
WORLDS = ("W", "W-d1")
QUIET_CELLS = ("N", "S2", "S3")
TUNING = range(0, 32)
D1 = range(64, 192)
DESIGN_LOG2 = range(4, 41)
#: A surged item counts as detected if its alarm comes before the surge's end plus this many hours.
DETECT_WITHIN_HOURS = 24


def decision_schedule(world: Any) -> list[tuple[int, list[int]]]:
    """Every decision hour of the horizon with its deciding items, as the frozen engine runs it."""
    supplier_index = {s.name: j for j, s in enumerate(world.suppliers)}
    item_supplier = np.array([supplier_index[item.supplier] for item in world.items])
    out: list[tuple[int, list[int]]] = []
    for hour in range(world.horizon_hours):
        deciding = [j for j, s in enumerate(world.suppliers) if hour % 24 in s.cutoff_hours]
        if deciding:
            out.append((hour, np.nonzero(np.isin(item_supplier, deciding))[0].tolist()))
    return out


def threshold_above(largest: float) -> float:
    """The smallest power of two strictly above ``largest``."""
    _, exponent = math.frexp(largest)
    return math.ldexp(1.0, exponent)


def evidence_trace(result: dict[str, Any], schedule: list[tuple[int, list[int]]]) -> list[float]:
    """The store's evidence at each decision of one replicate, from its report."""
    evidence = result["report"]["evidence"]
    if len(evidence) != len(schedule) or any(len(row) != 1 for row in evidence):
        raise RuntimeError("the instrument's trace does not match the engine's decision schedule")
    return [float(row[0]) for row in evidence]


def _checked(results: list[dict[str, Any]], world: Any, tables: Any, cell: str) -> None:
    """Refuse unless both replays held and the instrument ordered exactly as the lane incumbent."""
    if not all(r["outcome_replay"] is True and r["decision_replay"] is True for r in results):
        raise RuntimeError(f"a replay failed in cell {cell}")
    for start in range(0, len(results), 32):
        chunk = results[start : start + 32]
        lane = LaneIncumbent(world, tables["I2-P"], tables["I2-L"])
        costs = price(world, scenarios(world, cell, [r["seed"] for r in chunk]), lane).costs
        if [r["cost"] for r in chunk] != [float(c) for c in costs]:
            raise RuntimeError(f"the instrument did not order as the lane incumbent in cell {cell}")


def quiet_cell(
    label: str, world: Any, tables: Any, cell: str, ks: list[int], workers: int
) -> dict[str, Any]:
    """The largest evidence the instrument sees in one cell without a surge, and where."""
    seed_of = {seeds.explore_seed(k): k for k in ks}
    t0 = time.perf_counter()
    results = run_many(Spec("surge_calibration", label), cell, list(seed_of), workers)
    seconds = time.perf_counter() - t0
    _checked(results, world, tables, cell)
    schedule = decision_schedule(world)
    best = (0.0, -1, -1)
    for r in results:
        trace = evidence_trace(r, schedule)
        for (hour, _), value in zip(schedule, trace, strict=True):
            if value > best[0]:
                best = (value, seed_of[r["seed"]], hour)
        if max(max(trace), 1.0) != r["report"]["largest_evidence"]:
            raise RuntimeError("the report's largest evidence is not its trace's")
    return {
        "replicates": len(results),
        "largest_evidence": best[0],
        "largest_log2": math.log2(best[0]),
        "at": {"k": best[1], "hour": best[2]},
        "seconds": round(seconds, 1),
    }


def _share(hits: int, total: int) -> float | None:
    return round(hits / total, 4) if total else None


def _quartiles(xs: list[float]) -> dict[str, float] | None:
    if not xs:
        return None
    q = np.quantile(np.asarray(xs), [0.25, 0.5, 0.75])
    return {
        "p25": float(q[0]),
        "median": float(q[1]),
        "p75": float(q[2]),
        "mean": statistics.fmean(xs),
    }


def s1_look(
    label: str, world: Any, tables: Any, ks: list[int], threshold: float, workers: int
) -> dict[str, Any]:
    """What the fitted threshold detects in cell S1 on D1, and what every power of two would."""
    seed_of = {seeds.explore_seed(k): k for k in ks}
    t0 = time.perf_counter()
    results = run_many(Spec("surge_calibration", label), "S1", list(seed_of), workers)
    seconds = time.perf_counter() - t0
    _checked(results, world, tables, "S1")
    schedule = decision_schedule(world)
    delays: list[float] = []
    before_peak: list[float] = []  # per replicate: the largest evidence before the onset
    first_cross: list[list[float | None]] = []  # per replicate: the delay at each design level
    counts = dict.fromkeys(
        (
            "alarmed_before_onset",
            "alarmed_after_memory",
            "surged_attributed",
            "surged_alarmed",
            "unsurged_attributed",
            "unsurged_alarmed",
            "surged_after_end_attributed",
            "surged_after_end_alarmed",
        ),
        0,
    )
    size_ratio: list[float] = []
    for r in results:
        shock = build_scenario(world, "S1", r["seed"]).shock
        surged = set(shock.items)
        trace = evidence_trace(r, schedule)
        probs, sizes = r["report"]["prob"], r["report"]["sizes"]
        early = [v for (h, _), v in zip(schedule, trace, strict=True) if h < shock.onset_hour]
        before_peak.append(max([1.0, *early]))
        window = [
            (h, v)
            for (h, _), v in zip(schedule, trace, strict=True)
            if shock.onset_hour <= h < shock.end_hour + DETECT_WITHIN_HOURS
        ]
        hit = next((h for h, v in window if v >= threshold), None)
        if hit is not None:
            delays.append(hit - shock.onset_hour)
        first_cross.append(
            [
                next((h - shock.onset_hour for h, v in window if v >= math.ldexp(1.0, j)), None)
                for j in DESIGN_LOG2
            ]
        )
        for d, ((hour, items), value) in enumerate(zip(schedule, trace, strict=True)):
            alarmed = value >= threshold
            if alarmed and hour < shock.onset_hour:
                counts["alarmed_before_onset"] += 1
            if alarmed and hour >= shock.end_hour + 72:
                counts["alarmed_after_memory"] += 1
            if not alarmed or hour < shock.onset_hour:
                continue
            for item, prob, size in zip(items, probs[d][0], sizes[d][0], strict=True):
                on = int(prob >= 0.5)
                if item in surged and hour < shock.end_hour:
                    counts["surged_alarmed"] += 1
                    counts["surged_attributed"] += on
                    if on:
                        size_ratio.append(size / shock.size)
                elif item in surged:
                    counts["surged_after_end_alarmed"] += 1
                    counts["surged_after_end_attributed"] += on
                else:
                    counts["unsurged_alarmed"] += 1
                    counts["unsurged_attributed"] += on
    n = len(results)
    curve = []
    for j, log2 in enumerate(DESIGN_LOG2):
        hits = [h for f in first_cross if (h := f[j]) is not None]
        curve.append(
            {
                "log2": log2,
                "detected_share": _share(len(hits), n),
                "median_delay_hours": statistics.median(hits) if hits else None,
                "replicates_alarmed_before_onset": sum(
                    1 for p in before_peak if p >= math.ldexp(1.0, log2)
                ),
            }
        )
    return {
        "replicates": n,
        "detected": len(delays),
        "detected_share": _share(len(delays), n),
        "detected_within_hours_after_end": DETECT_WITHIN_HOURS,
        "delay_hours": _quartiles(delays),
        "replicates_alarmed_before_onset": sum(1 for p in before_peak if p >= threshold),
        "decisions": counts,
        "attribution_while_alarmed": {
            "surged_during_surge": _share(counts["surged_attributed"], counts["surged_alarmed"]),
            "unsurged": _share(counts["unsurged_attributed"], counts["unsurged_alarmed"]),
            "surged_after_end": _share(
                counts["surged_after_end_attributed"], counts["surged_after_end_alarmed"]
            ),
        },
        "planned_multiplier_over_true_size": _quartiles(size_ratio),
        "design_curve": curve,
        "seconds": round(seconds, 1),
    }


def fit(label: str, tuning: range, d1: range, workers: int) -> dict[str, Any]:
    """One world's threshold and its S1 look."""
    world, tables, _ = child.load(label)
    integrity.assert_frozen()
    ks = [*tuning, *d1]
    quiet = {}
    for cell in QUIET_CELLS:
        quiet[cell] = quiet_cell(label, world, tables, cell, ks, workers)
        print(label, cell, json.dumps(quiet[cell], sort_keys=True), flush=True)
    largest = max(q["largest_evidence"] for q in quiet.values())
    threshold = threshold_above(largest)
    look = s1_look(label, world, tables, list(d1), threshold, workers)
    print(
        label, "S1", json.dumps({k: v for k, v in look.items() if k != "design_curve"}), flush=True
    )
    integrity.assert_frozen()
    child.check(label, world, tables)
    return {
        "world": label,
        "seeds": {
            "fit": {
                "cells": list(QUIET_CELLS),
                "k": [[tuning.start, tuning.stop - 1], [d1.start, d1.stop - 1]],
            },
            "s1_look": {"cells": ["S1"], "k": [[d1.start, d1.stop - 1]]},
        },
        "quiet": quiet,
        "largest_evidence": largest,
        "threshold": threshold,
        "threshold_log2": int(math.log2(threshold)),
        "s1_d1": look,
    }


def _write(path: Path, document: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(document, sort_keys=True, separators=(",", ":")) + "\n"
    path.write_text(text, encoding="utf-8", newline="\n")


def _range(text: str) -> range:
    first, last = (int(x) for x in text.split(":"))
    return range(first, last + 1)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--worlds", nargs="+", default=list(WORLDS), choices=WORLDS)
    parser.add_argument("--tuning", type=_range, default=TUNING, help="k first:last")
    parser.add_argument("--d1", type=_range, default=D1, help="k first:last")
    parser.add_argument("--workers", type=int, default=10)
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args()
    rule = (
        "threshold = the smallest power of two strictly above the largest evidence the instrument "
        "sees on cells N, S2 and S3 at the tuning and D1 seeds (truth session 6, gate item 6)"
    )
    worlds = {}
    for label in args.worlds:
        worlds[label] = fit(label, args.tuning, args.d1, args.workers)
        _write(args.out / f"params-b-{label}.json", {"surge_threshold": worlds[label]["threshold"]})
    _write(args.out / "surge-threshold.json", {"rule": rule, "worlds": worlds})
    print("written", args.out / "surge-threshold.json", flush=True)


if __name__ == "__main__":
    main()
