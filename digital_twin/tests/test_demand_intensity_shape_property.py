# Feature: decision-quality-proof, Property 55: Demand intensity varies by hour, by weekday and
# under promotion, from the committed policy
"""Structure 1, realised: a day of the twin's demand follows the declared shape (task 12.2).

Subject: ``SupplyChainSimulation._order_arrival`` in the ``s1_only`` cell -- structure 1 on,
structure 3 off -- with endogenous restock off, over 24 h runs from 00:00 of each seed's start
weekday (R5.8-R5.11). Every expected value is read: the shape from ``policy.yaml``
``world.structure_1`` through ``load_world``, the rate from the ``TwinConfig`` the engine runs,
each run's start weekday from the engine itself. No intensity literal appears here.

**Seed set: ``range(70)``** -- ten runs per start weekday under ``seed_mod_7``. FIXED, not
``@given``: the clauses are statistical, and a fixed set makes each verdict a reproducible fact
with known power instead of a fresh draw on every CI run. (d) reruns the first seven seeds with
no world and once per structure-1-off cell of the grid.

**Bounds, derived.** Under structure 1 the arrivals are a Poisson process of the declared
intensity (Property 93), so a window's count -- and its sum over independent runs -- is Poisson
with mean ``mu``, the summed ``expected_units`` of the windows.

* (a) Each hour of the day, summed over the runs: ``|seen - mu| <= 5 sqrt(mu) + 1`` -- five
  standard deviations, plus one for discreteness. Over 24 buckets a false alarm is about 1.4e-5.
* (b) A day with no promotion hour has mean ``rate * 1440 * weekday[d]``, because the hourly
  profile sums to exactly 24 (Property 91). For two such start weekdays the ratio of mean daily
  totals therefore estimates ``weekday[a] / weekday[b]``, and by the delta method its log has
  standard deviation ``sqrt(1/mu_a + 1/mu_b)``, ``mu`` the expected total over each weekday's
  runs. Bound: five of those, for every pair.
* (c) Hours with a promotion open, against the same hours of the day on runs with none open, each
  count over its unpromoted expectation: their ratio estimates the declared multiplier, within the
  same log-scale bound over the two expected counts.
* (d) Every structure-1-off cell of the grid draws HEAD's stationary arrivals exactly.

Each statistical clause also shows its bound REJECTS the flat alternative -- uniform hours, equal
weekdays, no lift -- so it can fail: a bound loose enough to pass anything fails that check.

``@pytest.mark.slow`` -- drives the SimPy twin. Selected by ``ci.yml::uplift-verify-slow``
(``-m "slow"``, ``HYPOTHESIS_PROFILE=heavy``, ``digital_twin/tests`` in its path list). No
Hypothesis budget is spent here, so none is hardcoded.
"""

from __future__ import annotations

import dataclasses
import functools
import itertools
import logging
import math

import pytest
import structlog

from digital_twin.config import TwinConfig
from digital_twin.simulation.engine import SupplyChainSimulation
from digital_twin.simulation.world import (
    DAYS_PER_WEEK,
    HOURS_PER_DAY,
    MINUTES_PER_DAY,
    MINUTES_PER_HOUR,
    DemandShape,
    ResolvedWorld,
    WorldSpec,
    load_world,
)

structlog.configure(wrapper_class=structlog.make_filtering_bound_logger(logging.ERROR))

pytestmark = pytest.mark.slow

_RUNS_PER_WEEKDAY = 10
_SEEDS = tuple(range(_RUNS_PER_WEEKDAY * DAYS_PER_WEEK))
#: Standard deviations in every bound of this file.
_SIGMAS = 5.0
#: Structure 1 on and structure 3 off, at the declared amplitude.
_SHAPED_CELL = "s1_only"


@functools.cache
def _committed() -> WorldSpec:
    return load_world()


@functools.cache
def _config() -> TwinConfig:
    return TwinConfig()


def _shape() -> DemandShape:
    demand = _committed().resolve(_SHAPED_CELL).demand
    assert demand is not None, f"{_SHAPED_CELL} must run structure 1"
    return demand


def _hour_window(hour: int) -> tuple[float, float]:
    """Hour ``hour`` of a run, in minutes from its 00:00."""
    return float(hour * MINUTES_PER_HOUR), float((hour + 1) * MINUTES_PER_HOUR)


