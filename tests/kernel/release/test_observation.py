"""What a release policy may see and be built from: exactly PREREG-1 section 1, and nothing more.

No policy can read the cell, a shock, the day index or the horizon: the observation's fields are
enumerated, every time in it is relative (shifting the clock by whole weeks changes no byte), and no
object of the world's own reaches the policy. Construction inputs are byte-identical across the
five cells.
"""

from __future__ import annotations

import dataclasses
from typing import Any

import numpy as np

from synapse_kernel.release import engine
from synapse_kernel.release.cells import CELLS, Shock
from synapse_kernel.release.engine import observe, run
from synapse_kernel.release.observation import OBSERVATION_FIELDS, PolicyInputs, StoreObservation
from synapse_kernel.release.scenario import Scenario, build_scenario
from synapse_kernel.release.world import ReleaseWorld
from tests.kernel.release.fixtures import OrderUpTo, small_world

ALLOWED = (
    "hour_of_day",
    "day_of_week",
    "deciding",
    "sales",
    "receipts",
    "on_hand",
    "hours_to_expiry",
    "open_qty",
    "open_age_hours",
    "landed_lead_hours",
)


def test_the_observation_holds_exactly_the_sealed_fields() -> None:
    assert OBSERVATION_FIELDS == ALLOWED
    forbidden = ("cell", "shock", "day_index", "horizon", "hour", "time", "seed", "onset")
    assert not [name for name in OBSERVATION_FIELDS if name in forbidden]


def test_shifting_the_clock_by_whole_weeks_changes_no_byte_of_the_observation() -> None:
    rng = np.random.default_rng(5)  # test inputs only; the world itself never uses this
    reps, items, slots = 2, 4, 6
    hour = 200
    qty = rng.integers(0, 9, (reps, items, slots)).astype(np.int64)
    expiry = hour + rng.integers(1, 90, (reps, items, slots)).astype(np.int64)
    open_qty = rng.integers(0, 5, (reps, items, slots)).astype(np.int64)
    placed = np.where(open_qty > 0, hour - rng.integers(0, 30, (reps, items, slots)), -1)
    landed = rng.integers(-1, 30, (reps, items, slots)).astype(np.int64)
    sales = rng.integers(0, 4, (reps, 5, items)).astype(np.int32)
    receipts = rng.integers(0, 4, (reps, 6, items)).astype(np.int32)
    deciding = np.array([True, False, True, False])
    week = 168
    here = observe(hour, deciding, sales, receipts, qty, expiry, open_qty, placed, landed)
    later_placed = np.where(placed >= 0, placed + week, -1)
    there = observe(
        hour + week, deciding, sales, receipts, qty, expiry + week, open_qty, later_placed, landed
    )
    for name in OBSERVATION_FIELDS:
        a, b = getattr(here, name), getattr(there, name)
        assert np.array_equal(np.asarray(a), np.asarray(b)), name


class _Recorder:
    """Records every observation; orders like a plain base stock."""

    def __init__(self, world: ReleaseWorld) -> None:
        self.inner = OrderUpTo(world, 1.2)
        self.seen: list[StoreObservation] = []

    def start(self, replicates: int) -> None:
        self.inner.start(replicates)

    def decide(self, obs: StoreObservation) -> np.ndarray:
        self.seen.append(obs)
        return self.inner.decide(obs)


def _world_objects(value: Any) -> bool:
    return isinstance(value, (Scenario, Shock, ReleaseWorld))


def test_no_object_of_the_world_and_no_absolute_time_reaches_a_policy() -> None:
    world = small_world(items=6)
    recorder = _Recorder(world)
    run(world, [build_scenario(world, "S3", 2)], recorder)
    assert recorder.seen
    longest_life = max(item.shelf_life_hours for item in world.items)
    cutoffs = {h for s in world.suppliers for h in s.cutoff_hours}
    for obs in recorder.seen:
        assert not any(_world_objects(getattr(obs, f.name)) for f in dataclasses.fields(obs))
        assert int(obs.hours_to_expiry.max()) <= longest_life
        assert obs.hour_of_day in cutoffs
        ages = obs.open_age_hours[obs.open_age_hours >= 0]
        assert ages.size == 0 or int(ages.max()) < world.horizon_hours // 2


def test_construction_inputs_are_byte_identical_across_the_five_cells() -> None:
    world = small_world(items=5)
    records = {"N": {7: build_scenario(world, "N", 7).demand}}
    built_for = {
        cell: PolicyInputs(world=world, records=records).canonical_bytes() for cell in CELLS
    }
    assert len(set(built_for.values())) == 1
    other = PolicyInputs(world=world, records={"N": {8: build_scenario(world, "N", 8).demand}})
    assert other.canonical_bytes() != built_for["N"]  # the digest sees the records


def test_the_engine_hands_a_policy_only_observations() -> None:
    seen_types: set[type] = set()

    class Spy:
        def start(self, replicates: int) -> None:
            return None

        def decide(self, obs: object) -> np.ndarray:
            seen_types.add(type(obs))
            assert isinstance(obs, StoreObservation)
            return np.zeros(obs.on_hand.shape[:2], dtype=np.int64)

    world = small_world(items=3)
    engine.run(world, [build_scenario(world, "S1", 1)], Spy())
    assert seen_types == {StoreObservation}
