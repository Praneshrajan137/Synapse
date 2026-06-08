"""Serving adapter for the Sustainability Agent (ADR-043, predictive paradigm).

Training fits a Kaplan-Meier waste-survival curve (lifelines). Serving must run
without the lifelines runtime, so we persist the fitted survival curve as
(timeline, survival) arrays and interpolate it in pure numpy. The pipeline's
confidence is the **predictive entropy** of the waste probability
(PREDICTIVE_ENTROPY): a probability near 0 or 1 is a confident call, near 0.5 is
uncertain — tied to genuine model output, never a constant.

Pure numpy (no lifelines), so serving + the C42 probe run on any runner.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import structlog

logger = structlog.get_logger(__name__)


class WasteServingModel:
    """Reconstruct a fitted KM waste-survival curve from persisted arrays (ADR-043)."""

    def __init__(self, timeline: list[float], survival: list[float], *, version: str) -> None:
        self._t = np.asarray(timeline, dtype=np.float64)
        self._s = np.asarray(survival, dtype=np.float64)
        self.version = version

    @property
    def is_real(self) -> bool:
        return self._t.size >= 2 and self._s.size == self._t.size

    def predict_waste_probability(
        self, days_ahead: int, covariates: Any = None
    ) -> dict[str, Any]:
        """Interpolate the persisted survival curve at ``days_ahead`` (numpy)."""
        surv_at_t = float(np.interp(days_ahead, self._t, self._s, left=1.0, right=self._s[-1]))
        waste_probability = float(np.clip(1.0 - surv_at_t, 0.0, 1.0))
        timeline = np.arange(0, days_ahead + 1)
        survival_curve = [
            float(np.interp(t, self._t, self._s, left=1.0, right=self._s[-1])) for t in timeline
        ]
        # Discrete hazard at the horizon from the survival drop.
        prev = float(
            np.interp(max(days_ahead - 1, 0), self._t, self._s, left=1.0, right=self._s[-1])
        )
        hazard = max((prev - surv_at_t) / max(prev, 1e-9), 0.0)
        return {
            "waste_probability": waste_probability,
            "survival_at_t": surv_at_t,
            "survival_curve": survival_curve,
            "hazard_rate": hazard,
            "days_ahead": days_ahead,
        }


def build_sustainability_model(artifact: Any, meta: dict[str, Any] | None = None) -> Any:
    """Model-builder for the $0 checkpoint path. ``artifact`` is the curve dict."""
    meta = meta or {}
    data = artifact if isinstance(artifact, dict) else {}
    return WasteServingModel(
        timeline=list(data.get("timeline", [])),
        survival=list(data.get("survival", [])),
        version=str(meta.get("version") or "sustainability_waste_km"),
    )


def load_serving_model(
    registry: Any, *, city: str = "bengaluru", base_name: str = "sustainability_waste_km"
) -> WasteServingModel | None:
    """Resolve + wrap the fitted survival curve; None if degraded (I-7)."""
    if registry is None:
        return None
    loaded = registry.load(base_name, city=city)
    if not getattr(loaded, "is_real", False) or loaded.model is None:
        logger.warning("sustainability_serving_model_degraded", name=base_name, city=city)
        return None
    model = loaded.model
    if not getattr(model, "is_real", False):
        return None
    logger.info("sustainability_serving_model_loaded", name=loaded.name, version=loaded.version)
    return model  # type: ignore[no-any-return]


__all__ = ["WasteServingModel", "build_sustainability_model", "load_serving_model"]
