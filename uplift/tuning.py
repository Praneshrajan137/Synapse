"""Choose arm E's par levels by a pre-registered grid search (ADR-055 D2.6, finding 61).

WHAT THIS IS FOR. Task 11 measured a `material` regret of the incumbent `(s, S)` policy
against a hindsight oracle. That number is the incumbent's own mis-tuning PLUS the value of
perfect information, and only the second part is anything a forecaster or a consensus system
could win. Arm E is the best STATIC policy over a committed grid, so it splits the judged
regret into two terms that mean different things::

    regret(reference - hindsight) = [reference - tuned] + [tuned - hindsight]
                                  =  tuning gap        +  information ceiling

The second term is EVPI in its textbook sense -- perfect information minus the best
here-and-now decision -- so it is a **ceiling** on what any amount of forecasting could buy,
not an estimate of it.

WHY THE COST FUNCTION IS INJECTED. `tune_par_level` never builds a simulation and never
imports the objective. It takes ``cost_of(seed, point) -> float`` and does arithmetic on what
it is handed. Three things follow, and the third is the reason:

* the search is testable at the FAST suite's budget with a synthetic cost function, so the
  argmin logic, the tie-break and every refusal are proven without a twin run;
* there is exactly one place that decides an arm's physics (`foresight.run_single_arm`), so
  the levels cannot be selected under one cadence and measured under another;
* a property over this module can assert what the search DOES rather than what a twin
  happened to produce, which is the difference between a specification and a snapshot.

WHAT IS REFUSED RATHER THAN REPAIRED. An empty grid, a duplicated grid point, a point that
violates ``0 <= s < S``, a non-finite cost, a seed range overlapping the measurement range,
and a cost table that does not cover the whole grid. Each returns or raises rather than
falling back, because every one of them would otherwise yield a *number* -- a search over a
grid nobody declared, or a minimum over a subset nobody chose (I-7).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Final

import structlog
import yaml

if TYPE_CHECKING:  # pragma: no cover - annotations only, and `annotations` is imported above
    from collections.abc import Callable, Mapping, Sequence

__all__ = [
    "DEFAULT_TUNING_PATH",
    "GridPoint",
    "TunedSelection",
    "TuningSpec",
    "TuningUnavailableError",
    "load_tuning_spec",
    "seed_overlap_refusal",
    "select_levels",
    "tune_par_level",
    "tuning_seeds",
]

logger = structlog.get_logger(__name__)

#: The committed grid. Deliberately NOT in `digital_twin/simulation/policy.yaml`: that file's
#: contract 2 requires every value in it to carry a documentation pin, and
#: `doc_truth.documented_value` requires an anchor to match exactly one line -- which a LIST
#: cannot satisfy. The file itself records the full reasoning.
DEFAULT_TUNING_PATH: Final[Path] = (
    Path(__file__).resolve().parents[1] / "infrastructure" / "quality" / "comparator-tuning.yaml"
)


class TuningUnavailableError(RuntimeError):
    """The grid, the seeds or the costs could not support a selection.

    Always a refusal, never a fallback. A tuned level chosen from a grid that could not be read,
    or a minimum taken over a partial cost table, is a number with no pre-registration behind it
    -- which is exactly what arm E exists to avoid being.
    """


@dataclass(frozen=True, slots=True)
class GridPoint:
    """One candidate `(s, S)` pair, validated at construction.

    `Par_Level_Reorder` raises on a non-integral or non-ordered pair, so validating here means
    the refusal names the GRID FILE rather than surfacing later as a policy construction error
    at replicate 0 of a CI-only measurement.
    """

    s: int
    S: int

    def __post_init__(self) -> None:
        if self.s < 0:
            raise TuningUnavailableError(f"grid point has negative reorder point: s={self.s}")
        if not self.s < self.S:
            raise TuningUnavailableError(f"grid point violates 0 <= s < S: s={self.s}, S={self.S}")

    @property
    def label(self) -> str:
        """A stable, sortable identity for artifact keys and log lines."""
        return f"s{self.s}_S{self.S}"


@dataclass(frozen=True, slots=True)
class TuningSpec:
    """The pre-registered search: which candidates, and at which seeds."""

    grid: tuple[GridPoint, ...]
    seed_start: int
    seed_count: int
    source: str


@dataclass(frozen=True, slots=True)
class TunedSelection:
    """The search's outcome, carrying enough to argue with it rather than only to use it."""

    levels: GridPoint
    mean_cost: float
    #: Every candidate's mean cost, keyed by `GridPoint.label`. Reported in the artifact so a
    #: reader can see the whole surface the minimum was taken over -- a selected pair whose
    #: neighbours are unknown is a number nobody can argue with, which is the objection
    #: `RegretObjective.contributions` was written to answer for the cost itself.
    surface: Mapping[str, float]
    seeds: tuple[int, ...]
    #: True when two or more candidates tied at the minimum. Not an error -- the tie-break is
    #: deterministic and declared -- but it is recorded, because a tie means the grid's
    #: resolution is coarser than the difference it is being asked to resolve.
    tie_broken: bool


