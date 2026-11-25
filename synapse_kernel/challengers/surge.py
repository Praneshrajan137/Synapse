"""The Disruption Shield's job for demand: a surge, detected from censored sales, without being
told.

A day's demand level is a fresh draw every day, the store's factor times the item's (independent
across days, from the declared 16-point tables), so one busy day says little about one item; a
surge multiplies the demand of some unknown share of the items for days in a row. This component
tests for a surge the way Xie and Siegmund (Ann. Stat. 41(2), 2013) test many streams for a change
in an unknown subset of them, pooling the evidence of every item:

* per item and calendar day, the likelihood of the day's sales at each of the 16 store levels,
  marginalised over the 16 item levels, under "the item's level is as usual" and under "it is ``m``
  times that" for each ``m`` in a declared grid; exact hours count as Poisson counts, censored
  hours (sold out within the hour) as lower bounds, unobserved hours not at all;
* per day, the store's likelihood ratio for "a share ``p`` of the items is surged": the product
  over items of ``(1 - p) L0 + p mean_m(Lm)`` against the product of ``L0``, both summed over the
  store levels, which the items share (so a busy store day is not read as a surge);
* from an onset day ``k``, the product of the days' ratios since it, averaged over a declared grid
  of shares ``p``; the evidence is the largest over the onsets in memory (a CUSUM in product form).

The store is alarmed when the evidence reaches the threshold, a power of two fitted so the detector,
fed exactly what it sees in operation in cells without a surge, never fires (truth session 6, gate
item 6). While the alarm stands, an item whose own posterior probability of being surged is at
least one half plans its lane's I2 against its mean demand times ``1 + kappa (u_hat - 1)``,
``u_hat`` its posterior mean multiplier and ``kappa`` a factor per item and part of the day (1 until
tuned).

**Memory.** The calendar days complete inside the 72-hour memory, and today so far; the oldest,
partial day is left out. A complete day's likelihoods are a pure function of its own hours, all in
memory while it is used, so they are computed once and kept until the day leaves the memory: a
component started afresh on the same 72 hours computes the same numbers.

**Exactness.** + - x /, comparisons, the kernel's exact ``exp_neg``, integer sums, sums in order,
and products kept as ``(mantissa, exponent)`` (:func:`~synapse_kernel.challengers.exact.
scaled_product`), so no product over 300 items overflows and the bits are the same everywhere. The
multiplier and share grids are declared design choices, wide and generic, not any cell's
parameters.

Truth session 6 records why this replaced the first, per-item design (decision S6-D-06): on the
first development seeds, per-item evidence at a zero-false-alarm threshold found a fifth to a
quarter of surged items, a median of about 40 hours after the onset, and its no-sales days were
normalised per hypothesis, which overstated their evidence.
"""

from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING, Final

import numpy as np
import numpy.typing as npt

from synapse_kernel.challengers.exact import (
    exp_neg_live,
    isum,
    log_pos,
    scaled_float,
    scaled_product,
    scaled_ratio,
    scaled_sum,
    seq_sum,
)
from synapse_kernel.challengers.history import CENSORED, EXACT, WINDOW_HOURS
from synapse_kernel.challengers.sensing import AdjustedIncumbent, apply_censored, declared_means
from synapse_kernel.release.incumbent import part_of_day
from synapse_kernel.release.world import HOURS_PER_DAY

if TYPE_CHECKING:
    from synapse_kernel.challengers.history import History
    from synapse_kernel.release.incumbent import IncumbentTables
    from synapse_kernel.release.observation import StoreObservation
    from synapse_kernel.release.world import ReleaseWorld

__all__ = [
    "ATTRIBUTE_AT",
    "CAP_LOG2",
    "ENDS_PER_DAY",
    "FRACTIONS",
    "MULTIPLIERS",
    "PLANS",
    "SurgeCalibration",
    "SurgeDetector",
    "SurgeResponse",
    "SurgeState",
    "day_labels",
]

F64 = npt.NDArray[np.float64]
I64 = npt.NDArray[np.int64]
Bools = npt.NDArray[np.bool_]

