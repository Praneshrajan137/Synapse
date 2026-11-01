"""Choose arm E's par levels by a pre-registered search (ADR-055 D2.6; leaf 13.7a).

WHAT THIS IS FOR. The incumbent's regret against the hindsight oracle mixes the incumbent's own
mis-tuning with the value of information, and only the second is anything a forecaster or a
consensus system could win (finding 61). Arm E -- the best STATIC policy -- separates them, and the
structure-aware arm O separates what an information-using static rule achieves from what only
perfect information buys (R5.46)::

    regret(B - D) = [B - E]     + [E - O]                      + [O - D]
                  = tuning gap  + achievable information value + residual value of information

``E - D`` is the information ceiling checkpoint B-prime judges. **A weak E inflates it** -- the
unsafe direction, a false "room to win" -- so E must be the best static policy for the world under
measurement. Version 1 (finding 63's 18-point grid, one ``(s, S)`` for every SKU) fails that twice
once structure 3 is on: suppliers differ, so one shared pair is not the best static policy, and a
grid sized for instantaneous replenishment cannot contain the optimum when lead-time demand is
several times larger. Version 2 therefore tunes one pair PER SUPPLIER GROUP
(``uplift/tuned_static.py``) over candidates DERIVED by a committed rule
(:func:`derive_candidates`), with a search that extends, refines, and refuses at a box boundary
(:func:`tune_group_levels`).

WHY THE COST FUNCTION IS INJECTED. Neither search builds a simulation or imports the objective:
each takes ``cost_of(seed, levels) -> float`` and does arithmetic on what it is handed. So every
branch -- argmin, tie-break, extension, refusal -- is provable at the fast suite's budget with a
synthetic cost (Property 81), and exactly one place decides an arm's physics
(``foresight.run_single_arm``), so levels cannot be selected under one cadence and measured under
another.

WHAT IS REFUSED RATHER THAN REPAIRED. A spec of any version but 2; a missing or unknown key; a rule
or point violating its own constraints; a stale budget projection; an empty or repeated grid, group
list or seed list; a group without candidates; a non-finite cost; a seed range overlapping the
measurement range. Each raises rather than falling back, because each would otherwise yield a
NUMBER -- a search over candidates nobody declared (I-7). The search's two OUTCOME refusals,
:data:`BOUNDARY_REFUSAL` and :data:`NON_CONVERGENCE_REFUSAL`, are reported on the selection with
the levels reached instead, because a refused split must still show what the search found.
"""

from __future__ import annotations

import itertools
import math
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Final

import structlog
import yaml

if TYPE_CHECKING:  # pragma: no cover - annotations only, and `annotations` is imported above
    from collections.abc import Callable, Mapping, Sequence

    from digital_twin.simulation.world import ResolvedWorld, SupplyStructure
    from uplift.tuned_static import GroupLevels

__all__ = [
    "BOUNDARY_REFUSAL",
    "DEFAULT_TUNING_PATH",
    "NON_CONVERGENCE_REFUSAL",
    "TUNING_SPEC_VERSION",
    "CandidateRule",
    "GridPoint",
    "GroupTunedSelection",
    "ThreeTermSplit",
    "TunedSelection",
    "TuningSpec",
    "TuningUnavailableError",
    "decomposition_identity_residual",
    "derive_candidates",
    "load_tuning_spec",
    "neighbours",
    "seed_overlap_refusal",
    "select_levels",
    "sequence_mean",
    "three_term_split",
    "tune_group_levels",
    "tune_par_level",
    "tuning_seeds",
]

logger = structlog.get_logger(__name__)

#: The committed search spec. Deliberately NOT in `digital_twin/simulation/policy.yaml`: that
#: file's contract 2 requires every value in it to carry a documentation pin, and
#: `doc_truth.documented_value` requires an anchor to match exactly one line -- which a LIST
#: (the rule's `z_values`, its `gaps`) cannot satisfy. The file itself records the reasoning.
DEFAULT_TUNING_PATH: Final[Path] = (
    Path(__file__).resolve().parents[1] / "infrastructure" / "quality" / "comparator-tuning.yaml"
)

#: The schema version this reader implements. Version 1 was finding 63's fixed 18-point grid; it
#: survives in the file only as a COMMENT, and a version-1 file is refused by its version.
TUNING_SPEC_VERSION: Final[int] = 2

#: The two refusals `tune_group_levels` REPORTS rather than raises. Every reported refusal string
#: starts with one of them, so a caller matches a constant instead of a literal kept in step.
BOUNDARY_REFUSAL: Final[str] = "search-box boundary"
NON_CONVERGENCE_REFUSAL: Final[str] = "non-convergence"

#: The four unit moves :func:`neighbours` makes per group, as ``(delta s, delta S)``, in its
#: declared order. One tuple, so the neighbourhood, the certificate and the recheck's budget
#: projection (:func:`_check_budget`) count the same moves.
_UNIT_MOVES: Final[tuple[tuple[int, int], ...]] = ((-1, 0), (1, 0), (0, -1), (0, 1))

#: The keys each block may carry. An unknown key is REFUSED: a value no reader reads is a committed
#: number nothing uses, and it would read as configuration while configuring nothing.
_TOP_LEVEL_KEYS: Final[frozenset[str]] = frozenset(
    {"version", "candidate_rule", "tuning_seeds", "budget"}
)
_RULE_KEYS: Final[frozenset[str]] = frozenset(
    {
        "provenance",
        "review_min",
        "z_values",
        "extension_factor",
        "max_extensions",
        "gaps",
        "max_passes",
        "max_evaluations",
        "recheck_top_k",
    }
)
_SEED_KEYS: Final[frozenset[str]] = frozenset({"start", "count"})
_BUDGET_KEYS: Final[frozenset[str]] = frozenset(
    {
        "provenance",
        "measured_reference_run",
        "measured_arm_replicates",
        "measured_measure_step_minutes",
        "projected_max_tuning_arm_replicates",
        "recheck_measurement_replicates",
        "recheck_max_groups",
        "projected_max_recheck_arm_replicates",
    }
)


