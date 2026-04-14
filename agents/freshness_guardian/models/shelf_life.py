"""
SYNAPSE Freshness Guardian — Shelf Life Survival Model.
Uses Weibull AFT (Accelerated Failure Time) from lifelines for
shelf life prediction based on storage conditions.

Survival analysis is the correct framework because:
1. Shelf life is a time-to-event (expiry) problem
2. We have right-censored data (items sold before expiry)
3. Covariates (temperature, humidity) affect the hazard rate
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
import structlog
from lifelines import WeibullAFTFitter

logger = structlog.get_logger(__name__)


@dataclass
class ShelfLifePrediction:
    """Shelf life prediction result."""

    sku_id: str
    store_id: str
    days_to_expiry: float
    quality_score: float
    survival_probability: float
    median_remaining_life_days: float
    hazard_rate: float


class ShelfLifeModel:
    """Weibull AFT model for perishable shelf life prediction.

    Covariates:
    - temperature_deviation_hours: cumulative hours above safe temp
    - humidity_deviation_pct: avg humidity deviation from optimal
    - initial_shelf_life_days: product-specific baseline
    - is_cold_chain: cold_chain vs ambient (binary)
    """

    def __init__(self) -> None:
        self.model = WeibullAFTFitter()
        self.fitted = False

    def fit(self, training_data: pd.DataFrame) -> None:
        """Fit Weibull AFT on historical expiry data.

        Args:
            training_data: DataFrame with columns:
                - duration: observed shelf life (days)
                - event: 1 if expired, 0 if sold/consumed (censored)
                - temperature_deviation_hours
                - humidity_deviation_pct
                - initial_shelf_life_days
                - is_cold_chain
        """
        self.model.fit(
            training_data,
            duration_col="duration",
            event_col="event",
            formula="temperature_deviation_hours + humidity_deviation_pct + "
            "initial_shelf_life_days + is_cold_chain",
        )
        self.fitted = True
        logger.info("shelf_life_model_fitted", aic=self.model.AIC_)

    def predict(
        self,
        sku_id: str,
        store_id: str,
        temperature_deviation_hours: float,
        humidity_deviation_pct: float,
        initial_shelf_life_days: float,
        is_cold_chain: bool,
        days_since_receipt: float,
    ) -> ShelfLifePrediction:
        """Predict remaining shelf life and quality score."""
        if not self.fitted:
            return self._fallback_predict(
                sku_id,
                store_id,
                temperature_deviation_hours,
                initial_shelf_life_days,
                days_since_receipt,
            )

        covariates = pd.DataFrame(
            [
                {
                    "temperature_deviation_hours": temperature_deviation_hours,
                    "humidity_deviation_pct": humidity_deviation_pct,
                    "initial_shelf_life_days": initial_shelf_life_days,
                    "is_cold_chain": 1.0 if is_cold_chain else 0.0,
                }
            ]
        )

        surv_prob = float(
            self.model.predict_survival_function(covariates, times=[days_since_receipt]).values[0][
                0
            ]
        )

        median_life = float(self.model.predict_median(covariates).values[0])
        remaining = max(0.0, median_life - days_since_receipt)

        time_ratio = 1.0 - (days_since_receipt / max(initial_shelf_life_days, 1))
        quality = float(np.clip(surv_prob * 0.7 + max(time_ratio, 0.0) * 0.3, 0, 1))

        hazard = 1.0 - surv_prob if surv_prob > 0 else 1.0

        return ShelfLifePrediction(
            sku_id=sku_id,
            store_id=store_id,
            days_to_expiry=remaining,
            quality_score=quality,
            survival_probability=surv_prob,
            median_remaining_life_days=remaining,
            hazard_rate=hazard,
        )

    def _fallback_predict(
        self,
        sku_id: str,
        store_id: str,
        temperature_deviation_hours: float,
        initial_shelf_life_days: float,
        days_since_receipt: float,
    ) -> ShelfLifePrediction:
        """Graceful degradation (I-7): simple exponential decay when model not fitted."""
        decay_rate = 0.05 * (1 + temperature_deviation_hours / 24)
        remaining = max(0.0, initial_shelf_life_days - days_since_receipt)
        quality = float(np.clip(np.exp(-decay_rate * days_since_receipt), 0, 1))
        return ShelfLifePrediction(
            sku_id=sku_id,
            store_id=store_id,
            days_to_expiry=remaining,
            quality_score=quality,
            survival_probability=quality,
            median_remaining_life_days=remaining,
            hazard_rate=decay_rate,
        )

    def generate_synthetic_training_data(
        self, n_samples: int = 5000, seed: int = 42
    ) -> pd.DataFrame:
        """Generate synthetic training data for development."""
        rng = np.random.default_rng(seed)

        data = {
            "temperature_deviation_hours": rng.exponential(2.0, n_samples),
            "humidity_deviation_pct": rng.normal(5.0, 3.0, n_samples).clip(0),
            "initial_shelf_life_days": rng.choice([3.0, 5.0, 7.0, 14.0, 30.0], n_samples).astype(
                float
            ),
            "is_cold_chain": rng.binomial(1, 0.4, n_samples).astype(float),
        }

        base_scale = data["initial_shelf_life_days"] * 0.8
        temp_effect = np.exp(-0.1 * data["temperature_deviation_hours"])
        humidity_effect = np.exp(-0.02 * data["humidity_deviation_pct"])
        cold_chain_effect = np.where(data["is_cold_chain"] == 1, 1.3, 1.0)

        scale = base_scale * temp_effect * humidity_effect * cold_chain_effect
        shape = 2.5

        duration = rng.weibull(shape, n_samples) * scale
        duration = np.clip(duration, 0.5, 60)

        event = rng.binomial(1, 0.7, n_samples)

        data["duration"] = duration
        data["event"] = event

        return pd.DataFrame(data)
