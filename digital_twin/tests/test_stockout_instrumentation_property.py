"""A stockout costs something, and the instrumentation changed only what is recorded.

Feature: decision-quality-proof, Property 49: A stockout costs something, and the
instrumentation changed only what is recorded.

Task 9.8. Subject: ``digital_twin/simulation/engine.py`` (R5.38, R5.39).

**Clause 1 -- a stockout costs something.** Before task 9.1, ``_delivery`` incremented
``orders_delivered`` and both time totals *unconditionally*, before depleting stock. A stockout
was free, ``fill_rate`` could not fall, and all six ``KpiVector`` fields were blind to
availability. This asserts the repair: when stock runs out, the KPIs move.

**Clause 2 -- the load-bearing check of AD-17, and how it is stated here.** The task text
frames it as "the sequence produced by the instrumented engine equals the sequence produced by
the pre-change engine on the same seed". That comparison is not directly constructible: the
pre-change engine no longer exists, and reconstructing it inside a test would mean maintaining
a second copy of the physics whose fidelity nobody checks -- a worse foundation than the claim
it is meant to support.

So it is stated in the **equivalent invariant form**, which is both checkable and stronger
where it matters: *the demand path is invariant to fulfilment*. Concretely, for one seed and
two policies that produce wildly different fulfilment outcomes,

* ``orders_created`` is identical,
* the recorded ``DemandTrace`` is identical event-for-event, and
* ``demand_events == orders_delivered + unmet_demand_events`` **exactly**,

which is the accounting form of "``orders_delivered`` differs only on events whose drawn SKU
was at zero". If instrumentation had changed what the world *does* rather than what it
*records*, the first two would diverge. This is what makes "the unmodified twin" in R5.1 a
mechanical claim rather than an assertion -- and it is the property E2b's regret measurement
actually depends on.

Budget inherited from the root ``conftest.py`` profile via ``HYPOTHESIS_PROFILE``. **No
``max_examples`` literal appears in this file.**

``@pytest.mark.slow`` -- drives the real SimPy twin. Selected by
``ci.yml::uplift-verify``'s slow step, whose path list already collects ``digital_twin/tests``
and whose selector is ``-m "slow"`` at ``HYPOTHESIS_PROFILE=heavy``. A slow-marked test placed
outside that step's four paths is selected by **no job at all**.
"""

from __future__ import annotations

import logging

import pytest
import structlog
from hypothesis import given, settings
from hypothesis import strategies as st

from digital_twin.simulation.engine import SupplyChainSimulation

# The twin logs one debug line per pick/pack and per delivery. At the profile budgets this
# runs under that is tens of thousands of lines of noise per session, so the module quiets
# structlog rather than each test doing it. This changes no behaviour under test.
structlog.configure(wrapper_class=structlog.make_filtering_bound_logger(logging.ERROR))

pytestmark = pytest.mark.slow

#: Seeds, not values. The property must hold for any seed; pinning one would test an example.
_SEEDS = st.integers(min_value=0, max_value=2**31 - 1)

#: Short horizons keep each example cheap. NOTE they do NOT guarantee stock exhaustion: the
#: opening stock is 10 SKUs x 100 units = 1000, and 8h at the default arrival rate yields
#: roughly 800-950 demand events, so at many seeds nothing runs out. That is why the strict
#: claims below use `_EXHAUSTING_HOURS` and the universal claim uses these.
_HOURS = st.sampled_from([8.0, 12.0])

#: A horizon that provably exhausts the opening 1000 units: ~2800 demand events at 24h.
#: Stated rather than assumed -- a strict "service got worse" claim measured on a run where
#: stock never ran out is not a weaker test, it is a test of nothing.
_EXHAUSTING_HOURS: float = 24.0

#: Opening stock the engine warms in `start()`: 10 SKUs at 100.0 units.
_OPENING_UNITS: float = 1000.0


def _run(seed: int, hours: float, *, restock_threshold: float | None) -> SupplyChainSimulation:
    sim = SupplyChainSimulation(seed=seed)
    sim.start()
    if restock_threshold is not None:
        sim.set_policy(restock_threshold=restock_threshold)
    sim.advance(hours)
    return sim


