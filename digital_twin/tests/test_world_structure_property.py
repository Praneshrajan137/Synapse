# Feature: decision-quality-proof, Property 90: The lead-time path is a pure function of seed,
# supplier and time: identical across arms, non-crossing, and absent when structure 3 is off
# Feature: decision-quality-proof, Property 91: Every declared intensity profile has mean exactly
# one, so structure 1 changes demand's shape and never its whole-week volume; only a declared
# promotion adds volume
"""The world structures' spec, their reader, the lead-time path, and the engine seam they reach.

Task 13.1 (ADR-055 D2.8; findings 66 and 67). Subjects: ``digital_twin/simulation/world.py``,
``digital_twin/simulation/lead_time.py`` and ``SupplyChainSimulation.place_order``.

**Property 90.** Arrivals are one function of seed, supplier and time: asked in any order, by any
engine at the seed, before or after any orders, they agree exactly. They never cross -- a later
order never arrives earlier, including across a piece boundary -- and never precede the floor.
With structure 3 off there is no path at all: ``place_order`` is ``add_stock``, nothing is
scheduled, nothing is drawn, and a run is step-for-step HEAD's.

**Property 91, and the domain its title holds over.** Both profiles have mean EXACTLY one over
their stated decimals, so over any whole week they add no volume -- asserted over ``Fraction``
with an oracle that does not use ``DemandShape``'s arithmetic. The title names its own two
limits. Promotions add volume -- a multiplier is > 1 by rule -- and the last clause measures the
committed promotion's excess exactly, after asserting one is declared, so that clause cannot pass
on an empty set. And the claim is about a WHOLE week: a few hours from midnight carry far less
than the flat volume.

Refusals are proven by construction: each case starts from the committed document and breaks ONE
rule, and a control proves the round trip itself refuses nothing.

Locus: the clauses that advance the SimPy twin are ``@pytest.mark.slow`` (``uplift-verify-slow``
collects ``digital_twin/tests``); the rest are arithmetic or construction only and run in
``quality-gates``. Budget inherited from ``HYPOTHESIS_PROFILE``; no ``max_examples`` literal.
"""

from __future__ import annotations

import dataclasses
import functools
import logging
import math
from fractions import Fraction
from typing import TYPE_CHECKING, Any

import pytest
import structlog
import yaml
from hypothesis import example, given, settings
from hypothesis import strategies as st

from digital_twin.simulation.engine import SUBSTREAM_NAMES, SupplyChainSimulation
from digital_twin.simulation.lead_time import LeadTimePath
from digital_twin.simulation.policy import POLICY_PATH, PolicyUnavailableError, load_policy
from digital_twin.simulation.world import (
    DAYS_PER_WEEK,
    HOURS_PER_DAY,
    HOURS_PER_WEEK,
    MINUTES_PER_DAY,
    MINUTES_PER_HOUR,
    CellSpec,
    ResolvedWorld,
    SupplyStructure,
    WorldSpec,
    load_world,
)

if TYPE_CHECKING:
    from pathlib import Path

    import numpy as np

structlog.configure(wrapper_class=structlog.make_filtering_bound_logger(logging.ERROR))


@functools.cache
def _committed() -> WorldSpec:
    return load_world()


def _cell(name: str) -> ResolvedWorld:
    return _committed().resolve(name)


def _supply() -> SupplyStructure:
    supply = _cell("primary").supply
    assert supply is not None, "the primary cell must run structure 3"
    return supply


def _path(seeds: dict[str, int], start: int, *, shaped: bool) -> LeadTimePath:
    """The primary cell's path; ``shaped=False`` is the same supply with structure 1 off."""
    primary = _cell("primary")
    return LeadTimePath(
        supply=_supply(),
        demand=primary.demand if shaped else None,
        start_weekday=start,
        seeds=seeds,
    )


def _state(generator: np.random.Generator) -> object:
    return generator.bit_generator.state


def _queued(sim: SupplyChainSimulation) -> int:
    """Events on the twin's SimPy queue: how "schedules nothing" is observed rather than assumed."""
    env = sim._env  # noqa: SLF001 -- the engine exposes no public view of its event queue
    assert env is not None, "start() creates the clock"
    return len(env._queue)  # noqa: SLF001


