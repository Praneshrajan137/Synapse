"""Price elasticity features — consumed by Pricing Oracle.

Double-ML causal elasticity estimates, cross-price elasticities, and
recent markdown history per (sku, category). Enforces essential-category
cap (I-6) upstream by exposing the `essential_flag` signal.
"""
from datetime import timedelta

from feast import FeatureView, Field, FileSource
from feast.types import Float64, Int64

from features.entities import category, sku

elasticity_source = FileSource(
    path="data/price_elasticity.parquet",
    timestamp_field="event_timestamp",
)

sku_elasticity_features = FeatureView(
    name="sku_price_elasticity",
    entities=[sku],
    ttl=timedelta(hours=6),
    schema=[
        Field(name="own_price_elasticity", dtype=Float64),
        Field(name="own_price_elasticity_ci_lower", dtype=Float64),
        Field(name="own_price_elasticity_ci_upper", dtype=Float64),
        Field(name="cross_price_elasticity_mean", dtype=Float64),
        Field(name="recent_markdown_pct", dtype=Float64),
        Field(name="essential_flag", dtype=Int64),  # I-6: 1.3x cap enforcement
    ],
    source=elasticity_source,
    online=True,
)

category_elasticity_features = FeatureView(
    name="category_price_elasticity",
    entities=[category],
    ttl=timedelta(hours=12),
    schema=[
        Field(name="category_elasticity_mean", dtype=Float64),
        Field(name="category_elasticity_std", dtype=Float64),
        Field(name="basket_affinity_score", dtype=Float64),
    ],
    source=elasticity_source,
    online=True,
)
