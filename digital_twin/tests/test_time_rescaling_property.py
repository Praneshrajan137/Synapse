# Feature: decision-quality-proof, Property 93: Arrivals invert the declared cumulative intensity
# exactly, and structure 1 off is HEAD's arrival process
"""Structure 1's arrivals are exact time-rescaling of the declared intensity (task 12.1).

Subjects: ``DemandShape.next_arrival`` (``digital_twin/simulation/world.py``) and the engine's
``_order_arrival``. Under structure 1 each arrival draws ONE standard exponential ``E`` from the
``demand`` substream and lands where the declared cumulative intensity since the previous arrival
reaches ``E`` (Lewis & Shedler 1979, NRLQ 26(3):403-413, section 1(i)) -- exact for an intensity
that is constant within each simulated hour.

**(a) The inverse, checked by an independent computation.** ``expected_units`` integrates over
``hour_boundaries`` in ``math.fsum``; ``next_arrival`` walks the hours by subtraction and solves
the last in closed form. They share only ``hour_intensity``. **The domain of ``1e-9``:** an
arrival is a float, so the mass between ``t`` and it is resolved only to about
``rate * I * ulp(arrival)`` -- a fact about the clock, not about the inversion. ``_MASS_FLOOR`` is
DERIVED from the committed shapes and the generated bounds so that four such ulps, at the peak
intensity and the latest instant the domain reaches, are ``1e-9`` of it; the walk's own rounding
(about ``K * eps`` relative over ``K`` hours) is far inside that. Smaller masses are covered by
(b)'s ordering clause, which claims no precision.

**(b)** More mass arrives strictly later for any gap the clock resolves, and never at ``t``; for
EVERY mass, zero included, the arrival is non-decreasing in IEEE 754 itself -- by construction,
because the result is clamped to the hour that solved it. **(c)** A flat profile reduces the
inversion to ``t + mass / rate`` within ``1e-12``. Every refusal is proven by construction.

**(d)** No world and the ``off_off`` cell draw one 24 h demand path and leave the ``demand``
substream in one state; ``s1_only`` at the same seed draws another, so the equality could fail.
**(e)** With structure 1 on, the engine's arrival times are exactly the inversions of its own
``demand`` draws, replayed one draw per arrival -- so the arithmetic (a) checks is what runs.

Locus: (a)-(c) and the refusals are arithmetic and run in ``quality-gates``. (d) and (e) advance
the SimPy twin, so they are ``@pytest.mark.slow`` (I-0) and run in ``uplift-verify-slow``. Budget
inherited from ``HYPOTHESIS_PROFILE``; no ``max_examples`` literal.
"""

from __future__ import annotations

import functools
import logging
import math

import pytest
import structlog
from hypothesis import example, given
from hypothesis import strategies as st

from digital_twin.config import TwinConfig
from digital_twin.simulation import world as world_module
from digital_twin.simulation.engine import SupplyChainSimulation
from digital_twin.simulation.world import (
    DAYS_PER_WEEK,
    HOURS_PER_DAY,
    HOURS_PER_WEEK,
    MINUTES_PER_HOUR,
    DemandShape,
    Promotion,
    ResolvedWorld,
    WorldSpec,
    load_world,
)

structlog.configure(wrapper_class=structlog.make_filtering_bound_logger(logging.ERROR))


@functools.cache
def _committed() -> WorldSpec:
    return load_world()


@functools.cache
def _config() -> TwinConfig:
    return TwinConfig()


def _cell(name: str) -> ResolvedWorld:
    return _committed().resolve(name)


@functools.cache
def _shape(cell: str) -> DemandShape:
    demand = _cell(cell).demand
    assert demand is not None, f"{cell} must run structure 1"
    return demand


def _first_promotion() -> Promotion:
    promotions = _committed().structure_1.promotions
    assert promotions, "the committed world declares a promotion; an example below crosses it"
    return promotions[0]


#: Every committed cell running structure 1: the declared shape and each amplitude rescale of it.
_SHAPED_CELLS = sorted(name for name, spec in _committed().cells.items() if spec.structure_1)
_INTENSITIES = [
    _shape(name).hour_intensity(hour, 0) for name in _SHAPED_CELLS for hour in range(HOURS_PER_WEEK)
]
_PEAK = max(_INTENSITIES)
_TROUGH = min(_INTENSITIES)
_PRIMARY = _committed().primary_cell

