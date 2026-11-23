"""Stage D: tune the incumbent as sealed, select it per cell, and report what freeze W fixes.

``python -m scripts.kernel.tune_incumbent`` reads the release world, and:

1. measures the waste share of the better of I1 and I2 tuned on cell N's tuning seeds; outside
   [2.7%, 10.9%] it recalibrates the world's shelf lives by one global scale, bisected in log scale
   toward IFPA's 5.46%, at most six times, every iteration recorded (the session-5 gate, section 7);
2. tunes six versions (I1 and I2, each on N's tuning seeds, on L's, and on N, S1, S2 and S3 pooled)
   with the sealed coordinate search (``synapse_kernel.release.tuning``);
3. selects the incumbent per cell on that cell's 32 validation seeds (lowest mean J; ties: I1, then
   the version tuned on normal conditions) and the contest's incumbent (pooled versions, S1 to S3);
4. computes ``D_c``, ``p_c`` and ``M_c`` per cell from the declared parameters, the shock headroom
   of an oracle told each shock, and, as an exploratory description, how much of it survives the
   guard of D-4(b);
5. reports each version's tuning-validation gap (on the validation seeds of the cells it was tuned
   on), 1-D profiles around the selected N version's optimum, and a restart of I1-N from k = 2;
6. writes the tables (``synapse_kernel/worlds/incumbent_tables.json``), the report
   (``docs/truth/world/incumbent-report.json``) and, if it recalibrated, the world with the
   calibration in its shelf lives' provenance (``--world-out``).

It uses no process pool, so the ``__main__`` guard of E-TP-01 is a habit here, not a need.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import math
import platform
import sys
import time
from pathlib import Path
from typing import Any, Final

import numpy as np

from synapse_kernel.release import seeds
from synapse_kernel.release.harness import price, scenarios, tune_incumbent, used_parts
from synapse_kernel.release.incumbent import Incumbent, IncumbentTables
from synapse_kernel.release.objective import PRIMARY
from synapse_kernel.release.oracle import Guarded, ShockOracle
from synapse_kernel.release.scenario import demand_means
from synapse_kernel.release.tuning import coordinate_search
from synapse_kernel.release.world import (
    HOURS_PER_DAY,
    MEASURED_DAYS,
    ReleaseWorld,
    load_release_world,
    world_to_document,
)

ROOT: Final[Path] = Path(__file__).resolve().parents[2]
IFPA_SHRINK: Final[float] = 0.0546
BAND: Final[tuple[float, float]] = (0.027, 0.109)
SCALE_BRACKET: Final[tuple[float, float]] = (0.5, 2.0)
MAX_CALIBRATIONS: Final[int] = 6
SHOCK_CELLS: Final[tuple[str, ...]] = ("S1", "S2", "S3")
BOOTSTRAP_SEED: Final[int] = 20261121


def scaled(world: ReleaseWorld, scale: float) -> ReleaseWorld:
    """The world with every shelf life times ``scale``, rounded to whole hours, at least 12."""
    items = tuple(
        dataclasses.replace(item, shelf_life_hours=max(12, round(item.shelf_life_hours * scale)))
        for item in world.items
    )
    return dataclasses.replace(world, items=items)


def calibrated(world: ReleaseWorld, scale: float, steps: list[dict[str, Any]]) -> ReleaseWorld:
    """:func:`scaled`, with the calibration written into the shelf lives' provenance."""
    key = "items.shelf_life_hours"
    old = world.provenance[key]
    history = "; ".join(f"{s['waste_share']:.2%} at {s['scale']:.4f}" for s in steps)
    hours = sorted({max(12, round(item.shelf_life_hours * scale)) for item in world.items})
    note = (
        f"{old.source}. Calibrated before freeze W by the session-5 gate's rule (section 7): the "
        f"incumbent's waste share in N (units discarded over units sold, tuning seeds) was "
        f"{history}, so every shelf life is times {scale!r}, rounded to whole hours: "
        f"{', '.join(str(h) for h in hours)} hours"
    )
    provenance = {**world.provenance, key: dataclasses.replace(old, source=note)}
    return dataclasses.replace(scaled(world, scale), provenance=provenance)


#: Offsets of one part's factor around the tuned point, for the 1-D profiles (gate, section 6 D).
PROFILE_OFFSETS: Final[tuple[float, ...]] = (
    -0.5,
    -0.25,
    -0.125,
    -0.0625,
    -0.03125,
    0.03125,
    0.0625,
    0.125,
    0.25,
    0.5,
)


