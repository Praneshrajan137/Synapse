"""The release engine: stock that ages and spoils, sold first in first out, and nothing random.

The acceptance conditions of session 5's stage B that live here: waste rises with stock held (it
did not in the legacy twin, truth finding F-30); a policy's orders move no random draw; each
replicate computes the same alone or in a batch; one item's orders leave every other item alone;
and units are conserved exactly.
"""

from __future__ import annotations

import ast
import dataclasses
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
import pytest

from synapse_kernel.release import engine
from synapse_kernel.release.cells import Shock
from synapse_kernel.release.engine import run
from synapse_kernel.release.scenario import Scenario, build_scenario
from tests.kernel.release.fixtures import Never, OrderUpTo, small_world

if TYPE_CHECKING:
    from synapse_kernel.release.observation import StoreObservation

RELEASE = Path(__file__).resolve().parents[3] / "synapse_kernel" / "release"


def _conserved(out: engine.Outcome) -> bool:
    lhs = out.initial + out.received_all
    rhs = out.sold_all + out.wasted_all + out.end_on_hand
    return bool(np.array_equal(lhs, rhs))


def test_units_are_conserved_exactly_under_any_policy() -> None:
    world = small_world(items=10)
    scenarios = [build_scenario(world, cell, 3) for cell in ("N",)]
    for policy in (Never(), OrderUpTo(world, 0.6), OrderUpTo(world, 2.5)):
        out = run(world, scenarios, policy)
        assert _conserved(out)
        assert bool(np.array_equal(out.lost + out.sold, out.demanded))


def test_waste_rises_with_stock_held() -> None:
    """F-30 repaired: in the legacy twin spoilage was a clock no order could move."""
    world = small_world(items=12)
    scenarios = [build_scenario(world, "N", seed) for seed in range(8)]
    wasted, held = [], []
    for factor in (0.5, 1.0, 1.5, 2.5):
        out = run(world, scenarios, OrderUpTo(world, factor))
        wasted.append(int(out.wasted.sum()))
        held.append(int(out.holding2.sum()))
    assert wasted == sorted(wasted) and len(set(wasted)) == 4, wasted
    assert held == sorted(held) and len(set(held)) == 4, held


def test_in_the_legacy_twin_spoilage_did_not_depend_on_stock_finding_f30() -> None:
    from synapse_kernel import drive
    from synapse_kernel.drive import run_replicate
    from synapse_kernel.policies.tuned import GroupParLevelReorder, Levels, sku_groups
    from synapse_kernel.world import load_world

    world = load_world()
    spoiled = []
    for s, big_s in ((5, 20), (100, 400)):
        levels = {g: Levels(s, big_s) for g in ("sup_a", "sup_b", "sup_c")}
        policy = GroupParLevelReorder(levels, sku_groups(world, drive.CANONICAL_SKUS))
        spoiled.append(run_replicate(4248394379, policy, world).metrics.orders_spoiled)
    assert spoiled[0] == spoiled[1]  # the clock ticks the same whatever is held


def test_the_oldest_batch_sells_first() -> None:
    """A hand-made day: FIFO sells all six units; LIFO would waste one and lose one."""
    base = small_world(items=1)
    item = dataclasses.replace(base.items[0], supplier="hub", rate_per_day=1.0, shelf_life_hours=24)
    world = dataclasses.replace(base, items=(item,))
    assert int(engine.initial_stock(world)[0]) == 1  # batch A: 1 unit, expires at hour 24
    demand = np.zeros((world.horizon_hours, 1), dtype=np.int64)
    demand[10, 0] = 1  # FIFO takes it from batch A
    demand[26, 0] = 5  # after A's expiry: batch B (5 units, landed 06:00, expires 30) covers it
    scene = Scenario(0, "N", demand, Shock("none"), np.array([24], dtype=np.int64))

    class FiveOnce:
        def __init__(self) -> None:
            self.done = False

        def start(self, replicates: int) -> None:
            self.done = False

        def decide(self, obs: StoreObservation) -> np.ndarray:
            ordered = np.zeros((1, 1), dtype=np.int64)
            if obs.hour_of_day == 2 and not self.done:  # the hub's 02:00 cut-off: lands 06:00
                self.done = True
                ordered[0, 0] = 5
            return ordered

    out = run(world, [scene], FiveOnce())
    assert int(out.sold_all[0, 0]) == 6
    assert int(out.wasted_all[0, 0]) == 0
    assert _conserved(out)


