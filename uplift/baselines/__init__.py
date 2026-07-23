"""
SYNAPSE Decision-Integrity Uplift Proof — baseline policy suite.

Transparent, documented control policies representing "what a competent operator does
without SYNAPSE" (R1.1, R1.8). Each baseline is pure, deterministic, seed-stable control
code implementing the shared ``uplift.interfaces.DecisionPolicy`` protocol (R1.6), so the
harness loop drives every arm through one identical interface and any KPI delta is
attributable to the decision policy alone.

The suite comprises exactly four policies (R1.1):

* :class:`~uplift.baselines.par_level_reorder.Par_Level_Reorder` — the (s, S) reorder
  policy (R1.2, R1.10).
* :class:`~uplift.baselines.static_pricing.Static_Pricing` — the static / cost-plus
  pricing policy (R1.3, R1.12); also exported under the PascalCase alias
  :data:`~uplift.baselines.static_pricing.StaticPricing`.
* :class:`~uplift.baselines.greedy_routing.Greedy_Routing` — the greedy nearest-store
  routing policy (R1.4, R1.11).
* :class:`~uplift.baselines.no_op_disruption.NoOpDisruption` — the no-op
  disruption-response policy (R1.5).

Import the whole suite from this package, e.g.::

    from uplift.baselines import (
        Par_Level_Reorder,
        Static_Pricing,
        Greedy_Routing,
        NoOpDisruption,
    )

See :doc:`README <README>` for each policy's plain-language rule and its role as the
control representing operation *without* SYNAPSE (R1.8).
"""
from __future__ import annotations

from uplift.baselines.greedy_routing import Greedy_Routing
from uplift.baselines.no_op_disruption import NoOpDisruption
from uplift.baselines.par_level_reorder import Par_Level_Reorder
from uplift.baselines.static_pricing import Static_Pricing, StaticPricing

__all__ = [
    "Par_Level_Reorder",
    "Static_Pricing",
    "StaticPricing",
    "Greedy_Routing",
    "NoOpDisruption",
]
