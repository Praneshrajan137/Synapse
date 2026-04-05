"""Demand signal features — consumed by Demand Prophet and Pricing Oracle."""
from datetime import timedelta

from feast import FeatureView, Field, FileSource
from feast.types import Float64, Int64

from features.entities import sku, store

demand_source = FileSource(
    path="data/demand_signals.parquet",
    timestamp_field="event_timestamp",
)

demand_features = FeatureView(
    name="sku_demand_signals",
    entities=[sku, store],
    ttl=timedelta(hours=1),
    schema=[
        Field(name="rolling_mean_7d", dtype=Float64),
        Field(name="rolling_std_7d", dtype=Float64),
        Field(name="trend_slope", dtype=Float64),
        Field(name="seasonality_idx", dtype=Float64),
        Field(name="orders_last_1h", dtype=Int64),
        Field(name="orders_last_24h", dtype=Int64),
    ],
    source=demand_source,
    online=True,
)
