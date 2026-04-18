"""scripts/convert_to_parquet.py — backward-compat shim.

The implementation moved to `data_fabric/etl/parquet_etl.py` per the v4.0
plan (Part K.5b). This shim preserves existing CLI invocations (Makefile,
docs, tutorials) while routing to the canonical module.

New code should import from `data_fabric.etl.parquet_etl` directly.
"""

from __future__ import annotations

from data_fabric.etl.parquet_etl import (  # noqa: F401  (re-exported)
    convert_all,
    convert_demand_features,
    convert_store_features,
    convert_weather_features,
    main,
)

if __name__ == "__main__":
    main()
