"""What every SYNAPSE component must be on the release world, each claim shown able to fail.

Truth session 6, stage B (gate items 2, 9, 10 and 14):

* **batch independence**: each replicate decided exactly as alone (freeze W's rule); planted: a
  policy pooling sales across replicates;
* **no carry-over**: an object used for seed j in N then reused for seed j in S1 decides as a fresh
  one (the isolation test's planted class memory covers the failing side);
* **bounded memory**: on the last measured day, a component fed only the observations from 96 hours
  before decides exactly as one fed everything; planted: a call counter;
* **the lane** settles on development seeds: outside L lane P from the first decision, every
  outcome I2-P's; in L lane P at the first decision (no receipt seen yet) and L from the second on;
  planted: a life at receipt one hour short (16 seeds here; ``measure.py`` checks all 128 D1 seeds
  of both worlds against the lane's frozen version);
* **no supply flag** in N, L and S1 on 32 development seeds (no order is ever late there;
  ``measure.py`` counts flags on all D1 seeds);
* **items kept apart** by the components that claim it (sensing, both Sentinels): altering one
  item's observations leaves every other item's orders unchanged; planted: a policy reading the
  store's total sales. The surge, supply and lane components couple items by design (decision
  S6-D-06; supply flags a supplier, the lane is the store's);
* **construction inputs hold no protected seed**: no number in a parameter file is a validation,
  D2, D3 or D4 seed; planted: a D2 seed in a copy;
* **golden decisions**: a digest of each component's orders on a fixed development replicate, which
  Linux CI must reproduce bit for bit (exact arithmetic, gate item 8).
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from synapse_kernel.challengers import history as history_module
from synapse_kernel.challengers.registry import build
from synapse_kernel.challengers.shelf import LaneIncumbent
from synapse_kernel.challengers.supply import SupplyDetector
from synapse_kernel.release import seeds
from synapse_kernel.release.engine import run
from synapse_kernel.release.harness import batch_independent, scenarios
from synapse_kernel.release.incumbent import Incumbent, load_incumbent_tables
from synapse_kernel.release.scenario import build_scenario
from synapse_kernel.release.world import HOURS_PER_DAY, load_release_world

ROOT = Path(__file__).resolve().parents[3]
PARAMS = {"surge_threshold": 2.0**12}
D1 = range(64, 192)
#: (component, a cell where it acts)
WHERE = (
    ("lane_incumbent", "L"),
    ("sensing", "N"),
    ("surge_today", "S1"),
    ("surge_ahead", "S1"),
    ("supply", "S3"),
    ("sentinel_as_built", "N"),
    ("sentinel_world", "N"),
)


@pytest.fixture(scope="module")
def world() -> Any:
    return load_release_world()


@pytest.fixture(scope="module")
def tables() -> Any:
    return load_incumbent_tables()


def _make(name: str, world: Any, tables: Any) -> Any:
    return build(name, world, tables, PARAMS)


class _Log:
    """Wraps a policy and keeps every observation and every order it gave."""

    def __init__(self, inner: Any) -> None:
        self.inner = inner
        self.observations: list[Any] = []
        self.orders: list[Any] = []

    def start(self, replicates: int) -> None:
        self.inner.start(replicates)

    def decide(self, obs: Any) -> Any:
        out = np.asarray(self.inner.decide(obs)).copy()
        self.observations.append(obs)
        self.orders.append(out)
        return out


def _orders(policy: Any, world: Any, cell: str, k: int) -> _Log:
    log = _Log(policy)
    run(world, [build_scenario(world, cell, seeds.explore_seed(k))], log)
    return log


# -- batch independence --------------------------------------------------------------------------


@pytest.mark.parametrize(("name", "cell"), WHERE)
def test_every_component_decides_each_replicate_as_alone(
    name: str, cell: str, world: Any, tables: Any
) -> None:
    batch = scenarios(world, cell, seeds.explore_seeds(range(64, 66)))
    assert batch_independent(world, lambda: _make(name, world, tables), batch)


class _Pooler:
    """Planted: orders one more where the batch's other replicates sold more than this one."""

    def __init__(self, inner: Any) -> None:
        self.inner = inner

    def start(self, replicates: int) -> None:
        self.inner.start(replicates)

    def decide(self, obs: Any) -> Any:
        out = np.asarray(self.inner.decide(obs))
        sold = obs.sales.sum(axis=1)
        more = (sold < sold.mean(axis=0, keepdims=True)) & obs.deciding[None, :]
        return out + more.astype(np.int64)


