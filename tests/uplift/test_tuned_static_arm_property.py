# Feature: decision-quality-proof, Property 81: The tuned static arm is the pre-registered
# search's out-of-sample minimum, never worse than the incumbent, and the decomposition it
# induces is exact
"""Arm E is the pre-registered search's minimum, never worse than the incumbent, split exactly.

Session 10 (ADR-055 D2.6, finding 61) wrote this property over a fixed grid. Leaf 13.7a re-derives
arm E per world and RETITLES it as a precondition correction: "the grid's minimum" was true and
beside the point once the grid could not contain the world's optimum. Subjects:
``uplift/tuning.py`` -- ``CandidateRule``, ``load_tuning_spec``, ``derive_candidates``,
``tune_group_levels``, ``GroupTunedSelection``, ``neighbours``, ``three_term_split``, and the v1
functions that stay (``GridPoint``, ``tuning_seeds``, ``seed_overlap_refusal``, ``select_levels``,
``tune_par_level``, ``decomposition_identity_residual``); ``uplift/tuned_static.py`` --
``GroupLevels``, ``sku_groups``, ``GroupParLevelReorder``; and the committed version-2 spec at
``infrastructure/quality/comparator-tuning.yaml``.

**Requirements.** R5.1 and R5.3 (the falsification test whose `material` verdict this arm
re-denominates) and R5.33 (the declared scalar objective the candidate costs are measured
against), plus the three criteria added by the R5.4 re-cut: **R5.41** -- a `material` verdict
attributable to baseline mis-tuning may not denominate E3's floor or the published claim;
**R5.42** -- the next comparator run SHALL include a tuned-static comparator arm and record the
information-gap term measured against it; **R5.43** -- that term decides whether R5.8-R5.14 and
R5.21-R5.23 are reinstated as in-scope. R5.42 is the criterion this module exists to make
satisfiable, and R5.43 is why its arithmetic has to be exact rather than approximately right.
**R5.44** re-derives the tuned control per world cell, and **R5.46** adds the three-term split
``B - D = (B - E) + (E - O) + (O - D)``, each term exactly the float difference it names.

**Which landed clauses still apply, and which were rewritten.** KEPT unchanged: the two-term
identity over the rationals and its float falsifier (sections 1-2); ``select_levels``' membership,
argmin, tie-break, unique-minimum and finiteness clauses (3-5, 8); the seed-overlap biconditional
and its boundary (6); ``GridPoint``'s construction clauses (9); the committed seed range's
out-of-sample clause (10). KEPT, MECHANICALLY EDITED: the three ``tune_par_level`` clauses (7, 8),
which now pass the grid explicitly because version 2's ``TuningSpec`` has none; section 7 gains one
clause for the two refusals that moved from the v1 loader to the supplied grid. REWRITTEN, because
it read the v1 grid: "the committed grid is valid and contains the incumbent" became the committed
rule's clauses and the loader's refusals (10), and the incumbent's guarantee moved from grid
membership into the search -- it STARTS at the incumbent and accepts only strict improvements --
where clause (b) proves it. NEW: clauses (a)-(g) of leaf 13.7a in sections 11-15 -- (h), the
seed-overlap refusal, is section 6 -- and the policy class in section 16. WAVE 2b (review findings
R1, R3, R5): the local-minimum clauses check moves of ``s`` alone and ``S`` alone beside the
band-kept ones, with by-construction cases for an ``(S - 3, S)`` optimum and for the base-stock
re-try (12); section 15's ``identity_exact`` clauses became the term-equality clause, because a
flag true for every finite input asserts nothing; the recheck's budget is bound to its sources
(10); and ``ranked`` and ``neighbours``, the in-sample recheck's inputs, are section 17.

**What the subject is for, in one paragraph.** ``regret(incumbent - hindsight)`` mixes the
incumbent's mis-tuning with the value of information, and only the second is anything a
forecaster or a consensus system could win. Arm E is the best STATIC policy, so ``B - E`` is a
tuning gap a search closes with no agent and no forecast, and ``E - D`` is an information ceiling
checkpoint B-prime judges. A WEAK E INFLATES THAT CEILING -- the unsafe direction, a false "room
to win" -- which is why E is re-derived per world, per supplier group, by a search that may not
end worse than the incumbent and refuses rather than reports a box-edge or unfinished optimum.

**What would make this file wrong.** A converged result that a move of ``s``, of ``S``, or of
both with the band kept improves; a result costlier than the incumbent; a cost falling past every
extension that is not refused; a spent budget reported as converged, or exceeded; a result that
depends on the order its inputs are listed in, or a tie resolved by anything but the declared rule;
a candidate box that is not ascending, distinct and >= 1, or that shrinks as lead time grows; a
split term that is not the float difference it names, or a float residual other than the one
reported; an overlapping seed range accepted; a loader that defaults a key, reads a version-1 file,
or keeps a stale budget, or a recheck budget whose inputs drift from their sources; a ``ranked``
that is not the cheapest distinct evaluated vectors headed by the selection, or a neighbourhood
that is invalid, incomplete or out of order; or a per-group policy deciding differently from
``Par_Level_Reorder`` at its own group's levels. Each has a clause below, and each clause can fail.

**Where the exactness stops, stated rather than papered over (R2.10, finding 56).** The
decomposition identity is a theorem over the reals -- the tuned mean appears once with each sign,
so it cancels -- and it is asserted here over ``fractions.Fraction``, where it holds for every
finite input. It is **not** a theorem over IEEE 754, and a clause below constructs the case that
proves so: a large term set against two nearly equal small ones, where the two huge magnitudes
cancel and destroy the small difference between them. Finding 56 was exactly this defect, found by
CI at 500 examples, and the repair then was to correct the claim's **domain** rather than to add a
tolerance. No tolerance appears anywhere in this file.

**No simulation runs here, and that is the feature rather than the gap.** Both searches take an
injected ``cost_of`` and do arithmetic on what they are handed, so every search clause drives a
synthetic, integral cost function: no ``SupplyChainSimulation``, no ``start()``, no ``advance()``,
no subprocess and no network. Worlds are built by hand from ``digital_twin.simulation.world``'s
dataclasses -- a pure module: no engine, no RNG, no clock -- or read through ``load_world``. One
clause imports ``uplift.foresight``, which imports the engine MODULE, to read
``FORESIGHT_WINDOW_MIN``; it constructs nothing. That is what lets the argmin, the tie-break, the
extension and **every refusal** be proven at the fast suite's budget instead of being inferred from
one twin run's output.

**What this file does NOT establish, and it is the larger half.** It does not measure the
information ceiling or settle checkpoint B-prime -- that is task 13.7's CI-only measurement. It
does not show the search finds the twin's GLOBAL minimum: it certifies a unit-step LOCAL one, and
section 12 proves exactly that much over non-convex costs. And it does not show that the caller
runs ``seed_overlap_refusal`` before ``tune_group_levels``, which is not told the measurement
range; that obligation sits with ``uplift/regret.py``.

Budget inherited from the root ``conftest.py`` profile via ``HYPOTHESIS_PROFILE``. **No
``max_examples`` literal appears in this file** (CF-13), and no clause asserts a total.

Locus: ``ci.yml::uplift-verify`` fast shard 2/4 (``tests/uplift/test_[pqrstuvwxyz]*.py``, at the
``ci`` profile). **Not** slow-marked. Committed files are read through the subjects' loaders, except
the two the recheck budget is bound to -- the spec's raw ``budget:`` block and
``.github/workflows/uplift.yml`` -- which one clause reads directly; every read passes
``encoding='utf-8'`` (E-S13-07), and the loader clauses write their variants to ``tmp_path`` with
the same encoding. Every assertion message is ASCII.

**Validates: Requirements 5.1, 5.3, 5.33, 5.41, 5.42, 5.43, 5.44, 5.46**
"""

from __future__ import annotations

import dataclasses
import itertools
import json
import math
import re
from fractions import Fraction
from pathlib import Path
from typing import TYPE_CHECKING, Final

import pytest
import yaml
from hypothesis import given
from hypothesis import strategies as st

from digital_twin.simulation.world import (
    ResolvedWorld,
    SupplierSpec,
    SupplyStructure,
    load_world,
)
from uplift.baselines.par_level_reorder import Par_Level_Reorder
from uplift.interfaces import DecisionPolicy, Observation
from uplift.tuned_static import (
    ALL_SKUS_GROUP,
    TUNED_STATIC_ARM,
    GroupLevels,
    GroupParLevelReorder,
    sku_groups,
)
from uplift.tuning import (
    BOUNDARY_REFUSAL,
    DEFAULT_TUNING_PATH,
    NON_CONVERGENCE_REFUSAL,
    TUNING_SPEC_VERSION,
    CandidateRule,
    GridPoint,
    GroupTunedSelection,
    TuningSpec,
    TuningUnavailableError,
    decomposition_identity_residual,
    derive_candidates,
    load_tuning_spec,
    neighbours,
    seed_overlap_refusal,
    select_levels,
    three_term_split,
    tune_group_levels,
    tune_par_level,
    tuning_seeds,
)

if TYPE_CHECKING:  # pragma: no cover - annotations only
    from collections.abc import Callable, Mapping, Sequence

# ---------------------------------------------------------------------------
# Generators. Valid BY CONSTRUCTION rather than by filtering, so no example is
# discarded and the inherited budget is spent on cases that count.
# ---------------------------------------------------------------------------


def _point(pair: tuple[int, int]) -> GridPoint:
    """A candidate built from a reorder point and a strictly positive band width.

    ``S = s + gap`` with ``gap >= 1`` cannot violate ``0 <= s < S``, so the valid-input clauses
    never spend budget on inputs the constructor refuses. The refusal clauses build their own
    invalid pairs deliberately instead.
    """
    lower, gap = pair
    return GridPoint(s=lower, S=lower + gap)


_LEVEL_PAIRS = st.tuples(
    st.integers(min_value=0, max_value=90), st.integers(min_value=1, max_value=60)
)
_GRID_POINTS = _LEVEL_PAIRS.map(_point)

#: Finite by construction. The subject's finiteness refusal is exercised separately, with
#: non-finite values injected on purpose rather than arrived at by accident.
_COSTS = st.floats(min_value=-1e6, max_value=1e6, allow_nan=False, allow_infinity=False)

#: Integral costs, used wherever a clause needs a strict inequality to be beyond dispute: an
#: integer of magnitude below ``2**53`` is exact as a double, and so is the difference of two.
_EXACT_COSTS = st.integers(min_value=-1_000_000, max_value=1_000_000)
_EXACT_MARGINS = st.integers(min_value=1, max_value=1000)

#: The three means the decomposition is taken over. Wide, signed and finite -- a tuned arm may cost
#: MORE than the incumbent on the measurement seeds, which is the out-of-sample effect the grid
#: file's own comment predicts, so a non-negative generator would exclude the interesting half.
_MEANS = st.floats(min_value=-1e9, max_value=1e9, allow_nan=False, allow_infinity=False)

#: A synthetic rule for the search and loader clauses, so a clause about the search's LOGIC does
#: not move when the committed bounds are re-chosen. Variants are `dataclasses.replace`d from it,
#: which re-runs `CandidateRule`'s own validation. The budget is generous on purpose: a clause
#: that needs a spent budget builds one explicitly.
_SEARCH_RULE: Final[CandidateRule] = CandidateRule(
    review_min=60.0,
    z_values=(-1.0, 0.0, 1.0, 3.0),
    extension_factor=2.0,
    max_extensions=3,
    gaps=(5, 10, 25),
    max_passes=6,
    max_evaluations=5000,
    recheck_top_k=4,
)

#: The group names the generated search problems draw from, in sorted order.
_GROUP_NAMES: Final[tuple[str, ...]] = ("g_a", "g_b", "g_c")

#: Tuning seeds: distinct, and few, because each one multiplies every evaluation's cost calls.
_SEED_LISTS = st.lists(
    st.integers(min_value=1000, max_value=1099), min_size=1, max_size=3, unique=True
)

#: The synthetic pre-registration the loader clauses write and read back.
_LOADER_START: Final[int] = 2000
_LOADER_COUNT: Final[int] = 7
_LOADER_RECHECK_REPLICATES: Final[int] = 3
_LOADER_RECHECK_GROUPS: Final[int] = 2

#: The most unit moves ``neighbours`` may make per group -- ``s - 1``, ``s + 1``, ``S - 1``,
#: ``S + 1`` -- stated independently of the subject, so the recheck projection's factor is checked
#: against the neighbourhood's behaviour (section 17) rather than read off the subject.
_MOVES_PER_GROUP: Final[int] = 4

#: The measuring job the recheck's replicate count is bound to, and how its invocations are read.
_UPLIFT_WORKFLOW: Final[Path] = (
    Path(__file__).resolve().parents[2] / ".github" / "workflows" / "uplift.yml"
)
_MEASURE_COMMAND: Final[re.Pattern[str]] = re.compile(r"python -m uplift\.regret\b([^\n|]*)")
_REPLICATES_FLAG: Final[re.Pattern[str]] = re.compile(r"--replicates[ =](\d+)\b")

#: The extreme case that makes the exactness claim informative instead of decorative. A large term
#: against two nearly equal small ones. Every literal is exactly representable as a double, so the
#: residual it produces is a property of the SUBTRACTION and not of the constants.
_LOSSY_REFERENCE: Final[float] = 1.0
_LOSSY_TUNED: Final[float] = 1e16
_LOSSY_HINDSIGHT: Final[float] = 0.0

#: An ordinary, well-conditioned triple of the same shape. Its residual is exactly zero, which is
#: what stops "the float path can be lossy" from being read as "the float path is always lossy".
_ORDINARY_REFERENCE: Final[float] = 3.0
_ORDINARY_TUNED: Final[float] = 2.0
_ORDINARY_HINDSIGHT: Final[float] = 1.0


def _spec(*, start: int, count: int) -> TuningSpec:
    """A hand-built pre-registration, so the search is tested independently of the real file."""
    return TuningSpec(rule=_SEARCH_RULE, seed_start=start, seed_count=count, source="synthetic")


def _tie_break_key(point: GridPoint) -> tuple[int, int]:
    """The declared tie-break: lowest reorder point, then lowest par band.

    Written here as an independent expectation rather than read off the subject, so a clause that
    compared the subject against itself is impossible.
    """
    return (point.s, point.S)


