"""``s_c`` and ``n_c`` per cell and world, on the 32 validation seeds, with the arms of freeze C.

PREREG-1 section 6: ``n_c = min(2000, max(200, ceil((2 * 1.96 * s_c / M_c)^2)))``, with ``s_c`` the
standard deviation (``n - 1``) of the paired differences ``J_SYNAPSE - J_incumbent`` on the 32
validation seeds (k 32-63), fixed at freeze C. SYNAPSE is the composition committed in stage C
(``docs/truth/composition/params-<world>.json``), a fresh child process per replicate with both
replays; the incumbent is the cell's selected version (frozen, in this process). Every delta is
published, and per claim what the run could detect at ``n_c``: for C1 the largest mean delta whose
upper 97.5% bound still clears ``M_c`` at that spread, for C2 the mean advantage whose lower bound
clears ``M_c`` at Holm's first step (one-sided ``1 - 0.025 / 4``), both under a normal approximation
(a guide for the reader; the analysis itself is the BCa bootstrap).

``python -m scripts.confirm.power`` writes ``docs/truth/composition/power.json`` before freeze C,
and after it a rehearsal's ``docs/truth/confirm/rehearsals/power.json``: it never overwrites a
frozen file (:mod:`scripts.confirm.outputs`).
"""

from __future__ import annotations

import argparse
import json
import math
import subprocess
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from statistics import NormalDist
from typing import Any

from scripts.challengers import child
from scripts.challengers.isolate import SPAWN, Spec, run_one, summarise
from scripts.confirm.outputs import record_dir, write_json
from synapse_kernel.proof.analysis import CELLS, replicates_for, sample_sd
from synapse_kernel.release import seeds

ROOT = Path(__file__).resolve().parents[2]
COMPOSITION = ROOT / "docs" / "truth" / "composition"
REPORTS = {
    "W": ROOT / "docs" / "truth" / "world" / "incumbent-report.json",
    "W-d1": ROOT / "docs" / "truth" / "world" / "incumbent-report-d1.json",
}
WORLDS = ("W", "W-d1")
VALIDATION = range(32, 64)


def _pair(job: tuple[str, str, int]) -> dict[str, Any]:
    from synapse_kernel.release import integrity
    from synapse_kernel.release.engine import run
    from synapse_kernel.release.incumbent import Incumbent
    from synapse_kernel.release.scenario import build_scenario

    world_label, cell, k = job
    world, tables, _ = child.load(world_label)
    integrity.assert_frozen()
    version = json.loads(REPORTS[world_label].read_text(encoding="utf-8"))["selection"][cell][
        "selected"
    ]
    seed = seeds.explore_seed(k)
    scenario = build_scenario(world, cell, seed)
    incumbent = summarise(world, run(world, [scenario], Incumbent(world, tables[version])))
    synapse = run_one(
        Spec("synapse", world_label, params=f"docs/truth/composition/params-{world_label}.json"),
        cell,
        seed,
    )
    if not (synapse["outcome_replay"] and synapse["decision_replay"]):
        raise RuntimeError(f"a replay failed: {world_label} {cell} k {k}")
    child.check(world_label, world, tables)
    return {
        "k": k,
        "delta": synapse["cost"] - incumbent["cost"],
        "version": version,
        "orders_digest": synapse["orders_digest"],
    }


def summarise_power(
    rows_by_job: list[tuple[tuple[str, str, int], dict[str, Any]]],
) -> dict[str, Any]:
    """Per world and cell: every delta, ``s_c`` (``n - 1``), ``n_c`` and what ``n_c`` can detect."""
    z_c1 = NormalDist().inv_cdf(0.975)
    z_c2 = NormalDist().inv_cdf(1.0 - 0.025 / 4)
    worlds: dict[str, Any] = {}
    for w in WORLDS:
        margins = json.loads(REPORTS[w].read_text(encoding="utf-8"))["M_c"]
        cells: dict[str, Any] = {}
        for cell in CELLS:
            rows = sorted(
                (r for (jw, jc, _), r in rows_by_job if jw == w and jc == cell),
                key=lambda r: int(r["k"]),
            )
            if [int(r["k"]) for r in rows] != list(VALIDATION):
                raise RuntimeError(f"{w} {cell}: validation seeds missing or repeated")
            deltas = [float(r["delta"]) for r in rows]
            s_c = sample_sd(deltas)
            n_c = replicates_for(s_c, float(margins[cell]))
            se = s_c / math.sqrt(n_c)
            cells[cell] = {
                "incumbent": rows[0]["version"],
                "M_c": float(margins[cell]),
                "deltas": deltas,
                "mean_delta": math.fsum(deltas) / len(deltas),
                "s_c": s_c,
                "n_c": n_c,
                "c1_largest_mean_delta_that_clears": float(margins[cell]) - z_c1 * se,
                "c2_mean_advantage_needed_first_holm_step": float(margins[cell]) + z_c2 * se,
            }
        worlds[w] = cells
    return worlds


def main() -> None:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--workers", type=int, default=10)
    parser.add_argument("--worlds", nargs="+", default=list(WORLDS), choices=WORLDS)
    parser.add_argument("--cells", nargs="+", default=list(CELLS), choices=CELLS)
    parser.add_argument("--raw-out", type=Path, help="run these worlds and cells only")
    parser.add_argument("--merge", type=Path, help="assemble the parts in this folder")
    args = parser.parse_args()
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout.strip()
    t0 = time.perf_counter()
    if args.merge is not None:
        rows_by_job: list[tuple[tuple[str, str, int], dict[str, Any]]] = []
        for path in sorted(args.merge.glob("**/power-part-*.json")):
            part = json.loads(path.read_text(encoding="utf-8"))
            rows_by_job.extend(((w, c, int(k)), row) for (w, c, k), row in part["rows"])
    else:
        jobs = [(w, cell, k) for w in args.worlds for cell in args.cells for k in VALIDATION]
        with ProcessPoolExecutor(max_workers=args.workers, mp_context=SPAWN) as pool:
            done = list(pool.map(_pair, jobs))
        rows_by_job = list(zip(jobs, done, strict=True))
        if args.raw_out is not None:
            tag = "-".join(args.worlds) + "-" + "-".join(args.cells)
            part = {"rows": [[list(job), row] for job, row in rows_by_job], "commit": commit}
            write_json(args.raw_out / f"power-part-{tag}.json", part)
            return
    document = {
        "rule": "PREREG-1 section 6; s_c with n - 1 on the 32 validation seeds (k 32-63)",
        "composition_commit": commit,
        "worlds": summarise_power(rows_by_job),
        "wall_seconds": round(time.perf_counter() - t0, 1),
    }
    write_json(record_dir() / "power.json", document)


if __name__ == "__main__":
    main()
