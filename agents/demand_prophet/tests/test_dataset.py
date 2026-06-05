"""Tests for the torch-free supervised dataset core (Phase 1, ADR-042).

Proves the real feature engineering over demand history produces correctly-shaped,
deterministic, model-contract-matching windows — without torch. The torch
tensorization (to_torch_batch / build_graph) is exercised by the CI smoke train.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
import pandas as pd
import pytest

if TYPE_CHECKING:
    from pathlib import Path

from agents.demand_prophet.training.dataset import (
    HORIZONS,
    build_supervised,
    build_windows,
    load_demand_frame,
)


def _synthetic_csv(tmp_path: Path, n_skus: int = 3, n_days: int = 60) -> Path:
    rng = np.random.default_rng(0)
    rows = []
    dates = pd.date_range("2025-01-01", periods=n_days, freq="D")
    for sku in range(n_skus):
        base = 10 + 5 * sku
        for d, date in enumerate(dates):
            # two intraday rows per day to exercise the daily aggregation
            for hour in (8, 18):
                rows.append(
                    {
                        "date": date.strftime("%Y-%m-%d"),
                        "store_id": "BLR-001",
                        "sku_id": f"SKU-{sku:04d}",
                        "quantity": max(0, int(base + 3 * np.sin(d / 7) + rng.normal(0, 1))),
                        "hour": hour,
                        "day_of_week": date.dayofweek,
                        "is_weekend": date.dayofweek >= 5,
                        "is_festival": (d % 17 == 0),
                        "festival_name": "",
                        "temperature_c": 28.0,
                        "humidity_pct": 50.0,
                        "precip_mm": 0.0,
                        "monsoon_active": False,
                    }
                )
    path = tmp_path / "demand_history.csv"
    pd.DataFrame(rows).to_csv(path, index=False)
    return path


def test_load_demand_frame_aggregates_to_daily(tmp_path: Path) -> None:
    daily = load_demand_frame(_synthetic_csv(tmp_path, n_skus=2, n_days=40))
    # 2 SKUs * 40 days, one row each after daily aggregation
    assert len(daily) == 80
    assert set(daily["sku_id"].unique()) == {"SKU-0000", "SKU-0001"}
    assert (daily["quantity"] >= 0).all()


def test_build_windows_shapes_match_model_contract(tmp_path: Path) -> None:
    daily = load_demand_frame(_synthetic_csv(tmp_path, n_skus=3, n_days=60))
    w = build_windows(daily, num_static=8, num_channels=17, seq_len=20)
    assert len(w) > 0
    assert w.temporal.shape[1:] == (17, 20)  # (C, seq)
    assert w.static.shape[1] == 8
    assert w.targets.shape[1] == len(HORIZONS)
    assert w.event.shape[0] == len(w)
    assert len(w.sku_ids) == len(w)


def test_targets_non_negative_and_finite(tmp_path: Path) -> None:
    daily = load_demand_frame(_synthetic_csv(tmp_path, n_skus=2, n_days=60))
    w = build_windows(daily, seq_len=20)
    assert np.all(w.targets >= 0.0)
    assert np.all(np.isfinite(w.temporal))
    assert np.all(np.isfinite(w.static))


def test_build_windows_is_deterministic(tmp_path: Path) -> None:
    csv = _synthetic_csv(tmp_path, n_skus=3, n_days=60)
    w1 = build_windows(load_demand_frame(csv), seq_len=20)
    w2 = build_windows(load_demand_frame(csv), seq_len=20)
    assert np.array_equal(w1.temporal, w2.temporal)
    assert np.array_equal(w1.targets, w2.targets)


def test_smoke_supervised_uses_deterministic_fallback_when_default_csv_missing() -> None:
    w1 = build_supervised(city="ci_smoke_missing", smoke=True, num_channels=9, num_static=8)
    w2 = build_supervised(city="ci_smoke_missing", smoke=True, num_channels=9, num_static=8)
    assert len(w1) > 0
    assert w1.temporal.shape[1:] == (9, 20)
    assert np.array_equal(w1.temporal, w2.temporal)
    assert np.array_equal(w1.targets, w2.targets)


def test_short_series_raises(tmp_path: Path) -> None:
    daily = load_demand_frame(_synthetic_csv(tmp_path, n_skus=1, n_days=15))
    with pytest.raises(ValueError, match="no samples"):
        build_windows(daily, seq_len=30)