def _exact_residual(*, reference: float, tuned: float, hindsight: float) -> Fraction:
    """The subject's residual formula, evaluated over the rationals instead of over IEEE 754.

    ``Fraction(x)`` is an exact conversion for any finite double, so this performs the same
    arithmetic ``decomposition_identity_residual`` does, in the domain where the tuned mean's
    cancellation is a theorem.
    """
    regret = Fraction(reference) - Fraction(hindsight)
    tuning_gap = Fraction(reference) - Fraction(tuned)
    information_ceiling = Fraction(tuned) - Fraction(hindsight)
    return regret - (tuning_gap + information_ceiling)


class _CountingCost:
    """A synthetic ``cost_of`` that records every call it receives.

    The call log is what makes the refusal clause assertable at all: a refusal that evaluated the
    grid anyway is not a refusal, and only a count can tell the two apart -- the raised error looks
    identical either way. It also lets the coverage clause assert that the search touched **every**
    declared candidate at **every** declared seed, since a minimum over a subset nobody chose is
    the defect the subject's own docstring names and a call log is the only thing that can see it.
    """

    def __init__(self, *, offender: GridPoint | None = None, offending_value: float = 0.0) -> None:
        """Record nothing yet; optionally make one named candidate return a chosen value."""
        self.calls: list[tuple[int, GridPoint]] = []
        self._offender = offender
        self._offending_value = offending_value

    def __call__(self, seed: int, point: GridPoint) -> float:
        """Log the request, then return the offending value for the offender, a cost otherwise."""
        self.calls.append((seed, point))
        if self._offender is not None and point == self._offender:
            return self._offending_value
        return float(point.s + point.S)

    @property
    def seeds_seen(self) -> set[int]:
        """Every seed the search asked about."""
        return {seed for seed, _ in self.calls}

    @property
    def points_seen(self) -> set[GridPoint]:
        """Every candidate the search asked about."""
        return {point for _, point in self.calls}


@st.composite
def _boxes(
    draw: st.DrawFn, *, low: int, high: int, min_size: int, min_groups: int
) -> dict[str, list[int]]:
    """Groups drawn from ``_GROUP_NAMES``, each with a box of distinct candidates, ascending.

    Distinct and ascending by construction, so no example is discarded.
    """
    count = draw(st.integers(min_value=min_groups, max_value=len(_GROUP_NAMES)))
    levels = st.integers(min_value=low, max_value=high)
    return {
        name: sorted(draw(st.lists(levels, min_size=min_size, max_size=6, unique=True)))
        for name in _GROUP_NAMES[:count]
    }


class _SeparableCost:
    """A synthetic ``cost_of``: per group ``2w(S - t)**2 + S + (S - s - 1) + bump * k(S)``.

    INTEGRAL, so every comparison the search makes is exact: magnitudes stay far below ``2**53``,
    and a seed offset ``seed % 3``, constant across levels, moves every mean and no comparison.
    With ``bump = 0`` the cost is convex in ``S`` and INJECTIVE in it:
    ``(S1 - S2)(2w(S1 + S2 - 2t) + 1) = 0`` forces ``S1 = S2``, the second factor being odd, so no
    two order-up-to levels ever tie; the band term makes base-stock strictly cheapest at every
    ``S``; and the unique minimum is ``(t - 1, t)`` for ``w >= 1``. ``k(S) = (7919 S) mod 5`` makes
    it non-convex when ``bump > 0``. Every call is logged, so a clause can count the evaluations.
    """

    def __init__(
        self, *, targets: Mapping[str, int], weights: Mapping[str, int], bump: int
    ) -> None:
        self._targets = dict(targets)
        self._weights = dict(weights)
        self._bump = bump
        self.calls: list[tuple[int, GroupLevels]] = []

    def at(self, levels: Mapping[str, GridPoint]) -> int:
        """The level-dependent part of the cost: the quantity every comparison turns on."""
        total = 0
        for group, point in levels.items():
            distance = point.S - self._targets[group]
            total += 2 * self._weights[group] * distance * distance + point.S
            total += point.S - point.s - 1
            total += self._bump * ((point.S * 7919) % 5)
        return total

    def mean(self, levels: Mapping[str, GridPoint], seeds: Sequence[int]) -> float:
        """The mean the subject must report for ``levels``: seeds ascending, summed in order."""
        costs = [float(self.at(levels) + seed % 3) for seed in sorted(seeds)]
        return sum(costs) / len(costs)

    def trace(self) -> list[tuple[int, dict[str, dict[str, int]]]]:
        """Every call, in order, in a comparable form."""
        return [(seed, levels.as_dict()) for seed, levels in self.calls]

    def __call__(self, seed: int, levels: GroupLevels) -> float:
        """Log the request, then return the cost."""
        self.calls.append((seed, levels))
        return float(self.at(levels.levels) + seed % 3)


class _OrderUpToCost:
    """A synthetic ``cost_of`` that depends on each group's ``S`` alone, through ``per_group``."""

    def __init__(self, per_group: Callable[[int], int]) -> None:
        self._per_group = per_group
        self.calls = 0

    def __call__(self, seed: int, levels: GroupLevels) -> float:
        """Count the request, then sum ``per_group`` over every group's ``S``."""
        self.calls += 1
        return float(sum(self._per_group(point.S) for point in levels.levels.values()))


class _PointCost:
    """A synthetic ``cost_of`` summing ``per_point`` over every group's ``(s, S)``."""

    def __init__(self, per_point: Callable[[GridPoint], int]) -> None:
        self._per_point = per_point

    def at(self, levels: Mapping[str, GridPoint]) -> int:
        """The cost of ``levels``: what every comparison in the search turns on."""
        return sum(self._per_point(point) for point in levels.values())

    def __call__(self, seed: int, levels: GroupLevels) -> float:
        """Return the cost; the seed moves nothing."""
        return float(self.at(levels.levels))


def _band_kept_neighbours(point: GridPoint) -> list[GridPoint]:
    """``S -+ 1`` with the band ``S - s`` kept: the only unit moves the first version-2
    certificate made, kept so a clause can show what that certificate could not see (R3)."""
    moves = [GridPoint(s=point.s + 1, S=point.S + 1)]
    if point.s >= 1:
        moves.insert(0, GridPoint(s=point.s - 1, S=point.S - 1))
    return moves


def _unit_neighbours(point: GridPoint) -> list[GridPoint]:
    """Every unit move the certificate claims to rule out, written independently of the subject:
    ``s`` alone and ``S`` alone (R3's two directions), and both with the band kept -- the one
    direction those cannot take at base-stock, where ``(s, S - 1)`` breaks ``s < S``."""
    moves = _band_kept_neighbours(point)
    axis = (
        (point.s - 1, point.S),
        (point.s + 1, point.S),
        (point.s, point.S - 1),
        (point.s, point.S + 1),
    )
    moves.extend(GridPoint(s=lower, S=upper) for lower, upper in axis if 0 <= lower < upper)
    return moves


def _improving_unit_moves(
    at: Callable[[Mapping[str, GridPoint]], int], levels: Mapping[str, GridPoint]
) -> list[str]:
    """Every unit move strictly cheaper than ``levels``: EMPTY at a unit-step local minimum."""
    here = at(levels)
    return [
        f"{group}:{neighbour.label}"
        for group, point in levels.items()
        for neighbour in _unit_neighbours(point)
        if at({**levels, group: neighbour}) < here
    ]


def _pair(point: GridPoint) -> tuple[int, int]:
    """``(s, S)``, compared as a pair for the reason section 9 records (ruff's SIM300)."""
    return (point.s, point.S)


def _search(
    *,
    boxes: Mapping[str, Sequence[int]],
    incumbent: GridPoint,
    seeds: Sequence[int],
    cost_of: Callable[[int, GroupLevels], float],
    rule: CandidateRule,
) -> GroupTunedSelection:
    """``tune_group_levels`` over exactly the groups the boxes name."""
    return tune_group_levels(
        groups=list(boxes),
        candidates=boxes,
        incumbent=incumbent,
        seeds=seeds,
        cost_of=cost_of,
        rule=rule,
    )


def _single_supplier_world(*, lead_time: float, log_sd: float) -> ResolvedWorld:
    """A hand-built world with structure 3 on: one supplier ``sup`` serving one SKU."""
    supply = SupplyStructure(
        suppliers={"sup": SupplierSpec(mean_lead_time_min=lead_time, log_sd=log_sd)},
        sku_supplier={"sku_0": "sup"},
        daily_autocorrelation=0.0,
        demand_coupling=0.0,
        coupling_floor=1.0,
        min_lead_time_min=1.0,
    )
    return ResolvedWorld(cell="synthetic", demand=None, supply=supply)


def _observation(inventory: Mapping[str, int], on_order: Mapping[str, float]) -> Observation:
    """The snapshot ``observe`` builds, reduced to the two fields the reorder rule reads."""
    return Observation(
        inventory=dict(inventory),
        sim_time=0.0,
        delivery_count=0,
        spoilage_count=0,
        stockout_count=0,
        unit_costs=dict.fromkeys(inventory, 1.0),
        on_order=dict(on_order),
    )


def _rule_block(rule: CandidateRule) -> dict[str, object]:
    """``rule`` as the ``candidate_rule:`` block a version-2 file declares."""
    return {
        "provenance": "synthetic, for the loader clauses",
        "review_min": rule.review_min,
        "z_values": list(rule.z_values),
        "extension_factor": rule.extension_factor,
        "max_extensions": rule.max_extensions,
        "gaps": list(rule.gaps),
        "max_passes": rule.max_passes,
        "max_evaluations": rule.max_evaluations,
        "recheck_top_k": rule.recheck_top_k,
    }


def _recheck_projection(rule: CandidateRule) -> int:
    """``(recheck_top_k + 4 x groups) x replicates`` over the synthetic recheck inputs."""
    vectors = rule.recheck_top_k + _MOVES_PER_GROUP * _LOADER_RECHECK_GROUPS
    return vectors * _LOADER_RECHECK_REPLICATES


def _budget_block(*, projected: int, recheck: int) -> dict[str, object]:
    """A ``budget:`` block whose two projections are ``projected`` and ``recheck``."""
    return {
        "provenance": "synthetic, for the loader clauses",
        "measured_reference_run": "0",
        "measured_arm_replicates": 1,
        "measured_measure_step_minutes": 1.0,
        "projected_max_tuning_arm_replicates": projected,
        "recheck_measurement_replicates": _LOADER_RECHECK_REPLICATES,
        "recheck_max_groups": _LOADER_RECHECK_GROUPS,
        "projected_max_recheck_arm_replicates": recheck,
    }


def _document(
    *, version: object, rule_block: Mapping[str, object], budget_block: Mapping[str, object]
) -> dict[str, object]:
    """A whole tuning spec, with the synthetic seed range."""
    return {
        "version": version,
        "candidate_rule": dict(rule_block),
        "tuning_seeds": {"start": _LOADER_START, "count": _LOADER_COUNT},
        "budget": dict(budget_block),
    }


def _well_formed() -> dict[str, object]:
    """The synthetic version-2 document every loader refusal is one edit away from."""
    return _document(
        version=TUNING_SPEC_VERSION,
        rule_block=_rule_block(_SEARCH_RULE),
        budget_block=_budget_block(
            projected=_SEARCH_RULE.max_evaluations * _LOADER_COUNT,
            recheck=_recheck_projection(_SEARCH_RULE),
        ),
    )


def _written(tmp_path: Path, document: Mapping[str, object]) -> Path:
    """``document`` written as YAML under ``tmp_path``, UTF-8, for the loader to read back."""
    target = tmp_path / "comparator-tuning.yaml"
    target.write_text(yaml.safe_dump(dict(document), sort_keys=True), encoding="utf-8")
    return target


# ---------------------------------------------------------------------------
# 1. The decomposition identity, over the domain where it is a theorem
# ---------------------------------------------------------------------------


@given(reference=_MEANS, tuned=_MEANS, hindsight=_MEANS)
def test_the_decomposition_identity_holds_exactly_over_the_rationals(
    reference: float, tuned: float, hindsight: float
) -> None:
    """``regret == tuning_gap + information_ceiling``, exactly, for every finite triple.

    The tuned mean appears once with each sign, so over the rationals it cancels and the identity
    is a theorem rather than a coincidence. Asserting it over ``Fraction`` states the domain the
    claim holds over instead of buying a pass with a tolerance (R2.10, finding 56).

    The float residual is separately required to be **finite**. The subject is handed finite means,
    so a nan or an infinity coming back would mean the arithmetic overflowed on a domain the caller
    is entitled to hand it -- and a reader would then have no residual to report at all.
    """
    exact = _exact_residual(reference=reference, tuned=tuned, hindsight=hindsight)
    assert exact == Fraction(0), (
        "the decomposition identity failed over the rationals, where it is a theorem: "
        f"reference={reference!r}, tuned={tuned!r}, hindsight={hindsight!r}, residual={exact!r}"
    )

    observed = decomposition_identity_residual(
        regret=reference - hindsight,
        tuning_gap=reference - tuned,
        information_ceiling=tuned - hindsight,
    )
    assert math.isfinite(observed), (
        "a residual taken over finite means must itself be finite -- got "
        f"{observed!r} for reference={reference!r}, tuned={tuned!r}, hindsight={hindsight!r}"
    )


@given(reference=_EXACT_COSTS, tuned=_EXACT_COSTS, hindsight=_EXACT_COSTS)
def test_the_float_residual_vanishes_on_the_exactly_representable_subdomain(
    reference: int, tuned: int, hindsight: int
) -> None:
    """On integral means below ``2**20`` the subject's FLOAT residual is exactly zero.

    This is the clause that binds the identity to the code rather than to ``Fraction``, and its
    domain is stated and defensible: every value the subject sees here is an integer of magnitude
    below ``2**21``, and every intermediate below ``2**22``, all exact as doubles -- so no rounding
    can occur and the residual has to be ``0.0`` on the nose. A subject that added a term in the
    wrong sense, or dropped one, fails it.
    """
    residual = decomposition_identity_residual(
        regret=float(reference - hindsight),
        tuning_gap=float(reference - tuned),
        information_ceiling=float(tuned - hindsight),
    )
    assert residual == 0.0, (
        "the residual must be exactly zero on the exactly-representable subdomain: "
        f"reference={reference}, tuned={tuned}, hindsight={hindsight}, residual={residual!r}"
    )


# ---------------------------------------------------------------------------
# 2. And the identity is not a tautology about the code
# ---------------------------------------------------------------------------