#: The declared multipliers a surged item's demand may take (a design choice, not a cell's).
MULTIPLIERS: Final[tuple[float, ...]] = (1.25, 1.5, 2.0, 2.5, 3.0, 4.0)
#: The declared shares of surged items the store's test averages over (four: a division by 4).
FRACTIONS: Final[tuple[float, ...]] = (0.0625, 0.125, 0.25, 0.5)
#: The store's evidence is carried up to ``2**CAP_LOG2``, far above any threshold.
CAP_LOG2: Final[int] = 1000
#: An item's own ratios are carried up to ``2**256``.
ITEM_CAP: Final[float] = 2.0**256
#: An item is planned as surged once its posterior probability of being so today reaches this.
ATTRIBUTE_AT: Final[float] = 0.5
#: The declared chance that a surge ends at a midnight it reaches (a design choice, not a cell's).
ENDS_PER_DAY: Final[float] = 0.5
#: Expectation-maximisation steps for the share of surged items.
SHARE_STEPS: Final[int] = 8
#: How a surged item plans: today's hours only, or the whole window weighted by the hazard.
PLANS: Final[tuple[str, ...]] = ("today", "ahead")
_HYPOTHESES: Final[int] = 1 + len(MULTIPLIERS)


def day_labels(week_hour: I64) -> I64:
    """For hours in order, the calendar day each falls on, counted from the oldest (0, 1, ...)."""
    starts = (week_hour % HOURS_PER_DAY == 0).astype(np.int64)
    if starts.size:
        starts[0] = 0
    out: I64 = np.cumsum(starts)
    return out


def likelihood(levels: F64, log_levels: F64, sold: I64, mean: F64) -> F64:
    """``c^S e^(-cM)`` at every level ``c``, over a constant per item and day: ``(R, I, levels)``.

    With sales, the constant is the value at ``c = S/M``, so ``e^(-S (y - 1 - ln y))`` with ``y =
    cM/S``, at most 1; without, it is 1, so ``e^(-cM)``. Either constant is the same for every level
    and hypothesis, so ratios between hypotheses are exact. ``log_levels`` is ``ln c``
    (:func:`~synapse_kernel.challengers.exact.log_pos`); each branch is computed only where it
    applies.
    """
    r, i = sold.shape
    out: F64 = np.empty((r, i, levels.size), dtype=np.float64)
    with_sales = sold > 0
    rows, cols = np.nonzero(with_sales)
    if rows.size:
        s = sold[rows, cols].astype(np.float64)[:, None]
        a = mean[rows, cols][:, None] / s
        gap = levels[None, :] * a - 1.0 - (log_levels[None, :] + log_pos(a))
        out[rows, cols] = exp_neg_live(np.maximum(s * gap, 0.0))
    rows, cols = np.nonzero(~with_sales)
    if rows.size:
        out[rows, cols] = exp_neg_live(levels[None, :] * mean[rows, cols][:, None])
    return out


def _ratio(top: F64, base: F64) -> F64:
    """``top / base``, with ``x / 0`` as :data:`ITEM_CAP` for ``x > 0`` and 1 for ``x = 0``."""
    live = base > 0
    out: F64 = np.where(live, top / np.where(live, base, 1.0), np.where(top > 0, ITEM_CAP, 1.0))
    return out


@dataclasses.dataclass(frozen=True)
class SurgeState:
    """The detector's reading at one decision, per replicate (and item)."""

    evidence: F64
    """The store's evidence for a surge, ``(R,)``, capped at ``2**CAP_LOG2``."""
    prob: F64
    """Each item's posterior probability of being surged today, ``(R, I)``; 0 where not asked."""
    size: F64
    """Each item's posterior mean multiplier of today's demand, ``(R, I)``; 1 where not asked."""


