"""Property-based tests for ``KpiExtractor`` KpiVector range invariants.

Feature: decision-integrity-uplift-proof
Property 7: Every recorded KPI_Vector satisfies its range invariants.

    *For any* completed scenario run — any twin ``SimulationMetrics`` plus any
    ``AppliedDecisions`` the extractor could see, including adversarial or degenerate
    inputs (negative or huge counts, ``nan``/``inf`` rates) — the derived
    ``KpiVector`` has ``fill_rate``/``spoilage_rate``/``stockout_rate`` in the closed
    interval ``[0.0, 1.0]``, ``avg_delivery_time_min >= 0`` and finite, and
    ``margin``/``co2_estimate`` finite.

Validates: Requirements 2.3
"""
from __future__ import annotations

import math
import types

from hypothesis import given, settings
from hypothesis import strategies as st

from uplift.kpi import AppliedDecisions, DeliveredOrder, KpiExtractor


# ---------------------------------------------------------------------------
# Strategies
#
# The extractor only ever reads four attributes off the metrics object
# (``orders_created``, ``orders_delivered``, ``spoilage_rate``,
# ``avg_delivery_time_min``). On the real ``SimulationMetrics`` two of those are
# *derived* properties that can never carry ``nan``/``inf`` — but Property 7 must
# hold for *any* value the extractor could plausibly read, so we feed a lightweight
# stub that exposes those attributes directly and can carry adversarial values.
# ---------------------------------------------------------------------------

# Counts: include negatives, zero, and huge magnitudes.
_counts = st.integers(min_value=-(10**18), max_value=10**18)

# Rates the extractor consumes directly: include in-range, out-of-range,
# negative, huge, and non-finite (nan/inf) values.
_adversarial_floats = st.floats(allow_nan=True, allow_infinity=True)

# Prices/costs for delivered orders: allow non-finite so margin summation is
# exercised on degenerate inputs too.
_price_or_cost = st.floats(allow_nan=True, allow_infinity=True)


def _metrics_strategy() -> st.SearchStrategy[types.SimpleNamespace]:
    """A stub exposing exactly the attributes ``KpiExtractor.extract`` reads."""
    return st.builds(
        types.SimpleNamespace,
        orders_created=_counts,
        orders_delivered=_counts,
        spoilage_rate=_adversarial_floats,
        avg_delivery_time_min=_adversarial_floats,
    )


_delivered_orders = st.lists(
    st.builds(DeliveredOrder, applied_price=_price_or_cost, unit_cost=_price_or_cost),
    max_size=8,
).map(tuple)


def _applied_strategy() -> st.SearchStrategy[AppliedDecisions]:
    return st.builds(
        AppliedDecisions,
        delivered_orders=_delivered_orders,
        unmet_demand_events=_counts,
        demand_events=st.none() | _counts,
        delivered_volume=st.none() | _adversarial_floats,
    )


# ---------------------------------------------------------------------------
# Property 7: derived KpiVector always satisfies its range invariants (R2.3)
# ---------------------------------------------------------------------------
@settings(max_examples=200)
@given(metrics=_metrics_strategy(), applied=_applied_strategy())
def test_kpi_vector_satisfies_range_invariants(
    metrics: types.SimpleNamespace, applied: AppliedDecisions
) -> None:
    """Every derived KpiVector honours the design's range invariants (Property 7)."""
    extractor = KpiExtractor()
    kpis = extractor.extract(metrics, applied)

    # Fractional KPIs must lie in the closed interval [0.0, 1.0].
    for fraction in (kpis.fill_rate, kpis.spoilage_rate, kpis.stockout_rate):
        assert math.isfinite(fraction)
        assert 0.0 <= fraction <= 1.0

    # Delivery time is a non-negative, finite number of minutes.
    assert math.isfinite(kpis.avg_delivery_time_min)
    assert kpis.avg_delivery_time_min >= 0.0

    # Margin and CO2 estimate are numeric and finite.
    assert math.isfinite(kpis.margin)
    assert math.isfinite(kpis.co2_estimate)