def test_the_float_evaluation_of_the_identity_can_carry_a_non_zero_residual() -> None:
    """The float path is lossy on an extreme triple and exact on an ordinary one.

    **This is the clause that makes the exactness claim informative rather than decorative.** If
    the residual were zero for every input, asserting exactness over ``Fraction`` would restate
    ``float`` arithmetic and would prove nothing about the domain. It is not: with a large term set
    against two nearly equal small ones, the two huge magnitudes cancel to zero and the small
    difference between them is destroyed, so the reported residual is the whole of the small term.

    Both directions are asserted, because either alone misleads. Lossy on the extreme case, exactly
    zero on the ordinary one -- so "the float evaluation MAY carry a residual" is a statement about
    conditioning and not a blanket disclaimer attached to every number in the artifact.
    """
    residual = decomposition_identity_residual(
        regret=_LOSSY_REFERENCE - _LOSSY_HINDSIGHT,
        tuning_gap=_LOSSY_REFERENCE - _LOSSY_TUNED,
        information_ceiling=_LOSSY_TUNED - _LOSSY_HINDSIGHT,
    )
    assert residual != 0.0, (
        "the extreme triple no longer exhibits float cancellation, so the exactness claim in this "
        "file has lost its falsifier and its domain statement is now unfalsifiable: "
        f"reference={_LOSSY_REFERENCE!r}, tuned={_LOSSY_TUNED!r}, "
        f"hindsight={_LOSSY_HINDSIGHT!r}, residual={residual!r}"
    )

    exact = _exact_residual(
        reference=_LOSSY_REFERENCE, tuned=_LOSSY_TUNED, hindsight=_LOSSY_HINDSIGHT
    )
    assert exact == Fraction(0), (
        "the same triple must be exact over the rationals -- that difference IS the property "
        f"this file asserts: residual={exact!r}"
    )

    ordinary = decomposition_identity_residual(
        regret=_ORDINARY_REFERENCE - _ORDINARY_HINDSIGHT,
        tuning_gap=_ORDINARY_REFERENCE - _ORDINARY_TUNED,
        information_ceiling=_ORDINARY_TUNED - _ORDINARY_HINDSIGHT,
    )
    assert ordinary == 0.0, (
        "a well-conditioned triple must evaluate exactly in float too, otherwise the clause above "
        f"reads as 'float is always wrong' rather than as a claim about conditioning: {ordinary!r}"
    )


# ---------------------------------------------------------------------------
# 3 and 4. The selection is a grid MEMBER, and it is the minimum
# ---------------------------------------------------------------------------


@given(surface=st.dictionaries(keys=_GRID_POINTS, values=_COSTS, min_size=1, max_size=8))
def test_the_selected_levels_are_a_member_of_the_grid(surface: dict[GridPoint, float]) -> None:
    """The search returns a candidate it was given, never an interpolation between two.

    Arm E is the best policy **in the pre-registered grid**. A pair lying between two grid members
    would be a policy nobody declared and whose cost was never evaluated, so the surface the
    artifact publishes would not contain the pair the artifact reports.

    Non-emptiness is asserted rather than assumed: "the returned point is a member" is satisfied by
    every possible return value over an empty mapping, so a generator that shrank to ``{}`` would
    leave this clause vacuous instead of red.
    """
    assert surface, "an empty surface would make the membership clause below vacuous"

    chosen, mean_cost, _ = select_levels(surface)

    assert chosen in surface, (
        f"selected {chosen.label}, which is not a key of the searched surface: "
        f"{sorted(point.label for point in surface)}"
    )
    assert surface[chosen] == mean_cost, (
        f"selected {chosen.label} but reported a cost of {mean_cost!r} against the surface's "
        f"own {surface[chosen]!r} for that point"
    )


@given(surface=st.dictionaries(keys=_GRID_POINTS, values=_COSTS, min_size=1, max_size=8))
def test_no_candidate_costs_less_than_the_selected_levels(surface: dict[GridPoint, float]) -> None:
    """The selection is the argmin: nothing on the surface is strictly cheaper than what was chosen.

    The claim is deliberately one-sided. Asserting equality against an independently computed
    ``min`` would be the same arithmetic twice; asserting that **no** candidate is strictly lower is
    the property a caller actually depends on, and it fails for a subject that returned the maximum,
    the first key, or the last one.

    Non-emptiness is asserted first, because a no-counterexample clause is satisfied by finding
    nothing at all -- and an empty surface finds nothing for the wrong reason.
    """
    assert surface, "an empty surface would make a no-counterexample clause vacuous"

    _, mean_cost, _ = select_levels(surface)

    cheaper = {point.label: cost for point, cost in surface.items() if cost < mean_cost}
    assert not cheaper, (
        f"selected a cost of {mean_cost!r} while strictly cheaper candidates existed: {cheaper}"
    )
    assert mean_cost in surface.values(), (
        f"the reported cost {mean_cost!r} is not any candidate's cost, so it is an aggregate of "
        f"the surface rather than a point on it: {sorted(surface.values())}"
    )


# ---------------------------------------------------------------------------
# 5. The tie-break is declared, deterministic, and independent of file order
# ---------------------------------------------------------------------------


@given(points=st.lists(_GRID_POINTS, min_size=1, max_size=6, unique=True), cost=_COSTS)
def test_an_exact_tie_resolves_to_the_lowest_reorder_point_then_the_lowest_band(
    points: list[GridPoint], cost: float
) -> None:
    """Ties break on the declared key, and the same tie in reverse file order picks the same pair.

    **Why this matters, and it is a fact about file layout rather than about the search.**
    ``min()`` over a mapping resolves ties by insertion order, and the insertion order of a grid is
    the order its candidates are written in (in version 1, ``comparator-tuning.yaml``'s grid).
    Under that behaviour, reordering the grid -- an edit no reviewer would read as a change of
    policy -- would silently change which levels arm E uses, and the artifact would report a
    different tuned pair for a reason nobody recorded. So the tie-break is declared: lowest
    reorder point, then lowest par band.

    The reversal is the clause that can actually catch it. Asserting the winner once would pass for
    an insertion-order implementation whenever the declared key happened to agree with it;
    asserting that both insertion orders agree cannot.

    ``tie_broken`` is asserted in both directions here: true when two or more candidates sit at the
    minimum, false for a single-candidate surface where the minimum is unique.
    """
    assert points, "a tie clause over no candidates asserts nothing"

    forward: dict[GridPoint, float] = dict.fromkeys(points, cost)
    reverse: dict[GridPoint, float] = dict.fromkeys(reversed(points), cost)
    expected = min(points, key=_tie_break_key)

    chosen_forward, cost_forward, tied_forward = select_levels(forward)
    chosen_reverse, _, tied_reverse = select_levels(reverse)

    assert chosen_forward == expected, (
        f"a tie over {sorted(point.label for point in points)} resolved to "
        f"{chosen_forward.label}; the declared key selects {expected.label}"
    )
    assert chosen_reverse == chosen_forward, (
        "the tie resolved differently under a reversed grid order -- insertion order is a property "
        f"of the YAML layout, not of the search: {chosen_forward.label} then {chosen_reverse.label}"
    )
    assert cost_forward == cost, f"reported {cost_forward!r} for a surface flat at {cost!r}"

    expected_tie = len(points) > 1
    assert tied_forward is expected_tie, (
        f"{len(points)} candidate(s) at the minimum was reported as tie_broken={tied_forward}"
    )
    assert tied_reverse is expected_tie, (
        f"tie_broken disagreed with itself across grid orders: {tied_forward} then {tied_reverse}"
    )


@given(
    points=st.lists(_GRID_POINTS, min_size=2, max_size=6, unique=True),
    base=_EXACT_COSTS,
    margin=_EXACT_MARGINS,
)
def test_a_unique_minimum_wins_from_any_position_and_is_reported_as_untied(
    points: list[GridPoint], base: int, margin: int
) -> None:
    """A strictly cheaper candidate wins wherever it sits, and ``tie_broken`` is then false.

    The cheapest point is placed **last** in insertion order, so the clause fails for a subject
    that preferred the first key, and its tie-break ranking is left to chance, so it also fails for
    a subject that let the tie-break key outrank the cost. Integral costs are used so that
    ``base - margin < base`` is exact rather than an argument about rounding.

    This is the other half of the tie clause above: ``tie_broken`` must be false when the minimum
    is unique, otherwise the flag records nothing and a genuine tie -- which means the grid's
    resolution is coarser than the difference it is being asked to resolve -- is indistinguishable
    from a clean win.
    """
    surface: dict[GridPoint, float] = dict.fromkeys(points, float(base))
    winner = points[-1]
    surface[winner] = float(base - margin)

    chosen, mean_cost, tie_broken = select_levels(surface)

    assert chosen == winner, (
        f"the strictly cheapest candidate {winner.label} at {surface[winner]!r} lost to "
        f"{chosen.label} at {mean_cost!r}"
    )
    assert mean_cost == float(base - margin), (
        f"reported {mean_cost!r} for a unique minimum of {float(base - margin)!r}"
    )
    assert tie_broken is False, (
        f"a unique minimum was reported as a tie over costs {sorted(surface.values())}"
    )


# ---------------------------------------------------------------------------
# 6. The seed-overlap refusal, driven in BOTH directions
# ---------------------------------------------------------------------------


@given(
    start=st.integers(min_value=0, max_value=2000),
    count=st.integers(min_value=1, max_value=200),
    replicates=st.integers(min_value=1, max_value=2000),
)
def test_the_tuning_range_is_refused_exactly_when_it_overlaps_the_measurement_range(
    start: int, count: int, replicates: int
) -> None:
    """``None`` if and only if the tuning range starts at or above the replicate count.

    **Why this is the load-bearing guard.** ``_measure`` iterates ``range(replicates)``, so the
    measurement seeds are ``0 .. replicates - 1``. Tuning arm E on those same seeds would make its
    levels **in-sample** optimal, which inflates the tuning gap and deflates the information
    ceiling -- biasing the split toward the very hypothesis finding 61 records, and a measurement
    must not be biased toward the thing it is testing. Out-of-sample levels bias the ceiling the
    OTHER way -- UP, by the winner's curse -- which is safe for finding 63's question and unsafe
    for B-prime's, so the comparator adds an in-sample recheck rather than dropping this guard (R1;
    stated once, in ``comparator-tuning.yaml``).

    Driven as a biconditional rather than as a one-sided check, because a guard that refuses
    everything is as useless as one that refuses nothing and only the ``iff`` can fail for both.
    The reason is required to be non-blank: ``tune_par_level`` raises with this text as the whole
    of its message, so a refusal nobody can read is a refusal nobody can act on.
    """
    spec = _spec(start=start, count=count)

    refusal = seed_overlap_refusal(spec, measurement_replicates=replicates)
    disjoint = start >= replicates

    assert (refusal is None) is disjoint, (
        f"tuning covers {start}..{start + count - 1} and the measurement covers "
        f"0..{replicates - 1}; disjoint={disjoint} but the refusal was {refusal!r}"
    )
    if refusal is not None:
        assert refusal.strip(), "a refusal whose reason is blank cannot be reported to anyone"


def test_the_overlap_boundary_sits_exactly_at_the_first_unmeasured_seed() -> None:
    """The boundary is pinned on both sides, and a non-positive replicate count also refuses.

    The generated clause above covers the biconditional, but any single example lands on one side
    of it, so the boundary itself is pinned here: a tuning range starting at the replicate count is
    disjoint, and one starting a single seed lower overlaps. An off-by-one in either direction is
    what turns an out-of-sample search into an in-sample one for exactly one replicate -- enough to
    bias the split and not enough for anyone to notice.
    """
    replicates = 200

    disjoint = seed_overlap_refusal(
        _spec(start=replicates, count=5), measurement_replicates=replicates
    )
    assert disjoint is None, (
        f"a tuning range starting at the replicate count is disjoint, but got {disjoint!r}"
    )

    overlapping = seed_overlap_refusal(
        _spec(start=replicates - 1, count=5), measurement_replicates=replicates
    )
    assert overlapping is not None, (
        "a tuning range starting one seed below the replicate count overlaps it and must be refused"
    )
    assert overlapping.strip(), "the overlap refusal carries no reason"

    non_positive = seed_overlap_refusal(_spec(start=replicates, count=5), measurement_replicates=0)
    assert non_positive is not None, (
        "a non-positive replicate count has no measurement range to be disjoint from, so it must "
        "be refused rather than read as disjoint"
    )
    assert non_positive.strip(), "the non-positive replicate refusal carries no reason"


# ---------------------------------------------------------------------------
# 7. The search REFUSES rather than falling back, and does no work when it does
# ---------------------------------------------------------------------------


@given(
    grid=st.lists(_GRID_POINTS, min_size=1, max_size=4, unique=True),
    count=st.integers(min_value=1, max_value=5),
    start=st.integers(min_value=0, max_value=40),
    excess=st.integers(min_value=1, max_value=40),
)
def test_an_overlapping_search_refuses_without_evaluating_a_single_candidate(
    grid: list[GridPoint], count: int, start: int, excess: int
) -> None:
    """``tune_par_level`` raises on an overlapping range and never calls ``cost_of`` at all.

    **A refusal that still did the work is not a refusal.** It would burn the twin replicates the
    run is bounded by, and -- worse -- it would mean the overlap check sat downstream of the search
    rather than in front of it, so a later edit turning the raise into a log line would find the
    in-sample surface already computed and ready to be reported.

    The call count is the only instrument that can see this, because the raised error looks
    identical either way. ``excess >= 1`` makes the range overlap by construction, so no example is
    discarded and every one of them exercises the branch this clause names.
    """
    spec = _spec(start=start, count=count)
    counter = _CountingCost()

    with pytest.raises(TuningUnavailableError):
        tune_par_level(spec, grid=grid, cost_of=counter, measurement_replicates=start + excess)

    assert counter.calls == [], (
        f"a refused search evaluated {len(counter.calls)} candidate-seed pair(s): "
        f"{[(seed, point.label) for seed, point in counter.calls]}"
    )