class SurgeDetector:
    """The store's evidence for a surge and each item's share in it, from the 72-hour memory."""

    def __init__(self, world: ReleaseWorld) -> None:
        self.means = declared_means(world)
        store = np.asarray(world.day_store_factors, dtype=np.float64)
        item = np.asarray(world.day_item_factors, dtype=np.float64)
        self.store_points = int(store.size)
        self.item_points = int(item.size)
        base = (store[:, None] * item[None, :]).reshape(-1)
        multipliers = np.asarray((1.0, *MULTIPLIERS), dtype=np.float64)
        self.levels: F64 = (multipliers[:, None] * base[None, :]).reshape(-1)
        self.log_levels: F64 = log_pos(self.levels)
        self.sizes: F64 = np.asarray(MULTIPLIERS, dtype=np.float64)
        self.days: dict[int, F64] = {}

    def reset(self) -> None:
        """Forget every kept day (a new batch of replicates)."""
        self.days = {}

    def day_terms(self, sales: I64, state: npt.NDArray[np.int8], mu: F64) -> F64:
        """One day's likelihoods, ``(R, I, 1 + len(MULTIPLIERS), store points)``."""
        exact = state == EXACT
        sold = isum(np.where(exact, sales, 0), axis=0)
        mean = seq_sum(np.where(exact, mu[:, None, :], 0.0), axis=0)
        weight = apply_censored(
            likelihood(self.levels, self.log_levels, sold, mean),
            mu,
            sales,
            state == CENSORED,
            self.levels,
        )
        r, i = sold.shape
        shaped = weight.reshape(r, i, _HYPOTHESES, self.store_points, self.item_points)
        out: F64 = seq_sum(shaped, axis=-1)
        return out

    def terms(self, history: History) -> list[F64]:
        """The likelihoods of every day in scope, oldest first; complete days are kept."""
        sales, state, week_hour = history.window(WINDOW_HOURS)
        labels = day_labels(week_hour)
        last = int(labels.max())
        kept: dict[int, F64] = {}
        out: list[F64] = []
        for d in range(last + 1):
            on = labels == d
            complete = int(np.count_nonzero(on)) == HOURS_PER_DAY
            if not complete and d != last:
                continue  # the oldest day, partly forgotten
            hours = week_hour[on]
            key = int(hours[0]) // HOURS_PER_DAY
            found = self.days.get(key) if complete else None
            day = (
                found
                if found is not None
                else self.day_terms(sales[on], state[on], self.means[hours])
            )
            if complete:
                kept[key] = day
            out.append(day)
        self.days = kept
        return out

    def assess(self, history: History, items: I64 | None = None) -> SurgeState:
        """The store's evidence; with ``items``, those items' posteriors too."""
        r, i = history.replicates, history.items
        prob = np.zeros((r, i), dtype=np.float64)
        size = np.ones((r, i), dtype=np.float64)
        if history.window(WINDOW_HOURS)[2].size == 0:
            return SurgeState(np.ones(r, dtype=np.float64), prob, size)
        terms = self.terms(history)
        days, shares = len(terms), len(FRACTIONS)
        day_m = np.zeros((days, shares, r), dtype=np.float64)
        day_e = np.zeros((days, shares, r), dtype=np.int64)
        level_m: list[list[F64]] = []  # per day and share: the product over items, per store level
        level_e: list[list[I64]] = []
        for t, day in enumerate(terms):
            null = day[:, :, 0, :]
            alt = seq_sum(np.moveaxis(day[:, :, 1:, :], 2, -1), axis=-1) / len(MULTIPLIERS)
            den_m, den_e = scaled_sum(*scaled_product(null, axis=1), axis=-1)
            per_m: list[F64] = []
            per_e: list[I64] = []
            for j, p in enumerate(FRACTIONS):
                sm, se = scaled_product((1.0 - p) * null + p * alt, axis=1)
                per_m.append(sm)
                per_e.append(se)
                num_m, num_e = scaled_sum(sm, se, axis=-1)
                day_m[t, j], day_e[t, j] = scaled_ratio(num_m, num_e, den_m, den_e, CAP_LOG2)
            level_m.append(per_m)
            level_e.append(per_e)
        # From each onset day k to today: the product of the days' ratios, per share.
        on_m = np.zeros((days, shares, r), dtype=np.float64)
        on_e = np.zeros((days, shares, r), dtype=np.int64)
        acc_m = np.ones((shares, r), dtype=np.float64)
        acc_e = np.zeros((shares, r), dtype=np.int64)
        for t in range(days - 1, -1, -1):
            acc_m, shift = np.frexp(acc_m * day_m[t])
            acc_e = np.where(acc_m == 0.0, 0, np.minimum(acc_e + day_e[t] + shift, CAP_LOG2 + 1))
            on_m[t], on_e[t] = acc_m, acc_e
        mixed_m, mixed_e = scaled_sum(on_m, on_e, axis=1)  # over shares: (days, R)
        mixed = scaled_float(mixed_m, mixed_e - 2, CAP_LOG2)  # the mean of 4 shares, exactly
        onset = np.argmax(mixed, axis=0)  # (R,): the oldest onset among the largest
        rows = np.arange(r)
        evidence: F64 = mixed[onset, rows]
        cols = np.asarray([] if items is None else items, dtype=np.int64)
        if cols.size == 0:
            return SurgeState(evidence, prob, size)
        by_share = scaled_float(on_m, on_e, CAP_LOG2)  # (days, shares, R)
        share = np.argmax(by_share[onset, :, rows], axis=-1)  # (R,)
        # Per item, from the store's onset day to today, a surge that may end at each midnight
        # (hazard ENDS_PER_DAY): a forward filter per multiplier, in ratios to "not surged".
        alive = np.zeros((r, i, len(MULTIPLIERS)), dtype=np.float64)  # surged still, today
        ended = np.zeros((r, i, len(MULTIPLIERS)), dtype=np.float64)  # surged, then ended
        for t, day in enumerate(terms):
            sm = np.stack([level_m[t][j][k] for k, j in enumerate(share.tolist())])  # (R, S)
            se = np.stack([level_e[t][j][k] for k, j in enumerate(share.tolist())])
            # The store levels' posterior that day, given the share: weights in exact proportion.
            top = np.where(sm > 0.0, se, np.iinfo(np.int64).min).max(axis=-1, keepdims=True)
            weight = scaled_float(sm, np.where(sm > 0.0, se - top, 0), CAP_LOG2)
            norm = seq_sum(weight, axis=-1)
            weight = weight / np.where(norm > 0, norm, 1.0)[:, None]
            blend = seq_sum(day * weight[:, None, None, :], axis=-1)  # (R, I, hypotheses)
            step = _ratio(blend[:, :, 1:], blend[:, :, :1])
            first = (t == onset)[:, None, None]
            later = (t > onset)[:, None, None]
            ended = np.where(later, np.minimum(ended + ENDS_PER_DAY * alive, ITEM_CAP), ended)
            carried = np.minimum((1.0 - ENDS_PER_DAY) * alive * step, ITEM_CAP)
            alive = np.where(first, step, np.where(later, carried, alive))
        affected = alive + ended
        item_lr = seq_sum(affected, axis=-1) / len(MULTIPLIERS)  # surged at the onset, or not
        # The share of surged items by expectation-maximisation, from the store's best share.
        q: F64 = np.asarray(FRACTIONS, dtype=np.float64)[share][:, None]
        for _ in range(SHARE_STEPS):
            p_item = q * item_lr / ((1.0 - q) + q * item_lr)
            q = np.clip(seq_sum(p_item, axis=-1) / i, 1.0 / i, 1.0 - 1.0 / i)[:, None]
        p_item = q * item_lr / ((1.0 - q) + q * item_lr)
        alive_total = seq_sum(alive, axis=-1)
        affected_total = seq_sum(affected, axis=-1)
        still = np.where(
            affected_total > 0, alive_total / np.where(affected_total > 0, affected_total, 1.0), 0.0
        )
        now = p_item * still  # the posterior probability that the item is surged today
        if_now = np.where(
            alive_total > 0,
            seq_sum(alive * self.sizes[None, None, :], axis=-1)
            / np.where(alive_total > 0, alive_total, 1.0),
            1.0,
        )
        prob[:, cols] = now[:, cols]
        size[:, cols] = (1.0 + now * (if_now - 1.0))[:, cols]
        return SurgeState(evidence, prob, size)


