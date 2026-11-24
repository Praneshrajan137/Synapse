"""The guard of D-4(b) in whole units; the headroom oracle equals the incumbent without a shock."""

from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING

import numpy as np
import numpy.typing as npt
import pytest
from hypothesis import given
from hypothesis import strategies as st

from synapse_kernel.release.cells import Shock
from synapse_kernel.release.engine import run
from synapse_kernel.release.guard import guard
from synapse_kernel.release.harness import mean_demand_table, scenarios
from synapse_kernel.release.incumbent import Incumbent, IncumbentTables
from synapse_kernel.release.oracle import Guarded, ShockOracle
from tests.kernel.release.fixtures import small_world

if TYPE_CHECKING:
    from synapse_kernel.release.observation import StoreObservation
    from synapse_kernel.release.scenario import Scenario
    from synapse_kernel.release.world import ReleaseWorld

UNITS = st.integers(min_value=0, max_value=10_000)


@given(UNITS, UNITS)
def test_the_guard_keeps_a_quantity_within_half_to_twice_the_incumbents(
    want: int, base: int
) -> None:
    got = int(guard(np.array([want]), np.array([base]))[0])
    if base == 0:
        assert got == 0
    else:
        assert (base + 1) // 2 <= got <= 2 * base
        if (base + 1) // 2 <= want <= 2 * base:
            assert got == want


def test_the_guard_on_known_values() -> None:
    base = np.array([0, 1, 2, 3, 10])
    assert guard(np.array([5, 5, 0, 1, 100]), base).tolist() == [0, 2, 1, 2, 20]
    assert guard(np.zeros(5, dtype=np.int64), base).tolist() == [0, 1, 1, 2, 5]


def _tables(world: ReleaseWorld, aware: bool) -> IncumbentTables:
    table = mean_demand_table(world, [scenarios(world, "N", range(4))])
    factors = np.full((len(world.items), 6), 1.25)
    return IncumbentTables("I2" if aware else "I1", aware, factors, table)


def test_without_a_shock_the_oracle_is_the_incumbent_and_the_guard_never_clips() -> None:
    world = small_world(items=9)
    for aware in (False, True):
        tables = _tables(world, aware)
        batch = scenarios(world, "N", (11, 12))
        plain = run(world, batch, Incumbent(world, tables))
        told = run(world, batch, ShockOracle(world, tables, batch))
        guarded_policy = Guarded(ShockOracle(world, tables, batch), Incumbent(world, tables))
        guarded = run(world, batch, guarded_policy)
        for field in dataclasses.fields(plain):
            assert np.array_equal(getattr(plain, field.name), getattr(told, field.name))
            assert np.array_equal(getattr(plain, field.name), getattr(guarded, field.name))
        assert guarded_policy.decisions > 0 and guarded_policy.clipped == 0


def test_told_of_a_surge_the_oracle_orders_more_for_the_surged_items() -> None:
    world = small_world(items=12)
    tables = _tables(world, False)
    batch = scenarios(world, "S1", (5,))
    surged = list(batch[0].shock.items)
    plain = run(world, batch, Incumbent(world, tables))
    told = run(world, batch, ShockOracle(world, tables, batch))
    assert int(told.received_all[0, surged].sum()) > int(plain.received_all[0, surged].sum())


class _FirstDecision:
    """A policy that orders nothing and keeps the first observation at which an item decides."""

    def __init__(self) -> None:
        self.first: StoreObservation | None = None

    def start(self, replicates: int) -> None:
        return None

    def decide(self, obs: StoreObservation) -> npt.NDArray[np.int64]:
        if self.first is None and bool(obs.deciding.any()):
            self.first = obs
        return np.zeros((obs.on_hand.shape[0], obs.on_hand.shape[1]), dtype=np.int64)


def _first_decision(world: ReleaseWorld, seed: int) -> tuple[StoreObservation, Scenario]:
    scenario = scenarios(world, "N", (seed,))[0]
    capture = _FirstDecision()
    run(world, [scenario], capture)
    assert capture.first is not None
    return capture.first, scenario


def test_the_gate_oracle_inserts_a_surge_before_clipping() -> None:
    """Told a doubled demand, the incumbent plans against twice the mean; holding more than that
    target, it orders nothing (the first rule added the surge on top of a zero order)."""
    world = small_world(items=9)
    tables = _tables(world, aware=False)
    obs, plain_scenario = _first_decision(world, 3)
    item = int(np.flatnonzero(obs.deciding)[0])
    surge = Shock("surge", onset_hour=0.0, duration_hours=10_000.0, items=(item,), size=2.0)
    scenario = dataclasses.replace(plain_scenario, shock=surge)
    oracle = ShockOracle(world, tables, [scenario])
    oracle.hour = oracle.decision_hours[0]
    empty = dataclasses.replace(
        obs, on_hand=np.zeros_like(obs.on_hand), open_qty=np.zeros_like(obs.open_qty)
    )
    plain = int(Incumbent(world, tables).decide(empty)[0, item])
    told = int(oracle._decide_one(empty, 0, scenario)[item])
    protection = int(oracle.protection[item, obs.hour_of_day])
    week_hour = obs.day_of_week * 24 + obs.hour_of_day
    mu = float(oracle._window(week_hour, np.full(len(world.items), protection))[item])
    assert plain == int(np.ceil(1.25 * mu))
    assert told == int(np.ceil(1.25 * 2.0 * mu)) > plain
    on_hand = np.zeros_like(obs.on_hand)
    on_hand[0, item, 0] = told + 5
    full = dataclasses.replace(empty, on_hand=on_hand, hours_to_expiry=np.full_like(on_hand, 999))
    assert int(oracle._decide_one(full, 0, scenario)[item]) == 0


def test_the_gate_oracle_plans_to_the_next_orders_actual_arrival() -> None:
    """Told of an outage over the next delivery, the shocked supplier's items cover the longer
    interval; told of an outage elsewhere, the incumbent decides unchanged."""
    world = small_world(items=9)
    tables = _tables(world, aware=False)
    obs, plain_scenario = _first_decision(world, 3)
    item = int(np.flatnonzero(obs.deciding)[0])
    supplier = [s.name for s in world.suppliers].index(world.items[item].supplier)
    oracle_hour = ShockOracle(world, tables, [plain_scenario]).decision_hours[0]
    empty = dataclasses.replace(
        obs, on_hand=np.zeros_like(obs.on_hand), open_qty=np.zeros_like(obs.open_qty)
    )
    plain = int(Incumbent(world, tables).decide(empty)[0, item])
    for onset, longer in ((float(oracle_hour), True), (float(oracle_hour) + 500.0, False)):
        outage = Shock("outage", onset_hour=onset, duration_hours=48.0, supplier=supplier)
        scenario = dataclasses.replace(plain_scenario, shock=outage)
        oracle = ShockOracle(world, tables, [scenario])
        oracle.hour = oracle_hour
        told = int(oracle._decide_one(empty, 0, scenario)[item])
        assert (told > plain) if longer else (told == plain)


def test_the_rules_are_checked() -> None:
    world = small_world(items=9)
    tables = _tables(world, aware=False)
    batch = scenarios(world, "S1", (5,))
    with pytest.raises(ValueError, match="rule"):
        ShockOracle(world, tables, batch, rule="clairvoyant")
    with pytest.raises(ValueError, match="no response factor"):
        ShockOracle(world, tables, batch, response=np.ones(len(world.items)))