class TuningUnavailableError(RuntimeError):
    """The spec, the candidates, the seeds or the costs could not support a selection.

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
class CandidateRule:
    """The committed rule arm E's candidates are derived by, and the bounds of its search.

    Read from ``comparator-tuning.yaml``'s ``candidate_rule:`` block, where every field is
    required. Validated HERE rather than in the reader, so a rule built by hand obeys exactly the
    rules a rule read from the file does; the reader adds only the file and key path.

    * ``review_min`` -- the review period the protected demand covers, in minutes. It is the
      comparator's decision cadence (``uplift/foresight.py::FORESIGHT_WINDOW_MIN``) stated a
      second time, and Property 81 asserts the two agree.
    * ``z_values`` -- safety factors, strictly increasing; one candidate ``S`` per value.
    * ``extension_factor``, ``max_extensions`` -- each extension appends the next term of a
      geometric sequence of ratio ``extension_factor``, at most ``max_extensions`` per direction.
    * ``gaps`` -- the bands ``S - s`` the gap check tries, strictly increasing and each >= 2
      (a band of 1 is base-stock itself).
    * ``max_passes``, ``max_evaluations`` -- the search's two hard bounds.
    * ``recheck_top_k`` -- how many of the search's cheapest level vectors
      :attr:`GroupTunedSelection.ranked` hands the comparator's in-sample recheck (R1); at least
      1, so the selection itself is always among them.
    """

    review_min: float
    z_values: tuple[float, ...]
    extension_factor: float
    max_extensions: int
    gaps: tuple[int, ...]
    max_passes: int
    max_evaluations: int
    recheck_top_k: int

    def __post_init__(self) -> None:
        if not (math.isfinite(self.review_min) and self.review_min > 0.0):
            raise TuningUnavailableError(
                f"candidate_rule.review_min = {self.review_min!r} must be finite and > 0"
            )
        if not self.z_values:
            raise TuningUnavailableError("candidate_rule.z_values declares no safety factor")
        for index, z in enumerate(self.z_values):
            if not math.isfinite(z):
                raise TuningUnavailableError(
                    f"candidate_rule.z_values[{index}] = {z!r} is not finite"
                )
        _require_strictly_increasing(self.z_values, "candidate_rule.z_values")
        if not (math.isfinite(self.extension_factor) and self.extension_factor > 1.0):
            raise TuningUnavailableError(
                f"candidate_rule.extension_factor = {self.extension_factor!r} must be finite and "
                "> 1, or an extension would not extend"
            )
        _require_count(self.max_extensions, "candidate_rule.max_extensions", minimum=0)
        if not self.gaps:
            raise TuningUnavailableError("candidate_rule.gaps declares no band to check")
        for index, gap in enumerate(self.gaps):
            _require_count(gap, f"candidate_rule.gaps[{index}]", minimum=2)
        _require_strictly_increasing(self.gaps, "candidate_rule.gaps")
        _require_count(self.max_passes, "candidate_rule.max_passes", minimum=1)
        _require_count(self.max_evaluations, "candidate_rule.max_evaluations", minimum=1)
        _require_count(self.recheck_top_k, "candidate_rule.recheck_top_k", minimum=1)


@dataclass(frozen=True, slots=True)
class TuningSpec:
    """The pre-registered search: the rule its candidates come from, and the seeds it runs on.

    Version 2 has no ``grid``. Candidates are derived per world by ``rule``
    (:func:`derive_candidates`), because a list sized for one world cannot contain another's
    optimum; :func:`tune_par_level`, the v1 single-pair search, now takes its grid explicitly.
    """

    rule: CandidateRule
    seed_start: int
    seed_count: int
    source: str

    @property
    def seeds(self) -> tuple[int, ...]:
        """The tuning seeds -- exactly :func:`tuning_seeds` of this spec."""
        return tuning_seeds(self)


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


@dataclass(frozen=True, slots=True)
class GroupTunedSelection:
    """:func:`tune_group_levels`' outcome, carrying enough to argue with it.

    ``levels`` is returned on every path, refusal or not, because a refused split must still show
    what the search reached. ``evaluations`` counts distinct level vectors, each costed at every
    tuning seed; ``passes`` counts coordinate passes; ``candidates`` is each group's FINAL box,
    extensions included, so a reader sees what was searched as well as what was chosen.

    ``ranked`` is the in-sample recheck's input (R1, ``uplift/regret.py``): the distinct level
    vectors the search evaluated with their mean TUNING costs, ascending, ties in EVALUATION
    order, truncated to ``min(rule.recheck_top_k, evaluations)``. Evaluation order is the search's
    own tie-break -- a tie keeps the point costed first -- and the search moves only on a strict
    improvement, so the held point is the first vector costed at the minimum of everything it
    costed. ``ranked[0]`` is therefore ``(levels, mean_cost)`` on EVERY path, refusals included.

    Facts enforced at construction, so no record can carry their negation:
    ``mean_cost <= incumbent_cost`` (the search starts at the incumbent and accepts only strict
    improvements -- raised as an ``AssertionError`` naming the invariant); ``converged`` holds
    exactly when ``refusal`` is ``None``; and ``ranked`` is non-empty, ascending, distinct, no
    longer than ``evaluations``, and headed by the selection whenever it converged.
    """

    levels: GroupLevels
    mean_cost: float
    incumbent_cost: float
    evaluations: int
    passes: int
    converged: bool
    refusal: str | None
    candidates: Mapping[str, tuple[int, ...]]
    tie_broken: bool
    ranked: tuple[tuple[GroupLevels, float], ...]

    def __post_init__(self) -> None:
        if not self.mean_cost <= self.incumbent_cost:
            raise AssertionError(
                "invariant mean_cost <= incumbent_cost violated: a search that starts at the "
                "incumbent and accepts only strict improvements cannot end costlier than it "
                f"({self.mean_cost!r} > {self.incumbent_cost!r})"
            )
        if self.converged == (self.refusal is not None):
            raise TuningUnavailableError(
                f"converged={self.converged} with refusal={self.refusal!r}: a selection is "
                "converged exactly when it carries no refusal"
            )
        if not self.ranked:
            raise TuningUnavailableError("ranked is empty, yet every search costs its incumbent")
        costs = [cost for _, cost in self.ranked]
        if not all(earlier <= later for earlier, later in itertools.pairwise(costs)):
            raise TuningUnavailableError(f"ranked is not ascending by mean tuning cost: {costs}")
        if len({vector for vector, _ in self.ranked}) != len(self.ranked):
            raise TuningUnavailableError("ranked lists one level vector more than once")
        if len(self.ranked) > self.evaluations:
            raise TuningUnavailableError(
                f"ranked lists {len(self.ranked)} vectors, but only {self.evaluations} were "
                "evaluated"
            )
        if self.converged and self.ranked[0] != (self.levels, self.mean_cost):
            raise TuningUnavailableError(
                "a converged selection must head ranked -- it is the cheapest vector the search "
                f"costed -- but ranked[0] is {self.ranked[0]!r}"
            )


@dataclass(frozen=True, slots=True)
class ThreeTermSplit:
    """``B - D = (B - E) + (E - O) + (O - D)`` (R5.46): each term in float, and the residual.

    Each term is ONE rounded subtraction of the two means it names. ``residual_float`` --
    ``regret - (tuning_gap + achievable + residual)``, summed left to right in IEEE 754 -- is
    REPORTED, not asserted zero (finding 56). No exactness flag is carried: over
    ``fractions.Fraction`` the identity is a theorem for every finite input, so a flag computing
    it could never be ``False`` (R5). What can fail is that each term is the float difference it
    names, and Property 81 asserts exactly that.
    """

    tuning_gap: float
    achievable_information_value: float
    residual_information_value: float
    information_ceiling: float
    regret: float
    residual_float: float


def load_tuning_spec(path: Path = DEFAULT_TUNING_PATH) -> TuningSpec:
    """Read and validate the committed search spec (version 2). Raises rather than defaulting.

    Every key is required and every unknown key is refused, so each value in the file is one this
    reader reads -- including ``budget``, whose two projections are checked against the rule they
    project. The version is checked first, so a version-1 file is refused by its version and not
    by the first v1 key the reader happens to meet.
    """
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:  # pragma: no cover - exercised by a property
        raise TuningUnavailableError(f"tuning spec unreadable at {path}: {error}") from error
    document = _mapping(raw, "the tuning spec", path)
    version = _field(document, "version", "", path)
    if isinstance(version, bool) or not isinstance(version, int) or version != TUNING_SPEC_VERSION:
        raise _refusal(
            path,
            "version",
            f"{version!r}; this reader implements version {TUNING_SPEC_VERSION} only (version 1 "
            "was finding 63's fixed grid, kept in the file as a comment)",
        )
    _only_keys(document, _TOP_LEVEL_KEYS, "the tuning spec", path)
    rule = _read_rule(document, path)
    start, count = _read_seeds(document, path)
    _check_budget(document, rule=rule, seed_count=count, path=path)
    return TuningSpec(rule=rule, seed_start=start, seed_count=count, source=str(path))


def _read_rule(document: Mapping[str, object], path: Path) -> CandidateRule:
    key = "candidate_rule"
    block = _mapping(_field(document, key, "", path), key, path)
    _only_keys(block, _RULE_KEYS, key, path)
    _text(_field(block, "provenance", key, path), f"{key}.provenance", path)
    review_min = _real(_field(block, "review_min", key, path), f"{key}.review_min", path)
    z_values = _reals(_field(block, "z_values", key, path), f"{key}.z_values", path)
    factor = _real(_field(block, "extension_factor", key, path), f"{key}.extension_factor", path)
    extensions = _whole(_field(block, "max_extensions", key, path), f"{key}.max_extensions", path)
    gaps = _wholes(_field(block, "gaps", key, path), f"{key}.gaps", path)
    passes = _whole(_field(block, "max_passes", key, path), f"{key}.max_passes", path)
    budget = _whole(_field(block, "max_evaluations", key, path), f"{key}.max_evaluations", path)
    top_k = _whole(_field(block, "recheck_top_k", key, path), f"{key}.recheck_top_k", path)
    try:
        return CandidateRule(
            review_min=review_min,
            z_values=z_values,
            extension_factor=factor,
            max_extensions=extensions,
            gaps=gaps,
            max_passes=passes,
            max_evaluations=budget,
            recheck_top_k=top_k,
        )
    except TuningUnavailableError as error:
        raise _refusal(path, key, error) from error


def _read_seeds(document: Mapping[str, object], path: Path) -> tuple[int, int]:
    key = "tuning_seeds"
    block = _mapping(_field(document, key, "", path), key, path)
    _only_keys(block, _SEED_KEYS, key, path)
    start = _whole(_field(block, "start", key, path), f"{key}.start", path)
    count = _whole(_field(block, "count", key, path), f"{key}.count", path)
    if count <= 0:
        raise _refusal(path, f"{key}.count", f"{count} is not positive")
    if start < 0:
        raise _refusal(path, f"{key}.start", f"{start} is negative")
    return start, count


def _check_budget(
    document: Mapping[str, object], *, rule: CandidateRule, seed_count: int, path: Path
) -> None:
    """Read ``budget`` and refuse a projection the committed rule no longer produces.

    Two projections, each re-derived here so an edit to any bound cannot leave a stale cost
    estimate behind it -- a projection nothing re-derives is a number nobody checked:

    * the search, ``max_evaluations x tuning_seeds.count`` arm-replicates -- the most one world's
      search can spend;
    * the in-sample recheck (R1), ``(recheck_top_k + 4 x recheck_max_groups) x
      recheck_measurement_replicates`` -- every vector ``ranked`` carries plus every
      :func:`neighbours` move of the selection (at most four per group), each re-measured on
      every measurement seed. Its two inputs are declared beside it, and Property 81 binds them
      to the committed world and to ``uplift.yml::twin-regret``'s ``--replicates``.
    """
    key = "budget"
    block = _mapping(_field(document, key, "", path), key, path)
    _only_keys(block, _BUDGET_KEYS, key, path)
    _text(_field(block, "provenance", key, path), f"{key}.provenance", path)
    run = f"{key}.measured_reference_run"
    _text(_field(block, "measured_reference_run", key, path), run, path)
    measured = f"{key}.measured_arm_replicates"
    replicates = _whole(_field(block, "measured_arm_replicates", key, path), measured, path)
    step = f"{key}.measured_measure_step_minutes"
    minutes = _real(_field(block, "measured_measure_step_minutes", key, path), step, path)
    if replicates <= 0 or minutes <= 0.0:
        raise _refusal(path, key, "a measured cost must be positive to project from")
    projected_key = f"{key}.projected_max_tuning_arm_replicates"
    projected = _whole(
        _field(block, "projected_max_tuning_arm_replicates", key, path), projected_key, path
    )
    derived = rule.max_evaluations * seed_count
    if projected != derived:
        raise _refusal(
            path,
            projected_key,
            f"{projected} is not candidate_rule.max_evaluations x tuning_seeds.count = {derived}",
        )
    replicates_key = f"{key}.recheck_measurement_replicates"
    measurement = _whole(
        _field(block, "recheck_measurement_replicates", key, path), replicates_key, path
    )
    groups_key = f"{key}.recheck_max_groups"
    groups = _whole(_field(block, "recheck_max_groups", key, path), groups_key, path)
    if measurement <= 0 or groups <= 0:
        raise _refusal(
            path, key, "the recheck must be projected over a positive replicate and group count"
        )
    recheck_key = f"{key}.projected_max_recheck_arm_replicates"
    recheck = _whole(
        _field(block, "projected_max_recheck_arm_replicates", key, path), recheck_key, path
    )
    vectors = rule.recheck_top_k + len(_UNIT_MOVES) * groups
    if recheck != vectors * measurement:
        raise _refusal(
            path,
            recheck_key,
            f"{recheck} is not (candidate_rule.recheck_top_k + {len(_UNIT_MOVES)} x {groups_key})"
            f" x {replicates_key} = {vectors * measurement}",
        )


def _refusal(path: Path, key: str, reason: object) -> TuningUnavailableError:
    return TuningUnavailableError(
        f"{path.as_posix()} declares an inadmissible {key}: {reason}. Refused, not repaired: a "
        "defaulted search is a search nobody pre-registered"
    )


def _field(block: Mapping[str, object], name: str, prefix: str, path: Path) -> object:
    """``block[name]``, or a refusal naming the key's full path -- never a default."""
    if name not in block:
        qualified = f"{prefix}.{name}" if prefix else name
        raise TuningUnavailableError(
            f"{path.as_posix()} declares no value at {qualified}. This is NOT defaulted: a "
            "default would substitute an unreviewed number for a committed one"
        )
    return block[name]


