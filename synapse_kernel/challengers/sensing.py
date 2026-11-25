"""The Demand Prophet's job: today's demand level, sensed from today's sales, exactly.

Each day of the release world multiplies every item's mean demand by a store factor and an item
factor, independent draws from the two 16-point tables the world declares (cell N's parameters, so
allowed construction inputs). A day's sales therefore tell the rest of that day's demand, and
nothing about tomorrow's. Before the order, this component computes, per item, the posterior mean of
today's level ``c = f g`` given today's remembered hours
(:class:`~synapse_kernel.challengers.history.History`): an exact hour contributes a Poisson
likelihood at mean ``mu_h c``, a censored hour the probability that demand reached its sales, an
unobserved hour nothing. The prior is the declared 16 x 16 grid, each point weighing the same.

The arithmetic is exact (:mod:`~synapse_kernel.challengers.exact`): the exact hours' likelihood is
taken relative to its maximum, as ``(y e^(1-y))^S`` with ``y = c / (S/M)``, ``S`` their sales and
``M`` their mean, so nothing overflows; a censored hour's tail is one minus a running sum of the
Poisson probabilities.

:class:`AdjustedIncumbent` then runs I2's rule (PREREG-1 section 3) with its mean demand over any
window from now scaled: by ``today`` over the hours left today, by ``later`` after; with both 1 it
gives the incumbent's own orders to the bit (a test).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
import numpy.typing as npt

from synapse_kernel.challengers.exact import (
    exp_neg_clamped,
    exp_neg_live,
    exp_pos,
    ipow,
    isum,
    seq_sum,
)
from synapse_kernel.challengers.history import CENSORED, EXACT
from synapse_kernel.release.incumbent import Incumbent, part_of_day
from synapse_kernel.release.world import HOURS_PER_DAY, HOURS_PER_WEEK

if TYPE_CHECKING:
    from synapse_kernel.challengers.history import History
    from synapse_kernel.release.incumbent import IncumbentTables
    from synapse_kernel.release.observation import StoreObservation
    from synapse_kernel.release.world import ReleaseWorld

__all__ = [
    "AdjustedIncumbent",
    "Sensing",
    "declared_means",
    "level_grid",
    "poisson_tail",
    "posterior_level",
    "relative_likelihood",
]

F64 = npt.NDArray[np.float64]
I64 = npt.NDArray[np.int64]


def declared_means(world: ReleaseWorld) -> F64:
    """Declared mean demand per hour of the week and item, ``(168, items)`` (no day factor)."""
    out = np.empty((HOURS_PER_WEEK, len(world.items)), dtype=np.float64)
    for i, item in enumerate(world.items):
        profile = np.asarray(world.profiles[item.profile], dtype=np.float64)
        out[:, i] = (item.rate_per_day / HOURS_PER_DAY) * profile
    return out


def level_grid(world: ReleaseWorld) -> F64:
    """Every store factor times every item factor: the prior's 256 equally weighted points."""
    store = np.asarray(world.day_store_factors, dtype=np.float64)
    item = np.asarray(world.day_item_factors, dtype=np.float64)
    out: F64 = (store[:, None] * item[None, :]).reshape(-1)
    return out


def relative_likelihood(grid: F64, sold: I64, mean: F64) -> F64:
    """``c^S e^(-c M)`` over the grid, divided by its value at ``S/M``: shape ``(R, I, grid)``."""
    s = sold.astype(np.float64)[:, :, None]
    m = mean[:, :, None]
    c = grid[None, None, :]
    y = np.where(s > 0, c * m / np.where(s > 0, s, 1.0), 1.0)
    # y e^(1-y), exactly: e^(1-y) is exp_pos below 1, exp_neg above it.
    one_minus = 1.0 - y
    grow = np.where(one_minus >= 0, exp_pos(np.maximum(one_minus, 0.0)), 1.0)
    shrink = np.where(one_minus < 0, exp_neg_clamped(np.maximum(-one_minus, 0.0)), 1.0)
    z = y * grow * shrink
    with_sales = ipow(z, np.broadcast_to(sold[:, :, None], z.shape))
    lowest = float(grid.min())
    no_sales = exp_neg_clamped((c - lowest) * m)
    out: F64 = np.where(s > 0, with_sales, no_sales)
    return out


