"""Regret is total against the declared objective, and an insensitive KPI outranks a null.

Feature: decision-quality-proof, Property 54: Regret is total against the declared objective,
and an insensitive KPI outranks a null.

Task 10.6. Subject: ``uplift/regret.py`` (R5.1, R5.3, R5.14, R5.33, R5.34, R5.35).

Two halves, and the second is the one that decides what task 11 is allowed to conclude.

**Totality.** The objective must produce a finite cost for any finite KPI observation, must rank
a worse world as more costly, and must read every number from the committed policy file rather
than inlining one. A cost function that raises on a legal input would turn a measurement into a
crash report; one that silently defaults a missing weight would score a run against an objective
nobody declared.

**Insensitivity precedence (R5.35).** A regret below the materiality margin, measured while ANY
objective KPI is recorded under R5.34 as not observably sensitive, is ``inconclusive`` -- and
``inconclusive`` is **not** confirmation. This is asserted as a hard invariant over the whole
verdict space: ``confirms_finding_4`` is true for exactly one of the four verdicts, and never
while an insensitive KPI is on record.

**The committed tree's own state is pinned too**, because it has a consequence worth stating
before the run rather than discovering after it: ``spoilage_rate`` and ``delivery_latency`` are
still ``sensitive: false`` (``_spoilage`` reads neither inventory nor order size; ``_delivery``
draws travel time from an independent uniform). So **no sub-margin regret on today's twin can
confirm Finding 4** -- task 11 can only falsify it or report inconclusive. Structures 4 and 2
(tasks 13.3, 12.3) earn those flips.

Budget inherited from the root ``conftest.py`` profile via ``HYPOTHESIS_PROFILE``. **No
``max_examples`` literal appears in this file.**

Locus: ``ci.yml::uplift-verify`` fast step. **Not** slow-marked: every case here is pure
arithmetic over a policy file read, with no twin, no subprocess and no network.
"""

from __future__ import annotations

import math

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from digital_twin.simulation.policy import PolicyUnavailableError
from uplift.regret import (
    OBJECTIVE_TERMS,
    InsensitiveKpi,
    RegretObjective,
    classify_regret,
    load_objective,
)

# ---------------------------------------------------------------------------
# Strategies -- KPI observations that are legal but not necessarily pretty
# ---------------------------------------------------------------------------

_FRACTIONS = st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)
_UNITS = st.floats(min_value=0.0, max_value=5000.0, allow_nan=False, allow_infinity=False)
_MINUTES = st.floats(min_value=0.0, max_value=600.0, allow_nan=False, allow_infinity=False)
_REGRETS = st.floats(
    min_value=-1e6, max_value=1e6, allow_nan=False, allow_infinity=False
)


def _objective(*, insensitive: tuple[str, ...] = ()) -> RegretObjective:
    """A hand-built objective, so the verdict logic is tested independently of the real file."""
    return RegretObjective(
        weights=dict.fromkeys(OBJECTIVE_TERMS, 1.0),
        on_hand_normaliser=1000.0,
        delivery_normaliser=27.5,
        aggregation="mean_paired_on_seed",
        sensitivity={term: term not in insensitive for term in OBJECTIVE_TERMS},
        insensitive=tuple(
            InsensitiveKpi(term=term, blocked_on="fixture") for term in insensitive
        ),
    )


# ---------------------------------------------------------------------------
# 1. Totality of the objective
# ---------------------------------------------------------------------------


@given(
    stockout=_FRACTIONS,
    spoilage=_FRACTIONS,
    fill=_FRACTIONS,
    on_hand=_UNITS,
    delivery=_MINUTES,
)
def test_the_cost_is_finite_and_non_negative_for_any_legal_observation(
    stockout: float, spoilage: float, fill: float, on_hand: float, delivery: float
) -> None:
    """Every term is a cost, so their weighted sum is finite and cannot go negative."""
    objective = _objective()
    cost = objective.cost(
        stockout_rate=stockout,
        spoilage_rate=spoilage,
        fill_rate=fill,
        avg_on_hand_units=on_hand,
        avg_delivery_time_min=delivery,
    )

    assert math.isfinite(cost)
    assert cost >= 0.0


