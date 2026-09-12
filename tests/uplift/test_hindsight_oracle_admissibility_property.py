# Feature: decision-quality-proof, Property 80: A hindsight minimum over a family containing the
# subject can never yield a negative regret, and the cumulative-cover oracle covers every unit of
# outstanding demand while holding no buffer beyond it
"""The oracle is admissible by construction: it covers all outstanding demand and holds no buffer.

Session 9, task 11 option (b). Subjects: ``uplift/regret.py::hindsight_min`` and
``uplift/foresight.py::HindsightOraclePolicy`` (R5.1, R5.3, R5.33; ADR-055 D2.5.4).

**Why this property exists, measured rather than anticipated.** Run ``34570166681`` measured
``regret = -0.8123524459522771`` and run ``34590696403`` decomposed it: the arm labelled
``perfect_foresight`` leaves **8.2%** of demand unmet while the incumbent leaves none, so it did
not bound its own subject (findings 54, 59; ADR-055 D2.5.2, D2.5.3). Property 61 refuses that
measurement. This property asserts that the replacement **cannot** produce it, which is the
difference between a guard that fires and a comparator that does not need one.

**The two clauses that carry the argument, and neither is sufficient alone.** ``hindsight_min``
gives a floor whose non-negativity is a theorem about the FAMILY -- so it is asserted, and so is
its converse, because a guarantee that held for every family would be a claim about subtraction
rather than about membership. ``HindsightOraclePolicy`` gives an oracle whose zero-stockout claim
is a theorem about the CADENCE -- so the coverage inequality is asserted, and so is the
configuration in which it FAILS.

**Where the exactness stops, stated rather than papered over (R2.10, finding 56).** The coverage
and minimality claims are asserted over ``fractions.Fraction``, where they hold for every finite
input, and the arm's arithmetic is additionally exercised on integral units -- the domain the twin
actually produces, since ``DemandTrace.record`` defaults ``units=1.0`` and
``engine.py::_order_arrival`` calls it with that default. The one thing NOT asserted as a theorem
is the float-level aggregation: ``statistics.fmean`` sums and divides, so
``fmean(subject) >= fmean(minimum)`` is a fact about the reals and not about IEEE 754 -- the same
defect CI found in Property 61's first draft at 500 examples. The POINTWISE ordering is exact and
is asserted exactly; the AGGREGATED ordering is asserted over ``Fraction``. Adding a tolerance to
either would be asserting a blurrier claim in order to pass.

**No twin is constructed here.** ``HindsightOraclePolicy``'s order schedule is a pure function of
the recorded trace, the opening stock and the clock -- that is what "oracle by construction" buys
-- so every clause below is arithmetic over hand-built ``DemandTrace`` objects with no
``SupplyChainSimulation``, no ``start()``, no ``advance()``, no subprocess and no network. Arm
C's rule could never be asserted this way, because it reads twin inventory.

Budget inherited from the root ``conftest.py`` profile via ``HYPOTHESIS_PROFILE``. **No
``max_examples`` literal appears in this file** (CF-13).

Locus: ``ci.yml::uplift-verify`` fast step. **Not** slow-marked.
"""

from __future__ import annotations

from fractions import Fraction

import pytest
from hypothesis import given
from hypothesis import strategies as st

from digital_twin.simulation.engine import DemandTrace
from uplift.foresight import HindsightOraclePolicy
from uplift.interfaces import Observation
from uplift.regret import hindsight_min

#: Bounded and finite BY CONSTRUCTION rather than filtered afterwards, so no example is
#: discarded and the budget is spent on cases that count.
_COSTS = st.floats(min_value=0.0, max_value=1e6, allow_nan=False, allow_infinity=False)
_SKUS = st.sampled_from(["sku_0", "sku_1", "sku_2"])
#: Integral units, because that is what the twin records: `DemandTrace.record` defaults
#: `units=1.0` and `_order_arrival` uses the default. A precondition matching the subject.
_UNITS = st.integers(min_value=1, max_value=4)
_MINUTES = st.integers(min_value=0, max_value=600)
_OPENING = st.integers(min_value=0, max_value=200)
_EVENTS = st.lists(st.tuples(_MINUTES, _SKUS, _UNITS), min_size=0, max_size=12)
#: A cadence range, not a claim about cadence. The coverage theorem is independent of the window's
#: size -- it depends only on the window matching the decision interval -- so this range is chosen
#: for BUDGET: it keeps the boundary count per example in the tens rather than the hundreds. The
#: committed comparator runs at 60.0, which is inside it.
_WINDOWS = st.integers(min_value=30, max_value=180)
#: One minute past the last event a trace can carry, so the boundary walk always reaches a slice
#: in which every generated unit is due and the telescoping sum is complete.
_HORIZON_MIN = 601


