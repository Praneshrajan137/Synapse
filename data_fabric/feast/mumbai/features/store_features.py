"""Mumbai Feast store feature definitions."""

from datetime import timedelta

from feast import FeatureView, Field, FileSource
from feast.types import Float64, Int64, String

from features.entities import store

mumbai_store_source = FileSource(
    path="data/mumbai/store_features.parquet",
    timestamp_field="event_timestamp",
)

mumbai_store_features = FeatureView(
    name="mumbai_store_attributes",
    entities=[store],
    ttl=timedelta(days=1),
    schema=[
        Field(name="lat", dtype=Float64),
        Field(name="lon", dtype=Float64),
        Field(name="zone", dtype=String),
        Field(name="capacity_sqft", dtype=Int64),
        Field(name="cold_chain_enabled", dtype=Int64),
    ],
    source=mumbai_store_source,
    online=True,
)