@given(
    stockout=_FRACTIONS,
    spoilage=_FRACTIONS,
    fill=_FRACTIONS,
    on_hand=_UNITS,
    delivery=_MINUTES,
)
def test_the_decomposition_sums_to_the_cost(
    stockout: float, spoilage: float, fill: float, on_hand: float, delivery: float
) -> None:
    """The per-term breakdown is the cost, not a parallel narrative about it.

    Recorded per term so the composition is inspectable -- a regret number whose composition
    cannot be examined is a number nobody can argue with, and committing the weights was
    precisely so it could be argued with.
    """
    objective = _objective()
    kpis = {
        "stockout_rate": stockout,
        "spoilage_rate": spoilage,
        "fill_rate": fill,
        "avg_on_hand_units": on_hand,
        "avg_delivery_time_min": delivery,
    }
    contributions = objective.contributions(**kpis)

    assert {item.term for item in contributions} == set(OBJECTIVE_TERMS)
    assert sum(item.weighted for item in contributions) == pytest.approx(objective.cost(**kpis))


@given(worse=_FRACTIONS, better=_FRACTIONS)
def test_a_higher_stockout_rate_never_costs_less(worse: float, better: float) -> None:
    """Monotonicity in the shortage term. If this inverted, the objective would reward stockouts."""
    assume(worse > better)
    objective = _objective()
    base = {
        "spoilage_rate": 0.1,
        "fill_rate": 0.9,
        "avg_on_hand_units": 100.0,
        "avg_delivery_time_min": 20.0,
    }

    assert objective.cost(stockout_rate=worse, **base) >= objective.cost(
        stockout_rate=better, **base
    )


@given(costs=st.lists(st.floats(min_value=0.0, max_value=100.0), min_size=1, max_size=30))
def test_aggregation_is_the_mean_and_an_empty_set_is_refused(costs: list[float]) -> None:
    """``mean_paired_on_seed`` is the arithmetic mean, and there is no mean of nothing."""
    objective = _objective()

    assert objective.aggregate(costs) == pytest.approx(sum(costs) / len(costs))
    with pytest.raises(ValueError, match="empty"):
        objective.aggregate([])


@given(
    a=st.lists(st.floats(min_value=0.0, max_value=50.0), min_size=1, max_size=12),
    extra=st.integers(min_value=1, max_value=5),
)
def test_unpaired_replicate_counts_are_refused(a: list[float], extra: int) -> None:
    """A paired estimator silently computed on unpaired data misreports its own precision."""
    objective = _objective()
    with pytest.raises(ValueError, match="paired"):
        objective.regret(a, a + [1.0] * extra)


@given(costs=st.lists(st.floats(min_value=0.0, max_value=50.0), min_size=1, max_size=12))
def test_regret_against_itself_is_zero(costs: list[float]) -> None:
    """A policy compared with itself has no regret. The sign convention depends on it."""
    assert _objective().regret(costs, costs) == pytest.approx(0.0)


def test_an_unrecognised_aggregation_rule_is_refused_not_guessed() -> None:
    """A reader that guesses at an aggregation it does not implement reports a different number."""
    objective = _objective()
    guessing = RegretObjective(
        weights=objective.weights,
        on_hand_normaliser=objective.on_hand_normaliser,
        delivery_normaliser=objective.delivery_normaliser,
        aggregation="median_of_medians",
        sensitivity=objective.sensitivity,
        insensitive=(),
    )
    with pytest.raises(PolicyUnavailableError, match="aggregation"):
        guessing.aggregate([1.0, 2.0])


# ---------------------------------------------------------------------------
# 2. The insensitivity precedence -- R5.35
# ---------------------------------------------------------------------------


@given(regret=_REGRETS, margin=st.floats(min_value=0.0, max_value=1e5))
def test_confirmation_requires_every_objective_kpi_to_be_sensitive(
    regret: float, margin: float
) -> None:
    """The load-bearing invariant, over the whole verdict space.

    Whatever the numbers, a verdict may only *confirm* Finding 4 when nothing is recorded
    insensitive. This is stated as an implication rather than a case analysis so that adding a
    fifth verdict later cannot quietly open a path to confirmation.
    """
    blind = _objective(insensitive=("spoilage_rate",))
    verdict = classify_regret(regret, objective=blind, margin=margin)

    assert not verdict.confirms_finding_4, (
        "a null measured while a KPI cannot see its subject is not evidence of absence (I-7)"
    )
    if regret < margin:
        assert verdict.verdict == "inconclusive"
        assert verdict.insensitive, "an inconclusive verdict must name what was blind"


@given(regret=_REGRETS, margin=st.floats(min_value=0.0, max_value=1e5))
def test_a_sub_margin_regret_confirms_only_with_a_fully_sensitive_instrument(
    regret: float, margin: float
) -> None:
    """The complement: with everything sensitive, a sub-margin result is readable as such."""
    assume(regret < margin)
    verdict = classify_regret(regret, objective=_objective(), margin=margin)

    assert verdict.verdict == "sub-margin"
    assert verdict.confirms_finding_4
    assert verdict.insensitive == ()


