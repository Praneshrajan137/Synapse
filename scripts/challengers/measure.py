"""Each SYNAPSE component alone on the first development range, in a process of its own.

Truth session 6, stage B (scorecard row P17). Every component runs on both worlds (W primary, W-d1
secondary), in cells N, L, S1, S2 and S3, at the D1 seeds (k 64-191), through the isolation harness
(:mod:`scripts.challengers.isolate`: one fresh challenger process per replicate, both replays), and
is compared, paired by seed, with:

* **the cell's incumbent**, the version each world's freeze selected for that cell (read from its
  incumbent report: I2-N in N, I2-L in L, I2-P in S1 to S3);
* **the lane incumbent**, I2-P, or I2-L once a short shelf life is seen: SYNAPSE's own incumbent and
  the guard's anchor (gate item 1);
* **the headroom** in S1, S2 and S3: the gate's shock oracle, told the scenario, guarded around
  I2-P, as freeze W ran it (none is defined in N or L).

The frozen arms run in the harness's process; only the challenger needs isolating. Every candidate
is measured behind the D-4(b) guard around the lane incumbent, as the composition would run it; the
Sentinel also without it, as built. Per world, cell and component: the mean of J, fill, lost sales,
waste at cost and holding; each delta against each comparator with a two-sided 95% BCa interval
(:mod:`synapse_kernel.proof.analysis`, 10,000 resamples, one generator per world and component,
seeded from ``SHA-256("synapse/session-6/measure/" || world || "/" || component)``, cells in order);
the clipped share; for the surge components, the store's alarms (any alarm outside S1, or before
the onset in S1, is false) and the delay of the first alarm after the onset; for the supply
component, the same for its flags in S2 and S3.

Writes ``docs/truth/challengers/measure-d1-<world>.json``, one world after the other; with
``--cells`` and ``--raw-out`` it runs a part (some cells of a world) and ``--merge`` assembles the
parts, so the work can be spread over machines with the same result. Run after
``calibrate_surge``, whose threshold the surge components are built from:
``python -m scripts.challengers.measure``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any

import numpy as np
import numpy.typing as npt

from scripts.challengers.isolate import SPAWN, Spec, run_one, summarise
from synapse_kernel.proof.analysis import CELLS, Arm, bootstrap, index_stream, interval95
from synapse_kernel.release import seeds

F64 = npt.NDArray[np.float64]
ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs" / "truth" / "challengers"
WORLDS = ("W", "W-d1")
D1 = range(64, 192)
REPORTS = {
    "W": ROOT / "docs" / "truth" / "world" / "incumbent-report.json",
    "W-d1": ROOT / "docs" / "truth" / "world" / "incumbent-report-d1.json",
}
#: (label, component, behind the guard)
COMPONENTS: tuple[tuple[str, str, bool], ...] = (
    ("lane_incumbent", "lane_incumbent", False),
    ("sensing+guard", "sensing", True),
    ("surge_today+guard", "surge_today", True),
    ("surge_ahead+guard", "surge_ahead", True),
    ("supply+guard", "supply", True),
    ("sentinel_as_built", "sentinel_as_built", False),
    ("sentinel_as_built+guard", "sentinel_as_built", True),
    ("sentinel_world", "sentinel_world", False),
    ("sentinel_world+guard", "sentinel_world", True),
)
#: Relative cost of one replicate, to start the slowest jobs first.
_WEIGHT = {"surge_today": 10, "surge_ahead": 10, "sensing": 3}


def params_name(world: str, guarded: bool) -> str:
    """The committed parameter file a component is built from (relative to the repository)."""
    suffix = "-guard" if guarded else ""
    return f"docs/truth/challengers/params-b-{world}{suffix}.json"


def write_params(world: str) -> None:
    """Write the guarded parameter file from the fitted threshold's (before any worker starts)."""
    fitted = json.loads((ROOT / params_name(world, False)).read_text(encoding="utf-8"))
    text = json.dumps({**fitted, "guard": True}, sort_keys=True, separators=(",", ":")) + "\n"
    (ROOT / params_name(world, True)).write_text(text, encoding="utf-8", newline="\n")


