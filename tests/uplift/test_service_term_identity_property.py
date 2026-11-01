"""`fill_rate` has two inequivalent definitions, and on one of them the objective double-counted.

Feature: decision-quality-proof, Property 64: The engine's `fill_rate` is the exact complement
of `stockout_rate`, the extractor's is not, and the committed objective prices that one quantity
exactly once.

Session 9, finding 60; session 11, finding 65. Subject:
`digital_twin/simulation/engine.py::SimulationMetrics` and `uplift/regret.py` (R5.33, R5.38;
ADR-055 D2.3, D2.5.3, D3).

**What this pins, and why prose was not enough.** Run `34590696403`'s decomposition reported
`stockout_rate` and `unmet_service` **bit-identical** for all three arms. The first record of that
called it measured-but-possibly-horizon-specific, on the reasoning that
`fill_rate = orders_delivered / max(1, orders_created)` (`uplift/kpi.py`) and
`stockout_rate = unmet_demand_events / demand_events` share no denominator, so they would collapse
only when `orders_created == demand_events`.

**That cited the wrong derivation.** `uplift/regret.py::_measure` reads
`SimulationMetrics.fill_rate`, the **engine property**, which is
`(demand_events - unmet_demand_events) / demand_events` and whose own docstring says "The exact
complement of :attr:`stockout_rate`". Over one shared denominator the identity is
**structural**, not conditional — so the objective's `unmet_service` term (`1 - fill_rate`, ADR-055
D2.5) and its `stockout_rate` term are **one quantity**, which the committed weights priced at 8.0
twice until finding 65 zeroed the `stockout_rate` weight (clause 2 pins the repair; section 4 pins
the rule that a zero weight must state why).

**A citation is not a mechanism.** Two definitions of one domain term exist in this tree and they
are not equivalent; which one a measurement gets depends on whether it reads the engine metric or
the KPI extractor. Clause 3 asserts the inequivalence, because without it clauses 1 and 2 would be
consistent with there being only one definition and no finding at all.

Budget inherited from the root `conftest.py` profile. **No `max_examples` literal appears in this
file** (CF-13).

Locus: `ci.yml::uplift-verify` fast step. **Not** slow-marked: `SimulationMetrics` is a dataclass
constructed directly from counters. No twin is started, nothing is simulated, no network.
"""

from __future__ import annotations

import functools
import math
from typing import TYPE_CHECKING

import pytest
import yaml
from hypothesis import assume, given
from hypothesis import strategies as st

from digital_twin.simulation.engine import SimulationMetrics
from digital_twin.simulation.policy import (
    POLICY_PATH,
    MarginRule,
    PolicyUnavailableError,
    load_policy,
    materiality_margin,
    materiality_margin_rule,
)
from uplift.regret import (
    OBJECTIVE_TERMS,
    ZEROED_PROVENANCE_PREFIX,
    RegretObjective,
    load_objective,
)

if TYPE_CHECKING:
    from pathlib import Path

_EVENTS = st.integers(min_value=0, max_value=100_000)


def _metrics(*, demand: int, unmet: int, created: int, delivered: int) -> SimulationMetrics:
    return SimulationMetrics(
        orders_created=created,
        orders_delivered=delivered,
        demand_events=demand,
        unmet_demand_events=unmet,
    )


@functools.cache
def _committed_objective() -> RegretObjective:
    """The objective exactly as `policy.yaml` commits it, read once per test session.

    Read, not transcribed: a fixture copy of the weights cannot see a revert of the committed
    file, and a revert of `stockout_rate` to 8.0 is the one change clause 2 exists to catch.
    """
    return load_objective()


@functools.cache
def _committed_rule() -> MarginRule:
    """The committed materiality-margin rule, whose weight term converts service points."""
    return materiality_margin_rule()


# ---------------------------------------------------------------------------
# 1. The engine's two service metrics are exact complements
# ---------------------------------------------------------------------------


@given(demand=_EVENTS, unmet=_EVENTS)
def test_the_engines_fill_rate_is_the_exact_complement_of_its_stockout_rate(
    demand: int, unmet: int
) -> None:
    """One shared denominator, so the identity is arithmetic rather than empirical."""
    assume(unmet <= demand)
    metrics = _metrics(demand=demand, unmet=unmet, created=demand, delivered=demand - unmet)

    if demand == 0:
        # Both guard the zero denominator to 0.0, so the complement does NOT hold there --
        # asserted rather than skipped, because a reader needs to know the one exception.
        assert metrics.fill_rate == 0.0
        assert metrics.stockout_rate == 0.0
        return

    assert math.isclose(
        metrics.fill_rate + metrics.stockout_rate, 1.0, rel_tol=1e-12, abs_tol=1e-12
    )


