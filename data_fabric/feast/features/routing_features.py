"""Routing context features — consumed by Routing Navigator.

Traffic conditions, weather-adjusted ETA offsets, rider fatigue, and
Gini-fairness tracking signals for the pointer-network routing policy.
"""

from datetime import timedelta

from feast import FeatureView, Field, FileSource
from feast.types import Float64, Int64
from features.entities import rider, zone

routing_source = FileSource(
    path="data/routing_context.parquet",
    timestamp_field="event_timestamp",
)

zone_routing_features = FeatureView(
    name="zone_routing_context",
    entities=[zone],
    ttl=timedelta(minutes=15),
    schema=[
        Field(name="traffic_congestion_idx", dtype=Float64),
        Field(name="avg_travel_time_minutes", dtype=Float64),
        Field(name="active_orders", dtype=Int64),
        Field(name="weather_eta_multiplier", dtype=Float64),
        Field(name="monsoon_wind_kmh", dtype=Float64),
    ],
    source=routing_source,
    online=True,
)

rider_routing_features = FeatureView(
    name="rider_routing_context",
    entities=[rider],
    ttl=timedelta(minutes=5),
    schema=[
        Field(name="rider_fatigue_score", dtype=Float64),
        Field(name="consecutive_deliveries", dtype=Int64),
        Field(name="earnings_last_24h", dtype=Float64),
        Field(name="gini_cohort_idx", dtype=Float64),
        Field(name="shift_minutes_elapsed", dtype=Float64),
    ],
    source=routing_source,
    online=True,
)
