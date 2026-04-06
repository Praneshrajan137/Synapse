"""
SYNAPSE Sustainability Agent -- Waste Prediction via Survival Analysis.
Uses lifelines KaplanMeierFitter for non-parametric survival curves and
CoxPHFitter for covariate-based hazard modelling. Connects with quality
scores from Freshness Guardian.
"""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
import structlog

logger = structlog.get_logger(__name__)


class WastePredictionModel:
    """
    Survival-analysis-based food waste predictor.
    KaplanMeierFitter: non-parametric survival curve per product category.
    CoxPHFitter: semi-parametric hazard model using quality covariates.
    """

    def __init__(self) -> None:
        self._km_fitter: Any = None
        self._cox_fitter: Any = None
        self._is_fitted: bool = False

    def fit(
        self,
        durations: np.ndarray,
        event_observed: np.ndarray,
        covariates: pd.DataFrame | None = None,
    ) -> None:
        """
        Fit survival models on historical waste data.

        Args:
            durations: Time-to-event (days until waste/discard).
            event_observed: 1 if item was wasted, 0 if censored (sold).
            covariates: Optional DataFrame with columns for Cox model
                        (e.g. quality_score, temperature, humidity).
        """
        from lifelines import CoxPHFitter, KaplanMeierFitter

        self._km_fitter = KaplanMeierFitter()
        self._km_fitter.fit(durations, event_observed=event_observed)

        if covariates is not None and len(covariates.columns) > 0:
            cox_df = covariates.copy()
            cox_df["duration"] = durations
            cox_df["event"] = event_observed

            self._cox_fitter = CoxPHFitter(penalizer=0.1)
            self._cox_fitter.fit(
                cox_df,
                duration_col="duration",
                event_col="event",
            )

        self._is_fitted = True
        logger.info(
            "waste_model_fitted",
            n_samples=len(durations),
            has_cox=self._cox_fitter is not None,
        )

    def predict_waste_probability(
        self,
        days_ahead: int,
        covariates: pd.DataFrame | None = None,
    ) -> dict[str, Any]:
        """
        Predict waste probability at a given time horizon.

        Args:
            days_ahead: Number of days into the future.
            covariates: Per-item covariates for Cox model.

        Returns:
            Dict with waste_probability, survival_curve, and hazard_rate.
        """
        if not self._is_fitted or self._km_fitter is None:
            logger.warning("model_not_fitted", fallback="default waste estimate")
            return self._fallback_prediction(days_ahead)

        survival_at_t = float(self._km_fitter.predict(days_ahead))
        waste_probability = 1.0 - survival_at_t

        timeline = np.arange(0, days_ahead + 1)
        survival_curve = [
            float(self._km_fitter.predict(t)) for t in timeline
        ]

        hazard_rate = 0.0
        if self._cox_fitter is not None and covariates is not None:
            try:
                hazard_values = self._cox_fitter.predict_partial_hazard(covariates)
                hazard_rate = float(hazard_values.mean())
            except Exception as exc:
                logger.error("cox_prediction_error", error=str(exc))

        result: dict[str, Any] = {
            "waste_probability": np.clip(waste_probability, 0.0, 1.0),
            "survival_at_t": survival_at_t,
            "survival_curve": survival_curve,
            "hazard_rate": max(hazard_rate, 0.0),
            "days_ahead": days_ahead,
        }

        logger.info(
            "waste_prediction_complete",
            days_ahead=days_ahead,
            waste_probability=round(waste_probability, 4),
        )
        return result

    def _fallback_prediction(self, days_ahead: int) -> dict[str, Any]:
        """Exponential decay fallback when model not fitted (I-7)."""
        decay_rate = 0.05
        survival = float(np.exp(-decay_rate * days_ahead))
        timeline = np.arange(0, days_ahead + 1)
        survival_curve = [float(np.exp(-decay_rate * t)) for t in timeline]

        return {
            "waste_probability": np.clip(1.0 - survival, 0.0, 1.0),
            "survival_at_t": survival,
            "survival_curve": survival_curve,
            "hazard_rate": decay_rate,
            "days_ahead": days_ahead,
        }