@given(
    grid=st.lists(_GRID_POINTS, min_size=1, max_size=4, unique=True),
    count=st.integers(min_value=1, max_value=5),
    replicates=st.integers(min_value=1, max_value=40),
    extra=st.integers(min_value=0, max_value=40),
)
def test_a_disjoint_search_evaluates_every_declared_candidate_at_every_declared_seed(
    grid: list[GridPoint], count: int, replicates: int, extra: int
) -> None:
    """The search covers the whole pre-registration -- and this is what makes the zero above real.

    ``counter.calls == []`` on a refusal means nothing unless the search calls ``cost_of`` when it
    is *not* refusing, so these two clauses are a pair and neither stands alone. This one also
    asserts the stronger claim the subject's docstring makes: the minimum is taken over **the grid
    that was declared**, at **the seeds that were declared** -- not over a subset nobody chose, and
    not over ``range(count)``, which is the plausible wrong seed range and the one that would make
    the search in-sample while every other clause stayed green.

    The reported surface must carry one entry per candidate, because the artifact publishes it so a
    reader can argue with the minimum, and a surface missing a neighbour is a selected pair nobody
    can check.
    """
    spec = _spec(start=replicates + extra, count=count)
    counter = _CountingCost()

    selection = tune_par_level(spec, grid=grid, cost_of=counter, measurement_replicates=replicates)

    assert counter.calls, "a disjoint search that evaluated nothing selected a pair from nowhere"
    assert len(counter.calls) == len(grid) * spec.seed_count, (
        f"{len(counter.calls)} evaluation(s) for {len(grid)} candidate(s) x "
        f"{spec.seed_count} seed(s)"
    )
    assert counter.points_seen == set(grid), (
        "the search did not cover the declared grid; missing "
        f"{sorted(point.label for point in set(grid) - counter.points_seen)}"
    )
    assert counter.seeds_seen == set(tuning_seeds(spec)), (
        f"the search ran on seeds {sorted(counter.seeds_seen)} rather than on the declared "
        f"{sorted(tuning_seeds(spec))}"
    )
    assert selection.seeds == tuning_seeds(spec), (
        f"the selection records seeds {selection.seeds} against a declared {tuning_seeds(spec)}"
    )
    assert set(selection.surface) == {point.label for point in grid}, (
        f"the reported surface covers {sorted(selection.surface)} against a declared grid of "
        f"{sorted(point.label for point in grid)}"
    )
    assert selection.levels in grid, (
        f"selected {selection.levels.label}, which is not a declared candidate"
    )


def test_an_empty_or_repeating_supplied_grid_is_refused_before_any_evaluation() -> None:
    """The two refusals version 1's loader applied to its grid now apply to the supplied one.

    Version 2's spec carries no grid, so ``tune_par_level`` takes it as an argument -- and a
    duplicate would otherwise be silently de-duplicated by the surface's keys, making the searched
    grid differ from the supplied one. Both refusals must happen before ``cost_of`` is called.
    """
    spec = _spec(start=100, count=2)
    point = GridPoint(s=1, S=5)
    refused: tuple[tuple[GridPoint, ...], ...] = ((), (point, point))
    for grid in refused:
        counter = _CountingCost()
        with pytest.raises(TuningUnavailableError):
            tune_par_level(spec, grid=grid, cost_of=counter, measurement_replicates=10)
        assert counter.calls == [], f"a refused grid {grid!r} was evaluated anyway"

    control = _CountingCost()
    tune_par_level(spec, grid=(point,), cost_of=control, measurement_replicates=10)
    assert control.calls, "a one-point grid must evaluate, or the refusals above are moot"


# ---------------------------------------------------------------------------
# 8. Non-finite costs and an empty surface are refused, not skipped
# ---------------------------------------------------------------------------


@given(
    points=st.lists(_GRID_POINTS, min_size=1, max_size=5, unique=True),
    finite=_COSTS,
    bad=st.sampled_from([math.nan, math.inf, -math.inf]),
)
def test_a_non_finite_candidate_cost_is_refused_rather_than_skipped(
    points: list[GridPoint], finite: float, bad: float
) -> None:
    """A nan or an infinity on the surface raises instead of being dropped from the argmin.

    Skipping it would be much the worse failure: the search would still report a minimum, that
    minimum would be over a grid one candidate short of the pre-registered one, and nothing in the
    artifact would say so (I-7). The nan is the sharper case, because every comparison against it
    is false -- so an argmin that did not check finiteness would ignore it in silence rather than
    crash.

    The same surface with the offending value replaced selects normally, which attributes the
    refusal to the **value** rather than to the shape of the input.
    """
    surface: dict[GridPoint, float] = dict.fromkeys(points, finite)
    surface[points[0]] = bad

    with pytest.raises(TuningUnavailableError):
        select_levels(surface)

    surface[points[0]] = finite
    chosen, _, _ = select_levels(surface)
    assert chosen in surface, (
        "the same surface without the non-finite entry must select normally, otherwise the refusal "
        "above is attributable to the surface's shape rather than to its value"
    )


@given(
    grid=st.lists(_GRID_POINTS, min_size=1, max_size=3, unique=True),
    count=st.integers(min_value=1, max_value=3),
    replicates=st.integers(min_value=1, max_value=20),
    bad=st.sampled_from([math.nan, math.inf, -math.inf]),
)
def test_a_non_finite_cost_from_the_injected_function_refuses_the_whole_search(
    grid: list[GridPoint], count: int, replicates: int, bad: float
) -> None:
    """One candidate producing a non-finite cost refuses the search, not merely that candidate.

    Asserted through ``tune_par_level`` as well as through ``select_levels`` because the mean is
    taken between the two: a subject that averaged first and never checked, or that checked the
    per-seed values and not the mean, would pass one clause and fail the other.

    The call log is asserted non-empty, because a search that refused before evaluating anything
    would have exercised the overlap guard and this clause would be silently testing the wrong one.
    """
    spec = _spec(start=replicates, count=count)
    counter = _CountingCost(offender=grid[0], offending_value=bad)

    with pytest.raises(TuningUnavailableError):
        tune_par_level(spec, grid=grid, cost_of=counter, measurement_replicates=replicates)

    assert counter.calls, (
        "the search refused before evaluating anything, so this clause tested the overlap guard "
        "rather than the finiteness guard it names"
    )


def test_an_empty_cost_surface_is_refused_rather_than_answered() -> None:
    """No candidates means no minimum, and a minimum reported anyway would have no grid behind it.

    The counterpart to every non-emptiness assertion above: those guard against a clause passing
    vacuously, and this guards against the subject inventing an answer in the case where they would.
    """
    with pytest.raises(TuningUnavailableError):
        select_levels({})


# ---------------------------------------------------------------------------
# 9. A grid point refuses at construction, where the refusal can name the file
# ---------------------------------------------------------------------------


@given(lower=st.integers(min_value=0, max_value=200), gap=st.integers(min_value=1, max_value=200))
def test_an_ordered_non_negative_pair_constructs_and_reports_its_own_levels(
    lower: int, gap: int
) -> None:
    """Every valid pair constructs, so the two refusal clauses below are not refusing everything.

    A constructor that rejected all input would satisfy both refusals and be useless. The label is
    asserted too: it is the key the published surface is keyed by, so a label that did not identify
    the levels it was built from would make that surface unreadable.
    """
    point = GridPoint(s=lower, S=lower + gap)

    # Compared as a PAIR rather than field by field, and that is not cosmetic: `ruff`'s SIM300
    # reads the upper-case attribute `point.S` as a constant and flags `point.S == expr` as a Yoda
    # condition. The domain owns that name -- `Par_Level_Reorder(s, S)` and `policy.yaml`'s
    # `order_up_to_S` both use it -- so renaming the field to satisfy a linter heuristic would
    # damage the vocabulary, and a `noqa` would silence a rule rather than fix an expression. The
    # tuple form is clearer anyway: it asserts the levels round-trip together.
    assert (point.s, point.S) == (lower, lower + gap)
    assert point.label == f"s{lower}_S{lower + gap}", (
        f"label {point.label!r} does not identify the levels it was built from"
    )


@given(
    lower=st.integers(min_value=-200, max_value=-1),
    gap=st.integers(min_value=1, max_value=200),
)
def test_a_negative_reorder_point_is_refused_at_construction(lower: int, gap: int) -> None:
    """A negative reorder point raises while the grid file can still be named.

    ``Par_Level_Reorder`` raises on a non-integral or non-ordered pair, so without validation here
    the refusal would surface as a policy-construction error at replicate 0 of a CI-only
    measurement -- a red job whose message points at the twin rather than at the line of YAML that
    caused it.
    """
    with pytest.raises(TuningUnavailableError):
        GridPoint(s=lower, S=lower + gap)


@given(
    lower=st.integers(min_value=0, max_value=200),
    excess=st.integers(min_value=0, max_value=200),
)
def test_a_reorder_point_at_or_above_the_par_band_is_refused_at_construction(
    lower: int, excess: int
) -> None:
    """``s >= S`` raises, and the ``s == S`` boundary is inside the generated range.

    ``excess = 0`` makes the two levels equal, which is a band of zero width: an order-up-to level
    no order can ever reach. It is refused for the same reason a strict inversion is, and
    generating from zero rather than from one is what puts that boundary under this clause.
    """
    with pytest.raises(TuningUnavailableError):
        GridPoint(s=lower, S=lower - excess)


# ---------------------------------------------------------------------------
# 10. The COMMITTED version-2 spec, and the loader's refusals
# ---------------------------------------------------------------------------


def test_the_committed_spec_carries_a_rule_whose_safety_factors_reach_the_protected_mean() -> None:
    """The real ``comparator-tuning.yaml`` loads as version 2, with a rule the search can use.

    REWRITTEN from v1's "the committed grid is valid and contains the incumbent". There is no grid
    to contain anything now, and the incumbent's guarantee is the search's own (clause (b)). What
    the committed file must still provide is a rule whose every value was read -- the loader
    refuses otherwise -- and safety factors reaching at least the protected mean, the precondition
    of section 11's growth clause: with every ``z < 0`` a longer lead time could LOWER the largest
    candidate, and the box would not scale with the world. ``spec.seeds`` must be the seeds the
    module function derives, so the two spellings cannot drift.

    No value is asserted: the rule's numbers are a design choice argued in the file itself, and
    pinning them here would turn re-choosing them into a test edit (CF-13).
    """
    assert DEFAULT_TUNING_PATH.is_file(), (
        f"the committed tuning spec is missing at {DEFAULT_TUNING_PATH} -- arm E has no "
        "pre-registration to search"
    )

    spec = load_tuning_spec()

    assert isinstance(spec.rule, CandidateRule)
    assert spec.rule.z_values, f"{spec.source} declares no safety factor"
    assert max(spec.rule.z_values) >= 0.0, (
        f"{spec.source} declares only negative safety factors {spec.rule.z_values}, so a longer "
        "lead time could shrink the largest candidate"
    )
    assert spec.seeds == tuning_seeds(spec), (
        f"spec.seeds {spec.seeds} disagrees with tuning_seeds(spec) {tuning_seeds(spec)}"
    )


def test_the_committed_review_period_is_the_comparators_decision_cadence() -> None:
    """``candidate_rule.review_min`` equals ``FORESIGHT_WINDOW_MIN``: one fact, stated twice.

    The rule protects demand over the lead time PLUS ONE REVIEW, and a review is how often the
    comparator lets an arm decide -- ``run_single_arm`` slices the horizon by
    ``FORESIGHT_WINDOW_MIN``. If the two drift, every derived box is centred on the wrong demand
    and nothing else would say so. The import pulls the engine MODULE in to read one constant;
    nothing is constructed and nothing runs.
    """
    from uplift.foresight import FORESIGHT_WINDOW_MIN

    rule = load_tuning_spec().rule
    assert rule.review_min == FORESIGHT_WINDOW_MIN, (
        f"candidate_rule.review_min = {rule.review_min!r} but the comparator decides every "
        f"{FORESIGHT_WINDOW_MIN!r} minutes, so every derived box protects the wrong interval"
    )


def test_the_loader_reads_back_exactly_the_rule_and_seeds_a_well_formed_document_declares(
    tmp_path: Path,
) -> None:
    """The control for every refusal below: an unedited synthetic document loads, value for value.

    Without it, the refusals could all be passing because the loader refuses EVERYTHING. The
    refusal clauses match on the refusal's own wording (``no value at ...``, ``inadmissible ...``,
    ``unknown key(s) ...``) rather than on a bare key name, because every message carries the
    file's path and ``tmp_path`` is named after the test -- a bare ``version`` would match it.
    """
    path = _written(tmp_path, _well_formed())

    spec = load_tuning_spec(path)

    assert spec.rule == _SEARCH_RULE, f"read back {spec.rule!r}, wrote {_SEARCH_RULE!r}"
    assert (spec.seed_start, spec.seed_count) == (_LOADER_START, _LOADER_COUNT)
    assert spec.source == str(path)


@pytest.mark.parametrize("field", sorted(_rule_block(_SEARCH_RULE)))
def test_every_rule_field_is_required_and_a_missing_one_is_refused_by_name(
    tmp_path: Path, field: str
) -> None:
    """No rule field has a default: dropping any one refuses the file, naming the field."""
    kept = {key: value for key, value in _rule_block(_SEARCH_RULE).items() if key != field}
    document = {**_well_formed(), "candidate_rule": kept}

    with pytest.raises(TuningUnavailableError, match=rf"no value at candidate_rule\.{field}\b"):
        load_tuning_spec(_written(tmp_path, document))


def test_a_version_1_document_is_refused_by_its_version_and_a_stray_grid_by_its_key(
    tmp_path: Path,
) -> None:
    """Version 1's grid is history, not configuration.

    A version-1 document is refused by its VERSION, before any v1 key is looked at; a version-2
    document still carrying ``grid:`` is refused by that KEY, because a value no reader reads is a
    committed search nothing runs.
    """
    grid = [{"s": 0, "S": 10}]
    legacy = {**_well_formed(), "version": 1, "grid": grid}
    with pytest.raises(TuningUnavailableError, match=r"inadmissible version:"):
        load_tuning_spec(_written(tmp_path, legacy))

    stray = {**_well_formed(), "grid": grid}
    with pytest.raises(TuningUnavailableError, match=r"unknown key\(s\) grid"):
        load_tuning_spec(_written(tmp_path, stray))


def test_a_budget_projection_the_rule_no_longer_produces_is_refused(tmp_path: Path) -> None:
    """``projected_max_tuning_arm_replicates`` must equal ``max_evaluations x tuning_seeds.count``.

    Raising either bound without re-deriving the projection would leave a cost estimate behind
    that nothing re-derives -- the stale number this project's gates exist to refuse.
    """
    stale = _budget_block(
        projected=_SEARCH_RULE.max_evaluations * _LOADER_COUNT + 1,
        recheck=_recheck_projection(_SEARCH_RULE),
    )
    document = {**_well_formed(), "budget": stale}

    with pytest.raises(
        TuningUnavailableError, match=r"inadmissible budget\.projected_max_tuning_arm_replicates"
    ):
        load_tuning_spec(_written(tmp_path, document))


