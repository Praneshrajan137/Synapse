"""Property-based tests for the ``Static_Pricing`` baseline policy.

Feature: decision-integrity-uplift-proof
Property 2: Static_Pricing is cost-plus and never prices below cost.

    *For any* non-negative unit cost and markup factor ``>= 1.0``, ``Static_Pricing``
    returns a price equal to ``unit_cost × markup``, which is always greater than or
    equal to the unit cost; and *for any* negative unit cost it rejects the input with
    an error and produces no price.

Validates: Requirements 1.3, 1.12
"""
from __future__ import annotations

import math

import pytest
from hypothesis import given
from hypothesis import strategies as st

from uplift.baselines.static_pricing import NegativeUnitCostError, Static_Pricing


# ---------------------------------------------------------------------------
# Strategies — bounded to sensible finite ranges so ``unit_cost × markup`` never
# overflows to ``inf`` and float tolerance checks stay meaningful.
# ---------------------------------------------------------------------------
_non_negative_cost = st.floats(
    min_value=0.0,
    max_value=1e9,
    allow_nan=False,
    allow_infinity=False,
)
_markup = st.floats(
    min_value=1.0,
    max_value=1e6,
    allow_nan=False,
    allow_infinity=False,
)
_negative_cost = st.floats(
    min_value=-1e9,
    max_value=-1e-9,
    allow_nan=False,
    allow_infinity=False,
)


# ---------------------------------------------------------------------------
# Property 2 (positive branch): cost-plus and never below cost (R1.3)
# ---------------------------------------------------------------------------
@given(unit_cost=_non_negative_cost, markup=_markup)
def test_price_is_cost_plus_and_never_below_cost(unit_cost: float, markup: float) -> None:
    """price == unit_cost × markup, and that price is always >= unit_cost (R1.3)."""
    policy = Static_Pricing(markup=markup)
    price = policy.price_for(unit_cost)

    # price equals unit_cost × markup within float tolerance
    assert math.isclose(price, unit_cost * markup, rel_tol=1e-9, abs_tol=1e-12)
    # markup >= 1.0 guarantees the policy never prices below cost
    assert price >= unit_cost


# ---------------------------------------------------------------------------
# Property 2 (negative branch): reject negative cost, produce no price (R1.12)
# ---------------------------------------------------------------------------
@given(unit_cost=_negative_cost, markup=_markup)
def test_negative_unit_cost_is_rejected_without_price(unit_cost: float, markup: float) -> None:
    """A negative unit cost raises NegativeUnitCostError and yields no price (R1.12)."""
    policy = Static_Pricing(markup=markup)
    with pytest.raises(NegativeUnitCostError):
        policy.price_for(unit_cost)
