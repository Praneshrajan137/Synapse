# Feature: decision-quality-proof, Property 57: Lead time is demand-correlated, day-autocorrelated
# and supplier-attributed
"""Structure 3's lead time follows its hour's declared demand, carries its day's AR(1) state, and
is charged to the supplier the committed map names.

Task 13.2 (R5.21-R5.23; ADR-055 D2.8). Subjects: ``digital_twin/simulation/lead_time.py`` and the
seam that lands an order, ``SupplyChainSimulation.place_order``. Every parameter is read from the
committed policy through ``load_world``; none is restated here.

**Not repeated from Property 90** (``test_world_structure_property.py``): the path's purity in
seed, supplier and time; non-crossing; the arrival floor in the primary cell; a day's lead time
varying only with structure 1 on; the history holding only landed orders from one instant. Task
13.2's clause (f) -- two engines at one seed, different order sequences, one arrival function --
is NOT written, because Property 90's
``test_two_arms_at_one_seed_face_one_arrival_function_whatever_they_order`` asserts exactly it.

**Exact where the design samples.** design.md states the demand correlation as a sample
correlation of the declared sign and magnitude. Clause (a) asserts the deterministic relation
that correlation would estimate, to the bit, so no tolerance enters it; only clause (b) is about
a random process, and its bands are derived where they are used. Both floors in the formula are
reached by construction rather than left to whether committed data or a seed reaches them. The
design's fourth conjunct -- an ``Observation`` carries each supplier's history -- is harness
wiring (``uplift/harness.py::observe``) and is not asserted here.

Locus: clauses (d) and (e) advance the SimPy twin and are ``@pytest.mark.slow``
(``uplift-verify-slow`` collects ``digital_twin/tests``); the rest are pure and run in
``quality-gates``. Budget inherited from ``HYPOTHESIS_PROFILE``; no ``max_examples`` literal.
"""

from __future__ import annotations

import dataclasses
import functools
import itertools
import math
from typing import TYPE_CHECKING

import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st

from digital_twin.simulation.engine import (
    _SUPPLIER_SEED_BOUND,
    SUBSTREAM_NAMES,
    SupplyChainSimulation,
)
from digital_twin.simulation.lead_time import LeadTimePath
from digital_twin.simulation.world import (
    DAYS_PER_WEEK,
    HOURS_PER_DAY,
    HOURS_PER_WEEK,
    MINUTES_PER_HOUR,
    load_world,
    start_weekday,
)

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from digital_twin.simulation.world import (
        DemandShape,
        ResolvedWorld,
        SupplyStructure,
        WorldSpec,
    )


@functools.cache
def _committed() -> WorldSpec:
    return load_world()


def _cell(name: str) -> ResolvedWorld:
    return _committed().resolve(name)


def _primary() -> ResolvedWorld:
    return _cell(_committed().primary_cell)


def _supply() -> SupplyStructure:
    supply = _primary().supply
    assert supply is not None, "the primary cell runs structure 3 (WorldSpec's own rule)"
    return supply


def _shape() -> DemandShape:
    demand = _primary().demand
    assert demand is not None, "the primary cell runs structure 1 (WorldSpec's own rule)"
    return demand


def _path(seeds: Mapping[str, int], start: int) -> LeadTimePath:
    """The primary cell's lead-time path, built as the engine builds it, from explicit seeds."""
    return LeadTimePath(supply=_supply(), demand=_shape(), start_weekday=start, seeds=seeds)


