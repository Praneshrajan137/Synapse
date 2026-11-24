"""The release world's engine: one dark store, hour by hour, stock held in batches that age.

Each hour ``h`` of a replicate, in this order:

1. **Expiry.** Batches whose expiry is at or before ``h`` are discarded; their units are waste (W).
2. **Receipts.** Orders landing at ``h`` arrive as one new batch per item, expiring ``shelf_life``
   hours later (the shelf life left at receipt; cell L halves it).
3. **Decision.** At a supplier's order cut-off, the policy sees the store
   (:class:`~synapse_kernel.release.observation.StoreObservation`) and orders whole units of that
   supplier's items, which land when the scenario says (normally the next scheduled delivery).
4. **Sales.** Units demanded this hour are sold from stock, oldest batch first (first in, first
   out); demand beyond the stock is lost (L).
5. **Holding.** On-hand units over the hour by the trapezoid: ``(start + end) / 2`` unit-hours,
   kept doubled (H2) so the accounting stays in integers.

Only hours from the start of measured day 1 are counted (PREREG-1 section 1: the warm-up is never
priced). The engine draws nothing: every random quantity is in the
:class:`~synapse_kernel.release.scenario.Scenario` it is given, built before it runs. Replicates of
one cell run together as the first axis of every array; each replicate's arithmetic is the same
whether it runs alone or in a batch (``tests/kernel/release``).
"""

from __future__ import annotations

import dataclasses
import math
from typing import TYPE_CHECKING, Final, Protocol

import numpy as np
import numpy.typing as npt

from synapse_kernel.release.observation import StoreObservation
from synapse_kernel.release.scenario import arrival_hour, demand_means
from synapse_kernel.release.world import HOURS_PER_DAY

if TYPE_CHECKING:
    from collections.abc import Sequence

    from synapse_kernel.release.scenario import Scenario
    from synapse_kernel.release.world import ReleaseWorld

__all__ = ["OPEN_ORDER_SLOTS", "Outcome", "ReleasePolicy", "initial_stock", "observe", "run"]

I64 = npt.NDArray[np.int64]
#: Expiry hour of an empty batch slot: later than any run.
_NO_EXPIRY: Final[int] = 1 << 40
#: Open orders an item may have at once; a run that needs more is refused, not truncated.
OPEN_ORDER_SLOTS: Final[int] = 24


class ReleasePolicy(Protocol):
    """A decision rule for the release world, run on a batch of replicates of one cell."""

    def start(self, replicates: int) -> None:
        """Forget everything: a new batch of ``replicates`` replicates begins."""
        ...

    def decide(self, obs: StoreObservation) -> I64:
        """Whole units to order per replicate and item, shape ``(replicates, items)``.

        Only the items ``obs.deciding`` marks may be ordered now; every other entry must be 0.
        """
        ...


@dataclasses.dataclass(frozen=True)
class Outcome:
    """Per replicate and item, over the measured days (integers), plus the end state."""

    demanded: I64
    sold: I64
    lost: I64
    wasted: I64
    holding2: I64
    """Twice the on-hand unit-hours (trapezoid per hour)."""
    received: I64
    end_on_hand: I64
    end_on_order: I64
    received_all: I64
    """Units received over the whole run, warm-up included (for conservation)."""
    wasted_all: I64
    sold_all: I64
    initial: I64


def initial_stock(world: ReleaseWorld) -> I64:
    """Per item, the ceiling of mean demand over its supplier's lead time plus review period.

    PREREG-1 section 1: on hand at age zero, the ceiling of the mean demand over the nominal
    protection interval, counted from hour 0 (Monday 00:00), nothing on order.
    """
    week = demand_means(world)
    suppliers = world.supplier_by_name
    out = np.empty(len(world.items), dtype=np.int64)
    for i, item in enumerate(world.items):
        spec = suppliers[item.supplier]
        hours = spec.lead_time_hours + spec.review_hours
        total = math.fsum(float(week[h % week.shape[0], i]) for h in range(hours))
        out[i] = math.ceil(total)
    return out


def _batch_slots(world: ReleaseWorld, shelf_life: I64) -> int:
    """The most batches an item can hold at once: deliveries within its shelf life, plus slack."""
    deliveries = max(len(s.delivery_hours) for s in world.suppliers)
    longest = int(shelf_life.max())
    return deliveries * (math.ceil(longest / HOURS_PER_DAY) + 1) + 4