def _started(seed: int) -> SupplyChainSimulation:
    """A primary-cell twin with no endogenous demand or restock: only orders move its stock."""
    sim = SupplyChainSimulation(seed=seed, world=_cell("primary"))
    sim.start(external_demand=True)
    sim.set_policy(restock_threshold=0.0)
    return sim


_SEEDS = st.integers(min_value=0, max_value=2**31 - 1)
_SUPPLIERS = sorted(_supply().suppliers)
_SUPPLIER = st.sampled_from(_SUPPLIERS)
_SUPPLIER_SEEDS = st.fixed_dictionaries(
    {supplier: st.integers(min_value=0, max_value=2**62 - 1) for supplier in _SUPPLIERS}
)
_WEEKDAYS = st.integers(min_value=0, max_value=DAYS_PER_WEEK - 1)
_TIMES = st.floats(min_value=0.0, max_value=14.0 * MINUTES_PER_DAY, allow_nan=False)
_MULTS = st.floats(min_value=0.1, max_value=3.0, allow_nan=False)
#: Placement instants straddling piece and day boundaries, for the cross-engine comparison.
_GRID_MIN = (0.0, 17.5, 59.999, 60.0, 61.25, 600.0, 1439.5, 1440.0, 2000.0, 5000.0)


# ---------------------------------------------------------------------------
# Property 90 -- the path, pure
# ---------------------------------------------------------------------------


@given(
    seeds=_SUPPLIER_SEEDS,
    start=_WEEKDAYS,
    mult=_MULTS,
    queries=st.lists(st.tuples(_SUPPLIER, _TIMES), min_size=1, max_size=12),
)
def test_the_path_is_the_same_whatever_order_it_is_asked_in(
    seeds: dict[str, int], start: int, mult: float, queries: list[tuple[str, float]]
) -> None:
    """Lazy generation runs in day and hour order whatever is asked, so asking cannot move it."""
    forward = _path(seeds, start, shaped=True)
    backward = _path(seeds, start, shaped=True)

    asked_forward = [forward.arrival_time(supplier, t, mult) for supplier, t in queries]
    asked_backward = [backward.arrival_time(supplier, t, mult) for supplier, t in queries[::-1]]

    assert asked_forward == asked_backward[::-1]


@given(seeds=_SUPPLIER_SEEDS, start=_WEEKDAYS)
def test_each_supplier_path_moves_with_its_own_seed_and_no_other(
    seeds: dict[str, int], start: int
) -> None:
    """One independent generator per supplier -- and the seed really is an input (non-vacuity)."""
    base = _path(seeds, start, shaped=True)
    for moved in _SUPPLIERS:
        other = _path({**seeds, moved: (seeds[moved] + 1) % 2**62}, start, shaped=True)
        for supplier in _SUPPLIERS:
            same = other.arrival_time(supplier, 0.0, 1.0) == base.arrival_time(supplier, 0.0, 1.0)
            assert same == (supplier != moved), f"moving {moved}'s seed moved {supplier}: {same}"


@given(
    seeds=_SUPPLIER_SEEDS,
    start=_WEEKDAYS,
    supplier=_SUPPLIER,
    first=_TIMES,
    second=_TIMES,
    mult=_MULTS,
)
def test_an_order_placed_later_never_arrives_earlier_nor_any_order_before_the_floor(
    seeds: dict[str, int], start: int, supplier: str, first: float, second: float, mult: float
) -> None:
    """Non-crossing at a fixed multiplier, exact in floats: a running maximum only rises."""
    path = _path(seeds, start, shaped=True)
    early, late = sorted((first, second))

    arrives_early = path.arrival_time(supplier, early, mult)
    arrives_late = path.arrival_time(supplier, late, mult)

    assert arrives_early <= arrives_late
    assert arrives_early >= early + mult * _supply().min_lead_time_min
    assert arrives_early > early


@given(seeds=_SUPPLIER_SEEDS, start=_WEEKDAYS, mult=_MULTS)
def test_no_piece_boundary_lets_an_order_overtake_one_placed_just_before_it(
    seeds: dict[str, int], start: int, mult: float
) -> None:
    """A boundary is where a piecewise lead time could cross; the past-piece maximum forbids it."""
    path = _path(seeds, start, shaped=True)
    for supplier in path.suppliers:
        for hour in range(1, 3 * HOURS_PER_DAY):
            boundary = float(hour * MINUTES_PER_HOUR)
            just_before = math.nextafter(boundary, 0.0)
            assert path.arrival_time(supplier, just_before, mult) <= path.arrival_time(
                supplier, boundary, mult
            ), f"{supplier}: an order at {boundary} overtook one at {just_before}"


