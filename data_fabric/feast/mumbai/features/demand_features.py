"""
Mumbai Feast demand feature definitions.

Schema is ALIGNED with Bengaluru's sku_demand_signals to support transfer learning.
Same columns, same types — only the FeatureView name uses 'mumbai_' prefix to prevent
registry collision (E-S6-03).

Uses Float64 to match Bengaluru's type convention.
"""

from datetime import timedelta

from feast import FeatureView, Field, FileSource
from feast.types import Float64, Int64

from features.entities import sku, store

mumbai_demand_source = FileSource(
    path="data/mumbai/demand_features.parquet",
    timestamp_field="event_timestamp",
)

mumbai_demand_features = FeatureView(
    name="mumbai_sku_demand_signals",
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
    source=mumbai_demand_source,
    online=True,
)
