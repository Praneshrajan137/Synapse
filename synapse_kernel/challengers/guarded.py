"""A component behind the guard of the operator's decision D-4(b), around the lane incumbent.

PREREG-1 section 3: a challenger's quantity outside ``[0.5 q_I, 2 q_I]`` is clipped to the nearest
end (:func:`synapse_kernel.release.guard.guard`), ``q_I`` the incumbent's quantity there; truth
session 6, gate item 1, reads ``q_I`` as the lane incumbent's. The composition guards every decision
this way; this wrapper lets a component be measured alone both with and without it, and counts the
item-decisions the guard changed (the clipped share, reported per cell).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import numpy as np

from synapse_kernel.challengers.shelf import LaneIncumbent
from synapse_kernel.release.guard import guard

if TYPE_CHECKING:
    from collections.abc import Callable

    import numpy.typing as npt

    from synapse_kernel.release.engine import ReleasePolicy
    from synapse_kernel.release.incumbent import IncumbentTables
    from synapse_kernel.release.observation import StoreObservation
    from synapse_kernel.release.world import ReleaseWorld

__all__ = ["Guarded"]


class Guarded:
    """``inner``'s orders, clipped to ``[ceil(q_I / 2), 2 q_I]`` around the lane incumbent's."""

    def __init__(
        self,
        inner: ReleasePolicy,
        world: ReleaseWorld,
        normal: IncumbentTables,
        short: IncumbentTables,
        name: str,
        inner_report: Callable[[], dict[str, Any]] | None = None,
    ) -> None:
        self.inner = inner
        self.inner_report = inner_report
        self.lane = LaneIncumbent(world, normal, short)
        self.name = f"{name}+guard"
        self.clipped = 0
        self.decisions = 0

    def start(self, replicates: int) -> None:
        self.inner.start(replicates)
        self.lane.start(replicates)
        self.clipped = 0
        self.decisions = 0

    def decide(self, obs: StoreObservation) -> npt.NDArray[np.int64]:
        wanted = np.asarray(self.inner.decide(obs), dtype=np.int64)
        self.lane.observe(obs)
        out = guard(wanted, self.lane.incumbent_orders(obs))
        deciding = np.broadcast_to(obs.deciding[None, :], out.shape)
        self.clipped += int(np.count_nonzero((out != wanted) & deciding))
        self.decisions += int(np.count_nonzero(deciding))
        return out

    def report(self) -> dict[str, Any]:
        summary: dict[str, Any] = {} if self.inner_report is None else dict(self.inner_report())
        summary["clipped"] = self.clipped
        summary["decisions"] = self.decisions
        return summary