@given(seeds=_SUPPLIER_SEEDS, day=st.integers(min_value=0, max_value=13))
def test_without_structure_1_a_lead_time_changes_only_at_midnight(
    seeds: dict[str, int], day: int
) -> None:
    """Demand reaches the lead time only through intensity, so with no shape a day is flat."""
    flat = _path(seeds, 0, shaped=False)
    shaped = _path(seeds, 0, shaped=True)
    hours = range(day * HOURS_PER_DAY, (day + 1) * HOURS_PER_DAY)

    for supplier in flat.suppliers:
        assert len({flat.piece_lead_time(supplier, hour) for hour in hours}) == 1, supplier
    # Non-vacuity: with structure 1 on, the same day's busy hours stretch the lead time.
    assert any(
        len({shaped.piece_lead_time(supplier, hour) for hour in hours}) > 1
        for supplier in shaped.suppliers
    )


# ---------------------------------------------------------------------------
# Property 90 -- the engine seam, by construction (no clock advanced)
# ---------------------------------------------------------------------------


@given(seed=_SEEDS)
def test_only_structure_3_draws_and_it_draws_only_from_the_restock_stream(seed: int) -> None:
    """PRESERVE: no world, or both structures off, leaves every substream where HEAD leaves it."""
    head = SupplyChainSimulation(seed=seed).streams
    off = SupplyChainSimulation(seed=seed, world=_cell("off_off")).streams
    shaped_only = SupplyChainSimulation(seed=seed, world=_cell("s1_only")).streams
    drawn = SupplyChainSimulation(seed=seed, world=_cell("s3_only")).streams

    assert all(_state(off[name]) == _state(head[name]) for name in SUBSTREAM_NAMES)
    assert _state(shaped_only["restock"]) == _state(head["restock"])
    # The seeds really are drawn with structure 3 on, so the equalities above could fail.
    assert _state(drawn["restock"]) != _state(head["restock"])
    assert all(
        _state(drawn[name]) == _state(head[name]) for name in SUBSTREAM_NAMES if name != "restock"
    )


@given(seed=_SEEDS, times=st.lists(_TIMES, min_size=1, max_size=8))
def test_two_engines_at_one_seed_read_one_arrival_function(seed: int, times: list[float]) -> None:
    """What an arm reads through ``arrival_time_for`` depends on the seed and nothing else."""
    first = SupplyChainSimulation(seed=seed, world=_cell("primary"))
    second = SupplyChainSimulation(seed=seed, world=_cell("primary"))
    assert first.sku_supplier, "the primary cell maps SKUs to suppliers"

    for sku in sorted(first.sku_supplier):
        forward = [first.arrival_time_for(sku, t) for t in times]
        backward = [second.arrival_time_for(sku, t) for t in times[::-1]]
        assert forward == backward[::-1], sku


@given(
    seed=_SEEDS,
    units=st.floats(min_value=-10.0, max_value=1e4, allow_nan=False, allow_infinity=False),
)
def test_with_structure_3_off_an_order_is_add_stock_and_schedules_nothing(
    seed: int, units: float
) -> None:
    """No world, both structures off, or structure 1 alone: no lead time exists to wait for."""
    for world in (None, _cell("off_off"), _cell("s1_only")):
        sim = SupplyChainSimulation(seed=seed, world=world).start(external_demand=True)
        queued = _queued(sim)
        level = sim.inventory["sku_0"]

        assert sim.place_order("sku_0", units) == 0.0
        assert sim.inventory["sku_0"] == level + max(0.0, units)
        assert _queued(sim) == queued, "an order with no lead time must schedule nothing"
        assert sim.on_order == {}
        assert sim.sku_supplier == {}
        assert sim.supplier_lead_time_history == {}
        assert sim.arrival_time_for("sku_0", 125.0) == 125.0