def test_a_policys_orders_move_no_random_draw() -> None:
    world = small_world(items=10)
    scenarios = [build_scenario(world, "S1", seed) for seed in (1, 2)]
    before = [s.demand_digest() for s in scenarios]
    starved = run(world, scenarios, Never())
    flooded = run(world, scenarios, OrderUpTo(world, 4.0))
    assert [s.demand_digest() for s in scenarios] == before
    assert np.array_equal(starved.demanded, flooded.demanded)  # same demand met very differently
    assert not np.array_equal(starved.sold, flooded.sold)
    rebuilt = [build_scenario(world, "S1", seed).demand_digest() for seed in (1, 2)]
    assert rebuilt == before


def test_the_engine_holds_no_generator() -> None:
    tree = ast.parse((RELEASE / "engine.py").read_text(encoding="utf-8"))
    imported = {
        node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
    } | {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    assert not any("rng" in name or "random" in name or "sampling" in name for name in imported)


def test_a_replicate_computes_the_same_alone_or_in_a_batch() -> None:
    world = small_world(items=8)
    scenarios = [build_scenario(world, "S3", seed) for seed in (4, 5, 6)]
    together = run(world, scenarios, OrderUpTo(world, 1.3))
    for r, scene in enumerate(scenarios):
        alone = run(world, [scene], OrderUpTo(world, 1.3))
        for field in dataclasses.fields(engine.Outcome):
            assert np.array_equal(getattr(alone, field.name)[0], getattr(together, field.name)[r])


def test_one_items_orders_leave_every_other_item_alone() -> None:
    world = small_world(items=8)
    scenarios = [build_scenario(world, "N", seed) for seed in (7, 8)]

    class Doubled(OrderUpTo):
        def decide(self, obs: object) -> np.ndarray:
            out = super().decide(obs)
            out[:, 0] *= 2
            return out

    plain = run(world, scenarios, OrderUpTo(world, 1.0))
    doubled = run(world, scenarios, Doubled(world, 1.0))
    assert not np.array_equal(plain.wasted[:, 0], doubled.wasted[:, 0]) or not np.array_equal(
        plain.holding2[:, 0], doubled.holding2[:, 0]
    )
    for field in dataclasses.fields(engine.Outcome):
        assert np.array_equal(
            getattr(plain, field.name)[:, 1:], getattr(doubled, field.name)[:, 1:]
        )


def test_the_warm_up_is_never_priced() -> None:
    world = small_world(items=6)
    scene = build_scenario(world, "N", 9)
    out = run(world, [scene], Never())
    measured = scene.demand[world.measured_start_hour :].sum(axis=0)
    assert np.array_equal(out.demanded[0], measured)


@pytest.mark.parametrize("fault", ["negative", "not-deciding", "shape", "float"])
def test_an_order_the_world_cannot_take_is_refused(fault: str) -> None:
    world = small_world(items=4)
    scene = build_scenario(world, "N", 1)

    class Bad:
        def start(self, replicates: int) -> None:
            return None

        def decide(self, obs: StoreObservation) -> np.ndarray:
            deciding = obs.deciding
            out = np.zeros((1, 4), dtype=np.int64)
            if fault == "negative":
                out[0, int(np.argmax(deciding))] = -1
            elif fault == "not-deciding":
                if bool(deciding.all()):
                    return out
                out[0, int(np.argmin(deciding))] = 1
            elif fault == "shape":
                return np.zeros((1, 3), dtype=np.int64)
            else:
                return out.astype(np.float64)
            return out

    with pytest.raises(ValueError):
        run(world, [scene], Bad())