def load_tuning_spec(path: Path | None = None) -> TuningSpec:
    """Read and validate the committed grid. Raises rather than defaulting anything."""
    resolved = DEFAULT_TUNING_PATH if path is None else path
    try:
        raw = yaml.safe_load(resolved.read_text(encoding="utf-8"))
    except OSError as error:  # pragma: no cover - exercised by the absent-file property
        raise TuningUnavailableError(f"tuning grid unreadable at {resolved}: {error}") from error
    if not isinstance(raw, dict):
        raise TuningUnavailableError(f"tuning grid at {resolved} is not a mapping")

    entries = raw.get("grid")
    if not isinstance(entries, list) or not entries:
        raise TuningUnavailableError(f"tuning grid at {resolved} declares no candidates")

    points: list[GridPoint] = []
    seen: set[tuple[int, int]] = set()
    for entry in entries:
        if not isinstance(entry, dict) or "s" not in entry or "S" not in entry:
            raise TuningUnavailableError(f"grid entry is not an {{s, S}} mapping: {entry!r}")
        point = GridPoint(s=int(entry["s"]), S=int(entry["S"]))
        if (point.s, point.S) in seen:
            # A duplicate is refused rather than de-duplicated: it means the declared grid and
            # the searched grid differ, and the count reported in the artifact would be wrong.
            raise TuningUnavailableError(f"grid declares {point.label} more than once")
        seen.add((point.s, point.S))
        points.append(point)

    seeds = raw.get("tuning_seeds")
    if not isinstance(seeds, dict) or "start" not in seeds or "count" not in seeds:
        raise TuningUnavailableError(f"tuning grid at {resolved} declares no tuning_seeds")
    start = int(seeds["start"])
    count = int(seeds["count"])
    if count <= 0:
        raise TuningUnavailableError(f"tuning_seeds.count must be positive, got {count}")
    if start < 0:
        raise TuningUnavailableError(f"tuning_seeds.start must be non-negative, got {start}")

    return TuningSpec(grid=tuple(points), seed_start=start, seed_count=count, source=str(resolved))


def tuning_seeds(spec: TuningSpec) -> tuple[int, ...]:
    """The seeds the search runs on -- contiguous, from the committed start."""
    return tuple(range(spec.seed_start, spec.seed_start + spec.seed_count))


def seed_overlap_refusal(spec: TuningSpec, *, measurement_replicates: int) -> str | None:
    """Refuse a tuning range that overlaps the measurement range. `None` when disjoint.

    **This is the guard that keeps the decomposition honest, and it is the whole reason the
    ranges are separate.** `_measure` iterates `range(measurement_replicates)`. Tuning on those
    same seeds would make arm E's levels in-sample optimal, which inflates the tuning gap and
    deflates the information ceiling -- biasing the split toward the hypothesis finding 61
    records. A measurement must not be biased toward the thing it is testing.

    Computed against the ACTUAL replicate count rather than an assumed one, so raising
    `--replicates` past the tuning start fails loudly instead of overlapping quietly.

    The bias direction of the repair is stated so it can be checked: out-of-sample levels can
    only make the tuning gap smaller and the ceiling larger than in-sample levels would. Adopting
    a standard stricter than the criterion demands is legitimate only in the direction that makes
    a claim harder to confirm, and this is that direction.
    """
    if measurement_replicates <= 0:
        return f"measurement_replicates must be positive, got {measurement_replicates}"
    last_measurement = measurement_replicates - 1
    last_tuning = spec.seed_start + spec.seed_count - 1
    if spec.seed_start <= last_measurement:
        return (
            "tuning seeds overlap the measurement seeds: tuning covers "
            f"{spec.seed_start}..{last_tuning} while the measurement covers "
            f"0..{last_measurement}. In-sample tuning would bias the decomposition toward "
            "the tuning gap and away from the information ceiling."
        )
    return None


