"""Each replicate's memory, rebuilt exactly from its own observations.

Between two decisions an observation reports hourly sales and receipts; at each decision it reports
the batches on hand with their hours to expiry. Replaying the engine's own order of events within
an hour (expiry, receipts, then sales first in first out) from the batches seen at the previous
decision recovers the stock on hand at the start of every hour since. Each item-hour is then
**exact** (stock was left after the hour's sales, so demand equalled sales), **censored** (the hour
sold out its stock, so demand was at least sales) or **unobserved** (no stock at all). The replay is
checked against the batches the next observation shows; a disagreement is counted in
:attr:`History.mismatches` (the tests require zero) and that item's hours in the window are marked
unobserved rather than guessed.

Every time is kept relative to the current decision, never as a clock: the memory holds at most
:data:`WINDOW_HOURS` hours, so no component built on it can tell the last measured day from the same
weekday a week earlier (truth session 6, gate item 10). Each item's shelf life at receipt is learned
from any batch whose receipt was observed: its hours to expiry plus the hours since that receipt.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

import numpy as np
import numpy.typing as npt

from synapse_kernel.challengers.exact import isum

if TYPE_CHECKING:
    from synapse_kernel.release.observation import StoreObservation

__all__ = ["EXACT", "CENSORED", "UNOBSERVED", "WINDOW_HOURS", "History"]

I64 = npt.NDArray[np.int64]
#: The longest memory any component keeps, in hours (gate item 10: below (warm-up - 1) x 24 in both
#: worlds, so the start of a replicate is never in view on its last measured days).
WINDOW_HOURS: Final[int] = 72
EXACT: Final[int] = 0
CENSORED: Final[int] = 1
UNOBSERVED: Final[int] = 2
_NONE: Final[int] = -1


class History:
    """The last :data:`WINDOW_HOURS` hours of every replicate and item, newest last."""

    def __init__(self, items: int, declared_life: I64) -> None:
        self.items = items
        self.declared_life = np.asarray(declared_life, dtype=np.int64).copy()
        self.replicates = 0
        self.mismatches = 0
        self._started = False

    def start(self, replicates: int) -> None:
        """Forget everything: a new replicate (or batch of replicates) begins."""
        r, i = replicates, self.items
        self.replicates = replicates
        self.mismatches = 0
        self._started = False
        self.qty = np.zeros((r, i, 1), dtype=np.int64)
        self.hte = np.full((r, i, 1), _NONE, dtype=np.int64)
        self.life = np.full((r, i), _NONE, dtype=np.int64)
        self.sales = np.zeros((0, r, i), dtype=np.int64)
        self.state = np.zeros((0, r, i), dtype=np.int8)
        self.week_hour = np.zeros(0, dtype=np.int64)
        """Hour of the week (0 is Monday 00:00) of each remembered hour, oldest first."""

    # -- the update -------------------------------------------------------------------------------

    def update(self, obs: StoreObservation) -> None:
        """Take in the hours since the previous decision, and the batches seen now."""
        now_week = obs.day_of_week * 24 + obs.hour_of_day
        on_hand = np.asarray(obs.on_hand, dtype=np.int64)
        expiry = np.asarray(obs.hours_to_expiry, dtype=np.int64)
        if not self._started:
            self._started = True
            self._adopt(on_hand, expiry)
            return
        sales = np.asarray(obs.sales, dtype=np.int64)  # (R, L, I): hours [P, t)
        receipts = np.asarray(obs.receipts, dtype=np.int64)  # (R, L, I): hours [P+1, t]
        length = sales.shape[1]
        qty, hte = self.qty.copy(), self.hte.copy()
        new_sales = np.zeros((length, self.replicates, self.items), dtype=np.int64)
        new_state = np.zeros((length, self.replicates, self.items), dtype=np.int8)
        received_at = np.full((self.replicates, self.items), _NONE, dtype=np.int64)
        bad = np.zeros((self.replicates, self.items), dtype=bool)
        for k in range(length):
            if k > 0:
                qty, hte = _expire(qty, hte, k)
                qty, hte = _receive(qty, hte, receipts[:, k - 1, :], k, self._life_now())
                received_at = np.where(receipts[:, k - 1, :] > 0, k, received_at)
            start = isum(qty, axis=-1)
            sold = sales[:, k, :]
            bad |= sold > start
            qty, hte = _compact(_sell(qty, sold), hte)
            end = start - sold
            new_sales[k] = sold
            new_state[k] = np.where(
                start == 0, UNOBSERVED, np.where(end > 0, EXACT, CENSORED)
            ).astype(np.int8)
        qty, hte = _expire(qty, hte, length)
        qty, hte = _receive(qty, hte, receipts[:, length - 1, :], length, self._life_now())
        received_at = np.where(receipts[:, length - 1, :] > 0, length, received_at)
        bad |= ~_same_quantities(qty, on_hand)
        self.mismatches += int(isum(bad.astype(np.int64)))
        new_state = np.where(bad[None, :, :], UNOBSERVED, new_state).astype(np.int8)
        self._learn_life(on_hand, expiry, received_at, length)
        hours = (now_week - length + np.arange(length)) % 168
        self._remember(new_sales, new_state, hours)
        self._adopt(on_hand, expiry)

    # -- what components read ---------------------------------------------------------------------

    def hours_today(self, now_week: int) -> int:
        """How many remembered hours fall on the current day (from its 00:00 up to now)."""
        hour_of_day = now_week % 24
        return min(hour_of_day, self.week_hour.size)

    def window(self, hours: int) -> tuple[I64, npt.NDArray[np.int8], I64]:
        """The newest ``hours`` remembered hours: sales, state and hour of the week."""
        take = min(hours, self.week_hour.size)
        if take == 0:
            empty = np.zeros((0, self.replicates, self.items), dtype=np.int64)
            return empty, np.zeros(empty.shape, dtype=np.int8), np.zeros(0, dtype=np.int64)
        return self.sales[-take:], self.state[-take:], self.week_hour[-take:]

    # -- internals --------------------------------------------------------------------------------

    def _life_now(self) -> I64:
        """Each item's life at receipt: learned where seen, else the declared one."""
        out: I64 = np.where(self.life == _NONE, self.declared_life[None, :], self.life)
        return out

    def _adopt(self, on_hand: I64, expiry: I64) -> None:
        self.qty, self.hte = _compact(on_hand.copy(), expiry.copy())

    def _learn_life(self, on_hand: I64, expiry: I64, received_at: I64, length: int) -> None:
        """Life at receipt of the newest batch, where this window's receipt is still on hand."""
        held = on_hand > 0
        slots = np.arange(on_hand.shape[-1])
        newest = np.where(held, slots, -1).max(axis=-1)  # the last slot still holding units
        has = (received_at != _NONE) & (newest >= 0)
        if not bool(has.any()):
            return
        r, i = np.nonzero(has)
        age = length - received_at[r, i]
        self.life[r, i] = expiry[r, i, newest[r, i]] + age

    def _remember(self, sales: I64, state: npt.NDArray[np.int8], hours: I64) -> None:
        self.sales = np.concatenate([self.sales, sales])[-WINDOW_HOURS:]
        self.state = np.concatenate([self.state, state])[-WINDOW_HOURS:]
        self.week_hour = np.concatenate([self.week_hour, hours])[-WINDOW_HOURS:]