def comparators(world_label: str, cell: str, k: int) -> dict[str, Any]:
    """The frozen arms at one seed, in this process: the cell's incumbent, the lane incumbent and,
    in S1 to S3, the gate's oracle behind the guard around I2-P."""
    from scripts.challengers import child
    from synapse_kernel.challengers.shelf import LaneIncumbent
    from synapse_kernel.release import integrity
    from synapse_kernel.release.engine import run
    from synapse_kernel.release.guard import guard
    from synapse_kernel.release.incumbent import Incumbent
    from synapse_kernel.release.oracle import ShockOracle
    from synapse_kernel.release.scenario import build_scenario

    world, tables, _ = child.load(world_label)
    integrity.assert_frozen()
    selected = json.loads(REPORTS[world_label].read_text(encoding="utf-8"))["selection"]
    version = selected[cell]["selected"]
    scenario = build_scenario(world, cell, seeds.explore_seed(k))
    out: dict[str, Any] = {
        "cell_incumbent": summarise(
            world, run(world, [scenario], Incumbent(world, tables[version]))
        ),
        "cell_incumbent_version": version,
        "lane_incumbent": summarise(
            world, run(world, [scenario], LaneIncumbent(world, tables["I2-P"], tables["I2-L"]))
        ),
        # The frozen version the lane rule should settle on: I2-L in L, I2-P elsewhere.
        "lane_version": summarise(
            world,
            run(world, [scenario], Incumbent(world, tables["I2-L" if cell == "L" else "I2-P"])),
        ),
    }
    if cell in ("S1", "S2", "S3"):

        class GuardedOracle:
            def __init__(self) -> None:
                self.oracle = ShockOracle(world, tables["I2-P"], [scenario], rule="gate")
                self.incumbent = Incumbent(world, tables["I2-P"])

            def start(self, replicates: int) -> None:
                self.oracle.start(replicates)
                self.incumbent.start(replicates)

            def decide(self, obs: Any) -> Any:
                return guard(self.oracle.decide(obs), self.incumbent.decide(obs))

        out["headroom"] = summarise(world, run(world, [scenario], GuardedOracle()))
    shock = scenario.shock
    out["shock"] = {
        "kind": shock.kind,
        "onset_hour": shock.onset_hour,
        "end_hour": shock.end_hour,
        "supplier": shock.supplier,
        "items": len(shock.items),
    }
    child.check(world_label, world, tables)
    integrity.assert_frozen()
    return out


def challenger(world_label: str, cell: str, k: int, label: str) -> dict[str, Any]:
    """One component at one seed, in a fresh challenger process, both replays run."""
    name, guarded = next((c, g) for lab, c, g in COMPONENTS if lab == label)
    spec = Spec(name, world_label, params_name(world_label, guarded))
    result = run_one(spec, cell, seeds.explore_seed(k))
    result.pop("item_cost", None)
    return result


def _job(job: tuple[str, str, int, str]) -> tuple[tuple[str, str, int, str], dict[str, Any], float]:
    world_label, cell, k, label = job
    t0 = time.perf_counter()
    if label == "comparators":
        out = comparators(world_label, cell, k)
    else:
        out = challenger(world_label, cell, k, label)
    for arm in ("cell_incumbent", "lane_incumbent", "lane_version", "headroom"):
        if arm in out:
            out[arm].pop("item_cost", None)
    return job, out, time.perf_counter() - t0


def _arm(rows: list[dict[str, Any]]) -> Arm:
    def col(key: str) -> F64:
        return np.asarray([float(r[key]) for r in rows], dtype=np.float64)

    return Arm(
        col("cost"), col("fill"), col("lost"), col("wasted"), col("held"), col("end_on_hand")
    )


def _delta(values: F64, indices: npt.NDArray[np.int64]) -> dict[str, Any]:
    boot = bootstrap(values, indices)
    low, high = interval95(boot)
    return {"mean": boot.estimate, "ci95": [low, high], "sd": statistics.stdev(values.tolist())}


def _schedule(world: Any) -> list[int]:
    return [
        h
        for h in range(world.horizon_hours)
        if any(h % 24 in s.cutoff_hours for s in world.suppliers)
    ]


def _alarms(
    rows: list[dict[str, Any]], shocks: list[dict[str, Any]], hours: list[int], key: str
) -> dict[str, Any]:
    """False alarms, and in the cell whose shock the component looks for, the first alarm's delay.

    ``key`` is ``"alarms"`` (the surge component: a value of 0 or more is a store alarm) or
    ``"flagged"`` (the supply component: a value above 0 is a flagged supplier).
    """
    looks_for = ("surge",) if key == "alarms" else ("delay", "outage")
    false_decisions = 0
    false_replicates = 0
    delays: list[float] = []
    for row, shock in zip(rows, shocks, strict=True):
        trace = [v[0] for v in row["report"][key]]
        alarmed = [
            h for h, v in zip(hours, trace, strict=True) if (v >= 0 if key == "alarms" else v > 0)
        ]
        relevant = shock["kind"] in looks_for
        early = [h for h in alarmed if not relevant or h < shock["onset_hour"]]
        false_decisions += len(early)
        false_replicates += int(bool(early))
        if relevant:
            hit = next((h for h in alarmed if h >= shock["onset_hour"]), None)
            if hit is not None:
                delays.append(hit - shock["onset_hour"])
    out: dict[str, Any] = {
        "false_alarm_decisions": false_decisions,
        "replicates_with_false_alarm": false_replicates,
    }
    if delays:
        out["detected"] = len(delays)
        out["delay_hours_median"] = statistics.median(delays)
        out["delay_hours_mean"] = statistics.fmean(delays)
    return out


