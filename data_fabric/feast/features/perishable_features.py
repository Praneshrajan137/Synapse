"""Perishable state features — consumed by Freshness Guardian + Sustainability.

Shelf life remaining, cold-chain temperature history, FSSAI compliance
flags, and markdown state per (sku, store) pair.
"""
from datetime import timedelta

from feast import FeatureView, Field, FileSource
from feast.types import Float64, Int64

from features.entities import sku, store

perishable_source = FileSource(
    path="data/perishable_state.parquet",
    timestamp_field="event_timestamp",
)

perishable_features = FeatureView(
    name="perishable_state",
    entities=[sku, store],
    ttl=timedelta(minutes=30),
    schema=[
        Field(name="shelf_life_remaining_hours", dtype=Float64),
        Field(name="temp_deviation_cumulative_hours", dtype=Float64),
        Field(name="cold_chain_breach_count_7d", dtype=Int64),
        Field(name="quality_score", dtype=Float64),
        Field(name="markdown_applied", dtype=Int64),
        Field(name="markdown_pct", dtype=Float64),
        Field(name="expiry_risk_score", dtype=Float64),
    ],
    source=perishable_source,
    online=True,
)
