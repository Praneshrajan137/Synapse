"""Property-based tests for the Par_Level_Reorder (s, S) baseline policy.

Property 1: Par_Level_Reorder honors the (s, S) rule.

    *For any* reorder points and level with ``0 <= s < S``, ``Par_Level_Reorder``
    emits a reorder quantity of ``S - projected_level`` when the inventory level is
    at or below ``s``, and a reorder quantity of exactly ``0`` when the level is
    strictly above ``s``.

**Validates: Requirements 1.2, 1.10**

The example budget is controlled by the active Hypothesis profile (see the root
``conftest.py``). Every profile runs at least 100 iterations, satisfying the
property-based minimum for this suite.
"""
from __future__ import annotations

import pytest

try:
    from hypothesis import given, settings, strategies as st
except ImportError:  # pragma: no cover - hypothesis is a test dependency
    pytest.skip("hypothesis not installed", allow_module_level=True)

from uplift.baselines.par_level_reorder import Par_Level_Reorder
from uplift.interfaces import Observation


def _observation(inventory: dict[str, int]) -> Observation:
    """Build a minimal Observation carrying only the inventory the policy reads."""
    return Observation(
        inventory=inventory,
        sim_time=0.0,
        delivery_count=0,
        spoilage_count=0,
        stockout_count=0,
        unit_costs={sku: 1.0 for sku in inventory},
    )


# ---------------------------------------------------------------------------
# Strategies: 0 <= s < S and per-SKU inventory levels
# ---------------------------------------------------------------------------
# s in [0, 10_000]; S = s + delta with delta >= 1 guarantees 0 <= s < S.
_s_st = st.integers(min_value=0, max_value=10_000)
_delta_st = st.integers(min_value=1, max_value=10_000)

# Inventory levels are non-negative integer stock counts; the upper bound comfortably
# spans both the "level <= s" and "level > s" branches for the s range above.
_inventory_st = st.dictionaries(
    keys=st.text(min_size=1, max_size=8),
    values=st.integers(min_value=0, max_value=25_000),
    min_size=1,
    max_size=6,
)


@settings(max_examples=200)
@given(s=_s_st, delta=_delta_st, inventory=_inventory_st)
def test_par_level_reorder_honors_s_S_rule(
    s: int, delta: int, inventory: dict[str, int]
) -> None:
    """Property 1 — every SKU's reorder qty follows the (s, S) rule.

    **Validates: Requirements 1.2, 1.10**
    """
    S = s + delta
    assert 0 <= s < S  # strategy invariant

    policy = Par_Level_Reorder(s, S, seed=0)
    action = policy.decide(_observation(inventory))

    # Every SKU in the observation must receive a reorder quantity.
    assert set(action.reorder_quantities) == set(inventory)

    for sku, level in inventory.items():
        qty = action.reorder_quantities[sku]
        if level <= s:
            # R1.2: at or below reorder point -> order up to target S.
            assert qty == float(S - level)
        else:
            # R1.10: strictly above reorder point -> order exactly zero.
            assert qty == 0.0
