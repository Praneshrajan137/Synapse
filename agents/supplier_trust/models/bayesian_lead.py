"""
SYNAPSE Supplier Trust -- Bayesian Lead-Time Estimation via Pyro.

LogNormal distribution with informative priors.  Uses pyro.infer.SVI with
AutoNormal guide.  Returns FULL POSTERIOR: mean_days, std_days, p10_days, p90_days.
"""
from __future__ import annotations

from typing import Any

import pyro
import pyro.distributions as dist
import structlog
import torch
from pyro.infer import SVI, Trace_ELBO
from pyro.infer.autoguide import AutoNormal
from pyro.optim import Adam
from torch import Tensor

logger = structlog.get_logger(__name__)


class LeadTimePosterior:
    """Immutable container for lead-time posterior summary."""

    __slots__ = ("mean_days", "std_days", "p10_days", "p90_days")

    def __init__(self, mean_days: float, std_days: float, p10_days: float, p90_days: float) -> None:
        self.mean_days = mean_days
        self.std_days = std_days
        self.p10_days = p10_days
        self.p90_days = p90_days

    def to_dict(self) -> dict[str, float]:
        return {
            "mean_days": self.mean_days,
            "std_days": self.std_days,
            "p10_days": self.p10_days,
            "p90_days": self.p90_days,
        }


class BayesianLeadTimeModel:
    """Bayesian lead-time model using Pyro SVI with LogNormal likelihood.

    Priors:
      mu    ~ Normal(prior_mu, 1.0)
      sigma ~ LogNormal(prior_sigma_loc, 0.5)

    Likelihood:
      observed_days ~ LogNormal(mu, sigma)
    """

    def __init__(
        self,
        prior_mu: float = 2.0,
        prior_sigma: float = 0.5,
        learning_rate: float = 0.01,
        num_steps: int = 1000,
        num_samples: int = 500,
    ) -> None:
        self._prior_mu = prior_mu
        self._prior_sigma = prior_sigma
        self._lr = learning_rate
        self._num_steps = num_steps
        self._num_samples = num_samples
        self._guide: AutoNormal | None = None

    def _model(self, obs: Tensor | None = None) -> Tensor:
        mu = pyro.sample("mu", dist.Normal(self._prior_mu, 1.0))
        sigma = pyro.sample("sigma", dist.LogNormal(self._prior_sigma, 0.5))
        with pyro.plate("data", obs.shape[0] if obs is not None else 1):
            return pyro.sample("lead_time", dist.LogNormal(mu, sigma), obs=obs)

    def fit(self, observed_days: Tensor) -> list[float]:
        """Fit the model to observed lead-time data via SVI.

        Args:
            observed_days: 1D tensor of observed lead times (days).
                           Must contain positive values.

        Returns:
            List of ELBO losses per step for diagnostics.
        """
        if observed_days.ndim != 1 or observed_days.shape[0] == 0:
            raise ValueError("PRE-ST-002: observed_days must be non-empty 1D tensor")
        if (observed_days <= 0).any():
            raise ValueError("Lead times must be positive for LogNormal likelihood")

        pyro.clear_param_store()
        self._guide = AutoNormal(self._model)
        optimizer = Adam({"lr": self._lr})
        svi = SVI(self._model, self._guide, optimizer, loss=Trace_ELBO())

        losses: list[float] = []
        for step in range(self._num_steps):
            loss = svi.step(observed_days)
            losses.append(loss)
            if step % 200 == 0:
                logger.debug("svi_step", step=step, loss=round(loss, 4))

        return losses

    def posterior(self) -> LeadTimePosterior:
        """Sample from the fitted posterior and return summary statistics.

        Returns:
            LeadTimePosterior with mean_days, std_days, p10_days, p90_days.

        Raises:
            RuntimeError: If fit() has not been called.
        """
        if self._guide is None:
            raise RuntimeError("Call fit() before posterior()")

        samples: list[Tensor] = []
        for _ in range(self._num_samples):
            guide_trace = self._guide()  # noqa: F841
            mu = pyro.param("AutoNormal.locs.mu").detach()
            sigma = torch.exp(pyro.param("AutoNormal.scales.sigma").detach())
            lead_sample = dist.LogNormal(mu, sigma).sample()
            samples.append(lead_sample)

        all_samples = torch.stack(samples)
        mean_days = float(all_samples.mean())
        std_days = float(all_samples.std())
        p10_days = float(all_samples.quantile(0.1))
        p90_days = float(all_samples.quantile(0.9))

        if std_days <= 0:
            logger.warning("degenerate_posterior", std_days=std_days)
            std_days = 1e-6

        return LeadTimePosterior(
            mean_days=round(mean_days, 4),
            std_days=round(std_days, 4),
            p10_days=round(p10_days, 4),
            p90_days=round(p90_days, 4),
        )

    def predict(self, observed_days: Tensor) -> LeadTimePosterior:
        """Convenience: fit + posterior in one call."""
        self.fit(observed_days)
        return self.posterior()