def _trace(events: list[tuple[int, str, int]]) -> DemandTrace:
    """A hand-built demand path. Recorded at GENERATION time, exactly as the engine records it."""
    trace = DemandTrace()
    for t_min, sku, units in events:
        trace.record(t_min=float(t_min), sku=sku, units=float(units))
    return trace


def _arm(
    events: list[tuple[int, str, int]], *, opening: float, window: float
) -> HindsightOraclePolicy:
    """The arm under test, with one opening level for every SKU the trace names."""
    return HindsightOraclePolicy(
        trace=_trace(events),
        opening_stock=dict.fromkeys({sku for _, sku, _ in events}, opening),
        window_min=window,
    )


def _boundaries(window: int) -> list[float]:
    """Every decision time from zero until the whole trace is due, spaced by the arm's window."""
    return [float(minute) for minute in range(0, _HORIZON_MIN + window, window)]


def _observation(*, sim_time: float, inventory: dict[str, int]) -> Observation:
    """The snapshot ``uplift/harness.py::observe`` builds, with the fields the arm may see."""
    return Observation(
        inventory=inventory,
        sim_time=sim_time,
        delivery_count=0,
        spoilage_count=0,
        stockout_count=0,
        unit_costs={"sku_0": 1.0, "sku_1": 1.5, "sku_2": 2.0},
    )


# ---------------------------------------------------------------------------
# 1. The hindsight minimum is the pointwise minimum, exactly
# ---------------------------------------------------------------------------


@given(first=st.lists(_COSTS, min_size=1, max_size=6), second=st.lists(_COSTS, min_size=1))
def test_the_hindsight_minimum_is_no_greater_than_any_arm_at_every_replicate(
    first: list[float], second: list[float]
) -> None:
    """Exact, with no tolerance: ``min`` returns one of its arguments and rounds nothing."""
    paired = min(len(first), len(second))
    family = {"a": first[:paired], "b": second[:paired]}

    minimum = hindsight_min(family)

    assert len(minimum) == paired
    for index, value in enumerate(minimum):
        for name, costs in family.items():
            assert value <= costs[index], (
                f"replicate {index}: minimum {value!r} exceeds arm {name}'s {costs[index]!r}, so "
                "it is not a floor and the non-negativity theorem below rests on nothing"
            )


@given(first=st.lists(_COSTS, min_size=1, max_size=6), second=st.lists(_COSTS, min_size=1))
def test_the_hindsight_minimum_is_attained_by_some_arm_rather_than_merely_bounding_them(
    first: list[float], second: list[float]
) -> None:
    """The clause above alone would be satisfied by returning zeros, which is why this exists.

    A floor no arm achieved is not a hindsight cost: it would make ``regret_vs_hindsight_min`` a
    comparison against a policy nobody ran. Attainment is what keeps the reported number a cost
    some declared arm actually paid.
    """
    paired = min(len(first), len(second))
    family = {"a": first[:paired], "b": second[:paired]}

    minimum = hindsight_min(family)

    for index, value in enumerate(minimum):
        assert value in {costs[index] for costs in family.values()}


@given(costs=st.lists(st.tuples(_COSTS, _COSTS, _COSTS), min_size=1, max_size=6))
def test_the_hindsight_minimum_does_not_depend_on_the_order_the_arms_are_declared(
    costs: list[tuple[float, float, float]],
) -> None:
    """A comparator whose value depended on a dict's insertion order would be a defect.

    Falsifiable: an implementation that returned the first arm's costs, or that short-circuited
    on the first arm to beat some running value, would fail this.
    """
    forward = {
        "a": [row[0] for row in costs],
        "b": [row[1] for row in costs],
        "c": [row[2] for row in costs],
    }
    backward = {"c": forward["c"], "b": forward["b"], "a": forward["a"]}

    assert hindsight_min(forward) == hindsight_min(backward)