def test_re_choosing_recheck_top_k_without_re_projecting_the_recheck_is_refused(
    tmp_path: Path,
) -> None:
    """The recheck projection is ``(recheck_top_k + 4 x groups) x replicates``, re-derived on load.

    The edit is made to the RULE, not to the budget, because that is the edit that leaves a stale
    projection behind: R1's recheck cost grows with ``recheck_top_k`` and nothing else would say
    so. A non-positive input is refused too, since nothing can be projected over it.
    """
    edited = {**_rule_block(_SEARCH_RULE), "recheck_top_k": _SEARCH_RULE.recheck_top_k + 1}
    stale = {**_well_formed(), "candidate_rule": edited}
    with pytest.raises(
        TuningUnavailableError, match=r"inadmissible budget\.projected_max_recheck_arm_replicates"
    ):
        load_tuning_spec(_written(tmp_path, stale))

    budget = _budget_block(
        projected=_SEARCH_RULE.max_evaluations * _LOADER_COUNT,
        recheck=_recheck_projection(_SEARCH_RULE),
    )
    for name in ("recheck_measurement_replicates", "recheck_max_groups"):
        emptied = {**_well_formed(), "budget": {**budget, name: 0}}
        with pytest.raises(TuningUnavailableError, match=r"inadmissible budget:"):
            load_tuning_spec(_written(tmp_path, emptied))


@pytest.mark.parametrize("field", sorted(_budget_block(projected=0, recheck=0)))
def test_every_budget_field_is_required_and_a_missing_one_is_refused_by_name(
    tmp_path: Path, field: str
) -> None:
    """No budget field has a default either, the recheck's three included."""
    well_formed = _well_formed()
    budget = well_formed["budget"]
    assert isinstance(budget, dict)
    kept = {key: value for key, value in budget.items() if key != field}

    with pytest.raises(TuningUnavailableError, match=rf"no value at budget\.{field}\b"):
        load_tuning_spec(_written(tmp_path, {**well_formed, "budget": kept}))


def test_the_recheck_projection_is_sized_for_the_committed_world_and_the_measuring_job() -> None:
    """The projection's two declared inputs equal their sources, so its arithmetic is not enough.

    ``recheck_max_groups`` is the most groups any committed cell has, read through ``load_world``
    and ``sku_groups`` rather than restated; ``recheck_measurement_replicates`` is the
    ``--replicates`` EVERY ``python -m uplift.regret`` in ``uplift.yml::twin-regret`` passes. The
    loader checks the formula; only this clause sees an input drift from what it sizes. The
    invocation list is asserted non-empty, or "every invocation agrees" would hold over none.
    """
    raw = yaml.safe_load(DEFAULT_TUNING_PATH.read_text(encoding="utf-8"))
    budget = raw["budget"]
    world = load_world()
    skus = sorted(world.structure_3.sku_supplier)
    most_groups = max(
        len(set(sku_groups(world.resolve(cell), skus).values())) for cell in world.cells
    )
    assert budget["recheck_max_groups"] == most_groups, (
        f"budget.recheck_max_groups = {budget['recheck_max_groups']!r}, but the committed world's "
        f"largest cell has {most_groups} group(s)"
    )

    workflow = yaml.safe_load(_UPLIFT_WORKFLOW.read_text(encoding="utf-8"))
    counts: list[int | None] = []
    for step in workflow["jobs"]["twin-regret"]["steps"]:
        script = str(step.get("run", "")).replace("\\\n", " ")
        for command in _MEASURE_COMMAND.finditer(script):
            flag = _REPLICATES_FLAG.search(command.group(1))
            counts.append(None if flag is None else int(flag.group(1)))
    assert counts, "twin-regret runs no `python -m uplift.regret`, so nothing sizes the recheck"
    expected = budget["recheck_measurement_replicates"]
    assert counts == [expected] * len(counts), (
        f"twin-regret measures with --replicates {counts}, but the recheck is projected over "
        f"{expected!r} (None = no explicit --replicates, so the CLI default)"
    )


def test_an_unknown_key_a_boolean_count_and_an_absent_file_are_refused(tmp_path: Path) -> None:
    """Neither ignored, nor coerced, nor defaulted.

    A stray rule key would read as configuration while configuring nothing; ``True`` is an ``int``
    to Python and must still not be read as a pass count; and an absent file is a refusal, not an
    empty spec.
    """
    stray = {**_well_formed(), "candidate_rule": {**_rule_block(_SEARCH_RULE), "review_hours": 1}}
    with pytest.raises(TuningUnavailableError, match=r"unknown key\(s\) review_hours"):
        load_tuning_spec(_written(tmp_path, stray))

    coerced_block = {**_rule_block(_SEARCH_RULE), "max_passes": True}
    coerced = {**_well_formed(), "candidate_rule": coerced_block}
    with pytest.raises(TuningUnavailableError, match=r"inadmissible candidate_rule\.max_passes:"):
        load_tuning_spec(_written(tmp_path, coerced))

    with pytest.raises(TuningUnavailableError):
        load_tuning_spec(tmp_path / "absent.yaml")


def test_the_committed_tuning_seeds_are_out_of_sample_at_their_own_boundary() -> None:
    """The committed seed range is out of sample, pinned at its own boundary in both directions.

    Asserted relationally against ``spec.seed_start`` rather than against the literal the file
    carries, so this clause states the property -- disjointness -- instead of re-pinning a value
    the grid file already commits and that ``doc_truth`` has no single-line anchor for. Raising
    ``--replicates`` to the tuning start is the exact edit that would make the search in-sample,
    and the second half below is what makes that edit loud instead of quiet.
    """
    spec = load_tuning_spec()

    assert spec.seed_count > 0, f"{spec.source} declares a non-positive tuning seed count"
    assert spec.seed_start >= 0, f"{spec.source} declares a negative tuning seed start"

    seeds = tuning_seeds(spec)
    assert seeds, "the committed pre-registration resolves to no seeds at all"
    assert len(seeds) == spec.seed_count
    assert min(seeds) == spec.seed_start

    at_boundary = seed_overlap_refusal(spec, measurement_replicates=spec.seed_start)
    assert at_boundary is None, (
        f"the committed range {min(seeds)}..{max(seeds)} must be disjoint from a measurement "
        f"covering 0..{spec.seed_start - 1}, but got {at_boundary!r}"
    )

    past_boundary = seed_overlap_refusal(spec, measurement_replicates=spec.seed_start + 1)
    assert past_boundary is not None, (
        "one more replicate than the committed tuning start makes the two ranges overlap, and that "
        "must be refused rather than read as disjoint"
    )
    assert past_boundary.strip(), "the overlap refusal on the committed spec carries no reason"


# ---------------------------------------------------------------------------
# 11. (f) The candidate rule derives boxes that scale with the world
# ---------------------------------------------------------------------------

_RATES = st.floats(min_value=0.01, max_value=5.0, allow_nan=False, allow_infinity=False)
_LEAD_TIMES = st.floats(min_value=2.0, max_value=2000.0, allow_nan=False, allow_infinity=False)
_LOG_SDS = st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)
_SAFETY_FACTORS = st.floats(min_value=-3.0, max_value=8.0, allow_nan=False, allow_infinity=False)


@st.composite
def _derivation_rules(draw: st.DrawFn) -> CandidateRule:
    """A rule whose safety factors reach at least the mean -- the growth clause's precondition."""
    others = draw(st.lists(_SAFETY_FACTORS, max_size=11))
    top = draw(st.floats(min_value=0.0, max_value=8.0, allow_nan=False, allow_infinity=False))
    review = draw(st.floats(min_value=1.0, max_value=240.0, allow_nan=False, allow_infinity=False))
    return dataclasses.replace(
        _SEARCH_RULE, review_min=review, z_values=tuple(sorted({*others, top}))
    )


@given(
    rule=_derivation_rules(),
    rate=_RATES,
    lead_time=_LEAD_TIMES,
    log_sd=_LOG_SDS,
    extra=_LEAD_TIMES,
)
def test_derived_boxes_are_ascending_distinct_at_least_one_and_never_shrink_with_lead_time(
    rule: CandidateRule, rate: float, lead_time: float, log_sd: float, extra: float
) -> None:
    """(f): every box is ascending, distinct and >= 1, and its top grows with the lead time.

    Three worlds at one demand rate: structure 3 off (lead time zero, by the rule), a supplier at
    ``lead_time``, and the same supplier at ``lead_time + extra``; "off" derives one box whether it
    is spelled ``None`` or a world with no supply. The top candidate never shrinks along that chain
    -- mean and spread both grow with the lead time, ``max(z) >= 0``, and every operation is
    monotone in IEEE 754 -- and it strictly grows once the extra lead time adds three or more units
    of mean demand, because ``round(x + 2) == round(x) + 2`` even half-to-even. No box holds more
    candidates than the rule has safety factors: duplicates are merged, never invented.
    """
    off = derive_candidates(None, [ALL_SKUS_GROUP], rule, rate_per_sku_per_min=rate)
    unsupplied = ResolvedWorld(cell="off", demand=None, supply=None)
    also_off = derive_candidates(unsupplied, [ALL_SKUS_GROUP], rule, rate_per_sku_per_min=rate)
    near_world = _single_supplier_world(lead_time=lead_time, log_sd=log_sd)
    far_world = _single_supplier_world(lead_time=lead_time + extra, log_sd=log_sd)
    near = derive_candidates(near_world, ["sup"], rule, rate_per_sku_per_min=rate)["sup"]
    far = derive_candidates(far_world, ["sup"], rule, rate_per_sku_per_min=rate)["sup"]

    assert also_off == off, f"structure 3 off derived {off} as None but {also_off} as no supply"
    boxes = {"off": off[ALL_SKUS_GROUP], "near": near, "far": far}
    for name, box in boxes.items():
        assert box, f"the {name} box is empty"
        malformed = [level for level in box if isinstance(level, bool) or level < 1]
        assert not malformed, f"the {name} box {box} carries levels that are not integers >= 1"
        assert all(isinstance(level, int) for level in box), f"the {name} box is not integral"
        assert all(lower < upper for lower, upper in itertools.pairwise(box)), (
            f"the {name} box {box} is not strictly ascending"
        )
        assert len(box) <= len(rule.z_values), (
            f"the {name} box {box} outnumbers the rule's {len(rule.z_values)} safety factors"
        )

    assert max(boxes["off"]) <= max(near) <= max(far), (
        f"the top candidate shrank as lead time grew: off {boxes['off']}, near {near}, far {far}"
    )
    if rate * extra >= 3.0:
        assert max(near) < max(far), (
            f"{rate * extra!r} more units of mean demand left the top candidate at {max(far)}"
        )


def test_candidate_derivation_refuses_what_it_cannot_size() -> None:
    """A group that is no supplier, a rate that is not positive, and an empty or repeated group
    list are refused rather than sized by a guess -- and the corrected call succeeds."""
    world = _single_supplier_world(lead_time=10.0, log_sd=0.1)
    assert derive_candidates(world, ["sup"], _SEARCH_RULE, rate_per_sku_per_min=1.0)["sup"]

    with pytest.raises(TuningUnavailableError, match="'all'"):
        derive_candidates(world, [ALL_SKUS_GROUP], _SEARCH_RULE, rate_per_sku_per_min=1.0)
    for rate in (0.0, -1.0, math.nan, math.inf):
        with pytest.raises(TuningUnavailableError):
            derive_candidates(world, ["sup"], _SEARCH_RULE, rate_per_sku_per_min=rate)
    refused_groups: tuple[list[str], ...] = ([], ["sup", "sup"])
    for groups in refused_groups:
        with pytest.raises(TuningUnavailableError):
            derive_candidates(world, groups, _SEARCH_RULE, rate_per_sku_per_min=1.0)


@pytest.mark.parametrize("rate", [0.05, 0.2, 1.0])
def test_the_committed_rule_derives_a_box_for_every_group_of_every_committed_cell(
    rate: float,
) -> None:
    """Read, not restated: the committed world and the committed rule fit together in every cell.

    A structure-3 cell's groups are its SKUs' suppliers, each with a non-empty ascending box; any
    other cell has exactly the one group ``"all"``. The rates are probes, because
    ``derive_candidates`` is told the rate by its caller, and the SKU set is the world's own. At
    least one cell must run structure 3, or the per-supplier half of this clause never ran.
    """
    world = load_world()
    rule = load_tuning_spec().rule
    skus = sorted(world.structure_3.sku_supplier)
    supplied_cells = 0
    for cell in sorted(world.cells):
        resolved = world.resolve(cell)
        groups = sorted(set(sku_groups(resolved, skus).values()))
        boxes = derive_candidates(resolved, groups, rule, rate_per_sku_per_min=rate)

        assert sorted(boxes) == groups, f"cell {cell}: boxes for {sorted(boxes)}, groups {groups}"
        for group, box in boxes.items():
            assert box, f"cell {cell}: group {group} derived an empty box"
            assert box[0] >= 1, f"cell {cell}: group {group} box {box} starts below 1"
            assert all(lower < upper for lower, upper in itertools.pairwise(box)), (
                f"cell {cell}: group {group} box {box} is not strictly ascending"
            )
        if resolved.structure_3_on:
            supplied_cells += 1
            assert ALL_SKUS_GROUP not in boxes, f"cell {cell} runs structure 3 yet grouped all"
        else:
            assert groups == [ALL_SKUS_GROUP], f"cell {cell} has no supply but groups {groups}"
    assert supplied_cells, "no committed cell runs structure 3"


# ---------------------------------------------------------------------------
# 12. (a), (b) The search ends at a certified minimum, never worse than the incumbent
# ---------------------------------------------------------------------------


