"""The headroom oracle and the guard: exploratory descriptions for freeze W, never a challenger.

PREREG-1 section 6: before freeze W, an oracle arm told each shock's items, onset, size and duration
runs on the validation seeds, and its mean advantage over the incumbent in each shock cell is
published. The oracle here is the cell's selected incumbent version with the shock inserted into
what it plans against (the session-5 gate, section 7): in a surge, the affected items' mean
demand over the protection interval gains ``(u - 1)`` times the mean demand in the window's overlap
with it; in a delay or an outage, the protection interval runs to the delivery after the order's
actual arrival. It reads the scenario, which no policy may do: it is a measuring instrument, not
a policy.

:class:`Guarded` passes the oracle through the guard (:mod:`synapse_kernel.release.guard`) against
the incumbent on the same state, to measure how much of the oracle's headroom survives it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
import numpy.typing as npt

from synapse_kernel.release.guard import guard
from synapse_kernel.release.incumbent import Incumbent, part_of_day
from synapse_kernel.release.scenario import arrival_hour
from synapse_kernel.release.world import HOURS_PER_DAY

if TYPE_CHECKING:
    from synapse_kernel.release.cells import Shock
    from synapse_kernel.release.incumbent import IncumbentTables
    from synapse_kernel.release.observation import StoreObservation
    from synapse_kernel.release.scenario import Scenario
    from synapse_kernel.release.world import ReleaseWorld

__all__ = ["Guarded", "ShockOracle"]

I64 = npt.NDArray[np.int64]


class ShockOracle(Incumbent):
    """An incumbent version told the shock of each replicate (one scenario per replicate)."""

    def __init__(
        self,
        world: ReleaseWorld,
        tables: IncumbentTables,
        batch: list[Scenario],
        response: npt.NDArray[np.float64] | None = None,
    ) -> None:
        super().__init__(world, tables)
        self.world = world
        self.batch = batch
        # kappa per item: scales only the informed part of a decision (1 keeps the told rule).
        self.response = (
            np.ones(len(world.items)) if response is None else np.asarray(response, dtype=float)
        )
        self.supplier_of = np.array(
            [[s.name for s in world.suppliers].index(item.supplier) for item in world.items]
        )
        # The engine never tells a policy the hour; the oracle, an instrument, counts its calls
        # against the declared cut-off schedule, which fixes the hour of every decision.
        cutoffs = {h for s in world.suppliers for h in s.cutoff_hours}
        self.decision_hours = [
            h for h in range(world.horizon_hours) if h % HOURS_PER_DAY in cutoffs
        ]
        self.calls = 0
        self.hour = 0

    def start(self, replicates: int) -> None:
        if replicates != len(self.batch):
            raise ValueError("the oracle needs one scenario per replicate")
        self.calls = 0

    def decide(self, obs: StoreObservation) -> I64:
        """Per replicate: the incumbent's rule with its own replicate's shock inserted."""
        self.hour = self.decision_hours[self.calls]
        self.calls += 1
        if self.hour % HOURS_PER_DAY != obs.hour_of_day:
            raise RuntimeError("the oracle lost count of the decisions")
        rows = [self._decide_one(obs, r, scenario) for r, scenario in enumerate(self.batch)]
        out: I64 = np.stack(rows)
        return out

    def _decide_one(self, obs: StoreObservation, r: int, scenario: Scenario) -> I64:
        """The incumbent's decision, informed of this replicate's shock where the shock bears."""
        one = _single(obs, r)
        base: I64 = Incumbent.decide(self, one)[0]
        shock = scenario.shock
        if shock.kind == "surge":
            return self._surge(obs, base, shock)
        if shock.kind in ("delay", "outage"):
            return self._supply(obs, r, base, scenario)
        return base

    def _surge(self, obs: StoreObservation, base: I64, shock: Shock) -> I64:
        """Surged items: the incumbent's level with ``(u - 1)`` times the window's demand added."""
        hour = self.hour
        week_hour = obs.day_of_week * HOURS_PER_DAY + obs.hour_of_day
        out = base.copy()
        factor = self.tables.factors[:, part_of_day(obs.hour_of_day)]
        for item in shock.items:
            if not obs.deciding[item]:
                continue
            span = int(self.protection[item, obs.hour_of_day])
            lo = max(float(hour), shock.onset_hour)
            hi = min(float(hour + span), shock.end_hour)
            if hi <= lo:
                continue
            a = week_hour + int(np.ceil(lo)) - hour
            b = week_hour + int(np.ceil(hi)) - hour
            extra = (shock.size - 1.0) * (self.cumulative[b, item] - self.cumulative[a, item])
            scale = float(factor[item]) * float(self.response[item])
            out[item] = base[item] + int(np.ceil(scale * extra))
        return out

    def _supply(self, obs: StoreObservation, r: int, base: I64, scenario: Scenario) -> I64:
        """The shocked supplier's items: cover demand from this order's actual arrival to the next
        order's, given the stock projected to that arrival (lost sales: demand before it is lost),
        capped by what can sell before the batch expires."""
        shock = scenario.shock
        j = int(shock.supplier)
        hour = self.hour
        week_hour = obs.day_of_week * HOURS_PER_DAY + obs.hour_of_day
        spec = self.world.suppliers[j]
        cutoffs = sorted(spec.cutoff_hours)
        later = [c for c in cutoffs if c > obs.hour_of_day]
        next_cut = hour + ((later[0] if later else cutoffs[0] + HOURS_PER_DAY) - obs.hour_of_day)
        lands = arrival_hour(self.world, shock, j, hour)
        lands_next = max(arrival_hour(self.world, shock, j, next_cut), lands)
        if lands == hour + spec.lead_time_hours and lands_next == next_cut + spec.lead_time_hours:
            return base  # this order and the next land on schedule: the incumbent decides
        out = base.copy()
        factor = self.tables.factors[:, part_of_day(obs.hour_of_day)]
        for item in np.nonzero(obs.deciding & (self.supplier_of == j))[0]:
            life = int(scenario.shelf_life[item])
            until = min(lands_next, lands + life)
            cover = self._demand(week_hour, hour, lands, until, int(item))
            ready = self._projected(obs, r, int(item), week_hour, hour, lands, scenario)
            target = int(np.ceil(float(factor[item]) * float(self.response[item]) * cover))
            out[item] = max(0, target - ready)
        return out

    def _demand(self, week_hour: int, hour: int, start: int, stop: int, item: int) -> float:
        if stop <= start:
            return 0.0
        a = week_hour + (start - hour)
        b = week_hour + (stop - hour)
        return float(self.cumulative[b, item] - self.cumulative[a, item])

    def _projected(
        self,
        obs: StoreObservation,
        r: int,
        item: int,
        week_hour: int,
        hour: int,
        lands: int,
        scenario: Scenario,
    ) -> int:
        """Units on hand at ``lands``: batches depleted oldest first by mean demand, those expiring
        before it dropped, plus open orders landing before it."""
        consumed = 0.0
        left = 0.0
        for b in range(obs.on_hand.shape[2]):
            qty = float(obs.on_hand[r, item, b])
            if qty <= 0.0:
                continue
            expires = hour + int(obs.hours_to_expiry[r, item, b])
            demand = self._demand(week_hour, hour, hour, min(expires, lands), item)
            used = min(qty, max(0.0, demand - consumed))
            consumed += used
            if expires > lands:
                left += qty - used
        j = int(scenario.shock.supplier)
        for k in range(obs.open_qty.shape[2]):
            qty = int(obs.open_qty[r, item, k])
            if qty <= 0:
                continue
            placed = hour - int(obs.open_age_hours[r, item, k])
            if arrival_hour(self.world, scenario.shock, j, placed) <= lands:
                left += qty
        return int(np.floor(left))


class Guarded:
    """A challenger whose every quantity passes the guard against an incumbent on the same state."""

    def __init__(self, challenger: ShockOracle, incumbent: Incumbent) -> None:
        self.challenger = challenger
        self.incumbent = incumbent
        self.decisions = 0
        self.clipped = 0

    def start(self, replicates: int) -> None:
        self.challenger.start(replicates)
        self.incumbent.start(replicates)
        self.decisions = 0
        self.clipped = 0

    def decide(self, obs: StoreObservation) -> I64:
        wanted = self.challenger.decide(obs)
        base = self.incumbent.decide(obs)
        allowed = guard(wanted, base)
        mask = np.broadcast_to(obs.deciding[None, :], wanted.shape)
        self.decisions += int(mask.sum())
        self.clipped += int(((allowed != wanted) & mask).sum())
        return allowed


def _single(obs: StoreObservation, r: int) -> StoreObservation:
    import dataclasses

    return dataclasses.replace(
        obs,
        on_hand=obs.on_hand[r : r + 1],
        hours_to_expiry=obs.hours_to_expiry[r : r + 1],
        open_qty=obs.open_qty[r : r + 1],
        open_age_hours=obs.open_age_hours[r : r + 1],
        landed_lead_hours=obs.landed_lead_hours[r : r + 1],
        sales=obs.sales[r : r + 1],
        receipts=obs.receipts[r : r + 1],
    )