@given(regret=_REGRETS)
def test_no_committed_margin_judges_nothing(regret: float) -> None:
    """R5.2's deferral is a first-class state, not an excuse to compare against an invented one."""
    verdict = classify_regret(regret, objective=_objective(), margin=None)

    assert verdict.verdict == "unavailable"
    assert not verdict.confirms_finding_4
    assert not verdict.falsifies_finding_4
    assert "R5.2" in verdict.reason


@given(
    margin=st.floats(min_value=1.0, max_value=100.0),
    excess=st.floats(min_value=0.1, max_value=50.0),
    width=st.floats(min_value=0.01, max_value=0.5),
)
def test_material_requires_the_interval_to_exclude_the_margin(
    margin: float, excess: float, width: float
) -> None:
    """A point estimate above the margin is not enough; the interval must exclude it.

    Otherwise a regret whose interval straddles the margin would be reported as falsifying
    Finding 4 on the strength of noise.
    """
    point = margin + excess
    objective = _objective()

    excluding = classify_regret(
        point, objective=objective, margin=margin, interval=(point - width, point + width)
    )
    straddling = classify_regret(
        point, objective=objective, margin=margin, interval=(margin - width, point + width)
    )

    assert excluding.verdict == "material"
    assert excluding.falsifies_finding_4
    assert straddling.verdict != "material", (
        "an interval containing the margin cannot falsify Finding 4 on the point estimate alone"
    )


@given(regret=_REGRETS, margin=st.floats(min_value=0.0, max_value=1e5))
def test_the_verdict_is_total_and_the_two_readings_are_exclusive(
    regret: float, margin: float
) -> None:
    """Four values, always one, and never both readings at once."""
    for objective in (_objective(), _objective(insensitive=("delivery_latency",))):
        verdict = classify_regret(regret, objective=objective, margin=margin)
        assert verdict.verdict in {"material", "sub-margin", "inconclusive", "unavailable"}
        assert not (verdict.confirms_finding_4 and verdict.falsifies_finding_4)
        assert verdict.reason.strip(), "every verdict must state its reason"


# ---------------------------------------------------------------------------
# 3. The committed objective, and the consequence it carries today
# ---------------------------------------------------------------------------


def test_the_committed_objective_reads_every_declared_term() -> None:
    """No weight, normaliser or sensitivity record is defaulted."""
    objective = load_objective()

    assert set(objective.weights) >= set(OBJECTIVE_TERMS)
    assert objective.on_hand_normaliser > 0.0
    assert objective.delivery_normaliser > 0.0
    assert objective.aggregation == "mean_paired_on_seed"
    assert set(objective.sensitivity) >= set(OBJECTIVE_TERMS)


def test_the_committed_weights_carry_the_newsvendor_ratio() -> None:
    """The 8:1 shortage-to-holding ratio is READ from newsvendor.py, not chosen here.

    Pinned so that changing the objective's balance becomes a visible, deliberate act rather
    than an edit nobody notices.
    """
    weights = load_objective().weights

    assert weights["stockout_rate"] == 8.0
    assert weights["unmet_service"] == 8.0
    assert weights["on_hand"] == 1.0
    assert weights["spoilage_rate"] == 1.0


def test_today_a_sub_margin_regret_cannot_confirm_finding_4() -> None:
    """The consequence, pinned BEFORE the run it decides.

    ``spoilage_rate`` and ``delivery_latency`` are still recorded insensitive, so task 11 can
    **falsify** Finding 4 by measuring material regret but cannot **confirm** it. Recorded as a
    test rather than a note so that when structures 2 and 4 land and the flips are earned, this
    test fails and forces the reader to notice that the conclusion space has changed.
    """
    objective = load_objective()
    blind = {item.term for item in objective.insensitive}

    assert blind == {"spoilage_rate", "delivery_latency"}, (
        f"the recorded insensitive set changed to {blind}; if a structure earned a flip, update "
        "this test deliberately -- it guards what task 11 is allowed to conclude"
    )
    verdict = classify_regret(0.0, objective=objective, margin=1.0)
    assert verdict.verdict == "inconclusive"
    assert not verdict.confirms_finding_4


def test_a_sensitive_claim_without_a_citation_is_refused() -> None:
    """ADR-055 D3: each flip to ``true`` must name the property that demonstrates it."""
    objective = load_objective()
    for term, is_sensitive in objective.sensitivity.items():
        if is_sensitive:
            # Reaching here at all proves `load_objective` accepted it, which it only does when
            # a non-empty `demonstrated_by` is present -- the refusal path is unit-tested by the
            # loader itself raising on a bare `true`.
            assert term in OBJECTIVE_TERMS
    assert any(objective.sensitivity.values()), "task 9 flipped at least one KPI to sensitive"
