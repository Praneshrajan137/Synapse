"""Serving adapter for the Pricing Oracle (ADR-043, RL paradigm).

Two artifacts travel together: the trained MADDPG **actor** (a torch ``state_dict``
in ``pricing_maddpg.pt``) and a torch-free **linear elasticity model** (the causal
estimator, persisted in the sidecar). :class:`PricingServingModel` exposes the
``select_actions`` interface the pipeline calls on its model, and embeds the
:class:`LinearElasticityModel`, which satisfies the pipeline's causal-estimator
interface (``is_fitted`` + ``estimate_elasticity``) — so a fully-loaded pricing
serve is non-degraded on *both* the action and the elasticity.

The elasticity model is pure numpy (locally testable + the C42 confidence proof);
only the actor needs torch, imported lazily so this module loads on any runner.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import structlog

logger = structlog.get_logger(__name__)

CATEGORIES = ["essential", "snack", "beverage", "dairy", "produce"]


class LinearElasticityModel:
    """Torch-free per-context causal elasticity: ``elasticity = controls·w + b``.

    Fitted by OLS on observational pricing data (``train.py``). Satisfies the
    pipeline's causal-estimator interface so the served elasticity is real and
    *varies per SKU* (drives the honest ELASTICITY_STRENGTH confidence), never a
    heuristic constant. Estimates are clamped finite (INV-PO-005).
    """

    def __init__(self, weights: list[float], bias: float) -> None:
        self._w = np.asarray(weights, dtype=np.float64)
        self._b = float(bias)

    @property
    def is_fitted(self) -> bool:
        return self._w.size > 0

    def estimate_elasticity(self, controls: np.ndarray) -> np.ndarray:
        x = np.atleast_2d(np.asarray(controls, dtype=np.float64))
        f = self._w.size
        if x.shape[1] != f:  # pad/trim controls to the fitted feature width
            x = np.array([np.resize(row, f) for row in x])
        eff = x @ self._w + self._b
        eff = np.where(np.isfinite(eff), eff, 0.0)
        # Elasticities are negative (demand falls as price rises); keep them so.
        return np.clip(eff, -5.0, -0.01)


class PricingServingModel:
    """Wrap the trained MADDPG actor behind ``select_actions`` (ADR-043)."""

    def __init__(
        self, torch_model: Any, elasticity: LinearElasticityModel, *, version: str, obs_dim: int
    ) -> None:
        self._model = torch_model
        self.elasticity = elasticity
        self.version = version
        self.obs_dim = obs_dim

    @property
    def is_real(self) -> bool:
        return self._model is not None and self.elasticity.is_fitted

    def select_actions(self, observations: dict[str, Any]) -> dict[str, Any]:
        """Delegate to the trained actor's deterministic policy (essential cap held)."""
        return self._model.select_actions(observations)  # type: ignore[no-any-return]


def build_pricing_model(artifact: Any, meta: dict[str, Any] | None = None) -> Any:
    """Model-builder injected into ModelRegistry for the $0 checkpoint path.

    ``artifact`` is the actor ``state_dict`` (from ``pricing_maddpg.pt``); ``meta``
    is the sidecar carrying the architecture dims + the fitted elasticity weights.
    Builds the actor (torch, lazy) + the numpy elasticity model. Raises on mismatch
    (the registry catches → degrades, I-7).
    """
    from agents.pricing_oracle.models.maddpg import PricingMADDPG  # noqa: PLC0415

    meta = meta or {}
    arch = dict(meta.get("arch") or {})
    elast = dict(meta.get("elasticity") or {})
    obs_dim = int(arch.get("obs_dim", 24))
    model = PricingMADDPG(
        num_agents=int(arch.get("num_agents", 5)),
        obs_dim=obs_dim,
        action_dim=int(arch.get("action_dim", 1)),
    )
    state = artifact
    if isinstance(artifact, dict) and "state_dict" in artifact:
        state = artifact["state_dict"]
    model.load_state_dict(state)
    model.eval()
    elasticity = LinearElasticityModel(
        weights=list(elast.get("weights", [])), bias=float(elast.get("bias", -1.0))
    )
    return PricingServingModel(
        model, elasticity, version=str(meta.get("version") or "pricing_maddpg"), obs_dim=obs_dim
    )


def load_serving_model(
    registry: Any, *, city: str = "bengaluru", base_name: str = "pricing_maddpg"
) -> PricingServingModel | None:
    """Resolve + wrap the trained actor + elasticity model; None if degraded (I-7)."""
    if registry is None:
        return None
    loaded = registry.load(base_name, city=city)
    if not getattr(loaded, "is_real", False) or loaded.model is None:
        logger.warning("pricing_serving_model_degraded", name=base_name, city=city)
        return None
    model = loaded.model
    if not getattr(model, "is_real", False):
        return None
    logger.info("pricing_serving_model_loaded", name=loaded.name, version=loaded.version)
    return model  # type: ignore[no-any-return]


__all__ = [
    "LinearElasticityModel",
    "PricingServingModel",
    "build_pricing_model",
    "load_serving_model",
]
