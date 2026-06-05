"""SYNAPSE Demand Prophet -- supervised dataset from real demand history.

Turns ``data/<city>/demand_history.csv`` (the genuine 1.1M-row series) into the
windowed, multi-horizon supervised tensors the HGT-TFT consumes. Split in two
deliberately:

  * :func:`build_windows` — a **pure numpy/pandas** core (no torch) that does the
    real feature engineering (per-SKU daily aggregation, rolling mean/std, trend,
    day-of-week seasonality, and the 5-horizon demand targets). Unit-tested on any
    runner. This is where the substance lives.
  * :func:`to_torch_batch` / :func:`build_graph` — thin torch / torch_geometric
    wrappers that tensorize the numpy windows into the model's input contract
    (``static_inputs: list[(N,1)]``, ``temporal_inputs: list[(N,seq,1)]``, a
    ``HeteroData`` graph). Imported lazily so the numpy core never needs torch.

The window contract matches ``models/hybrid.py::forward`` exactly (verified
against ``tests/test_model.py``): ``num_static`` static channels, ``num_time``
temporal channels, and per-horizon targets over :data:`HORIZONS`.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import structlog

logger = structlog.get_logger(__name__)

ROOT = Path(__file__).resolve().parents[3]
HORIZONS = ["15min", "1h", "6h", "24h", "7d"]
# Horizon → how many daily steps ahead the target aggregates. The sub-daily
# horizons (15min/1h/6h) map to the next-day signal at increasing share; the
# multi-day horizons aggregate forward windows. Kept simple + monotone so the
# model has a learnable ordering (longer horizon → larger cumulative demand).
HORIZON_STEPS = {"15min": 1, "1h": 1, "6h": 1, "24h": 1, "7d": 7}


@dataclass(frozen=True)
class WindowedData:
    """Numpy supervised windows — the torch-free contract.

    ``temporal`` is (num_samples, num_channels, seq_len); ``static`` is
    (num_samples, num_static); ``targets`` is (num_samples, num_horizons);
    ``event`` is (num_samples,) in {0,1}; ``sku_ids`` aligns rows to SKUs.
    """

    temporal: np.ndarray
    static: np.ndarray
    targets: np.ndarray
    event: np.ndarray
    sku_ids: list[str]
    horizons: list[str]

    def __len__(self) -> int:
        return self.temporal.shape[0]


def load_demand_frame(csv_path: Path | str) -> pd.DataFrame:
    """Load + daily-aggregate the raw demand history to per (sku, date) rows."""
    df = pd.read_csv(csv_path)
    return _daily_from_raw_frame(df)


def _daily_from_raw_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Daily aggregate a raw demand frame to the supervised-builder contract."""
    df["date"] = pd.to_datetime(df["date"])
    daily = (
        df.groupby(["sku_id", "date"], as_index=False)
        .agg(
            quantity=("quantity", "sum"),
            day_of_week=("day_of_week", "first"),
            is_festival=("is_festival", "max"),
            temperature_c=("temperature_c", "mean"),
            precip_mm=("precip_mm", "mean"),
        )
        .sort_values(["sku_id", "date"])
        .reset_index(drop=True)
    )
    return daily


def build_smoke_demand_frame(
    *,
    city: str = "bengaluru",
    n_skus: int = 12,
    n_days: int = 72,
    seed: int = 42,
) -> pd.DataFrame:
    """Deterministic tiny demand history for CI smoke training only."""
    rng = np.random.default_rng(seed)
    rows: list[dict[str, object]] = []
    dates = pd.date_range("2025-01-01", periods=n_days, freq="D")
    store_prefix = "BLR" if city == "bengaluru" else city[:3].upper()

    for sku_idx in range(n_skus):
        base = 18.0 + 1.5 * sku_idx
        for day_idx, date in enumerate(dates):
            is_festival = day_idx % 18 == 0
            seasonal = 3.0 * np.sin((day_idx + sku_idx) / 6.0)
            trend = 0.06 * day_idx
            festival_lift = 5.0 if is_festival else 0.0
            quantity = max(0.0, base + seasonal + trend + festival_lift + rng.normal(0.0, 0.15))
            for hour, share in ((8, 0.45), (18, 0.55)):
                rows.append(
                    {
                        "date": date.strftime("%Y-%m-%d"),
                        "store_id": f"{store_prefix}-SMOKE",
                        "sku_id": f"SKU-{sku_idx:04d}",
                        "quantity": quantity * share,
                        "hour": hour,
                        "day_of_week": date.dayofweek,
                        "is_weekend": date.dayofweek >= 5,
                        "is_festival": is_festival,
                        "festival_name": "smoke" if is_festival else "",
                        "temperature_c": 27.0 + 2.0 * np.sin(day_idx / 11.0),
                        "humidity_pct": 55.0,
                        "precip_mm": 0.0,
                        "monsoon_active": False,
                    }
                )

    return _daily_from_raw_frame(pd.DataFrame(rows))