# ---------------------------------------------------------------------------
# 2. So the committed objective must price that one quantity exactly once
# ---------------------------------------------------------------------------


@given(demand=st.integers(min_value=1, max_value=100_000), unmet=_EVENTS)
def test_the_committed_objective_prices_the_shared_service_quantity_exactly_once(
    demand: int, unmet: int
) -> None:
    """`unmet_service` is `1 - fill_rate`, which the engine makes equal to `stockout_rate`.

    **PRECONDITION CORRECTION, SESSION 11 -- NOT AN ASSERTION WEAKENING (R2.10).** This clause
    asserted that the objective priced the shared quantity at 16.0, because both service terms
    carried 8.0 (finding 60). Finding 65 recorded the consequence -- a service point cost 0.16,
    so the 0.40 margin meant 2.5 points -- and the repair zeroed the `stockout_rate` weight. The
    subject changed; the standard did not, and it is STRICTER: the old clause read a transcribed
    fixture and could not see the committed file, while this one reads the committed objective
    and margin rule, so a revert of either weight fails here.

    **The expectation now:** the two terms together charge the one quantity exactly once, at an
    effective weight of 8.0 -- the `unmet_service` weight the margin rule converts with -- and
    `stockout_rate` is still one of the five terms, contributing exactly 0.0.
    """
    assume(unmet <= demand)
    metrics = _metrics(demand=demand, unmet=unmet, created=demand, delivered=demand - unmet)
    rule = _committed_rule()

    contributions = {
        item.term: item
        for item in _committed_objective().contributions(
            stockout_rate=metrics.stockout_rate,
            spoilage_rate=0.0,
            fill_rate=metrics.fill_rate,
            avg_on_hand_units=0.0,
            avg_delivery_time_min=0.0,
        )
    }
    stockout = contributions["stockout_rate"]
    unmet_service = contributions["unmet_service"]

    # The identity did not move -- only the pricing did.
    assert math.isclose(stockout.raw, unmet_service.raw, rel_tol=1e-12, abs_tol=1e-12)
    # The duplicate is kept, not deleted, so every per-term report still has five entries.
    assert set(contributions) == set(OBJECTIVE_TERMS)
    assert stockout.weight == 0.0
    assert stockout.weighted == 0.0
    # Together the two terms charge the quantity once, at the weight the margin converts with.
    assert rule.weight_term == "unmet_service"
    assert rule.weight == 8.0
    combined = stockout.weighted + unmet_service.weighted
    assert math.isclose(combined, rule.weight * metrics.stockout_rate, rel_tol=1e-9, abs_tol=1e-12)


def test_the_committed_margin_buys_the_service_points_its_rule_declares() -> None:
    """Finding 65's consequence, in the unit ADR-055 D2.5 states the margin in.

    The rule converts at `weight(unmet_service)` per unit of unmet service. That is honest only
    if the objective charges exactly that per unit, and on the measured path a unit of unmet
    service is charged by BOTH service terms. Under the double-count the committed 0.40 bought
    2.5 points, below D2.5's lower bracket (8/9 - 0.8556, about 3.3); now it buys the 5.0 the
    rule declares.
    """
    weights = _committed_objective().weights
    rule = _committed_rule()
    margin = materiality_margin()
    assert margin is not None, "checkpoint A instantiated the margin; a null here is a revert"

    charged_per_unit = weights["stockout_rate"] + weights["unmet_service"]
    effective_points = margin / (rule.points_to_fraction * charged_per_unit)

    assert math.isclose(effective_points, rule.service_points, rel_tol=1e-9)
    assert effective_points > (8.0 / 9.0 - 0.8556) * 100.0


# ---------------------------------------------------------------------------
# 3. Non-vacuity: the OTHER definition of fill_rate is not the complement
# ---------------------------------------------------------------------------


