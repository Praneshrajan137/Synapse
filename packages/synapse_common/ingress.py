"""Ingress adapter boundary — where demand orders enter SYNAPSE (Phase 2.1).

Production-intent (ADR-049) needs a real data path, but the demonstration tier
runs on synthetic traffic. This module is the *port* both tiers share: one
``IngressSource`` contract that yields canonical ``IngressOrder`` objects, with
the demo generator as one implementation and a typed, documented extension point
for a real source.

The honesty rule (I-7): an order's origin is a **first-class, explicit field**
(``source``) — never a hidden default, never inferred from a string prefix after
the fact. The synthetic source still stamps the ``SYNTHETIC_ORDER_PREFIX``
order_id so the deployed single-source-of-truth (``synapse_common.synthetic``)
keeps detecting it downstream and the two signals can never disagree
(``is_synthetic`` is true if *either* says so — a synthetic order can never
masquerade as real).

Adoption (follow-up): ``scripts/traffic/decision_loop.py`` constructs orders via
``SyntheticIngressSource``; ``api/routers/orders.py`` carries ``source`` through
the outbox. This PR lands the boundary + its synthetic implementation + the
Tier-P contract, verified consistent with the existing synthetic marker.
"""

from __future__ import annotations

import abc
import os
import random
import time
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, ConfigDict, Field

from synapse_common.synthetic import SYNTHETIC_ORDER_PREFIX, is_synthetic_order_id

logger = structlog.get_logger(__name__)


class IngressSourceKind(StrEnum):
    """Where an order came from — an explicit, audited fact, not an inference."""

    SYNTHETIC = "synthetic"  # Tier-D demo traffic generator
    REAL_API = "real_api"  # external systems POST /orders (push)
    REAL_QUEUE = "real_queue"  # an adapter polls a real broker/queue (pull)


class IngressOrder(BaseModel):
    """A canonical demand order at the ingress boundary, with explicit origin."""

    model_config = ConfigDict(frozen=True)

    order_id: str = Field(..., min_length=1)
    city: str = Field(..., min_length=1)
    store_id: str = Field(..., min_length=1, max_length=64)
    sku_id: str = Field(..., min_length=1, max_length=64)
    quantity: int = Field(..., gt=0, le=1000)
    source: IngressSourceKind

    @property
    def is_synthetic(self) -> bool:
        """Honest origin: synthetic if the source says so OR the order_id carries
        the deployed synthetic prefix. Either signal is sufficient — a synthetic
        order can never present as real (cf. ``synapse_common.synthetic``)."""
        return self.source is IngressSourceKind.SYNTHETIC or is_synthetic_order_id(self.order_id)

    def to_demand_payload(self) -> dict[str, Any]:
        """The ``synapse.orders.demand`` payload shape (``domain.order_request``)."""
        return {
            "order_id": self.order_id,
            "city": self.city,
            "store_id": self.store_id,
            "sku_id": self.sku_id,
            "quantity": self.quantity,
            "timestamp": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        }


class IngressSource(abc.ABC):
    """Port: a source of demand orders. Implementations pull a batch on demand."""

    kind: IngressSourceKind

    @abc.abstractmethod
    def fetch_batch(self, limit: int = 1) -> list[IngressOrder]:
        """Return up to ``limit`` orders; an empty list means none available now."""
        raise NotImplementedError


class SyntheticIngressSource(IngressSource):
    """Tier-D demo source. Emits labelled synthetic orders whose ``order_id``
    carries ``SYNTHETIC_ORDER_PREFIX`` so downstream detection stays consistent.
    Deterministic when constructed with a ``seed`` (for tests/replay)."""

    kind = IngressSourceKind.SYNTHETIC

    def __init__(
        self,
        city: str = "bengaluru",
        *,
        stores: list[str] | None = None,
        skus: list[str] | None = None,
        seed: int | None = None,
    ) -> None:
        self._city = city
        # Defaults mirror the generated city data (25 stores, 500 SKUs).
        self._stores = stores or [f"STORE-{i:03d}" for i in range(1, 26)]
        self._skus = skus or [f"SKU-{i:04d}" for i in range(1, 501)]
        self._rng = random.Random(seed)
        self._seq = 0

    def fetch_batch(self, limit: int = 1) -> list[IngressOrder]:
        orders: list[IngressOrder] = []
        for _ in range(max(0, limit)):
            self._seq += 1
            order_id = f"{SYNTHETIC_ORDER_PREFIX}{int(time.time())}-{self._seq}"
            orders.append(
                IngressOrder(
                    order_id=order_id,
                    city=self._city,
                    store_id=self._rng.choice(self._stores),
                    sku_id=self._rng.choice(self._skus),
                    quantity=self._rng.randint(1, 20),
                    source=IngressSourceKind.SYNTHETIC,
                )
            )
        return orders


class RealIngressSource(IngressSource):
    """Tier-P extension point. Subclass and implement ``fetch_batch`` to pull from
    a real order source (a Kafka topic, a webhook queue, a partner API …). It MUST
    stamp ``source=REAL_*`` and a real ``order_id`` WITHOUT the synthetic prefix.

    Left abstract on purpose: there is no real source at $0 (ADR-049 — Tier P is
    activated only by explicit spend). Calling it surfaces the gap honestly rather
    than silently degrading to synthetic.
    """

    kind = IngressSourceKind.REAL_QUEUE

    def fetch_batch(self, limit: int = 1) -> list[IngressOrder]:
        raise NotImplementedError(
            "RealIngressSource is the Tier-P contract: wire your real order source "
            "here (ADR-049 Tier P / ADR-050). Until then SYNAPSE runs on "
            "SyntheticIngressSource and every order is labelled synthetic."
        )


def make_ingress_source(
    kind: str | None = None,
    *,
    city: str = "bengaluru",
    seed: int | None = None,
) -> IngressSource:
    """Select the ingress source by EXPLICIT config (``SYNAPSE_INGRESS_SOURCE``),
    defaulting to synthetic for the demonstration tier.

    The default is *labelled* synthetic (never silent), so a $0 demo can never be
    mistaken for real traffic. Selecting a real source without a registered
    implementation raises (honest gap) instead of falling back to synthetic.
    """
    selected = (kind or os.environ.get("SYNAPSE_INGRESS_SOURCE") or "synthetic").lower()
    if selected == IngressSourceKind.SYNTHETIC.value:
        return SyntheticIngressSource(city=city, seed=seed)
    if selected in (IngressSourceKind.REAL_API.value, IngressSourceKind.REAL_QUEUE.value):
        raise NotImplementedError(
            f"ingress source '{selected}' is a Tier-P extension point — subclass "
            "RealIngressSource (ADR-049: Tier P is activated only by explicit spend)."
        )
    raise ValueError(f"unknown SYNAPSE_INGRESS_SOURCE={selected!r}")


__all__ = [
    "IngressOrder",
    "IngressSource",
    "IngressSourceKind",
    "RealIngressSource",
    "SyntheticIngressSource",
    "make_ingress_source",
]
