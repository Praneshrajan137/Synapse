"""The Freshness Guardian's job: which shelf-life lane the store is in, and so which incumbent runs.

A planner knows how long a product keeps (PREREG-1 section 3 re-tunes the incumbent in cell L for
that reason), and the observation shows it: a batch's hours to expiry. Truth session 6's gate (item
2) fixed the rule before any result, from the observation and cell N's declared parameters only,
with no parameter of cell L: a batch whose receipt was observed has a known life at receipt, its
hours to expiry plus the hours since it arrived
(:class:`~synapse_kernel.challengers.history.History` learns it). The store is in **lane L** once
some such life is shorter than its item's declared shelf life; in **lane P** until then, and for
good once one equals the declared life.

SYNAPSE's incumbent is the lane's frozen incumbent version, and the guard's anchor with it (gate
item 1, a reading recorded as one): I2-P in lane P, the contest's incumbent and the cell-blind
default that loses least by construction; I2-L in lane L, the version a planner who knew the shorter
shelf life would run.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
import numpy.typing as npt

from synapse_kernel.challengers.history import History
from synapse_kernel.release.incumbent import Incumbent

if TYPE_CHECKING:
    from synapse_kernel.release.incumbent import IncumbentTables
    from synapse_kernel.release.observation import StoreObservation
    from synapse_kernel.release.world import ReleaseWorld

__all__ = ["Lane", "LaneIncumbent", "LaneSensing", "declared_lives"]

I64 = npt.NDArray[np.int64]
Bools = npt.NDArray[np.bool_]


def declared_lives(world: ReleaseWorld) -> I64:
    """Each item's declared shelf life at receipt, in hours (cell N's)."""
    return np.array([item.shelf_life_hours for item in world.items], dtype=np.int64)


class Lane:
    """Per replicate: whether the store is in the short-shelf-life lane."""

    def __init__(self, declared: I64) -> None:
        self.declared = np.asarray(declared, dtype=np.int64).copy()
        self.start(0)

    def start(self, replicates: int) -> None:
        self.short = np.zeros(replicates, dtype=bool)
        self.normal = np.zeros(replicates, dtype=bool)

    def update(self, history: History) -> Bools:
        """The lane after the history's latest update: ``True`` for lane L."""
        known = history.life >= 0
        self.normal |= (known & (history.life == self.declared[None, :])).any(axis=1)
        shorter = (known & (history.life < self.declared[None, :])).any(axis=1)
        self.short = shorter & ~self.normal
        out: Bools = self.short.copy()
        return out


class LaneIncumbent:
    """SYNAPSE's incumbent alone: the lane's frozen version decides every order (no challenger)."""

    name = "lane_incumbent"

    def __init__(
        self, world: ReleaseWorld, normal: IncumbentTables, short: IncumbentTables
    ) -> None:
        declared = declared_lives(world)
        self.history = History(len(world.items), declared)
        self.lane = Lane(declared)
        self.normal = Incumbent(world, normal)
        self.short = Incumbent(world, short)
        self.is_short = np.zeros(0, dtype=bool)

    def start(self, replicates: int) -> None:
        self.history.start(replicates)
        self.lane.start(replicates)
        self.normal.start(replicates)
        self.short.start(replicates)

    def observe(self, obs: StoreObservation) -> Bools:
        """Update the memory and the lane; return the lane per replicate."""
        self.history.update(obs)
        self.is_short = self.lane.update(self.history)
        return self.is_short

    def incumbent_orders(self, obs: StoreObservation) -> I64:
        """``q_I``: the lane incumbent's orders, the guard's anchor."""
        out: I64 = np.where(self.is_short[:, None], self.short.decide(obs), self.normal.decide(obs))
        return out

    def decide(self, obs: StoreObservation) -> I64:
        self.observe(obs)
        return self.incumbent_orders(obs)


class LaneSensing:
    """The Demand Prophet's job alone, lane-aware: each lane's I2 with today's level sensed."""

    name = "sensing"

    def __init__(
        self, world: ReleaseWorld, normal: IncumbentTables, short: IncumbentTables
    ) -> None:
        from synapse_kernel.challengers.sensing import Sensing

        self.base = LaneIncumbent(world, normal, short)
        self.normal = Sensing(world, normal)
        self.short = Sensing(world, short)

    def start(self, replicates: int) -> None:
        self.base.start(replicates)

    def decide(self, obs: StoreObservation) -> I64:
        short = self.base.observe(obs)
        history = self.base.history
        out: I64 = np.where(
            short[:, None], self.short.orders(history, obs), self.normal.orders(history, obs)
        )
        return out