def poisson_tail(mean: F64, sold: I64) -> F64:
    """``P(D >= sold)`` for Poisson ``D`` of each mean: ``mean`` is ``(n, grid)``, ``sold``
    ``(n,)``.

    One minus a running sum of the probabilities ``e^-mean mean^k / k!`` below ``sold``.
    """
    top = int(sold.max()) if sold.size else 0
    term = exp_neg_live(mean)
    below = np.zeros(mean.shape, dtype=np.float64)
    for k in range(top):
        below = below + np.where(k < sold[:, None], term, 0.0)
        term = term * mean / (k + 1)
    out: F64 = np.maximum(0.0, 1.0 - below)
    return out


def apply_censored(
    weight: F64, mu: F64, sales: I64, censored: npt.NDArray[np.bool_], grid: F64
) -> F64:
    """Multiply into ``weight`` (``(R, I', grid)``) each censored hour's ``P(D >= sales)``.

    ``mu`` is ``(H, I')``, ``sales`` and ``censored`` ``(H, R, I')``. Only the censored hours are
    computed, and they are multiplied in a fixed order (``np.multiply.at`` is unbuffered and goes in
    index order), so the result has the same bits everywhere.
    """
    h, r, i = np.nonzero(censored)
    if h.size == 0:
        return weight
    lam = mu[h, i][:, None] * grid[None, :]
    tails = poisson_tail(lam, sales[h, r, i])
    out = weight.copy()
    np.multiply.at(out, (r, i), tails)
    return out


def posterior_level(
    history: History,
    means: F64,
    grid: F64,
    now_week: int,
    hours: int,
    items: I64 | None = None,
) -> F64:
    """Posterior mean of the level over the newest ``hours`` remembered hours, per replicate and
    item; with ``items``, only those items are computed and the others get the prior's mean.

    ``means`` is the declared mean per hour of the week and item; ``grid`` the prior's points. With
    no exact or censored hour the posterior is the prior, whose mean the caller gets back.
    """
    r, i = history.replicates, history.items
    prior = float(seq_sum(grid)) / grid.size
    out: F64 = np.full((r, i), prior)
    sales, state, week_hour = history.window(hours)
    if week_hour.size == 0:
        return out
    cols = np.arange(i) if items is None else np.asarray(items, dtype=np.int64)
    if cols.size == 0:
        return out
    mu = means[week_hour][:, cols]  # (H, I')
    sales = sales[:, :, cols]
    state = state[:, :, cols]
    exact = state == EXACT
    sold = isum(np.where(exact, sales, 0), axis=0)  # (R, I')
    mean = seq_sum(np.where(exact, mu[:, None, :], 0.0), axis=0)  # (R, I')
    weight = apply_censored(
        relative_likelihood(grid, sold, mean), mu, sales, state == CENSORED, grid
    )
    total = seq_sum(weight, axis=-1)
    first = seq_sum(weight * grid[None, None, :], axis=-1)
    out[:, cols] = np.where(total > 0, first / np.where(total > 0, total, 1.0), prior)
    return out


