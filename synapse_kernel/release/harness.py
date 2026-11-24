"""Wiring for the release world: scenarios by cell and seed, the incumbent's tuning and pricing.

Everything here composes the frozen parts (world, cells, scenarios, engine, objective, incumbent,
tuning) and adds no physics of its own. ``scripts/kernel/tune_incumbent.py`` drives it to produce
the incumbent's tables for freeze W; session 6 tunes its composition through the same functions.
"""

from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING

import numpy as np
import numpy.typing as npt

from synapse_kernel.release.engine import run
from synapse_kernel.release.incumbent import PARTS, Incumbent, IncumbentTables, part_of_day
from synapse_kernel.release.objective import fill_rate, item_costs, replicate_costs, waste_share
from synapse_kernel.release.scenario import build_scenario
from synapse_kernel.release.tuning import TuningResult, coordinate_search
from synapse_kernel.release.world import HOURS_PER_WEEK

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from synapse_kernel.release.engine import ReleasePolicy
    from synapse_kernel.release.scenario import Scenario
    from synapse_kernel.release.world import ReleaseWorld

__all__ = [
    "Priced",
    "batch_independent",
    "mean_demand_table",
    "price",
    "scenarios",
    "tune_incumbent",
    "used_parts",
]

F64 = npt.NDArray[np.float64]


def scenarios(world: ReleaseWorld, cell: str, seeds: Sequence[int]) -> list[Scenario]:
    """The scenarios of ``cell`` at ``seeds``, in order."""
    return [build_scenario(world, cell, seed) for seed in seeds]


def mean_demand_table(world: ReleaseWorld, groups: Sequence[Sequence[Scenario]]) -> F64:
    """Mean demand per hour of the week and item over every simulated hour of the scenarios.

    PREREG-1 section 3's ``mu`` "as the tuning seeds show it per item, day of week and hour": the
    recorded (uncensored) demand of the tuning replicates, warm-up included (the gate, section 7).
    """
    total = np.zeros((HOURS_PER_WEEK, len(world.items)))
    count = np.zeros(HOURS_PER_WEEK)
    hours = np.arange(world.horizon_hours) % HOURS_PER_WEEK
    for group in groups:
        for scenario in group:
            np.add.at(total, hours, scenario.demand)
            np.add.at(count, hours, 1.0)
    out: F64 = total / count[:, None]
    return out


def used_parts(world: ReleaseWorld) -> npt.NDArray[np.bool_]:
    """``used[i, d]``: whether item ``i`` decides in part of the day ``d`` (at a cut-off)."""
    by_name = world.supplier_by_name
    used = np.zeros((len(world.items), PARTS), dtype=bool)
    for i, item in enumerate(world.items):
        for cutoff in by_name[item.supplier].cutoff_hours:
            used[i, part_of_day(cutoff)] = True
    return used


@dataclasses.dataclass(frozen=True)
class Priced:
    """One policy priced on one cell's replicates."""

    cell: str
    costs: tuple[float, ...]
    fill: tuple[float, ...]
    waste: tuple[float, ...]
    item_cost: F64
    """Mean cost per item over the replicates."""

    @property
    def mean_cost(self) -> float:
        return float(np.mean(self.costs))


def price(world: ReleaseWorld, batch: Sequence[Scenario], policy: ReleasePolicy) -> Priced:
    """Run ``policy`` on one cell's scenarios and price every replicate."""
    out = run(world, batch, policy)
    return Priced(
        cell=batch[0].cell,
        costs=tuple(replicate_costs(world, out)),
        fill=tuple(fill_rate(out)),
        waste=tuple(waste_share(out)),
        item_cost=item_costs(world, out).mean(axis=0),
    )


def batch_independent(
    world: ReleaseWorld, make_policy: Callable[[], ReleasePolicy], batch: Sequence[Scenario]
) -> bool:
    """Whether a policy decides each replicate exactly as it would alone (freeze W's rule).

    A policy sees the whole batch's observations and is told the batch size by ``start``, so it
    could pool information across replicates, or read the batch size: in the confirmatory run a
    cell's size is its ``n_c``, which differs by cell. PREREG-1 section 1 gives a policy neither
    the cell nor any other replicate. One run of the batch is compared with one run per scenario,
    each with a fresh policy, outcome by outcome; any difference is a ``False``.
    """
    together = run(world, batch, make_policy())
    for r, scenario in enumerate(batch):
        alone = run(world, [scenario], make_policy())
        for field in dataclasses.fields(alone):
            mine, theirs = getattr(together, field.name), getattr(alone, field.name)
            if mine.ndim >= 1 and mine.shape[0] == len(batch) and theirs.shape[0] == 1:
                if not np.array_equal(mine[r], theirs[0]):
                    return False
            elif not np.array_equal(mine, theirs):
                return False
    return True


def tune_incumbent(
    world: ReleaseWorld,
    name: str,
    waste_aware: bool,
    groups: Sequence[Sequence[Scenario]],
) -> tuple[IncumbentTables, TuningResult]:
    """Tune one incumbent version on the tuning scenarios ``groups`` (one list per cell).

    The mean-demand table comes from the same scenarios' records; each evaluation prices every
    replicate of every group and averages each item's cost over all of them.
    """
    table = mean_demand_table(world, groups)
    replicates = sum(len(group) for group in groups)

    def evaluate(factors: F64) -> F64:
        tables = IncumbentTables(name, waste_aware, factors.copy(), table)
        total = np.zeros(len(world.items))
        for group in groups:
            total += price(world, group, Incumbent(world, tables)).item_cost * len(group)
        out: F64 = total / replicates
        return out

    result = coordinate_search(evaluate, used_parts(world), replicates)
    return IncumbentTables(name, waste_aware, result.factors, table), result
