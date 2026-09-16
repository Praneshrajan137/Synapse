# Feature: decision-quality-proof, Property 81: The tuned static arm is the pre-registered grid's
# out-of-sample minimum, and the decomposition it induces is exact
"""Arm E's levels are the grid's out-of-sample minimum, and the split it induces sums exactly.

Session 10, ADR-055 D2.6, finding 61. Subject: ``uplift/tuning.py`` -- ``GridPoint``,
``load_tuning_spec``, ``tuning_seeds``, ``seed_overlap_refusal``, ``select_levels``,
``tune_par_level`` and ``decomposition_identity_residual`` -- together with the committed grid at
``infrastructure/quality/comparator-tuning.yaml``.

**Requirements.** R5.1 and R5.3 (the falsification test whose `material` verdict this arm
re-denominates) and R5.33 (the declared scalar objective the candidate costs are measured
against), plus the three criteria added by the R5.4 re-cut: **R5.41** -- a `material` verdict
attributable to baseline mis-tuning may not denominate E3's floor or the published claim;
**R5.42** -- the next comparator run SHALL include a tuned-static comparator arm and record the
information-gap term measured against it; **R5.43** -- that term decides whether R5.8-R5.14 and
R5.21-R5.23 are reinstated as in-scope. R5.42 is the criterion this module exists to make
satisfiable, and R5.43 is why its arithmetic has to be exact rather than approximately right.

**What the subject is for, in one paragraph.** ADR-055 D2.6 records that
``regret(incumbent - hindsight)`` is a sum of three terms -- a tuning gap, an information gap and
EVPI proper -- and that ``twin-regret.json`` reports the sum as one number labelled ``regret``.
Only the middle term is the quantity R5.1's claim is about. Arm E is the best static policy over a
committed grid, so it splits the judged contrast into ``[reference - tuned]`` and
``[tuned - hindsight]``: a tuning gap a grid search closes with no agent, no forecast and no
consensus, and an information ceiling no information-gathering activity can exceed.

**What would make this file wrong.** Any of: a selected pair that is not a member of the declared
grid; a selected pair that is not the grid's minimum; a tie resolved by the YAML file's line order
rather than by the declared key; a search that ran on seeds overlapping the measurement range; a
refusal that evaluated the grid anyway; or a decomposition asserted as exact in a domain where it
is not. Each has a clause below, and each clause can fail.

**Where the exactness stops, stated rather than papered over (R2.10, finding 56).** The
decomposition identity is a theorem over the reals -- the tuned mean appears once with each sign,
so it cancels -- and it is asserted here over ``fractions.Fraction``, where it holds for every
finite input. It is **not** a theorem over IEEE 754, and a clause below constructs the case that
proves so: a large term set against two nearly equal small ones, where the two huge magnitudes
cancel and destroy the small difference between them. Finding 56 was exactly this defect, found by
CI at 500 examples, and the repair then was to correct the claim's **domain** rather than to add a
tolerance. No tolerance appears anywhere in this file.

**No simulation runs here, and that is the feature rather than the gap.** ``tune_par_level`` takes
an injected ``cost_of(seed, point) -> float`` and does arithmetic on what it is handed, so every
clause below drives a synthetic cost function: no ``SupplyChainSimulation``, no ``start()``, no
``advance()``, no ``digital_twin`` import, no subprocess and no network. That is what lets the
argmin, the tie-break and **every refusal** be proven at the fast suite's budget instead of being
inferred from one twin run's output. A property over a snapshot can assert what a twin happened to
produce; this asserts what the search does.

**What this file does NOT establish, and it is the larger half.** It does not measure the
information ceiling and it does not settle finding 61's hypothesis -- that is the CI-only arm E run
D2.6 pre-registers as its own falsifier. And read from the tree rather than assumed: nothing calls
``tune_par_level`` yet, so what is proven here is a **capability**, not a use.

Budget inherited from the root ``conftest.py`` profile via ``HYPOTHESIS_PROFILE``. **No
``max_examples`` literal appears in this file** (CF-13), and no clause asserts a total.

Locus: ``ci.yml::uplift-verify`` fast shard 2/4 (``tests/uplift/test_[pqrstuvwxyz]*.py``, at the
``ci`` profile). **Not** slow-marked. The only file read is through the subject's own loader, which
passes ``encoding='utf-8'`` (E-S13-07), and every assertion message is ASCII.

**Validates: Requirements 5.1, 5.3, 5.33, 5.41, 5.42, 5.43**
"""