class AdjustedIncumbent:
    """I2's rule with its mean demand over a window from now scaled per replicate and item.

    Demand over the next ``H`` hours is ``later * base(H) + (today - later) * base(min(H, left
    today))``, ``base`` the incumbent's own mean, wherever the rule depletes batches (I2's expected
    outdating); the order-up-to level is ``k * later * base(H) + (today - later) * post``, ``post``
    the base demand of today's hours after this order lands: a persistent factor scales the level,
    safety stock included; a same-day revision shifts it one for one, and only over the hours the
    order can serve, since under lost sales demand before it lands is served from stock or lost
    (truth session 6: with the true day level this form gains 9.3 in N, the plain one 6.7). Every
    other step is the incumbent's, in its order of operations, so ``today = later = 1`` gives its
    orders to the bit.
    """

    def __init__(self, world: ReleaseWorld, tables: IncumbentTables) -> None:
        self.inner = Incumbent(world, tables)
        self.items = np.arange(len(world.items))
        names = [s.name for s in world.suppliers]
        lead = np.array([s.lead_time_hours for s in world.suppliers], dtype=np.int64)
        self.lead = lead[[names.index(item.supplier) for item in world.items]]

    def _base(self, week_hour: int, hours: I64) -> F64:
        cum = self.inner.cumulative
        out: F64 = cum[week_hour + hours, self.items] - cum[week_hour, self.items]
        return out

    def segments(self, obs: StoreObservation) -> tuple[F64, F64, F64]:
        """The base demand of each deciding item's protection window from now, ``(1, I)`` each:
        today's hours, tomorrow's, and the rest."""
        week_hour = obs.day_of_week * HOURS_PER_DAY + obs.hour_of_day
        left = HOURS_PER_DAY - obs.hour_of_day
        hours = np.where(obs.deciding, self.inner.protection[:, obs.hour_of_day], 0)[None, :]
        whole = self._base(week_hour, hours)
        today = self._base(week_hour, np.minimum(hours, left))
        tomorrow = self._base(week_hour, np.minimum(hours, left + HOURS_PER_DAY)) - today
        return today, tomorrow, whole - today - tomorrow

    def _demand(self, week_hour: int, hours: I64, left: int, today: F64, later: F64) -> F64:
        whole = self._base(week_hour, hours)
        part = self._base(week_hour, np.minimum(hours, left))
        out: F64 = later * whole + (today - later) * part
        return out

    def decide(
        self,
        obs: StoreObservation,
        today: F64,
        later: F64,
        factors: F64 | None = None,
    ) -> I64:
        """Orders per replicate and item; ``factors`` replaces the incumbent's own ``k`` if
        given."""
        inner = self.inner
        week_hour = obs.day_of_week * HOURS_PER_DAY + obs.hour_of_day
        left = HOURS_PER_DAY - obs.hour_of_day
        hours = np.where(obs.deciding, inner.protection[:, obs.hour_of_day], 0)
        whole = self._base(week_hour, hours[None, :])
        # Today's hours after this order lands: before it lands, extra demand is served from stock
        # on hand or lost, so only the hours after arrival need covering (lost sales).
        today_end = np.minimum(hours, left)
        landed = np.minimum(np.minimum(self.lead, hours), left)
        post = self._base(week_hour, today_end[None, :]) - self._base(week_hour, landed[None, :])
        table = inner.tables.factors if factors is None else factors
        k = table[:, part_of_day(obs.hour_of_day)]
        # A persistent factor (``later``) scales the whole level, safety included; a same-day
        # revision (``today - later``) shifts it one for one over today's hours after arrival.
        level = k[None, :] * later * whole + (today - later) * post
        target = np.where(obs.deciding[None, :], np.ceil(level), 0.0)
        position = isum(obs.on_hand, axis=-1) + isum(obs.open_qty, axis=-1)
        if inner.tables.waste_aware:
            raw = np.ceil(target - position + self._outdating(obs, week_hour, left, today, later))
            orders = np.maximum(0, raw).astype(np.int64)
        else:
            orders = np.maximum(0, target - position).astype(np.int64)
        out: I64 = np.where(obs.deciding[None, :], orders, 0)
        return out

    def _outdating(
        self, obs: StoreObservation, week_hour: int, left: int, today: F64, later: F64
    ) -> F64:
        qty = obs.on_hand.astype(np.float64)
        until = np.maximum(obs.hours_to_expiry, 0)
        consumed = np.zeros(qty.shape[:2])
        outdating = np.zeros(qty.shape[:2])
        for b in range(qty.shape[2]):
            demand = self._demand(week_hour, until[:, :, b], left, today, later)
            used = np.minimum(qty[:, :, b], np.maximum(0.0, demand - consumed))
            consumed = consumed + used
            outdating = outdating + (qty[:, :, b] - used)
        return outdating


class Sensing:
    """The sensing challenger alone: the lane's I2 with today's level sensed, later days at 1."""

    name = "sensing"

    def __init__(self, world: ReleaseWorld, tables: IncumbentTables) -> None:
        self.rule = AdjustedIncumbent(world, tables)
        self.means = declared_means(world)
        self.grid = level_grid(world)

    def level(self, history: History, obs: StoreObservation) -> F64:
        """Today's sensed level per replicate and item."""
        now_week = obs.day_of_week * HOURS_PER_DAY + obs.hour_of_day
        deciding = np.nonzero(obs.deciding)[0]
        return posterior_level(
            history, self.means, self.grid, now_week, history.hours_today(now_week), deciding
        )

    def orders(self, history: History, obs: StoreObservation, factors: F64 | None = None) -> I64:
        today = self.level(history, obs)
        return self.rule.decide(obs, today, np.ones_like(today), factors)