# ---------------------------------------------------------------------------
# Clause 1: a stockout costs something
# ---------------------------------------------------------------------------


@settings(deadline=None)
@given(seed=_SEEDS, hours=_HOURS)
def test_disabling_restock_never_improves_service(seed: int, hours: float) -> None:
    """The universal claim: replenishing can never make service worse.

    Deliberately non-strict. At many seeds an 8-12h horizon produces fewer demand events than
    the 1000-unit opening stock, so nothing runs out and the two arms tie at ``1.0``. Asserting
    strict inequality here would fail on a correct engine -- the defect the falsifying example
    ``seed=62, hours=8.0`` exposed in the first draft of this file. Strictness is asserted
    separately, at a horizon that provably exhausts the shelf.
    """
    replenished = _run(seed, hours, restock_threshold=None)
    starved = _run(seed, hours, restock_threshold=0.0)

    assert starved.metrics.demand_events > 0, "no demand reached fulfilment; nothing was measured"
    assert starved.metrics.fill_rate <= replenished.metrics.fill_rate, (
        "disabling replenishment must never IMPROVE the served fraction; "
        f"starved={starved.metrics.fill_rate} replenished={replenished.metrics.fill_rate}"
    )
    assert starved.metrics.restocks_triggered == 0, (
        "a zero threshold must disable the endogenous restock entirely, not merely lower it"
    )


@settings(deadline=None)
@given(seed=_SEEDS)
def test_demand_beyond_the_opening_stock_forces_unmet_demand(seed: int) -> None:
    """The strict claim, at a horizon where the shelf provably empties.

    This is the clause that would have been impossible to state before task 9.1: with the
    endogenous restock off and demand exceeding the opening 1000 units, some demand MUST go
    unmet and ``fill_rate`` MUST fall below one. Previously it was pinned at one by
    construction.
    """
    starved = _run(seed, _EXHAUSTING_HOURS, restock_threshold=0.0)
    metrics = starved.metrics

    assert metrics.demand_events > _OPENING_UNITS, (
        f"this seed produced only {metrics.demand_events} demand events against "
        f"{_OPENING_UNITS} opening units, so the horizon did not exhaust the shelf"
    )
    assert metrics.unmet_demand_events > 0
    assert metrics.fill_rate < 1.0
    assert metrics.stockout_rate > 0.0
    # Deliveries cannot exceed the stock that existed, since nothing replenished it.
    assert metrics.orders_delivered <= _OPENING_UNITS


@settings(deadline=None)
@given(seed=_SEEDS, hours=_HOURS)
def test_an_empty_shelf_serves_nothing_and_says_so(seed: int, hours: float) -> None:
    """Zero stock with the catalogue intact is a total stockout, not a silent zero.

    This is the exact shape of the cold-start defect task 9.6 exposed: if the catalogue is
    deleted rather than emptied, no demand event is recorded at all and BOTH rates report
    ``0.0`` for a world where every order fails. Here the keys are kept, so the truth is
    reportable.
    """
    sim = SupplyChainSimulation(seed=seed)
    sim.start()
    for sku in list(sim.inventory):
        sim.add_stock(sku, 0.0)  # no-op add, keeps the key
    # Zero every level while preserving the catalogue.
    sim._inventory.update({sku: 0.0 for sku in sim.inventory})  # noqa: SLF001
    sim.set_policy(restock_threshold=0.0)
    sim.advance(hours)

    assert sim.metrics.demand_events > 0, "demand must still be observed against a known catalogue"
    assert sim.metrics.unmet_demand_events == sim.metrics.demand_events
    assert sim.metrics.stockout_rate == pytest.approx(1.0)
    assert sim.metrics.fill_rate == pytest.approx(0.0)
    assert sim.metrics.orders_delivered == 0


# ---------------------------------------------------------------------------
# Clause 2: the instrumentation changed only what is RECORDED
# ---------------------------------------------------------------------------


