"""Event calendar features — consumed by Demand Prophet + Pricing Oracle.

Captures demand-impacting events (IPL matches, festivals, weather alerts,
municipal holidays). Indexed by city_id so transfer learning can key into
per-city event streams.
"""

from datetime import timedelta

from feast import FeatureView, Field, FileSource
from feast.types import Float64, Int64, String
from features.entities import city

event_source = FileSource(
    path="data/event_calendar.parquet",
    timestamp_field="event_timestamp",
)

event_features = FeatureView(
    name="event_calendar",
    entities=[city],
    ttl=timedelta(days=7),
    schema=[
        Field(name="event_type", dtype=String),
        Field(name="event_intensity", dtype=Float64),
        Field(name="hours_to_event", dtype=Float64),
        Field(name="ipl_match_active", dtype=Int64),
        Field(name="festival_active", dtype=Int64),
        Field(name="expected_uplift_pct", dtype=Float64),
    ],
    source=event_source,
    online=True,
)
