"""SYNAPSE ETL — Parquet conversion and Kafka-to-Parquet sinks.

Per Part K.5b/K-M6: scripts/convert_to_parquet.py logic relocated here.
A backward-compat shim remains at scripts/convert_to_parquet.py.
"""

from data_fabric.etl.parquet_etl import (
    convert_demand_features,
    convert_store_features,
    convert_weather_features,
    convert_all,
)

__all__ = [
    "convert_demand_features",
    "convert_store_features",
    "convert_weather_features",
    "convert_all",
]