@dataclasses.dataclass(frozen=True)
class _Day:
    """One 24 h run: its seed, the weekday its hour 0 falls on, and its arrivals."""

    seed: int
    weekday: int
    times: tuple[float, ...]
    hourly: tuple[int, ...]


def _run_day(seed: int, world: ResolvedWorld | None) -> SupplyChainSimulation:
    """24 h of the twin at ``seed``, its endogenous restock off."""
    sim = SupplyChainSimulation(config=_config(), seed=seed, world=world)
    sim.set_policy(restock_threshold=0.0)
    sim.start()
    sim.advance(float(HOURS_PER_DAY))
    return sim


@functools.cache
def _shaped_days() -> tuple[_Day, ...]:
    """The seed set under structure 1, run once and read by every clause."""
    world = _committed().resolve(_SHAPED_CELL)
    days: list[_Day] = []
    for seed in _SEEDS:
        sim = _run_day(seed, world)
        weekday = sim.start_weekday
        assert weekday is not None, "structure 1 on derives the start weekday from the seed"
        times = tuple(event.t_min for event in sim.demand_trace.events)
        assert len(times) == sim.metrics.orders_created, "every arrival is in the trace"
        assert all(0.0 <= t < MINUTES_PER_DAY for t in times), "every arrival is inside the day"
        hourly = [0] * HOURS_PER_DAY
        for t in times:
            hourly[int(t // MINUTES_PER_HOUR)] += 1
        days.append(_Day(seed=seed, weekday=weekday, times=times, hourly=tuple(hourly)))
    return tuple(days)


def _within(seen: float, mu: float) -> bool:
    """Clause (a)'s per-bucket Poisson bound."""
    return abs(seen - mu) <= _SIGMAS * math.sqrt(mu) + 1.0


def _log_bound(*mus: float) -> float:
    """Five delta-method sds of the log of a ratio of independent Poisson totals."""
    return _SIGMAS * math.sqrt(math.fsum(1.0 / mu for mu in mus))


def _promoted_hours(shape: DemandShape, weekday: int) -> tuple[int, ...]:
    """The hours of ``weekday`` (0 = Monday) during which some promotion is open."""
    return tuple(
        hour
        for hour in range(HOURS_PER_DAY)
        if shape.promotion_factor(weekday * HOURS_PER_DAY + hour) != 1.0
    )


def _tally(
    slots: list[tuple[_Day, int]], unpromoted: DemandShape, rate: float
) -> tuple[int, float]:
    """Arrivals seen in ``slots`` (run, hour of day), and their expectation with no promotion."""
    seen = sum(day.hourly[hour] for day, hour in slots)
    mu = math.fsum(
        unpromoted.expected_units(*_hour_window(hour), day.weekday, rate) for day, hour in slots
    )
    return seen, mu


def test_each_hour_of_the_day_carries_its_declared_share_of_demand() -> None:
    """(a) R5.8: summed over the seed set, each hour of the day holds its expected count within
    the Poisson bound -- and the same bound rejects a flat day, so it can fail."""
    shape, rate, days = _shape(), _config().order_arrival_rate, _shaped_days()
    seen = [sum(day.hourly[hour] for day in days) for hour in range(HOURS_PER_DAY)]
    mus = [
        math.fsum(shape.expected_units(*_hour_window(hour), day.weekday, rate) for day in days)
        for hour in range(HOURS_PER_DAY)
    ]

    assert sum(seen) > 0, "the seed set generated demand"
    misses = [
        (hour, count, round(mu, 1))
        for hour, (count, mu) in enumerate(zip(seen, mus, strict=True))
        if not _within(count, mu)
    ]
    assert not misses, f"hours outside the Poisson bound (hour, seen, expected): {misses}"
    flat = len(days) * rate * MINUTES_PER_HOUR
    assert any(not _within(count, flat) for count in seen), "the bound cannot tell shape from flat"


def test_runs_on_different_weekdays_carry_demand_in_the_declared_weekday_ratio() -> None:
    """(b) R5.9: for every pair of promotion-free start weekdays the ratio of mean daily totals is
    the declared ratio within the bound -- and the most different pair is told from a flat week."""
    shape, rate, days = _shape(), _config().order_arrival_rate, _shaped_days()
    plain = [weekday for weekday in range(DAYS_PER_WEEK) if not _promoted_hours(shape, weekday)]
    runs = {weekday: [day for day in days if day.weekday == weekday] for weekday in plain}
    assert len(plain) >= 2, "two promotion-free weekdays exist to compare"
    assert all(runs.values()), "the seed set runs every promotion-free weekday"
    mean_total = {w: sum(len(day.times) for day in runs[w]) / len(runs[w]) for w in plain}
    day_minutes = float(MINUTES_PER_DAY)
    mu = {w: len(runs[w]) * shape.expected_units(0.0, day_minutes, w, rate) for w in plain}

    misses: list[tuple[int, int, float, float]] = []
    for a, b in itertools.combinations(plain, 2):
        realised = math.log(mean_total[a] / mean_total[b])
        declared = math.log(shape.weekday[a] / shape.weekday[b])
        if abs(realised - declared) > _log_bound(mu[a], mu[b]):
            misses.append((a, b, round(realised, 4), round(declared, 4)))
    assert not misses, f"weekday pairs outside the bound (a, b, realised, declared): {misses}"

    # Power: the pair the policy declares most different is told apart from a flat week.
    a, b = max(
        itertools.combinations(plain, 2),
        key=lambda pair: abs(math.log(shape.weekday[pair[0]] / shape.weekday[pair[1]])),
    )
    realised = math.log(mean_total[a] / mean_total[b])
    assert abs(realised) > _log_bound(mu[a], mu[b]), f"weekdays {a} and {b} read as a flat week"


def test_a_promotion_window_carries_its_declared_multiplier() -> None:
    """(c) R5.10: hours with a promotion open, over their unpromoted expectation, against the same
    hours of the day on runs with none open -- the realised lift is the declared multiplier, and
    it is told apart from no lift at all."""
    shape, rate, days = _shape(), _config().order_arrival_rate, _shaped_days()
    assert shape.promotions, "the committed world declares a promotion, so this is not vacuous"
    unpromoted = dataclasses.replace(shape, promotions=())
    slots = [
        (day, hour, shape.promotion_factor(day.weekday * HOURS_PER_DAY + hour))
        for day in days
        for hour in range(HOURS_PER_DAY)
    ]
    lifts = sorted({factor for _, _, factor in slots if factor != 1.0})
    assert lifts, "the seed set reaches an hour with a promotion open"

    for lift in lifts:
        promoted = [(day, hour) for day, hour, factor in slots if factor == lift]
        hours = {hour for _, hour in promoted}
        control = [(day, hour) for day, hour, factor in slots if factor == 1.0 and hour in hours]
        assert control, f"no promotion-free run covers the hours of the x{lift} window"
        seen_promoted, mu_promoted = _tally(promoted, unpromoted, rate)
        seen_control, mu_control = _tally(control, unpromoted, rate)
        realised = math.log((seen_promoted / mu_promoted) / (seen_control / mu_control))
        bound = _log_bound(lift * mu_promoted, mu_control)

        assert abs(realised - math.log(lift)) <= bound, (lift, math.exp(realised), bound)
        assert abs(realised) > bound, f"the x{lift} window cannot be told from no lift"


def test_with_structure_1_off_every_cell_draws_heads_stationary_arrivals_exactly() -> None:
    """(d) PRESERVE: at one seed, every structure-1-off cell of the grid is HEAD's demand path --
    and the shaped run at that seed is not, so the equality could fail."""
    grid = _committed()
    off = sorted(name for name, cell in grid.cells.items() if not cell.structure_1)
    assert off, "the grid declares structure-1-off cells, so the loop compares some"
    shaped = {day.seed: day.times for day in _shaped_days()}

    for seed in _SEEDS[:DAYS_PER_WEEK]:
        head = _run_day(seed, None).demand_trace.as_tuples()
        assert head, f"seed {seed}: a day of HEAD's twin generates demand"
        for name in off:
            path = _run_day(seed, grid.resolve(name)).demand_trace.as_tuples()
            assert path == head, f"{name} at seed {seed} left HEAD's arrival process"
        assert shaped[seed] != tuple(t for t, _, _ in head), f"seed {seed}: shape moved nothing"
