"""Tests for the Feast demand-signals parquet builder (ADR-042 §Feast).

Proves the generated parquet matches the schema the `sku_demand_signals`
FeatureView declares (entities + 6 features, correct dtypes) so that, once Redis
is up, `feast materialize` populates the online store and FeatureProvider returns
FeatureSource.FEAST instead of FALLBACK. Pure pandas — no Feast/Redis needed.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from scripts.build_feature_store import FEATURE_COLUMNS, build_demand_signals


def _tiny_history(tmp_path: Path) -> Path:
    rows = []
    dates = pd.date_range("2025-01-01", periods=30, freq="D")
    for sku in range(3):
        for store in range(2):
            for d, date in enumerate(dates):
                rows.append(
                    {
                        "date": date.strftime("%Y-%m-%d"),
                        "store_id": f"BLR-00{store}",
                        "sku_id": f"SKU-{sku:04d}",
                        "quantity": 5 + sku + (d % 4),
                        "hour": 10,
                        "day_of_week": date.dayofweek,
                        "is_weekend": date.dayofweek >= 5,
                        "is_festival": False,
                        "festival_name": "",
                        "temperature_c": 28.0,
                        "humidity_pct": 50.0,
                        "precip_mm": 0.0,
                        "monsoon_active": False,
                    }
                )
    p = tmp_path / "demand_history.csv"
    pd.DataFrame(rows).to_csv(p, index=False)
    return p


def test_parquet_has_exact_feature_view_schema(tmp_path: Path) -> None:
    df = build_demand_signals(_tiny_history(tmp_path))
    expected = {"event_timestamp", "sku_id", "store_id", *FEATURE_COLUMNS}
    assert set(df.columns) == expected


def test_feature_dtypes_match_declaration(tmp_path: Path) -> None:
    df = build_demand_signals(_tiny_history(tmp_path))
    for col in ("rolling_mean_7d", "rolling_std_7d", "trend_slope", "seasonality_idx"):
        assert df[col].dtype == "float64", col
    for col in ("orders_last_1h", "orders_last_24h"):
        assert df[col].dtype == "int64", col


def test_features_are_finite_and_nonnegative_where_expected(tmp_path: Path) -> None:
    df = build_demand_signals(_tiny_history(tmp_path))
    assert df["rolling_mean_7d"].notna().all()
    assert (df["rolling_mean_7d"] >= 0).all()
    assert (df["rolling_std_7d"] >= 0).all()
    assert (df["orders_last_24h"] >= 0).all()


def test_one_row_per_sku_store_day(tmp_path: Path) -> None:
    df = build_demand_signals(_tiny_history(tmp_path))
    # 3 SKUs * 2 stores * 30 days, deduplicated by the daily groupby.
    assert len(df) == 3 * 2 * 30
    assert not df.duplicated(subset=["sku_id", "store_id", "event_timestamp"]).any()
