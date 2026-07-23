"""
SYNAPSE Decision-Integrity Uplift Proof — KPI extraction (``KpiExtractor``).

Derives a single :class:`~uplift.interfaces.KpiVector` from the twin's
``SimulationMetrics`` plus the decisions an arm actually applied during a scenario
(R2.3). The extractor is *shared identically by both arms* — the consensus arm and
every baseline arm run their completed scenarios through this exact same derivation —
so derivation choices cannot bias attribution. Any KPI delta between arms is caused by
the decision policy, never by how the KPIs were computed.

Derivation (design "KpiVector derivation (KpiExtractor)"):

- ``fill_rate = orders_delivered / max(1, orders_created)``
- ``spoilage_rate`` = twin ``spoilage_rate``
- ``stockout_rate`` = unmet-demand fraction from a harness-side counter (incremented
  when a delivery draws a SKU already at zero inventory) over total demand
- ``avg_delivery_time_min`` = twin ``avg_delivery_time_min``
- ``margin`` = Σ over delivered orders of ``(applied_price − unit_cost)``
- ``co2_estimate`` = delivered volume × per-delivery emission factor

All three fractional KPIs (``fill_rate``, ``spoilage_rate``, ``stockout_rate``) are
clamped into the closed interval ``[0.0, 1.0]`` and ``avg_delivery_time_min`` is floored
at ``0.0`` so every produced ``KpiVector`` satisfies its range invariants (Property 7).
"""
from __future__ import annotations

import dataclasses
import math
from collections.abc import Iterable

from digital_twin.simulation.engine import SimulationMetrics
from uplift.interfaces import KpiVector

# ---------------------------------------------------------------------------
# CO2 estimator basis (same basis as tests/oracle/test_carbon_estimate_oracle.py,
# which anchors delivery CO2 to the twin's delivered-order volume). Diesel emits
# ~2.68 kg CO2 per liter (agents.sustainability_agent.models.carbon), and a single
# last-mile delivery is estimated to consume ~0.25 L, giving a per-delivery factor.
# ---------------------------------------------------------------------------
CO2_KG_PER_LITER_DIESEL: float = 2.68
LITERS_PER_DELIVERY: float = 0.25
DEFAULT_EMISSION_FACTOR_KG_PER_DELIVERY: float = CO2_KG_PER_LITER_DIESEL * LITERS_PER_DELIVERY


def _clamp_fraction(value: float) -> float:
    """Clamp a fraction into the closed interval ``[0.0, 1.0]`` (Property 7).

    Non-finite inputs (``nan``/``inf``) collapse to ``0.0`` so the invariant that
    every recorded fraction lies in ``[0, 1]`` can never be violated.
    """
    if not math.isfinite(value):
        return 0.0
    if value < 0.0:
        return 0.0
    if value > 1.0:
        return 1.0
    return value


@dataclasses.dataclass(frozen=True)
class DeliveredOrder:
    """One delivered order's pricing, used to derive margin (R2.3).

    ``applied_price`` is the price the arm's pricing decision set for the order;
    ``unit_cost`` is the twin's unit cost for the delivered SKU. The order's margin
    contribution is ``applied_price − unit_cost``.
    """

    applied_price: float
    unit_cost: float

    @property
    def margin(self) -> float:
        return self.applied_price - self.unit_cost


@dataclasses.dataclass(frozen=True)
class AppliedDecisions:
    """The arm-applied decision effects a scenario accumulates for KPI derivation.

    This is the second half of the ``KpiExtractor`` input (twin metrics being the
    first). It is populated identically for either arm by the harness loop:

    - ``delivered_orders`` — per delivered order pricing, summed into ``margin``.
    - ``unmet_demand_events`` — the harness-side stockout counter numerator,
      incremented whenever a delivery draws a SKU already at zero inventory.
    - ``demand_events`` — the denominator for ``stockout_rate``; when ``None`` the
      extractor falls back to the twin's ``orders_created`` (total demand).
    - ``delivered_volume`` — units delivered used for the CO2 estimate; when ``None``
      the extractor falls back to the twin's ``orders_delivered`` count.
    """

    delivered_orders: tuple[DeliveredOrder, ...] = ()
    unmet_demand_events: int = 0
    demand_events: int | None = None
    delivered_volume: float | None = None