@given(boxes=_boxes(low=1, high=300, min_size=1, min_groups=1), seeds=_SEED_LISTS, data=st.data())
def test_on_a_convex_separable_cost_the_search_converges_to_every_groups_exact_minimum(
    boxes: dict[str, list[int]], seeds: list[int], data: st.DataObject
) -> None:
    """(a), (b): converged, certified, EXACTLY ``(t - 1, t)`` per group, never above the incumbent.

    Each group's target ``t`` lies inside its box's span but not necessarily ON a candidate, so the
    refinement has to find it; the incumbent is base-stock, so the band never favours it. On this
    cost a unit-step local minimum is the global one, which is what lets the clause demand the
    exact optimum. Every number the selection reports is recomputed independently -- the
    incumbent's cost, the selected levels' cost, the absence of an improving unit move, and the
    cost-call count, ``evaluations`` vectors at every seed and no more. ``tie_broken`` must be
    FALSE: this cost is injective in ``S``, so a subject that sets the flag regardless fails here.
    """
    targets = {
        group: data.draw(st.integers(min_value=box[0], max_value=box[-1]))
        for group, box in boxes.items()
    }
    weights = {group: data.draw(st.integers(min_value=1, max_value=5)) for group in boxes}
    level = data.draw(st.integers(min_value=1, max_value=400))
    incumbent = GridPoint(s=level - 1, S=level)
    cost = _SeparableCost(targets=targets, weights=weights, bump=0)

    result = _search(boxes=boxes, incumbent=incumbent, seeds=seeds, cost_of=cost, rule=_SEARCH_RULE)

    assert result.converged, f"a convex cost refused: {result.refusal}"
    assert result.refusal is None
    chosen = {group: _pair(result.levels.for_group(group)) for group in boxes}
    assert chosen == {group: (target - 1, target) for group, target in targets.items()}, (
        f"targets {targets} but the search chose {chosen}"
    )
    assert not _improving_unit_moves(cost.at, result.levels.levels)
    assert result.incumbent_cost == cost.mean(dict.fromkeys(boxes, incumbent), seeds)
    assert result.mean_cost == cost.mean(result.levels.levels, seeds)
    assert result.mean_cost <= result.incumbent_cost
    assert result.tie_broken is False, "an injective cost cannot tie, yet a tie was reported"
    assert cost.calls, "a search that evaluated nothing reported a minimum from nowhere"
    assert len(cost.calls) == result.evaluations * len(seeds), (
        f"{len(cost.calls)} calls for {result.evaluations} evaluation(s) x {len(seeds)} seed(s)"
    )


@given(
    boxes=_boxes(low=1, high=300, min_size=1, min_groups=1),
    seeds=_SEED_LISTS,
    incumbent=_GRID_POINTS,
    data=st.data(),
)
def test_on_any_separable_cost_the_result_is_never_costlier_than_the_incumbent(
    boxes: dict[str, list[int]], seeds: list[int], incumbent: GridPoint, data: st.DataObject
) -> None:
    """(b) for convex AND non-convex costs and any incumbent; (a) whenever the search converged.

    The bump term breaks convexity, so a converged result may be a LOCAL minimum -- which is all
    the certificate claims and all this clause asserts. A refused result must name one of the two
    refusals and still report levels whose cost is the one it states, no worse than the incumbent.
    """
    targets = {group: data.draw(st.integers(min_value=1, max_value=400)) for group in boxes}
    weights = {group: data.draw(st.integers(min_value=1, max_value=5)) for group in boxes}
    bump = data.draw(st.integers(min_value=0, max_value=200))
    cost = _SeparableCost(targets=targets, weights=weights, bump=bump)

    result = _search(boxes=boxes, incumbent=incumbent, seeds=seeds, cost_of=cost, rule=_SEARCH_RULE)

    assert result.mean_cost <= result.incumbent_cost, (
        f"the search ended at {result.mean_cost!r}, above the incumbent {result.incumbent_cost!r}"
    )
    assert result.incumbent_cost == cost.mean(dict.fromkeys(boxes, incumbent), seeds)
    assert result.mean_cost == cost.mean(result.levels.levels, seeds)
    if result.converged:
        assert result.refusal is None
        moves = _improving_unit_moves(cost.at, result.levels.levels)
        assert not moves, f"a converged result is improved by the unit move(s) {moves}"
    else:
        assert result.refusal is not None
        assert result.refusal.startswith((BOUNDARY_REFUSAL, NON_CONVERGENCE_REFUSAL)), (
            f"an unconverged result carries an undeclared refusal: {result.refusal!r}"
        )


def test_a_non_convex_cost_can_still_be_certified_and_the_certificate_is_checked() -> None:
    """Pins the conditional branch above to a case that reaches it.

    The cost is genuinely non-convex along base-stock ``S`` -- a second difference near its target
    is negative, asserted below -- and the search still converges there, to a point no unit move
    improves.
    """
    cost = _SeparableCost(targets={"g_a": 50}, weights={"g_a": 1}, bump=3)

    result = _search(
        boxes={"g_a": [20, 40, 60, 80]},
        incumbent=GridPoint(s=0, S=200),
        seeds=[1000],
        cost_of=cost,
        rule=_SEARCH_RULE,
    )

    assert result.converged, f"refused: {result.refusal}"
    assert result.refusal is None
    assert not _improving_unit_moves(cost.at, result.levels.levels)
    assert result.mean_cost < result.incumbent_cost
    along = [cost.at({"g_a": GridPoint(s=upper - 1, S=upper)}) for upper in range(40, 61)]
    seconds = [
        right - 2 * middle + left
        for left, middle, right in zip(along, along[1:], along[2:], strict=False)
    ]
    assert min(seconds) < 0, "the cost is convex on [40, 60], so this clause tests nothing new"


def test_an_optimum_three_below_the_par_level_is_certified_only_by_moving_s_alone() -> None:
    """R3, by construction: the optimum is ``(S - 3, S)``, which only an ``s``-move can reach.

    The cost is ``10 |S - 40| + |(S - s) - 3|``: band 3 at ``S = 40`` is free, base-stock there
    costs 2. Every trial the first version-2 search made kept band 1 (the coordinate passes and
    refinement), a declared gap, or the incumbent's band -- and 3 is none of them -- so it ended at
    ``(39, 40)``, where its own certificate held: no band-kept ``S -+ 1`` move improves it. One
    ``s``-step does. The repaired certificate must take two and certify ``(37, 40)``.
    """
    target, band = 40, 3
    cost = _PointCost(lambda point: 10 * abs(point.S - target) + abs(point.S - point.s - band))
    incumbent = GridPoint(s=0, S=100)

    result = _search(
        boxes={"g_a": [20, 40, 60]},
        incumbent=incumbent,
        seeds=[1000],
        cost_of=cost,
        rule=_SEARCH_RULE,
    )

    assert result.converged, f"refused: {result.refusal}"
    assert _pair(result.levels.for_group("g_a")) == (target - band, target), (
        f"the search certified {result.levels.for_group('g_a').label}, not s{target - band}_S40"
    )
    assert not _improving_unit_moves(cost.at, result.levels.levels)
    assert result.mean_cost == 0.0

    old_end = {"g_a": GridPoint(s=target - 1, S=target)}
    old_moves = [{"g_a": point} for point in _band_kept_neighbours(old_end["g_a"])]
    assert all(cost.at(moved) >= cost.at(old_end) for moved in old_moves), (
        "the band-kept certificate would not have held at (39, 40), so this case shows nothing"
    )
    s_step = f"g_a:{GridPoint(s=target - 2, S=target).label}"
    assert s_step in _improving_unit_moves(cost.at, old_end), (
        f"the s-step {s_step} does not improve (39, 40), so this case is not R3's blind spot"
    )
    reachable = {1, incumbent.S - incumbent.s, *_SEARCH_RULE.gaps}
    assert band not in reachable, f"band {band} was reachable without an s-move: {reachable}"


def test_base_stock_is_re_tried_at_the_refined_level_where_no_unit_move_reaches_it() -> None:
    """R3, by construction: after refinement, base-stock at the refined ``S`` is tried again.

    The band costs 0 at 1, 3 at 10 (the incumbent's), and 50 everywhere else, so from a band of 10
    no unit move -- in ``s``, in ``S``, or both -- can improve, and every declared gap is >= 2 by
    the rule's own validation. The box sits far from ``S = 40``, so the coordinate passes keep the
    incumbent and refinement carries its band of 10 to ``(30, 40)``. Only the re-try reaches
    ``(39, 40)``: a search without it certifies ``(30, 40)``, a strict local minimum of every unit
    move, at cost 3 instead of 0.
    """
    band_cost = {1: 0, 10: 3}
    cost = _PointCost(lambda point: 10 * abs(point.S - 40) + band_cost.get(point.S - point.s, 50))

    result = _search(
        boxes={"g_a": [5, 100]},
        incumbent=GridPoint(s=25, S=35),
        seeds=[1000],
        cost_of=cost,
        rule=_SEARCH_RULE,
    )

    assert result.converged, f"refused: {result.refusal}"
    assert _pair(result.levels.for_group("g_a")) == (39, 40), (
        f"the search certified {result.levels.for_group('g_a').label}, not base-stock at 40"
    )
    assert result.mean_cost == 0.0
    stranded = {"g_a": GridPoint(s=30, S=40)}
    assert not _improving_unit_moves(cost.at, stranded), (
        "a unit move leaves (30, 40), so the re-try is not what this case proves"
    )


def test_no_selection_is_built_costlier_than_its_incumbent_or_converged_with_a_refusal() -> None:
    """The invariant is enforced where the record is made, so no record can carry its negation.

    ``mean_cost <= incumbent_cost`` raises an ``AssertionError`` naming the invariant -- a nan
    fails it too -- and ``converged`` must hold exactly when ``refusal`` is ``None``. ``ranked``
    must be non-empty, ascending, distinct, no longer than ``evaluations``, and headed by a
    converged selection; each defect is built once and refused by name, beside a control that
    ties at the top and still constructs.
    """
    levels = GroupLevels({"g_a": GridPoint(s=0, S=1)})
    other = GroupLevels({"g_a": GridPoint(s=0, S=2)})
    third = GroupLevels({"g_a": GridPoint(s=0, S=3)})
    headed = ((levels, 1.0), (other, 1.0))

    def build(
        *,
        mean: float,
        converged: bool,
        refusal: str | None,
        ranked: tuple[tuple[GroupLevels, float], ...],
    ) -> GroupTunedSelection:
        return GroupTunedSelection(
            levels=levels,
            mean_cost=mean,
            incumbent_cost=1.0,
            evaluations=2,
            passes=0,
            converged=converged,
            refusal=refusal,
            candidates={"g_a": (1,)},
            tie_broken=False,
            ranked=ranked,
        )

    control = build(mean=1.0, converged=True, refusal=None, ranked=headed)
    assert control.converged, "the control must construct"
    for mean in (2.0, math.nan):
        with pytest.raises(AssertionError, match="mean_cost <= incumbent_cost"):
            build(mean=mean, converged=True, refusal=None, ranked=((levels, mean),))
    with pytest.raises(TuningUnavailableError):
        build(mean=1.0, converged=True, refusal=BOUNDARY_REFUSAL, ranked=headed)
    with pytest.raises(TuningUnavailableError):
        build(mean=1.0, converged=False, refusal=None, ranked=headed)
    malformed: dict[str, tuple[tuple[GroupLevels, float], ...]] = {
        "empty": (),
        "descending": ((levels, 1.0), (other, 0.5)),
        "repeated": ((levels, 1.0), (levels, 1.0)),
        "longer than evaluated": ((levels, 1.0), (other, 1.0), (third, 1.0)),
        "headed by another vector": ((other, 1.0), (levels, 1.0)),
    }
    for defect, ranked in malformed.items():
        try:
            build(mean=1.0, converged=True, refusal=None, ranked=ranked)
        except TuningUnavailableError as error:
            assert "ranked" in str(error), f"{defect}: refused for another reason: {error}"
        else:
            pytest.fail(f"a ranked list that is {defect} was accepted")


# ---------------------------------------------------------------------------
# 13. (c), (d) Refusal BY CONSTRUCTION: the box boundary, a spent budget, an undeclared search
# ---------------------------------------------------------------------------


@given(
    boxes=_boxes(low=1, high=300, min_size=1, min_groups=1),
    seeds=_SEED_LISTS,
    incumbent=_GRID_POINTS,
)
def test_a_cost_falling_past_every_extension_is_refused_at_the_upper_box_boundary(
    boxes: dict[str, list[int]], seeds: list[int], incumbent: GridPoint
) -> None:
    """(c), upward. ``-S`` falls without bound, so the cost is still falling after every extension.

    Every group climbs to the top of its box, the box extends ``max_extensions`` times, and the
    search must REFUSE rather than certify the box's edge as a minimum. The refused group -- the
    first in sorted order, since all of them sit on the edge -- grew by exactly ``max_extensions``
    candidates, so the whole extension budget was spent before the refusal, and it holds an ``S``
    at or above every candidate it was given.
    """
    cost = _OrderUpToCost(lambda upper: -upper)

    result = _search(boxes=boxes, incumbent=incumbent, seeds=seeds, cost_of=cost, rule=_SEARCH_RULE)

    first = min(boxes)
    held = result.levels.for_group(first).S
    assert not result.converged
    assert result.refusal is not None
    assert result.refusal.startswith(BOUNDARY_REFUSAL), result.refusal
    assert repr(first) in result.refusal, f"the refusal does not name {first!r}: {result.refusal}"
    grown = len(result.candidates[first]) - len(boxes[first])
    assert grown == _SEARCH_RULE.max_extensions, f"{first} grew by {grown} candidate(s)"
    assert max(result.candidates[first]) <= held, f"{first} holds S={held} inside its box"
    assert result.mean_cost <= result.incumbent_cost
    assert cost.calls == result.evaluations * len(seeds)


@given(boxes=_boxes(low=16, high=300, min_size=2, min_groups=1), seeds=_SEED_LISTS, data=st.data())
def test_a_cost_rising_past_every_extension_is_refused_at_the_lower_box_boundary(
    boxes: dict[str, list[int]], seeds: list[int], data: st.DataObject
) -> None:
    """(c), downward. ``+S`` rises everywhere, so the cost is still rising below every extension.

    Boxes start at 16 or above, hold two or more candidates (so no upward extension is ever due),
    and the incumbent's ``S`` is at or above the smallest box start, so after three halvings the
    held ``S`` is still above 1 -- the floor where a minimum would be genuine rather than a
    boundary. The refused group's box grew downward by exactly ``max_extensions`` candidates.
    """
    lowest = min(box[0] for box in boxes.values())
    upper = data.draw(st.integers(min_value=lowest, max_value=400))
    band = data.draw(st.integers(min_value=1, max_value=upper))
    incumbent = GridPoint(s=upper - band, S=upper)
    cost = _OrderUpToCost(lambda level: level)

    result = _search(boxes=boxes, incumbent=incumbent, seeds=seeds, cost_of=cost, rule=_SEARCH_RULE)

    first = min(boxes)
    held = result.levels.for_group(first).S
    assert not result.converged
    assert result.refusal is not None
    assert result.refusal.startswith(BOUNDARY_REFUSAL), result.refusal
    assert repr(first) in result.refusal, f"the refusal does not name {first!r}: {result.refusal}"
    grown = len(result.candidates[first]) - len(boxes[first])
    assert grown == _SEARCH_RULE.max_extensions, f"{first} grew by {grown} candidate(s)"
    assert held <= min(result.candidates[first]), f"{first} holds S={held} inside its box"
    assert held > 1, f"{first} reached S={held}, where no lower box exists to refuse"


