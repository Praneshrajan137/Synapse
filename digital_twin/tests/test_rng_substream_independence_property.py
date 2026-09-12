"""Feature: decision-quality-proof, Property 52: Named RNG substreams are independent.

Task 9.11. Subject: ``SUBSTREAM_NAMES`` / ``_spawn_streams`` (R5.30, R5.37).

**This is what makes the two-pass comparator protocol sound**, and what makes E2c possible at
all. With one shared generator the realised demand path is a function of the *global draw order
across all five processes*, so adding a queue in structure 2 would perturb the demand stream and
every seeded expectation in the PRESERVE list would break for a reason unrelated to the
structure being added. With substreams, pass two's demand is provably identical to pass one's
despite a different policy consuming different draws elsewhere.

It also makes ``test_arms_receive_identical_seeded_demand`` a **stronger** statement rather than
a weaker one: the demand substream is provably independent of any arm's actions, rather than
merely observed to agree.

**The ordering hazard, pinned here.** ``SeedSequence.spawn`` derives each child from the
parent's entropy plus its *index*, so inserting a name into the middle of ``SUBSTREAM_NAMES``
silently re-seeds every substream after it. The order is therefore asserted, not just
documented -- a comment cannot fail.

``@pytest.mark.slow`` -- the behavioural clauses drive the real SimPy twin. Selected by
``ci.yml::uplift-verify``'s slow step.

Budget inherited from the root ``conftest.py`` profile. **No ``max_examples`` literal here.**
"""

from __future__ import annotations

import logging

import numpy as np
import pytest
import structlog
from hypothesis import given, settings
from hypothesis import strategies as st

from digital_twin.simulation.engine import SUBSTREAM_NAMES, SupplyChainSimulation

structlog.configure(wrapper_class=structlog.make_filtering_bound_logger(logging.ERROR))

pytestmark = pytest.mark.slow

_SEEDS = st.integers(min_value=0, max_value=2**31 - 1)

#: The committed order. Pinned because `spawn` derives children by INDEX: reordering silently
#: re-seeds every stream after the moved name, which would change every realised number on the
#: seeded path without changing a single line of physics.
_EXPECTED_ORDER = ("demand", "pick_pack", "travel", "restock", "spoilage", "sku_choice")


def test_the_substream_roster_and_order_are_pinned() -> None:
    """A rename or reorder must be a deliberate, visible change."""
    assert SUBSTREAM_NAMES == _EXPECTED_ORDER
    assert len(set(SUBSTREAM_NAMES)) == len(SUBSTREAM_NAMES), "duplicate substream name"


@given(seed=_SEEDS)
def test_every_named_stream_exists_and_is_a_distinct_generator(seed: int) -> None:
    """Six names, six distinct generator objects.

    Two names aliasing one generator would silently re-couple the processes this change exists
    to separate, and nothing else would notice.
    """
    sim = SupplyChainSimulation(seed=seed)
    streams = sim.streams

    assert set(streams) == set(SUBSTREAM_NAMES)
    assert len({id(generator) for generator in streams.values()}) == len(SUBSTREAM_NAMES)


@given(seed=_SEEDS)
def test_streams_are_reproducible_from_the_seed(seed: int) -> None:
    """One seed, one set of streams -- byte for byte, per stream."""
    first = SupplyChainSimulation(seed=seed).streams
    second = SupplyChainSimulation(seed=seed).streams

    for name in SUBSTREAM_NAMES:
        a = first[name].random(8)
        b = second[name].random(8)
        assert np.array_equal(a, b), f"stream {name!r} did not reproduce"


@given(seed=_SEEDS)
def test_distinct_streams_do_not_produce_the_same_values(seed: int) -> None:
    """Independence, in the form that actually matters here.

    Not a statistical independence claim -- that is ``SeedSequence``'s contract, not this
    project's to re-derive. What is asserted is the operational consequence: no two named
    streams hand out the same sequence, so consuming from one cannot advance another.
    """
    streams = SupplyChainSimulation(seed=seed).streams
    draws = {name: tuple(streams[name].random(16)) for name in SUBSTREAM_NAMES}

    assert len(set(draws.values())) == len(SUBSTREAM_NAMES), (
        "two substreams produced an identical sequence, so they are not independent"
    )


@given(seed=_SEEDS)
def test_an_unseeded_engine_still_gets_independent_streams(seed: int) -> None:
    """``seed=None`` draws OS entropy rather than falling back to one shared generator.

    The degenerate alternative -- returning a single generator under every name when no seed is
    given -- would leave unseeded runs silently coupled, and unseeded runs are the ones nobody
    inspects.
    """
    del seed  # the point of this case is the absence of a seed
    streams = SupplyChainSimulation(seed=None).streams

    assert set(streams) == set(SUBSTREAM_NAMES)
    draws = {name: tuple(streams[name].random(8)) for name in SUBSTREAM_NAMES}
    assert len(set(draws.values())) == len(SUBSTREAM_NAMES)


@settings(deadline=None)
@given(seed=_SEEDS)
def test_consuming_the_fulfilment_streams_does_not_move_the_demand_path(seed: int) -> None:
    """The behavioural clause, and the one the comparator depends on.

    Two runs at one seed under policies that consume the ``pick_pack``, ``travel`` and
    ``restock`` streams differently must still generate **identical demand**. Under a single
    shared generator this would be false by construction.
    """
    slow = SupplyChainSimulation(seed=seed)
    slow.start()
    slow.set_policy(dispatch_speed=0.5, restock_threshold=0.0)
    slow.advance(8.0)

    fast = SupplyChainSimulation(seed=seed)
    fast.start()
    fast.set_policy(dispatch_speed=2.0, restock_threshold=200.0)
    fast.advance(8.0)

    assert slow.demand_trace.as_tuples() == fast.demand_trace.as_tuples(), (
        "the demand path moved when only fulfilment policy changed; the substreams are coupled"
    )
    assert slow.metrics.orders_created == fast.metrics.orders_created
    # The policies really did diverge downstream, so the claim above is not vacuous.
    assert slow.metrics.restocks_triggered != fast.metrics.restocks_triggered
