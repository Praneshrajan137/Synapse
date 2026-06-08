"""Serving adapter: bridge the trained optimality-gap calibration to the pipeline.

The CVRPTW solver lives in the pipeline; what training produces is a *calibration*
(the empirical distribution of the solver's LB/achieved optimality ratio). This
module is the anti-corruption seam (ADR-041/043): :class:`RoutingServingModel`
owns the calibration loaded from the $0 checkpoint and exposes
``calibrated_confidence(lb, achieved)`` — the pipeline maps a live route's
optimality gap to a *calibrated* confidence (its percentile in the training
distribution) instead of an ad-hoc formula.

Pure-stdlib/numpy — no torch — so the C39 AST gate and the C42 runtime probe run
on any runner. When no checkpoint is available, :func:`load_serving_model` returns
``None`` and the pipeline takes its honest greedy/raw I-7 fallback.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import structlog

logger = structlog.get_logger(__name__)


class RoutingServingModel:
    """Wrap the trained optimality-gap calibration behind a confidence map (ADR-043)."""

    def __init__(self, calibration: dict[str, Any], *, version: str) -> None:
        self.version = version
        ratios = calibration.get("ratios") or []
        self._ratios = np.asarray(sorted(float(r) for r in ratios), dtype=np.float64)
        self.q_lo = float(calibration.get("q_lo", 0.0))
        self.q_med = float(calibration.get("q_med", 0.0))
        self.q_hi = float(calibration.get("q_hi", 1.0))

    @property
    def is_real(self) -> bool:
        return self._ratios.size > 0

    def calibrated_confidence(self, lb: float, achieved: float) -> float:
        """Confidence in (0.5, 0.99) from the route's calibrated optimality percentile.

        ``ratio = LB / achieved`` ∈ (0, 1]; its empirical CDF position in the
        training distribution is how good this solution is *relative to what the
        solver typically achieves* — a calibrated, monotone, never-constant signal
        (ADR-042 C41). A route at the calibrated median maps to ~0.745.
        """
        ratio = min(float(lb) / max(float(achieved), 1e-6), 1.0)
        if self._ratios.size == 0:
            pct = ratio
        else:
            pct = float(np.searchsorted(self._ratios, ratio, side="right")) / self._ratios.size
        return round(float(np.clip(0.5 + 0.49 * pct, 0.5, 0.99)), 4)


def build_routing_model(artifact: Any, meta: dict[str, Any] | None = None) -> Any:
    """Model-builder injected into :class:`ModelRegistry` for the $0 checkpoint path.

    ``artifact`` is the calibration dict written by ``train.py`` (JSON-serialised
    into ``routing_cvrptw.pt`` by ``save_checkpoint``). ``meta`` is the serving
    sidecar. Returns a :class:`RoutingServingModel`, or raises (the registry
    catches → degrades, I-7).
    """
    meta = meta or {}
    calibration = artifact if isinstance(artifact, dict) else {}
    version = str(meta.get("version") or "routing_cvrptw")
    return RoutingServingModel(calibration, version=version)


def load_serving_model(
    registry: Any, *, city: str = "bengaluru", base_name: str = "routing_cvrptw"
) -> RoutingServingModel | None:
    """Resolve + wrap the trained calibration from the registry; None if degraded."""
    if registry is None:
        return None
    loaded = registry.load(base_name, city=city)
    if not getattr(loaded, "is_real", False) or loaded.model is None:
        logger.warning("routing_serving_model_degraded", name=base_name, city=city)
        return None
    model = loaded.model
    if not getattr(model, "is_real", False):
        return None
    logger.info("routing_serving_model_loaded", name=loaded.name, version=loaded.version)
    return model  # type: ignore[no-any-return]


__all__ = ["RoutingServingModel", "build_routing_model", "load_serving_model"]