@given(
    boxes=_boxes(low=1, high=300, min_size=3, min_groups=2),
    seeds=_SEED_LISTS,
    incumbent=_GRID_POINTS,
    budget=st.integers(min_value=1, max_value=3),
    data=st.data(),
)
def test_a_budget_spent_before_the_certificate_is_refused_as_non_convergence(
    boxes: dict[str, list[int]],
    seeds: list[int],
    incumbent: GridPoint,
    budget: int,
    data: st.DataObject,
) -> None:
    """(d). A budget of one to three is spent BY CONSTRUCTION.

    Two or more groups with three or more candidates each need at least five evaluations in the
    first pass alone -- the incumbent, plus two trials per group that differ from the held point.
    The search must stop at EXACTLY its budget, report non-convergence, and still return the best
    point it costed, at that point's own cost.
    """
    targets = {group: data.draw(st.integers(min_value=1, max_value=400)) for group in boxes}
    weights = {group: data.draw(st.integers(min_value=1, max_value=5)) for group in boxes}
    cost = _SeparableCost(targets=targets, weights=weights, bump=0)
    rule = dataclasses.replace(_SEARCH_RULE, max_evaluations=budget)

    result = _search(boxes=boxes, incumbent=incumbent, seeds=seeds, cost_of=cost, rule=rule)

    assert not result.converged
    assert result.refusal is not None
    assert result.refusal.startswith(NON_CONVERGENCE_REFUSAL), result.refusal
    assert result.evaluations == budget, f"{result.evaluations} evaluation(s) on budget {budget}"
    assert len(cost.calls) == budget * len(seeds), "the budget was exceeded off the books"
    assert result.mean_cost <= result.incumbent_cost
    assert result.mean_cost == cost.mean(result.levels.levels, seeds)


def test_the_group_search_refuses_an_undeclared_search_before_costing_anything() -> None:
    """Each malformed input is refused BEFORE ``cost_of`` is called.

    Candidates that do not cover exactly the groups, a repeated or sub-1 candidate, a repeated
    group, and an empty or repeated seed list: a refusal that did the work first would have
    searched something nobody declared. The corrected call is then searched, so the zero is real.
    """
    incumbent = GridPoint(s=1, S=2)
    cost = _OrderUpToCost(lambda upper: upper)
    cases: list[tuple[list[str], dict[str, list[int]], list[int]]] = [
        (["g_a", "g_b"], {"g_a": [5]}, [1000]),
        (["g_a"], {"g_a": [5], "g_b": [5]}, [1000]),
        (["g_a"], {"g_a": [5, 5]}, [1000]),
        (["g_a"], {"g_a": [0, 5]}, [1000]),
        (["g_a", "g_a"], {"g_a": [5]}, [1000]),
        (["g_a"], {"g_a": [5]}, []),
        (["g_a"], {"g_a": [5]}, [1000, 1000]),
    ]
    for groups, candidates, seeds in cases:
        with pytest.raises(TuningUnavailableError):
            tune_group_levels(
                groups=groups,
                candidates=candidates,
                incumbent=incumbent,
                seeds=seeds,
                cost_of=cost,
                rule=_SEARCH_RULE,
            )
    assert cost.calls == 0, f"refused searches still made {cost.calls} cost call(s)"

    tune_group_levels(
        groups=["g_a"],
        candidates={"g_a": [5]},
        incumbent=incumbent,
        seeds=[1000],
        cost_of=cost,
        rule=_SEARCH_RULE,
    )
    assert cost.calls > 0, "the corrected search made no cost call, so the zero above is moot"


@pytest.mark.parametrize("bad", [math.nan, math.inf, -math.inf])
def test_a_non_finite_cost_is_raised_by_the_group_search_rather_than_reported(bad: float) -> None:
    """A nan or an infinity is a defect in the cost, not an outcome of the search: it RAISES.

    Only the two declared refusals are reported; reporting this one would hand the caller a
    selection whose cost is no minimum of anything.
    """

    def poisoned(seed: int, levels: GroupLevels) -> float:
        upper = levels.for_group("g_a").S
        return bad if upper == 5 else float(seed % 3)

    with pytest.raises(TuningUnavailableError):
        tune_group_levels(
            groups=["g_a"],
            candidates={"g_a": [5, 9]},
            incumbent=GridPoint(s=1, S=2),
            seeds=[1000],
            cost_of=poisoned,
            rule=_SEARCH_RULE,
        )


# ---------------------------------------------------------------------------
# 14. (e) Determinism, and the declared tie-break
# ---------------------------------------------------------------------------


@given(
    boxes=_boxes(low=1, high=300, min_size=1, min_groups=1),
    seeds=_SEED_LISTS,
    incumbent=_GRID_POINTS,
    data=st.data(),
)
def test_the_search_is_deterministic_and_blind_to_the_order_its_inputs_are_listed_in(
    boxes: dict[str, list[int]], seeds: list[int], incumbent: GridPoint, data: st.DataObject
) -> None:
    """(e). One problem, three runs, one selection and one sequence of evaluations.

    The same problem twice gives the same selection AND the same calls in the same order; the
    problem with its groups, every box and the seeds listed in REVERSE gives both again. A subject
    whose result depended on insertion order -- of a YAML list, of a dict -- fails the second half.
    """
    targets = {group: data.draw(st.integers(min_value=1, max_value=400)) for group in boxes}
    weights = {group: data.draw(st.integers(min_value=1, max_value=5)) for group in boxes}
    bump = data.draw(st.integers(min_value=0, max_value=50))
    reversed_boxes = {group: list(reversed(boxes[group])) for group in reversed(list(boxes))}

    runs: list[tuple[GroupTunedSelection, _SeparableCost]] = []
    problems = ((boxes, seeds), (boxes, seeds), (reversed_boxes, list(reversed(seeds))))
    for listed_boxes, listed_seeds in problems:
        cost = _SeparableCost(targets=targets, weights=weights, bump=bump)
        selection = _search(
            boxes=listed_boxes,
            incumbent=incumbent,
            seeds=listed_seeds,
            cost_of=cost,
            rule=_SEARCH_RULE,
        )
        runs.append((selection, cost))

    (first, first_cost), (again, again_cost), (flipped, flipped_cost) = runs
    assert again == first, "the same problem gave two different selections"
    assert again_cost.trace() == first_cost.trace(), "the same problem was searched differently"
    assert flipped == first, "listing the inputs in reverse changed the selection"
    assert flipped_cost.trace() == first_cost.trace(), "listing in reverse changed the search"


def test_a_trial_tying_the_held_point_leaves_the_held_point_and_is_reported() -> None:
    """(e), tie-break 1: a tie with the HELD point keeps it -- here the incumbent itself.

    The cost depends on ``S`` alone and is zero at ``S = 50``, so base-stock ``(49, 50)`` and every
    gap trial at ``S = 50`` tie the incumbent ``(10, 50)`` exactly. The incumbent must be kept,
    ``tie_broken`` set, and the result still certified.
    """
    incumbent = GridPoint(s=10, S=50)

    result = _search(
        boxes={"g_a": [50, 70]},
        incumbent=incumbent,
        seeds=[1000],
        cost_of=_OrderUpToCost(lambda upper: abs(upper - 50)),
        rule=_SEARCH_RULE,
    )

    assert result.levels.for_group("g_a") == incumbent, (
        f"a tie moved the held point to {result.levels.for_group('g_a').label}"
    )
    assert result.tie_broken is True, "a tie with the held point was not reported"
    assert result.converged, f"refused: {result.refusal}"
    assert result.mean_cost == result.incumbent_cost


def test_two_improving_trials_that_tie_leave_the_lower_order_up_to_level() -> None:
    """(e), tie-break 2: two trials tying each other, both better than the held point, keep the
    LOWER ``S`` -- the first in a scan that always runs lowest ``S`` first.

    The cost is zero on ``40 <= S <= 60`` and the incumbent ``(0, 200)`` sits far above it, so
    ``(39, 40)`` and ``(59, 60)`` tie as the best candidates; every later trial inside the plateau
    ties too. The result must be ``(39, 40)``, with the tie reported.
    """
    result = _search(
        boxes={"g_a": [40, 60, 90]},
        incumbent=GridPoint(s=0, S=200),
        seeds=[1000],
        cost_of=_OrderUpToCost(lambda upper: max(0, 40 - upper) + max(0, upper - 60)),
        rule=_SEARCH_RULE,
    )

    assert _pair(result.levels.for_group("g_a")) == (39, 40), (
        f"the tie resolved to {result.levels.for_group('g_a').label}, not the lower S"
    )
    assert result.tie_broken is True, "a tie between improving trials was not reported"
    assert result.converged, f"refused: {result.refusal}"
    assert result.mean_cost < result.incumbent_cost


# ---------------------------------------------------------------------------
# 15. (g) Every split term is the float difference it names; the float residual is reported
# ---------------------------------------------------------------------------


def _assert_terms_are_their_named_differences(
    *, reference: float, tuned: float, structure_aware: float, hindsight: float
) -> float:
    """Split the four means, assert every term is its ONE named subtraction, return the residual
    the REPORTED terms leave -- which the caller compares with ``residual_float``."""
    split = three_term_split(
        reference=reference, tuned=tuned, structure_aware=structure_aware, hindsight=hindsight
    )
    reported = (
        split.tuning_gap,
        split.achievable_information_value,
        split.residual_information_value,
        split.information_ceiling,
        split.regret,
    )
    assert reported == (
        reference - tuned,
        tuned - structure_aware,
        structure_aware - hindsight,
        tuned - hindsight,
        reference - hindsight,
    ), f"a term is not the subtraction its name says: {reported}"
    residual = split.regret - (
        split.tuning_gap + split.achievable_information_value + split.residual_information_value
    )
    assert split.residual_float == residual, (
        f"reported residual {split.residual_float!r}, but the reported terms leave {residual!r}"
    )
    return split.residual_float


@given(reference=_MEANS, tuned=_MEANS, structure_aware=_MEANS, hindsight=_MEANS)
def test_every_three_term_split_term_is_exactly_the_float_difference_it_names(
    reference: float, tuned: float, structure_aware: float, hindsight: float
) -> None:
    """(g), corrected (R5): the claim that CAN fail replaces ``identity_exact``.

    That flag was the identity over ``Fraction`` -- a theorem, true for every finite input, so
    asserting it on a run asserted nothing. What can fail is that each float term is the ONE
    subtraction its name says: a ceiling formed as ``achievable + residual``, say, differs from
    ``tuned - hindsight`` in IEEE 754 and fails here. ``residual_float`` must be exactly the
    residual of the reported terms, summed left to right as documented, and finite.
    """
    residual = _assert_terms_are_their_named_differences(
        reference=reference, tuned=tuned, structure_aware=structure_aware, hindsight=hindsight
    )
    assert math.isfinite(residual)


@given(
    reference=_EXACT_COSTS,
    tuned=_EXACT_COSTS,
    structure_aware=_EXACT_COSTS,
    hindsight=_EXACT_COSTS,
)
def test_the_three_term_float_residual_vanishes_on_the_exactly_representable_subdomain(
    reference: int, tuned: int, structure_aware: int, hindsight: int
) -> None:
    """On integral means below ``2**20`` every subtraction and sum is exact, so the residual is
    ``0.0`` on the nose -- the clause that binds the identity to the CODE, not to ``Fraction``."""
    split = three_term_split(
        reference=float(reference),
        tuned=float(tuned),
        structure_aware=float(structure_aware),
        hindsight=float(hindsight),
    )

    assert split.residual_float == 0.0, f"residual {split.residual_float!r} on exact inputs"


def test_a_non_zero_float_residual_is_reported_while_every_term_is_its_named_difference() -> None:
    """The residual belongs to the SUMMATION, not to the terms, and is reported, not repaired.

    On the lossy quadruple the two huge terms cancel to zero and the float residual is the whole
    small term, while every term is still exactly the subtraction its name says. A subject that
    re-formed a term to force the residual to zero would fail the term clause here.
    """
    residual = _assert_terms_are_their_named_differences(
        reference=_LOSSY_REFERENCE,
        tuned=_LOSSY_TUNED,
        structure_aware=_LOSSY_HINDSIGHT,
        hindsight=_LOSSY_HINDSIGHT,
    )

    assert residual != 0.0, "the lossy quadruple no longer exhibits cancellation"


@pytest.mark.parametrize("bad", [math.nan, math.inf, -math.inf])
def test_a_non_finite_mean_is_refused_rather_than_split(bad: float) -> None:
    """A nan or an infinity has no exact value to split, whichever arm's mean it is."""
    names = ("reference", "tuned", "structure_aware", "hindsight")
    for name in names:
        means = dict.fromkeys(names, 1.0)
        means[name] = bad
        with pytest.raises(TuningUnavailableError, match=f"non-finite {name} mean"):
            three_term_split(**means)


# ---------------------------------------------------------------------------
# 16. The policy class: Par_Level_Reorder's rule, one pair per group
# ---------------------------------------------------------------------------

_SKU_NAMES = st.text(alphabet="abcdefghij_0123456789", min_size=1, max_size=6)
_PIPELINE = st.floats(min_value=0.0, max_value=1e6, allow_nan=False, allow_infinity=False)


