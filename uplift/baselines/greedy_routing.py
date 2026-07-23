"""
``Greedy_Routing`` — a greedy nearest-store routing baseline policy (R1.1, R1.4, R1.11).

This is transparent control code representing "what a competent operator does without
SYNAPSE" for routing: assign each pending order to the eligible store whose location is
closest (Euclidean distance) to the order's destination, breaking ties deterministically
by the lowest store id. When no store is eligible, the order is reported as unroutable and
its routing state is left unchanged.

The policy implements the ``DecisionPolicy`` protocol: it exposes a ``name`` attribute and a
``decide(obs) -> PolicyAction`` method. It holds no hidden global state, so a given
``Observation`` always yields the same routing decision.
"""
from __future__ import annotations

import math

from uplift.interfaces import (
    Observation,
    PolicyAction,
    RoutingAssignment,
    Store,
)


def _euclidean_distance(a: tuple[float, float], b: tuple[float, float]) -> float:
    """Euclidean distance between two 2-D points."""
    return math.hypot(a[0] - b[0], a[1] - b[1])


class Greedy_Routing:
    """Assign each order to its nearest eligible store; tie → lowest store id (R1.4).

    An empty eligible set yields an unroutable assignment (``store_id is None``,
    ``unroutable=True``) with an explanatory error, leaving routing state unchanged (R1.11).
    """

    def __init__(self, name: str = "greedy_routing") -> None:
        self.name = name

    def decide(self, obs: Observation) -> PolicyAction:
        """Return a ``PolicyAction`` carrying the routing assignment for ``obs``.

        When there is no pending order this policy has nothing to route and returns a
        neutral (empty) ``PolicyAction``. When a pending order exists, it is assigned to the
        nearest eligible store (ties broken by lowest ``store_id``), or reported as
        unroutable if the eligible set is empty.
        """
        order = obs.pending_order
        if order is None:
            # Nothing to route this step; leave every lever at its neutral default.
            return PolicyAction()

        eligible = obs.eligible_stores
        if not eligible:
            # R1.11: no assignment, unroutable error, routing state unchanged.
            assignment = RoutingAssignment(
                order_id=order.order_id,
                store_id=None,
                unroutable=True,
                error=f"order {order.order_id} is unroutable: no eligible stores",
            )
            return PolicyAction(routing_assignment=assignment)

        # R1.4: nearest store by Euclidean distance to the destination; break ties by
        # lowest store id. Sorting on (distance, store_id) makes both criteria explicit and
        # deterministic.
        best: Store = min(
            eligible,
            key=lambda store: (
                _euclidean_distance(order.destination, store.location),
                store.store_id,
            ),
        )
        assignment = RoutingAssignment(
            order_id=order.order_id,
            store_id=best.store_id,
            unroutable=False,
            error=None,
        )
        return PolicyAction(routing_assignment=assignment)
