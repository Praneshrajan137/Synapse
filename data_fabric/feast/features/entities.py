"""SYNAPSE Feast Entity Definitions — all entity keys for the feature store."""
from feast import Entity

sku = Entity(
    name="sku_id",
    description="Stock Keeping Unit identifier",
)

store = Entity(
    name="store_id",
    description="Dark store identifier",
)

supplier = Entity(
    name="supplier_id",
    description="Supplier identifier",
)

zone = Entity(
    name="zone_id",
    description="Delivery zone identifier",
)

rider = Entity(
    name="rider_id",
    description="Delivery rider identifier",
)

city = Entity(
    name="city_id",
    description="City identifier for event calendar",
)

category = Entity(
    name="category_id",
    description="Product category identifier",
)