def run(world: ReleaseWorld, scenarios: Sequence[Scenario], policy: ReleasePolicy) -> Outcome:
    """Run ``policy`` on every scenario (one cell, any seeds) and return the measured outcome.

    Raises:
        ValueError: Scenarios of different cells, a policy order that is negative, not whole, of
            the wrong shape or for an item not taking orders, or an item exceeding its batch or
            open-order slots.
    """
    if not scenarios:
        raise ValueError("no scenario to run")
    cells = {s.cell for s in scenarios}
    if len(cells) != 1:
        raise ValueError(f"a batch runs one cell, got {sorted(cells)}")
    reps = len(scenarios)
    items = len(world.items)
    horizon = world.horizon_hours
    start_measure = world.measured_start_hour
    shelf = scenarios[0].shelf_life
    demand = np.stack([s.demand for s in scenarios])  # (R, H, I)
    if demand.shape != (reps, horizon, items):
        raise ValueError(f"scenario demand has shape {demand.shape[1:]}, not {(horizon, items)}")

    slots = _batch_slots(world, shelf)
    qty = np.zeros((reps, items, slots), dtype=np.int64)
    expiry = np.full((reps, items, slots), _NO_EXPIRY, dtype=np.int64)
    batches = np.zeros((reps, items), dtype=np.int64)
    initial = initial_stock(world)
    qty[:, :, 0] = initial
    expiry[:, :, 0] = shelf
    batches[:, :] = (initial > 0).astype(np.int64)
    expiry[:, :, 0] = np.where(initial > 0, shelf, _NO_EXPIRY)

    arrivals = np.zeros((reps, items, horizon), dtype=np.int64)
    open_qty = np.zeros((reps, items, OPEN_ORDER_SLOTS), dtype=np.int64)
    open_placed = np.full((reps, items, OPEN_ORDER_SLOTS), -1, dtype=np.int64)
    open_due = np.full((reps, items, OPEN_ORDER_SLOTS), -1, dtype=np.int64)
    landed_lead = np.full((reps, items, OPEN_ORDER_SLOTS), -1, dtype=np.int64)

    sales_log = np.zeros((reps, horizon, items), dtype=np.int32)
    receipts_log = np.zeros((reps, horizon, items), dtype=np.int32)
    totals = {
        name: np.zeros((reps, items), dtype=np.int64)
        for name in (
            "demanded",
            "sold",
            "lost",
            "wasted",
            "holding2",
            "received",
            "received_all",
            "wasted_all",
            "sold_all",
        )
    }
    supplier_index = {s.name: j for j, s in enumerate(world.suppliers)}
    item_supplier = np.array([supplier_index[item.supplier] for item in world.items])
    cutoffs = {j: set(s.cutoff_hours) for j, s in enumerate(world.suppliers)}
    policy.start(reps)
    sales_from = 0  # sales of the decision hour come after it: shown at the next call
    receipts_from = 0  # receipts of the decision hour come before it: shown at that call
    # Slots past ``active`` are empty in every row: the hourly work runs on live slots only.
    active = int(batches.max())

    for hour in range(horizon):
        measured = hour >= start_measure
        # 1. expiry: a row's batches are in receipt order, which is expiry order (one shelf life
        # per item), so only the front batch can be due; drop it, as often as one is.
        while active > 0:
            front = expiry[:, :, 0] <= hour
            if not front.any():
                break
            waste = np.where(front, qty[:, :, 0], 0)
            totals["wasted_all"] += waste
            if measured:
                totals["wasted"] += waste
            expiring = front[:, :, None]
            live_q = qty[:, :, :active]
            live_x = expiry[:, :, :active]
            shifted_q = np.concatenate([live_q[:, :, 1:], np.zeros_like(live_q[:, :, :1])], axis=-1)
            shifted_x = np.concatenate(
                [live_x[:, :, 1:], np.full_like(live_x[:, :, :1], _NO_EXPIRY)], axis=-1
            )
            qty[:, :, :active] = np.where(expiring, shifted_q, live_q)
            expiry[:, :, :active] = np.where(expiring, shifted_x, live_x)
            batches = batches - front
            active = int(batches.max())
        # 2. receipts: one new batch per item that receives units this hour.
        landing = arrivals[:, :, hour]
        if landing.any():
            rr, ii = np.nonzero(landing)
            pos = batches[rr, ii]
            if int(pos.max()) >= slots:
                raise ValueError("an item holds more batches than its slots allow")
            qty[rr, ii, pos] = landing[rr, ii]
            expiry[rr, ii, pos] = hour + shelf[ii]
            batches[rr, ii] += 1
            active = int(batches.max())
            receipts_log[:, hour, :] = landing
            totals["received_all"] += landing
            if measured:
                totals["received"] += landing
            due_now = open_due == hour
            landed_lead = np.where(due_now, hour - open_placed, landed_lead)
            open_qty = np.where(due_now, 0, open_qty)
            open_placed = np.where(due_now, -1, open_placed)
            open_due = np.where(due_now, -1, open_due)
        # 3. decision at any supplier's cut-off.
        deciding_suppliers = [j for j, hours in cutoffs.items() if hour % HOURS_PER_DAY in hours]
        if deciding_suppliers:
            deciding = np.isin(item_supplier, deciding_suppliers)
            obs = observe(
                hour,
                deciding,
                sales_log[:, sales_from:hour, :],
                receipts_log[:, receipts_from : hour + 1, :],
                qty[:, :, : max(active, 1)],
                expiry[:, :, : max(active, 1)],
                open_qty,
                open_placed,
                landed_lead,
            )
            orders = np.asarray(policy.decide(obs))
            _check_orders(orders, deciding, reps, items)
            landed_lead = np.full_like(landed_lead, -1)
            sales_from, receipts_from = hour, hour + 1
            for j in deciding_suppliers:
                cols = np.nonzero(item_supplier == j)[0]
                for r, scenario in enumerate(scenarios):
                    due = arrival_hour(world, scenario.shock, j, hour)
                    placed = orders[r, cols]
                    if not placed.any():
                        continue
                    free = np.argmax(open_qty[r, cols, :] == 0, axis=-1)
                    full = open_qty[r, cols, free] != 0
                    if bool((full & (placed > 0)).any()):
                        raise ValueError("an item exceeds its open-order slots")
                    put = placed > 0
                    c, f = cols[put], free[put]
                    open_qty[r, c, f] = placed[put]
                    open_placed[r, c, f] = hour
                    open_due[r, c, f] = due
                    if due < horizon:
                        arrivals[r, cols, due] += placed
        # 4. sales, oldest batch first.
        wanted = demand[:, hour, :]
        live = qty[:, :, :active]
        on_hand_start = live.sum(axis=-1)
        sold = np.minimum(wanted, on_hand_start)
        before = np.cumsum(live, axis=-1) - live
        take = np.clip(sold[:, :, None] - before, 0, live)
        qty[:, :, :active] = live - take
        on_hand_end = on_hand_start - sold
        sales_log[:, hour, :] = sold
        totals["sold_all"] += sold
        if measured:
            totals["demanded"] += wanted
            totals["sold"] += sold
            totals["lost"] += wanted - sold
            totals["holding2"] += on_hand_start + on_hand_end

    return Outcome(
        demanded=totals["demanded"],
        sold=totals["sold"],
        lost=totals["lost"],
        wasted=totals["wasted"],
        holding2=totals["holding2"],
        received=totals["received"],
        end_on_hand=qty.sum(axis=-1),
        end_on_order=open_qty.sum(axis=-1),
        received_all=totals["received_all"],
        wasted_all=totals["wasted_all"],
        sold_all=totals["sold_all"],
        initial=np.broadcast_to(initial, (reps, items)).copy(),
    )


