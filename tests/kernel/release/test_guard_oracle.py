"""The guard of D-4(b) in whole units; the headroom oracle equals the incumbent without a shock."""

from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING

import numpy as np
from hypothesis import given
from hypothesis import strategies as st

from synapse_kernel.release.engine import run
from synapse_kernel.release.guard import guard
from synapse_kernel.release.harness import mean_demand_table, scenarios
from synapse_kernel.release.incumbent import Incumbent, IncumbentTables
from synapse_kernel.release.oracle import Guarded, ShockOracle
from tests.kernel.release.fixtures import small_world

if TYPE_CHECKING:
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
