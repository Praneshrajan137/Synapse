"""The headroom oracle and the guard: exploratory descriptions for freeze W, never a challenger.

PREREG-1 section 6: before freeze W, an oracle arm told each shock's items, onset, size and duration
runs on the validation seeds, and its mean advantage over the incumbent in each shock cell is
published. The oracle is the cell's selected incumbent version told the shock. It reads the
scenario, which no policy may do: it is a measuring instrument, not a policy. Two rules:

* ``rule="gate"``, the gate's oracle as the session-5 gate (section 7) defines it: the shock is
  inserted into what the incumbent plans against, and the incumbent's own rule decides. In a
  surge, the affected items' mean demand in the shock's hours is times ``u`` wherever the
  incumbent reads it (its order-up-to level and, for I2, its expected outdating), before the order
  is clipped at zero. In a delay or an outage, the shocked supplier's items plan against the
  protection interval as it will actually run: from the decision to the actual arrival of the next
  order, with the pipeline as it will actually land.
* ``rule="informed"``, a better use of the same information, designed on the fixture world after
  the gate's rule lost there (truth log S5-M-22) and repaired after freeze W's attack (S5-D-07): the
  surge enters as ``1 + kappa (u - 1)``; in a delay or an outage an order covers only the demand
  from its own actual arrival to the next order's, given the stock projected to that arrival and
  capped by what can sell before it expires, times ``kappa``. ``kappa`` (``response``) is one
  factor per item, tuned by the sealed search on the cell's tuning seeds.

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

__all__ = ["RULES", "Guarded", "ShockOracle"]

I64 = npt.NDArray[np.int64]
F64 = npt.NDArray[np.float64]
#: The oracle's two rules: the gate's, and the informed variant (module docstring).
RULES = ("gate", "informed")


class ShockOracle(Incumbent):
    """An incumbent version told the shock of each replicate (one scenario per replicate)."""

    def __init__(
        self,
        world: ReleaseWorld,
        tables: IncumbentTables,
        batch: list[Scenario],
        response: npt.NDArray[np.float64] | None = None,
        rule: str = "gate",
    ) -> None:
        super().__init__(world, tables)
        if rule not in RULES:
            raise ValueError(f"rule {rule!r} is not one of {RULES}")
        if rule == "gate" and response is not None:
            raise ValueError("the gate's oracle has no response factor")
        self.rule = rule
        self.world = world
        self.batch = batch
        # kappa per item: scales only the informed part of a decision (1 is the gate's surge).
        self.response = (
            np.ones(len(world.items)) if response is None else np.asarray(response, dtype=float)
        )
        # The table the incumbent's cumulative sums, kept to rebuild it with a surge inserted.
        self.weeks = np.concatenate([tables.mean_table] * 4, axis=0)
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
        shock = scenario.shock
        if shock.kind == "surge":
            return self._surge(one, shock)
        base: I64 = Incumbent.decide(self, one)[0]
        if shock.kind in ("delay", "outage"):
            if self.rule == "gate":
                return self._gate_supply(one, base, scenario)
            return self._supply(obs, r, base, scenario)
        return base

    def _surge(self, one: StoreObservation, shock: Shock) -> I64:
        """The incumbent's own decision, planned against the surged mean demand.

        The cumulative mean demand the incumbent reads is rebuilt with the surged items' mean in
        the shock's hours (``onset <= h < end``, as the scenario draws them) times ``u`` (gate) or
        ``1 + kappa (u - 1)`` (informed), so both the order-up-to level and I2's expected outdating
        see the surge, and the order is clipped at zero only after.
        """
        week_hour = one.day_of_week * HOURS_PER_DAY + one.hour_of_day
        offset = self.hour - week_hour  # the absolute hour of cumulative row x is x + offset
        rows = np.arange(self.weeks.shape[0]) + offset
        surged = (rows >= shock.onset_hour) & (rows < shock.end_hour)
        reach = int(self.protection[:, one.hour_of_day].max())
        if self.tables.waste_aware:
            reach = max(reach, int(one.hours_to_expiry.max()))
        read = (rows >= self.hour) & (rows < self.hour + reach)
        if not bool((surged & read).any()):
            plain: I64 = Incumbent.decide(self, one)[0]
            return plain
        items = np.asarray(shock.items, dtype=np.int64)
        factor = np.ones(len(self.world.items))
        factor[items] = 1.0 + self.response[items] * (shock.size - 1.0)
        weeks = self.weeks.copy()
        weeks[surged] = weeks[surged] * factor[None, :]
        saved = self.cumulative
        self.cumulative = np.concatenate(
            [np.zeros((1, weeks.shape[1])), np.cumsum(weeks, axis=0)], axis=0
        )
        try:
            out: I64 = Incumbent.decide(self, one)[0]
        finally:
            self.cumulative = saved
        return out

    def _gate_supply(self, one: StoreObservation, base: I64, scenario: Scenario) -> I64:
        """The gate's rule for the shocked supplier's items: the incumbent's own decision, with the
        protection interval running from the decision to the next order's actual arrival."""
        shock = scenario.shock
        j = int(shock.supplier)
        items = np.nonzero(one.deciding & (self.supplier_of == j))[0]
        if items.size == 0:
            return base
        spec = self.world.suppliers[j]
        cutoffs = sorted(spec.cutoff_hours)
        later = [c for c in cutoffs if c > one.hour_of_day]
        step = (later[0] if later else cutoffs[0] + HOURS_PER_DAY) - one.hour_of_day
        lands = arrival_hour(self.world, shock, j, self.hour)
        lands_next = max(arrival_hour(self.world, shock, j, self.hour + step), lands)
        week_hour = one.day_of_week * HOURS_PER_DAY + one.hour_of_day
        hours = np.where(one.deciding, self.protection[:, one.hour_of_day], 0)
        hours[items] = lands_next - self.hour
        mu = self._window(week_hour, hours)
        factor = self.tables.factors[:, part_of_day(one.hour_of_day)]
        target: F64 = np.ceil(factor * mu)
        position = (one.on_hand.sum(axis=-1) + one.open_qty.sum(axis=-1))[0]
        if self.tables.waste_aware:
            wanted = np.ceil(target - position + self.expected_outdating(one)[0])
        else:
            wanted = target - position
        out = base.copy()
        out[items] = np.maximum(0, wanted[items]).astype(np.int64)
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
