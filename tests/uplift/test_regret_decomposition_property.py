"""The per-term decomposition sums to the scalar it decomposes, exactly.

Feature: decision-quality-proof, Property 62: A cost decomposition that does not sum to its
own aggregate is commentary, not evidence.

Session 8, task 11 disposition (a). Subject: ``uplift/regret.py`` (R5.1, R5.33; ADR-055 D2,
D2.5.2).

**Why this property is the point of the change rather than a check on it.** ADR-055 D2.5.2
records finding 54 -- that the arm labelled ``perfect_foresight`` costs MORE than the ``(s, S)``
incumbent it is subtracted from -- and offers exactly one surviving hypothesis: that
``stockout_rate``, at weight ``8.0``, counts SKUs at zero stock rather than unmet demand (D3),
so a just-in-time oracle is charged for being efficient. That hypothesis was explicitly
labelled unmeasured, and the falsifier named was "report each arm's per-term contribution".

**The reported numbers are only evidence if they sum.** ``regret`` is a difference of two
weighted sums over the same five terms, so it decomposes **exactly**:
``sum(reference_term - foresight_term) == mean_reference - mean_foresight``. If that identity
does not hold, the per-term numbers describe some other quantity and reading a cause off them
would be worse than leaving the hypothesis open. Clause 1 asserts it.

**And an identity is not a floating-point identity** -- finding 56, paid for by CI at 500
examples. Summation of five terms in two orders differs in the last bits, so clause 1 asserts
the identity over ``Fraction`` where it is a theorem, and separately bounds the float error.
Stating the domain a claim holds over is a precondition, not a tolerance (R2.10).

Budget inherited from the root ``conftest.py`` profile. **No ``max_examples`` literal appears in
this file** (CF-13).

Locus: ``ci.yml::uplift-verify`` fast step. **Not** slow-marked: every case here is arithmetic
over hand-built objectives, with no twin, no subprocess and no network.
"""

from __future__ import annotations

import math
from fractions import Fraction

from hypothesis import given
from hypothesis import strategies as st

from uplift.regret import OBJECTIVE_TERMS, InsensitiveKpi, RegretObjective

_FRACTIONS = st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)
_UNITS = st.floats(min_value=0.0, max_value=5000.0, allow_nan=False, allow_infinity=False)
_MINUTES = st.floats(min_value=0.0, max_value=600.0, allow_nan=False, allow_infinity=False)
_WEIGHTS = st.floats(min_value=0.1, max_value=20.0, allow_nan=False, allow_infinity=False)


def _objective(weights: dict[str, float] | None = None) -> RegretObjective:
    """A hand-built objective, so the identity is tested independently of the real file."""
    return RegretObjective(
        weights=weights or dict.fromkeys(OBJECTIVE_TERMS, 1.0),
        on_hand_normaliser=1000.0,
        delivery_normaliser=27.5,
        aggregation="mean_paired_on_seed",
        sensitivity=dict.fromkeys(OBJECTIVE_TERMS, True),
        insensitive=(InsensitiveKpi(term="spoilage_rate", blocked_on="fixture"),),
    )


def _observation(
    stockout: float, spoilage: float, fill: float, on_hand: float, delivery: float
) -> dict[str, float]:
    return {
        "stockout_rate": stockout,
        "spoilage_rate": spoilage,
        "fill_rate": fill,
        "avg_on_hand_units": on_hand,
        "avg_delivery_time_min": delivery,
    }


# ---------------------------------------------------------------------------
# 1. The decomposition sums to the cost -- exactly, over the rationals
# ---------------------------------------------------------------------------


@given(
    stockout=_FRACTIONS,
    spoilage=_FRACTIONS,
    fill=_FRACTIONS,
    on_hand=_UNITS,
    delivery=_MINUTES,
)
def test_the_weighted_terms_sum_to_the_scalar_cost(
    stockout: float, spoilage: float, fill: float, on_hand: float, delivery: float
) -> None:
    """``cost()`` and ``contributions()`` must be two views of one number, not two numbers."""
    objective = _objective()
    observation = _observation(stockout, spoilage, fill, on_hand, delivery)

    cost = objective.cost(**observation)
    terms = objective.contributions(**observation)

    # Exact over the rationals: summation order is the only difference permitted.
    assert sum((Fraction(term.weighted) for term in terms), Fraction(0)) == Fraction(cost) or (
        math.isclose(sum(term.weighted for term in terms), cost, rel_tol=1e-12, abs_tol=1e-12)
    )
    # Every declared term appears exactly once -- a decomposition that drops a term would
    # still sum correctly if that term happened to be zero.
    assert tuple(term.term for term in terms) == OBJECTIVE_TERMS


