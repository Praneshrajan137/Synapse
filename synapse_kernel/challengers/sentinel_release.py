"""The Inventory Sentinel's newsvendor on the release world, in two forms, each measured alone.

The Sentinel's rule is SYNAPSE's whole decision on the legacy world: the eight-agent consensus arm
equals it to the bit (truth session 5, PR #104; :mod:`synapse_kernel.policies.sentinel`). Here it
meets the release world's observation and economics, in two forms:

* :class:`SentinelAsBuilt`, the legacy rule translated, constants unchanged: the critical fractile
  8/9 (the agent's own costs 8 and 1), demand rate from sales over the component's memory (the
  legacy rate "since the run began", read over the 72-hour memory every component keeps: gate item
  10), the mean landed lead time of the item's supplier seen in that memory or the 24-hour prior, a
  1-hour review, a Poisson spread, and the legacy defaults (mean 10, spread 3) while nothing has
  sold. The legacy arm kept fractional quantities; the release world takes whole units, so the order
  is rounded half up, a chosen translation. It ignores the day's shape, the delivery schedule and
  shelf life, as the legacy rule did.
* :class:`SentinelForThisWorld`, the same newsvendor with the release world's own terms: the
  fractile from J's weights, ``(m + g) / ((m + g) + (1 - m)) = 0.38``; the declared mean over the
  order's protection interval (the incumbent's interval); a spread from Poisson noise and the
  declared day-factor variance; and I2's expected outdating taken off the position. Untuned.

Neither is in the composition unless the trust rule admits it (truth session 6, gate items 7 and
13).
"""

from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING

import numpy as np
import numpy.typing as npt

from synapse_kernel.challengers.exact import isum, seq_sum
from synapse_kernel.challengers.history import WINDOW_HOURS, History
from synapse_kernel.challengers.sensing import AdjustedIncumbent, declared_means, level_grid
from synapse_kernel.challengers.shelf import declared_lives
from synapse_kernel.policies.sentinel import (
    DEFAULT_MEAN,
    DEFAULT_STD,
    STD_FLOOR,
    critical_fractile,
    inverse_normal,
)
from synapse_kernel.release.world import HOURS_PER_DAY

if TYPE_CHECKING:
    from synapse_kernel.release.incumbent import IncumbentTables
    from synapse_kernel.release.observation import StoreObservation
    from synapse_kernel.release.world import ReleaseWorld

__all__ = ["SentinelAsBuilt", "SentinelForThisWorld", "WORLD_FRACTILE"]

F64 = npt.NDArray[np.float64]
I64 = npt.NDArray[np.int64]
#: The newsvendor's fractile at J's primary weights: a lost sale costs m + g = 0.38, a unit thrown
#: away its cost 1 - m = 0.62 (PREREG-1 section 2).
WORLD_FRACTILE: float = 0.38 / (0.38 + 0.62)
#: The legacy review period, one hour (``REVIEW_PERIOD_MIN`` = 60 minutes).
REVIEW_HOURS: float = 1.0
#: The legacy lead-time prior, one day (``LEAD_TIME_PRIOR_MIN`` = 1440 minutes).
LEAD_PRIOR_HOURS: float = 24.0