def analyse(
    world_label: str,
    results: dict[tuple[str, str, int, str], dict[str, Any]],
    components: tuple[tuple[str, str, bool], ...],
    ks: range = D1,
) -> dict[str, Any]:
    """Every component's comparison in every cell of one world."""
    from scripts.challengers import child

    world, _, _ = child.load(world_label)
    hours = _schedule(world)
    out: dict[str, Any] = {}
    for label, name, guarded in components:
        digest = hashlib.sha256(
            f"synapse/session-6/measure/{world_label}/{label}".encode()
        ).digest()
        stream = index_stream(int.from_bytes(digest[:8], "big") >> 1, dict.fromkeys(CELLS, len(ks)))
        cells: dict[str, Any] = {}
        for cell in CELLS:
            rows = [results[(world_label, cell, k, label)] for k in ks]
            base = [results[(world_label, cell, k, "comparators")] for k in ks]
            if not all(r["outcome_replay"] and r["decision_replay"] for r in rows):
                raise RuntimeError(f"a replay failed: {world_label} {cell} {label}")
            mine = _arm(rows)
            entry: dict[str, Any] = {
                "mean": {
                    "cost": float(np.mean(mine.cost)),
                    "fill": float(np.mean(mine.fill)),
                    "waste_at_cost": float(np.mean(mine.waste_at_cost())),
                },
                "against": {},
            }
            for comparator in ("cell_incumbent", "lane_incumbent", "headroom"):
                if comparator not in base[0]:
                    continue
                theirs = _arm([b[comparator] for b in base])
                entry["against"][comparator] = {
                    "cost": _delta(mine.cost - theirs.cost, stream[cell]),
                    "fill": _delta(mine.fill - theirs.fill, stream[cell]),
                    "waste_at_cost": _delta(
                        mine.waste_at_cost() - theirs.waste_at_cost(), stream[cell]
                    ),
                }
            entry["cell_incumbent_version"] = base[0]["cell_incumbent_version"]
            if name == "lane_incumbent":
                # Against the frozen version of its lane, seed by seed. Lane P is the default from
                # the first decision, so outside L it must be that version exactly. In L the first
                # decision (02:00 on day 0) comes before any receipt shows a life, so it orders as
                # I2-P; the trace of that order can reach the measured week, so L is reported.
                gaps = [
                    r["cost"] - b["lane_version"]["cost"] for r, b in zip(rows, base, strict=True)
                ]
                differ = [(k, g) for k, g in zip(ks, gaps, strict=True) if g != 0.0]
                if differ and cell != "L":
                    raise RuntimeError(f"the lane rule missed its version: {world_label} {cell}")
                entry["against_its_lane_version"] = {
                    "seeds_that_differ": [k for k, _ in differ],
                    "deltas": [g for _, g in differ],
                    "mean_delta": math.fsum(gaps) / len(gaps),
                }
            if guarded:
                clipped = sum(r["report"]["clipped"] for r in rows)
                decisions = sum(r["report"]["decisions"] for r in rows)
                entry["clipped_share"] = clipped / decisions if decisions else 0.0
            shocks = [b["shock"] for b in base]
            if name in ("surge_today", "surge_ahead"):
                entry["surge_alarms"] = _alarms(rows, shocks, hours, "alarms")
            if name == "supply":
                entry["supply_flags"] = _alarms(rows, shocks, hours, "flagged")
            cells[cell] = entry
        out[label] = cells
    return out


def code_digest() -> dict[str, str]:
    """The sha256 of every challenger source file (bytes as checked out, LF), and their combined
    digest, so a report names the exact code that produced it."""
    files = sorted(
        [
            *(ROOT / "synapse_kernel" / "challengers").glob("*.py"),
            *(ROOT / "scripts" / "challengers").glob("*.py"),
        ]
    )
    out: dict[str, str] = {}
    whole = hashlib.sha256()
    for path in files:
        data = path.read_bytes().replace(b"\r\n", b"\n")
        name = path.relative_to(ROOT).as_posix()
        out[name] = hashlib.sha256(data).hexdigest()
        whole.update(name.encode() + b"\x00" + data)
    out["all"] = whole.hexdigest()
    return out


