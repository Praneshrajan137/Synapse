"""SYNAPSE Supplier Trust -- Bayesian training (ADR-042/043, Bayesian paradigm).

Fits the *population* lead-time prior with a real Pyro SVI loop (C37: genuine
``svi.step()`` gradient steps, ELBO falls), then persists a compact, torch-free
prior so serving scores each supplier by a closed-form conjugate update instead of
re-running SVI per request (ADR-043). Substance is proven by **held-out
posterior-interval coverage** (C40, the Bayesian analogue of conformal coverage).

The serving prior is three floats:
  * ``prior_mu``       — population log-mean of lead time (from the SVI posterior).
  * ``prior_mu_scale`` — between-supplier spread of log-means (the genuine prior
                         uncertainty for a *new* supplier's mean).
  * ``sigma``          — within-supplier log-scale (the per-delivery noise).

Run::

    python -m agents.supplier_trust.training.train [--smoke]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import structlog
from synapse_common.training_contract import TrainResult, save_checkpoint

logger = structlog.get_logger(__name__)

ROOT = Path(__file__).resolve().parents[3]
CHECKPOINT_DIR = ROOT / "artifacts" / "checkpoints"
SERVING_NAME = "supplier_bayesian"


def _generate_panel(rng: np.random.Generator, n_suppliers: int, n_obs: int) -> list[np.ndarray]:
    """Seeded per-supplier lead-time panels (days), log-normally distributed.

    Each supplier has its own true log-mean (between-supplier spread) and shares a
    within-supplier log-scale — the structure the prior + conjugate update model.
    """
    true_mu = rng.normal(2.0, 0.35, size=n_suppliers)  # log-space supplier means
    within_sigma = 0.4
    panels: list[np.ndarray] = []
    for i in range(n_suppliers):
        logs = rng.normal(true_mu[i], within_sigma, size=n_obs)
        panels.append(np.exp(logs))  # back to days, strictly positive
    return panels


def _svi_population_fit(pooled_days: np.ndarray, *, num_steps: int) -> tuple[list[float], float]:
    """Real Pyro SVI loop over the pooled log-lead-times (C37). Returns (ELBO losses, mu_loc).

    The loop is the substance the training-truth gate checks; the resulting mu
    posterior locates the population log-mean. Pyro is imported lazily so this
    module imports torch-free (the gate AST-walks it without the ML stack).
    """
    import torch  # noqa: PLC0415

    from agents.supplier_trust.models.bayesian_lead import BayesianLeadTimeModel  # noqa: PLC0415

    model = BayesianLeadTimeModel(prior_mu=2.0, prior_sigma=0.5, num_steps=num_steps)
    losses = model.fit(torch.tensor(pooled_days.tolist(), dtype=torch.float32))
    try:
        mu_loc = float(model._guide.median()["mu"])  # type: ignore[union-attr]
    except Exception as exc:  # noqa: BLE001 — fall back to the empirical mean (I-7)
        logger.warning("svi_median_unavailable", error=str(exc))
        mu_loc = float(np.mean(np.log(np.clip(pooled_days, 1e-3, None))))
    return [float(x) for x in losses], mu_loc


def train(config: object | None = None, *, smoke: bool = False) -> TrainResult:
    """Fit the lead-time prior (SVI) + calibrate the conjugate serving posterior."""
    from agents.supplier_trust.inference.serving_model import SupplierServingModel  # noqa: PLC0415

    seed = 42
    rng = np.random.default_rng(seed)
    # Smoke uses a deliberately small panel for CI speed, but the held-out 80%
    # interval coverage (C40) is estimated over n_suppliers/2 × n_obs/2 points, so
    # too-small a panel makes the estimate noisy and biased low. 40×40 keeps the
    # SVI fit trivial (1600 pooled points) while giving a stable ~0.78 estimate.
    n_suppliers = 40 if smoke else 120
    n_obs = 40 if smoke else 60
    num_steps = 200 if smoke else 1000

    panels = _generate_panel(rng, n_suppliers, n_obs)
    pooled = np.concatenate(panels)

    losses, mu_loc = _svi_population_fit(pooled, num_steps=num_steps)

    # Empirical variance decomposition calibrates the conjugate serving prior:
    # between-supplier spread of log-means → prior scale; pooled within-supplier
    # residual std → the per-delivery log-noise sigma.
    log_means = np.array([float(np.mean(np.log(p))) for p in panels])
    prior_mu_scale = float(np.std(log_means)) or 0.1
    # Unbiased pooled within-supplier log-noise: each panel loses one degree of
    # freedom to its own sample mean, so divide the pooled residual SS by
    # (N_total − n_suppliers), not N. The old ddof=0 np.std estimate biased sigma
    # low (~0.39 vs true 0.40), narrowing the predictive interval and dragging
    # held-out coverage below the C40 floor.
    _resid_ss = sum(float(np.sum((np.log(p) - np.mean(np.log(p))) ** 2)) for p in panels)
    _resid_dof = max(sum(len(p) for p in panels) - len(panels), 1)
    sigma = float(np.sqrt(_resid_ss / _resid_dof)) or 0.1

    prior = {
        "prior_mu": round(float(mu_loc), 6),
        "prior_mu_scale": round(prior_mu_scale, 6),
        "sigma": round(sigma, 6),
    }

    # Held-out posterior-interval coverage (C40): for each test supplier, split its
    # deliveries, build the conjugate predictive from the first half, and measure
    # the fraction of held-out deliveries inside the 80% credible interval.
    serving = SupplierServingModel(version="cal", **prior)
    test_panels = panels[len(panels) // 2 :]
    inside, total = 0, 0
    for p in test_panels:
        half = len(p) // 2
        post = serving.posterior(p[:half])
        for obs in p[half:]:
            total += 1
            if post.p10_days <= obs <= post.p90_days:
                inside += 1
    posterior_coverage = (inside / total) if total else 0.0

    CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
    ckpt_path = CHECKPOINT_DIR / f"{SERVING_NAME}.pt"
    sha = save_checkpoint(prior, ckpt_path)
    sidecar = {"version": f"{'smoke' if smoke else 'full'}_{sha}", "smoke": smoke}
    (CHECKPOINT_DIR / f"{SERVING_NAME}.serving.json").write_text(
        json.dumps(sidecar, sort_keys=True, separators=(",", ":")), encoding="utf-8"
    )

    start_loss = losses[0] if losses else float("nan")
    end_loss = losses[-1] if losses else float("nan")
    result = TrainResult(
        agent="supplier_trust",
        gradient_steps=len(losses),
        start_loss=start_loss,
        end_loss=end_loss,
        epochs=1,
        seed=seed,
        smoke=smoke,
        checkpoint_path=ckpt_path,
        checkpoint_sha=sha,
        metrics={"posterior_coverage": posterior_coverage, "sigma": sigma},
    )
    logger.info("supplier_training_complete", sha=sha, **result.to_dict()["metrics"])
    result.assert_learned()
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Train Supplier Trust Bayesian lead-time prior")
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args()
    train(smoke=args.smoke)


if __name__ == "__main__":
    sys.exit(main())  # type: ignore[func-returns-value]