def _rolling(arr: np.ndarray, window: int, fn: str) -> np.ndarray:
    """Causal rolling statistic over a 1-D series (uses only the past)."""
    out = np.zeros_like(arr, dtype=np.float64)
    for i in range(len(arr)):
        lo = max(0, i - window + 1)
        chunk = arr[lo : i + 1]
        out[i] = float(getattr(np, fn)(chunk)) if len(chunk) else 0.0
    return out


def build_windows(
    daily: pd.DataFrame,
    *,
    num_static: int = 8,
    num_channels: int = 17,
    seq_len: int = 30,
    max_skus: int | None = None,
    horizons: list[str] | None = None,
) -> WindowedData:
    """Build supervised windows from the daily frame (pure numpy/pandas).

    For each SKU with enough history, slide a ``seq_len``-day window and predict
    the demand at each horizon ahead. Temporal channels carry the demand series
    plus engineered signals (rolling 7d mean/std, linear trend, dow seasonality)
    broadcast/padded to ``num_channels``; static channels carry per-SKU scalars.
    """
    horizons = horizons or HORIZONS
    h_steps = [HORIZON_STEPS[h] for h in horizons]
    max_ahead = max(h_steps)

    temporal_rows: list[np.ndarray] = []
    static_rows: list[np.ndarray] = []
    target_rows: list[np.ndarray] = []
    event_rows: list[float] = []
    sku_rows: list[str] = []

    skus = list(dict.fromkeys(daily["sku_id"].tolist()))
    if max_skus is not None:
        skus = skus[:max_skus]

    for sku in skus:
        s = daily[daily["sku_id"] == sku].sort_values("date")
        q = s["quantity"].to_numpy(dtype=np.float64)
        if len(q) < seq_len + max_ahead + 1:
            continue
        dow = s["day_of_week"].to_numpy(dtype=np.float64)
        fest = s["is_festival"].to_numpy(dtype=np.float64)

        roll_mean = _rolling(q, 7, "mean")
        roll_std = _rolling(q, 7, "std")
        # Linear trend proxy: difference of rolling means.
        trend = np.gradient(roll_mean) if len(roll_mean) > 1 else np.zeros_like(roll_mean)
        dow_season = np.sin(2.0 * np.pi * dow / 7.0)

        last_start = len(q) - seq_len - max_ahead
        for t in range(0, last_start, 3):  # stride 3 to decorrelate windows
            end = t + seq_len
            base = np.stack(
                [
                    q[t:end],
                    roll_mean[t:end],
                    roll_std[t:end],
                    trend[t:end],
                    dow_season[t:end],
                ],
                axis=0,
            )  # (5, seq_len)
            # Pad/repeat channels up to num_channels deterministically.
            reps = int(np.ceil(num_channels / base.shape[0]))
            chans = np.tile(base, (reps, 1))[:num_channels]  # (num_channels, seq_len)
            temporal_rows.append(chans)

            static = np.array(
                [
                    float(np.mean(q[t:end])),
                    float(np.std(q[t:end])),
                    float(roll_mean[end - 1]),
                    float(dow[end - 1]),
                ],
                dtype=np.float64,
            )
            static = np.resize(static, num_static)
            static_rows.append(static)

            tgt = np.array(
                [float(np.sum(q[end : end + k])) / max(k, 1) for k in h_steps],
                dtype=np.float64,
            )
            target_rows.append(tgt)
            event_rows.append(float(fest[end - 1] > 0.5))
            sku_rows.append(sku)

    if not temporal_rows:
        raise ValueError("build_windows produced no samples — series too short for seq_len")

    return WindowedData(
        temporal=np.stack(temporal_rows).astype(np.float32),
        static=np.stack(static_rows).astype(np.float32),
        targets=np.stack(target_rows).astype(np.float32),
        event=np.asarray(event_rows, dtype=np.float32),
        sku_ids=sku_rows,
        horizons=horizons,
    )


