"""data_fabric/etl/parquet_etl.py

CSV → Parquet conversion for Feast offline store. Adds event_timestamp
column required by Feast FileSource. Deterministic and reproducible (I-8).

Relocated from scripts/convert_to_parquet.py per v4.0 Part K.5b. The original
script remains as a thin shim for backward compatibility.

Usage:
    python -m data_fabric.etl.parquet_etl --city mumbai
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import structlog

log = structlog.get_logger()


def convert_demand_features(city: str, *, base_dir: Path | None = None) -> Path:
    """Convert demand_history.csv -> demand_features.parquet."""
    base = base_dir or Path("data") / city
    csv_path = base / "demand_history.csv"
    parquet_path = base / "demand_features.parquet"

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
    return parquet_path


def convert_weather_features(city: str, *, base_dir: Path | None = None) -> Path:
    """Convert weather_history.csv -> weather_features.parquet."""
    base = base_dir or Path("data") / city
    csv_path = base / "weather_history.csv"
    parquet_path = base / "weather_features.parquet"

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
    return parquet_path


def convert_store_features(city: str, *, base_dir: Path | None = None) -> Path:
    """Generate store_features.parquet from stores.json.

    Date range derived from demand_history.csv to ensure point-in-time
    alignment for Feast joins.
    """
    base = base_dir or Path("data") / city
    stores = pd.read_json(base / "stores.json")

    demand_dates = pd.read_csv(base / "demand_history.csv", usecols=["date"])["date"]
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
    parquet_path = base / "store_features.parquet"
    result.to_parquet(parquet_path, index=False)
    log.info("store_features_converted", city=city, rows=len(result), path=str(parquet_path))
    return parquet_path


def convert_all(city: str, *, base_dir: Path | None = None) -> dict[str, Path]:
    """Run all three conversions for one city."""
    return {
        "demand": convert_demand_features(city, base_dir=base_dir),
        "weather": convert_weather_features(city, base_dir=base_dir),
        "store": convert_store_features(city, base_dir=base_dir),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert CSV to Parquet for Feast")
    parser.add_argument("--city", required=True, choices=["bengaluru", "mumbai"])
    args = parser.parse_args()

    convert_all(args.city)
    log.info("all_conversions_complete", city=args.city)


if __name__ == "__main__":
    main()
