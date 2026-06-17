"""SYNAPSE WorldSource — the pluggable origin of demand for the standing world (ADR-052).

The whole point of the seam is that the downstream loop — SensorLoop → consensus →
actuation → outcome scoring — is **identical regardless of where demand comes from**.

  * ``SimWorldSource`` (now): deterministic Poisson demand the simulation drives. The
    operator chose "sim now"; this is a real, seeded, unit-testable generator.
  * ``ExternalFeedSource`` (later): would drain real orders off ``synapse.orders.demand``.
    It is an **honest stub** — it never pretends to be wired (I-7); ``poll_arrivals``
    returns ``[]`` and logs ``external_feed_not_wired`` until a real increment lands it.

Swapping the source must never require touching the sensor, consensus, or actuation.
"""

from __future__ import annotations

import math
import random
from typing import Protocol, runtime_checkable

import structlog

from synapse_common.world.models import WorldEvent, WorldEventKind

logger = structlog.get_logger(__name__)


@runtime_checkable
class WorldSource(Protocol):
    """Origin of demand-arrival events for one city's world."""

    name: str

    def poll_arrivals(self, now_sim_min: float, horizon_min: float) -> list[WorldEvent]:
        """Return the demand-arrival ``WorldEvent``s in ``[now, now+horizon)``."""
        ...


class SimWorldSource:
    """Deterministic Poisson demand generator over a fixed store/SKU catalog.

    Seeded so a given (seed, catalog, λ) replays the same arrival stream — this is the
    determinism the SensorLoop tests rely on. Stateful: successive ``poll_arrivals``
    calls advance the RNG and an arrival counter, so two polls over disjoint windows do
    not collide. ``ts`` is wall-clock (observability only); replay equality is over
    ``(kind, store_id, sku_id, sim_time_min, quantity)``.
    """

    def __init__(
        self,
        *,
        city: str,
        store_ids: list[str],
        sku_ids: list[str],
        arrival_rate_per_min: float = 2.0,
        seed: int = 0xC0FFEE,
    ) -> None:
        if arrival_rate_per_min <= 0.0:
            raise ValueError("arrival_rate_per_min must be > 0")
        if not store_ids or not sku_ids:
            raise ValueError("SimWorldSource needs a non-empty store/SKU catalog")
        self.name = f"sim:{city}"
        self._city = city
        self._stores = list(store_ids)
        self._skus = list(sku_ids)
        self._lambda = float(arrival_rate_per_min)
        self._rng = random.Random(seed)
        self._seq = 0

    def poll_arrivals(self, now_sim_min: float, horizon_min: float) -> list[WorldEvent]:
        """Draw Poisson(λ·horizon) arrivals, each at a uniform instant in the window."""
        if horizon_min <= 0.0:
            return []
        n = self._poisson(self._lambda * horizon_min)
        events: list[WorldEvent] = []
        for _ in range(n):
            self._seq += 1
            offset = self._rng.random() * horizon_min
            events.append(
                WorldEvent(
                    event_id=f"{self.name}-{self._seq:08d}",
                    kind=WorldEventKind.DEMAND_ARRIVAL,
                    city=self._city,
                    sim_time_min=round(now_sim_min + offset, 4),
                    store_id=self._rng.choice(self._stores),
                    sku_id=self._rng.choice(self._skus),
                    quantity=float(self._rng.randint(1, 5)),
                )
            )
        events.sort(key=lambda e: e.sim_time_min)
        return events

    def _poisson(self, lam: float) -> int:
        """Knuth's Poisson sampler on the source's own seeded RNG (deterministic)."""
        if lam <= 0.0:
            return 0
        target = math.exp(-lam)
        k = 0
        p = 1.0
        while True:
            k += 1
            p *= self._rng.random()
            if p <= target:
                return k - 1


class ExternalFeedSource:
    """Honest stub for a real demand feed (``synapse.orders.demand``) — NOT yet wired.

    Returning ``[]`` and logging is the I-7 honest-degradation contract: the seam exists
    and is typed, but it never fabricates arrivals it cannot actually read. A future
    increment implements ``poll_arrivals`` by draining the orders topic.
    """

    def __init__(self, *, city: str, topic: str = "synapse.orders.demand") -> None:
        self.name = f"feed:{city}"
        self._city = city
        self._topic = topic

    def poll_arrivals(self, now_sim_min: float, horizon_min: float) -> list[WorldEvent]:
        logger.warning(
            "external_feed_not_wired",
            city=self._city,
            topic=self._topic,
            note="ExternalFeedSource is an ADR-052 seam; demand stays endogenous to the sim",
        )
        return []