class SurgeResponse:
    """The surge challenger alone, lane-aware: while the store's alarm stands, its surged items
    plan for the surge."""

    name = "surge"

    def __init__(
        self,
        world: ReleaseWorld,
        normal: IncumbentTables,
        short: IncumbentTables,
        threshold: float,
        kappa: F64 | None = None,
        plan: str = "today",
    ) -> None:
        from synapse_kernel.challengers.shelf import LaneIncumbent

        if plan not in PLANS:
            raise ValueError(f"unknown plan {plan!r}; the plans are {PLANS}")
        self.plan = plan
        self.base = LaneIncumbent(world, normal, short)
        self.detector = SurgeDetector(world)
        self.normal = AdjustedIncumbent(world, normal)
        self.short = AdjustedIncumbent(world, short)
        self.threshold = float(threshold)
        items = len(world.items)
        self.kappa = np.ones((items, 6)) if kappa is None else np.asarray(kappa, dtype=np.float64)
        self.alarms: list[list[int]] = []

    def start(self, replicates: int) -> None:
        self.base.start(replicates)
        self.detector.reset()
        self.alarms = []

    def assess(self, obs: StoreObservation) -> tuple[Bools, F64]:
        """Update the memory and the lane; return each item's surge regime and planned factor."""
        self.base.observe(obs)
        deciding = np.nonzero(obs.deciding)[0]
        state = self.detector.assess(self.base.history, deciding)
        alarm = state.evidence >= self.threshold
        surged: Bools = alarm[:, None] & (state.prob >= ATTRIBUTE_AT) & obs.deciding[None, :]
        # Per replicate: -1 if the store is not alarmed, else the deciding items planned as surged.
        count = np.count_nonzero(surged, axis=1)
        self.alarms.append(np.where(alarm, count, -1).tolist())
        k = self.kappa[:, part_of_day(obs.hour_of_day)]
        factor: F64 = np.where(surged, 1.0 + k[None, :] * (state.size - 1.0), 1.0)
        return surged, factor

    def orders(self, obs: StoreObservation, factor: F64) -> I64:
        """The lane's I2 planning for the surge, by the declared plan.

        ``today``: ``factor`` times the mean over today's hours after the order lands, the rest of
        the window as usual (a same-day revision). ``ahead``: the whole window, each hour's mean
        times its expected multiplier if the surge goes on, ``1 + (factor - 1) s``, ``s`` its chance
        of lasting that long under the declared hazard: 1 today, ``1 - ENDS_PER_DAY`` tomorrow,
        its square after.
        """
        out = []
        for planner in (self.normal, self.short):
            if self.plan == "today":
                out.append(planner.decide(obs, factor, np.ones_like(factor)))
                continue
            today, tomorrow, rest = planner.segments(obs)
            whole = today + tomorrow + rest
            excess = factor - 1.0
            stay = 1.0 - ENDS_PER_DAY
            weighted = today * factor + tomorrow * (1.0 + excess * stay)
            weighted = weighted + rest * (1.0 + excess * (stay * stay))
            ahead = np.where(whole > 0, weighted / np.where(whole > 0, whole, 1.0), factor)
            out.append(planner.decide(obs, ahead, ahead))
        chosen: I64 = np.where(self.base.is_short[:, None], out[1], out[0])
        return chosen

    def decide(self, obs: StoreObservation) -> I64:
        surged, factor = self.assess(obs)
        incumbent = self.base.incumbent_orders(obs)
        if not bool(surged.any()):
            return incumbent
        out: I64 = np.where(surged, self.orders(obs, factor), incumbent)
        return out

    def report(self) -> dict[str, object]:
        """Per decision and replicate: -1 with no store alarm, else the items planned as surged."""
        return {"alarms": self.alarms}


