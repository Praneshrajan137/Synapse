"""Pinned bits: the release world's draws and one engine run, computed on Windows, checked anywhere.

The digests below were computed on the laptop (Windows, CPython 3.11, numpy 2.4.4) when the engine
was written. The kernel workflow runs this file on Linux (and session 8 runs it under Pyodide), so
a platform that computes any draw, count or cost differently fails here, naming what moved.
"""

from __future__ import annotations

import hashlib

import numpy as np
import pytest

from synapse_kernel.release.engine import run
from synapse_kernel.release.objective import replicate_costs
from synapse_kernel.release.scenario import build_scenario
from tests.kernel.release.fixtures import OrderUpTo, small_world

BIG_SEED = 2**62 + 12345
DEMAND = {
    ("N", 0): "c52b739d440cb760",
    ("N", BIG_SEED): "13c1ce1b1837adb7",
    ("S1", 0): "93bf80023a6285c5",
    ("S1", BIG_SEED): "86fbd1fa12b9ba3c",
}
OUTCOME = "60672ea0207d3f05"
COSTS = ("0x1.8bc0219a044e0p+3", "0x1.a8246640c7a4bp+3", "0x1.d4717b78c95d3p+3")


@pytest.mark.parametrize(("cell", "seed"), sorted(DEMAND))
def test_a_scenarios_demand_has_the_pinned_bits(cell: str, seed: int) -> None:
    demand = build_scenario(small_world(items=12), cell, seed).demand_digest()[:16]
    assert demand == DEMAND[(cell, seed)]


def test_an_engine_run_has_the_pinned_outcome_and_costs() -> None:
    world = small_world(items=12)
    scenarios = [build_scenario(world, "S3", seed) for seed in (1, 2, 3)]
    out = run(world, scenarios, OrderUpTo(world, 1.25))
    digest = hashlib.sha256()
    for name in (
        "demanded",
        "sold",
        "lost",
        "wasted",
        "holding2",
        "received",
        "end_on_hand",
        "end_on_order",
    ):
        digest.update(np.ascontiguousarray(getattr(out, name), dtype=np.int64).tobytes())
    assert digest.hexdigest()[:16] == OUTCOME
    assert tuple(cost.hex() for cost in replicate_costs(world, out)) == COSTS