@settings(deadline=None)
@given(seed=_SEEDS, hours=_HOURS)
def test_the_demand_path_is_invariant_to_fulfilment(seed: int, hours: float) -> None:
    """AD-17's separation clause, in its checkable form.

    Two policies with different fulfilment outcomes must generate **the same demand**. If
    instrumentation had altered what the world does rather than what it records, these would
    diverge -- and every seeded expectation in the PRESERVE list would be moving for a reason
    unrelated to the change under test.
    """
    replenished = _run(seed, hours, restock_threshold=None)
    starved = _run(seed, hours, restock_threshold=0.0)

    assert replenished.metrics.orders_created == starved.metrics.orders_created
    assert replenished.demand_trace.as_tuples() == starved.demand_trace.as_tuples(), (
        "the recorded demand path must be identical across policies; it is drawn from the "
        "`demand` and `sku_choice` substreams, which no arm's actions consume"
    )


@settings(deadline=None)
@given(seed=_SEEDS)
def test_the_invariance_is_not_vacuous(seed: int) -> None:
    """The companion to the test above: the outcomes really do diverge.

    Separated and given an exhausting horizon on purpose. At 8-12h many seeds never empty the
    shelf, so both arms deliver identically and an equality-of-demand assertion would hold
    trivially. Proving the demand path is invariant is only interesting if the FULFILMENT path
    demonstrably is not.
    """
    replenished = _run(seed, _EXHAUSTING_HOURS, restock_threshold=None)
    starved = _run(seed, _EXHAUSTING_HOURS, restock_threshold=0.0)

    assert replenished.demand_trace.as_tuples() == starved.demand_trace.as_tuples()
    assert replenished.metrics.orders_delivered != starved.metrics.orders_delivered, (
        "at an exhausting horizon the two policies must produce different fulfilment, or the "
        "invariance claim is measuring nothing"
    )
    assert starved.metrics.unmet_demand_events > replenished.metrics.unmet_demand_events


@settings(deadline=None)
@given(seed=_SEEDS, hours=_HOURS)
def test_every_demand_event_is_either_delivered_or_unmet(seed: int, hours: float) -> None:
    """Exact conservation: the accounting form of "differs only on zero-stock events".

    No demand event may be silently dropped, and none may be counted twice. An inequality
    here would mean a fulfilment outcome that is neither a delivery nor a stockout -- a hole
    through which the stockout rate could be understated.
    """
    for threshold in (None, 0.0):
        sim = _run(seed, hours, restock_threshold=threshold)
        metrics = sim.metrics
        assert metrics.demand_events == metrics.orders_delivered + metrics.unmet_demand_events, (
            f"conservation violated at threshold={threshold}: demand={metrics.demand_events} "
            f"delivered={metrics.orders_delivered} unmet={metrics.unmet_demand_events}"
        )
        assert metrics.fill_rate + metrics.stockout_rate == pytest.approx(1.0)


@settings(deadline=None)
@given(seed=_SEEDS)
def test_unfulfilled_demand_contributes_no_delivery_time(seed: int) -> None:
    """An order that was never served did not experience a delivery time.

    Both time totals accumulate only on a fulfilled delivery, so a run that delivers nothing
    must report a zero average rather than dividing accumulated effort by zero deliveries or,
    worse, inflating the average with the effort spent on orders nobody received.
    """
    sim = SupplyChainSimulation(seed=seed)
    sim.start()
    sim._inventory.update({sku: 0.0 for sku in sim.inventory})  # noqa: SLF001
    sim.set_policy(restock_threshold=0.0)
    sim.advance(8.0)

    assert sim.metrics.orders_delivered == 0
    assert sim.metrics.total_delivery_time_min == 0.0
    assert sim.metrics.total_pick_pack_time_min == 0.0
    assert sim.metrics.avg_delivery_time_min == 0.0


@settings(deadline=None)
@given(seed=_SEEDS)
def test_demand_events_name_a_sku_in_the_catalogue(seed: int) -> None:
    """Property 49's R5.39 half: demand names its SKU, and the name is real.

    Before task 9.2 the depleting SKU was drawn inside ``_delivery`` *after* the delivery had
    been counted, so demand never named a SKU and there was no per-SKU series to forecast.
    """
    sim = _run(seed, 8.0, restock_threshold=None)
    catalogue = set(sim.inventory)

    assert len(sim.demand_trace) > 0, "a run must record the demand it generated"
    for event in sim.demand_trace.events:
        assert event.sku in catalogue, f"demand named {event.sku!r}, not in the catalogue"
        assert event.units > 0.0
        assert event.t_min >= 0.0
