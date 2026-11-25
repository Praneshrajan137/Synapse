"""Every fitted number of SYNAPSE's composition, by one committed procedure, per world.

Truth session 6, stage C (gate items 5, 6, 7 and 15). One procedure, run once per world (W primary,
W-d1 secondary), from that world's own inputs:

1. **The surge threshold** is :mod:`scripts.challengers.calibrate_surge`'s (its own committed
   script; ``docs/truth/challengers/surge-threshold.json``).
2. **The candidates** (gate item 7, one per entry), from stage B's D1 measurement, behind the
   guard: for ``P/surge``, the surge plan with the lower mean J pooled with equal weight over lane
   P's cells (N, S1, S2, S3) at ``kappa = 1``, the plan chosen before either is tuned (decision
   S6-D-08); for ``P/supply``, the supply response.
3. **Kappa** per item and part of the day for each tuned candidate (``tune``), by the sealed search
   :func:`synapse_kernel.release.tuning.coordinate_search` from 1, ``J_i`` at the primary weights
   over lane P's tuning seeds pooled (N, S1, S2 and S3 at k 0-31, 128 replicates). Every
   evaluation runs the candidate in challenger processes of its own, a fresh one per replicate. A
   replicate in which the candidate never acts at ``kappa = 1`` orders as the lane incumbent at
   every decision, so at every kappa (its detector sees the same sales), and is priced once; the
   others are run at every evaluation. The final table is then re-evaluated in reported mode
   (both replays) and its ``J_i`` must equal the search's to the bit.
4. **The trust map** (``trust``, gate item 7): per entry in the order L/calm, P/calm, P/surge,
   P/supply, its candidate is first set in the composition alone and compared on D1 with the lane
   incumbent, pooled over the lane's cells; if lower, D2 is opened for it once: the composition
   with it against the composition without it, by the D-4(a) mark with zero margin in every
   cell of its lane. The whole is then re-checked against the lane incumbent in all five cells,
   entries removed in reverse order until it passes. Every look is recorded.

``python -m scripts.challengers.fit tune --world W --component surge_today``
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any

import numpy as np
import numpy.typing as npt

from scripts.challengers import child
from scripts.challengers.isolate import SPAWN, Spec, run_one
from synapse_kernel.release import seeds
from synapse_kernel.release.incumbent import part_of_day
from synapse_kernel.release.tuning import STEPS, coordinate_search

F64 = npt.NDArray[np.float64]
ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs" / "truth" / "composition"
THRESHOLDS = ROOT / "docs" / "truth" / "challengers" / "surge-threshold.json"
LANE_P_CELLS = ("N", "S1", "S2", "S3")
TUNING = range(0, 32)
TUNED = {
    "surge_today": "surge_today_kappa",
    "surge_ahead": "surge_ahead_kappa",
    "supply": "supply_kappa",
}


def canonical(document: Any) -> str:
    return json.dumps(document, sort_keys=True, separators=(",", ":"))


def threshold(world_label: str) -> float:
    record = json.loads(THRESHOLDS.read_text(encoding="utf-8"))
    return float(record["worlds"][world_label]["threshold"])


def used_parts(world: Any) -> npt.NDArray[np.bool_]:
    """``used[i, d]``: item ``i`` decides in part ``d`` of the day (its supplier's cutoffs)."""
    cutoffs = {s.name: s.cutoff_hours for s in world.suppliers}
    used = np.zeros((len(world.items), 6), dtype=bool)
    for i, item in enumerate(world.items):
        for hour in cutoffs[item.supplier]:
            used[i, part_of_day(hour)] = True
    return used


def acted(component: str, report: dict[str, Any]) -> bool:
    """Whether the candidate changed any order in this replicate (from its own report)."""
    if component == "supply":
        return any(v[0] > 0 for v in report["flagged"])
    return any(v[0] > 0 for v in report["alarms"])  # a store alarm with surged items


def _one(job: tuple[Spec, str, int, bool]) -> dict[str, Any]:
    spec, cell, seed, replay = job
    return run_one(spec, cell, seed, replay_decisions=replay)


def tune(world_label: str, component: str, workers: int, ks: range = TUNING) -> dict[str, Any]:
    """Kappa for one candidate in one world, by the sealed search; the record of how."""
    world, _, _ = child.load(world_label)
    key = TUNED[component]
    fixed = {"guard": True, "surge_threshold": threshold(world_label)}
    order = [(cell, seeds.explore_seed(k)) for cell in LANE_P_CELLS for k in ks]
    n = len(order)
    log: list[dict[str, Any]] = []
    t0 = time.perf_counter()
    with ProcessPoolExecutor(max_workers=workers, mp_context=SPAWN) as pool:

        def run(table: F64, jobs: list[tuple[str, int]], replay: bool) -> list[dict[str, Any]]:
            spec = Spec(component, world_label, inline=canonical({**fixed, key: table.tolist()}))
            return list(pool.map(_one, [(spec, cell, seed, replay) for cell, seed in jobs]))

        ones = np.ones((len(world.items), 6), dtype=np.float64)
        first = run(ones, order, False)
        moving = [j for j, r in enumerate(first) if acted(component, r["report"])]
        priced: list[list[float]] = [r["item_cost"] for r in first]

        def evaluate(table: F64) -> F64:
            start = time.perf_counter()
            costs = list(priced)
            if moving:
                for j, result in zip(
                    moving, run(table, [order[j] for j in moving], False), strict=True
                ):
                    costs[j] = result["item_cost"]
            per_item = np.array(
                [math.fsum(row[i] for row in costs) / n for i in range(len(world.items))]
            )
            log.append(
                {
                    "seconds": round(time.perf_counter() - start, 1),
                    "pooled_cost": math.fsum(per_item.tolist()),
                }
            )
            last = log[-1]
            print(
                f"{world_label} {component}: evaluation {len(log)}, "
                f"J {last['pooled_cost']:.4f}, {last['seconds']} s",
                flush=True,
            )
            return per_item

        result = coordinate_search(evaluate, used_parts(world), replicates=len(moving))
        # The final table once more as the search evaluates (decision S6-D-09): where items are
        # coupled (the surge detector pools them), an item's cost moves when others' kappa moves,
        # so the search's own record of it, kept from its last accepted step, can be stale.
        final = evaluate(result.factors)
        reported = run(result.factors, order, True)
    if not all(r["outcome_replay"] and r["decision_replay"] for r in reported):
        raise RuntimeError("a replay failed in the reported re-evaluation")
    again = np.array(
        [math.fsum(r["item_cost"][i] for r in reported) / n for i in range(len(world.items))]
    )
    if not np.array_equal(again, final):
        raise RuntimeError("the reported re-evaluation does not give the tuning's J_i to the bit")
    stale = np.abs(final - result.cost)
    return {
        "world": world_label,
        "component": component,
        "key": key,
        "procedure": "release.tuning.coordinate_search from 1, steps " + str(STEPS),
        "seeds": {"cells": list(LANE_P_CELLS), "k": [ks.start, ks.stop - 1]},
        "replicates": n,
        "replicates_where_it_acts": len(moving),
        "kappa": result.factors.tolist(),
        "item_cost": final.tolist(),
        "pooled_cost": math.fsum(final.tolist()),
        "pooled_cost_at_one": log[0]["pooled_cost"],
        "search_record": {
            "pooled_cost": math.fsum(result.cost.tolist()),
            "items_whose_record_was_stale": int(np.count_nonzero(stale)),
            "largest_stale_gap": float(stale.max()),
        },
        "replicate_evaluations": result.replicate_evaluations,
        "sweeps_per_step": list(result.sweeps_per_step),
        "items_moved": int(np.count_nonzero(result.factors[used_parts(world)] != 1.0)),
        "evaluations": log,
        "reported_check": (
            "the final table in reported mode gives the tuning's J_i to the bit; both replays held"
        ),
        "wall_seconds": round(time.perf_counter() - t0, 1),
    }


# -- the trust map (gate item 7) ------------------------------------------------------------------

D1 = range(64, 192)
D2 = range(192, 320)
ALL_CELLS = ("N", "L", "S1", "S2", "S3")
LANE_CELLS = {"L": ("L",), "P": LANE_P_CELLS}
TRUST_LABEL = b"synapse/session-6/trust/"
MEASURES = ROOT / "docs" / "truth" / "challengers"
#: The stage-B labels (guarded, as the composition would run them) that may decide each entry.
CANDIDATES = {
    "L/calm": ("sensing", "sentinel_as_built", "sentinel_world"),
    "P/calm": ("sensing", "sentinel_as_built", "sentinel_world"),
    "P/surge": ("surge_today", "surge_ahead"),
    "P/supply": ("supply",),
}
ENTRY_ORDER = ("L/calm", "P/calm", "P/surge", "P/supply")


def pooled_d1(measure: dict[str, Any], label: str, cells: tuple[str, ...]) -> float:
    """A stage-B label's mean J on D1, pooled with equal weight over ``cells``."""
    return math.fsum(measure["components"][label][c]["mean"]["cost"] for c in cells) / len(cells)


def choose(world_label: str, measures: Path = MEASURES) -> dict[str, Any]:
    """Each entry's one candidate: the lowest pooled D1 mean J among its allowed deciders, behind
    the guard, from stage B's measurement (``kappa = 1``: decision S6-D-08)."""
    measure = json.loads((measures / f"measure-d1-{world_label}.json").read_text(encoding="utf-8"))
    out: dict[str, Any] = {}
    for entry in ENTRY_ORDER:
        cells = LANE_CELLS[entry[0]]
        pooled = {name: pooled_d1(measure, f"{name}+guard", cells) for name in CANDIDATES[entry]}
        best = min(sorted(pooled), key=lambda name: pooled[name])
        out[entry] = {
            "candidate": best,
            "pooled_d1_mean_j_at_kappa_1": pooled,
            "lane_incumbent_pooled_d1_mean_j": pooled_d1(measure, "lane_incumbent", cells),
        }
    return out


def kappas(world_label: str) -> dict[str, Any]:
    """The tuned kappa tables committed for this world, by parameter key."""
    out: dict[str, Any] = {}
    for component, key in TUNED.items():
        path = OUT / f"kappa-{component}-{world_label}.json"
        if path.exists():
            out[key] = json.loads(path.read_text(encoding="utf-8"))["kappa"]
    return out


def composition_params(world_label: str, trust: dict[str, str]) -> dict[str, Any]:
    """The composition's parameters for a trust map: the threshold and every tuned table."""
    return {"trust": trust, "surge_threshold": threshold(world_label), **kappas(world_label)}


class Cache:
    """Composition results by (trust map, cell, seed) from run files, noting what is missing."""

    def __init__(self, world_label: str, raw: Path | None) -> None:
        self.world = world_label
        self.kept: dict[tuple[str, str, int], dict[str, Any]] = {}
        self.missing: list[dict[str, Any]] = []
        self.files: dict[str, str] = {}  # run file -> sha256 of its bytes (LF)
        for path in sorted(raw.glob("**/runs-*.json")) if raw is not None else []:
            document = json.loads(path.read_text(encoding="utf-8"))
            if document["world"] != world_label:
                continue
            if document["params"] != composition_params(world_label, document["trust"]):
                raise RuntimeError(f"{path.name} ran other parameters than these")
            data = path.read_bytes().replace(b"\r\n", b"\n")
            self.files[path.name] = hashlib.sha256(data).hexdigest()
            key = canonical(document["trust"])
            for row in document["results"]:
                self.kept[(key, document["cell"], int(row["k"]))] = row

    def costs(
        self, trust: dict[str, str], cells: tuple[str, ...], ks: range, replay: bool = True
    ) -> dict[str, list[dict[str, Any]]] | None:
        """Per cell, the results in seed order; ``None``, noted, if any is missing."""
        key = canonical(trust)
        absent = [c for c in cells if any((key, c, k) not in self.kept for k in ks)]
        for cell in absent:
            self.missing.append(
                {
                    "world": self.world,
                    "trust": trust,
                    "cell": cell,
                    "k": [ks.start, ks.stop - 1],
                    "replay": replay,
                }
            )
        if absent:
            return None
        out = {cell: [self.kept[(key, cell, k)] for k in ks] for cell in cells}
        for cell, rows in out.items():
            if not all(r["outcome_replay"] for r in rows) or (
                replay and not all(r["decision_replay"] is True for r in rows)
            ):
                raise RuntimeError(f"{self.world} {key} {cell}: a replay failed or was not run")
        return out


def run_item(item: dict[str, Any], workers: int) -> dict[str, Any]:
    """One needed run: a composition on one cell's seeds, a fresh child per replicate."""
    world_label = str(item["world"])
    trust = dict(item["trust"])
    params = composition_params(world_label, trust)
    spec = Spec("synapse", world_label, inline=canonical(params))
    first, last = (int(x) for x in item["k"])
    ks = range(first, last + 1)
    jobs = [(spec, str(item["cell"]), seeds.explore_seed(k), bool(item["replay"])) for k in ks]
    t0 = time.perf_counter()
    with ProcessPoolExecutor(max_workers=workers, mp_context=SPAWN) as pool:
        done = list(pool.map(_one, jobs))
    results = []
    for k, result in zip(ks, done, strict=True):
        result.pop("item_cost", None)
        result.pop("handshake", None)
        results.append({"k": k, **result})
    from scripts.challengers.measure import code_digest

    return {
        "world": world_label,
        "trust": trust,
        "params": params,
        "cell": item["cell"],
        "k": [first, last],
        "replay": bool(item["replay"]),
        "results": results,
        "wall_seconds": round(time.perf_counter() - t0, 1),
        "code": code_digest(),
    }


def d4a(
    world_label: str, mine: dict[str, list[dict[str, Any]]], theirs: dict[str, list[dict[str, Any]]]
) -> dict[str, Any]:
    """The D-4(a) mark with zero margin, per cell: the two-sided 95% BCa interval of the mean
    difference in J has its upper end at or below 0, the 95% interval of the mean fill difference
    its lower end at or above -0.01, and in at least one cell the mean difference is below 0."""
    from synapse_kernel.proof.analysis import (
        FILL_FLOOR,
        bootstrap,
        bootstrap_seed,
        endpoint,
        index_stream,
    )

    cells: dict[str, Any] = {}
    for cell in mine:
        cost = np.array(
            [a["cost"] - b["cost"] for a, b in zip(mine[cell], theirs[cell], strict=True)]
        )
        fill = np.array(
            [a["fill"] - b["fill"] for a, b in zip(mine[cell], theirs[cell], strict=True)]
        )
        seed = bootstrap_seed(f"{world_label}{cell}".encode(), TRUST_LABEL)
        indices = index_stream(seed, {cell: cost.size}, cells=(cell,))[cell]
        boot_cost, boot_fill = bootstrap(cost, indices), bootstrap(fill, indices)
        upper = endpoint(boot_cost, 0.975)
        fill_low = endpoint(boot_fill, 0.025)
        cells[cell] = {
            "n": int(cost.size),
            "mean_delta": boot_cost.estimate,
            "ci95": [endpoint(boot_cost, 0.025), upper],
            "fill_mean_delta": boot_fill.estimate,
            "fill_ci95_low": fill_low,
            "holds": bool(upper <= 0.0 and fill_low >= FILL_FLOOR),
        }
    passes = all(c["holds"] for c in cells.values()) and any(
        c["mean_delta"] < 0.0 for c in cells.values()
    )
    return {"cells": cells, "passes": passes}


def _deltas(
    mine: dict[str, list[dict[str, Any]]], theirs: dict[str, list[dict[str, Any]]]
) -> dict[str, Any]:
    return {
        cell: {
            "cost": [a["cost"] - b["cost"] for a, b in zip(mine[cell], theirs[cell], strict=True)],
            "fill": [a["fill"] - b["fill"] for a, b in zip(mine[cell], theirs[cell], strict=True)],
        }
        for cell in mine
    }


def plan(
    world_label: str,
    raw: Path | None,
    d1: range = D1,
    d2: range = D2,
    measures: Path = MEASURES,
) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    """Gate item 7, as far as the runs in ``raw`` allow: the record, or the runs needed next.

    Every entry's D1 check is independent of the others, so all are asked for at once; the D2
    steps are asked for one at a time, each only once the steps before it are decided, so no D2
    run is made that the procedure does not look at.
    """
    candidates = choose(world_label, measures)
    cache = Cache(world_label, raw)
    checks = {}
    for entry in ENTRY_ORDER:
        cells = LANE_CELLS[entry[0]]
        decider = candidates[entry]["candidate"]
        checks[entry] = (
            cache.costs({entry: decider}, cells, d1, replay=False),
            cache.costs({}, cells, d1, replay=False),
        )
    if cache.missing:
        return None, cache.missing
    opened: dict[str, bool] = {}
    for entry, (alone, lane) in checks.items():
        assert alone is not None and lane is not None
        cells = LANE_CELLS[entry[0]]
        pooled = math.fsum(statistics_mean([r["cost"] for r in alone[c]]) for c in cells)
        base = math.fsum(statistics_mean([r["cost"] for r in lane[c]]) for c in cells)
        candidates[entry]["composition_pooled_d1_mean_j"] = pooled / len(cells)
        candidates[entry]["lane_pooled_d1_mean_j"] = base / len(cells)
        opened[entry] = pooled < base
    looks: list[dict[str, Any]] = []
    trusted: dict[str, str] = {}
    for entry in ENTRY_ORDER:
        decider = candidates[entry]["candidate"]
        if not opened[entry]:
            looks.append({"entry": entry, "candidate": decider, "d2_opened": False})
            continue
        cells = LANE_CELLS[entry[0]]
        with_it = {**trusted, entry: decider}
        mine, theirs = cache.costs(with_it, cells, d2), cache.costs(trusted, cells, d2)
        if mine is None or theirs is None:
            return None, cache.missing
        mark = d4a(world_label, mine, theirs)
        looks.append(
            {
                "entry": entry,
                "candidate": decider,
                "d2_opened": True,
                "against": dict(trusted),
                **mark,
                "deltas": _deltas(mine, theirs),
            }
        )
        if mark["passes"]:
            trusted = with_it
    backed_off: list[str] = []
    while trusted:
        mine, theirs = cache.costs(trusted, ALL_CELLS, d2), cache.costs({}, ALL_CELLS, d2)
        if mine is None or theirs is None:
            return None, cache.missing
        whole = d4a(world_label, mine, theirs)
        looks.append(
            {"entry": "whole", "trust": dict(trusted), **whole, "deltas": _deltas(mine, theirs)}
        )
        if whole["passes"]:
            break
        last = [e for e in ENTRY_ORDER if e in trusted][-1]
        backed_off.append(last)
        trusted = {e: d for e, d in trusted.items() if e != last}
    record = {
        "world": world_label,
        "rule": "gate item 7: D-4(a) with zero margin against the composition without the entry, "
        f"on D2 (k {d2.start}-{d2.stop - 1}), entries in the order " + ", ".join(ENTRY_ORDER),
        "d1": [d1.start, d1.stop - 1],
        "candidates": candidates,
        "looks": looks,
        "backed_off": backed_off,
        "trust": trusted,
        "params": composition_params(world_label, trusted),
        "run_files": cache.files,
    }
    return record, []


def statistics_mean(values: list[float]) -> float:
    """A mean summed exactly (``math.fsum``), the same whatever the order."""
    return math.fsum(values) / len(values)


def main() -> None:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    sub = parser.add_subparsers(dest="step", required=True)
    one = sub.add_parser("tune", help="kappa for one candidate in one world")
    one.add_argument("--world", required=True, choices=("W", "W-d1"))
    one.add_argument("--component", required=True, choices=sorted(TUNED))
    one.add_argument("--workers", type=int, default=10)
    one.add_argument("--k", default="0:31", help="tuning seeds k first:last (smoke tests only)")
    one.add_argument("--out", type=Path, default=OUT)
    two = sub.add_parser("trust", help="gate item 7 as far as the runs allow (gate item 7)")
    two.add_argument("--worlds", nargs="+", default=["W", "W-d1"], choices=("W", "W-d1"))
    two.add_argument("--raw", type=Path, help="folder of run files already made")
    two.add_argument("--d1", default="64:191", help="k first:last (smoke tests only)")
    two.add_argument("--d2", default="192:319", help="k first:last (smoke tests only)")
    two.add_argument("--measures", type=Path, default=MEASURES)
    two.add_argument("--out", type=Path, default=OUT)
    three = sub.add_parser("runs", help="make one needed run (a matrix job)")
    three.add_argument("--needed", type=Path, required=True)
    three.add_argument("--index", type=int, required=True)
    three.add_argument("--workers", type=int, default=4)
    three.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.step == "trust":
        d1a, d1b = (int(x) for x in args.d1.split(":"))
        d2a, d2b = (int(x) for x in args.d2.split(":"))
        needed: list[dict[str, Any]] = []
        args.out.mkdir(parents=True, exist_ok=True)
        for world_label in args.worlds:
            record, missing = plan(
                world_label, args.raw, range(d1a, d1b + 1), range(d2a, d2b + 1), args.measures
            )
            for item in missing:  # one run per (world, map, cell, seeds), however often asked
                if item not in needed:
                    needed.append(item)
            if record is not None:
                for name, document in (
                    (f"trust-{world_label}.json", record),
                    (f"params-{world_label}.json", record["params"]),
                ):
                    path = args.out / name
                    path.write_text(canonical(document) + "\n", encoding="utf-8", newline="\n")
                    print("written", path, flush=True)
        if needed:
            path = args.out / "needed.json"
            path.write_text(canonical({"items": needed}) + "\n", encoding="utf-8", newline="\n")
            print(f"{len(needed)} runs needed next: {path}", flush=True)
            raise SystemExit(3)
    if args.step == "runs":
        item = json.loads(args.needed.read_text(encoding="utf-8"))["items"][args.index]
        document = run_item(item, args.workers)
        args.out.mkdir(parents=True, exist_ok=True)
        tag = hashlib.sha256(canonical(item).encode()).hexdigest()[:12]
        path = args.out / f"runs-{item['world']}-{item['cell']}-{tag}.json"
        path.write_text(canonical(document) + "\n", encoding="utf-8", newline="\n")
        print("written", path, flush=True)
    if args.step == "tune":
        first, last = (int(x) for x in args.k.split(":"))
        record = tune(args.world, args.component, args.workers, range(first, last + 1))
        args.out.mkdir(parents=True, exist_ok=True)
        path = args.out / f"kappa-{args.component}-{args.world}.json"
        path.write_text(canonical(record) + "\n", encoding="utf-8", newline="\n")
        print("written", path, flush=True)


if __name__ == "__main__":
    main()
