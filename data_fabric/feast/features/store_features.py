"""Store operational state features — consumed by Inventory Sentinel and Routing Nav."""
from datetime import timedelta

from feast import FeatureView, Field, FileSource
from feast.types import Float64, Int64
from features.entities import store

store_source = FileSource(
    path="data/store_state.parquet",
    timestamp_field="event_timestamp",
)

store_operational_features = FeatureView(
    name="store_operational_state",
    entities=[store],
    ttl=timedelta(minutes=5),
    schema=[
        Field(name="current_occupancy_pct", dtype=Float64),
        Field(name="fill_rate", dtype=Float64),
        Field(name="avg_pick_time_sec", dtype=Float64),
        Field(name="active_orders", dtype=Int64),
    ],
    source=store_source,
    online=True,
)
