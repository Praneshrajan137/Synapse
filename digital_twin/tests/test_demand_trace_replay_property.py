"""Feature: decision-quality-proof, Property 51: The demand path replays exactly.

Task 9.10. Subject: ``DemandTrace`` (R5.37).

**Why a recorded trace at all.** A perfect-foresight policy needs to know future demand, and
``DecisionPolicy.decide(obs)`` sees only present state -- so foresight cannot exist without
this. The refused alternative is re-deriving the demand path by replaying the generator, which
couples the comparator to the generator's internals and breaks the moment E2c changes the
arrival process. E2c changes the arrival process.

**The seam that must NOT be used, asserted here so it is not reached for later.**
``start(external_demand=True)`` + ``inject_orders(n)`` takes a bare count and *replaces* the
demand process, so a run using it is **not the unmodified twin**. It remains available, and the
last test below pins that an injected order still names a SKU and lands in the trace -- because
if it did not, the foresight comparator would be blind to exactly the externally-driven demand
a ``WorldSource`` exists to supply.

``@pytest.mark.slow`` -- drives the real SimPy twin. Selected by ``ci.yml::uplift-verify``'s
slow step (``-m "slow"``, ``HYPOTHESIS_PROFILE=heavy``, ``digital_twin/tests`` already in that
step's path list).

Budget inherited from the root ``conftest.py`` profile. **No ``max_examples`` literal here.**
"""

from __future__ import annotations

import logging

import pytest
import structlog
from hypothesis import given, settings
from hypothesis import strategies as st

from digital_twin.simulation.engine import SupplyChainSimulation

structlog.configure(wrapper_class=structlog.make_filtering_bound_logger(logging.ERROR))

pytestmark = pytest.mark.slow

_SEEDS = st.integers(min_value=0, max_value=2**31 - 1)
_HOURS = st.sampled_from([6.0, 10.0])


def _traced(seed: int, hours: float) -> SupplyChainSimulation:
    sim = SupplyChainSimulation(seed=seed)
    sim.start()
    sim.advance(hours)
    return sim


@settings(deadline=None)
@given(seed=_SEEDS, hours=_HOURS)
def test_the_same_seed_replays_the_same_demand_path(seed: int, hours: float) -> None:
    """Two independent runs at one seed produce identical traces, event for event.

    This is the foundation the two-pass foresight comparator stands on: pass one records the
    trace, pass two replays the *same seed* with a foresight policy. If the path were not
    reproducible, pass two would be optimising against demand that never arrives.
    """
    first = _traced(seed, hours)
    second = _traced(seed, hours)

    assert len(first.demand_trace) > 0, "a run must record the demand it generated"
    assert first.demand_trace.as_tuples() == second.demand_trace.as_tuples()


@settings(deadline=None)
@given(seed=_SEEDS, hours=_HOURS)
def test_the_trace_is_ordered_and_bounded_by_the_horizon(seed: int, hours: float) -> None:
    """Events are recorded in generation order and none falls outside the simulated window."""
    sim = _traced(seed, hours)
    times = [event.t_min for event in sim.demand_trace.events]

    assert times == sorted(times), "the trace must be in generation order"
    assert all(0.0 <= t <= sim.sim_time_min for t in times), (
        "an event outside the simulated window would let foresight read demand that never "
        "occurred within the horizon being scored"
    )


@settings(deadline=None)
@given(seed=_SEEDS, hours=_HOURS)
def test_the_trace_accounts_for_every_created_order(seed: int, hours: float) -> None:
    """One recorded event per created order, while the catalogue is non-empty.

    Recorded at GENERATION time, not at fulfilment: an order that is generated and never
    fulfilled is still demand. A trace built from fulfilments would silently omit precisely
    the stockouts the experiment is about, which is the failure mode that would make a null
    result unfalsifiable.
    """
    sim = _traced(seed, hours)

    assert len(sim.demand_trace) == sim.metrics.orders_created
    assert sim.demand_trace.total_units == pytest.approx(float(sim.metrics.orders_created))


@settings(deadline=None)
@given(seed=_SEEDS, hours=_HOURS)
def test_per_sku_totals_reconstruct_the_whole(seed: int, hours: float) -> None:
    """The per-SKU decomposition is complete and consistent.

    This is the series ``demand_prophet`` forecasts. Before task 9.2 it did not exist: demand
    never named a SKU, so there was no per-SKU path to forecast, price, or hold stock against.
    """
    sim = _traced(seed, hours)
    by_sku = sim.demand_trace.units_by_sku()

    assert set(by_sku) <= set(sim.inventory), "demand named a SKU outside the catalogue"
    assert sum(by_sku.values()) == pytest.approx(sim.demand_trace.total_units)


@settings(deadline=None)
@given(seed=_SEEDS)
def test_a_restart_discards_the_previous_scenario_trace(seed: int) -> None:
    """``start()`` resets the trace with the rest of the accumulators.

    A trace surviving a restart would attribute one scenario's demand to the next, and the
    foresight comparator would then optimise pass two against a concatenation of two worlds.
    """
    sim = SupplyChainSimulation(seed=seed)
    sim.start()
    sim.advance(6.0)
    assert len(sim.demand_trace) > 0

    sim.start()
    assert len(sim.demand_trace) == 0
    assert sim.metrics.inventory_minutes == 0.0


@settings(deadline=None)
@given(seed=_SEEDS, count=st.integers(min_value=1, max_value=25))
def test_injected_orders_are_recorded_as_demand_too(seed: int, count: int) -> None:
    """The ``WorldSource`` path records on the same terms as endogenous arrivals.

    ``inject_orders`` must NOT be used as the foresight seam -- it replaces the demand process,
    so a run using it is not the unmodified twin -- but when a pluggable source does drive the
    world, its demand still has to be visible to anything reading the trace.
    """
    sim = SupplyChainSimulation(seed=seed)
    sim.start(external_demand=True)
    sim.inject_orders(count)
    sim.advance(4.0)

    assert len(sim.demand_trace) == count
    assert sim.metrics.orders_created == count
    for event in sim.demand_trace.events:
        assert event.sku in sim.inventory
