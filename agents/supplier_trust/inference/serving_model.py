"""Serving adapter: a torch-free conjugate posterior over the SVI-learned prior.

Training (``training/train.py``, Pyro/CI) fits the *population* lead-time prior via
SVI: a Normal posterior over the log-mean ``mu`` and a point estimate of the
log-scale ``sigma``. Serving must score one supplier per request *fast* and without
re-running SVI — so this module restores that prior and does the exact
**conjugate Normal–Normal update** with the supplier's own log-lead-times (a known
log-scale ``sigma``). That update is closed-form and pure-numpy, so the entire
serving path runs without torch/pyro (the C42 probe + the INV-ST tests run on any
runner); only the one-off prior fit needs the ML stack (ADR-043).

The fitted prior travels in the checkpoint sidecar as three floats
(``prior_mu``, ``prior_mu_scale``, ``sigma``) — the Bayesian analogue of
demand_prophet's conformal calibrator state.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import structlog

from agents.supplier_trust.models.posterior import LeadTimePosterior

logger = structlog.get_logger(__name__)

_Z10 = 1.2815515594  # standard-normal 0.90 quantile (for the 80% central interval)


class SupplierServingModel:
    """Restore the SVI-fitted lead-time prior; score suppliers by conjugate update."""

    def __init__(
        self, prior_mu: float, prior_mu_scale: float, sigma: float, *, version: str
    ) -> None:
        self.prior_mu = float(prior_mu)
        self.prior_mu_scale = max(float(prior_mu_scale), 1e-6)
        self.sigma = max(float(sigma), 1e-6)
        self.version = version

    @property
    def is_real(self) -> bool:
        return self.prior_mu_scale > 0 and self.sigma > 0

    def posterior(self, lead_times_days: np.ndarray) -> LeadTimePosterior:
        """Conjugate Normal–Normal posterior predictive for one supplier.

        ``y_i = log(lead_time_i) ~ Normal(mu, sigma)`` with a Normal prior on ``mu``
        and known ``sigma``. The posterior on ``mu`` is closed-form; the predictive
        lead time is LogNormal with log-scale ``sqrt(sigma^2 + post_scale^2)``.
        """
        y = np.log(np.clip(np.asarray(lead_times_days, dtype=np.float64), 1e-3, None))
        n = int(y.size)
        prior_var = self.prior_mu_scale**2
        obs_var = self.sigma**2
        if n > 0:
            post_var = 1.0 / (1.0 / prior_var + n / obs_var)
            post_mu = post_var * (self.prior_mu / prior_var + float(y.sum()) / obs_var)
        else:  # no observations → fall back to the prior (a new vendor)
            post_var, post_mu = prior_var, self.prior_mu
        pred_logstd = math.sqrt(obs_var + post_var)

        mean_days = math.exp(post_mu + 0.5 * pred_logstd**2)
        var_days = (math.exp(pred_logstd**2) - 1.0) * math.exp(2 * post_mu + pred_logstd**2)
        return LeadTimePosterior(
            mean_days=round(mean_days, 4),
            std_days=round(math.sqrt(max(var_days, 0.0)), 4),
            p10_days=round(math.exp(post_mu - _Z10 * pred_logstd), 4),
            p90_days=round(math.exp(post_mu + _Z10 * pred_logstd), 4),
        )

    def predict(self, observed: Any) -> LeadTimePosterior:
        """Pipeline-facing alias mirroring BayesianLeadTimeModel.predict (no SVI)."""
        arr = (
            observed.detach().cpu().numpy() if hasattr(observed, "detach") else np.asarray(observed)
        )
        return self.posterior(arr)

    @property
    def is_fitted(self) -> bool:  # parity with the pyro model's interface
        return True


def build_supplier_model(artifact: Any, meta: dict[str, Any] | None = None) -> Any:
    """Model-builder injected into ModelRegistry for the $0 checkpoint path.

    ``artifact`` is the prior dict written by ``train.py`` (JSON in
    ``supplier_bayesian.pt``). Returns a :class:`SupplierServingModel`.
    """
    meta = meta or {}
    prior = artifact if isinstance(artifact, dict) else {}
    return SupplierServingModel(
        prior_mu=float(prior.get("prior_mu", 2.0)),
        prior_mu_scale=float(prior.get("prior_mu_scale", 0.5)),
        sigma=float(prior.get("sigma", 0.5)),
        version=str(meta.get("version") or "supplier_bayesian"),
    )


def load_serving_model(
    registry: Any, *, city: str = "bengaluru", base_name: str = "supplier_bayesian"
) -> SupplierServingModel | None:
    """Resolve + wrap the fitted prior from the registry; None if degraded (I-7)."""
    if registry is None:
        return None
    loaded = registry.load(base_name, city=city)
    if not getattr(loaded, "is_real", False) or loaded.model is None:
        logger.warning("supplier_serving_model_degraded", name=base_name, city=city)
        return None
    model = loaded.model
    if not getattr(model, "is_real", False):
        return None
    logger.info("supplier_serving_model_loaded", name=loaded.name, version=loaded.version)
    return model  # type: ignore[no-any-return]


__all__ = ["SupplierServingModel", "build_supplier_model", "load_serving_model"]
