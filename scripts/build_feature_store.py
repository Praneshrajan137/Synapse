"""Materialize the Feast offline feature parquet from real demand history.

The Feast `sku_demand_signals` FileSource points at ``data/demand_signals.parquet``
(relative to the feast repo at ``data_fabric/feast/``), but that file was never
generated — so even with Redis up, ``feast materialize`` had nothing to push and
``FeatureProvider`` always returned ``FALLBACK``. This script computes the six
declared features from ``data/<city>/demand_history.csv`` and writes the parquet
in the exact schema ``features/demand_features.py`` expects.

Pipeline (ADR-042 §Feast):
  1. build the parquet (this script — pure pandas, no infra) ;
  2. ``feast apply`` in ``data_fabric/feast/`` (registers views to registry.db) ;
  3. ``feast materialize`` (offline parquet → Redis online store — needs Redis).

Steps 2-3 are the operator/CI path; ``--apply`` shells step 2 when the feast CLI
is available. The parquet itself is the verifiable substance.

Run::

    python scripts/build_feature_store.py --city bengaluru
    python scripts/build_feature_store.py --city bengaluru --apply
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import structlog

logger = structlog.get_logger(__name__)

ROOT = Path(__file__).resolve().parents[1]
FEAST_REPO = ROOT / "data_fabric" / "feast"
# The FileSource path is relative to the feast repo dir.
OFFLINE_PARQUET = FEAST_REPO / "data" / "demand_signals.parquet"

FEATURE_COLUMNS = [
    "rolling_mean_7d",
    "rolling_std_7d",
    "trend_slope",
    "seasonality_idx",
    "orders_last_1h",
    "orders_last_24h",
]


def build_demand_signals(csv_path: Path) -> pd.DataFrame:
    """Compute the six `sku_demand_signals` features per (sku, store, day)."""
    df = pd.read_csv(csv_path)
    df["date"] = pd.to_datetime(df["date"])

    daily = (
        df.groupby(["sku_id", "store_id", "date"], as_index=False)
        .agg(quantity=("quantity", "sum"), orders=("quantity", "size"))
        .sort_values(["sku_id", "store_id", "date"])
        .reset_index(drop=True)
    )

    frames: list[pd.DataFrame] = []
    for (sku, store), g in daily.groupby(["sku_id", "store_id"], sort=False):
        g = g.sort_values("date").copy()
        q = g["quantity"].astype(float)
        g["rolling_mean_7d"] = q.rolling(7, min_periods=1).mean()
        g["rolling_std_7d"] = q.rolling(7, min_periods=1).std().fillna(0.0)
        # Trend slope: gradient of the rolling mean (per-day change).
        g["trend_slope"] = np.gradient(g["rolling_mean_7d"].to_numpy()) if len(g) > 1 else 0.0
        # Day-of-week seasonality index vs the SKU/store mean.
        dow = g["date"].dt.dayofweek
        dow_mean = q.groupby(dow).transform("mean")
        overall = max(float(q.mean()), 1e-6)
        g["seasonality_idx"] = (dow_mean / overall).to_numpy()
        g["orders_last_1h"] = np.maximum(g["orders"] // 24, 0).astype("int64")
        g["orders_last_24h"] = g["orders"].astype("int64")
        frames.append(g)

    out = pd.concat(frames, ignore_index=True)
    out["event_timestamp"] = out["date"]
    cols = ["event_timestamp", "sku_id", "store_id", *FEATURE_COLUMNS]
    result = out[cols].copy()
    for c in ("rolling_mean_7d", "rolling_std_7d", "trend_slope", "seasonality_idx"):
        result[c] = result[c].astype("float64")
    return result


def write_parquet(df: pd.DataFrame, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)
    logger.info("feature_parquet_written", path=str(path), rows=len(df))
    return path


def run_feast_apply() -> bool:
    """Best-effort ``feast apply`` in the feast repo. Returns success."""
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "feast", "apply"],
            cwd=FEAST_REPO,
            capture_output=True,
            text=True,
            timeout=120,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        logger.warning("feast_apply_failed", error=str(exc))
        return False
    if proc.returncode != 0:
        logger.warning("feast_apply_nonzero", stderr=proc.stderr[:400])
        return False
    logger.info("feast_apply_ok", stdout=proc.stdout[-200:])
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the Feast demand-signals parquet")
    parser.add_argument("--city", default="bengaluru")
    parser.add_argument("--apply", action="store_true", help="also run `feast apply`")
    parser.add_argument("--max-rows", type=int, default=None, help="cap rows (smoke)")
    args = parser.parse_args(argv)

    csv_path = ROOT / "data" / args.city / "demand_history.csv"
    if not csv_path.is_file():
        print(f"[XX] no demand history at {csv_path}")
        return 1

    df = build_demand_signals(csv_path)
    if args.max_rows:
        df = df.head(args.max_rows)
    out = OFFLINE_PARQUET if args.city == "bengaluru" else (
        FEAST_REPO / args.city / "data" / "demand_signals.parquet"
    )
    write_parquet(df, out)
    print(f"[OK] wrote {len(df)} rows -> {out.relative_to(ROOT)}")

    if args.apply and not run_feast_apply():
        print("[--] feast apply skipped/failed (CLI or registry unavailable)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
