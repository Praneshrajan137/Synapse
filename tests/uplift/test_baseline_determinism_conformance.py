"""Determinism + interface-conformance tests for the baseline policy suite.

Feature: decision-integrity-uplift-proof
Property 5: Seeded baseline decisions are deterministic.

    *For any* seed and input observation, a seeded baseline policy produces identical
    decisions across two consecutive runs (construct the policy twice with the same seed,
    or call ``decide`` twice; the returned ``PolicyAction`` values are identical).

**Validates: Requirements 1.9** (with unit coverage for 1.7)

The property test drives all four baselines (``Par_Level_Reorder``, ``Static_Pricing``,
``Greedy_Routing``, ``NoOpDisruption``) over a shared observation generator. The unit
tests assert that each policy satisfies the runtime-checkable ``DecisionPolicy`` interface
(R1.6/R1.7), exposes a ``name`` attribute plus a working ``decide``, and honors one
representative documented-behavior assertion per policy (R1.7).

Equality relies on ``PolicyAction`` being a frozen dataclass whose ``reorder_quantities``
(dict) and ``disruption_actions`` (frozenset) compare by value, so comparisons are
order-insensitive.

The example budget for property tests is pinned with ``@settings(max_examples=200)`` so
every environment/profile runs at least 100 iterations for this suite.
"""
from __future__ import annotations

import pytest

try:
    from hypothesis import given, settings, strategies as st
except ImportError:  # pragma: no cover - hypothesis is a test dependency
    pytest.skip("hypothesis not installed", allow_module_level=True)

from digital_twin.simulation.monte_carlo import ShockParams

from uplift.baselines import (
    Greedy_Routing,
    NoOpDisruption,
    Par_Level_Reorder,
    Static_Pricing,
)
from uplift.interfaces import (
    DecisionPolicy,
    Observation,
    PendingOrder,
    Store,
)


# ---------------------------------------------------------------------------
# Shared observation strategy — populates every field a baseline might read
# (inventory, unit_costs, pending_order + eligible_stores, active_shock) so a
# single Observation exercises all four policies simultaneously.
# ---------------------------------------------------------------------------
_sku = st.text(min_size=1, max_size=8)
_coord = st.floats(min_value=-1e6, max_value=1e6, allow_nan=False, allow_infinity=False)
_point = st.tuples(_coord, _coord)
_non_negative_cost = st.floats(
    min_value=0.0, max_value=1e6, allow_nan=False, allow_infinity=False
)
_multiplier = st.floats(
    min_value=0.0, max_value=1e6, allow_nan=False, allow_infinity=False
)

_inventory_st = st.dictionaries(
    keys=_sku,
    values=st.integers(min_value=0, max_value=25_000),
    min_size=1,
    max_size=6,
)

_unit_costs_st = st.dictionaries(
    keys=_sku,
    values=_non_negative_cost,
    min_size=1,
    max_size=6,
)

_order_st = st.one_of(
    st.none(),
    st.builds(
        PendingOrder,
        order_id=st.text(min_size=1, max_size=12),
        destination=_point,
    ),
)


@st.composite
def _stores_st(draw: st.DrawFn) -> tuple[Store, ...]:
    """An eligible store set (possibly empty) with unique, increasing store ids."""
    locations = draw(st.lists(_point, min_size=0, max_size=6))
    return tuple(Store(store_id=i, location=loc) for i, loc in enumerate(locations))


_shock_st = st.one_of(
    st.none(),
    st.builds(
        ShockParams,
        demand_multiplier=_multiplier,
        lead_time_multiplier=_multiplier,
        failure_rate_multiplier=_multiplier,
        spoilage_rate_multiplier=_multiplier,
    ),
)


@st.composite
def _observation_st(draw: st.DrawFn) -> Observation:
    """A fully-populated Observation exercising every baseline's inputs."""
    return Observation(
        inventory=draw(_inventory_st),
        sim_time=draw(st.floats(min_value=0.0, max_value=1e6, allow_nan=False, allow_infinity=False)),
        delivery_count=draw(st.integers(min_value=0, max_value=1_000_000)),
        spoilage_count=draw(st.integers(min_value=0, max_value=1_000_000)),
        stockout_count=draw(st.integers(min_value=0, max_value=1_000_000)),
        unit_costs=draw(_unit_costs_st),
        active_shock=draw(_shock_st),
        pending_order=draw(_order_st),
        eligible_stores=draw(_stores_st()),
    )


def _make_policies(seed: int) -> list[DecisionPolicy]:
    """Construct one instance of every baseline for the given seed.

    ``Greedy_Routing`` / ``NoOpDisruption`` take no seed but are deterministic; they are
    included so the whole suite is checked under one identical harness.
    """
    return [
        Par_Level_Reorder(s=5, S=20, seed=seed),
        Static_Pricing(markup=1.5, seed=seed),
        Greedy_Routing(),
        NoOpDisruption(),
    ]


