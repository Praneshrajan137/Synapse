"""SYNAPSE Freshness Guardian -- training (ADR-042/043, survival paradigm).

Fits the Weibull-AFT shelf-life model (lifelines), extracts its parameters (shape
``rho`` + the log-scale linear predictor), and persists them so serving
reconstructs the survival function in pure numpy (no lifelines runtime). Substance
is proven by **D-calibration coverage** (``d_cal``): the fraction of held-out
uncensored shelf lives that fall inside the model's 80% survival-time interval —
the survival analogue of conformal coverage (C40).

Analytical :class:`TrainResult` (AFT is a fit, not a gradient loop). lifelines is
imported lazily, so this module imports torch/lifelines-free for the AST gates.

Run::

    python -m agents.freshness_guardian.training.train [--smoke]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import structlog
from synapse_common.training_contract import TrainResult, save_checkpoint

logger = structlog.get_logger(__name__)

ROOT = Path(__file__).resolve().parents[3]
CHECKPOINT_DIR = ROOT / "artifacts" / "checkpoints"
SERVING_NAME = "freshness_weibull_aft"


def _extract_params(fitter: object) -> tuple[float, float, dict[str, float]]:
    """Pull (rho, lambda-intercept, lambda-coeffs) from a fitted WeibullAFTFitter."""
    params = fitter.params_  # type: ignore[attr-defined]  # MultiIndex Series
    lam = params["lambda_"]
    intercept = float(lam.get("Intercept", 0.0))
    coeffs = {str(k): float(v) for k, v in lam.items() if k != "Intercept"}
    rho = float(np.exp(params["rho_"].get("Intercept", 0.0)))
    return rho, intercept, coeffs


def train(config: object | None = None, *, smoke: bool = False) -> TrainResult:
    """Fit the Weibull-AFT, persist its params, measure D-cal interval coverage."""
    from agents.freshness_guardian.inference.serving_model import (  # noqa: PLC0415
        FreshnessServingModel,
    )
    from agents.freshness_guardian.models.shelf_life import ShelfLifeModel  # noqa: PLC0415

    seed = 42
    n = 1500 if smoke else 5000
    model = ShelfLifeModel()
    data = model.generate_synthetic_training_data(n_samples=n, seed=seed)
    mid = len(data) // 2
    fit_df, test_df = data.iloc[:mid].copy(), data.iloc[mid:].copy()
    model.fit(fit_df)

    rho, intercept, coeffs = _extract_params(model.model)
    serving = FreshnessServingModel(rho, intercept, coeffs, version="cal")

    # D-cal coverage: fraction of held-out *uncensored* lives inside the 80% interval.
    inside, total = 0, 0
    for _, row in test_df.iterrows():
        if int(row["event"]) != 1:  # censored — excluded from coverage
            continue
        cov = {
            "temperature_deviation_hours": float(row["temperature_deviation_hours"]),
            "humidity_deviation_pct": float(row["humidity_deviation_pct"]),
            "initial_shelf_life_days": float(row["initial_shelf_life_days"]),
            "is_cold_chain": float(row["is_cold_chain"]),
        }
        scale = serving._scale(cov)
        p10 = serving._time_at_survival(scale, 0.9)
        p90 = serving._time_at_survival(scale, 0.1)
        total += 1
        if p10 <= float(row["duration"]) <= p90:
            inside += 1
    d_cal = (inside / total) if total else 0.0

    CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
    params = {"rho": rho, "intercept": intercept, "coeffs": coeffs}
    ckpt_path = CHECKPOINT_DIR / f"{SERVING_NAME}.pt"
    sha = save_checkpoint(params, ckpt_path)
    (CHECKPOINT_DIR / f"{SERVING_NAME}.serving.json").write_text(
        json.dumps(
            {"version": f"{'smoke' if smoke else 'full'}_{sha}", "smoke": smoke},
            sort_keys=True,
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )

    result = TrainResult.analytical(
        "freshness_guardian", metrics={"d_cal": d_cal, "rho": rho, "n": float(n)}, seed=seed
    )
    logger.info("freshness_training_complete", sha=sha, d_cal=round(d_cal, 4), rho=round(rho, 4))
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Train Freshness Guardian Weibull-AFT")
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args()
    train(smoke=args.smoke)


if __name__ == "__main__":
    sys.exit(main())  # type: ignore[func-returns-value]