def test_the_two_definitions_of_fill_rate_are_not_equivalent() -> None:
    """Without this, clauses 1 and 2 are consistent with there being only one definition.

    `uplift/kpi.py` derives `fill_rate = orders_delivered / max(1, orders_created)`, which does
    **not** share a denominator with `stockout_rate = unmet_demand_events / demand_events`. So
    the same domain term means two different things depending on which module computed it, and a
    measurement inherits whichever its own read path used. **That is the finding**, and this
    clause proves the divergence by construction rather than waiting for a horizon to exhibit it.
    """
    # An order created near the horizon's end that never reached fulfilment: `orders_created`
    # exceeds `demand_events`, which is exactly the case task 9.1 kept the counters apart for.
    metrics = _metrics(demand=100, unmet=10, created=140, delivered=90)

    engine_fill = metrics.fill_rate
    extractor_fill = metrics.orders_delivered / max(1, metrics.orders_created)

    assert math.isclose(engine_fill, 0.90, rel_tol=1e-12)
    assert math.isclose(extractor_fill, 90 / 140, rel_tol=1e-12)
    assert not math.isclose(engine_fill, extractor_fill, rel_tol=1e-6), (
        "if these ever agree for this input, one definition changed and finding 60's premise "
        "must be re-derived rather than this assertion relaxed"
    )
    # And only the engine's is the complement, which is why the double-count is path-dependent.
    assert math.isclose(engine_fill + metrics.stockout_rate, 1.0, rel_tol=1e-12)
    assert not math.isclose(extractor_fill + metrics.stockout_rate, 1.0, rel_tol=1e-6)


# ---------------------------------------------------------------------------
# 4. A zero weight is admitted only when the policy states why (finding 65's guard)
# ---------------------------------------------------------------------------


def _policy_with_weight(
    tmp_path: Path, *, term: str, weight: float, provenance: str | None
) -> Path:
    """The committed policy with one weight and its provenance replaced; `None` deletes it."""
    document = load_policy(POLICY_PATH)
    block = document["regret_objective"]
    block["weights"] = {**block["weights"], term: weight}
    stated = {**block["weight_provenance"]}
    if provenance is None:
        stated.pop(term, None)
    else:
        stated[term] = provenance
    block["weight_provenance"] = stated
    target = tmp_path / "policy.yaml"
    target.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")
    return target


def test_the_committed_zero_is_admitted_because_its_provenance_states_why() -> None:
    """The admission path, exercised by the committed file itself rather than by a fixture.

    Non-empty by construction: the zero-weighted set is asserted to be exactly
    `stockout_rate`, so this cannot pass over a policy that commits no zero at all.
    """
    objective = _committed_objective()
    zeroed = {term for term in OBJECTIVE_TERMS if objective.weights[term] == 0.0}
    assert zeroed == {"stockout_rate"}

    stated = load_policy(POLICY_PATH)["regret_objective"]["weight_provenance"]["stockout_rate"]
    assert stated.startswith(ZEROED_PROVENANCE_PREFIX)
    assert "Property 64" in stated


@pytest.mark.parametrize(
    ("term", "provenance"),
    [
        ("stockout_rate", None),
        ("stockout_rate", "read: agents/inventory_sentinel/models/newsvendor.py::cost_under"),
        ("delivery_latency", "chosen: declaration-time choice, no committed antecedent"),
        ("stockout_rate", ZEROED_PROVENANCE_PREFIX),
        ("stockout_rate", f"  {ZEROED_PROVENANCE_PREFIX}   "),
    ],
)
def test_a_zero_weight_that_does_not_say_why_is_refused(
    tmp_path: Path, term: str, provenance: str | None
) -> None:
    """Absent, `read:`, another term's `chosen:`, and a bare prefix are all refused.

    A zero deletes its term's contribution exactly as an omitted term would, and an omitted term
    is refused, so each shape here must be refused too -- otherwise a term could be dropped from
    the objective by writing `0.0` instead of deleting the line.
    """
    target = _policy_with_weight(tmp_path, term=term, weight=0.0, provenance=provenance)
    with pytest.raises(PolicyUnavailableError, match=rf"regret_objective\.weights\.{term} = 0\.0"):
        load_objective(target)


@pytest.mark.parametrize("weight", [-8.0, math.nan, math.inf])
def test_a_negative_or_non_finite_weight_is_refused(tmp_path: Path, weight: float) -> None:
    """Every term is a COST (ADR-055 D2.1); a `zeroed:` provenance cannot admit a negative."""
    target = _policy_with_weight(
        tmp_path, term="unmet_service", weight=weight, provenance="zeroed: irrelevant here"
    )
    with pytest.raises(PolicyUnavailableError, match="Every objective term is a COST"):
        load_objective(target)


def test_a_positive_weight_is_admitted_whatever_its_provenance_says(tmp_path: Path) -> None:
    """Positive weights are unchanged by the zero rule: their provenance is not read at all."""
    target = _policy_with_weight(tmp_path, term="delivery_latency", weight=2.0, provenance=None)
    assert load_objective(target).weights["delivery_latency"] == 2.0
