"""The five cells of PREREG-1 section 6, and the one shock a replicate of a shock cell meets.

| Cell | Definition (sealed) |
| N | No shock |
| L | Every item's shelf life halved, rounded down to whole hours, at least 12 hours |
| S1 | 30% of items (rounded up), drawn uniformly by count, demand times one u ~ U(1.5, 3.0), for
       U(1, 3) days |
| S2 | One supplier, uniformly chosen: lead times times v ~ U(2, 4), for U(2, 4) days |
| S3 | One supplier, uniformly chosen, delivers nothing for U(1, 3) days; an order placed during the
       outage arrives at its end plus its lead time |

One shock per replicate; its onset uniform between the start of measured day 1 and the end of
measured day 7 less its duration, from a draw of its own. Every draw is counter-based
(:mod:`synapse_kernel.release.rng`), keyed by the replicate's seed and a purpose, so a shock is a
pure function of (seed, cell) and no policy can move it. Implementation choices the sealed text
leaves open are fixed in the session-5 gate, section 7, and frozen with the world (ADR-062): an
hour belongs to a shock when its start lies in ``[onset, onset + duration)``; a continuous arrival
time lands at the first whole hour at or after it; deliveries scheduled inside an outage do not
happen and their orders arrive at the outage's end.
"""

from __future__ import annotations

import dataclasses
import math
from typing import TYPE_CHECKING, Final

import numpy as np
import numpy.typing as npt

from synapse_kernel.release.rng import Purpose, uniforms
from synapse_kernel.release.world import HOURS_PER_DAY, MEASURED_DAYS

if TYPE_CHECKING:
    from synapse_kernel.release.world import ReleaseWorld

__all__ = ["CELLS", "MIN_SHELF_LIFE_HOURS", "Shock", "draw_shock", "shelf_lives"]

CELLS: Final[tuple[str, ...]] = ("N", "L", "S1", "S2", "S3")
#: Cell L's floor on a halved shelf life (sealed).
MIN_SHELF_LIFE_HOURS: Final[int] = 12
MEASURED_HOURS: Final[int] = MEASURED_DAYS * HOURS_PER_DAY


@dataclasses.dataclass(frozen=True)
class Shock:
    """The shock one replicate meets; ``kind`` is ``none``, ``surge``, ``delay`` or ``outage``."""

    kind: str
    onset_hour: float = 0.0
    duration_hours: float = 0.0
    items: tuple[int, ...] = ()
    size: float = 1.0
    supplier: int = -1

    @property
    def end_hour(self) -> float:
        return self.onset_hour + self.duration_hours

    def covers(self, hour: int) -> bool:
        """Whether whole hour ``hour`` belongs to the shock: its start lies in the window."""
        return self.kind != "none" and self.onset_hour <= hour < self.end_hour


def shelf_lives(world: ReleaseWorld, cell: str) -> npt.NDArray[np.int64]:
    """Each item's shelf life at receipt in ``cell``, whole hours (cell L halves it, floor 12)."""
    if cell not in CELLS:
        raise ValueError(f"unknown cell {cell!r}; the cells are {CELLS}")
    lives = np.array([item.shelf_life_hours for item in world.items], dtype=np.int64)
    if cell == "L":
        return np.maximum(MIN_SHELF_LIFE_HOURS, lives // 2)
    return lives


def _u(seed: int, purpose: int) -> float:
    return float(uniforms(seed, purpose, 0, 0)[0])


def draw_shock(world: ReleaseWorld, cell: str, seed: int) -> Shock:
    """The shock of replicate ``seed`` in ``cell``: drawn from its seed alone, never from a policy.

    Raises:
        ValueError: An unknown cell.
    """
    if cell not in CELLS:
        raise ValueError(f"unknown cell {cell!r}; the cells are {CELLS}")
    if cell in ("N", "L"):
        return Shock(kind="none")
    start = float(world.measured_start_hour)
    if cell == "S1":
        duration = (1.0 + 2.0 * _u(seed, Purpose.SHOCK_DURATION)) * HOURS_PER_DAY
        size = 1.5 + 1.5 * _u(seed, Purpose.SHOCK_SIZE)
        count = math.ceil(3 * len(world.items) / 10)
        draws = uniforms(seed, Purpose.SHOCK_ITEMS, np.arange(len(world.items)), 0)
        chosen = np.argsort(draws, kind="stable")[:count]
        onset = start + _u(seed, Purpose.SHOCK_ONSET) * (MEASURED_HOURS - duration)
        return Shock("surge", onset, duration, tuple(sorted(int(i) for i in chosen)), size)
    supplier = int(math.floor(_u(seed, Purpose.SHOCK_SUPPLIER) * len(world.suppliers)))
    if cell == "S2":
        duration = (2.0 + 2.0 * _u(seed, Purpose.SHOCK_DURATION)) * HOURS_PER_DAY
        size = 2.0 + 2.0 * _u(seed, Purpose.SHOCK_SIZE)
        onset = start + _u(seed, Purpose.SHOCK_ONSET) * (MEASURED_HOURS - duration)
        return Shock("delay", onset, duration, (), size, supplier)
    duration = (1.0 + 2.0 * _u(seed, Purpose.SHOCK_DURATION)) * HOURS_PER_DAY
    onset = start + _u(seed, Purpose.SHOCK_ONSET) * (MEASURED_HOURS - duration)
    return Shock("outage", onset, duration, (), 1.0, supplier)