def _expire(qty: I64, hte: I64, k: int) -> tuple[I64, I64]:
    """Drop batches whose expiry is at or before ``k`` hours after the previous decision."""
    gone = (hte != _NONE) & (hte - k <= 0) & (qty > 0)
    if not bool(gone.any()):
        return qty, hte
    keep_q = np.where(gone, 0, qty)
    keep_x = np.where(gone, _NONE, hte)
    return _compact(keep_q, keep_x)


def _receive(qty: I64, hte: I64, landing: I64, k: int, life: I64) -> tuple[I64, I64]:
    """Append one batch per item that receives units, expiring ``life`` hours after ``k``."""
    if not bool((landing > 0).any()):
        return qty, hte
    q = np.concatenate([qty, np.zeros(qty.shape[:2] + (1,), dtype=np.int64)], axis=-1)
    x = np.concatenate([hte, np.full(hte.shape[:2] + (1,), _NONE, dtype=np.int64)], axis=-1)
    count = isum((q > 0).astype(np.int64), axis=-1)
    r, i = np.nonzero(landing > 0)
    q[r, i, count[r, i]] = landing[r, i]
    x[r, i, count[r, i]] = k + life[r, i]
    return q, x


def _sell(qty: I64, sold: I64) -> I64:
    """Take ``sold`` units from the batches, oldest first (the engine's own rule)."""
    before = np.cumsum(qty, axis=-1) - qty
    take = np.clip(sold[:, :, None] - before, 0, qty)
    out: I64 = qty - take
    return out


def _compact(qty: I64, hte: I64) -> tuple[I64, I64]:
    """Move non-empty batches to the front in their order; an empty slot's expiry is none.

    The engine keeps a sold-out batch as an empty slot until it expires; for the replay only the
    batches still holding units matter, in receipt order.
    """
    order = np.argsort(qty == 0, axis=-1, kind="stable")
    q = np.take_along_axis(qty, order, axis=-1)
    x = np.take_along_axis(hte, order, axis=-1)
    return q, np.where(q > 0, x, _NONE)


def _same_quantities(replayed: I64, observed: I64) -> npt.NDArray[np.bool_]:
    """Whether the non-empty batches agree in order and quantity, per replicate and item."""
    rq, _ = _compact(replayed, np.zeros_like(replayed))
    oq, _ = _compact(observed, np.zeros_like(observed))
    width = max(rq.shape[-1], oq.shape[-1])
    rq = np.pad(rq, ((0, 0), (0, 0), (0, width - rq.shape[-1])))
    oq = np.pad(oq, ((0, 0), (0, 0), (0, width - oq.shape[-1])))
    out: npt.NDArray[np.bool_] = (rq == oq).all(axis=-1)
    return out