def _declared_intensity(shape: DemandShape, hour_index: int, start: int) -> float:
    """``I(h)``: the declared intensity throughout whole hour ``h`` of a run whose hour 0 opens
    weekday ``start`` (0 = Monday).

    Computed here from the profiles and the promotion windows rather than by ``DemandShape``, so
    the path's reading of the shape is checked, not echoed. Multiplied in the engine's order --
    hourly, weekday, then the product of open promotions -- so it is the same float, not merely
    the same real.
    """
    hour_of_day = hour_index % HOURS_PER_DAY
    weekday = (start + hour_index // HOURS_PER_DAY) % DAYS_PER_WEEK
    hour_of_week = weekday * HOURS_PER_DAY + hour_of_day
    lift = 1.0
    for promotion in shape.promotions:
        opens = promotion.weekday * HOURS_PER_DAY + promotion.start_hour
        if (hour_of_week - opens) % HOURS_PER_WEEK < promotion.hours:
            lift *= promotion.multiplier
    return shape.hourly[hour_of_day] * shape.weekday[weekday] * lift


@dataclasses.dataclass(frozen=True)
class _Piece:
    """One hour's lead time as checked, and which branch of the formula produced it."""

    intensity: float
    lead_time_min: float
    floored: bool


def _assert_declared_piece(
    path: LeadTimePath,
    supply: SupplyStructure,
    shape: DemandShape,
    start: int,
    supplier: str,
    hour: int,
) -> _Piece:
    """Assert ``L(j, h)`` is the declared formula exactly, on whichever branch holds.

    ``L / L0 == max(floor, 1 + kappa (I - 1))`` is an identity over the reals. In IEEE 754 its
    exact form is ``L == fl(L0 * c)`` -- one rounding of one product -- and that is asserted, to
    the bit. Dividing back adds a second rounding that can miss ``c`` by an ulp, so a quotient
    compared with ``==`` would fail on arithmetic rather than on the model. Where the product
    falls below ``min_lead_time_min`` the piece is that minimum instead, and is asserted so.
    """
    intensity = _declared_intensity(shape, hour, start)
    coupling = max(supply.coupling_floor, 1.0 + supply.demand_coupling * (intensity - 1.0))
    stretched = path.base_lead_time(supplier, hour // HOURS_PER_DAY) * coupling
    piece = path.piece_lead_time(supplier, hour)
    if stretched < supply.min_lead_time_min:
        assert piece == supply.min_lead_time_min, (supplier, hour, piece)
        return _Piece(intensity=intensity, lead_time_min=piece, floored=True)
    assert piece == stretched, (supplier, hour, piece, stretched)
    return _Piece(intensity=intensity, lead_time_min=piece, floored=False)


_SUPPLIERS = sorted(_supply().suppliers)
_SUPPLIER_SEEDS = st.fixed_dictionaries(
    {supplier: st.integers(min_value=0, max_value=2**62 - 1) for supplier in _SUPPLIERS}
)
_WEEKDAYS = st.integers(min_value=0, max_value=DAYS_PER_WEEK - 1)
#: Every committed cell that runs structure 3, read from the grid rather than listed.
_SUPPLY_CELLS = tuple(sorted(name for name in _committed().cells if _cell(name).structure_3_on))
#: Explicit seeds for the constructed worlds: supplier ``i`` (sorted id order) draws seed ``i``.
_FIXED_SEEDS = {supplier: index for index, supplier in enumerate(_SUPPLIERS)}


# ---------------------------------------------------------------------------
# Clause (a) -- every piece's value and direction (pure)
# ---------------------------------------------------------------------------


@given(seeds=_SUPPLIER_SEEDS, start=_WEEKDAYS)
def test_every_hours_lead_time_is_its_days_base_stretched_by_that_hours_declared_demand(
    seeds: dict[str, int], start: int
) -> None:
    """Every supplier, every hour of one simulated week, the primary cell.

    Then the direction, exactly. Inside a day ``L0`` is one positive number and each step from
    ``I`` to ``L`` -- subtract, scale by ``kappa >= 0``, add, ``max``, scale by ``L0`` -- is
    monotone under round-to-nearest, so no two hours of a day are discordant (the Spearman
    statement with no sampling in it) and equal intensities give equal lead times. Checked on
    intensity-sorted neighbours, which implies it for every pair.
    """
    supply = _supply()
    shape = _shape()
    path = _path(seeds, start)
    for supplier in path.suppliers:
        stretched_hours = 0
        rises = 0
        for day in range(DAYS_PER_WEEK):
            pieces = [
                _assert_declared_piece(path, supply, shape, start, supplier, hour)
                for hour in range(day * HOURS_PER_DAY, (day + 1) * HOURS_PER_DAY)
            ]
            stretched_hours += sum(not piece.floored for piece in pieces)
            ranked = sorted((piece.intensity, piece.lead_time_min) for piece in pieces)
            for (quiet, shorter), (busy, longer) in itertools.pairwise(ranked):
                assert shorter <= longer, (supplier, day, quiet, busy)
                assert quiet < busy or shorter == longer, (supplier, day, quiet)
                if shorter < longer:
                    rises += 1
        assert stretched_hours, f"{supplier}: the stretched branch was reached and checked"
        assert rises, f"{supplier}: some busier hour waited strictly longer"


def test_where_the_minimum_binds_a_lead_time_is_the_minimum_and_nowhere_else() -> None:
    """Clause (a)'s ``min_lead_time_min`` branch, reached by construction, not by a lucky seed.

    The fastest supplier's spread is set to zero, so its base IS its declared mean every day,
    and the minimum is raised to the float just below that mean -- the highest value
    ``SupplyStructure`` admits. Every hour quieter than average is then floored and every busier
    hour is not, whatever the seed.
    """
    committed = _supply()
    shape = _shape()
    start = 0
    fastest = min(_SUPPLIERS, key=lambda name: committed.suppliers[name].mean_lead_time_min)
    mean = committed.suppliers[fastest].mean_lead_time_min
    rigid = dataclasses.replace(
        committed,
        suppliers={
            **committed.suppliers,
            fastest: dataclasses.replace(committed.suppliers[fastest], log_sd=0.0),
        },
        min_lead_time_min=math.nextafter(mean, 0.0),
    )
    assert committed.demand_coupling > 0.0 and committed.coupling_floor < 1.0, (
        "premise: the committed world shortens a lead time in an hour quieter than average"
    )
    path = LeadTimePath(supply=rigid, demand=shape, start_weekday=start, seeds=_FIXED_SEEDS)
    assert all(path.base_lead_time(fastest, day) == mean for day in range(DAYS_PER_WEEK))

    pieces = [
        _assert_declared_piece(path, rigid, shape, start, fastest, hour)
        for hour in range(HOURS_PER_WEEK)
    ]
    assert {piece.floored for piece in pieces if piece.intensity < 1.0} == {True}
    assert {piece.floored for piece in pieces if piece.intensity > 1.0} == {False}


def test_where_the_coupling_floor_binds_a_quiet_hours_lead_time_shrinks_no_further() -> None:
    """Clause (a)'s ``max(coupling_floor, ...)`` branch, reached by construction.

    The coupling is replaced by the one that takes the week's quietest stretch
    ``1 + kappa (I - 1)`` to zero, so the floor binds in the quietest hours and not in the
    busier ones, whatever the seed; every hour is then checked on its branch.
    """
    committed = _supply()
    shape = _shape()
    start = 0
    intensities = [_declared_intensity(shape, hour, start) for hour in range(HOURS_PER_WEEK)]
    quietest = min(intensities)
    assert quietest < 1.0, "the declared week has an hour quieter than average"
    steep = dataclasses.replace(committed, demand_coupling=1.0 / (1.0 - quietest))
    binds = [
        1.0 + steep.demand_coupling * (intensity - 1.0) < steep.coupling_floor
        for intensity in intensities
    ]
    assert set(binds) == {True, False}, "the floor binds in some hours of the week, not all"

    path = LeadTimePath(supply=steep, demand=shape, start_weekday=start, seeds=_FIXED_SEEDS)
    held = 0
    for supplier in path.suppliers:
        for hour, floor_binds in enumerate(binds):
            piece = _assert_declared_piece(path, steep, shape, start, supplier, hour)
            if floor_binds and not piece.floored:
                held += 1
    assert held, "some hour held at the coupling floor, above the minimum, was checked"


# ---------------------------------------------------------------------------
# Clause (b) -- the day state (pure, statistical)
# ---------------------------------------------------------------------------

#: Days sampled per supplier. At least 2000 are required; 10 000 makes the lag-1 band +-0.04
#: for 10 000 scalar draws per supplier.
_DAYS = 10_000
#: Clause (b)'s explicit seeds: supplier ``i`` (sorted id order) draws from ``root + i``.
_ROOTS = (0, 1, 20_260_929)


def _lag_one_autocorrelation(values: Sequence[float]) -> float:
    """The textbook estimator: lag-1 autocovariance over variance, both about the sample mean."""
    centre = math.fsum(values) / len(values)
    centred = [value - centre for value in values]
    lagged = math.fsum(left * right for left, right in itertools.pairwise(centred))
    return lagged / math.fsum(value * value for value in centred)


@pytest.mark.parametrize("root", _ROOTS)
def test_each_suppliers_day_state_is_ar1_at_the_declared_coefficient_around_the_declared_mean(
    root: int,
) -> None:
    """Each supplier's day state over ``n`` days, at fixed explicit seeds.

    The state is ``lead_time.py``'s own ``daily_shock`` ``z_d``, so nothing is inferred through a
    log. ``z_0 ~ N(0, 1)`` and each innovation is scaled by ``sqrt(1 - phi^2)``, so the path is
    stationary from day 0 and no burn-in is discarded.

    **Lag-1 band, 4 / sqrt(n).** Bartlett's large-sample variance of the lag-1 estimator of an
    AR(1) is ``(1 - phi^2) / n <= 1 / n``, so the band is at least four standard errors for
    every admissible ``phi``; at this ``n`` the estimator's ``(1 + 4 phi) / n`` bias is under
    1/80 of it.

    **Mean band, derived.** ``L0_d = m exp(s z_d - s^2 / 2)`` is lognormal with
    ``mu = ln m - s^2 / 2``, so its mean is ``m``. With ``corr(z_d, z_{d+k}) = phi^k``,
    ``Cov(L0_d, L0_{d+k}) = m^2 (exp(s^2 phi^k) - 1) <= phi^k m^2 (exp(s^2) - 1)`` by convexity
    of ``x -> exp(s^2 x)`` on [0, 1]; summing the geometric series bounds the sample mean's
    variance by ``m^2 (exp(s^2) - 1) (1 + phi) / ((1 - phi) n)``. The band is four of those
    standard errors: wider for a larger spread or more persistence, narrowing as ``1 / sqrt(n)``.
    """
    supply = _supply()
    phi = supply.daily_autocorrelation
    path = _path({supplier: root + index for index, supplier in enumerate(_SUPPLIERS)}, 0)
    band = 4.0 / math.sqrt(_DAYS)
    assert path.suppliers, "a declared roster, so the loop below checks something"
    for supplier in path.suppliers:
        r1 = _lag_one_autocorrelation([path.daily_shock(supplier, day) for day in range(_DAYS)])
        assert abs(r1 - phi) <= band, f"{supplier}: lag-1 r = {r1:.4f}, declared {phi}"

        spec = supply.suppliers[supplier]
        mean = math.fsum(path.base_lead_time(supplier, day) for day in range(_DAYS)) / _DAYS
        tolerance = (
            4.0
            * spec.mean_lead_time_min
            * math.sqrt(math.expm1(spec.log_sd**2) * (1.0 + phi) / ((1.0 - phi) * _DAYS))
        )
        assert abs(mean - spec.mean_lead_time_min) <= tolerance, (
            f"{supplier}: mean base {mean:.2f} min against the declared "
            f"{spec.mean_lead_time_min}, band +-{tolerance:.2f}"
        )


# ---------------------------------------------------------------------------
# Clause (c) -- the floor, in every committed cell (pure)
# ---------------------------------------------------------------------------


@given(cell=st.sampled_from(_SUPPLY_CELLS), seeds=_SUPPLIER_SEEDS, start=_WEEKDAYS)
def test_no_lead_time_in_any_committed_cell_is_negative_or_below_the_declared_minimum(
    cell: str, seeds: dict[str, int], start: int
) -> None:
    """On the piece itself, in every committed cell that runs structure 3.

    Property 90 asserts the floor on ARRIVALS in the primary cell; a cell that scales lead times
    down brings every base nearer the minimum, which is where a floor applied in the wrong order
    would show. The minimum is positive by rule, so at or above it is also non-negative.
    """
    world = _cell(cell)
    supply = world.supply
    assert supply is not None, cell
    floor = supply.min_lead_time_min
    assert floor > 0.0, "a positive minimum, so at or above it implies non-negative"
    path = LeadTimePath(supply=supply, demand=world.demand, start_weekday=start, seeds=seeds)
    pieces = [
        path.piece_lead_time(supplier, hour)
        for supplier in path.suppliers
        for hour in range(HOURS_PER_WEEK)
    ]
    assert pieces, "a week of hours for a declared roster"
    short = [lead for lead in pieces if not (math.isfinite(lead) and lead >= floor)]
    assert not short, f"{cell}: {short[:3]} below the declared minimum {floor}"


# ---------------------------------------------------------------------------
# Clauses (d) and (e) -- realised orders in the running twin (slow)
# ---------------------------------------------------------------------------

#: One short engine run per seed: the primary cell, endogenous demand and restock off.
_ENGINE_SEEDS = (0, 1, 20_260_929)
#: Units per order: any positive amount, since an order of nothing places nothing.
_UNITS = 5.0
#: Whole hours at which clause (d) orders every SKU. Whole minutes keep every SimPy delay exact,
#: so stock lands at its instant to the bit and equal instants land in the order placed -- which
#: is what lets arrival order be predicted rather than read back. An order placed as hour 3 opens
#: lands no earlier than one placed just before it, in hour 2 -- busier in the committed profile,
#: so slower -- and so inherits a finished piece's instant: the running maximum's second branch.
_ORDER_HOURS = (0, 3, 7)
#: The twin's lead-time multiplier, SET on it rather than left to the engine's default, so the
#: rebuilt arrivals scale each piece by the twin's own ``m`` by construction.
_LEAD_TIME_MULT = 1.0
#: Clause (d)'s clock resolution, 2**-20 h (about 3.4 ms): a dyadic fraction of the hour
#: ``advance`` takes. Every instant clause (d) stops the clock at is a multiple of it, so each
#: subtraction, addition, division by 60 and scaling by 60.0 between this test and SimPy's stop
#: is exact -- and a whole-hour placement made after stopping between ticks is still whole to the
#: bit. "Just before" an instant is the tick below it; "just after", the tick above.
_TICK_MIN = MINUTES_PER_HOUR * 2.0**-20


@dataclasses.dataclass(frozen=True)
class _Order:
    """One order as this test plans it, its arrival instant rebuilt before the order exists."""

    sequence: int
    sku: str
    supplier: str
    placed_at: float
    arrives_at: float
    #: Whether a finished piece set ``arrives_at`` -- the running maximum's inherited branch.
    inherited: bool

    @property
    def lead_time_min(self) -> float:
        return self.arrives_at - self.placed_at

    @property
    def arrival_order(self) -> tuple[float, int]:
        """When SimPy lands it: by instant, and in placement order at one instant."""
        return (self.arrives_at, self.sequence)


def _engine_supplier_seeds(seed: int) -> dict[str, int]:
    """The per-supplier seeds an engine at ``seed`` draws, redrawn here without one.

    ``_configure_world``'s documented rule: one integer below ``_SUPPLIER_SEED_BOUND`` per
    supplier, in sorted id order, from the ``restock`` child of ``SeedSequence(seed)``, spawned
    in the order Property 52 pins.
    """
    children = np.random.SeedSequence(seed).spawn(len(SUBSTREAM_NAMES))
    restock = np.random.default_rng(children[SUBSTREAM_NAMES.index("restock")])
    return {supplier: int(restock.integers(0, _SUPPLIER_SEED_BOUND)) for supplier in _SUPPLIERS}


def _rebuilt_arrival(
    path: LeadTimePath, start: int, supplier: str, placed_at: float
) -> tuple[float, bool]:
    """``A(j, t, m)`` rebuilt by this test, and whether a finished piece set it.

    Every piece from hour 0 to the placement's is first checked against the declared formula
    (``_assert_declared_piece``); the running maximum over them is then taken here rather than
    read from ``lead_time.py``. Each finished piece offers its END plus ``m`` times its lead
    time; the current piece offers the placement instant plus ``m`` times its own.
    """
    supply = _supply()
    shape = _shape()
    hour = int(placed_at // MINUTES_PER_HOUR)
    leads = [
        _assert_declared_piece(path, supply, shape, start, supplier, piece).lead_time_min
        for piece in range(hour + 1)
    ]
    current = placed_at + _LEAD_TIME_MULT * leads[hour]
    inherited = max(
        (
            float((piece + 1) * MINUTES_PER_HOUR) + _LEAD_TIME_MULT * lead
            for piece, lead in enumerate(leads[:hour])
        ),
        default=-math.inf,
    )
    return max(inherited, current), inherited > current


def _plan(seed: int, skus: Sequence[str], hours: Sequence[int]) -> list[_Order]:
    """Every SKU ordered as each whole hour opens, in placement order, with its instant rebuilt.

    Built before the twin places anything, from the seed and the committed world alone: an
    arrival depends on seed, supplier and time and on no order, so every one is known ahead.
    """
    start = start_weekday(seed)
    path = _path(_engine_supplier_seeds(seed), start)
    attribution = _supply().sku_supplier
    plan: list[_Order] = []
    for hour in hours:
        placed_at = float(hour * MINUTES_PER_HOUR)
        for sku in skus:
            supplier = attribution[sku]
            arrives_at, inherited = _rebuilt_arrival(path, start, supplier, placed_at)
            plan.append(
                _Order(
                    sequence=len(plan),
                    sku=sku,
                    supplier=supplier,
                    placed_at=placed_at,
                    arrives_at=arrives_at,
                    inherited=inherited,
                )
            )
    return plan


def _primary_twin(seed: int) -> SupplyChainSimulation:
    """The primary cell's twin with no endogenous demand or restock: only orders move stock."""
    sim = SupplyChainSimulation(seed=seed, world=_primary())
    sim.start(external_demand=True)
    sim.set_policy(restock_threshold=0.0, lead_time_mult=_LEAD_TIME_MULT)
    return sim


def _advance_to(sim: SupplyChainSimulation, t_min: float) -> None:
    """Run the twin's clock forward to ``t_min``; a clock already there stays where it is."""
    if t_min > sim.sim_time_min:
        sim.advance((t_min - sim.sim_time_min) / MINUTES_PER_HOUR)


def _place(sim: SupplyChainSimulation, order: _Order) -> None:
    """Place ``order`` at its whole-hour instant, judged against the instant rebuilt for it.

    The hindsight arm's read, taken before the order exists, and the twin's promise must both
    be that instant.
    """
    _advance_to(sim, order.placed_at)
    assert sim.sim_time_min == order.placed_at, "a whole-minute instant, so every delay is exact"
    assert sim.arrival_time_for(order.sku, order.placed_at) == order.arrives_at, order
    assert sim.place_order(order.sku, _UNITS) == order.arrives_at, order


def _straddle(instant: float) -> tuple[float, float]:
    """The ticks just before and just after ``instant``, which lies strictly between them.

    Exact multiples of ``_TICK_MIN``, also when the instant is itself a tick or its quotient by
    the tick rounds onto one.
    """
    before = math.floor(instant / _TICK_MIN) * _TICK_MIN
    if before >= instant:
        before -= _TICK_MIN
    after = before + _TICK_MIN
    if after <= instant:
        after += _TICK_MIN
    assert before < instant < after, instant
    return before, after


def _units_by_sku(orders: Sequence[_Order]) -> dict[str, float]:
    """Units per SKU over ``orders``; a SKU with none is absent, as it is from ``on_order``."""
    units: dict[str, float] = {}
    for order in orders:
        units[order.sku] = units.get(order.sku, 0.0) + _UNITS
    return units


@pytest.mark.slow
@pytest.mark.parametrize("seed", _ENGINE_SEEDS)
def test_every_order_lands_its_units_at_the_instant_rebuilt_from_its_pieces_and_not_before(
    seed: int,
) -> None:
    """Judged against an arrival the twin did not compute and a shelf it does not narrate.

    The oracle is ``_plan``: the seeds the engine documents drawing, every piece checked against
    the declared formula, and this test's own running maximum, whose inherited branch is
    asserted reached. A tick before each rebuilt instant every order due then is still on order
    and every shelf holds its opening stock plus what earlier instants brought; a tick after,
    exactly those units are on the shelf and off order. At every tick each supplier's history
    is the rebuilt waits landed so far, in arrival order. Finally each landed record names its
    SKU's committed supplier and the rebuilt instant.
    """
    sim = _primary_twin(seed)
    opening = sim.inventory
    plan = _plan(seed, sorted(opening), _ORDER_HOURS)
    assert {order.inherited for order in plan} == {True, False}, (
        "some order sets its own instant and some inherits a finished piece's, so both branches "
        "of the rebuilt running maximum are compared with the twin"
    )
    instants = sorted({order.arrives_at for order in plan})
    probes = [tick for instant in instants for tick in _straddle(instant)]
    assert probes == sorted(probes), "each pair of ticks holds one rebuilt instant and no other"

    unplaced = list(plan)
    for probe in probes:
        while unplaced and unplaced[0].placed_at <= probe:
            _place(sim, unplaced.pop(0))
        _advance_to(sim, probe)
        landed = sorted(
            (order for order in plan if order.arrives_at < probe),
            key=lambda order: order.arrival_order,
        )
        in_transit = [order for order in plan if order.placed_at <= probe < order.arrives_at]
        brought = _units_by_sku(landed)
        shelf = {sku: level + brought.get(sku, 0.0) for sku, level in opening.items()}
        history = {
            supplier: tuple(order.lead_time_min for order in landed if order.supplier == supplier)
            for supplier in _SUPPLIERS
        }
        assert sim.inventory == shelf, (
            f"t = {probe} min: every shelf is its opening stock plus what has landed, no more"
        )
        assert sim.on_order == _units_by_sku(in_transit), (
            f"t = {probe} min: on order is exactly what is placed and not yet due"
        )
        assert sim.supplier_lead_time_history == history, (
            f"t = {probe} min: the history is exactly the rebuilt waits landed so far"
        )
    assert not unplaced and not sim.on_order, "every order was placed, and every one has landed"

    attribution = _supply().sku_supplier
    rebuilt = {(order.sku, order.placed_at): order for order in plan}
    assert len(rebuilt) == len(plan) == len(sim.arrived_orders)
    for arrived in sim.arrived_orders:
        assert arrived.supplier == attribution[arrived.sku], arrived
        assert arrived.arrived_at == rebuilt[(arrived.sku, arrived.placed_at)].arrives_at, arrived
        assert arrived.quantity == _UNITS, arrived


@pytest.mark.slow
@pytest.mark.parametrize("seed", _ENGINE_SEEDS)
def test_an_order_placed_as_the_peak_hour_opens_waits_longer_than_one_placed_at_the_trough(
    seed: int,
) -> None:
    """Realised waits, day 0, the same supplier -- so one day state -- at the declared hours.

    The peak and trough are the hourly profile's argmax and argmin (earliest on a tie). The
    running maximum can hand an earlier piece's arrival to the trough order, so its wait is at
    most the largest piece from hour 0 to the trough, while the peak order waits at least its
    own piece. The premise that makes the comparison strict -- every hour the trough can inherit
    is quieter than the peak -- is asserted, not assumed. Later days are not used: there the
    running maximum can carry a slower PREVIOUS day into the trough, and the comparison would no
    longer be about this day's demand.
    """
    shape = _shape()
    peak = shape.hourly.index(max(shape.hourly))
    trough = shape.hourly.index(min(shape.hourly))
    sim = _primary_twin(seed)
    start = sim.start_weekday
    assert start is not None, "the primary cell runs structure 1"
    assert _supply().demand_coupling > 0.0, "the committed world couples lead time to demand"
    inherited = max(_declared_intensity(shape, hour, start) for hour in range(trough + 1))
    assert inherited < _declared_intensity(shape, peak, start), (
        "premise: on day 0 the trough opens before the peak and inherits only quieter hours"
    )

    placed = _plan(seed, sorted(sim.inventory), (trough, peak))
    for order in placed:
        _place(sim, order)
    _advance_to(sim, max(order.arrives_at for order in placed) + 1.0)
    assert not sim.on_order, "every order landed, so each wait compared is a realised one"

    waits: dict[tuple[str, float], list[float]] = {}
    for arrived in sim.arrived_orders:
        waits.setdefault((arrived.supplier, arrived.placed_at), []).append(arrived.lead_time_min)
    suppliers = sorted({supplier for supplier, _ in waits})
    assert suppliers, "orders landed, so the comparison has subjects"
    for supplier in suppliers:
        at_peak = waits[(supplier, float(peak * MINUTES_PER_HOUR))]
        at_trough = waits[(supplier, float(trough * MINUTES_PER_HOUR))]
        peak_wait = math.fsum(at_peak) / len(at_peak)
        trough_wait = math.fsum(at_trough) / len(at_trough)
        assert peak_wait > trough_wait, (
            f"{supplier}: {peak_wait:.1f} min after the peak opens, {trough_wait:.1f} after "
            "the trough"
        )
