"""Serving adapter for the Disruption Shield (ADR-043, anomaly paradigm).

The disruption pipeline's ``AnomalyEnsemble`` couples an sklearn IsolationForest
with torch LSTM/GNN detectors. For the $0 serving path we persist + restore just
the **IsolationForest** (sklearn, torch-free): it is the always-available point-
anomaly detector and gives a real, per-node confidence from the *anomaly-score
margin* — how decisively a node sits above/below the detection threshold. The
torch detectors remain optional enhancements on the full pipeline path.

Pure sklearn/numpy — no torch — so this serving model, its confidence, and the
C42 probe path run on any runner.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import structlog

logger = structlog.get_logger(__name__)


class DisruptionServingModel:
    """Wrap a fitted IsolationForest behind an anomaly-margin confidence (ADR-043)."""

    def __init__(self, iforest: Any, *, score_lo: float, score_hi: float, version: str) -> None:
        self._if = iforest
        self._lo = float(score_lo)
        self._hi = float(score_hi)
        self.version = version

    @property
    def is_real(self) -> bool:
        return self._if is not None and self._hi > self._lo

    def anomaly_probability(self, features: np.ndarray) -> np.ndarray:
        """Per-row anomaly probability in [0,1] (higher = more anomalous).

        ``-decision_function`` is large for anomalies; min-max normalised against
        the calibration score range so the output is a bounded probability.
        """
        x = np.atleast_2d(np.asarray(features, dtype=np.float64))
        raw = -np.asarray(self._if.decision_function(x), dtype=np.float64)
        span = max(self._hi - self._lo, 1e-9)
        return np.clip((raw - self._lo) / span, 0.0, 1.0)

    def confidence(self, features: np.ndarray, threshold: float = 0.5) -> float:
        """ADR-040 confidence = mean decisiveness margin |p − threshold| (×2, clamped).

        A score far from the decision boundary (clearly normal or clearly anomalous)
        is a confident call; one near the threshold is uncertain. Never constant.
        """
        p = self.anomaly_probability(features)
        margin = np.abs(p - float(threshold))
        return round(float(np.clip(0.5 + np.mean(margin), 0.5, 0.99)), 4)


def build_disruption_model(artifact: Any, meta: dict[str, Any] | None = None) -> Any:
    """Model-builder for the $0 checkpoint path. ``artifact`` is the pickled dict
    ``{iforest, score_lo, score_hi}`` written by ``train.py``."""
    meta = meta or {}
    data = artifact if isinstance(artifact, dict) else {}
    return DisruptionServingModel(
        data.get("iforest"),
        score_lo=float(data.get("score_lo", 0.0)),
        score_hi=float(data.get("score_hi", 1.0)),
        version=str(meta.get("version") or "disruption_iforest"),
    )


def load_serving_model(
    registry: Any, *, city: str = "bengaluru", base_name: str = "disruption_iforest"
) -> DisruptionServingModel | None:
    """Resolve + wrap the fitted detector; None if degraded (I-7)."""
    if registry is None:
        return None
    loaded = registry.load(base_name, city=city)
    if not getattr(loaded, "is_real", False) or loaded.model is None:
        logger.warning("disruption_serving_model_degraded", name=base_name, city=city)
        return None
    model = loaded.model
    if not getattr(model, "is_real", False):
        return None
    logger.info("disruption_serving_model_loaded", name=loaded.name, version=loaded.version)
    return model  # type: ignore[no-any-return]


__all__ = ["DisruptionServingModel", "build_disruption_model", "load_serving_model"]
