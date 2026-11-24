"""The sealed tuning procedure: cyclic coordinate search over per-item, per-part-of-day factors.

PREREG-1 section 3, as the session-5 gate (section 7) implements it, identical for both incumbent
candidates and for every tuned part of the composition:

* one replicate-evaluation is one simulated replicate at one seed; items are tuned together: every
  item's factor moves in the same replicates and each item's own cost ``J_i`` is read from them;
* start from ``k = 1``; steps 0.5, 0.25, 0.125, 0.0625, 0.03125; a sweep visits each item's used
  parts of the day in clock order and evaluates ``k + step`` and ``k - step`` (``k >= 0``) in the
  same replicates; an item moves to the lower of the two only if strictly below its current ``J_i``
  (an exact tie between them: the smaller ``k``);
* at each step, sweep until a sweep moves no item, then halve; stop after an unmoved sweep at the
  smallest step. No cap short of convergence.

Items are independent in the release world (``tests/kernel/release/test_engine.py`` shows one item's
orders leave every other item's path unchanged), so the coordinates of different items are
evaluated in the same replicates at once: each item's sequence of moves is exactly what a search
over that item alone would make. Parts of the day in which an item never decides are "unused".
"""

from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING, Final

import numpy as np
import numpy.typing as npt

if TYPE_CHECKING:
    from collections.abc import Callable

__all__ = ["STEPS", "TuningResult", "coordinate_search"]

F64 = npt.NDArray[np.float64]
I64 = npt.NDArray[np.int64]
#: The sealed steps.
STEPS: Final[tuple[float, ...]] = (0.5, 0.25, 0.125, 0.0625, 0.03125)


@dataclasses.dataclass(frozen=True)
class TuningResult:
    """A converged table and how it got there."""

    factors: F64
    """``k[i, d]``, shape ``(items, 6)``; unused parts stay at 1."""
    cost: F64
    """Each item's ``J_i`` at ``factors``, averaged over the tuning replicates."""
    replicate_evaluations: int
    """Simulated replicates run, the initial evaluation included."""
    sweeps_per_step: tuple[int, ...]
    last_move: I64
    """Per item: the global sweep index (from 1) of its last move; 0 if it never moved."""
    used: npt.NDArray[np.bool_]


def coordinate_search(
    evaluate: Callable[[F64], F64],
    used: npt.NDArray[np.bool_],
    replicates: int,
    steps: tuple[float, ...] = STEPS,
    start: float = 1.0,
) -> TuningResult:
    """Tune ``k`` to convergence; ``evaluate(k)`` returns each item's mean cost under ``k``.

    ``used[i, d]`` marks the parts of the day in which item ``i`` decides; ``replicates`` is the
    number of simulated replicates one call of ``evaluate`` runs (for the published count). The
    sealed start is ``k = 1``; another ``start`` serves only the restart check of convergence.

    Raises:
        ValueError: ``used`` is not ``(items, 6)``, or an evaluation returns a cost that is not
            finite.
    """
    items, parts = used.shape
    if parts != 6:
        raise ValueError("six parts of the day")
    factors = np.where(used, start, 1.0)
    cost = _checked(evaluate(factors), items)
    evaluations = replicates
    # Each item's used parts in clock order: the j-th coordinate visited in a sweep.
    order = [np.nonzero(used[i])[0] for i in range(items)]
    depth = max((len(o) for o in order), default=0)
    sweeps: list[int] = []
    last_move = np.zeros(items, dtype=np.int64)
    sweep_index = 0
    for step in steps:
        count = 0
        while True:
            count += 1
            sweep_index += 1
            moved_any = False
            for slot in range(depth):
                rows = np.array([i for i in range(items) if len(order[i]) > slot], dtype=np.int64)
                if rows.size == 0:
                    continue
                cols = np.array([order[i][slot] for i in rows], dtype=np.int64)
                up = factors.copy()
                up[rows, cols] += step
                down = factors.copy()
                can_lower = factors[rows, cols] - step >= 0.0
                down[rows[can_lower], cols[can_lower]] -= step
                cost_up = _checked(evaluate(up), items)
                cost_down = _checked(evaluate(down), items)
                evaluations += 2 * replicates
                current = cost[rows]
                c_up = cost_up[rows]
                c_down = np.where(can_lower, cost_down[rows], np.inf)
                take_down = (c_down <= c_up) & (c_down < current)
                take_up = ~take_down & (c_up < current)
                for which, chosen, chosen_cost in (
                    (take_down, down, cost_down),
                    (take_up, up, cost_up),
                ):
                    r, c = rows[which], cols[which]
                    factors[r, c] = chosen[r, c]
                    cost[r] = chosen_cost[r]
                    last_move[r] = sweep_index
                if bool(take_down.any() or take_up.any()):
                    moved_any = True
            if not moved_any:
                break
        sweeps.append(count)
    return TuningResult(
        factors=factors,
        cost=cost,
        replicate_evaluations=evaluations,
        sweeps_per_step=tuple(sweeps),
        last_move=last_move,
        used=used.copy(),
    )


def _checked(values: F64, items: int) -> F64:
    out = np.asarray(values, dtype=np.float64)
    if out.shape != (items,) or not bool(np.all(np.isfinite(out))):
        raise ValueError("an evaluation must return one finite cost per item")
    return out.copy()