def profiles(
    world: ReleaseWorld, tables: IncumbentTables, batch: list[Any], tuned_cost: np.ndarray
) -> dict[str, Any]:
    """1-D profiles of every item's cost along each used part's factor, around the tuned point.

    Items do not interact, so one evaluation moves every item's factor of part ``d`` by the same
    offset and reads each item's own cost. A pair (item, part) "improves" if some offset gives a
    strictly lower cost than the tuned point, which a lattice optimum of the sealed search (step
    1/32) may still allow farther out than one step.
    """
    used = used_parts(world)
    evaluate = _evaluator(world, tables, batch)
    out: dict[str, Any] = {"offsets": list(PROFILE_OFFSETS), "parts": {}}
    better, largest = 0, 0.0
    for part in range(used.shape[1]):
        items = np.flatnonzero(used[:, part])
        if items.size == 0:
            continue
        costs = []
        for offset in PROFILE_OFFSETS:
            factors = tables.factors.copy()
            factors[items, part] = np.maximum(0.0, factors[items, part] + offset)
            costs.append(evaluate(factors)[items])
        grid = np.array(costs)  # (offsets, items)
        gain = tuned_cost[items] - grid.min(axis=0)
        better += int((gain > 0).sum())
        largest = max(largest, float(gain.max()))
        out["parts"][str(part)] = {
            "items": int(items.size),
            "mean_cost_at_offset": [float(row.mean()) for row in grid],
            "mean_cost_tuned": float(tuned_cost[items].mean()),
            "pairs_improved_by_an_offset": int((gain > 0).sum()),
        }
    out["pairs_improved"] = better
    out["largest_improvement"] = largest
    return out


def tables_document(tables: IncumbentTables, result: Any) -> dict[str, Any]:
    return {
        "name": tables.name,
        "waste_aware": tables.waste_aware,
        "factors": tables.factors.tolist(),
        "mean_table": tables.mean_table.tolist(),
        "replicate_evaluations": result.replicate_evaluations,
        "sweeps_per_step": list(result.sweeps_per_step),
        "last_move_sweep": result.last_move.tolist(),
        "tuning_cost_per_item": result.cost.tolist(),
    }


def interval(values: np.ndarray, rng: np.random.Generator, resamples: int = 10_000) -> list[float]:
    """A percentile bootstrap 95% interval of the mean (exploratory description only)."""
    idx = rng.integers(0, len(values), (resamples, len(values)))
    means = values[idx].mean(axis=1)
    return [float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))]


