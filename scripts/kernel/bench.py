"""Stage C: how long the release world takes, measured, so sessions 5 to 8 budget from numbers.

``python -m scripts.kernel.bench [--world PATH] [--json-out FILE]`` times, on the release world:

* drawing one replicate's scenario (all its demand, day factors and shock);
* running the engine with the incumbent's rule (I1 and I2, factors 1) on one replicate alone, and
  on batches of 32 and 128 replicates of cell N (the seed axis vectorised);
* a simulated day of one replicate (the replicate's time over its days), the unit the browser's
  budget is stated in (PLAN 9.1 row 8: under 3 s on a mid laptop).

Each timing is the minimum of three runs (the least disturbed by other work), with the machine's
CPU count and platform reported; the power state is recorded by whoever runs it (truth log). Every
digest printed must equal the native run's when the same command runs elsewhere (CI, Pyodide).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import sys
import time
from pathlib import Path
from typing import Any, Final

import numpy as np

from synapse_kernel.release import seeds
from synapse_kernel.release.engine import run
from synapse_kernel.release.harness import mean_demand_table, scenarios
from synapse_kernel.release.incumbent import Incumbent, IncumbentTables
from synapse_kernel.release.objective import replicate_costs
from synapse_kernel.release.scenario import build_scenario
from synapse_kernel.release.world import RELEASE_WORLD, load_release_world

ROOT: Final[Path] = Path(__file__).resolve().parents[2]
REPEATS: Final[int] = 3


def _best(fn: Any) -> tuple[float, Any]:
    times, result = [], None
    for _ in range(REPEATS):
        started = time.perf_counter()
        result = fn()
        times.append(time.perf_counter() - started)
    return min(times), result


def measure(world_path: Path) -> dict[str, Any]:
    world = load_release_world(world_path)
    tuning = seeds.explore_seeds(seeds.TUNING)
    out: dict[str, Any] = {
        "platform": platform.platform(),
        "python": platform.python_version(),
        "numpy": np.__version__,
        "logical_cpus": os.cpu_count(),
        "items": len(world.items),
        "horizon_days": world.horizon_hours // 24,
    }
    seconds, scenario = _best(lambda: build_scenario(world, "N", tuning[0]))
    out["scenario_seconds"] = seconds
    out["scenario_digest"] = scenario.demand_digest()[:16]
    table = mean_demand_table(world, [scenarios(world, "N", tuning[:4])])
    for aware, tag in ((False, "I1"), (True, "I2")):
        tables = IncumbentTables(tag, aware, np.ones((len(world.items), 6)), table)
        for size in (1, 32, 128):
            batch = scenarios(world, "N", seeds.explore_seeds(range(size)))
            seconds, result = _best(lambda b=batch, t=tables: run(world, b, Incumbent(world, t)))
            costs = replicate_costs(world, result)
            out[f"{tag}_batch{size}_seconds"] = seconds
            out[f"{tag}_batch{size}_per_replicate_seconds"] = seconds / size
            out[f"{tag}_batch{size}_cost_digest"] = hashlib.sha256(
                "".join(c.hex() for c in costs).encode()
            ).hexdigest()[:16]
        out[f"{tag}_simulated_day_seconds"] = out[f"{tag}_batch1_seconds"] / out["horizon_days"]
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m scripts.kernel.bench")
    parser.add_argument("--world", type=Path, default=RELEASE_WORLD)
    parser.add_argument("--json-out", type=Path, default=None)
    args = parser.parse_args(argv)
    result = measure(args.world)
    text = json.dumps(result, sort_keys=True, indent=1)
    print(text)
    if args.json_out is not None:
        args.json_out.write_text(text + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
