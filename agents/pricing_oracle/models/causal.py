"""
SYNAPSE Pricing Oracle -- Causal Price Elasticity Estimation via Double ML.

Uses EconML's DML with LassoCV for both treatment and outcome models.
Estimates causal effect of price changes on demand, controlling for confounders
(weather, events, competitor pricing).
"""
from __future__ import annotations

import math
from typing import Any

import numpy as np
import structlog

logger = structlog.get_logger(__name__)


class CausalElasticityEstimator:
    """
    Double Machine Learning estimator for causal price elasticity.

    Treatment (T): price multiplier
    Outcome (Y): demand quantity
    Controls (X): weather, events, competitor prices, time features
    Instruments (W): cost shocks (optional)

    Uses econml.dml.DML with sklearn LassoCV for nuisance models.
    """

    def __init__(
        self,
        cv_folds: int = 5,
        max_iter: int = 1000,
        random_state: int = 42,
    ) -> None:
        self._cv_folds = cv_folds
        self._max_iter = max_iter
        self._random_state = random_state
        self._model: Any = None
        self._is_fitted: bool = False

    def fit(
        self,
        outcome: np.ndarray,
        treatment: np.ndarray,
        controls: np.ndarray,
        instruments: np.ndarray | None = None,
    ) -> CausalElasticityEstimator:
        """
        Fit the Double ML model.

        Args:
            outcome: demand quantities (Y), shape (n_samples,)
            treatment: price multipliers (T), shape (n_samples,) or (n_samples, 1)
            controls: confounders (X), shape (n_samples, n_features)
            instruments: cost shocks (W), optional, shape (n_samples, n_instruments)
        """
        from econml.dml import DML
        from sklearn.linear_model import LassoCV

        treatment_model = LassoCV(cv=self._cv_folds, max_iter=self._max_iter)
        outcome_model = LassoCV(cv=self._cv_folds, max_iter=self._max_iter)

        self._model = DML(
            model_y=outcome_model,
            model_t=treatment_model,
            random_state=self._random_state,
            cv=self._cv_folds,
        )

        if treatment.ndim == 1:
            treatment = treatment.reshape(-1, 1)

        self._model.fit(
            Y=outcome,
            T=treatment,
            X=controls,
            W=instruments,
        )
        self._is_fitted = True

        logger.info(
            "causal_model_fitted",
            n_samples=len(outcome),
            n_controls=controls.shape[1],
            has_instruments=instruments is not None,
        )

        return self

    def estimate_elasticity(
        self,
        controls: np.ndarray,
    ) -> np.ndarray:
        """
        Estimate causal price elasticity for given control contexts.

        Returns array of elasticity estimates, shape (n_samples,) or (n_samples, 1).
        All estimates are validated to be finite (INV-PO-005).
        """
        if not self._is_fitted or self._model is None:
            raise RuntimeError("Model must be fitted before calling estimate_elasticity")

        effects: np.ndarray = self._model.effect(X=controls)

        if not np.all(np.isfinite(effects)):
            non_finite_count = int(np.sum(~np.isfinite(effects)))
            logger.warning(
                "non_finite_elasticity_detected",
                count=non_finite_count,
                action="replacing with zero",
            )
            effects = np.where(np.isfinite(effects), effects, 0.0)

        return effects

    def estimate_elasticity_with_confidence(
        self,
        controls: np.ndarray,
        alpha: float = 0.05,
    ) -> dict[str, np.ndarray]:
        """
        Estimate elasticity with confidence intervals.

        Returns dict with keys: 'effect', 'lower', 'upper'.
        """
        if not self._is_fitted or self._model is None:
            raise RuntimeError("Model must be fitted before calling estimate_elasticity")

        effect = self._model.effect(X=controls)
        inference = self._model.effect_inference(X=controls)
        ci = inference.conf_int(alpha=alpha)

        lower = ci[0] if isinstance(ci, tuple) else ci[:, 0]
        upper = ci[1] if isinstance(ci, tuple) else ci[:, 1]

        for arr_name, arr in [("effect", effect), ("lower", lower), ("upper", upper)]:
            if not np.all(np.isfinite(arr)):
                logger.warning("non_finite_in_ci", field=arr_name)

        return {
            "effect": np.where(np.isfinite(effect), effect, 0.0),
            "lower": np.where(np.isfinite(lower), lower, 0.0),
            "upper": np.where(np.isfinite(upper), upper, 0.0),
        }

    @property
    def is_fitted(self) -> bool:
        return self._is_fitted

    @staticmethod
    def validate_elasticity(value: float) -> bool:
        """Validate a single elasticity estimate per INV-PO-005."""
        return math.isfinite(value)