def test_structure_3_refuses_what_no_supplier_could_restock() -> None:
    """Refused by name at ``start`` and at ``place_order``; with structure 3 off, not refused."""
    catalogue = {"sku_0": 5.0, "ghost_sku": 5.0}
    with pytest.raises(ValueError, match="ghost_sku"):
        SupplyChainSimulation(seed=0, world=_cell("primary")).start(initial_inventory=catalogue)
    # The refusal is structure 3's, not the catalogue's.
    SupplyChainSimulation(seed=0, world=_cell("s1_only")).start(initial_inventory=catalogue)

    started = SupplyChainSimulation(seed=0, world=_cell("primary")).start(external_demand=True)
    with pytest.raises(ValueError, match="ghost_sku"):
        started.place_order("ghost_sku", 5.0)
    with pytest.raises(RuntimeError, match="start"):
        SupplyChainSimulation(seed=0, world=_cell("primary")).place_order("sku_0", 5.0)


# ---------------------------------------------------------------------------
# Property 90 -- the engine seam, running (slow: these advance the SimPy twin)
# ---------------------------------------------------------------------------


@pytest.mark.slow
@settings(deadline=None)
@given(seed=_SEEDS)
def test_two_arms_at_one_seed_face_one_arrival_function_whatever_they_order(seed: int) -> None:
    """Orders placed, landed and in transit on one arm move nothing the other arm reads."""
    ordering = _started(seed)
    idle = _started(seed)
    grid = [(sku, t) for sku in sorted(ordering.sku_supplier) for t in _GRID_MIN]
    before = [idle.arrival_time_for(sku, t) for sku, t in grid]

    first_round = [ordering.place_order(sku, 25.0) for sku in sorted(ordering.inventory)]
    hours = max(first_round) / MINUTES_PER_HOUR + 1.0
    ordering.advance(hours)
    idle.advance(hours)
    second_round = [ordering.place_order(sku, 10.0) for sku in sorted(ordering.inventory)]

    assert len(ordering.arrived_orders) == len(first_round), "every first-round order landed"
    assert set(ordering.on_order) == set(ordering.inventory), "the second round is in transit"
    assert min(second_round) > ordering.sim_time_min
    assert [ordering.arrival_time_for(sku, t) for sku, t in grid] == before
    assert [idle.arrival_time_for(sku, t) for sku, t in grid] == before


@pytest.mark.slow
@settings(deadline=None)
@given(seed=_SEEDS)
def test_the_realised_history_holds_only_orders_that_have_landed(seed: int) -> None:
    """Midway between the first two distinct arrivals, some orders are here and some are not."""
    sim = _started(seed)
    opening = sim.inventory
    quantities = {sku: float(10 + index) for index, sku in enumerate(sorted(opening))}
    promised = {sku: sim.place_order(sku, units) for sku, units in quantities.items()}
    instants = sorted(set(promised.values()))
    assert len(instants) >= 2, "three suppliers at one instant cannot share an arrival time"

    sim.advance((instants[0] + instants[1]) / 2.0 / MINUTES_PER_HOUR)
    clock = sim.sim_time_min
    landed = {order.sku: order for order in sim.arrived_orders}
    in_transit = sim.on_order

    assert landed and in_transit, "the horizon splits the orders, so neither side is empty"
    assert set(landed).isdisjoint(in_transit)
    assert set(landed) | set(in_transit) == set(quantities)
    for sku, order in landed.items():
        assert order.placed_at == 0.0
        assert order.arrived_at == promised[sku] <= clock
        assert sim.inventory[sku] == opening[sku] + quantities[sku]
    for sku, units in in_transit.items():
        assert promised[sku] > clock
        assert units == quantities[sku]
        assert sim.inventory[sku] == opening[sku]

    history = sim.supplier_lead_time_history
    assert set(history) == set(_SUPPLIERS)
    for supplier, times in history.items():
        expected = tuple(o.lead_time_min for o in sim.arrived_orders if o.supplier == supplier)
        assert times == expected, supplier
    assert sum(len(times) for times in history.values()) == len(landed)


@pytest.mark.slow
@settings(deadline=None)
@given(seed=_SEEDS)
def test_with_both_structures_off_a_run_is_heads_run_step_for_step(seed: int) -> None:
    """The PRESERVE list's guarantee, measured: same stock, KPIs, demand path and RNG states."""
    head = SupplyChainSimulation(seed=seed)
    candidates = (
        SupplyChainSimulation(seed=seed, world=None),
        SupplyChainSimulation(seed=seed, world=_cell("off_off")),
    )
    for sim in (head, *candidates):
        sim.start()
    for _ in range(3):
        head.add_stock("sku_0", 7.0)
        for sim in candidates:
            queued = _queued(sim)
            assert sim.place_order("sku_0", 7.0) == sim.sim_time_min
            assert _queued(sim) == queued
        for sim in (head, *candidates):
            sim.advance(1.0)

    assert head.metrics.demand_events > 0, "the run fulfilled demand, so the match is not vacuous"
    assert sum(head.demand_to_date.values()) == len(head.demand_trace)
    for sim in candidates:
        assert sim.inventory == head.inventory
        assert sim.metrics.to_dict() == head.metrics.to_dict()
        assert sim.demand_trace.as_tuples() == head.demand_trace.as_tuples()
        assert sim.demand_to_date == head.demand_to_date
        assert all(_state(sim.streams[n]) == _state(head.streams[n]) for n in SUBSTREAM_NAMES)