_REL_TOL = 1e-9
#: Per-minute rates over two decades; the engine passes its arrival rate times ``demand_mult``.
_RATE_MIN = 0.05
_RATE_MAX = 5.0
#: Start instants over one week: every hour of the week, every weekday change, every promotion.
_T_MAX = float(HOURS_PER_WEEK * MINUTES_PER_HOUR)
#: A standard exponential exceeds this with probability e**-25.
_MASS_MAX = 25.0
#: The latest instant the domain reaches: the integral grows at no less than ``rate * trough``.
_LATEST = _T_MAX + _MASS_MAX / (_RATE_MIN * _TROUGH)
#: The floor of (a)'s domain: ``1e-9`` of it is four clock ulps' worth of mass at the peak rate
#: and the latest instant. Below it, ``1e-9`` would be a claim about float spacing.
_MASS_FLOOR = 4.0 * _RATE_MAX * _PEAK * math.ulp(_LATEST) / _REL_TOL

_CELLS = st.sampled_from(_SHAPED_CELLS)
_TIMES = st.floats(min_value=0.0, max_value=_T_MAX, allow_nan=False)
_RATES = st.floats(min_value=_RATE_MIN, max_value=_RATE_MAX, allow_nan=False)
_WEEKDAYS = st.integers(min_value=0, max_value=DAYS_PER_WEEK - 1)
_MASSES = st.floats(min_value=_MASS_FLOOR, max_value=_MASS_MAX, allow_nan=False)
#: Halves, so that a mass plus a gap stays inside the domain the floor was derived over.
_HALF_MASSES = st.floats(min_value=_MASS_FLOOR, max_value=_MASS_MAX / 2.0, allow_nan=False)
_ANY_MASSES = st.floats(min_value=0.0, max_value=_MASS_MAX, allow_nan=False)
#: Built by hand -- every value 1.0, no promotion -- so the walk is a sum of flat hours.
_FLAT = DemandShape(hourly=(1.0,) * HOURS_PER_DAY, weekday=(1.0,) * DAYS_PER_WEEK, promotions=())


# ---------------------------------------------------------------------------
# Property 93 -- the inversion, pure
# ---------------------------------------------------------------------------


@given(cell=_CELLS, t=_TIMES, mass=_MASSES, start=_WEEKDAYS, rate=_RATES)
@example(
    cell=_PRIMARY,
    t=max(0.0, _first_promotion().start_hour * MINUTES_PER_HOUR - 10.0),
    mass=_MASS_MAX,
    start=_first_promotion().weekday,
    rate=1.0,
)
@example(cell=_PRIMARY, t=_T_MAX - 30.0, mass=_MASS_MAX, start=0, rate=_RATE_MIN)
def test_an_arrival_spends_exactly_the_drawn_mass_of_declared_intensity(
    cell: str, t: float, mass: float, start: int, rate: float
) -> None:
    """The first example opens a promotion mid-gap; the second wraps Sunday into Monday."""
    shape = _shape(cell)

    arrival = shape.next_arrival(t, mass, start, rate)
    spent = shape.expected_units(t, arrival, start, rate)

    assert math.isclose(spent, mass, rel_tol=_REL_TOL), (arrival, spent)


@given(cell=_CELLS, t=_TIMES, mass=_HALF_MASSES, gap=_HALF_MASSES, start=_WEEKDAYS, rate=_RATES)
def test_more_mass_arrives_strictly_later_and_no_arrival_is_at_its_start(
    cell: str, t: float, mass: float, gap: float, start: int, rate: float
) -> None:
    """Strict over the reals; in floats for any gap of at least the floor, which at the peak rate
    is billions of clock ulps of time."""
    shape = _shape(cell)

    sooner = shape.next_arrival(t, mass, start, rate)
    later = shape.next_arrival(t, mass + gap, start, rate)

    assert t < sooner < later


@given(
    cell=_CELLS,
    t=_TIMES,
    masses=st.tuples(_ANY_MASSES, _ANY_MASSES),
    start=_WEEKDAYS,
    rate=_RATES,
)
@example(cell=_PRIMARY, t=0.0, masses=(0.0, math.ulp(0.0)), start=0, rate=_RATE_MAX)
def test_for_every_mass_including_zero_a_larger_mass_never_arrives_sooner(
    cell: str, t: float, masses: tuple[float, float], start: int, rate: float
) -> None:
    """Non-decreasing in IEEE 754 itself, not only over the reals: each subtraction rounds
    monotonically and the result is clamped to the hour that solved it. Zero mass arrives at t."""
    shape = _shape(cell)
    small, large = sorted(masses)

    first = shape.next_arrival(t, small, start, rate)
    second = shape.next_arrival(t, large, start, rate)

    assert t <= first <= second
    assert shape.next_arrival(t, 0.0, start, rate) == t


@given(t=_TIMES, mass=_ANY_MASSES, start=_WEEKDAYS, rate=_RATES)
def test_a_flat_profile_reduces_the_inversion_to_the_stationary_gap(
    t: float, mass: float, start: int, rate: float
) -> None:
    arrival = _FLAT.next_arrival(t, mass, start, rate)

    assert math.isclose(arrival, t + mass / rate, rel_tol=1e-12)


