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
        # Empirical 90% coverage measured on the most recent calibration set,
        # aggregated across horizons. The serving pipeline reads this to drive the
        # INV-DP-002 coverage metric (DEMAND_PROPHET_COVERAGE_P90). ``None`` until
        # fit() runs — the pipeline then skips the metric update (NaN-safe).
        self.last_coverage_p90: float | None = None
        self.last_coverage_per_horizon: dict[str, float] = {}

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

            # Conformalized Quantile Regression (Romano, Patterson & Candès, 2019).
            # A SINGLE symmetric conformity score E_i = max(q_lo - y, y - q_hi)
            # measures how far each actual falls outside the base interval (negative
            # when comfortably inside). The recalibration radius is the finite-sample
            # corrected (1-alpha)(1 + 1/n) empirical quantile of {E_i}. Widening both
            # ends by this single Q gives the marginal coverage guarantee
            # P(y in [q_lo - Q, q_hi + Q]) >= 1 - alpha.
            #
            # The previous implementation took two separate one-sided 0.9-quantiles of
            # the SIGNED exceedances and applied both — which systematically
            # under-covered (~0.80 for a nominal 0.90 interval). CQR fixes that.
            scores = np.maximum(lower_raw - actual, actual - upper_raw)

            n = len(actual)
            # Quantile level with the +1 finite-sample correction, clamped to 1.0.
            q_level = min((np.ceil((1 - self.alpha) * (n + 1))) / n, 1.0)
            q = float(np.quantile(scores, q_level, method="higher"))

            # Store as a symmetric (lower, upper) pair so predict_intervals — which
            # widens by adj_lower on the low side and adj_upper on the high side —
            # is unchanged.
            self._quantile_adjustments[horizon] = (q, q)

            calibrated_lower = np.maximum(lower_raw - q, 0.0)
            calibrated_upper = upper_raw + q
            coverage = float(np.mean((actual >= calibrated_lower) & (actual <= calibrated_upper)))
            coverages[horizon] = coverage

            logger.info(
                "conformal_calibration",
                horizon=horizon,
                coverage=f"{coverage:.3f}",
                target=self.coverage_target,
                conformity_q=f"{q:.4f}",
                passed=coverage >= self.coverage_target,
            )

        self._calibrated = True
        self.last_coverage_per_horizon = dict(coverages)
        # Aggregate empirical coverage across horizons → the single p90 number the
        # serving pipeline surfaces (INV-DP-002). Mean is the honest summary: a
        # single under-covered horizon drags it toward the floor.
        self.last_coverage_p90 = float(np.mean(list(coverages.values()))) if coverages else None
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