# ---------------------------------------------------------------------------
# 2. The theorem: a family CONTAINING the subject cannot produce a negative regret
# ---------------------------------------------------------------------------


@given(subject=st.lists(_COSTS, min_size=1, max_size=6), other=st.lists(_COSTS, min_size=1))
def test_regret_against_a_hindsight_minimum_containing_the_subject_is_never_negative(
    subject: list[float], other: list[float]
) -> None:
    """The claim R5.1's sign convention needs, asserted where it is a theorem: the rationals.

    **The domain is deliberate, and the precedent is measured.** Property 61's first draft
    asserted an algebraic identity over ``float`` and CI falsified it at 500 examples with
    subnormal inputs (finding 56). Here the pointwise ordering is exact -- ``min`` rounds nothing
    -- but the AGGREGATION need not be: ``statistics.fmean`` sums and divides, so
    ``fmean(subject) - fmean(minimum) >= 0`` is a fact about the reals. Converting the same
    values to ``Fraction`` makes the claim exact for every finite input without weakening it,
    because ``Fraction(float)`` is a lossless binary conversion. Stating the domain a claim holds
    over is a precondition correction; adding a tolerance would be the weakening R2.10 forbids.
    """
    paired = min(len(subject), len(other))
    subject_costs = subject[:paired]
    family = {"subject": subject_costs, "other": other[:paired]}

    minimum = hindsight_min(family)

    exact_subject = sum(Fraction(value) for value in subject_costs)
    exact_minimum = sum(Fraction(value) for value in minimum)
    # Equal denominators -- `paired` replicates each -- so ordering the sums orders the means.
    assert exact_subject >= exact_minimum, (
        "the subject is a member of its own family, so the pointwise minimum cannot cost more "
        "than the subject at any replicate and cannot cost more on average"
    )


def test_the_theorem_holds_at_the_measured_arm_costs_that_defeated_the_previous_oracle() -> None:
    """On run 34570166681's own means, the floor is non-negative where the old contrast was not.

    A regression pin on the RELATIONSHIP rather than on the world: those three numbers produced a
    negative ``regret`` against arm C, and against a family that includes the reference arm the
    same numbers cannot. That contrast is the whole argument for changing the comparator, so it is
    asserted rather than described.
    """
    family = {
        "noop": [11.835228527152536],
        "reference": [2.0849871282327],
        "foresight": [2.897339574184977],
    }

    minimum = hindsight_min(family)

    assert minimum == [2.0849871282327]
    assert Fraction(family["reference"][0]) - Fraction(minimum[0]) == 0
    # And the pre-repair contrast, for comparison: the old oracle cost MORE than the subject.
    assert Fraction(family["reference"][0]) - Fraction(family["foresight"][0]) < 0


# ---------------------------------------------------------------------------
# 3. The negative direction -- the guarantee belongs to the family, not to the arithmetic
# ---------------------------------------------------------------------------


def test_a_family_excluding_the_subject_can_produce_a_negative_regret() -> None:
    """Built directly, because this is the clause that stops clause 2 reading as a tautology.

    If non-negativity held for every family, ``hindsight_min`` would be guaranteeing something
    about subtraction rather than about membership -- and a reader would have no reason to check
    that the reference arm is in the family ``_measure`` declares. It is, and this is why that
    matters.
    """
    subject = [5.0]
    family_without_subject = {"other": [9.0]}

    minimum = hindsight_min(family_without_subject)

    assert Fraction(subject[0]) - Fraction(minimum[0]) < 0


@given(
    subject=st.floats(min_value=0.0, max_value=1e3, allow_nan=False, allow_infinity=False),
    gap=st.floats(min_value=1e-3, max_value=1e3, allow_nan=False, allow_infinity=False),
)
def test_a_subject_strictly_cheaper_than_every_declared_arm_inverts_the_sign(
    subject: float, gap: float
) -> None:
    """Generalised: the inversion is not one lucky pair, it is what exclusion always permits."""
    minimum = hindsight_min({"other": [subject + gap], "another": [subject + gap + gap]})

    assert Fraction(subject) - Fraction(minimum[0]) < 0


