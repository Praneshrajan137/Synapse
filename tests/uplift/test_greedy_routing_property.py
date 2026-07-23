"""Property-based tests for the ``Greedy_Routing`` baseline policy.

Feature: decision-integrity-uplift-proof
Property 3: Greedy_Routing selects the nearest store with deterministic tie-breaking.

    *For any* order and non-empty set of eligible stores, ``Greedy_Routing`` assigns the
    order to a store of minimum distance to the destination and, among equidistant stores,
    the one with the lowest store identifier; and *for any* order with an empty eligible
    set it returns no assignment, an unroutable error, and leaves the order's routing state
    unchanged.

Validates: Requirements 1.4, 1.11

The example budget is controlled by the active Hypothesis profile (see the root
``conftest.py``). Every profile runs at least 100 iterations, satisfying the
property-based minimum for this suite.
"""
from __future__ import annotations

import math

import pytest

try:
    from hypothesis import given, settings, strategies as st
except ImportError:  # pragma: no cover - hypothesis is a test dependency
    pytest.skip("hypothesis not installed", allow_module_level=True)

from uplift.baselines.greedy_routing import Greedy_Routing
from uplift.interfaces import Observation, PendingOrder, Store


# ---------------------------------------------------------------------------
# Strategies — orders, eligible store sets (with unique store ids), and an
# equidistant-store generator that deliberately exercises the tie-break path.
# ---------------------------------------------------------------------------
# Coordinates are bounded finite floats so ``math.hypot`` stays exact-enough for
# tie detection and never overflows.
_coord = st.floats(min_value=-1e6, max_value=1e6, allow_nan=False, allow_infinity=False)
_point = st.tuples(_coord, _coord)

_order_st = st.builds(
    PendingOrder,
    order_id=st.text(min_size=1, max_size=12),
    destination=_point,
)


def _euclidean(a: tuple[float, float], b: tuple[float, float]) -> float:
    """Reference distance metric — identical to the policy's ``math.hypot``."""
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _expected_winner(order: PendingOrder, stores: list[Store]) -> Store:
    """Reference nearest-store selection: min distance, ties → lowest store_id.

    Computed with the same Euclidean metric the policy uses so the expected winner is
    unambiguous under float arithmetic.
    """
    return min(
        stores,
        key=lambda s: (_euclidean(order.destination, s.location), s.store_id),
    )


@st.composite
def _stores_with_unique_ids(draw: st.DrawFn) -> list[Store]:
    """A non-empty eligible store set whose ``store_id`` values are unique.

    With some probability, additional stores are placed at the *same* location as an
    existing store but with different (higher) ids, forcing genuine equidistant ties so
    the lowest-id tie-break is exercised.
    """
    locations = draw(st.lists(_point, min_size=1, max_size=6))
    # Base stores: one per drawn location, ids 0..n-1.
    stores = [Store(store_id=i, location=loc) for i, loc in enumerate(locations)]

    # Optionally clone some locations under fresh, higher ids to create ties.
    next_id = len(stores)
    n_clones = draw(st.integers(min_value=0, max_value=3))
    for _ in range(n_clones):
        src = draw(st.sampled_from(stores))
        stores.append(Store(store_id=next_id, location=src.location))
        next_id += 1

    # Store ids are unique by construction (0..len-1, then strictly increasing clones).
    return stores


def _observation(
    order: PendingOrder | None, stores: tuple[Store, ...]
) -> Observation:
    """Build a minimal Observation carrying only the routing fields the policy reads."""
    return Observation(
        inventory={},
        sim_time=0.0,
        delivery_count=0,
        spoilage_count=0,
        stockout_count=0,
        unit_costs={},
        pending_order=order,
        eligible_stores=stores,
    )


# ---------------------------------------------------------------------------
# Property 3 (non-empty branch): nearest store, ties → lowest store_id (R1.4)
# ---------------------------------------------------------------------------
@settings(max_examples=200)
@given(order=_order_st, stores=_stores_with_unique_ids())
def test_assigns_nearest_store_with_lowest_id_tie_break(
    order: PendingOrder, stores: list[Store]
) -> None:
    """The order is assigned to the min-distance store; ties broken by lowest id (R1.4).

    **Validates: Requirements 1.4**
    """
    # Strategy invariant: store ids are unique within the eligible set.
    ids = [s.store_id for s in stores]
    assert len(ids) == len(set(ids))

    policy = Greedy_Routing()
    action = policy.decide(_observation(order, tuple(stores)))

    assignment = action.routing_assignment
    assert assignment is not None
    assert assignment.order_id == order.order_id
    assert assignment.unroutable is False
    assert assignment.error is None

    expected = _expected_winner(order, stores)
    assert assignment.store_id == expected.store_id

    # The winner is genuinely a minimum-distance store, and no strictly-closer store
    # exists; among all minimum-distance stores it has the lowest id.
    winner_dist = _euclidean(order.destination, expected.location)
    for s in stores:
        d = _euclidean(order.destination, s.location)
        assert d >= winner_dist  # winner is a global minimum
        if math.isclose(d, winner_dist, rel_tol=0.0, abs_tol=0.0):
            # equidistant stores never have a lower id than the chosen winner
            assert s.store_id >= expected.store_id


# ---------------------------------------------------------------------------
# Property 3 (empty branch): unroutable, no assignment, state unchanged (R1.11)
# ---------------------------------------------------------------------------
@settings(max_examples=200)
@given(order=_order_st)
def test_empty_eligible_set_is_unroutable(order: PendingOrder) -> None:
    """An empty eligible set yields an unroutable error and no store assignment (R1.11).

    **Validates: Requirements 1.11**
    """
    policy = Greedy_Routing()
    action = policy.decide(_observation(order, ()))

    assignment = action.routing_assignment
    assert assignment is not None
    assert assignment.order_id == order.order_id
    # No store assignment ...
    assert assignment.store_id is None
    # ... an unroutable error indication identifying the order ...
    assert assignment.unroutable is True
    assert assignment.error is not None
    assert order.order_id in assignment.error
    # ... and no other lever is actuated (routing state otherwise unchanged).
    assert action.reorder_quantities == {}
    assert action.price is None
    assert action.disruption_actions == frozenset()