def test_a_pooling_policy_is_caught(world: Any, tables: Any) -> None:
    batch = scenarios(world, "N", seeds.explore_seeds(range(64, 66)))
    assert not batch_independent(
        world, lambda: _Pooler(LaneIncumbent(world, tables["I2-P"], tables["I2-L"])), batch
    )


# -- carry-over and bounded memory ---------------------------------------------------------------


@pytest.mark.parametrize("name", [n for n, _ in WHERE])
def test_nothing_carries_from_one_replicate_to_the_next(name: str, world: Any, tables: Any) -> None:
    used = _make(name, world, tables)
    _orders(used, world, "N", 64)
    again = _orders(used, world, "S1", 64).orders
    fresh = _orders(_make(name, world, tables), world, "S1", 64).orders
    assert all(np.array_equal(a, b) for a, b in zip(again, fresh, strict=True))


def _schedule(world: Any) -> list[int]:
    return [
        h
        for h in range(world.horizon_hours)
        if any(h % HOURS_PER_DAY in s.cutoff_hours for s in world.suppliers)
    ]


def _last_day_agrees(make: Any, world: Any, cell: str, k: int) -> bool:
    """Whether a component fed only the last 96 hours' observations decides the last day as one
    fed everything (both started afresh)."""
    full = _orders(make(), world, cell, k)
    hours = _schedule(world)
    last_day = hours[-1] // HOURS_PER_DAY
    first_last = next(d for d, h in enumerate(hours) if h // HOURS_PER_DAY == last_day)
    begin = next(d for d, h in enumerate(hours) if h >= hours[first_last] - 96)
    late = make()
    late.start(1)
    orders = [np.asarray(late.decide(obs)) for obs in full.observations[begin:]]
    tail = orders[first_last - begin :]
    return all(np.array_equal(a, b) for a, b in zip(tail, full.orders[first_last:], strict=True))


@pytest.mark.parametrize(("name", "cell"), WHERE)
def test_the_last_day_needs_only_the_last_72_hours(
    name: str, cell: str, world: Any, tables: Any
) -> None:
    assert _last_day_agrees(lambda: _make(name, world, tables), world, cell, 67)


class _Counter:
    """Planted: orders one more of everything after its fortieth call."""

    def __init__(self, inner: Any) -> None:
        self.inner = inner
        self.calls = 0

    def start(self, replicates: int) -> None:
        self.inner.start(replicates)
        self.calls = 0

    def decide(self, obs: Any) -> Any:
        self.calls += 1
        out = np.asarray(self.inner.decide(obs))
        return out + (obs.deciding[None, :] & (self.calls > 40)).astype(np.int64)


def test_a_call_counter_is_caught(world: Any, tables: Any) -> None:
    make = lambda: _Counter(LaneIncumbent(world, tables["I2-P"], tables["I2-L"]))  # noqa: E731
    assert not _last_day_agrees(make, world, "N", 67)


# -- the lane ------------------------------------------------------------------------------------


def _lane_violations(world: Any, tables: Any, ks: range) -> list[str]:
    """Where the lane rule did not do what gate item 2 says.

    Outside L, lane P holds from the first decision, so every outcome must be I2-P's, field by
    field. In L, the first decision (02:00 on day 0) comes before any receipt shows a life, so the
    lane is P there and L from the second decision on (the hub's first receipt lands at 06:00).
    """
    out: list[str] = []
    for cell in ("N", "L", "S1", "S2", "S3"):
        batch = scenarios(world, cell, seeds.explore_seeds(ks))
        lane = LaneIncumbent(world, tables["I2-P"], tables["I2-L"])
        trace: list[Any] = []

        class Watch:
            def start(self, replicates: int, lane: Any = lane, trace: Any = trace) -> None:
                lane.start(replicates)
                trace.clear()

            def decide(self, obs: Any, lane: Any = lane, trace: Any = trace) -> Any:
                trace.append(lane.observe(obs).copy())
                return lane.incumbent_orders(obs)

        got = run(world, batch, Watch())
        if cell != "L":
            want = run(world, batch, Incumbent(world, tables["I2-P"]))
            for r, k in enumerate(ks):
                fields = [f.name for f in dataclasses.fields(got)]
                if not all(np.array_equal(getattr(got, f)[r], getattr(want, f)[r]) for f in fields):
                    out.append(f"{cell} k {k}: not I2-P's outcome")
        for r, k in enumerate(ks):
            lanes = [bool(t[r]) for t in trace]
            expected = [cell == "L" and d > 0 for d in range(len(lanes))]
            if lanes != expected:
                out.append(f"{cell} k {k}: lane by decision {lanes[:4]}...")
    return out


def test_the_lane_settles_on_development_seeds(world: Any, tables: Any) -> None:
    # 16 seeds here; the stage-B measurement checks all 128 D1 seeds of both worlds.
    assert _lane_violations(world, tables, range(64, 80)) == []


def test_the_lane_settles_on_deviation_1s_world() -> None:
    from scripts.challengers import child

    world_d1, tables_d1, _ = child.load("W-d1")
    assert _lane_violations(world_d1, tables_d1, range(64, 72)) == []


def test_the_old_lane_p_for_good_rule_is_caught(monkeypatch: pytest.MonkeyPatch) -> None:
    """Planted: the gate's first rule, lane P for good once a life equals its declared one, which
    W-d1's 12-hour items (whole in L, at the floor) satisfy (decision S6-D-10)."""
    from scripts.challengers import child
    from synapse_kernel.challengers import shelf

    def old_update(self: Any, history: Any) -> Any:
        known = history.life >= 0
        normal = (known & (history.life == self.declared[None, :])).any(axis=1)
        self.normal = getattr(self, "normal", np.zeros_like(normal)) | normal
        shorter = (known & (history.life < self.declared[None, :])).any(axis=1)
        self.short = shorter & ~self.normal
        return self.short.copy()

    monkeypatch.setattr(shelf.Lane, "update", old_update)
    world_d1, tables_d1, _ = child.load("W-d1")
    assert any(
        " L k " in v or v.startswith("L k")
        for v in _lane_violations(world_d1, tables_d1, range(64, 66))
    )


def test_a_life_one_hour_short_is_caught(
    world: Any, tables: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    true = history_module.History._learn_life

    def planted(self: Any, on_hand: Any, expiry: Any, received_at: Any, length: int) -> None:
        true(self, on_hand, expiry, received_at, length)
        self.life = np.where(self.life >= 0, self.life - 1, self.life)

    monkeypatch.setattr(history_module.History, "_learn_life", planted)
    assert _lane_violations(world, tables, range(64, 66)) != []


# -- supply flags --------------------------------------------------------------------------------


def test_no_supply_flag_without_a_supply_shock(world: Any, tables: Any) -> None:
    detector = SupplyDetector(world)
    flagged: dict[str, int] = {}
    for cell in ("N", "L", "S1"):
        lane = LaneIncumbent(world, tables["I2-P"], tables["I2-L"])
        count = [0]

        class Watch:
            def start(self, replicates: int, lane: Any = lane) -> None:
                lane.start(replicates)

            def decide(self, obs: Any, lane: Any = lane, count: Any = count) -> Any:
                lane.observe(obs)
                count[0] += int(np.count_nonzero(detector.disrupted(obs)))
                return lane.incumbent_orders(obs)

        run(world, scenarios(world, cell, seeds.explore_seeds(range(64, 96))), Watch())
        flagged[cell] = count[0]
    assert flagged == {"N": 0, "L": 0, "S1": 0}
    seen = [0]
    lane = LaneIncumbent(world, tables["I2-P"], tables["I2-L"])

    class Shocked:
        def start(self, replicates: int) -> None:
            lane.start(replicates)

        def decide(self, obs: Any) -> Any:
            lane.observe(obs)
            seen[0] += int(np.count_nonzero(detector.disrupted(obs)))
            return lane.incumbent_orders(obs)

    run(world, scenarios(world, "S3", seeds.explore_seeds(range(64, 72))), Shocked())
    assert seen[0] > 0  # the detector can fire: an outage leaves orders late


# -- items kept apart ----------------------------------------------------------------------------


def _alter_item(obs: Any, item: int) -> Any:
    """The same observation with one item's sales since the last decision removed."""
    import dataclasses

    sales = np.asarray(obs.sales).copy()
    sales[:, :, item] = 0
    return dataclasses.replace(obs, sales=sales)


def _apart(make: Any, world: Any, cell: str, k: int, item: int) -> bool:
    log = _orders(make(), world, cell, k)
    other = make()
    other.start(1)
    orders = [np.asarray(other.decide(_alter_item(obs, item))) for obs in log.observations]
    keep = np.ones(len(world.items), dtype=bool)
    keep[item] = False
    return all(
        np.array_equal(a[:, keep], b[:, keep]) for a, b in zip(orders, log.orders, strict=True)
    )


@pytest.mark.parametrize("name", ["sensing", "sentinel_as_built", "sentinel_world"])
def test_altering_one_item_leaves_the_others_alone(name: str, world: Any, tables: Any) -> None:
    assert _apart(lambda: _make(name, world, tables), world, "N", 64, item=7)


class _Total:
    """Planted: orders one more of an item whenever the store's sales since the last decision are
    odd in number (any change to one item's sales can flip it)."""

    def __init__(self, inner: Any) -> None:
        self.inner = inner

    def start(self, replicates: int) -> None:
        self.inner.start(replicates)

    def decide(self, obs: Any) -> Any:
        out = np.asarray(self.inner.decide(obs))
        odd = np.asarray(obs.sales).sum(axis=(1, 2)) % 2 == 1
        return out + (odd[:, None] & obs.deciding[None, :]).astype(np.int64)


def test_a_policy_reading_the_store_total_is_caught(world: Any, tables: Any) -> None:
    make = lambda: _Total(_make("sensing", world, tables))  # noqa: E731
    assert not _apart(make, world, "N", 64, item=7)


# -- construction inputs -------------------------------------------------------------------------

PROTECTED = (range(32, 64), range(192, 320), range(448, 648), range(648, 776))


def _protected_seeds_in(document: Any) -> list[int]:
    banned = {seeds.explore_seed(k) for span in PROTECTED for k in span}
    found: list[int] = []

    def walk(x: Any) -> None:
        if isinstance(x, dict):
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)
        elif isinstance(x, int) and not isinstance(x, bool) and x in banned:
            found.append(x)

    walk(document)
    return found


def test_no_parameter_file_holds_a_protected_seed() -> None:
    files = sorted((ROOT / "docs" / "truth" / "challengers").glob("params-*.json"))
    for path in files:
        assert _protected_seeds_in(json.loads(path.read_text(encoding="utf-8"))) == [], path
    planted = {"surge_threshold": 4096.0, "note": [seeds.explore_seed(200)]}
    assert _protected_seeds_in(planted) == [seeds.explore_seed(200)]


# -- golden decisions ----------------------------------------------------------------------------

#: sha256 of each component's orders (int64, in decision order) on D1 seed k 67 in its cell, built
#: with ``PARAMS``; measured on Windows (numpy 2.4.4), to be reproduced on Linux CI.
GOLDEN: dict[str, str] = {
    "lane_incumbent": "e60b12586d4a992b97f58d47df44c43d29b004d9eb19d908f01c70315ccc0cb9",
    "sensing": "cd50a7054c19ed92a0324f935069ace81f3669acfac23dc34cd42f06718b48da",
    "surge_today": "86add78b1de434ca35d1523a97dc1c847ad6f91b37b1e23c12b446f9cac5dfe2",
    "surge_ahead": "e1baeafd8025fdd627192895a77899e7892c5186ab5830eb18a37b7dc49c7813",
    "supply": "3a56501253c9bd2d035a9c31ade7b07ba562a5fa11f73250db55f082c03f51c2",
    "sentinel_as_built": "cc9a80b38cf7206e3dc2fa20352970bb0a3421a409fdb37e660dd751f533a05b",
    "sentinel_world": "94f37bf1b20b7460fe70b9125737cbc891200ad9bf032565fc02158d7ca31a23",
}


@pytest.mark.parametrize(("name", "cell"), WHERE)
def test_golden_decisions(name: str, cell: str, world: Any, tables: Any) -> None:
    log = _orders(_make(name, world, tables), world, cell, 67)
    digest = hashlib.sha256()
    for orders in log.orders:
        digest.update(np.ascontiguousarray(orders, dtype=np.int64).tobytes())
    assert digest.hexdigest() == GOLDEN[name], f"{name} {cell}: {digest.hexdigest()}"