# ---------------------------------------------------------------------------
# 4. The refusal paths are REACHABLE, and each is built rather than waited for
# ---------------------------------------------------------------------------


def test_an_empty_family_is_refused_because_an_empty_family_guarantees_nothing() -> None:
    """Constructed, not generated: "no example triggered it" is not evidence a guard works."""
    with pytest.raises(ValueError, match="empty family"):
        hindsight_min({})


def test_ragged_replicate_counts_are_refused_rather_than_truncated() -> None:
    """Truncating to the shortest arm would silently change the replicate set being compared.

    The same reasoning ``RegretObjective.regret`` already applies to an unpaired difference: it is
    a different estimator with a different variance, so computing it quietly would misreport
    precision.
    """
    with pytest.raises(ValueError, match="equal replicate counts"):
        hindsight_min({"a": [1.0, 2.0], "b": [1.0]})


def test_a_family_whose_arms_ran_no_replicates_is_refused() -> None:
    """An empty result would be aggregated to nothing and read as a measurement of nothing."""
    with pytest.raises(ValueError, match="zero replicates"):
        hindsight_min({"a": [], "b": []})


# ---------------------------------------------------------------------------
# 5. The oracle covers every outstanding unit, and holds nothing beyond it
# ---------------------------------------------------------------------------


@given(events=_EVENTS, opening=_OPENING, window=_WINDOWS)
def test_cumulative_supply_covers_every_unit_generated_before_the_next_decision(
    events: list[tuple[int, str, int]], opening: int, window: int
) -> None:
    """The zero-stockout claim, reduced to the arithmetic it rests on (ADR-055 D2.5.4).

    Every unit consumed in ``[t, t + w)`` was generated before ``t + w`` -- ``_delivery`` runs
    after two strictly positive timeouts -- so an arm holding at least the outstanding generated
    demand at ``t`` cannot meet a fulfilment with an empty shelf before its next decision. This
    asserts the supply side of that inequality: after the decision at ``t``, cumulative supply is
    at least all demand generated before ``t + w``.

    Asserted over ``Fraction`` so it is exact for every input, and over the telescoping SUM of
    :meth:`orders_at` rather than the closed form, so a defect in the order schedule -- a wrong
    boundary comparison, a dropped SKU, a clamp on the wrong side -- fails here.
    """
    arm = _arm(events, opening=float(opening), window=float(window))
    skus = {sku for _, sku, _ in events}
    supplied = dict.fromkeys(skus, Fraction(opening))

    for boundary in _boundaries(window):
        orders = arm.orders_at(boundary)
        due = arm.generated_before(boundary + window)
        for sku in skus:
            supplied[sku] += Fraction(orders.get(sku, 0.0))
            required = Fraction(due.get(sku, 0.0))
            assert supplied[sku] >= required, (
                f"{sku}: cumulative supply {supplied[sku]} does not cover the {required} unit(s) "
                f"generated before {boundary + window}, so a fulfilment in this slice could find "
                "an empty shelf and the arm is not an oracle"
            )


@given(events=_EVENTS, opening=_OPENING, window=_WINDOWS)
def test_the_arm_holds_no_buffer_beyond_the_coverage_requirement(
    events: list[tuple[int, str, int]], opening: int, window: int
) -> None:
    """ZERO CHOSEN CONSTANTS, asserted rather than promised.

    A comparator is allowed no irreducible choice -- only a materiality margin is (ADR-055 D2.5).
    An additive safety buffer of any size would make the measured regret a fact about this arm's
    tuning rather than about the twin, so the absence of one is a property: at every decision the
    cumulative supply equals either the opening stock (which ``add_stock`` cannot reduce, so it is
    forced) or exactly the coverage requirement, and never a unit more.
    """
    arm = _arm(events, opening=float(opening), window=float(window))
    skus = {sku for _, sku, _ in events}

    for boundary in _boundaries(window):
        due = arm.generated_before(boundary + window)
        for sku in skus:
            target = Fraction(arm.supply_target(sku, generated=due))
            assert target in {Fraction(opening), Fraction(due.get(sku, 0.0))}, (
                f"{sku} at {boundary}: cumulative supply {target} is neither the opening stock "
                "nor the coverage requirement, so the arm carries a buffer nobody committed"
            )


