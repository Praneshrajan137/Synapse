"""The sealed objective J, in money per store-day (PREREG-1 section 2), from integer totals.

``J = sum_i p_i [ (m + g) L_i + (1 - m) W_i + r (1 - m) / 365 H_i ] / 7`` per store-day, with
``L`` lost units, ``W`` discarded units, ``H`` unit-days held over the 7 measured days. Primary
values ``m = 0.38``, ``g = 0``, ``r = 0.25`` (sealed). The engine keeps H doubled in unit-hours
(H2), so ``H_i = H2_i / 48``. Every total is an integer, and a replicate's J is summed over
items with ``math.fsum`` (correctly rounded, so the same bits on every platform).
"""

from __future__ import annotations

import dataclasses
import math
from typing import TYPE_CHECKING, Final

import numpy as np
import numpy.typing as npt

from synapse_kernel.release.world import MEASURED_DAYS

if TYPE_CHECKING:
    from synapse_kernel.release.engine import Outcome
    from synapse_kernel.release.world import ReleaseWorld

__all__ = ["PRIMARY", "Weights", "fill_rate", "item_costs", "replicate_costs", "waste_share"]

F64 = npt.NDArray[np.float64]


@dataclasses.dataclass(frozen=True)
class Weights:
    """The objective's economic weights: margin m, loss beyond margin g, carrying rate r."""

    margin: float
    beyond: float
    carrying: float

    @property
    def lost_sale(self) -> float:
        return self.margin + self.beyond

    @property
    def waste(self) -> float:
        return 1.0 - self.margin

    @property
    def holding_per_h2(self) -> float:
        """Cost of one doubled unit-hour: ``r (1 - m) / 365 / 48``."""
        return self.carrying * (1.0 - self.margin) / 365.0 / 48.0


#: PREREG-1 section 2's primary values (sealed).
PRIMARY: Final[Weights] = Weights(margin=0.38, beyond=0.0, carrying=0.25)


def item_costs(world: ReleaseWorld, outcome: Outcome, weights: Weights = PRIMARY) -> F64:
    """Per replicate and item: ``p_i [ (m+g) L + (1-m) W + c H2 ] / 7``, shape ``(R, items)``."""
    prices = np.array([item.price for item in world.items], dtype=np.float64)
    lost = outcome.lost.astype(np.float64)
    wasted = outcome.wasted.astype(np.float64)
    held = outcome.holding2.astype(np.float64)
    per_item: F64 = (
        prices
        * (weights.lost_sale * lost + weights.waste * wasted + weights.holding_per_h2 * held)
        / MEASURED_DAYS
    )
    return per_item


def replicate_costs(
    world: ReleaseWorld, outcome: Outcome, weights: Weights = PRIMARY
) -> list[float]:
    """J per replicate: the item costs summed with ``math.fsum``, in item order."""
    costs = item_costs(world, outcome, weights)
    return [math.fsum(float(v) for v in row) for row in costs]


def fill_rate(outcome: Outcome) -> list[float]:
    """Units filled over units demanded, all items pooled, per replicate (measured days)."""
    return [
        (int(s) / int(d)) if int(d) > 0 else 0.0
        for s, d in zip(outcome.sold.sum(axis=-1), outcome.demanded.sum(axis=-1), strict=True)
    ]


def waste_share(outcome: Outcome) -> list[float]:
    """Units discarded over units sold, per replicate: retail value at unit prices."""
    return [
        (int(w) / int(s)) if int(s) > 0 else 0.0
        for w, s in zip(outcome.wasted.sum(axis=-1), outcome.sold.sum(axis=-1), strict=True)
    ]
