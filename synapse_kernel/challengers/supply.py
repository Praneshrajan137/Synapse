"""Supplier Trust's job: a late or missing delivery, detected at the first delivery that does not
come.

In the release world an order lands exactly when its supplier's declared schedule says, unless that
supplier is shocked, so an open order older than the supplier's declared lead time is proof that the
supplier is disrupted: outside cells S2 and S3 the detector cannot fire (a test shows it never does
on the development seeds of N, L and S1). It reads only the observation's open orders and the
declared lead times.

What a store can do about it, blind: it cannot know when the disruption ends (the informed oracle of
freeze W could, and still gained about nothing in S2). So the response is the smallest one with a
lever: while an item's supplier is disrupted, the lane's I2 plans that item against ``kappa`` times
its mean demand, ``kappa`` a factor per item and part of the day (1 until tuned), so tuning can
learn to hold back the glut that lands when the backlog does, or to hold more. Truth session 6
records this as simpler than the gate's sketch (a cover from an estimated arrival), because the
arrival cannot be estimated without the shock's end (decision S6-D-05).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
import numpy.typing as npt

from synapse_kernel.challengers.sensing import AdjustedIncumbent
from synapse_kernel.release.incumbent import part_of_day

if TYPE_CHECKING:
    from synapse_kernel.release.incumbent import IncumbentTables
    from synapse_kernel.release.observation import StoreObservation
    from synapse_kernel.release.world import ReleaseWorld

__all__ = ["SupplyDetector", "SupplyResponse"]

F64 = npt.NDArray[np.float64]
I64 = npt.NDArray[np.int64]
Bools = npt.NDArray[np.bool_]


class SupplyDetector:
    """Per replicate and item: whether the item's supplier has an order overdue."""

    def __init__(self, world: ReleaseWorld) -> None:
        names = [s.name for s in world.suppliers]
        self.supplier_of = np.array([names.index(item.supplier) for item in world.items])
        lead = np.array([s.lead_time_hours for s in world.suppliers], dtype=np.int64)
        self.lead_of_item = lead[self.supplier_of]
        self.suppliers = len(names)

    def overdue(self, obs: StoreObservation) -> Bools:
        """``(R, I)``: an open order of this item older than its supplier's declared lead time."""
        late = (obs.open_age_hours > self.lead_of_item[None, :, None]) & (obs.open_qty > 0)
        out: Bools = late.any(axis=-1)
        return out

    def disrupted(self, obs: StoreObservation) -> Bools:
        """``(R, I)``: any item of this item's supplier has an order overdue."""
        late = self.overdue(obs)
        by_supplier = np.zeros((late.shape[0], self.suppliers), dtype=bool)
        for j in range(self.suppliers):
            by_supplier[:, j] = late[:, self.supplier_of == j].any(axis=1)
        out: Bools = by_supplier[:, self.supplier_of]
        return out


class SupplyResponse:
    """The supply challenger alone, lane-aware: disrupted suppliers' items planned at ``kappa``."""

    name = "supply"

    def __init__(
        self,
        world: ReleaseWorld,
        normal: IncumbentTables,
        short: IncumbentTables,
        kappa: F64 | None = None,
    ) -> None:
        from synapse_kernel.challengers.shelf import LaneIncumbent

        self.base = LaneIncumbent(world, normal, short)
        self.detector = SupplyDetector(world)
        self.normal = AdjustedIncumbent(world, normal)
        self.short = AdjustedIncumbent(world, short)
        items = len(world.items)
        self.kappa = np.ones((items, 6)) if kappa is None else np.asarray(kappa, dtype=np.float64)
        self.flag = np.zeros((0, items), dtype=bool)
        self.flagged: list[list[int]] = []

    def start(self, replicates: int) -> None:
        self.base.start(replicates)
        self.flagged = []

    def assess(self, obs: StoreObservation) -> tuple[Bools, F64]:
        """Update the memory and the lane; return the disruption flag and the planned factor."""
        self.base.observe(obs)
        self.flag = self.detector.disrupted(obs)
        self.flagged.append(np.count_nonzero(self.flag & obs.deciding[None, :], axis=1).tolist())
        k = self.kappa[:, part_of_day(obs.hour_of_day)]
        factor: F64 = np.where(self.flag, k[None, :], 1.0)
        return self.flag, factor

    def orders(self, obs: StoreObservation, factor: F64) -> I64:
        short = self.base.is_short
        normal = self.normal.decide(obs, factor, factor)
        brief = self.short.decide(obs, factor, factor)
        out: I64 = np.where(short[:, None], brief, normal)
        return out

    def decide(self, obs: StoreObservation) -> I64:
        flag, factor = self.assess(obs)
        out: I64 = np.where(flag, self.orders(obs, factor), self.base.incumbent_orders(obs))
        return out

    def report(self) -> dict[str, object]:
        """Per decision and replicate, the deciding items flagged as supply-disrupted."""
        return {"flagged": self.flagged}