def select_levels(surface: Mapping[GridPoint, float]) -> tuple[GridPoint, float, bool]:
    """Take the argmin over a COMPLETE cost surface, with a declared deterministic tie-break.

    Returns `(levels, mean_cost, tie_broken)`. Pure arithmetic, no simulation, no I/O -- which is
    what lets a fast property exercise every branch including the refusals. It deliberately does
    NOT return a `TunedSelection`: that record carries the seed list, this function is not told
    the seeds, and a record with a placeholder field is a state a reader has to hold in their head.

    The tie-break is lowest `s`, then lowest `S`. It is declared rather than incidental because
    `min()` over a mapping would otherwise resolve ties by insertion order, and insertion order is
    a property of the YAML file's layout rather than of the search -- so reordering the grid file
    could silently change which levels arm E uses.
    """
    if not surface:
        raise TuningUnavailableError("cannot select levels from an empty cost surface")
    for point, cost in surface.items():
        if not math.isfinite(cost):
            raise TuningUnavailableError(
                f"candidate {point.label} has a non-finite mean cost: {cost!r}"
            )

    levels, mean_cost = min(surface.items(), key=lambda item: (item[1], item[0].s, item[0].S))
    ties = sum(1 for cost in surface.values() if cost == mean_cost)
    return levels, mean_cost, ties > 1


def tune_par_level(
    spec: TuningSpec,
    *,
    cost_of: Callable[[int, GridPoint], float],
    measurement_replicates: int,
) -> TunedSelection:
    """Run the pre-registered search and return the selected levels with its whole surface.

    `cost_of(seed, point)` is supplied by the caller and is the ONLY thing here that touches a
    simulation or an objective. See the module docstring for why.

    Refuses -- never falls back -- when the seed ranges overlap, when a candidate produces a
    non-finite cost, or when the grid is empty. A tuned level obtained past any of those is not
    the minimum of the grid that was pre-registered.
    """
    overlap = seed_overlap_refusal(spec, measurement_replicates=measurement_replicates)
    if overlap is not None:
        raise TuningUnavailableError(overlap)

    seeds = tuning_seeds(spec)
    surface: dict[GridPoint, float] = {}
    for point in spec.grid:
        costs = [cost_of(seed, point) for seed in seeds]
        if not costs:
            raise TuningUnavailableError(f"candidate {point.label} produced no costs")
        surface[point] = sum(costs) / len(costs)

    chosen, mean_cost, tie_broken = select_levels(surface)
    selection = TunedSelection(
        levels=chosen,
        mean_cost=mean_cost,
        surface={point.label: cost for point, cost in surface.items()},
        seeds=seeds,
        tie_broken=tie_broken,
    )
    logger.info(
        "arm_e_levels_selected",
        s=selection.levels.s,
        S=selection.levels.S,
        mean_cost=selection.mean_cost,
        candidates=len(spec.grid),
        tuning_seeds=len(seeds),
        tie_broken=selection.tie_broken,
        source=spec.source,
    )
    return selection


def decomposition_identity_residual(
    *, regret: float, tuning_gap: float, information_ceiling: float
) -> float:
    """`regret - (tuning_gap + information_ceiling)`, for the caller to assert on.

    The identity is a theorem over the reals: both terms are differences of the same three means,
    so the middle one cancels. It is **not** a theorem over IEEE 754, and this project has already
    paid for that distinction once -- finding 56 falsified a property whose algebra was exact and
    whose floating-point evaluation was not, because subtracting a large term from two nearly
    equal small ones destroys the difference between them.

    So this returns the residual rather than a bool, and the caller decides the tolerance it can
    defend. The exact version of the claim belongs in a property over `Fraction`, where it cannot
    fail for any finite input; the float version belongs here, where a caller can report the
    residual it actually observed instead of asserting a blurrier claim in order to pass.
    """
    return regret - (tuning_gap + information_ceiling)


def sequence_mean(values: Sequence[float]) -> float:
    """Mean of a non-empty sequence, refusing an empty one rather than returning zero.

    A zero mean over no observations is indistinguishable from a measured zero, and the whole
    point of arm E is to stop two different quantities being reported as one number.
    """
    if not values:
        raise TuningUnavailableError("cannot take a mean over an empty sequence")
    return sum(values) / len(values)