def observe(
    hour: int,
    deciding: npt.NDArray[np.bool_],
    sales: npt.NDArray[np.int32],
    receipts: npt.NDArray[np.int32],
    qty: I64,
    expiry: I64,
    open_qty: I64,
    open_placed: I64,
    landed_lead: I64,
) -> StoreObservation:
    """The observation at ``hour``: every time relative to it, the hour and weekday, nothing else.

    A pure function of the store's state, whose times are absolute hours; adding a whole number of
    weeks to ``hour`` and to every absolute time leaves its output unchanged
    (``tests/kernel/release/test_observation.py``), which is how the day index stays hidden.
    """
    return StoreObservation(
        hour_of_day=hour % HOURS_PER_DAY,
        day_of_week=(hour // HOURS_PER_DAY) % 7,
        deciding=deciding.copy(),
        sales=sales.copy(),
        receipts=receipts.copy(),
        on_hand=qty.copy(),
        hours_to_expiry=np.where(qty > 0, expiry - hour, -1),
        open_qty=open_qty.copy(),
        open_age_hours=np.where(open_placed >= 0, hour - open_placed, -1),
        landed_lead_hours=landed_lead.copy(),
    )


def _check_orders(orders: I64, deciding: npt.NDArray[np.bool_], reps: int, items: int) -> None:
    if orders.shape != (reps, items):
        raise ValueError(f"orders have shape {orders.shape}, not {(reps, items)}")
    if not np.issubdtype(orders.dtype, np.integer):
        raise ValueError("orders are whole units: an integer array")
    if bool((orders < 0).any()):
        raise ValueError("an order is negative")
    if bool((orders[:, ~deciding] != 0).any()):
        raise ValueError("an order for an item whose supplier is not taking orders now")