class KpiExtractor:
    """Derives a :class:`KpiVector` from twin ``SimulationMetrics`` + applied decisions.

    A single ``KpiExtractor`` instance is shared by every arm in a harness run so the
    derivation is byte-for-byte identical across arms (the attribution guarantee).
    """

    def __init__(
        self,
        emission_factor_kg_per_delivery: float = DEFAULT_EMISSION_FACTOR_KG_PER_DELIVERY,
    ) -> None:
        if not math.isfinite(emission_factor_kg_per_delivery) or emission_factor_kg_per_delivery < 0.0:
            raise ValueError(
                "emission_factor_kg_per_delivery must be a non-negative finite number, "
                f"got {emission_factor_kg_per_delivery!r}"
            )
        self._emission_factor = emission_factor_kg_per_delivery

    @property
    def emission_factor_kg_per_delivery(self) -> float:
        return self._emission_factor

    def extract(
        self,
        metrics: SimulationMetrics,
        applied: AppliedDecisions | None = None,
    ) -> KpiVector:
        """Derive the full ``KpiVector`` for one completed scenario run (R2.3).

        ``metrics`` is the twin's accumulated ``SimulationMetrics`` and ``applied`` is
        the arm's accumulated decision effects. The result respects every range
        invariant in the design Data Models section (Property 7).
        """
        applied = applied if applied is not None else AppliedDecisions()

        orders_created = max(0, int(metrics.orders_created))
        orders_delivered = max(0, int(metrics.orders_delivered))

        # fill_rate = orders_delivered / max(1, orders_created), clamped to [0, 1].
        fill_rate = _clamp_fraction(orders_delivered / max(1, orders_created))

        # spoilage_rate is the twin's own bounded fraction; clamp defensively.
        spoilage_rate = _clamp_fraction(metrics.spoilage_rate)

        # stockout_rate = harness-side unmet-demand fraction over total demand.
        demand_events = (
            applied.demand_events if applied.demand_events is not None else orders_created
        )
        stockout_rate = _clamp_fraction(
            max(0, int(applied.unmet_demand_events)) / max(1, int(demand_events))
        )

        # avg_delivery_time_min from the twin, floored at 0 and finite.
        avg_delivery_time_min = float(metrics.avg_delivery_time_min)
        if not math.isfinite(avg_delivery_time_min) or avg_delivery_time_min < 0.0:
            avg_delivery_time_min = 0.0

        # margin = Σ over delivered orders of (applied_price − unit_cost).
        margin = self._sum_margin(applied.delivered_orders)

        # co2_estimate = delivered volume × per-delivery emission factor.
        delivered_volume = (
            applied.delivered_volume
            if applied.delivered_volume is not None
            else float(orders_delivered)
        )
        co2_estimate = float(delivered_volume) * self._emission_factor
        if not math.isfinite(co2_estimate):
            co2_estimate = 0.0

        return KpiVector(
            fill_rate=fill_rate,
            spoilage_rate=spoilage_rate,
            stockout_rate=stockout_rate,
            avg_delivery_time_min=avg_delivery_time_min,
            margin=margin,
            co2_estimate=co2_estimate,
        )

    @staticmethod
    def _sum_margin(delivered_orders: Iterable[DeliveredOrder]) -> float:
        """Σ over delivered orders of ``(applied_price − unit_cost)`` (R2.3).

        Guarantees a finite float for *any* input (Property 7). ``math.fsum`` raises
        ``ValueError`` when it encounters mixed infinities (e.g. ``-inf + inf``) and
        can produce a non-finite total for degenerate ``nan``/``inf`` prices/costs, so
        any non-finite outcome — whether raised or returned — collapses to ``0.0``,
        consistent with ``_clamp_fraction`` and the ``co2_estimate`` guard.
        """
        try:
            total = math.fsum(order.margin for order in delivered_orders)
        except (ValueError, OverflowError):
            return 0.0
        return total if math.isfinite(total) else 0.0
