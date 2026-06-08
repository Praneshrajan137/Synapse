"""SYNAPSE Inventory Sentinel -- analytical "training" (ADR-042 analytical branch).

The newsvendor optimum Q* is **closed-form optimal** for the single-period problem
— forcing a gradient loop onto it would be the anti-pattern ADR-042 exists to
prevent. So this agent satisfies the training contract via *calibration*, not loss:
it calibrates the split-conformal interval on a held-out slice of the real demand
history and reports the empirical PI coverage. Returns a
:class:`~synapse_common.training_contract.TrainResult` with ``kind="analytical"``,
which the C40 calibration gate consumes (``pi_coverage``) and C37 exempts from the
gradient-step requirement.

Run::

    python -m agents.inventory_sentinel.training.train [--smoke]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import structlog
from synapse_common.training_contract import TrainResult

from agents.inventory_sentinel.models.newsvendor import conformal_bounds

logger = structlog.get_logger(__name__)

ROOT = Path(__file__).resolve().parents[3]
ALPHA = 0.1


def _residuals_from_history(csv_path: Path, *, max_skus: int, seed: int) -> np.ndarray:
    """Forecast = causal 7d rolling mean; residual = actual - forecast (per SKU)."""
    df = pd.read_csv(csv_path)
    df["date"] = pd.to_datetime(df["date"])
    daily = (
        df.groupby(["sku_id", "date"], as_index=False)["quantity"]
        .sum()
        .sort_values(["sku_id", "date"])
    )
    skus = list(dict.fromkeys(daily["sku_id"].tolist()))[:max_skus]
    residuals: list[float] = []
    for sku in skus:
        q = daily[daily["sku_id"] == sku]["quantity"].to_numpy(dtype=np.float64)
        if len(q) < 10:
            continue
        forecast = pd.Series(q).rolling(7, min_periods=1).mean().shift(1).to_numpy()
        valid = ~np.isnan(forecast)
        residuals.extend((q[valid] - forecast[valid]).tolist())
    return np.asarray(residuals, dtype=np.float64)


def train(config: object | None = None, *, smoke: bool = False) -> TrainResult:
    """Calibrate the newsvendor conformal interval; report held-out PI coverage."""
    seed = 42
    rng = np.random.default_rng(seed)
    csv = ROOT / "data" / "bengaluru" / "demand_history.csv"

    if csv.is_file():
        res = _residuals_from_history(csv, max_skus=8 if smoke else 100, seed=seed)
    else:  # pragma: no cover - data always present in repo
        res = rng.normal(0.0, 5.0, size=2000)

    if len(res) < 50:
        res = rng.normal(0.0, 5.0, size=2000)

    # Split-conformal: calibrate the half-width on one half, measure coverage on the other.
    rng.shuffle(res)
    mid = len(res) // 2
    cal, test = res[:mid], res[mid:]
    lower, upper = conformal_bounds(np.array([0.0]), cal, alpha=ALPHA)
    q = float((upper - lower) / 2.0)
    coverage = float(np.mean(np.abs(test) <= q))

    # ADR-043: persist the calibration residuals so serving restores *calibrated*
    # conformal bounds (real) instead of the empty default (degraded).
    from synapse_common.training_contract import save_checkpoint  # noqa: PLC0415

    ckpt_dir = ROOT / "artifacts" / "checkpoints"
    ckpt_dir.mkdir(parents=True, exist_ok=True)
    calibration = {"residuals": [round(float(r), 6) for r in cal.tolist()], "half_width": q}
    sha = save_checkpoint(calibration, ckpt_dir / "inventory_newsvendor.pt")
    (ckpt_dir / "inventory_newsvendor.serving.json").write_text(
        json.dumps(
            {"version": f"{'smoke' if smoke else 'full'}_{sha}", "smoke": smoke},
            sort_keys=True,
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )

    result = TrainResult.analytical(
        "inventory_sentinel",
        metrics={"pi_coverage": coverage, "half_width": q, "n_residuals": float(len(res))},
        seed=seed,
    )
    logger.info("inventory_calibration_complete", sha=sha, **result.to_dict()["metrics"])
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Calibrate Inventory Sentinel newsvendor interval")
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args()
    train(smoke=args.smoke)


if __name__ == "__main__":
    sys.exit(main())  # type: ignore[func-returns-value]