class SurgeCalibration:
    """The lane incumbent deciding while the detector watches: the threshold's instrument.

    Truth session 6, gate item 6: the threshold is the smallest power of two above the largest
    evidence this sees on cells without a surge, fed exactly what the detector sees in operation (in
    a challenger's process of its own, censored sales and all). It orders exactly as the lane
    incumbent does; what it computes reaches only its report: the largest evidence, and per decision
    and replicate the store's evidence and each deciding item's posterior probability and size, in
    item order, so the harness, which knows the scenario, can time detection and attribution.
    """

    name = "surge_calibration"

    def __init__(
        self, world: ReleaseWorld, normal: IncumbentTables, short: IncumbentTables
    ) -> None:
        from synapse_kernel.challengers.shelf import LaneIncumbent

        self.base = LaneIncumbent(world, normal, short)
        self.detector = SurgeDetector(world)
        self.largest = 1.0
        self.evidence: list[list[float]] = []
        self.prob: list[list[list[float]]] = []
        self.sizes: list[list[list[float]]] = []

    def start(self, replicates: int) -> None:
        self.base.start(replicates)
        self.detector.reset()
        self.largest = 1.0
        self.evidence = []
        self.prob = []
        self.sizes = []

    def decide(self, obs: StoreObservation) -> I64:
        self.base.observe(obs)
        deciding = np.nonzero(obs.deciding)[0]
        state = self.detector.assess(self.base.history, deciding)
        self.largest = max(self.largest, float(state.evidence.max()))
        self.evidence.append(state.evidence.tolist())
        self.prob.append(state.prob[:, deciding].tolist())
        self.sizes.append(state.size[:, deciding].tolist())
        return self.base.incumbent_orders(obs)

    def report(self) -> dict[str, object]:
        return {
            "largest_evidence": self.largest,
            "evidence": self.evidence,
            "prob": self.prob,
            "sizes": self.sizes,
        }
