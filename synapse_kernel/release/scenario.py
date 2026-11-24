"""One replicate's exogenous world, drawn entirely before any policy acts.

A :class:`Scenario` holds every random quantity a replicate meets: the units demanded per item and
hour, the shock, and when an order placed at each cut-off will land. It is a pure function of
(world, cell, seed) and is built before the engine starts, so a policy's orders cannot move a draw
by construction (PREREG-1 section 1, common random numbers): the engine has no generator at all.

Demand, per item ``i`` and hour ``h`` (hour 0 is Monday 00:00 of the warm-up's first day):
``lambda = rate_i / 24 * profile_i[h mod 168] * store_day[d] * item_day[d, i]``, the day factors
read from the world's equal-probability tables by one uniform each. Units arrive as singles and as
pairs (a share ``q`` of purchase events take two): ``singles ~ Poisson(lambda (1-q) / (1+q))``,
``pairs ~ Poisson(lambda q / (1+q))``, units = singles + 2 pairs, so the mean is ``lambda``. In a
surge, the affected items' hours in the window add the same construction at ``lambda (u - 1)`` from
streams of their own, so the base demand is identical to cell N's at the same seed.
"""

from __future__ import annotations

import dataclasses
import math
from typing import TYPE_CHECKING

import numpy as np
import numpy.typing as npt

from synapse_kernel.release.cells import Shock, draw_shock, shelf_lives
from synapse_kernel.release.rng import Purpose, uniforms
from synapse_kernel.release.sampling import poisson_inverse
from synapse_kernel.release.world import HOURS_PER_DAY, HOURS_PER_WEEK

if TYPE_CHECKING:
    from synapse_kernel.release.world import ReleaseWorld

__all__ = ["Scenario", "build_scenario", "demand_means"]

I64 = npt.NDArray[np.int64]
F64 = npt.NDArray[np.float64]


@dataclasses.dataclass(frozen=True)
class Scenario:
    """Everything random about one replicate, fixed before it runs."""

    seed: int
    cell: str
    demand: I64
    """Units demanded per hour per item, shape ``(horizon_hours, items)``."""
    shock: Shock
    shelf_life: I64
    """Each item's shelf life at receipt in this cell, whole hours."""

    def demand_digest(self) -> str:
        """A sha256 of the demand array's bytes: what tests compare across policies."""
        import hashlib

        return hashlib.sha256(np.ascontiguousarray(self.demand).tobytes()).hexdigest()


def demand_means(world: ReleaseWorld) -> F64:
    """``rate_i / 24 * profile_i[how]``: declared mean demand per item and hour of the week.

    Shape ``(168, items)``; the day factors have mean one, so this is cell N's expected demand.
    """
    out = np.empty((HOURS_PER_WEEK, len(world.items)), dtype=np.float64)
    for i, item in enumerate(world.items):
        profile = np.asarray(world.profiles[item.profile], dtype=np.float64)
        out[:, i] = (item.rate_per_day / HOURS_PER_DAY) * profile
    return out


def _factors(table: tuple[float, ...], draws: F64) -> F64:
    index = np.floor(draws * len(table)).astype(np.int64)
    return np.asarray(table, dtype=np.float64)[index]


def _units(seed: int, means: F64, singles: int, pairs: int, q: float) -> I64:
    """Units from singles and pairs at hourly means ``means`` (shape ``(hours, items)``)."""
    hours, items = means.shape
    entity = np.arange(items)[None, :]
    slot = np.arange(hours)[:, None]
    events = means / (1.0 + q)
    one = poisson_inverse(uniforms(seed, singles, entity, slot), events * (1.0 - q))
    two = poisson_inverse(uniforms(seed, pairs, entity, slot), events * q)
    out: I64 = one + 2 * two
    return out


def hourly_means(world: ReleaseWorld, seed: int) -> F64:
    """This replicate's demand means per hour and item, day factors included (cell N)."""
    hours = world.horizon_hours
    days = hours // HOURS_PER_DAY
    week = demand_means(world)
    base = week[np.arange(hours) % HOURS_PER_WEEK]
    store = _factors(world.day_store_factors, uniforms(seed, Purpose.DAY_STORE, 0, np.arange(days)))
    item_day = _factors(
        world.day_item_factors,
        uniforms(
            seed, Purpose.DAY_ITEM, np.arange(len(world.items))[None, :], np.arange(days)[:, None]
        ),
    )
    day_of_hour = np.arange(hours) // HOURS_PER_DAY
    out: F64 = base * store[day_of_hour][:, None] * item_day[day_of_hour]
    return out


def build_scenario(world: ReleaseWorld, cell: str, seed: int) -> Scenario:
    """Draw replicate ``seed`` of ``cell`` in ``world``: demand, shock and shelf lives."""
    shock = draw_shock(world, cell, seed)
    means = hourly_means(world, seed)
    q = world.pair_share
    demand = _units(seed, means, Purpose.DEMAND, Purpose.DEMAND_PAIRS, q)
    if shock.kind == "surge":
        hours = np.arange(world.horizon_hours)
        in_window = (hours >= shock.onset_hour) & (hours < shock.end_hour)
        surge = np.zeros_like(means)
        cols = np.asarray(shock.items, dtype=np.int64)
        surge[np.ix_(np.nonzero(in_window)[0], cols)] = means[
            np.ix_(np.nonzero(in_window)[0], cols)
        ] * (shock.size - 1.0)
        extra = _units(seed, surge, Purpose.SURGE_DEMAND, Purpose.SURGE_PAIRS, q)
        demand = demand + extra
    return Scenario(
        seed=seed, cell=cell, demand=demand, shock=shock, shelf_life=shelf_lives(world, cell)
    )


def arrival_hour(world: ReleaseWorld, shock: Shock, supplier: int, placed: int) -> int:
    """The whole hour an order placed at cut-off hour ``placed`` with ``supplier`` lands.

    Nominal: ``placed + lead time``, the delivery the cut-off serves. Delay (S2, placement in the
    window): the first scheduled delivery at or after ``placed + v * lead time``. Outage (S3): an
    order placed in the window lands at the first whole hour at or after ``end + lead time``; an
    order whose delivery falls in the window lands at the first whole hour at or after its end.
    """
    spec = world.suppliers[supplier]
    lead = spec.lead_time_hours
    nominal = placed + lead
    if shock.supplier != supplier:
        return nominal
    if shock.kind == "delay" and shock.covers(placed):
        earliest = placed + shock.size * lead
        day = math.floor(earliest / HOURS_PER_DAY)
        for d in range(day, day + 3):
            for hour in spec.delivery_hours:
                candidate = d * HOURS_PER_DAY + hour
                if candidate >= earliest:
                    return candidate
        raise AssertionError("a supplier with a delivery hour delivers within two days")
    if shock.kind == "outage":
        if shock.covers(placed):
            return math.ceil(shock.end_hour + lead)
        if shock.covers(nominal):
            return math.ceil(shock.end_hour)
    return nominal
