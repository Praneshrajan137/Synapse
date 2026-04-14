"""
scripts/convert_to_parquet.py

Converts city CSV data to Parquet format for Feast offline store.
Adds event_timestamp column required by Feast FileSource.

Usage:
    python scripts/convert_to_parquet.py --city mumbai
    python scripts/convert_to_parquet.py --city bengaluru

INVARIANT I-8: Parquet conversion is deterministic and reproducible.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import structlog

log = structlog.get_logger()


def convert_demand_features(city: str) -> None:
    """Convert demand_history.csv -> demand_features.parquet with Feast-compatible schema."""
    csv_path = Path(f"data/{city}/demand_history.csv")
    parquet_path = Path(f"data/{city}/demand_features.parquet")

    df = pd.read_csv(csv_path)

    features: list[pd.DataFrame] = []
    for (store_id, sku_id), group in df.groupby(["store_id", "sku_id"]):
        group = group.sort_values("date")
        qty = group["quantity"]
        feat = pd.DataFrame({
            "store_id": store_id,
            "sku_id": sku_id,
            "event_timestamp": pd.to_datetime(group["date"]).dt.tz_localize("UTC"),
            "rolling_mean_7d": qty.rolling(7, min_periods=1).mean().values,
            "rolling_std_7d": qty.rolling(7, min_periods=1).std().fillna(0).values,
            "trend_slope": qty.rolling(7, min_periods=1).apply(
                lambda x: (x.iloc[-1] - x.iloc[0]) / max(len(x), 1), raw=False
            ).fillna(0).values,
            "seasonality_idx": (qty / qty.expanding().mean()).fillna(1.0).values,
            "orders_last_1h": qty.rolling(1, min_periods=1).sum().astype(np.int64).values,
            "orders_last_24h": qty.rolling(1, min_periods=1).sum().astype(np.int64).values,
        })
        features.append(feat)

    result = pd.concat(features, ignore_index=True)
    result.to_parquet(parquet_path, index=False)
    log.info("demand_features_converted", city=city, rows=len(result), path=str(parquet_path))


def convert_weather_features(city: str) -> None:
    """Convert weather_history.csv -> weather_features.parquet with Feast-compatible schema."""
    csv_path = Path(f"data/{city}/weather_history.csv")
    parquet_path = Path(f"data/{city}/weather_features.parquet")

    df = pd.read_csv(csv_path)
    df["event_timestamp"] = pd.to_datetime(df["date"]).dt.tz_localize("UTC")

    columns = [
        "store_id", "event_timestamp", "temperature_c", "humidity_pct",
        "precip_prob", "wind_speed_kmh",
    ]

    if "monsoon_intensity" not in df.columns:
        df["monsoon_intensity"] = 0.0
    columns.append("monsoon_intensity")

    result = df[columns].copy()
    result.to_parquet(parquet_path, index=False)
    log.info("weather_features_converted", city=city, rows=len(result), path=str(parquet_path))


def convert_store_features(city: str) -> None:
    """Generate store_features.parquet from stores.json for Feast.

    Date range is derived from demand_history.csv to ensure temporal alignment
    for Feast point-in-time joins.
    """
    stores = pd.read_json(f"data/{city}/stores.json")

    demand_csv = Path(f"data/{city}/demand_history.csv")
    demand_dates = pd.read_csv(demand_csv, usecols=["date"])["date"]
    min_date = pd.to_datetime(demand_dates.min())
    max_date = pd.to_datetime(demand_dates.max())
    dates = pd.date_range(start=min_date, end=max_date, freq="D", tz="UTC")

    records: list[dict] = []
    for _, store in stores.iterrows():
        for dt in dates:
            records.append({
                "store_id": store["id"],
                "event_timestamp": dt,
                "lat": store["lat"],
                "lon": store["lon"],
                "zone": store["zone"],
                "capacity_sqft": store.get("capacity_sqft", 1500),
                "cold_chain_enabled": int(store.get("cold_chain", True)),
            })

    result = pd.DataFrame(records)
    parquet_path = Path(f"data/{city}/store_features.parquet")
    result.to_parquet(parquet_path, index=False)
    log.info("store_features_converted", city=city, rows=len(result), path=str(parquet_path))


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert CSV to Parquet for Feast")
    parser.add_argument("--city", required=True, choices=["bengaluru", "mumbai"])
    args = parser.parse_args()

    convert_demand_features(args.city)
    convert_weather_features(args.city)
    convert_store_features(args.city)
    log.info("all_conversions_complete", city=args.city)


if __name__ == "__main__":
    main()
