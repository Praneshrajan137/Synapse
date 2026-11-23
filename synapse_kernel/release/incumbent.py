"""The incumbent: profile base stock (I1) and waste-aware profile base stock (I2), as sealed.

PREREG-1 section 3. At a decision at time ``t`` for item ``i`` of a supplier taking orders, the
order-up-to level is ``S = ceil(k[i, d] * mu_i(t))``, where ``d`` is the four-hour part of the
day (00-04, ..., 20-24) and ``mu_i(t)`` the mean demand of ``i`` over the protection interval:
from ``t`` to the delivery after the one this order rides (lead time plus the time to the next
delivery), read from ``mean_table`` (per hour of the week, from the tuning seeds' records). With
``IP`` the units on hand plus on order:

* **I1** orders ``max(0, S - IP)``;
* **I2** first subtracts the units expected to outdate: the on-hand batches are depleted oldest
  first by the mean demand up to each batch's expiry; the units left in a batch at its expiry are
  its expected outdating (Broekmeulen and van Donselaar 2009). Its order is
  ``max(0, ceil(S - IP + outdating))`` (the session-5 gate, section 7).

Built only from :class:`~synapse_kernel.release.observation.PolicyInputs`-admissible data: cell N's
declared schedule and the tuning seeds' mean demand. It reads only the observation. Every
computation is exact arithmetic in a fixed order (cumulative sums run sequentially), so it gives the
same orders on every platform.
"""

from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING, Final

import numpy as np
import numpy.typing as npt

from synapse_kernel.release.world import HOURS_PER_DAY, HOURS_PER_WEEK

if TYPE_CHECKING:
    from synapse_kernel.release.observation import StoreObservation
    from synapse_kernel.release.world import ReleaseWorld

__all__ = ["PARTS", "Incumbent", "IncumbentTables", "part_of_day", "protection_hours"]

I64 = npt.NDArray[np.int64]
F64 = npt.NDArray[np.float64]
#: Six four-hour parts of the day (sealed).
PARTS: Final[int] = 6


def part_of_day(hour_of_day: int) -> int:
    """00-04 is part 0, ..., 20-24 is part 5."""
    return hour_of_day // 4


def protection_hours(world: ReleaseWorld) -> I64:
    """Per item and hour of the day: hours from an order placed then to the delivery after the one
    it rides. Only cut-off hours are read; others hold -1."""
    out = np.full((len(world.items), HOURS_PER_DAY), -1, dtype=np.int64)
    suppliers = world.supplier_by_name
    for i, item in enumerate(world.items):
        spec = suppliers[item.supplier]
        for cutoff in spec.cutoff_hours:
            arrives = cutoff + spec.lead_time_hours  # may pass midnight
            later = [h for h in spec.delivery_hours if h > arrives % HOURS_PER_DAY]
            gap = (later[0] if later else spec.delivery_hours[0] + HOURS_PER_DAY) - (
                arrives % HOURS_PER_DAY
            )
            out[i, cutoff] = spec.lead_time_hours + gap
    return out


@dataclasses.dataclass(frozen=True)
class IncumbentTables:
    """One tuned version: its factors and the mean demand it plans against."""

    name: str
    waste_aware: bool
    factors: F64
    """``k[i, d]``, shape ``(items, 6)``, each a multiple of 1/32 and >= 0."""
    mean_table: F64
    """Mean demand per hour of the week (Monday 00:00 first) and item, shape ``(168, items)``."""


class Incumbent:
    """I1 or I2 with one table of factors, deciding for a batch of replicates at once."""

    def __init__(self, world: ReleaseWorld, tables: IncumbentTables) -> None:
        items = len(world.items)
        if tables.factors.shape != (items, PARTS):
            raise ValueError(f"factors must have shape {(items, PARTS)}")
        if tables.mean_table.shape != (HOURS_PER_WEEK, items):
            raise ValueError(f"mean_table must have shape {(HOURS_PER_WEEK, items)}")
        if bool((tables.factors < 0).any()):
            raise ValueError("a factor is negative")
        self.tables = tables
        self.protection = protection_hours(world)
        # Cumulative mean demand over four weeks from Monday 00:00, summed sequentially (cumsum), so
        # mu over any window (a start within the first week, at most three weeks long) is a fixed
        # difference of two entries on every platform.
        weeks = np.concatenate([tables.mean_table] * 4, axis=0)
        self.cumulative = np.concatenate([np.zeros((1, items)), np.cumsum(weeks, axis=0)], axis=0)

    def start(self, replicates: int) -> None:
        return None

    def _window(self, start: int, hours: I64) -> F64:
        """Mean demand per item from hour of the week ``start`` over ``hours`` (per item)."""
        items = np.arange(hours.shape[-1])
        out: F64 = self.cumulative[start + hours, items] - self.cumulative[start, items]
        return out

    def order_up_to(self, obs: StoreObservation) -> I64:
        """``S`` per item at this decision (0 for items not taking orders)."""
        week_hour = obs.day_of_week * HOURS_PER_DAY + obs.hour_of_day
        hours = np.where(obs.deciding, self.protection[:, obs.hour_of_day], 0)
        if bool((hours[obs.deciding] < 0).any()):
            raise ValueError("a deciding item has no protection interval at this hour")
        mu = self._window(week_hour, hours)
        factor = self.tables.factors[:, part_of_day(obs.hour_of_day)]
        level: I64 = np.ceil(factor * mu).astype(np.int64)
        return np.where(obs.deciding, level, 0)

    def expected_outdating(self, obs: StoreObservation) -> F64:
        """Per replicate and item: units expected to outdate, depleting batches oldest first."""
        week_hour = obs.day_of_week * HOURS_PER_DAY + obs.hour_of_day
        qty = obs.on_hand.astype(np.float64)
        until = np.maximum(obs.hours_to_expiry, 0)
        items = np.arange(qty.shape[1])
        consumed = np.zeros(qty.shape[:2])
        outdating = np.zeros(qty.shape[:2])
        for b in range(qty.shape[2]):
            demand = (
                self.cumulative[week_hour + until[:, :, b], items]
                - self.cumulative[week_hour, items]
            )
            used = np.minimum(qty[:, :, b], np.maximum(0.0, demand - consumed))
            consumed = consumed + used
            outdating = outdating + (qty[:, :, b] - used)
        return outdating

    def decide(self, obs: StoreObservation) -> I64:
        target = self.order_up_to(obs)
        position = obs.on_hand.sum(axis=-1) + obs.open_qty.sum(axis=-1)
        if self.tables.waste_aware:
            raw = np.ceil(target[None, :] - position + self.expected_outdating(obs))
            orders = np.maximum(0, raw).astype(np.int64)
        else:
            orders = np.maximum(0, target[None, :] - position)
        out: I64 = np.where(obs.deciding[None, :], orders, 0)
        return out
