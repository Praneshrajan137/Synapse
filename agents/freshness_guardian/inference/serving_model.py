"""Serving adapter for the Freshness Guardian (ADR-043, survival paradigm).

Training fits a Weibull-AFT survival model (lifelines). Serving must predict shelf
life *fast* and without the lifelines runtime, so we persist the fitted AFT
parameters — the shape ``rho`` and the log-scale linear predictor
(``intercept`` + per-covariate ``coeffs``) — and reconstruct the survival function
in pure numpy:

    scale  = exp(intercept + Σ coeffs·x)      (accelerated-failure-time scale)
    S(t|x) = exp(-(t/scale)^rho)              (Weibull survival)

Confidence is the **survival-CI width** (SURVIVAL_CI_WIDTH): the relative spread of
the 10th–90th survival-time percentiles around the median — a wide interval (high
uncertainty) lowers confidence, a tight one raises it. Never a constant. Pure numpy
(no torch/lifelines), so serving + the C42 probe run on any runner.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

_LN2 = math.log(2.0)


@dataclass(frozen=True)
class ServingPrediction:
    """Numpy-reconstructed shelf-life prediction (mirrors ShelfLifePrediction)."""

    days_to_expiry: float
    quality_score: float
    survival_probability: float
    median_remaining_life_days: float
    hazard_rate: float


class FreshnessServingModel:
    """Reconstruct a Weibull-AFT survival model from persisted params (ADR-043)."""

    def __init__(
        self, rho: float, intercept: float, coeffs: dict[str, float], *, version: str
    ) -> None:
        self.rho = max(float(rho), 1e-3)
        self.intercept = float(intercept)
        self.coeffs = {str(k): float(v) for k, v in coeffs.items()}
        self.version = version

    @property
    def is_real(self) -> bool:
        return self.rho > 0 and bool(self.coeffs)

    def _scale(self, covariates: dict[str, float]) -> float:
        lp = self.intercept + sum(self.coeffs.get(k, 0.0) * float(v) for k, v in covariates.items())
        return math.exp(min(max(lp, -50.0), 50.0))

    def _time_at_survival(self, scale: float, q: float) -> float:
        return scale * (-math.log(q)) ** (1.0 / self.rho)

    def predict(
        self,
        *,
        temperature_deviation_hours: float,
        humidity_deviation_pct: float,
        initial_shelf_life_days: float,
        is_cold_chain: bool,
        days_since_receipt: float,
    ) -> ServingPrediction:
        cov = {
            "temperature_deviation_hours": temperature_deviation_hours,
            "humidity_deviation_pct": humidity_deviation_pct,
            "initial_shelf_life_days": initial_shelf_life_days,
            "is_cold_chain": 1.0 if is_cold_chain else 0.0,
        }
        scale = self._scale(cov)
        median = scale * _LN2 ** (1.0 / self.rho)
        remaining = max(0.0, median - days_since_receipt)
        surv_prob = math.exp(-((max(days_since_receipt, 0.0) / scale) ** self.rho))
        time_ratio = 1.0 - (days_since_receipt / max(initial_shelf_life_days, 1.0))
        quality = min(max(surv_prob * 0.7 + max(time_ratio, 0.0) * 0.3, 0.0), 1.0)
        return ServingPrediction(
            days_to_expiry=remaining,
            quality_score=quality,
            survival_probability=surv_prob,
            median_remaining_life_days=remaining,
            hazard_rate=1.0 - surv_prob,
        )

    def confidence(self, covariates: dict[str, float]) -> float:
        """SURVIVAL_CI_WIDTH: 1/(1+rel) of the *absolute* 10–90 survival-time interval.

        The interval is normalised by the product's baseline shelf life (not the
        median — the *relative* Weibull width is scale-invariant, i.e. a disguised
        constant). A short predicted life (e.g. temperature-abused) has a tight
        absolute interval → a more precise estimate → higher confidence; a long-lived
        item has a wide interval → lower confidence. Varies with conditions via the
        AFT scale, never constant (ADR-040/043).
        """
        scale = self._scale(covariates)
        p10 = self._time_at_survival(scale, 0.9)  # early failure time
        p90 = self._time_at_survival(scale, 0.1)  # late failure time
        ref = max(float(covariates.get("initial_shelf_life_days", 7.0)), 1.0)
        rel = (p90 - p10) / ref
        return round(1.0 / (1.0 + rel), 4)


def build_freshness_model(artifact: Any, meta: dict[str, Any] | None = None) -> Any:
    """Model-builder for the $0 checkpoint path. ``artifact`` is the params dict."""
    meta = meta or {}
    data = artifact if isinstance(artifact, dict) else {}
    return FreshnessServingModel(
        rho=float(data.get("rho", 2.0)),
        intercept=float(data.get("intercept", 1.0)),
        coeffs=dict(data.get("coeffs", {})),
        version=str(meta.get("version") or "freshness_weibull_aft"),
    )


def load_serving_model(
    registry: Any, *, city: str = "bengaluru", base_name: str = "freshness_weibull_aft"
) -> FreshnessServingModel | None:
    """Resolve + wrap the fitted survival params; None if degraded (I-7)."""
    if registry is None:
        return None
    loaded = registry.load(base_name, city=city)
    if not getattr(loaded, "is_real", False) or loaded.model is None:
        logger.warning("freshness_serving_model_degraded", name=base_name, city=city)
        return None
    model = loaded.model
    if not getattr(model, "is_real", False):
        return None
    logger.info("freshness_serving_model_loaded", name=loaded.name, version=loaded.version)
    return model  # type: ignore[no-any-return]


__all__ = [
    "FreshnessServingModel",
    "ServingPrediction",
    "build_freshness_model",
    "load_serving_model",
]