@st.composite
def _stock_either_side(
    draw: st.DrawFn, point: GridPoint
) -> tuple[dict[str, int], dict[str, float]]:
    """Stock with one SKU that must order and one that must not, plus generated others.

    The first SKU sits at or below ``s`` with nothing in transit; the second sits above ``S``.
    Built per branch rather than filtered, so every example exercises both the top-up and the hold.
    """
    names = draw(st.lists(_SKU_NAMES, min_size=2, max_size=6, unique=True))
    inventory = {
        names[0]: draw(st.integers(min_value=0, max_value=point.s)),
        names[1]: point.S + draw(st.integers(min_value=1, max_value=50)),
    }
    on_order: dict[str, float] = {}
    for sku in names[2:]:
        inventory[sku] = draw(st.integers(min_value=0, max_value=point.S + 50))
        if draw(st.booleans()):
            on_order[sku] = draw(_PIPELINE)
    return inventory, on_order


@given(point=_GRID_POINTS, seed=st.integers(min_value=0, max_value=2**31 - 1), data=st.data())
def test_with_one_group_the_tuned_static_arm_decides_exactly_as_par_level_reorder(
    point: GridPoint, seed: int, data: st.DataObject
) -> None:
    """Structure 3 off: one group, and the decision is ``Par_Level_Reorder``'s, to the bit.

    Compared as whole ``PolicyAction`` records, so a stray price or routing field fails too. Both
    branches of the rule are reached in every example (one SKU orders, one does not).
    """
    inventory, on_order = data.draw(_stock_either_side(point))
    arm = GroupParLevelReorder(
        GroupLevels({ALL_SKUS_GROUP: point}), dict.fromkeys(inventory, ALL_SKUS_GROUP), seed=seed
    )
    observation = _observation(inventory, on_order)

    decided = arm.decide(observation)

    assert decided == Par_Level_Reorder(point.s, point.S, seed=seed).decide(observation)
    quantities = list(decided.reorder_quantities.values())
    assert any(quantity > 0.0 for quantity in quantities), "no SKU ordered: no top-up was tested"
    assert any(quantity == 0.0 for quantity in quantities), "every SKU ordered: no hold was tested"


@given(data=st.data())
def test_every_sku_is_decided_by_par_level_reorder_at_its_own_groups_levels(
    data: st.DataObject,
) -> None:
    """Per group: each SKU's quantity is ``Par_Level_Reorder``'s at ITS group's ``(s, S)``.

    Every one of the three groups decides at least one SKU, so a subject that used one group's
    levels for all of them fails whenever the generated levels differ.
    """
    levels = {group: data.draw(_GRID_POINTS) for group in _GROUP_NAMES}
    skus = data.draw(st.lists(_SKU_NAMES, min_size=len(_GROUP_NAMES), max_size=8, unique=True))
    sku_group = {sku: _GROUP_NAMES[index % len(_GROUP_NAMES)] for index, sku in enumerate(skus)}
    inventory = {
        sku: data.draw(st.integers(min_value=0, max_value=levels[sku_group[sku]].S + 50))
        for sku in skus
    }
    on_order = {sku: data.draw(_PIPELINE) for sku in skus if data.draw(st.booleans())}
    arm = GroupParLevelReorder(GroupLevels(levels), sku_group, seed=0)

    decided = arm.decide(_observation(inventory, on_order)).reorder_quantities

    assert set(sku_group.values()) == set(_GROUP_NAMES)
    assert set(decided) == set(inventory)
    for sku in skus:
        point = levels[sku_group[sku]]
        pipeline = {sku: on_order[sku]} if sku in on_order else {}
        alone = _observation({sku: inventory[sku]}, pipeline)
        expected = Par_Level_Reorder(point.s, point.S, seed=0).decide(alone).reorder_quantities
        assert decided[sku] == expected[sku], (
            f"{sku} in group {sku_group[sku]} decided {decided[sku]!r}, not {expected[sku]!r}"
        )


def test_the_tuned_static_arm_is_arm_e_and_refuses_what_it_cannot_decide() -> None:
    """A ``DecisionPolicy`` named as arm E, refusing loudly and by name.

    A ``sku_group`` naming an untuned group is refused at CONSTRUCTION, not at the first decision
    of a CI-only run; an observed SKU with no group is refused at decision time; an untuned group
    and an empty mapping are refused by ``GroupLevels``. That ``TUNED_STATIC_ARM`` is one of the
    comparator's arm labels is pinned once, by Property 96, and deliberately not again here.
    """
    levels = GroupLevels({"sup_x": GridPoint(s=4, S=5)})
    arm = GroupParLevelReorder(levels, {"sku_a": "sup_x"}, seed=7)

    assert isinstance(arm, DecisionPolicy)
    assert arm.name == TUNED_STATIC_ARM
    assert arm.seed == 7
    assert arm.decide(_observation({"sku_a": 0}, {})).reorder_quantities == {"sku_a": 5.0}

    with pytest.raises(KeyError, match="sup_y"):
        GroupParLevelReorder(levels, {"sku_a": "sup_y"}, seed=0)
    with pytest.raises(KeyError, match="sku_b"):
        arm.decide(_observation({"sku_b": 0}, {}))
    with pytest.raises(KeyError, match="sup_z"):
        levels.for_group("sup_z")
    with pytest.raises(TuningUnavailableError):
        GroupLevels({})
    with pytest.raises(TuningUnavailableError):
        GroupParLevelReorder(levels, {}, seed=0)


@given(
    points=st.dictionaries(
        keys=st.sampled_from(_GROUP_NAMES), values=_GRID_POINTS, min_size=1, max_size=3
    )
)
def test_group_levels_are_canonical_in_any_build_order_and_cannot_be_moved_afterwards(
    points: dict[str, GridPoint],
) -> None:
    """The recorded result of the search is canonical, JSON-safe and immutable.

    Built in either order it is the same record with the same hash; ``as_dict`` lists groups and
    keys sorted, so plain ``json.dumps`` already equals the canonical form; and clearing the
    caller's dict afterwards cannot move the levels a selection reported.
    """
    forward = GroupLevels(dict(points))
    backward = GroupLevels(dict(reversed(list(points.items()))))

    assert forward == backward
    assert hash(forward) == hash(backward)
    exported = forward.as_dict()
    assert list(exported) == sorted(points)
    assert exported == {group: {"S": point.S, "s": point.s} for group, point in points.items()}
    canonical = json.dumps(exported, sort_keys=True, separators=(",", ":"))
    assert json.dumps(exported, separators=(",", ":")) == canonical, "as_dict is not canonical"
    assert json.loads(canonical) == exported

    source = dict(points)
    recorded = GroupLevels(source)
    source.clear()
    assert dict(recorded.levels) == points, "clearing the caller's dict moved the recorded levels"


def test_sku_groups_are_suppliers_with_structure_3_on_and_one_group_with_it_off() -> None:
    """Which pair each SKU uses: its supplier's when suppliers exist, the one shared pair if not.

    An unmapped SKU is refused, naming it, because the engine refuses to order it and a level that
    can never act is a level nobody can tune; an empty SKU list is refused because an arm over no
    SKU decides nothing.
    """
    supply = SupplyStructure(
        suppliers={
            "sup_x": SupplierSpec(mean_lead_time_min=10.0, log_sd=0.1),
            "sup_y": SupplierSpec(mean_lead_time_min=20.0, log_sd=0.2),
        },
        sku_supplier={"sku_a": "sup_x", "sku_b": "sup_y", "sku_c": "sup_x"},
        daily_autocorrelation=0.0,
        demand_coupling=0.0,
        coupling_floor=1.0,
        min_lead_time_min=1.0,
    )
    supplied = ResolvedWorld(cell="on", demand=None, supply=supply)
    unsupplied = ResolvedWorld(cell="off", demand=None, supply=None)
    skus = ["sku_c", "sku_a", "sku_b"]

    grouped = sku_groups(supplied, skus)
    assert grouped == {"sku_a": "sup_x", "sku_b": "sup_y", "sku_c": "sup_x"}
    assert list(grouped) == sorted(skus)
    assert sku_groups(unsupplied, skus) == dict.fromkeys(sorted(skus), ALL_SKUS_GROUP)
    assert sku_groups(None, skus) == sku_groups(unsupplied, skus)

    with pytest.raises(TuningUnavailableError, match="sku_q"):
        sku_groups(supplied, ["sku_a", "sku_q"])
    with pytest.raises(TuningUnavailableError):
        sku_groups(supplied, [])


# ---------------------------------------------------------------------------
# 17. The in-sample recheck's inputs (R1): `ranked` and `neighbours`
# ---------------------------------------------------------------------------


@given(
    boxes=_boxes(low=1, high=300, min_size=1, min_groups=1),
    seeds=_SEED_LISTS,
    incumbent=_GRID_POINTS,
    top_k=st.integers(min_value=1, max_value=8),
    budget=st.sampled_from([1, 2, 3, _SEARCH_RULE.max_evaluations]),
    data=st.data(),
)
def test_ranked_is_the_cheapest_distinct_vectors_evaluated_and_starts_at_the_selection(
    boxes: dict[str, list[int]],
    seeds: list[int],
    incumbent: GridPoint,
    top_k: int,
    budget: int,
    data: st.DataObject,
) -> None:
    """``ranked`` is recomputed from the cost-call log alone, and must equal it exactly.

    The log names every vector the search costed, in evaluation order; their means, ascending with
    ties in that order, cut at ``min(recheck_top_k, evaluations)``, are what ``ranked`` must be.
    ``ranked[0]`` must be ``(levels, mean_cost)`` on EVERY path -- converged, at a box boundary, or
    with the budget spent, all three of which the generated budgets reach -- because the search
    moves only on a strict improvement, so what it holds is the first vector costed at the minimum.
    That includes the refusals the interface allowed to differ, and it is what makes the recheck's
    first member the selection itself.
    """
    targets = {group: data.draw(st.integers(min_value=1, max_value=400)) for group in boxes}
    weights = {group: data.draw(st.integers(min_value=1, max_value=5)) for group in boxes}
    bump = data.draw(st.integers(min_value=0, max_value=50))
    cost = _SeparableCost(targets=targets, weights=weights, bump=bump)
    rule = dataclasses.replace(_SEARCH_RULE, recheck_top_k=top_k, max_evaluations=budget)

    result = _search(boxes=boxes, incumbent=incumbent, seeds=seeds, cost_of=cost, rule=rule)

    first_costed: dict[GroupLevels, int] = {}
    for _, levels in cost.calls:
        first_costed.setdefault(levels, len(first_costed))
    assert first_costed, "the search costed nothing, so ranked has nothing to rank"
    assert len(first_costed) == result.evaluations
    by_cost = sorted(
        ((levels, cost.mean(levels.levels, seeds)) for levels in first_costed),
        key=lambda item: (item[1], first_costed[item[0]]),
    )
    assert result.ranked == tuple(by_cost[:top_k]), (
        f"ranked {[(vector.as_dict(), mean) for vector, mean in result.ranked]} is not the "
        f"{top_k} cheapest vectors costed"
    )
    means = [mean for _, mean in result.ranked]
    assert means == sorted(means), f"ranked is not ascending: {means}"
    assert len({vector for vector, _ in result.ranked}) == len(result.ranked), "ranked repeats"
    assert len(result.ranked) == min(top_k, result.evaluations)
    assert result.ranked[0] == (result.levels, result.mean_cost), (
        f"ranked[0] is not the selection (refusal={result.refusal!r})"
    )


@given(
    points=st.dictionaries(
        keys=st.sampled_from(_GROUP_NAMES), values=_GRID_POINTS, min_size=1, max_size=3
    )
)
def test_neighbours_are_every_valid_single_group_unit_move_in_the_declared_order(
    points: dict[str, GridPoint],
) -> None:
    """``neighbours`` against an independent expectation, compared as a SEQUENCE.

    Per group in sorted order: ``(s - 1, S)``, ``(s + 1, S)``, ``(s, S - 1)``, ``(s, S + 1)``,
    the ones breaking ``0 <= s < S`` dropped -- ``1 + [s >= 1] + 2 [S - s >= 2]`` moves, never more
    than the four per group the recheck's budget projection counts. Each neighbour moves exactly
    one group, none repeats, and ``levels`` is not its own neighbour.
    """
    levels = GroupLevels(points)

    found = neighbours(levels)

    expected: list[dict[str, dict[str, int]]] = []
    for group in sorted(points):
        point = points[group]
        moves = (
            (point.s - 1, point.S),
            (point.s + 1, point.S),
            (point.s, point.S - 1),
            (point.s, point.S + 1),
        )
        for lower, upper in moves:
            if 0 <= lower < upper:
                expected.append({**levels.as_dict(), group: {"S": upper, "s": lower}})
    assert [vector.as_dict() for vector in found] == expected, "a neighbour or its order differs"
    assert found, "(s, S + 1) is always valid, so no neighbourhood can be empty"
    for group, point in points.items():
        moved = [vector for vector in found if vector.for_group(group) != point]
        count = 1 + int(point.s >= 1) + 2 * int(point.S - point.s >= 2)
        assert len(moved) == count, f"{group} at {point.label}: {len(moved)} moves, not {count}"
        assert len(moved) <= _MOVES_PER_GROUP, f"{group} exceeds the projected moves per group"
    assert len(set(found)) == len(found), "a neighbour is listed twice"
    assert levels not in found, "levels is listed as its own neighbour"
    for vector in found:
        changed = [group for group in points if vector.for_group(group) != points[group]]
        assert len(changed) == 1, f"{vector.as_dict()} moves {changed}, not exactly one group"


def test_neighbours_drop_invalid_moves_at_the_boundary_and_list_groups_in_sorted_order() -> None:
    """Pinned: ``(0, 1)`` has one neighbour, ``(0, 2)``; ``(5, 10)`` has all four, in the declared
    order -- so the projection's four per group is attained, a bound and not a guess; and groups
    come out sorted whatever order the levels were built in."""
    held = GridPoint(s=5, S=10)
    found = neighbours(GroupLevels({"g_b": held, "g_a": GridPoint(s=0, S=1)}))

    assert [vector.as_dict() for vector in found] == [
        {"g_a": {"S": 2, "s": 0}, "g_b": {"S": 10, "s": 5}},
        {"g_a": {"S": 1, "s": 0}, "g_b": {"S": 10, "s": 4}},
        {"g_a": {"S": 1, "s": 0}, "g_b": {"S": 10, "s": 6}},
        {"g_a": {"S": 1, "s": 0}, "g_b": {"S": 9, "s": 5}},
        {"g_a": {"S": 1, "s": 0}, "g_b": {"S": 11, "s": 5}},
    ]
    moved = [vector for vector in found if vector.for_group("g_b") != held]
    assert len(moved) == _MOVES_PER_GROUP, f"(5, 10) has {len(moved)} neighbours, not four"