# ---------------------------------------------------------------------------
# Property 91 -- the profiles, and the reader that guards them
# ---------------------------------------------------------------------------


def _exactly_one(values: tuple[float, ...]) -> bool:
    """The rule over the decimals the file states, written independently of ``world.py``."""
    return sum(Fraction(str(value)) for value in values) == len(values)


def test_the_committed_profiles_have_mean_exactly_one_over_their_stated_decimals() -> None:
    raw = load_policy(POLICY_PATH)["world"]["structure_1"]
    shape = _committed().structure_1

    assert shape.hourly == tuple(float(value) for value in raw["hourly"]), "read, not transformed"
    assert shape.weekday == tuple(float(value) for value in raw["weekday"])
    assert len(shape.hourly) == HOURS_PER_DAY and len(shape.weekday) == DAYS_PER_WEEK
    assert _exactly_one(shape.hourly) and _exactly_one(shape.weekday)
    assert min(shape.hourly) > 0.0 and min(shape.weekday) > 0.0

    scaled = [name for name, cell in _committed().cells.items() if cell.amplitude_scale is not None]
    assert scaled, "the grid commits amplitude cells, so the loop below checks a rescale"
    for name in scaled:
        demand = _cell(name).demand
        assert demand is not None
        assert _exactly_one(demand.hourly) and _exactly_one(demand.weekday), name


@given(millionths=st.integers(min_value=1, max_value=1_000_000))
@example(millionths=1_000_000)
def test_an_amplitude_scale_keeps_every_profile_mean_exactly_one_and_every_value_positive(
    millionths: int,
) -> None:
    """For every k a YAML file can state to six places in (0, 1]: exact mean, exact formula."""
    scale = millionths / 1_000_000
    exact_k = Fraction(millionths, 1_000_000)
    committed = _committed()
    probe = CellSpec(
        structure_1=True, structure_3=True, amplitude_scale=scale, lead_time_scale=None
    )
    spec = dataclasses.replace(committed, cells={**committed.cells, "probe": probe})

    demand = spec.resolve("probe").demand

    assert demand is not None
    pairs = (
        (demand.hourly, committed.structure_1.hourly),
        (demand.weekday, committed.structure_1.weekday),
    )
    for scaled, original in pairs:
        assert _exactly_one(scaled)
        assert min(scaled) > 0.0
        for got, p in zip(scaled, original, strict=True):
            assert Fraction(str(got)) == 1 + exact_k * (Fraction(str(p)) - 1)