def test_a_decision_spacing_wider_than_the_window_leaves_demand_uncovered() -> None:
    """The falsifier for the arm's cadence coupling, built as a witness.

    The coverage guarantee is a property of the relation between the window and the interval until
    the next decision -- not of the label ``oracle``. Driven on a cadence WIDER than its window,
    demand generated in the uncovered tail is not provisioned for and the arm stops being an
    oracle for exactly the reason arm C was not one: a window that does not span the interval it
    must serve. ``run_three_pass`` therefore passes the REALISED slice length rather than
    ``FORESIGHT_WINDOW_MIN``, and this asserts that the distinction is load-bearing rather than
    defensive.
    """
    arm = _arm([(0, "sku_0", 10), (70, "sku_0", 10)], opening=0.0, window=60.0)

    # On its own cadence the first decision covers everything due before minute 60 and the second
    # covers the rest, so the two together supply the whole trace.
    on_cadence = Fraction(arm.orders_at(0.0).get("sku_0", 0.0)) + Fraction(
        arm.orders_at(60.0).get("sku_0", 0.0)
    )
    assert on_cadence == 20

    # Decided every 120 minutes with the same 60-minute window, the decision at minute 0 supplies
    # only the first 10 units while the event at minute 70 falls in the same undecided slice.
    supplied_by_minute_120 = Fraction(arm.orders_at(0.0).get("sku_0", 0.0))
    due_by_minute_120 = Fraction(arm.generated_before(120.0).get("sku_0", 0.0))
    assert supplied_by_minute_120 == 10
    assert due_by_minute_120 == 20
    assert supplied_by_minute_120 < due_by_minute_120, (
        "if this ever passes, a window shorter than the decision interval no longer leaves a "
        "coverage hole and the reason run_three_pass passes the realised cadence has changed"
    )


def test_the_arm_orders_once_cumulative_demand_exceeds_the_opening_stock() -> None:
    """Non-emptiness: an arm that never ordered would satisfy both clauses above vacuously.

    "Holds no buffer" and "covers all outstanding demand" are both trivially true of a policy that
    does nothing while the opening stock is already enough. So the decisive case -- demand that
    outgrows the opening stock -- is asserted directly, and the quantities are checked rather than
    only their non-emptiness.
    """
    arm = _arm([(0, "sku_0", 4), (10, "sku_0", 4), (70, "sku_0", 5)], opening=6.0, window=60.0)

    # Minute 0: 8 units are due before minute 60 against an opening 6, so 2 are ordered.
    assert arm.orders_at(0.0) == {"sku_0": 2.0}
    # Minute 60: cumulative demand reaches 13, so the top-up is the further 5.
    assert arm.orders_at(60.0) == {"sku_0": 5.0}
    # And nothing is ordered once the trace is exhausted.
    assert arm.orders_at(120.0) == {}


@given(events=_EVENTS, level=st.integers(min_value=0, max_value=10**6))
def test_the_arm_reads_no_inventory_at_all(events: list[tuple[int, str, int]], level: int) -> None:
    """The mechanical form of the truncation-asymmetry claim in ADR-055 D2.5.4.

    ``Observation.inventory`` is declared ``Mapping[str, int]``, so ``observe`` truncates the
    twin's float levels; arm C is kept out of that loop because reading a level up to one unit low
    per SKU per decision moves the oracle's cost UP and the measured regret DOWN -- the
    self-serving direction (D2.5.1). This arm is immune because it never looks: identical
    decisions for an empty shelf and for a million units. Asserted here rather than inferred from
    reading ``decide``, because the immunity is what licenses driving arm D through the same seam
    as arms A and B, and a future edit that started reading inventory would silently re-acquire
    the bias.
    """
    arm = _arm(events, opening=100.0, window=60.0)
    skus = {sku for _, sku, _ in events}

    empty = arm.decide(_observation(sim_time=0.0, inventory=dict.fromkeys(skus, 0)))
    stuffed = arm.decide(_observation(sim_time=0.0, inventory=dict.fromkeys(skus, level)))

    assert empty == stuffed
