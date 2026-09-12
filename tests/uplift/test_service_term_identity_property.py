"""`fill_rate` has two inequivalent definitions, and on one of them the objective
double-counts.

Feature: decision-quality-proof, Property 64: The engine's `fill_rate` is the exact complement
of `stockout_rate`, the extractor's is not, and the objective weights the complement twice.

Session 9, finding 60. Subject: `digital_twin/simulation/engine.py::SimulationMetrics` and
`uplift/regret.py` (R5.33, R5.38; ADR-055 D2.3, D2.5.3, D3).

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
D2.5) and its `stockout_rate` term are **one quantity carrying weight 8.0 twice**.

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

import math

from hypothesis import assume, given
from hypothesis import strategies as st

from digital_twin.simulation.engine import SimulationMetrics
from uplift.regret import OBJECTIVE_TERMS, InsensitiveKpi, RegretObjective

_EVENTS = st.integers(min_value=0, max_value=100_000)


def _metrics(*, demand: int, unmet: int, created: int, delivered: int) -> SimulationMetrics:
    return SimulationMetrics(
        orders_created=created,
        orders_delivered=delivered,
        demand_events=demand,
        unmet_demand_events=unmet,
    )


def _objective() -> RegretObjective:
    """The committed weights, so the double-count is asserted at its real magnitude."""
    return RegretObjective(
        weights={
            "stockout_rate": 8.0,
            "unmet_service": 8.0,
            "on_hand": 1.0,
            "spoilage_rate": 1.0,
            "delivery_latency": 1.0,
        },
        on_hand_normaliser=1000.0,
        delivery_normaliser=27.5,
        aggregation="mean_paired_on_seed",
        sensitivity=dict.fromkeys(OBJECTIVE_TERMS, True),
        insensitive=(InsensitiveKpi(term="spoilage_rate", blocked_on="fixture"),),
    )


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
# 2. So the objective prices one quantity at 16.0, not two at 8.0
# ---------------------------------------------------------------------------


@given(demand=st.integers(min_value=1, max_value=100_000), unmet=_EVENTS)
def test_the_objective_charges_the_same_quantity_under_two_names(demand: int, unmet: int) -> None:
    """`unmet_service` is `1 - fill_rate`, which the engine makes equal to `stockout_rate`.

    This is the clause that turns an identity into a **decision-relevance** defect: two of the
    five committed terms are the same number, each weighted 8.0, so the objective applies an
    effective weight of **16.0** to unmet demand while ADR-055 D2.3 records two independent
    terms. A weight nobody intended is not a committed choice.
    """
    assume(unmet <= demand)
    metrics = _metrics(demand=demand, unmet=unmet, created=demand, delivered=demand - unmet)

    contributions = {
        item.term: item
        for item in _objective().contributions(
            stockout_rate=metrics.stockout_rate,
            spoilage_rate=0.0,
            fill_rate=metrics.fill_rate,
            avg_on_hand_units=0.0,
            avg_delivery_time_min=0.0,
        )
    }

    stockout = contributions["stockout_rate"]
    unmet_service = contributions["unmet_service"]

    # The raw inputs are complements, so the two cost terms are equal...
    assert math.isclose(stockout.raw, unmet_service.raw, rel_tol=1e-12, abs_tol=1e-12)
    assert math.isclose(stockout.weighted, unmet_service.weighted, rel_tol=1e-12, abs_tol=1e-12)
    # ...and together they price one quantity at twice its declared weight.
    combined = stockout.weighted + unmet_service.weighted
    assert math.isclose(combined, 16.0 * metrics.stockout_rate, rel_tol=1e-9, abs_tol=1e-12)


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
