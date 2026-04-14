"""
Mumbai Feast weather feature definitions.

E-S6-09: Mumbai MUST include monsoon_intensity feature (0-1 scale).
This feature does NOT exist in Bengaluru's weather views.
"""

from datetime import timedelta

from feast import FeatureView, Field, FileSource
from feast.types import Float64

from features.entities import store

mumbai_weather_source = FileSource(
    path="data/mumbai/weather_features.parquet",
    timestamp_field="event_timestamp",
)

mumbai_weather_features = FeatureView(
    name="mumbai_weather_context",
    entities=[store],
    ttl=timedelta(minutes=30),
    schema=[
        Field(name="temperature_c", dtype=Float64),
        Field(name="humidity_pct", dtype=Float64),
        Field(name="precip_prob", dtype=Float64),
        Field(name="wind_speed_kmh", dtype=Float64),
        Field(name="monsoon_intensity", dtype=Float64),
    ],
    source=mumbai_weather_source,
    online=True,
)
