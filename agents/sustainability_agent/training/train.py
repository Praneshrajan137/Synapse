"""SYNAPSE Sustainability Agent -- training (ADR-042/043, predictive paradigm).

Fits the Kaplan-Meier waste-survival curve (lifelines) on seeded waste-duration
data and persists the curve as (timeline, survival) arrays so serving reconstructs
it in numpy (no lifelines runtime). Substance is proven by **survival calibration**
(``survival_calibration``): 1 − mean|empirical − predicted| survival over a grid on
a held-out split — how well the fitted curve generalizes.

Analytical :class:`TrainResult` (KM is a fit, not a gradient loop). lifelines is
imported lazily so this module imports lifelines-free for the AST gates.

Run::

    python -m agents.sustainability_agent.training.train [--smoke]
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
SERVING_NAME = "sustainability_waste_km"


def _empirical_survival(durations: np.ndarray, grid: np.ndarray) -> np.ndarray:
    """Empirical survival S(t) = P(duration > t) over a grid (held-out check)."""
    return np.array([float(np.mean(durations > t)) for t in grid])


def train(config: object | None = None, *, smoke: bool = False) -> TrainResult:
    """Fit the KM waste-survival curve, persist it, measure held-out calibration."""
    from lifelines import KaplanMeierFitter  # noqa: PLC0415

    seed = 42
    rng = np.random.default_rng(seed)
    n = 1500 if smoke else 6000

    # Seeded waste durations (days-to-discard) with right-censoring (items sold).
    durations = rng.weibull(1.6, n) * 6.0
    events = rng.binomial(1, 0.7, n)  # 1 = wasted, 0 = censored (sold)
    mid = n // 2
    d_fit, d_test = durations[:mid], durations[mid:]
    e_fit = events[:mid]

    km = KaplanMeierFitter()
    km.fit(d_fit, event_observed=e_fit)
    sf = km.survival_function_
    timeline = [float(t) for t in sf.index.to_numpy()]
    survival = [float(v) for v in sf.iloc[:, 0].to_numpy()]

    # Survival calibration on held-out: 1 − mean|empirical − KM| over a grid.
    grid = np.linspace(0.5, float(np.quantile(d_test, 0.9)), 12)
    emp = _empirical_survival(d_test, grid)
    pred = np.interp(grid, timeline, survival, left=1.0, right=survival[-1])
    survival_calibration = float(np.clip(1.0 - np.mean(np.abs(emp - pred)), 0.0, 1.0))

    CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
    curve = {"timeline": timeline, "survival": survival}
    ckpt_path = CHECKPOINT_DIR / f"{SERVING_NAME}.pt"
    sha = save_checkpoint(curve, ckpt_path)
    (CHECKPOINT_DIR / f"{SERVING_NAME}.serving.json").write_text(
        json.dumps({"version": f"{'smoke' if smoke else 'full'}_{sha}", "smoke": smoke},
                   sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )

    result = TrainResult.analytical(
        "sustainability_agent",
        metrics={"survival_calibration": survival_calibration, "n": float(n)},
        seed=seed,
    )
    logger.info("sustainability_training_complete", sha=sha,
                survival_calibration=round(survival_calibration, 4))
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Train Sustainability Agent waste-survival curve")
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args()
    train(smoke=args.smoke)


if __name__ == "__main__":
    sys.exit(main())  # type: ignore[func-returns-value]
