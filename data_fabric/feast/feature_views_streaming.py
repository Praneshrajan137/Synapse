"""Streaming feature views (ADR-030).

Declarative push-API views that the materializer feeds. Kept separate from
`features/*.py` so the offline batch surface is not perturbed.
"""

from __future__ import annotations

from datetime import timedelta

try:
    from feast import FeatureView, Field, PushSource  # type: ignore[import-untyped]
    from feast.types import Float64, Int64  # type: ignore[import-untyped]

    from features.entities import sku, store  # noqa: F401
except ImportError:  # pragma: no cover — feast optional in dev
    FeatureView = None  # type: ignore[assignment]


_streaming_demand_source = (
    PushSource(
        name="streaming_demand_push",
        batch_source=None,
    )
    if FeatureView is not None
    else None
)

sku_demand_signals_streaming = (
    FeatureView(
        name="sku_demand_signals_streaming",
        entities=[sku, store],
        ttl=timedelta(minutes=10),
        schema=[
            Field(name="orders_last_1m", dtype=Int64),
            Field(name="orders_last_5m", dtype=Int64),
            Field(name="qty_last_5m", dtype=Float64),
        ],
        source=_streaming_demand_source,
        online=True,
    )
    if FeatureView is not None
    else None
)


__all__ = ["sku_demand_signals_streaming"]