@given(
    first_hour=st.integers(min_value=0, max_value=HOURS_PER_WEEK - 1),
    offset=st.floats(min_value=0.0, max_value=59.0, allow_nan=False),
    start=_WEEKDAYS,
    rate=st.floats(min_value=0.01, max_value=10.0, allow_nan=False),
)
def test_a_whole_week_of_profiles_is_the_flat_week_and_only_promotions_add_to_it(
    first_hour: int, offset: float, start: int, rate: float
) -> None:
    """Exact over the stated decimals; the float integral is then checked against that oracle."""
    shape = _committed().structure_1
    hourly = [Fraction(str(value)) for value in shape.hourly]
    weekday = [Fraction(str(value)) for value in shape.weekday]
    promoted: dict[int, Fraction] = {}
    for promotion in shape.promotions:
        opens = promotion.weekday * HOURS_PER_DAY + promotion.start_hour
        for step in range(promotion.hours):
            hour_of_week = (opens + step) % HOURS_PER_WEEK
            factor = promoted.get(hour_of_week, Fraction(1))
            promoted[hour_of_week] = factor * Fraction(str(promotion.multiplier))

    def exact_week(*, with_promotions: bool) -> Fraction:
        total = Fraction(0)
        for hour in range(first_hour, first_hour + HOURS_PER_WEEK):
            day = (start + hour // HOURS_PER_DAY) % DAYS_PER_WEEK
            hour_of_week = day * HOURS_PER_DAY + hour % HOURS_PER_DAY
            lift = promoted.get(hour_of_week, Fraction(1)) if with_promotions else Fraction(1)
            total += hourly[hour % HOURS_PER_DAY] * weekday[day] * lift * MINUTES_PER_HOUR
        return total

    week_min = HOURS_PER_WEEK * MINUTES_PER_HOUR
    assert exact_week(with_promotions=False) == week_min, "the profiles moved volume"
    excess = exact_week(with_promotions=True) - week_min
    assert shape.promotions, "the committed world declares a promotion, so this is not vacuous"
    assert (excess > 0) == bool(shape.promotions), "promotions, and only they, add volume"

    t0 = first_hour * MINUTES_PER_HOUR + offset
    t1 = t0 + week_min
    flat = dataclasses.replace(shape, promotions=())
    assert math.isclose(flat.expected_units(t0, t1, start, rate), rate * week_min, rel_tol=1e-12)
    shaped = shape.expected_units(t0, t1, start, rate)
    assert math.isclose(shaped, rate * float(week_min + excess), rel_tol=1e-12)


_DELETE = object()
_WORLD = load_policy(POLICY_PATH)["world"]
_HOURLY: list[float] = list(_WORLD["structure_1"]["hourly"])
_WEEKDAY: list[float] = list(_WORLD["structure_1"]["weekday"])
#: hourly[0] zeroed and its value moved to hourly[1] exactly, so ONLY positivity breaks.
_MERGED = float(Fraction(str(_HOURLY[0])) + Fraction(str(_HOURLY[1])))
#: Read from the committed roster rather than transcribed, so a research data edit that renames
#: suppliers or moves the floor leaves every case below breaking exactly one rule.
_ROSTER: dict[str, Any] = _WORLD["structure_3"]["suppliers"]
_A_SUPPLIER = sorted(_ROSTER)[0]
_A_SKU = sorted(_WORLD["structure_3"]["sku_supplier"])[0]
_FLOOR = _WORLD["structure_3"]["min_lead_time_min"]
_BELOW_FLOOR = _FLOOR / max(spec["mean_lead_time_min"] for spec in _ROSTER.values()) / 2.0
_S1: tuple[str, ...] = ("structure_1",)
_S3: tuple[str, ...] = ("structure_3",)
_PROMO: tuple[str | int, ...] = ("structure_1", "promotions", 0)

_REFUSALS = [
    pytest.param((*_S1, "hourly"), _HOURLY[:-1], ("structure_1", "exactly 24"), id="hourly-len"),
    pytest.param((*_S1, "weekday"), [*_WEEKDAY, 1.0], ("structure_1", "exactly 7"), id="week-len"),
    pytest.param(
        (*_S1, "hourly"), [0.0, _MERGED, *_HOURLY[2:]], ("hourly[0]", "positive"), id="zero"
    ),
    pytest.param(
        (*_S1, "hourly"), [math.inf, *_HOURLY[1:]], ("hourly[0]", "finite"), id="infinite"
    ),
    pytest.param(
        (*_S1, "hourly"),
        [math.nextafter(_HOURLY[0], math.inf), *_HOURLY[1:]],
        ("hourly", "not exactly one"),
        id="hourly-mean-one-ulp",
    ),
    pytest.param(
        (*_S1, "weekday"),
        [math.nextafter(_WEEKDAY[0], 0.0), *_WEEKDAY[1:]],
        ("weekday", "not exactly one"),
        id="weekday-mean-one-ulp",
    ),
    pytest.param((*_PROMO, "weekday"), 7, ("promotions[0]", "weekday"), id="promo-weekday"),
    pytest.param((*_PROMO, "start_hour"), 24, ("promotions[0]", "start_hour"), id="promo-hour"),
    pytest.param((*_PROMO, "hours"), 0, ("promotions[0]", "hours"), id="promo-no-hours"),
    pytest.param((*_PROMO, "hours"), 1.5, ("promotions[0].hours", "integer"), id="promo-frac"),
    pytest.param((*_PROMO, "multiplier"), 1.0, ("promotions[0]", "multiplier"), id="promo-mult"),
    pytest.param((*_S1, "start_weekday_rule"), "seed_mod_5", ("start_weekday_rule",), id="rule"),
    pytest.param(
        (*_S3, "suppliers", _A_SUPPLIER, "mean_lead_time_min"),
        _FLOOR,
        ("mean_lead_time_min", "min_lead_time_min"),
        id="mean-at-floor",
    ),
    pytest.param((*_S3, "suppliers", _A_SUPPLIER, "log_sd"), -0.1, ("log_sd",), id="log-sd"),
    pytest.param((*_S3, "daily_autocorrelation"), 1.0, ("daily_autocorrelation",), id="phi"),
    pytest.param((*_S3, "demand_coupling"), -0.5, ("demand_coupling",), id="kappa"),
    pytest.param((*_S3, "coupling_floor"), 0.0, ("coupling_floor",), id="floor-zero"),
    pytest.param((*_S3, "coupling_floor"), 1.5, ("coupling_floor",), id="floor-high"),
    pytest.param((*_S3, "min_lead_time_min"), 0, ("min_lead_time_min",), id="min-lead"),
    pytest.param(
        (*_S3, "sku_supplier", _A_SKU), "no_such_supplier", ("no_such_supplier",), id="stranger"
    ),
    pytest.param(
        ("cells", "s3_only", "amplitude_scale"),
        0.5,
        ("cells.s3_only", "amplitude_scale"),
        id="amplitude-without-s1",
    ),
    pytest.param(
        ("cells", "s1_only", "lead_time_scale"),
        0.5,
        ("cells.s1_only", "lead_time_scale"),
        id="lead-scale-without-s3",
    ),
    pytest.param(
        ("cells", "amplitude_half", "amplitude_scale"),
        1.5,
        ("amplitude_half", "(0, 1]"),
        id="amplitude-above-one",
    ),
    pytest.param(
        ("cells", "amplitude_half", "amplitude_scale"),
        0.0,
        ("amplitude_half", "(0, 1]"),
        id="amplitude-zero",
    ),
    pytest.param(
        ("cells", "lead_time_low", "lead_time_scale"),
        _BELOW_FLOOR,
        ("lead_time_low", "lead_time_scale"),
        id="lead-scale-below-floor",
    ),
    pytest.param(
        ("cells", "primary", "structure_1"),
        "yes",
        ("cells.primary.structure_1", "boolean"),
        id="flag-not-bool",
    ),
    pytest.param(
        ("cells", "primary", "amplitude_scal"), 0.5, ("amplitude_scal", "unknown"), id="typo"
    ),
    pytest.param(("primary_cell",), "s1_only", ("primary_cell", "both"), id="primary-half-on"),
    pytest.param(("primary_cell",), "nowhere", ("primary_cell", "nowhere"), id="primary-absent"),
    pytest.param(
        (*_S3, "coupling_floor"),
        _DELETE,
        ("world.structure_3.coupling_floor", "NOT"),
        id="missing-key",
    ),
    pytest.param(
        (*_S1, "provenance"), _DELETE, ("world.structure_1.provenance",), id="no-provenance"
    ),
]


def _rewritten(tmp_path: Path, keys: tuple[str | int, ...], value: object) -> Path:
    """The committed policy, with at most one value in ``world:`` replaced or deleted."""
    document = load_policy(POLICY_PATH)
    if keys:
        node: Any = document["world"]
        for key in keys[:-1]:
            node = node[key]
        if value is _DELETE:
            del node[keys[-1]]
        else:
            node[keys[-1]] = value
    target = tmp_path / "policy.yaml"
    target.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")
    return target


def test_the_round_trip_the_refusals_use_refuses_nothing_by_itself(tmp_path: Path) -> None:
    """The control: without a mutation the rewritten file loads to the committed world."""
    assert load_world(_rewritten(tmp_path, (), None)) == _committed()


@pytest.mark.parametrize(("keys", "value", "fragments"), _REFUSALS)
def test_the_reader_refuses_each_broken_rule_by_name(
    tmp_path: Path, keys: tuple[str | int, ...], value: object, fragments: tuple[str, ...]
) -> None:
    """One rule broken per case, everything else committed: the refusal is that rule's."""
    with pytest.raises(PolicyUnavailableError) as refused:
        load_world(_rewritten(tmp_path, keys, value))

    message = str(refused.value)
    for fragment in fragments:
        assert fragment in message, f"{fragment!r} not named in: {message}"