def _mapping(raw: object, key: str, path: Path) -> dict[str, object]:
    if not isinstance(raw, dict) or not all(isinstance(name, str) for name in raw):
        raise _refusal(path, key, f"a {type(raw).__name__}, not a mapping keyed by names")
    return raw


def _only_keys(block: Mapping[str, object], allowed: frozenset[str], key: str, path: Path) -> None:
    unknown = sorted(set(block) - allowed)
    if unknown:
        raise _refusal(path, key, f"unknown key(s) {', '.join(unknown)}")


def _real(raw: object, key: str, path: Path) -> float:
    if isinstance(raw, bool) or not isinstance(raw, int | float) or not math.isfinite(raw):
        raise _refusal(path, key, f"{raw!r} is not a finite real number")
    return float(raw)


def _reals(raw: object, key: str, path: Path) -> tuple[float, ...]:
    if not isinstance(raw, list):
        raise _refusal(path, key, f"a {type(raw).__name__}, not a list")
    return tuple(_real(value, f"{key}[{index}]", path) for index, value in enumerate(raw))


def _whole(raw: object, key: str, path: Path) -> int:
    if isinstance(raw, bool) or not isinstance(raw, int):
        raise _refusal(path, key, f"{raw!r} is not an integer")
    return raw


def _wholes(raw: object, key: str, path: Path) -> tuple[int, ...]:
    if not isinstance(raw, list):
        raise _refusal(path, key, f"a {type(raw).__name__}, not a list")
    return tuple(_whole(value, f"{key}[{index}]", path) for index, value in enumerate(raw))