class SentinelAsBuilt:
    """The legacy Sentinel's rule on the release world's observation, constants unchanged."""

    name = "sentinel_as_built"

    def __init__(self, world: ReleaseWorld) -> None:
        self.history = History(len(world.items), declared_lives(world))
        names = [s.name for s in world.suppliers]
        self.supplier_of = np.array([names.index(item.supplier) for item in world.items])
        self.suppliers = len(names)
        self.z = inverse_normal(critical_fractile())

    def start(self, replicates: int) -> None:
        self.history.start(replicates)
        # Landings seen in the memory: (hours ago, sum of lead hours, count), per supplier.
        self.landings: list[tuple[int, I64, I64]] = []

    def decide(self, obs: StoreObservation) -> I64:
        self.history.update(obs)
        sales, _, _ = self.history.window(WINDOW_HOURS)
        hours = sales.shape[0]
        sold = isum(sales, axis=0).astype(np.float64)
        lead = self._lead(obs)
        with_rate = (hours > 0) & (sold >= 1.0)
        rate = np.where(with_rate, sold / max(hours, 1), 0.0)
        mean = np.where(with_rate, rate * (lead + REVIEW_HOURS), DEFAULT_MEAN)
        std = np.maximum(STD_FLOOR, np.where(with_rate, np.sqrt(mean), DEFAULT_STD))
        q_star = np.maximum(0.0, mean + self.z * std)
        position = isum(obs.on_hand, axis=-1) + isum(obs.open_qty, axis=-1)
        orders = np.floor(np.maximum(0.0, q_star - position) + 0.5).astype(np.int64)
        out: I64 = np.where(obs.deciding[None, :], orders, 0)
        return out

    def _lead(self, obs: StoreObservation) -> F64:
        """Per replicate and item: the mean lead time landed for its supplier in the memory.

        The legacy reader averaged every lead time its supplier landed in the run; within the memory
        rule this averages those landed in the last 72 hours, and uses the 24-hour prior where none.
        """
        step = int(np.asarray(obs.sales).shape[1])
        self.landings = [
            (ago + step, s, c) for ago, s, c in self.landings if ago + step <= WINDOW_HOURS
        ]
        landed = np.asarray(obs.landed_lead_hours, dtype=np.int64)
        r = landed.shape[0]
        total = np.zeros((r, self.suppliers), dtype=np.int64)
        count = np.zeros((r, self.suppliers), dtype=np.int64)
        for j in range(self.suppliers):
            seen = landed[:, self.supplier_of == j, :]
            total[:, j] = isum(np.where(seen > 0, seen, 0), axis=(1, 2))
            count[:, j] = isum((seen > 0).astype(np.int64), axis=(1, 2))
        self.landings.append((0, total, count))
        all_total = np.zeros((r, self.suppliers), dtype=np.int64)
        all_count = np.zeros((r, self.suppliers), dtype=np.int64)
        for _, s, c in self.landings:
            all_total = all_total + s
            all_count = all_count + c
        mean = np.where(
            all_count > 0, all_total / np.where(all_count > 0, all_count, 1), LEAD_PRIOR_HOURS
        )
        out: F64 = mean[:, self.supplier_of].astype(np.float64)
        return out


class SentinelForThisWorld:
    """The newsvendor with the release world's own terms, I2's outdating taken off. Untuned."""

    name = "sentinel_world"

    def __init__(self, world: ReleaseWorld, tables: IncumbentTables) -> None:
        means = declared_means(world)
        declared = dataclasses.replace(
            tables, mean_table=means, factors=np.ones_like(tables.factors)
        )
        self.rule = AdjustedIncumbent(world, declared)
        grid = level_grid(world)
        self.variance = float(seq_sum(grid * grid)) / grid.size - 1.0
        self.z = inverse_normal(WORLD_FRACTILE)

    def start(self, replicates: int) -> None:
        return None

    def decide(self, obs: StoreObservation) -> I64:
        inner = self.rule.inner
        r = obs.on_hand.shape[0]
        ones = np.ones((r, inner.protection.shape[0]))
        week_hour = obs.day_of_week * HOURS_PER_DAY + obs.hour_of_day
        hours = np.where(obs.deciding, inner.protection[:, obs.hour_of_day], 0)
        left = HOURS_PER_DAY - obs.hour_of_day
        mu = self.rule._demand(week_hour, hours[None, :], left, ones, ones)
        sigma = np.sqrt(mu + self.variance * mu * mu)
        target = np.maximum(0.0, mu + self.z * sigma)
        position = isum(obs.on_hand, axis=-1) + isum(obs.open_qty, axis=-1)
        outdating = self.rule._outdating(obs, week_hour, left, ones, ones)
        raw = np.ceil(target - position + outdating)
        orders = np.maximum(0, raw).astype(np.int64)
        out: I64 = np.where(obs.deciding[None, :], orders, 0)
        return out