def run_part(
    world_label: str,
    cells: tuple[str, ...],
    ks: range,
    chosen: tuple[tuple[str, str, bool], ...],
    workers: int,
) -> dict[str, Any]:
    """Every job of some cells of one world, run in parallel; the raw results, not analysed."""
    write_params(world_label)
    jobs = [
        (world_label, cell, k, label)
        for cell in cells
        for k in ks
        for label in ["comparators", *(c[0] for c in chosen)]
    ]
    weight = {label: _WEIGHT.get(name, 1) for label, name, _ in chosen}
    jobs.sort(key=lambda j: -weight.get(j[3], 1))
    results: list[list[Any]] = []
    seconds: dict[str, float] = {}
    t0 = time.perf_counter()
    with ProcessPoolExecutor(max_workers=workers, mp_context=SPAWN) as pool:
        for n, (job, out, secs) in enumerate(pool.map(_job, jobs), start=1):
            results.append([list(job), out])
            seconds[job[3]] = seconds.get(job[3], 0.0) + secs
            if n % 250 == 0:
                print(
                    f"{world_label} {','.join(cells)}: {n}/{len(jobs)} jobs, "
                    f"{time.perf_counter() - t0:.0f} s",
                    flush=True,
                )
    return {
        "world": world_label,
        "cells": list(cells),
        "k": [ks.start, ks.stop - 1],
        "components": [c[0] for c in chosen],
        "results": results,
        "seconds": seconds,
        "wall_seconds": time.perf_counter() - t0,
        "code": code_digest(),
    }


def assemble(
    world_label: str, parts: list[dict[str, Any]], chosen: tuple[tuple[str, str, bool], ...]
) -> dict[str, Any]:
    """One world's parts merged (every cell once, the same seeds, components and code in each)
    and analysed."""
    if len({json.dumps(p["code"], sort_keys=True) for p in parts}) != 1:
        raise RuntimeError(f"{world_label}: the parts ran different code")
    if (
        len({tuple(p["k"]) for p in parts}) != 1
        or len({tuple(p["components"]) for p in parts}) != 1
    ):
        raise RuntimeError(f"{world_label}: the parts ran different seeds or components")
    cells = [c for p in parts for c in p["cells"]]
    if sorted(cells) != sorted(CELLS):
        raise RuntimeError(f"{world_label}: cells {sorted(cells)}, not each of {CELLS} once")
    if [c[0] for c in chosen] != list(parts[0]["components"]):
        raise RuntimeError(f"{world_label}: the parts measured other components")
    first, last = parts[0]["k"]
    ks = range(first, last + 1)
    results = {
        (str(j[0]), str(j[1]), int(j[2]), str(j[3])): out for p in parts for j, out in p["results"]
    }
    seconds: dict[str, float] = {}
    for p in parts:
        for label, secs in p["seconds"].items():
            seconds[label] = seconds.get(label, 0.0) + secs
    return {
        "what": "each component alone on D1, split mode, both replays; truth session 6",
        "world": world_label,
        "seeds_k": [first, last],
        "components": analyse(world_label, results, chosen, ks),
        "seconds_per_replicate": {
            label: secs / (len(CELLS) * len(ks)) for label, secs in seconds.items()
        },
        "wall_seconds": max(p["wall_seconds"] for p in parts),
        "code": parts[0]["code"],
        "merge_code": code_digest(),
    }


def _write(path: Path, document: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(document, sort_keys=True, separators=(",", ":")) + "\n"
    path.write_text(text, encoding="utf-8", newline="\n")
    print("written", path, flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--worlds", nargs="+", default=list(WORLDS), choices=WORLDS)
    parser.add_argument("--workers", type=int, default=10)
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--components", nargs="+", default=[c[0] for c in COMPONENTS])
    parser.add_argument("--cells", nargs="+", default=list(CELLS), choices=CELLS)
    parser.add_argument("--k", default=f"{D1.start}:{D1.stop - 1}", help="smoke tests only")
    parser.add_argument("--raw-out", type=Path, help="run these cells only; write raw results")
    parser.add_argument("--merge", type=Path, help="merge the raw parts in this folder")
    args = parser.parse_args()
    chosen = tuple(c for c in COMPONENTS if c[0] in args.components)
    first, last = (int(x) for x in args.k.split(":"))
    ks = range(first, last + 1)
    for world_label in args.worlds:
        if args.merge is not None:
            # By the world each part records ("raw-W-*" would also match W-d1's files).
            loaded = [
                json.loads(path.read_text(encoding="utf-8"))
                for path in sorted(args.merge.glob("**/raw-*.json"))
            ]
            parts = [part for part in loaded if part["world"] == world_label]
            _write(
                args.out / f"measure-d1-{world_label}.json", assemble(world_label, parts, chosen)
            )
        elif args.raw_out is not None:
            part = run_part(world_label, tuple(args.cells), ks, chosen, args.workers)
            _write(args.raw_out / f"raw-{world_label}-{'-'.join(args.cells)}.json", part)
        else:
            part = run_part(world_label, tuple(CELLS), ks, chosen, args.workers)
            _write(
                args.out / f"measure-d1-{world_label}.json", assemble(world_label, [part], chosen)
            )


if __name__ == "__main__":
    main()
