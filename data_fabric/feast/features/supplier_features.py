"""Supplier performance features — consumed by Supplier Trust + Inventory Sentinel.

Bayesian lead-time posteriors + fill-rate EWMA + defect rate. Feeds the
Supplier Trust GNN encoder and the Inventory Sentinel safety-stock
calculation.
"""
from datetime import timedelta

from feast import FeatureView, Field, FileSource
from feast.types import Float64, Int64

from features.entities import supplier

supplier_source = FileSource(
    path="data/supplier_performance.parquet",
    timestamp_field="event_timestamp",
)

supplier_features = FeatureView(
    name="supplier_performance",
    entities=[supplier],
    ttl=timedelta(hours=6),
    schema=[
        Field(name="lead_time_mean_days", dtype=Float64),
        Field(name="lead_time_std_days", dtype=Float64),
        Field(name="fill_rate_ewma_30d", dtype=Float64),
        Field(name="defect_rate_ewma_30d", dtype=Float64),
        Field(name="trust_score", dtype=Float64),
        Field(name="consecutive_late_deliveries", dtype=Int64),
        Field(name="on_time_ratio_90d", dtype=Float64),
    ],
    source=supplier_source,
    online=True,
)