def expected_demand(world: ReleaseWorld) -> dict[str, float]:
    """``D_c``: expected units demanded per store-day, from declared parameters only."""
    base = math.fsum(item.rate_per_day for item in world.items)
    week = demand_means(world)  # (168, items): rate / 24 * profile
    count = math.ceil(3 * len(world.items) / 10)
    start = world.measured_start_hour
    span = MEASURED_DAYS * HOURS_PER_DAY
    # E over onset and duration of the surged hours' mean demand, per item, averaged over items:
    grid = 120
    total = 0.0
    for a in range(grid):
        duration = (1.0 + 2.0 * (a + 0.5) / grid) * HOURS_PER_DAY
        for b in range(grid):
            onset = start + (b + 0.5) / grid * (span - duration)
            hours = np.arange(math.ceil(onset), math.ceil(onset + duration))
            total += float(week[hours % 168].sum())
    per_item_window = total / (grid * grid) / len(world.items)  # mean over items
    extra = count * per_item_window * 1.25 / MEASURED_DAYS  # E[u - 1] = 1.25
    return {"N": base, "L": base, "S1": base + extra, "S2": base, "S3": base}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m scripts.kernel.tune_incumbent")
    parser.add_argument(
        "--world", type=Path, default=ROOT / "synapse_kernel/worlds/release_world.json"
    )
    parser.add_argument(
        "--tables-out", type=Path, default=ROOT / "synapse_kernel/worlds/incumbent_tables.json"
    )
    parser.add_argument(
        "--report-out", type=Path, default=ROOT / "docs/truth/world/incumbent-report.json"
    )
    parser.add_argument(
        "--world-out", type=Path, default=None, help="where a recalibrated world goes"
    )
    args = parser.parse_args(argv)
    started = time.perf_counter()
    world = load_release_world(args.world)
    tuning = seeds.explore_seeds(seeds.TUNING)
    validation = seeds.explore_seeds(seeds.VALIDATION)
    report: dict[str, Any] = {
        "software": {"python": platform.python_version(), "numpy": np.__version__},
        "machine": platform.platform(),
        "calibration": [],
    }

    # 1. calibration, if at all.
    scale, lo, hi = 1.0, None, None
    for attempt in range(MAX_CALIBRATIONS + 1):
        current = scaled(world, scale) if scale != 1.0 else world
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
        share = trial[better][1]
        report["calibration"].append(
            {"scale": scale, "better": better, "waste_share": share, "tuned": trial}
        )
        print(
            f"calibration {attempt}: scale {scale:.4f} -> {better} waste share {share:.4f}",
            flush=True,
        )
        if BAND[0] <= share <= BAND[1] or attempt == MAX_CALIBRATIONS:
            break
        if share > BAND[1]:  # too much waste: longer shelf lives
            lo = scale
            hi = hi if hi is not None else SCALE_BRACKET[1]
        else:
            hi = scale
            lo = lo if lo is not None else SCALE_BRACKET[0]
        scale = math.sqrt(lo * hi)
    report["calibration_scale"] = scale
    if scale != 1.0:
        world = calibrated(world, scale, report["calibration"])
        out = args.world_out or args.world
        out.write_text(
            json.dumps(world_to_document(world), sort_keys=True, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )

    # 2. six versions.
    tune_sets = {cell: scenarios(world, cell, tuning) for cell in ("N", "L", "S1", "S2", "S3")}
    versions: dict[str, tuple[IncumbentTables, Any]] = {}
    for aware, tag in ((False, "I1"), (True, "I2")):
        versions[f"{tag}-N"] = tune_incumbent(world, f"{tag}-N", aware, [tune_sets["N"]])
        versions[f"{tag}-L"] = tune_incumbent(world, f"{tag}-L", aware, [tune_sets["L"]])
        versions[f"{tag}-P"] = tune_incumbent(
            world, f"{tag}-P", aware, [tune_sets[c] for c in ("N", "S1", "S2", "S3")]
        )
        for suffix in ("N", "L", "P"):
            result = versions[f"{tag}-{suffix}"][1]
            print(
                f"tuned {tag}-{suffix}: {result.replicate_evaluations} replicate-evaluations, "
                f"sweeps {result.sweeps_per_step}",
                flush=True,
            )

    # 3. selection on validation seeds.
    candidates = {"N": ["I1-N", "I2-N"], "L": ["I1-L", "I2-L"]}
    for cell in SHOCK_CELLS:
        candidates[cell] = ["I1-N", "I2-N", "I1-P", "I2-P"]
    valid_sets = {cell: scenarios(world, cell, validation) for cell in candidates}
    priced: dict[str, dict[str, Any]] = {}
    for cell, names in candidates.items():
        priced[cell] = {
            name: price(world, valid_sets[cell], Incumbent(world, versions[name][0]))
            for name in names
        }
    rank = {"I1-N": 0, "I1-L": 0, "I1-P": 1, "I2-N": 2, "I2-L": 2, "I2-P": 3}
    selected = {
        cell: min(names, key=lambda n: (priced[cell][n].mean_cost, rank[n]))
        for cell, names in candidates.items()
    }
    pooled_s = {
        name: float(np.mean([c for cell in SHOCK_CELLS for c in priced[cell][name].costs]))
        for name in ("I1-P", "I2-P")
    }
    contest = min(pooled_s, key=lambda n: (pooled_s[n], rank[n]))

    # 4. D_c, p_c, M_c; headroom.
    demand = expected_demand(world)
    weights = PRIMARY
    margins = {cell: 0.01 * demand[cell] * weights.lost_sale * 1.0 for cell in candidates}
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    headroom: dict[str, Any] = {}
    used = used_parts(world)
    kappa_slot = np.zeros_like(used)
    kappa_slot[:, 0] = True  # one response factor per item, in the first column
    for cell in SHOCK_CELLS:
        base = versions[selected[cell]][0]
        incumbent = priced[cell][selected[cell]]
        batch = valid_sets[cell]
        found: dict[str, Any] = {}
        for guarded in (False, True):
            for tuned in (False, True):
                label = ("guarded" if guarded else "unguarded") + ("_tuned" if tuned else "_told")
                response, evaluations = None, 0
                if tuned:
                    result = coordinate_search(
                        _told_evaluator(world, base, tune_sets[cell], guarded),
                        kappa_slot,
                        len(tune_sets[cell]),
                    )
                    response, evaluations = result.factors[:, 0], result.replicate_evaluations
                oracle = ShockOracle(world, base, batch, response)
                policy: Any = Guarded(oracle, Incumbent(world, base)) if guarded else oracle
                outcome = price(world, batch, policy)
                gain = np.array(incumbent.costs) - np.array(outcome.costs)
                found[label] = {
                    "mean_advantage": float(gain.mean()),
                    "advantage_ci95": interval(gain, rng),
                    "response_tuning_replicate_evaluations": evaluations,
                    "clipped_share": (policy.clipped / max(policy.decisions, 1))
                    if guarded
                    else None,
                }
                print(
                    f"headroom {cell} {label}: {gain.mean():+.3f} (margin {margins[cell]:.3f})",
                    flush=True,
                )
        headroom[cell] = {
            "incumbent": selected[cell],
            "margin": margins[cell],
            **found,
            "difference_in_differences_note": (
                "in N the told incumbent is the incumbent, so the DiD equals the advantage"
            ),
        }

    # Generalisation gap (validation seeds of the cells each version was tuned on), the 1-D
    # profiles around the selected N version's optimum, and a restart of I1-N from k = 2.
    gaps = {}
    for name, (tables_, result) in versions.items():
        cells = {"N": ("N",), "L": ("L",), "P": ("N", "S1", "S2", "S3")}[name.split("-")[1]]
        costs: list[float] = []
        for cell in cells:
            known = priced.get(cell, {}).get(name)
            costs += list(
                known.costs
                if known
                else price(world, valid_sets[cell], Incumbent(world, tables_)).costs
            )
        gaps[name] = {
            "cells": list(cells),
            "tuning_mean_cost": float(result.cost.sum()),
            "validation_mean_cost": math.fsum(costs) / len(costs),
        }
    n_tables, n_result = versions[selected["N"]]
    profile = profiles(world, n_tables, tune_sets["N"], n_result.cost)
    profile["version"] = selected["N"]
    i1n_tables, i1n_result = versions["I1-N"]
    restart = coordinate_search(
        _evaluator(world, i1n_tables, tune_sets["N"]), used, len(tuning), start=2.0
    )
    report.update(
        {
            "versions": {
                name: {k: v for k, v in tables_document(t, r).items() if k != "mean_table"}
                for name, (t, r) in versions.items()
            },
            "selection": {
                cell: {
                    "selected": selected[cell],
                    "validation_mean_cost": {n: priced[cell][n].mean_cost for n in names},
                }
                for cell, names in candidates.items()
            },
            "contest_incumbent": contest,
            "contest_pooled_validation_cost": pooled_s,
            "waste_share_N_selected": float(np.mean(priced["N"][selected["N"]].waste)),
            "fill_rate_N_selected": float(np.mean(priced["N"][selected["N"]].fill)),
            "ifpa_shrink_reference": IFPA_SHRINK,
            "D_c": demand,
            "p_c": dict.fromkeys(candidates, 1.0),
            "M_c": margins,
            "headroom": headroom,
            "generalisation": gaps,
            "profiles_at_optimum": profile,
            "restart_from_2": {
                "items_same_factors": int(
                    (restart.factors == i1n_result.factors).all(axis=1).sum()
                ),
                "items": len(world.items),
                "mean_cost_from_1": float(i1n_result.cost.sum()),
                "mean_cost_from_2": float(restart.cost.sum()),
            },
            "seconds": round(time.perf_counter() - started, 1),
        }
    )
    args.tables_out.parent.mkdir(parents=True, exist_ok=True)
    args.report_out.parent.mkdir(parents=True, exist_ok=True)
    tables = {name: tables_document(t, r) for name, (t, r) in versions.items()}
    args.tables_out.write_text(
        json.dumps(tables, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8"
    )
    args.report_out.write_text(
        json.dumps(report, sort_keys=True, indent=1) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {"selected": selected, "contest": contest, "M_c": margins, "seconds": report["seconds"]}
        )
    )
    return 0


def _evaluator(world: ReleaseWorld, tables: IncumbentTables, batch: list[Any]) -> Any:
    def evaluate(factors: np.ndarray) -> np.ndarray:
        trial = IncumbentTables(tables.name, tables.waste_aware, factors.copy(), tables.mean_table)
        return price(world, batch, Incumbent(world, trial)).item_cost

    return evaluate


def _told_evaluator(
    world: ReleaseWorld, base: IncumbentTables, batch: list[Any], guarded: bool
) -> Any:
    """Item costs of the incumbent told the shock, with response factors (through the guard)."""

    def evaluate(factors: np.ndarray) -> np.ndarray:
        oracle = ShockOracle(world, base, batch, factors[:, 0].copy())
        policy: Any = Guarded(oracle, Incumbent(world, base)) if guarded else oracle
        return price(world, batch, policy).item_cost

    return evaluate


if __name__ == "__main__":
    sys.exit(main())