def _text(raw: object, key: str, path: Path) -> str:
    if not isinstance(raw, str) or not raw.strip():
        raise _refusal(path, key, f"{raw!r} is not a non-empty string")
    return raw


def _require_count(value: int, name: str, *, minimum: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise TuningUnavailableError(f"{name} = {value!r} must be an integer >= {minimum}")


def _require_strictly_increasing(values: Sequence[float], name: str) -> None:
    """Refuse a repeated or out-of-order value, so a duplicate cannot hide inside a list."""
    for earlier, later in itertools.pairwise(values):
        if not earlier < later:
            raise TuningUnavailableError(
                f"{name} must be strictly increasing, but {later!r} follows {earlier!r}"
            )


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

    The bias direction depends on the question, so it is stated for both (R1; the canonical
    statement is ``comparator-tuning.yaml``'s). Levels selected as the minimum of noisy TUNING
    means are, in expectation, costlier on other seeds than the best static policy (the winner's
    curse), so out-of-sample tuning biases the ceiling UP: the safe side for finding 63's question
    ("is the ceiling small?"), the UNSAFE side for checkpoint B-prime's ("is it large enough?").
    So the comparator also reports an in-sample recheck, biased the other way, and B-prime binds
    on both.
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
    grid: Sequence[GridPoint],
    cost_of: Callable[[int, GridPoint], float],
    measurement_replicates: int,
) -> TunedSelection:
    """Search ONE shared ``(s, S)`` over a caller-supplied grid; return it with its whole surface.

    The v1 search, kept working. Version 2's spec carries no grid, so the grid is an argument, and
    the refusals the v1 loader applied to it -- an empty grid, a repeated point -- apply here,
    before any evaluation. `cost_of(seed, point)` is the ONLY thing that touches a simulation or
    an objective (see the module docstring). Per-group tuning is :func:`tune_group_levels`.

    Refuses -- never falls back -- when the seed ranges overlap, when the grid is empty or repeats
    a point, or when a candidate produces a non-finite cost. A level obtained past any of those is
    not the minimum of the grid that was supplied.
    """
    overlap = seed_overlap_refusal(spec, measurement_replicates=measurement_replicates)
    if overlap is not None:
        raise TuningUnavailableError(overlap)
    points = tuple(grid)
    if not points:
        raise TuningUnavailableError("the supplied grid declares no candidates")
    if len(set(points)) != len(points):
        # Refused rather than de-duplicated: the supplied grid and the searched grid would differ,
        # and the candidate count a caller reports would be wrong.
        raise TuningUnavailableError("the supplied grid declares a candidate more than once")

    seeds = tuning_seeds(spec)
    surface: dict[GridPoint, float] = {}
    for point in points:
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
        candidates=len(points),
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


def three_term_split(
    *, reference: float, tuned: float, structure_aware: float, hindsight: float
) -> ThreeTermSplit:
    """Split ``reference - hindsight`` through arms E and O (R5.46), exactly where it can be.

    ``tuning_gap = reference - tuned``; ``achievable_information_value = tuned -
    structure_aware``; ``residual_information_value = structure_aware - hindsight``;
    ``information_ceiling = tuned - hindsight``; ``regret = reference - hindsight``. Each is ONE
    rounded subtraction of the two means it names. Their sum is not exact in IEEE 754, so
    ``residual_float`` reports how far it lands from ``regret`` (R2.10, finding 56).

    Raises:
        TuningUnavailableError: If any mean is non-finite. A nan or an infinity has no exact value
            to split, and a split of one would read as a measured number.
    """
    means = {
        "reference": reference,
        "tuned": tuned,
        "structure_aware": structure_aware,
        "hindsight": hindsight,
    }
    for name, value in means.items():
        if not math.isfinite(value):
            raise TuningUnavailableError(f"cannot split a non-finite {name} mean: {value!r}")
    tuning_gap = reference - tuned
    achievable = tuned - structure_aware
    residual = structure_aware - hindsight
    regret = reference - hindsight
    return ThreeTermSplit(
        tuning_gap=tuning_gap,
        achievable_information_value=achievable,
        residual_information_value=residual,
        information_ceiling=tuned - hindsight,
        regret=regret,
        residual_float=regret - (tuning_gap + achievable + residual),
    )


# ---------------------------------------------------------------------------
# Version 2: candidates derived per world, searched per supplier group
# ---------------------------------------------------------------------------


def derive_candidates(
    world: ResolvedWorld | None,
    groups: Sequence[str],
    rule: CandidateRule,
    *,
    rate_per_sku_per_min: float,
) -> dict[str, tuple[int, ...]]:
    """Each group's candidate order-up-to levels ``S``, by the committed rule.

    For group ``g`` with declared mean lead time ``L`` (zero when structure 3 is off) and
    log-scale sd ``v``, a per-SKU demand rate ``lam`` and the rule's review period ``R``::

        mu    = lam * (L + R)
        sigma = sqrt(mu + (lam * L)**2 * (exp(v**2) - 1))
        S_z   = max(1, round(mu + z * sigma))        for z in rule.z_values

    deduplicated and ascending. ``mu`` is the mean demand a base-stock level must cover -- over
    the lead time plus one review -- and the variance is the Poisson count over that interval plus
    the lead time's own lognormal variance (``L**2 (exp(v**2) - 1)``) carried through the rate. So
    the box scales with the world instead of being sized for one. ``exp(x) - 1`` is evaluated as
    ``math.expm1``, the same quantity without the cancellation; ``round`` is Python's
    half-to-even, so the candidates are reproducible from this text.

    With structure 3 off every group's lead time is zero by the rule, whatever the group is called;
    :func:`uplift.tuned_static.sku_groups` then yields the one group ``"all"``.

    Raises:
        TuningUnavailableError: On a rate that is not finite and positive; an empty, blank or
            repeated group; with structure 3 on, a group that is not a declared supplier; or a
            derived level too large to be finite.
    """
    if not (math.isfinite(rate_per_sku_per_min) and rate_per_sku_per_min > 0.0):
        raise TuningUnavailableError(
            f"rate_per_sku_per_min = {rate_per_sku_per_min!r} must be finite and > 0; no demand "
            "derives no candidate"
        )
    names = _distinct_groups(groups)
    supply = None if world is None else world.supply
    derived: dict[str, tuple[int, ...]] = {}
    for group in names:
        lead_time, log_sd = _group_lead_time(supply, group)
        mean = rate_per_sku_per_min * (lead_time + rule.review_min)
        variance = mean + (rate_per_sku_per_min * lead_time) ** 2 * math.expm1(log_sd**2)
        spread = math.sqrt(variance)
        levels: set[int] = set()
        for z in rule.z_values:
            protected = mean + z * spread
            if not math.isfinite(protected):
                raise TuningUnavailableError(
                    f"group {group!r} derives a non-finite level at z={z!r} (mean={mean!r}, "
                    f"sd={spread!r}); no candidate can be rounded from it"
                )
            levels.add(max(1, round(protected)))
        derived[group] = tuple(sorted(levels))
    return derived


def neighbours(levels: GroupLevels) -> tuple[GroupLevels, ...]:
    """Every level vector one unit move from ``levels``: one group moved, every other held.

    For each group in sorted order, its four moves in this declared order -- ``(s - 1, S)``,
    ``(s + 1, S)``, ``(s, S - 1)``, ``(s, S + 1)`` -- each kept only when ``0 <= s < S``: so
    ``1 + [s >= 1] + 2 [S - s >= 2]`` per group, one to four. A function of ``levels`` alone, so
    the order is deterministic.

    Moving ``s`` with ``S`` held is R3's repair: the first version-2 certificate moved ``S`` with
    the band ``S - s`` kept, so it never moved ``s`` at the refined ``S``. The converse blind spot
    is why :func:`tune_group_levels` keeps those band-kept moves BESIDE these: at base-stock
    ``(S - 1, S)`` the move ``(s, S - 1)`` is invalid, so these four alone can never lower ``S``.
    The comparator's in-sample recheck re-measures these vectors around the selection.
    """
    # `uplift.tuned_static` imports this module at its top, so a module-scope import is a cycle.
    from uplift import tuned_static

    return tuple(
        tuned_static.GroupLevels({**levels.levels, group: moved})
        for group, point in levels.levels.items()
        for moved in _unit_moves(point)
    )


def tune_group_levels(
    *,
    groups: Sequence[str],
    candidates: Mapping[str, Sequence[int]],
    incumbent: GridPoint,
    seeds: Sequence[int],
    cost_of: Callable[[int, GroupLevels], float],
    rule: CandidateRule,
) -> GroupTunedSelection:
    """Tune one ``(s, S)`` per group by a deterministic local search; report, never raise, its end.

    ``cost_of(seed, levels)`` is the only thing that touches a simulation. One EVALUATION is one
    level vector costed at every seed (sorted, so the mean's summation order is fixed) and cached,
    so no vector is costed twice. The steps:

    1. Every group starts at ``incumbent``; its cost is ``incumbent_cost``.
    2. Coordinate passes over the groups in sorted order: each tries base-stock ``(S - 1, S)`` for
       every candidate ``S``, and moves only on a STRICT improvement.
    3. A group whose held ``S`` is at or above its box's largest candidate gets one more, the next
       term of the geometric sequence (``round(extension_factor x max)``, at least ``max + 1``),
       up to ``max_extensions`` times; likewise downward (``round(min / factor)``, floored at 1)
       while the smallest exceeds 1. One point per extension is enough: step 5 bisects whatever
       bracket an extension opens.
    4. Passes repeat until one moves nothing, or ``max_passes``.
    5. Refinement: around each held ``S``, try ``S +- step`` from half the widest bracket to its
       evaluated neighbours, halving to 1, the band ``S - s`` kept; then re-try base-stock
       ``(S - 1, S)`` at each group's refined ``S``, which a band-keeping move never returns to.
    6. Gap check: ``(S - g, S)`` for each ``g`` in ``gaps`` below ``S``.
    7. Unit-step certificate, per group: the band-kept shifts ``S -+ 1``, then
       :func:`neighbours`' four moves of ``s`` or ``S`` alone (R3). Any strict improvement is
       taken and every group is scanned again; when none improves, the result is a certified
       unit-step LOCAL minimum over both neighbourhoods -- ``converged``. A global minimum is not
       claimed; over a non-convex cost it may not be one.

    Ties keep the point tried first: a trial tying the held point leaves the held point, and of
    two improving trials that tie, the earlier in its step's declared order wins -- lowest ``S``
    first in steps 2 and 5, smallest gap first in step 6, step 7's order as listed. Either sets
    ``tie_broken``. ``ranked`` applies the same rule across steps (equal costs rank in evaluation
    order), which is why ``ranked[0]`` is the selection.

    REFUSALS, reported with the levels reached: :data:`BOUNDARY_REFUSAL` when, after step 4, a
    group holds the largest ``S`` evaluated for it with its upward extensions spent (or the
    smallest, above 1, with its downward ones spent) -- its minimum may lie outside the box; and
    :data:`NON_CONVERGENCE_REFUSAL` when ``max_evaluations`` runs out before step 7 holds.

    **The caller must run** :func:`seed_overlap_refusal` **first.** Unlike
    :func:`tune_par_level`, this function is not told the measurement range, so the guard that
    keeps the levels out of sample cannot live inside it.

    Raises:
        TuningUnavailableError: On an empty, blank or repeated group or seed; candidates that do
            not cover exactly the groups; a candidate that is not an integer >= 1, or repeats; or
            a non-finite cost.
    """
    # Imported here: `uplift.tuned_static` imports `GridPoint` from this module, so a module-scope
    # import would be a cycle. Both modules are fully loaded by the time this runs.
    from uplift import tuned_static

    names = _distinct_groups(groups)
    declared = sorted(candidates)
    if declared != list(names):
        raise TuningUnavailableError(
            f"candidates cover {declared} but the groups are {list(names)}; a group without "
            "candidates, or candidates for no group, is a search nobody declared"
        )
    boxes = {group: _candidate_levels(candidates[group], group) for group in names}
    search = _GroupSearch(
        names=names,
        boxes=boxes,
        incumbent=incumbent,
        seeds=_distinct_seeds(seeds),
        cost_of=cost_of,
        rule=rule,
        make_levels=tuned_static.GroupLevels,
    )
    refusal: str | None = None
    try:
        search.coordinate_passes()
        refusal = search.boundary_refusal()
        if refusal is None:
            search.refine()
            search.retry_base_stock()
            search.check_gaps()
            search.certify()
    except _BudgetSpentError:
        refusal = (
            f"{NON_CONVERGENCE_REFUSAL}: max_evaluations={rule.max_evaluations} was spent after "
            f"{search.passes} pass(es), before the unit-step certificate held, so the levels are "
            "the best point found and not a certified minimum"
        )
    selection = search.selection(refusal)
    logger.info(
        "arm_e_group_levels_selected",
        levels=selection.levels.as_dict(),
        mean_cost=selection.mean_cost,
        incumbent_cost=selection.incumbent_cost,
        evaluations=selection.evaluations,
        passes=selection.passes,
        converged=selection.converged,
        refusal=selection.refusal,
        tie_broken=selection.tie_broken,
    )
    return selection


def _distinct_groups(groups: Sequence[str]) -> tuple[str, ...]:
    """The groups, sorted -- refusing an empty list, a blank name and a repeated one."""
    names = tuple(groups)
    if not names:
        raise TuningUnavailableError("no groups were given, so there is nothing to tune")
    for name in names:
        if not isinstance(name, str) or not name.strip():
            raise TuningUnavailableError(f"group name {name!r} is not a non-blank string")
    repeated = sorted({name for name in names if names.count(name) > 1})
    if repeated:
        raise TuningUnavailableError(f"group(s) {', '.join(repeated)} named more than once")
    return tuple(sorted(names))


def _group_lead_time(supply: SupplyStructure | None, group: str) -> tuple[float, float]:
    """A group's supplier's ``(mean lead time, log-scale sd)``; ``(0, 0)`` with structure 3 off."""
    if supply is None:
        return 0.0, 0.0
    spec = supply.suppliers.get(group)
    if spec is None:
        known = ", ".join(sorted(supply.suppliers))
        raise TuningUnavailableError(
            f"group {group!r} is not a declared supplier (known: {known}); with structure 3 on "
            "every group is a supplier, because its lead time is what sizes its candidates"
        )
    return spec.mean_lead_time_min, spec.log_sd


def _candidate_levels(values: Sequence[int], group: str) -> list[int]:
    """A group's candidates, ascending -- refusing an empty list, a non-integer and a repeat."""
    levels = list(values)
    if not levels:
        raise TuningUnavailableError(f"group {group!r} has no candidate order-up-to level")
    for level in levels:
        if isinstance(level, bool) or not isinstance(level, int) or level < 1:
            raise TuningUnavailableError(
                f"group {group!r} candidate {level!r} is not an integer >= 1"
            )
    if len(set(levels)) != len(levels):
        raise TuningUnavailableError(f"group {group!r} declares a candidate more than once")
    return sorted(levels)


def _distinct_seeds(seeds: Sequence[int]) -> tuple[int, ...]:
    """The seeds, sorted -- refusing none at all, and a repeat that would weight a seed twice."""
    ordered = tuple(sorted(seeds))
    if not ordered:
        raise TuningUnavailableError("no tuning seeds were given, so no mean can be taken")
    if len(set(ordered)) != len(ordered):
        raise TuningUnavailableError("a tuning seed is repeated, which would weight it twice")
    return ordered


def _base_stock(level: int) -> GridPoint:
    return GridPoint(s=level - 1, S=level)


def _shifts(point: GridPoint, step: int) -> list[GridPoint]:
    """``point`` moved by ``-step``, then ``+step``, in ``S`` with its band kept; invalid drop."""
    moved: list[GridPoint] = []
    for delta in (-step, step):
        if point.s + delta >= 0:
            moved.append(GridPoint(s=point.s + delta, S=point.S + delta))
    return moved


def _unit_moves(point: GridPoint) -> list[GridPoint]:
    """``point``'s :data:`_UNIT_MOVES`, in order, keeping only pairs with ``0 <= s < S``."""
    moved: list[GridPoint] = []
    for delta_s, delta_upper in _UNIT_MOVES:
        lower, upper = point.s + delta_s, point.S + delta_upper
        if 0 <= lower < upper:
            moved.append(GridPoint(s=lower, S=upper))
    return moved


class _BudgetSpentError(Exception):
    """``max_evaluations`` is spent. Internal: :func:`tune_group_levels` reports it."""


class _GroupSearch:
    """The mutable state of one :func:`tune_group_levels` call. Private; never escapes it.

    Constructing it costs the incumbent -- the first evaluation, which ``max_evaluations >= 1``
    always affords -- so every later step compares against a measured point.
    """

    def __init__(
        self,
        *,
        names: tuple[str, ...],
        boxes: dict[str, list[int]],
        incumbent: GridPoint,
        seeds: tuple[int, ...],
        cost_of: Callable[[int, GroupLevels], float],
        rule: CandidateRule,
        make_levels: Callable[[Mapping[str, GridPoint]], GroupLevels],
    ) -> None:
        self._names = names
        self._boxes = boxes
        self._seeds = seeds
        self._cost_of = cost_of
        self._rule = rule
        self._make_levels = make_levels
        self._cache: dict[tuple[tuple[int, int], ...], float] = {}
        # Every distinct vector costed, with its mean, in evaluation order: `ranked`'s source.
        self._evaluated: list[tuple[GroupLevels, float]] = []
        self._seen: dict[str, set[int]] = {name: set() for name in names}
        self._extended_up = dict.fromkeys(names, 0)
        self._extended_down = dict.fromkeys(names, 0)
        self.evaluations = 0
        self.passes = 0
        self.tie_broken = False
        self._held: dict[str, GridPoint] = dict.fromkeys(names, incumbent)
        self.incumbent_cost = self._evaluate(self._held)
        self._held_cost = self.incumbent_cost

    def coordinate_passes(self) -> None:
        """Steps 2-4."""
        while self.passes < self._rule.max_passes:
            self.passes += 1
            moved = False
            for group in self._names:
                stepped = self._coordinate_step(group)
                moved = moved or stepped
            if not moved:
                return

    def boundary_refusal(self) -> str | None:
        """Step 3's refusal, or ``None`` when every group sits inside what was evaluated for it."""
        for group in self._names:
            held = self._held[group].S
            seen = self._seen[group]
            if held >= max(seen) and self._extended_up[group] >= self._rule.max_extensions:
                return (
                    f"{BOUNDARY_REFUSAL}: group {group!r} holds S={held}, the largest S evaluated "
                    f"for it after {self._extended_up[group]} upward extension(s), so its minimum "
                    "may lie above the search box"
                )
            lowest = min(seen)
            spent_down = self._extended_down[group] >= self._rule.max_extensions
            if held <= lowest and lowest > 1 and spent_down:
                return (
                    f"{BOUNDARY_REFUSAL}: group {group!r} holds S={held}, the smallest S "
                    f"evaluated for it after {self._extended_down[group]} downward extension(s), "
                    "so its minimum may lie below the search box"
                )
        return None

    def refine(self) -> None:
        """Step 5."""
        for group in self._names:
            step = self._initial_step(group)
            while True:
                self._scan(group, _shifts(self._held[group], step))
                if step == 1:
                    break
                step = max(1, step // 2)

    def retry_base_stock(self) -> None:
        """Step 5, last: base-stock ``(S - 1, S)`` at each group's refined ``S`` (R3)."""
        for group in self._names:
            self._scan(group, [_base_stock(self._held[group].S)])

    def check_gaps(self) -> None:
        """Step 6."""
        for group in self._names:
            upper = self._held[group].S
            bands = [gap for gap in self._rule.gaps if gap < upper]
            self._scan(group, [GridPoint(s=upper - gap, S=upper) for gap in bands])

    def certify(self) -> None:
        """Step 7: band-kept shifts, then :func:`neighbours`' moves, until none improves any group.

        A round that moves nothing scanned every member of ``neighbours(levels)`` from one held
        point, so the certificate holds exactly when no neighbour -- and no band-kept shift -- is
        strictly cheaper. Bounded by ``max_evaluations``.
        """
        while True:
            moved = False
            for group in self._names:
                held = self._held[group]
                stepped = self._scan(group, [*_shifts(held, 1), *_unit_moves(held)])
                moved = moved or stepped
            if not moved:
                return

    def selection(self, refusal: str | None) -> GroupTunedSelection:
        return GroupTunedSelection(
            levels=self._make_levels(self._held),
            mean_cost=self._held_cost,
            incumbent_cost=self.incumbent_cost,
            evaluations=self.evaluations,
            passes=self.passes,
            converged=refusal is None,
            refusal=refusal,
            candidates={group: tuple(self._boxes[group]) for group in self._names},
            tie_broken=self.tie_broken,
            ranked=self._ranked(),
        )

    def _ranked(self) -> tuple[tuple[GroupLevels, float], ...]:
        """The ``recheck_top_k`` cheapest vectors costed, equal costs in evaluation order."""
        order = sorted(
            range(len(self._evaluated)), key=lambda index: (self._evaluated[index][1], index)
        )
        return tuple(self._evaluated[index] for index in order[: self._rule.recheck_top_k])

    def _evaluate(self, levels: Mapping[str, GridPoint]) -> float:
        """The mean cost of ``levels`` over every seed -- from the cache when already costed."""
        key = tuple((levels[name].s, levels[name].S) for name in self._names)
        known = self._cache.get(key)
        if known is not None:
            return known
        if self.evaluations >= self._rule.max_evaluations:
            raise _BudgetSpentError
        record = self._make_levels(levels)
        costs: list[float] = []
        for seed in self._seeds:
            cost = self._cost_of(seed, record)
            if not math.isfinite(cost):
                raise TuningUnavailableError(
                    f"levels {record.as_dict()} produced a non-finite cost at seed {seed}: "
                    f"{cost!r}; a minimum over it would be a minimum of nothing"
                )
            costs.append(cost)
        mean = sequence_mean(costs)
        if not math.isfinite(mean):
            raise TuningUnavailableError(
                f"levels {record.as_dict()} have a non-finite mean cost: {mean!r}"
            )
        self.evaluations += 1
        self._cache[key] = mean
        self._evaluated.append((record, mean))
        for name in self._names:
            self._seen[name].add(levels[name].S)
        return mean

    def _scan(self, group: str, points: Sequence[GridPoint]) -> bool:
        """Move ``group`` to the cheapest of ``points`` if it STRICTLY beats the held point.

        Callers list points in their step's declared order (see :func:`tune_group_levels`), and a
        tie keeps the earlier point. When the budget is spent mid-scan, the best point already
        costed is still taken before the refusal propagates, so the levels returned are never
        worse than anything this scan evaluated.
        """
        held = self._held[group]
        best: GridPoint | None = None
        best_cost = self._held_cost
        tied = False
        try:
            for point in points:
                if point == held:
                    continue
                cost = self._evaluate({**self._held, group: point})
                if cost < best_cost:
                    best, best_cost, tied = point, cost, False
                elif cost == best_cost:
                    tied = True
        except _BudgetSpentError:
            self._settle(group, best, best_cost, tied=tied)
            raise
        self._settle(group, best, best_cost, tied=tied)
        return best is not None

    def _settle(self, group: str, best: GridPoint | None, cost: float, *, tied: bool) -> None:
        if tied:
            self.tie_broken = True
        if best is not None:
            self._held = {**self._held, group: best}
            self._held_cost = cost

    def _coordinate_step(self, group: str) -> bool:
        """One group's best base-stock point, the others held, extending the box at its edges."""
        moved = False
        while True:
            if self._scan(group, [_base_stock(level) for level in self._boxes[group]]):
                moved = True
            if not self._extend(group):
                return moved

    def _extend(self, group: str) -> bool:
        """Step 3: grow the box by one geometric term when the held ``S`` sits on an edge."""
        box = self._boxes[group]
        held = self._held[group].S
        factor = self._rule.extension_factor
        if held >= box[-1] and self._extended_up[group] < self._rule.max_extensions:
            box.append(max(box[-1] + 1, round(box[-1] * factor)))
            self._extended_up[group] += 1
            return True
        lowest = box[0]
        room_down = self._extended_down[group] < self._rule.max_extensions
        if held <= lowest and lowest > 1 and room_down:
            box.insert(0, min(lowest - 1, max(1, round(lowest / factor))))
            self._extended_down[group] += 1
            return True
        return False

    def _initial_step(self, group: str) -> int:
        """Half the widest gap from the held ``S`` to its nearest evaluated neighbours, >= 1."""
        held = self._held[group].S
        below = [level for level in self._seen[group] if level < held]
        above = [level for level in self._seen[group] if level > held]
        widths: list[int] = []
        if below:
            widths.append(held - max(below))
        if above:
            widths.append(min(above) - held)
        if not widths:
            return 1
        return max(1, max(widths) // 2)