@pytest.mark.parametrize(
    ("t", "mass", "start", "rate", "fragment"),
    [
        pytest.param(0.0, -1.0, 0, 1.0, "mass", id="negative-mass"),
        pytest.param(0.0, math.inf, 0, 1.0, "mass", id="infinite-mass"),
        pytest.param(0.0, math.nan, 0, 1.0, "mass", id="nan-mass"),
        pytest.param(0.0, 1.0, 0, 0.0, "rate_per_min", id="zero-rate"),
        pytest.param(0.0, 1.0, 0, -2.0, "rate_per_min", id="negative-rate"),
        pytest.param(0.0, 1.0, 0, math.inf, "rate_per_min", id="infinite-rate"),
        pytest.param(math.inf, 1.0, 0, 1.0, "simulated time", id="infinite-time"),
        pytest.param(0.0, 1.0, DAYS_PER_WEEK, 1.0, "start_weekday", id="weekday-out-of-range"),
    ],
)
def test_the_inversion_refuses_each_broken_precondition_by_name(
    t: float, mass: float, start: int, rate: float, fragment: str
) -> None:
    """Each case breaks one precondition of an otherwise valid call; the valid calls are (a)."""
    with pytest.raises(ValueError, match=fragment):
        _shape(_PRIMARY).next_arrival(t, mass, start, rate)


def test_a_mass_no_bounded_walk_can_spend_is_refused_naming_where_it_stopped() -> None:
    """By construction: a flat hour at unit rate holds sixty units, so one hour's more than the
    bound's worth of hours is refused rather than walked on -- naming the walk's state."""
    bound = world_module._MAX_INTENSITY_PIECES  # noqa: SLF001 -- the bound, read not restated
    too_much = float(MINUTES_PER_HOUR) * (bound + 1)

    with pytest.raises(RuntimeError, match=f"walked {bound} hours") as refused:
        _FLAT.next_arrival(0.0, too_much, 0, 1.0)

    assert "unspent" in str(refused.value)


# ---------------------------------------------------------------------------
# Property 93 -- the engine (slow: these advance the SimPy twin)
# ---------------------------------------------------------------------------

#: Explicit seeds for the engine clauses; each costs a few simulated days.
_ENGINE_SEEDS = (0, 1, 20260929)


def _day(seed: int, world: ResolvedWorld | None) -> SupplyChainSimulation:
    """One simulated day of the twin at ``seed``, endogenous demand on."""
    sim = SupplyChainSimulation(config=_config(), seed=seed, world=world)
    sim.start()
    sim.advance(float(HOURS_PER_DAY))
    return sim


def _demand_state(sim: SupplyChainSimulation) -> object:
    return sim.streams["demand"].bit_generator.state


@pytest.mark.slow
@pytest.mark.parametrize("seed", _ENGINE_SEEDS)
def test_with_structure_1_off_a_day_of_arrivals_is_heads_draw_for_draw(seed: int) -> None:
    """(d) PRESERVE: no world and the both-off cell, one demand path and one substream state."""
    head = _day(seed, None)
    off = _day(seed, _cell("off_off"))
    shaped = _day(seed, _cell("s1_only"))

    assert len(head.demand_trace) > 0, "a day of HEAD's twin generates demand"
    assert off.demand_trace.as_tuples() == head.demand_trace.as_tuples()
    assert _demand_state(off) == _demand_state(head)
    # The equality could fail: with structure 1 on, the same seed's draws land elsewhere.
    assert shaped.demand_trace.as_tuples() != head.demand_trace.as_tuples()


@pytest.mark.slow
@pytest.mark.parametrize("seed", _ENGINE_SEEDS)
def test_with_structure_1_on_each_arrival_is_the_inversion_of_one_demand_draw(seed: int) -> None:
    """(e) Replayed apart from the engine: a fresh ``demand`` substream at the seed, one unit
    exponential per arrival, inverted at the engine's rate, start weekday and clock."""
    world = _cell("s1_only")
    shape = world.demand
    assert shape is not None, "s1_only runs structure 1"
    sim = _day(seed, world)
    start = sim.start_weekday
    assert start is not None, "structure 1 on derives the start weekday from the seed"
    draws = SupplyChainSimulation(seed=seed).streams["demand"]
    rate = _config().order_arrival_rate

    replayed: list[float] = []
    now = 0.0
    while True:
        # The engine yields `arrival - now` and SimPy adds it back to the clock: the same floats.
        arrival = now + (shape.next_arrival(now, draws.exponential(1.0), start, rate) - now)
        if arrival >= sim.sim_time_min:
            break
        replayed.append(arrival)
        now = arrival

    assert replayed, "a day of shaped demand generates arrivals"
    assert [event.t_min for event in sim.demand_trace.events] == replayed
    assert draws.bit_generator.state == _demand_state(sim), "one draw per arrival, never more"
