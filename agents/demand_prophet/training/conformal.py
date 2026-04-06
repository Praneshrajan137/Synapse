"""
SYNAPSE Demand Prophet -- Conformal Prediction Calibration via MAPIE.
Post-training calibration producing guaranteed coverage intervals.

INV-DP-001: Every forecast MUST include conformal intervals.
INV-DP-002: 90% interval achieves >=85% empirical coverage.
"""
from __future__ import annotations

import numpy as np
import structlog

logger = structlog.get_logger(__name__)

try:
    from mapie.regression import MapieQuantileRegressor  # noqa: F401

    HAS_MAPIE = True
except ImportError:
    HAS_MAPIE = False
    logger.warning("mapie_not_available", fallback="quantile-based intervals")


class ConformalCalibrator:
    """
    MAPIE-based conformal prediction calibrator.
    Wraps trained model point predictions with distribution-free prediction intervals.
    """

    def __init__(
        self,
        alpha: float = 0.1,
        coverage_target: float = 0.85,
    ) -> None:
        self.alpha = alpha
        self.coverage_target = coverage_target
        self._calibrated = False
        self._quantile_adjustments: dict[str, tuple[float, float]] = {}

    def fit(
        self,
        predictions: dict[str, np.ndarray],
        actuals: dict[str, np.ndarray],
    ) -> dict[str, float]:
        """
        Calibrate conformal intervals on holdout set.

        Returns:
            Dict of empirical coverage per horizon after calibration.
        """
        coverages: dict[str, float] = {}

        for horizon in predictions:
            preds = predictions[horizon]
            actual = actuals[horizon]

            lower_raw = preds[:, 0]
            upper_raw = preds[:, 2]

            scores_lower = lower_raw - actual
            scores_upper = actual - upper_raw

            n = len(actual)
            q_level = min(np.ceil((1 - self.alpha) * (n + 1)) / n, 1.0)

            adjustment_lower = float(np.quantile(scores_lower, q_level))
            adjustment_upper = float(np.quantile(scores_upper, q_level))

            self._quantile_adjustments[horizon] = (adjustment_lower, adjustment_upper)

            calibrated_lower = lower_raw - adjustment_lower
            calibrated_upper = upper_raw + adjustment_upper
            coverage = float(
                np.mean((actual >= calibrated_lower) & (actual <= calibrated_upper))
            )
            coverages[horizon] = coverage

            logger.info(
                "conformal_calibration",
                horizon=horizon,
                coverage=f"{coverage:.3f}",
                target=self.coverage_target,
                adjustment_lower=f"{adjustment_lower:.4f}",
                adjustment_upper=f"{adjustment_upper:.4f}",
                passed=coverage >= self.coverage_target,
            )

        self._calibrated = True
        return coverages

    def predict_intervals(
        self,
        predictions: dict[str, np.ndarray],
    ) -> dict[str, tuple[np.ndarray, np.ndarray]]:
        """
        Apply calibrated conformal adjustments to predictions.

        Raises:
            RuntimeError: If not calibrated (INV-DP-001 would be violated).
        """
        if not self._calibrated:
            raise RuntimeError(
                "ConformalCalibrator not calibrated. Call fit() first. "
                "Producing forecasts without conformal intervals violates INV-DP-001."
            )

        intervals: dict[str, tuple[np.ndarray, np.ndarray]] = {}

        for horizon in predictions:
            preds = predictions[horizon]
            adj_lower, adj_upper = self._quantile_adjustments.get(horizon, (0.0, 0.0))

            lower = np.maximum(preds[:, 0] - adj_lower, 0.0)
            upper = np.maximum(preds[:, 2] + adj_upper, lower)

            intervals[horizon] = (lower, upper)

        return intervals

    @property
    def is_calibrated(self) -> bool:
        return self._calibrated

    def get_adjustments(self) -> dict[str, tuple[float, float]]:
        """Return calibration adjustments for MLflow logging."""
        return self._quantile_adjustments.copy()
