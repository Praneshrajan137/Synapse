"""The release world's rules, the five cells as sealed, and when an order lands under each shock."""

from __future__ import annotations

import dataclasses
import json
import math

import numpy as np
import pytest

from synapse_kernel.release import cells, scenario
from synapse_kernel.release.world import (
    REQUIRED_PROVENANCE,
    Provenance,
    world_from_document,
    world_to_document,
)
from tests.kernel.release.fixtures import DAY_SHAPE, small_world

SEEDS = range(40)


def test_a_world_round_trips_exactly_through_its_json() -> None:
    world = small_world()
    text = json.dumps(world_to_document(world), sort_keys=True, separators=(",", ":"))
    assert world_from_document(json.loads(text)) == world


def test_a_profile_that_moves_volume_is_refused() -> None:
    skewed = (DAY_SHAPE[:-1] + (DAY_SHAPE[-1] + 0.1,)) * 7
    with pytest.raises(ValueError, match="mean exactly one"):
        small_world(profiles={"day": skewed})


def test_every_parameter_group_needs_its_provenance() -> None:
    partial = {k: Provenance("chosen", "x") for k in REQUIRED_PROVENANCE if k != "pair_share"}
    with pytest.raises(ValueError, match="no provenance"):
        small_world(provenance=partial)
    with pytest.raises(ValueError, match="provenance kind"):
        Provenance("guessed", "x")


def test_an_item_with_an_undeclared_supplier_is_refused() -> None:
    world = small_world()
    stray = dataclasses.replace(world.items[0], supplier="nobody")
    with pytest.raises(ValueError, match="not declared"):
        dataclasses.replace(world, items=(stray, *world.items[1:]))


def test_warm_up_is_the_longest_shelf_life_plus_the_longest_lead_time_in_whole_days() -> None:
    world = small_world()
    assert world.warmup_days == math.ceil((5 * 24 + 8) / 24)
    assert world.horizon_hours == (world.warmup_days + 7) * 24


def test_cell_l_halves_shelf_lives_rounding_down_with_a_twelve_hour_floor() -> None:
    world = small_world()
    normal = cells.shelf_lives(world, "N")
    short = cells.shelf_lives(world, "L")
    assert np.array_equal(short, np.maximum(12, normal // 2))
    assert int(short.min()) >= 12


def test_s1_surges_thirty_percent_of_items_for_one_to_three_days_inside_the_week() -> None:
    world = small_world(items=40)
    start, end = world.measured_start_hour, world.horizon_hours
    for seed in SEEDS:
        shock = cells.draw_shock(world, "S1", seed)
        assert shock.kind == "surge"
        assert len(shock.items) == math.ceil(0.3 * 40) == len(set(shock.items))
        assert 1.5 <= shock.size < 3.0
        assert 24.0 <= shock.duration_hours < 72.0
        assert start <= shock.onset_hour and shock.end_hour <= end


def test_s2_and_s3_strike_one_supplier_for_their_sealed_durations() -> None:
    world = small_world()
    for seed in SEEDS:
        delay = cells.draw_shock(world, "S2", seed)
        outage = cells.draw_shock(world, "S3", seed)
        assert delay.kind == "delay" and 2.0 <= delay.size < 4.0
        assert 48.0 <= delay.duration_hours < 96.0
        assert outage.kind == "outage" and 24.0 <= outage.duration_hours < 72.0
        for shock in (delay, outage):
            assert 0 <= shock.supplier < len(world.suppliers)
            assert world.measured_start_hour <= shock.onset_hour
            assert shock.end_hour <= world.horizon_hours
    assert cells.draw_shock(world, "N", 3).kind == cells.draw_shock(world, "L", 3).kind == "none"


def test_a_shock_is_a_function_of_the_seed_alone() -> None:
    world = small_world()
    for cell in ("S1", "S2", "S3"):
        assert cells.draw_shock(world, cell, 11) == cells.draw_shock(world, cell, 11)
        assert cells.draw_shock(world, cell, 11) != cells.draw_shock(world, cell, 12)


def test_every_cell_shares_cell_ns_base_demand_and_s1_only_adds_inside_its_window() -> None:
    world = small_world(items=20)
    for seed in (0, 5, 9):
        base = scenario.build_scenario(world, "N", seed).demand
        for cell in ("L", "S2", "S3"):
            assert np.array_equal(scenario.build_scenario(world, cell, seed).demand, base)
        surged = scenario.build_scenario(world, "S1", seed)
        extra = surged.demand - base
        assert int(extra.min()) >= 0 and int(extra.sum()) > 0
        hours = np.arange(world.horizon_hours)
        outside = ~((hours >= surged.shock.onset_hour) & (hours < surged.shock.end_hour))
        others = np.setdiff1d(np.arange(20), surged.shock.items)
        assert int(extra[outside].sum()) == 0
        assert int(extra[:, others].sum()) == 0


def test_demand_has_the_declared_mean() -> None:
    world = small_world(items=12)
    means = scenario.demand_means(world).sum(axis=0) / 7.0  # per item per day
    totals = sum(scenario.build_scenario(world, "N", seed).demand.sum(axis=0) for seed in range(60))
    days = 60 * world.horizon_hours / 24
    ratio = totals / (means * days)
    # Pairs and day factors widen the spread: every item within 12%, the store within 2%.
    assert float(np.max(np.abs(ratio - 1.0))) < 0.12
    assert abs(float(totals.sum() / (means.sum() * days)) - 1.0) < 0.02


def test_orders_land_at_the_next_delivery_or_as_each_shock_says() -> None:
    world = small_world()
    produce, hub = 0, 1
    none = cells.Shock("none")
    # produce delivers at 06:00 with an 8-hour lead time: its cut-off is 22:00.
    assert scenario.arrival_hour(world, none, produce, 22) == 30
    delay = cells.Shock("delay", onset_hour=150.0, duration_hours=60.0, size=3.0, supplier=produce)
    # placed at 166 (22:00) in the window: lead 8 x 3 = 24 h -> earliest 190 -> next 06:00 is 198.
    assert scenario.arrival_hour(world, delay, produce, 166) == 198
    assert scenario.arrival_hour(world, delay, hub, 146) == 150  # another supplier: nominal
    outage = cells.Shock("outage", onset_hour=171.5, duration_hours=40.25, supplier=produce)
    # delivery due at 174 falls inside [171.5, 211.75): it lands at the end, 212.
    assert scenario.arrival_hour(world, outage, produce, 166) == 212
    # placed at 190 (inside): lands at ceil(211.75 + 8) = 220, an unscheduled receipt.
    assert scenario.arrival_hour(world, outage, produce, 190) == 220
    assert scenario.arrival_hour(world, outage, produce, 214) == 222  # after: nominal