# ---------------------------------------------------------------------------
# Property 5: identical seed + observation -> identical decisions (R1.9)
# ---------------------------------------------------------------------------
@settings(max_examples=200)
@given(seed=st.integers(min_value=0, max_value=2**31 - 1), obs=_observation_st())
def test_seeded_baselines_are_deterministic(seed: int, obs: Observation) -> None:
    """Two consecutive runs with the same seed + observation yield identical actions.

    Both freshly-constructing each policy twice with the same seed and calling ``decide``
    twice on the same instance must produce equal ``PolicyAction`` outputs (R1.9).

    **Validates: Requirements 1.9**
    """
    first_run = _make_policies(seed)
    second_run = _make_policies(seed)

    for policy_a, policy_b in zip(first_run, second_run):
        # Two independently-constructed policies with the same seed agree ...
        action_a = policy_a.decide(obs)
        action_b = policy_b.decide(obs)
        assert action_a == action_b, f"{policy_a.name}: cross-construction mismatch"

        # ... and calling decide twice on one instance is idempotent (no hidden state).
        assert policy_a.decide(obs) == action_a, f"{policy_a.name}: repeated-call mismatch"


# ---------------------------------------------------------------------------
# Unit tests — interface conformance (R1.6/R1.7)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "policy",
    _make_policies(seed=0),
    ids=lambda p: p.name,
)
def test_policy_satisfies_decision_policy_interface(policy: object) -> None:
    """Each baseline satisfies the runtime-checkable ``DecisionPolicy`` protocol (R1.6)."""
    assert isinstance(policy, DecisionPolicy)


@pytest.mark.parametrize(
    "policy",
    _make_policies(seed=0),
    ids=lambda p: p.name,
)
def test_policy_has_name_and_working_decide(policy: object) -> None:
    """Each baseline exposes a non-empty ``name`` and a callable ``decide`` (R1.7)."""
    assert isinstance(policy.name, str) and policy.name
    obs = Observation(
        inventory={"sku-a": 3},
        sim_time=0.0,
        delivery_count=0,
        spoilage_count=0,
        stockout_count=0,
        unit_costs={"sku-a": 10.0},
    )
    action = policy.decide(obs)
    # decide always returns a PolicyAction-shaped object with the expected levers.
    assert hasattr(action, "reorder_quantities")
    assert hasattr(action, "price")
    assert hasattr(action, "routing_assignment")
    assert hasattr(action, "disruption_actions")


# ---------------------------------------------------------------------------
# Unit tests — documented behavior, one representative assertion per policy (R1.7)
# ---------------------------------------------------------------------------
def test_par_level_reorder_documented_behavior() -> None:
    """Reorders ``S - level`` at/below ``s`` and ``0`` strictly above ``s`` (R1.2/R1.10)."""
    policy = Par_Level_Reorder(s=5, S=20, seed=0)
    obs = Observation(
        inventory={"low": 3, "high": 10},
        sim_time=0.0,
        delivery_count=0,
        spoilage_count=0,
        stockout_count=0,
        unit_costs={"low": 1.0, "high": 1.0},
    )
    action = policy.decide(obs)
    assert action.reorder_quantities["low"] == 17.0  # S - level = 20 - 3
    assert action.reorder_quantities["high"] == 0.0  # level 10 > s 5


def test_static_pricing_documented_behavior() -> None:
    """Prices a unit at ``unit_cost × markup`` (R1.3)."""
    policy = Static_Pricing(markup=1.5)
    assert policy.price_for(10.0) == 15.0
    # decide() prices the representative (mean) unit cost.
    obs = Observation(
        inventory={"sku-a": 1},
        sim_time=0.0,
        delivery_count=0,
        spoilage_count=0,
        stockout_count=0,
        unit_costs={"sku-a": 8.0, "sku-b": 12.0},
    )
    assert policy.decide(obs).price == pytest.approx(15.0)  # mean cost 10.0 × 1.5


def test_greedy_routing_documented_behavior() -> None:
    """Picks the nearest eligible store; empty eligible set is unroutable (R1.4/R1.11)."""
    policy = Greedy_Routing()
    order = PendingOrder(order_id="o1", destination=(0.0, 0.0))
    stores = (
        Store(store_id=1, location=(10.0, 0.0)),
        Store(store_id=2, location=(1.0, 0.0)),  # nearest
    )
    obs = Observation(
        inventory={},
        sim_time=0.0,
        delivery_count=0,
        spoilage_count=0,
        stockout_count=0,
        unit_costs={},
        pending_order=order,
        eligible_stores=stores,
    )
    assignment = policy.decide(obs).routing_assignment
    assert assignment is not None
    assert assignment.store_id == 2
    assert assignment.unroutable is False

    # Empty eligible set -> unroutable, no assignment.
    empty_obs = Observation(
        inventory={},
        sim_time=0.0,
        delivery_count=0,
        spoilage_count=0,
        stockout_count=0,
        unit_costs={},
        pending_order=order,
        eligible_stores=(),
    )
    unroutable = policy.decide(empty_obs).routing_assignment
    assert unroutable is not None
    assert unroutable.store_id is None
    assert unroutable.unroutable is True


def test_no_op_disruption_documented_behavior() -> None:
    """Returns an empty disruption action set for any event (R1.5)."""
    policy = NoOpDisruption()
    obs = Observation(
        inventory={"sku-a": 1},
        sim_time=0.0,
        delivery_count=0,
        spoilage_count=0,
        stockout_count=0,
        unit_costs={"sku-a": 1.0},
        active_shock=ShockParams(demand_multiplier=5.0),
    )
    assert policy.decide(obs).disruption_actions == frozenset()