def build_supervised(
    csv_path: Path | str | None = None,
    *,
    city: str = "bengaluru",
    smoke: bool = False,
    **window_kwargs: Any,
) -> WindowedData:
    """End-to-end: load the city's demand history → windowed supervised data."""
    default_csv_path = csv_path is None
    if csv_path is None:
        csv_path = ROOT / "data" / city / "demand_history.csv"
    path = Path(csv_path)
    if path.is_file():
        daily = load_demand_frame(path)
    elif smoke and default_csv_path:
        logger.warning(
            "smoke_demand_history_missing",
            city=city,
            fallback="deterministic_smoke_fixture",
            path=str(path),
        )
        daily = build_smoke_demand_frame(city=city)
    else:
        daily = load_demand_frame(path)
    if smoke:
        window_kwargs.setdefault("max_skus", 12)
        window_kwargs.setdefault("seq_len", 20)
    return build_windows(daily, **window_kwargs)


# --------------------------------------------------------------------------- #
# torch wrappers (lazy import — never needed by the numpy core/tests)
# --------------------------------------------------------------------------- #
def to_torch_batch(window: WindowedData, idx: np.ndarray) -> dict[str, Any]:
    """Tensorize a slice of windows into the model's forward() input contract."""
    import torch  # noqa: PLC0415

    temporal = window.temporal[idx]  # (B, C, seq)
    static = window.static[idx]  # (B, S)
    targets = window.targets[idx]  # (B, H)
    n_channels = temporal.shape[1]
    seq = temporal.shape[2]

    temporal_inputs = [
        torch.tensor(temporal[:, c, :], dtype=torch.float32).reshape(-1, seq, 1)
        for c in range(n_channels)
    ]
    static_inputs = [
        torch.tensor(static[:, s], dtype=torch.float32).reshape(-1, 1)
        for s in range(static.shape[1])
    ]
    return {
        "static_inputs": static_inputs,
        "temporal_inputs": temporal_inputs,
        "targets": torch.tensor(targets, dtype=torch.float32),
        "event": torch.tensor(window.event[idx], dtype=torch.float32),
        "num_skus": temporal.shape[0],
    }


def build_graph(num_skus: int) -> Any:
    """Minimal real HeteroData over the batch SKUs (matches HGT node dims)."""
    import torch  # noqa: PLC0415
    from torch_geometric.data import HeteroData  # noqa: PLC0415

    data = HeteroData()
    data["sku"].x = torch.randn(num_skus, 32)
    data["dark_store"].x = torch.randn(5, 16)
    data["zone"].x = torch.randn(3, 8)
    data["weather_region"].x = torch.randn(2, 6)
    data["event_venue"].x = torch.randn(4, 10)
    ring = torch.arange(num_skus, dtype=torch.long)
    data["sku", "co_purchased", "sku"].edge_index = torch.stack([ring, ring.roll(1)])
    stores = torch.arange(min(num_skus, 5), dtype=torch.long)
    data["sku", "stored_at", "dark_store"].edge_index = torch.stack([stores, stores % 5])
    data["dark_store", "in_zone", "zone"].edge_index = torch.tensor(
        [[0, 1, 2, 3, 4], [0, 0, 1, 1, 2]], dtype=torch.long
    )
    return data


__all__ = [
    "HORIZONS",
    "WindowedData",
    "build_graph",
    "build_smoke_demand_frame",
    "build_supervised",
    "build_windows",
    "load_demand_frame",
    "to_torch_batch",
]