from __future__ import annotations

import math
from fractions import Fraction
from typing import Final

import pytest
from hypothesis import given
from hypothesis import strategies as st

from uplift.tuning import (
    DEFAULT_TUNING_PATH,
    GridPoint,
    TuningSpec,
    TuningUnavailableError,
    decomposition_identity_residual,
    load_tuning_spec,
    seed_overlap_refusal,
    select_levels,
    tune_par_level,
    tuning_seeds,
)

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

#: The incumbent's own levels. Read from the engine's defaults per ADR-055 D2.5.1 -- the lower one
#: from its restock threshold, the upper one from its initial-stock literal -- and declared a grid
#: member by ``comparator-tuning.yaml``'s own comment. "Read from the engine" is the definition of
#: untuned, which is precisely why the tuned search has to be able to reach it.
_INCUMBENT_LOWER: Final[int] = 50
_INCUMBENT_UPPER: Final[int] = 100

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


def _spec(*, grid: tuple[GridPoint, ...], start: int, count: int) -> TuningSpec:
    """A hand-built pre-registration, so the search is tested independently of the real file."""
    return TuningSpec(grid=grid, seed_start=start, seed_count=count, source="synthetic")


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

    **Why this matters, and it is a fact about the YAML file rather than about the search.**
    ``min()`` over a mapping resolves ties by insertion order, and the insertion order here is the
    order the candidates are written in ``comparator-tuning.yaml``. Under that behaviour,
    reordering the grid file -- an edit no reviewer would read as a change of policy -- would
    silently change which levels arm E uses, and the artifact would report a different tuned pair
    for a reason nobody recorded. So the tie-break is declared: lowest reorder point, then lowest
    par band.

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
    must not be biased toward the thing it is testing. Out-of-sample levels can only move the split
    the other way, which is the one direction in which a standard stricter than the criterion
    demands is legitimate.

    Driven as a biconditional rather than as a one-sided check, because a guard that refuses
    everything is as useless as one that refuses nothing and only the ``iff`` can fail for both.
    The reason is required to be non-blank: ``tune_par_level`` raises with this text as the whole
    of its message, so a refusal nobody can read is a refusal nobody can act on.
    """
    spec = _spec(grid=(GridPoint(s=0, S=10),), start=start, count=count)

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
    grid = (GridPoint(s=0, S=10),)

    disjoint = seed_overlap_refusal(
        _spec(grid=grid, start=replicates, count=5), measurement_replicates=replicates
    )
    assert disjoint is None, (
        f"a tuning range starting at the replicate count is disjoint, but got {disjoint!r}"
    )

    overlapping = seed_overlap_refusal(
        _spec(grid=grid, start=replicates - 1, count=5), measurement_replicates=replicates
    )
    assert overlapping is not None, (
        "a tuning range starting one seed below the replicate count overlaps it and must be refused"
    )
    assert overlapping.strip(), "the overlap refusal carries no reason"

    non_positive = seed_overlap_refusal(
        _spec(grid=grid, start=replicates, count=5), measurement_replicates=0
    )
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
    spec = _spec(grid=tuple(grid), start=start, count=count)
    counter = _CountingCost()

    with pytest.raises(TuningUnavailableError):
        tune_par_level(spec, cost_of=counter, measurement_replicates=start + excess)

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
    spec = _spec(grid=tuple(grid), start=replicates + extra, count=count)
    counter = _CountingCost()

    selection = tune_par_level(spec, cost_of=counter, measurement_replicates=replicates)

    assert counter.calls, "a disjoint search that evaluated nothing selected a pair from nowhere"
    assert len(counter.calls) == len(spec.grid) * spec.seed_count, (
        f"{len(counter.calls)} evaluation(s) for {len(spec.grid)} candidate(s) x "
        f"{spec.seed_count} seed(s)"
    )
    assert counter.points_seen == set(spec.grid), (
        "the search did not cover the declared grid; missing "
        f"{sorted(point.label for point in set(spec.grid) - counter.points_seen)}"
    )
    assert counter.seeds_seen == set(tuning_seeds(spec)), (
        f"the search ran on seeds {sorted(counter.seeds_seen)} rather than on the declared "
        f"{sorted(tuning_seeds(spec))}"
    )
    assert selection.seeds == tuning_seeds(spec), (
        f"the selection records seeds {selection.seeds} against a declared {tuning_seeds(spec)}"
    )
    assert set(selection.surface) == {point.label for point in spec.grid}, (
        f"the reported surface covers {sorted(selection.surface)} against a declared grid of "
        f"{sorted(point.label for point in spec.grid)}"
    )
    assert selection.levels in spec.grid, (
        f"selected {selection.levels.label}, which is not a declared candidate"
    )


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
    spec = _spec(grid=tuple(grid), start=replicates, count=count)
    counter = _CountingCost(offender=grid[0], offending_value=bad)

    with pytest.raises(TuningUnavailableError):
        tune_par_level(spec, cost_of=counter, measurement_replicates=replicates)

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
# 10. The COMMITTED grid is valid and contains the incumbent
# ---------------------------------------------------------------------------


def test_the_committed_tuning_grid_is_valid_and_contains_the_incumbent_levels() -> None:
    """The real ``comparator-tuning.yaml`` loads, and the incumbent's own levels are a candidate.

    **Why the membership clause carries the argument.** The incumbent's levels are ``s=50`` and
    ``S=100``, read from the engine -- the lower one from its restock threshold, the upper one from
    its initial-stock literal (ADR-055 D2.5.1). Because they are a grid member, the search's
    minimum **over the tuning seeds** can never be worse than the incumbent there. So a negative
    tuning gap on the **measurement** seeds is unambiguously an out-of-sample effect rather than an
    artefact of a grid that excluded the very thing it is compared against -- and that distinction
    is what R5.41's attribution turns on. Drop this point from the file and it is unrecoverable
    from the artifact alone.

    **What the validity clauses actually catch, stated honestly.** ``load_tuning_spec`` already
    refuses an out-of-order pair and a duplicate, so against today's file those two loops restate
    what the loader enforced during the load. Their falsifier is therefore not the file -- it is
    the **loader**: if that validation is removed or routed around, these clauses fail here with
    the offending candidate named, instead of an invalid pair reaching ``Par_Level_Reorder`` inside
    a CI-only run.

    Non-emptiness is asserted first, because every "every candidate satisfies" clause below is
    vacuously true over an empty grid.

    No count is asserted. The grid's size is a design choice argued in the file's own comment, and
    pinning it here would turn widening the search into a test edit (CF-13).
    """
    assert DEFAULT_TUNING_PATH.is_file(), (
        f"the committed tuning grid is missing at {DEFAULT_TUNING_PATH} -- arm E has no "
        "pre-registration to search"
    )

    spec = load_tuning_spec()

    assert spec.grid, f"{spec.source} loaded but declares no candidates"

    disordered = [point.label for point in spec.grid if not 0 <= point.s < point.S]
    assert not disordered, (
        f"{spec.source} carries candidate(s) violating 0 <= s < S: {disordered} -- the loader is "
        "no longer routing every entry through GridPoint's own validation"
    )

    identities = [(point.s, point.S) for point in spec.grid]
    assert len(set(identities)) == len(identities), (
        f"{spec.source} declares a candidate more than once, so the declared grid and the searched "
        "grid differ and the candidate count reported in the artifact would be wrong"
    )

    incumbent = GridPoint(s=_INCUMBENT_LOWER, S=_INCUMBENT_UPPER)
    assert incumbent in spec.grid, (
        f"the incumbent's own levels {incumbent.label} are not a candidate in {spec.source}, so a "
        "negative tuning gap could not be distinguished from a grid that excluded its own "
        f"comparator. Declared: {sorted(point.label for point in spec.grid)}"
    )


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
