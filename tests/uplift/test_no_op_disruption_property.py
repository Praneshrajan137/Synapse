"""Property-based tests for the ``No_Op_Disruption`` baseline policy.

Feature: decision-integrity-uplift-proof
Property 4: No_Op_Disruption always returns an empty action set.

    *For any* disruption event (any :class:`Observation`, with or without an
    ``active_shock`` of arbitrary parameters), ``No_Op_Disruption`` returns a
    :class:`PolicyAction` whose ``disruption_actions`` is the empty ``frozenset``.

Validates: Requirements 1.5

The example budget is controlled by the active Hypothesis profile (see the root
``conftest.py``); every profile runs at least 100 iterations, satisfying the
property-based minimum for this suite.
"""
from __future__ import annotations

import pytest

try:
    from hypothesis import given, settings, strategies as st
except ImportError:  # pragma: no cover - hypothesis is a test dependency
    pytest.skip("hypothesis not installed", allow_module_level=True)

from digital_twin.simulation.monte_carlo import ShockParams

from uplift.baselines.no_op_disruption import NoOpDisruption
from uplift.interfaces import Observation


# ---------------------------------------------------------------------------
# Strategies — arbitrary disruption events: any Observation with a varied
# active_shock (arbitrary ShockParams multipliers) or None (unshocked).
# ---------------------------------------------------------------------------
# Finite, non-negative multipliers spanning benign (1.0) and severe shocks.
_multiplier = st.floats(
    min_value=0.0,
    max_value=1e6,
    allow_nan=False,
    allow_infinity=False,
)

# active_shock is either absent (None) or arbitrary ShockParams.
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

_inventory_st = st.dictionaries(
    keys=st.text(min_size=1, max_size=8),
    values=st.integers(min_value=0, max_value=25_000),
    max_size=6,
)


def _observation(
    inventory: dict[str, int],
    sim_time: float,
    delivery_count: int,
    spoilage_count: int,
    stockout_count: int,
    active_shock: ShockParams | None,
) -> Observation:
    """Build an arbitrary Observation representing a disruption event."""
    return Observation(
        inventory=inventory,
        sim_time=sim_time,
        delivery_count=delivery_count,
        spoilage_count=spoilage_count,
        stockout_count=stockout_count,
        unit_costs={sku: 1.0 for sku in inventory},
        active_shock=active_shock,
    )


# ---------------------------------------------------------------------------
# Property 4: any disruption event -> empty action set (R1.5)
# ---------------------------------------------------------------------------
@settings(max_examples=200)
@given(
    inventory=_inventory_st,
    sim_time=st.floats(min_value=0.0, max_value=1e6, allow_nan=False, allow_infinity=False),
    delivery_count=st.integers(min_value=0, max_value=1_000_000),
    spoilage_count=st.integers(min_value=0, max_value=1_000_000),
    stockout_count=st.integers(min_value=0, max_value=1_000_000),
    active_shock=_shock_st,
)
def test_no_op_disruption_returns_empty_action_set(
    inventory: dict[str, int],
    sim_time: float,
    delivery_count: int,
    spoilage_count: int,
    stockout_count: int,
    active_shock: ShockParams | None,
) -> None:
    """Property 4 — the disruption action set is always empty (R1.5).

    **Validates: Requirements 1.5**
    """
    policy = NoOpDisruption()
    obs = _observation(
        inventory,
        sim_time,
        delivery_count,
        spoilage_count,
        stockout_count,
        active_shock,
    )

    action = policy.decide(obs)

    # R1.5: no corrective action is ever taken, shocked or not.
    assert action.disruption_actions == frozenset()
    assert len(action.disruption_actions) == 0
