"""Serving adapter for the Inventory Sentinel (ADR-043, analytical paradigm).

The newsvendor optimum Q* is closed-form; what training produces is the
**split-conformal calibration** — the residual distribution whose quantile sets the
reorder interval half-width. Serving restores those residuals so the conformal
bounds are *calibrated* (real) rather than empty (degraded). Confidence is the
forecast residual-variance signal (RESIDUAL_VARIANCE). Pure numpy — no torch.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import structlog

logger = structlog.get_logger(__name__)


class InventoryServingModel:
    """Carry the fitted conformal calibration residuals for the newsvendor (ADR-043)."""

    def __init__(self, residuals: list[float], *, half_width: float, version: str) -> None:
        self.residuals = np.asarray(residuals, dtype=np.float64)
        self.half_width = float(half_width)
        self.version = version

    @property
    def is_real(self) -> bool:
        return self.residuals.size >= 10  # enough to calibrate a 90% interval


def build_inventory_model(artifact: Any, meta: dict[str, Any] | None = None) -> Any:
    """Model-builder for the $0 checkpoint path. ``artifact`` is the calibration dict."""
    meta = meta or {}
    data = artifact if isinstance(artifact, dict) else {}
    return InventoryServingModel(
        residuals=list(data.get("residuals", [])),
        half_width=float(data.get("half_width", 0.0)),
        version=str(meta.get("version") or "inventory_newsvendor"),
    )


def load_serving_model(
    registry: Any, *, city: str = "bengaluru", base_name: str = "inventory_newsvendor"
) -> InventoryServingModel | None:
    """Resolve + wrap the fitted calibration; None if degraded (I-7)."""
    if registry is None:
        return None
    loaded = registry.load(base_name, city=city)
    if not getattr(loaded, "is_real", False) or loaded.model is None:
        logger.warning("inventory_serving_model_degraded", name=base_name, city=city)
        return None
    model = loaded.model
    if not getattr(model, "is_real", False):
        return None
    logger.info("inventory_serving_model_loaded", name=loaded.name, version=loaded.version)
    return model  # type: ignore[no-any-return]


__all__ = ["InventoryServingModel", "build_inventory_model", "load_serving_model"]
