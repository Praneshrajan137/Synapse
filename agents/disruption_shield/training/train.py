"""SYNAPSE Disruption Shield -- training (ADR-042/043, anomaly paradigm).

Fits the IsolationForest point-anomaly detector on a seeded mix of normal and
anomalous supply-chain feature vectors, measures its **detection separability**
(ROC-AUC of the anomaly score vs. the injected labels — the anomaly analogue of
calibration coverage), and persists the fitted detector + score range so serving
reconstructs a real, margin-based confidence. Pure sklearn/numpy (no torch); the
torch LSTM/GNN detectors are optional pipeline enhancements, not required for the
substance proof.

Returns an analytical :class:`TrainResult` (no gradient loop — IsolationForest is
a fit, not an optimizer); C40-style substance is the AUC in ``metrics``.

Run::

    python -m agents.disruption_shield.training.train [--smoke]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import structlog
from synapse_common.training_contract import TrainResult, save_checkpoint

logger = structlog.get_logger(__name__)

ROOT = Path(__file__).resolve().parents[3]
CHECKPOINT_DIR = ROOT / "artifacts" / "checkpoints"
SERVING_NAME = "disruption_iforest"


def _make_data(rng: np.random.Generator, n: int, dim: int) -> tuple[np.ndarray, np.ndarray]:
    """Seeded normal cluster + injected anomalies; returns (features, is_anomaly)."""
    n_anom = max(1, n // 10)
    normal = rng.normal(0.0, 1.0, size=(n - n_anom, dim))
    anom = rng.normal(5.0, 1.5, size=(n_anom, dim))  # shifted = anomalous
    x = np.vstack([normal, anom])
    y = np.concatenate([np.zeros(len(normal)), np.ones(len(anom))])
    idx = rng.permutation(len(x))
    return x[idx], y[idx]


def train(config: object | None = None, *, smoke: bool = False) -> TrainResult:
    """Fit the IsolationForest detector + measure detection AUC + persist it."""
    from sklearn.ensemble import IsolationForest  # noqa: PLC0415
    from sklearn.metrics import roc_auc_score  # noqa: PLC0415

    seed = 42
    rng = np.random.default_rng(seed)
    n = 600 if smoke else 4000
    dim = 12

    x, y = _make_data(rng, n, dim)
    mid = len(x) // 2
    x_fit, x_test, y_test = x[:mid], x[mid:], y[mid:]

    iforest = IsolationForest(n_estimators=100, contamination=0.1, random_state=seed)
    iforest.fit(x_fit)

    # Detection separability: AUC of the anomaly score against injected labels.
    fit_scores = -iforest.decision_function(x_fit)
    score_lo, score_hi = float(np.min(fit_scores)), float(np.max(fit_scores))
    test_scores = -iforest.decision_function(x_test)
    auc = float(roc_auc_score(y_test, test_scores)) if len(set(y_test.tolist())) > 1 else 0.0

    CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
    ckpt_path = CHECKPOINT_DIR / f"{SERVING_NAME}.pt"
    payload = {"iforest": iforest, "score_lo": score_lo, "score_hi": score_hi}
    sha = save_checkpoint(payload, ckpt_path)  # sklearn obj → pickle
    (CHECKPOINT_DIR / f"{SERVING_NAME}.serving.json").write_text(
        f'{{"version":"{"smoke" if smoke else "full"}_{sha}","smoke":{str(smoke).lower()}}}',
        encoding="utf-8",
    )

    result = TrainResult.analytical(
        "disruption_shield", metrics={"detection_auc": auc, "n": float(n)}, seed=seed
    )
    logger.info("disruption_training_complete", sha=sha, detection_auc=round(auc, 4))
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Train Disruption Shield IsolationForest")
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args()
    train(smoke=args.smoke)


if __name__ == "__main__":
    sys.exit(main())  # type: ignore[func-returns-value]
