"""What a policy sees, and what it may do.

The legacy ``uplift.interfaces.Observation`` also carries ``active_shock``: the declared shock a
harness injected. The kernel's observation has no such field, on purpose: a policy here must detect
a disruption from what a store would observe (sales, stock, receipts, lead times), never be told
it (PLAN section 5.2, sealed in ``docs/truth/sealed/``).
"""

from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import Mapping


@dataclasses.dataclass(frozen=True)
class Observation:
    """One snapshot of the store, built by :func:`synapse_kernel.drive.observe`."""

    inventory: Mapping[str, int]
    sim_time: float
    delivery_count: int
    spoilage_count: int
    stockout_count: int
    unit_costs: Mapping[str, float]
    on_order: Mapping[str, float]
    supplier_lead_time_history: Mapping[str, tuple[float, ...]]
    demand_to_date: Mapping[str, int]
    sku_supplier: Mapping[str, str]
    start_weekday: int | None


@dataclasses.dataclass(frozen=True)
class PolicyAction:
    """Units to order per SKU; a SKU absent or at zero orders nothing."""

    reorder_quantities: Mapping[str, float]


class Policy(Protocol):
    """Anything that decides an action from an observation."""

    def decide(self, obs: Observation) -> PolicyAction:
        """The action for ``obs``."""
        ...