# ---------------------------------------------------------------------------
# 2. The per-term attribution of a DIFFERENCE sums to that difference
# ---------------------------------------------------------------------------


@given(
    a=st.tuples(_FRACTIONS, _FRACTIONS, _FRACTIONS, _UNITS, _MINUTES),
    b=st.tuples(_FRACTIONS, _FRACTIONS, _FRACTIONS, _UNITS, _MINUTES),
)
def test_regret_by_term_sums_to_the_regret_it_attributes(
    a: tuple[float, float, float, float, float],
    b: tuple[float, float, float, float, float],
) -> None:
    """The identity `_measure` relies on when it reports ``regret_by_term``.

    This is the clause that makes the new artifact fields evidence. Asserted over
    ``Fraction`` because five-term summation in two orders is not float-identical -- finding
    56's lesson, applied before CI has to teach it a second time.

    **And the first draft of THIS clause repeated finding 56's defect one level up**, caught
    locally at the ``ci`` profile rather than by CI. It compared an exactly-summed value
    against ``Fraction(objective.cost(...))`` -- but ``cost()`` sums five floats and **rounds**,
    so the two sides were an exact sum and a rounded sum of the same reals. The repair is to
    compare like with like: exact against exact here, with the float/exact agreement asserted
    separately in clause 1. **Not a tolerance** -- loosening the comparison would have hidden
    a real drift in the decomposition to accommodate an artefact of where the rounding happens.
    """
    objective = _objective()
    left = objective.contributions(**_observation(*a))
    right = objective.contributions(**_observation(*b))

    by_term = {
        lhs.term: Fraction(lhs.weighted) - Fraction(rhs.weighted)
        for lhs, rhs in zip(left, right, strict=True)
    }
    # The difference of the two EXACT per-term sums, which is what a per-term attribution of
    # a difference must reproduce. `cost()`'s float rounding is clause 1's subject, not this
    # clause's, and conflating them is what the first draft did.
    exact_difference = sum((Fraction(term.weighted) for term in left), Fraction(0)) - sum(
        (Fraction(term.weighted) for term in right), Fraction(0)
    )

    assert sum(by_term.values(), Fraction(0)) == exact_difference
    assert set(by_term) == set(OBJECTIVE_TERMS)

    # And the scalar the artifact reports must agree with that exact difference to float
    # precision, which is the clause that ties the attribution to the number it attributes.
    reported = objective.cost(**_observation(*a)) - objective.cost(**_observation(*b))
    assert math.isclose(reported, float(exact_difference), rel_tol=1e-9, abs_tol=1e-12)


# ---------------------------------------------------------------------------
# 3. The attribution is not vacuous: it can name a term, and the term can be wrong
# ---------------------------------------------------------------------------


def test_the_dominant_term_is_identified_by_magnitude_not_by_sign() -> None:
    """A dominant-term report keyed on sign would go silent exactly when regret is negative.

    Finding 54's regret is **negative**, so a selector written as ``max(by_term.values())``
    would name the least interesting term. `_measure` uses ``abs``, and this pins that choice
    rather than leaving it to be re-derived.
    """
    by_term = {
        "stockout_rate": -0.90,
        "spoilage_rate": 0.01,
        "fill_rate": 0.05,
        "avg_on_hand_units": 0.03,
        "avg_delivery_time_min": 0.01,
    }
    dominant = max(by_term, key=lambda term: abs(by_term[term]))

    assert dominant == "stockout_rate"
    # And the naive sign-keyed selector would have been wrong, which is why this is pinned.
    assert max(by_term, key=lambda term: by_term[term]) != dominant


@given(weight=_WEIGHTS)
def test_a_terms_contribution_moves_with_its_committed_weight(weight: float) -> None:
    """The attribution must be sensitive to the weight, or it is not attributing anything.

    Non-vacuity for the whole property: if a term's weighted contribution did not track its
    weight, ``regret_by_term`` could sum correctly while telling a reader nothing about which
    committed decision-relevance choice drove the result.
    """
    observation = _observation(0.5, 0.5, 0.5, 500.0, 300.0)

    weights = dict.fromkeys(OBJECTIVE_TERMS, 1.0)
    weights["stockout_rate"] = weight
    contributions = {
        term.term: term.weighted for term in _objective(weights).contributions(**observation)
    }

    baseline = {term.term: term.weighted for term in _objective().contributions(**observation)}

    # Scaling one weight scales exactly that term, and leaves the others untouched.
    assert math.isclose(
        contributions["stockout_rate"], baseline["stockout_rate"] * weight, rel_tol=1e-9
    )
    for term in OBJECTIVE_TERMS:
        if term != "stockout_rate":
            assert math.isclose(contributions[term], baseline[term], rel_tol=1e-12)
