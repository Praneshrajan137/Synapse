"""SYNAPSE Pricing Oracle -- training (ADR-042/043, RL paradigm).

Two real artifacts:

  1. **Causal elasticity** — a linear elasticity model ``elasticity = controls·w + b``
     fit by OLS on seeded observational pricing data (torch-free; persisted in the
     sidecar). The pipeline's causal estimator at serving.
  2. **MADDPG actor policy** — the per-category actors are trained by **deterministic
     policy gradient on a differentiable semi-log profit model**
     ``profit(m) = (m − cost)·exp(elasticity·(m−1))``. Because the reward is
     differentiable in the multiplier, the environment *is* the critic: real
     ``loss.backward()/optimizer.step()`` ascend expected profit toward the interior
     optimum ``m* = cost − 1/elasticity``. This learns reliably (no RL replay-buffer
     variance), satisfies C37, and is proven non-vacuous by a ``good-action >
     bad-action`` assertion. The essential cap (INV-PO-001) is a hard clamp, never
     learned.

Persists ``pricing_maddpg.pt`` (actor state_dict) + ``.serving.json`` (arch +
elasticity weights). Returns a gradient :class:`TrainResult`.

Run::

    python -m agents.pricing_oracle.training.train [--smoke]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
import structlog
from synapse_common.training_contract import TrainResult, save_checkpoint

if TYPE_CHECKING:
    import torch

logger = structlog.get_logger(__name__)

ROOT = Path(__file__).resolve().parents[3]
CHECKPOINT_DIR = ROOT / "artifacts" / "checkpoints"
SERVING_NAME = "pricing_maddpg"
OBS_DIM = 24
CATEGORIES = ["essential", "snack", "beverage", "dairy", "produce"]
# Per-category baseline elasticity (essentials inelastic, snacks/beverages elastic).
BASE_ELASTICITY = {
    "essential": -0.3,
    "snack": -1.4,
    "beverage": -1.6,
    "dairy": -0.8,
    "produce": -1.1,
}


def _fit_elasticity(rng: np.random.Generator, n: int) -> tuple[list[float], float, float]:
    """OLS fit of ``elasticity = controls·w + b`` on seeded observational data.

    Returns (weights, bias, r2). The "true" elasticity is a known linear function of
    the controls plus noise; OLS recovers it (high R² = a real, identifiable signal).
    """
    f = 4  # controls: [competitor_ratio, inventory_pressure, demand_idx, season]
    controls = rng.normal(0.0, 1.0, size=(n, f))
    true_w = np.array([-0.4, 0.25, -0.15, 0.1])
    true_b = -1.0
    elasticity = controls @ true_w + true_b + rng.normal(0.0, 0.05, size=n)
    # OLS with intercept.
    design = np.column_stack([controls, np.ones(n)])
    coef, *_ = np.linalg.lstsq(design, elasticity, rcond=None)
    w, b = coef[:f], float(coef[f])
    pred = design @ coef
    ss_res = float(np.sum((elasticity - pred) ** 2))
    ss_tot = float(np.sum((elasticity - elasticity.mean()) ** 2))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0
    return [float(x) for x in w], b, r2


def _profit(mult: torch.Tensor, elasticity: torch.Tensor, cost: torch.Tensor) -> torch.Tensor:
    """Differentiable semi-log profit: (m − cost)·exp(elasticity·(m − 1))."""
    import torch  # noqa: PLC0415

    return (mult - cost) * torch.exp(elasticity * (mult - 1.0))


def _make_obs(elasticity: float, cost: float) -> torch.Tensor:
    """Encode (elasticity, cost) into an OBS_DIM observation the actor consumes."""
    import torch  # noqa: PLC0415

    vec = torch.zeros(OBS_DIM, dtype=torch.float32)
    vec[0] = float(elasticity)
    vec[1] = float(cost)
    return vec.unsqueeze(0)


def train(config: object | None = None, *, smoke: bool = False) -> TrainResult:
    """Fit the elasticity model + train the actor policy by profit-gradient ascent."""
    import torch  # noqa: PLC0415

    from agents.pricing_oracle.models.maddpg import CATEGORIES as MADDPG_CATS  # noqa: PLC0415
    from agents.pricing_oracle.models.maddpg import ESSENTIAL_CAP, PricingMADDPG  # noqa: PLC0415

    seed = 42
    torch.manual_seed(seed)
    rng = np.random.default_rng(seed)
    n_obs = 500 if smoke else 4000
    steps = 150 if smoke else 600

    weights, bias, r2 = _fit_elasticity(rng, n_obs)
    logger.info("elasticity_fit", r2=round(r2, 4))

    model = PricingMADDPG(num_agents=len(MADDPG_CATS), obs_dim=OBS_DIM, action_dim=1)
    actor_params = [p for actor in model.actors for p in actor.parameters()]
    optimizer = torch.optim.Adam(actor_params, lr=1e-2)

    # Per-category (elasticity, cost) contexts — the optimal multiplier varies, so
    # the actor must learn a real obs→price mapping, not a constant.
    costs = {c: 0.5 + 0.1 * i for i, c in enumerate(CATEGORIES)}
    obs_by_cat = {c: _make_obs(BASE_ELASTICITY[c], costs[c]) for c in CATEGORIES}

    losses: list[float] = []
    for _ in range(steps):
        optimizer.zero_grad()
        actions = model.forward({c: obs_by_cat[c] for c in MADDPG_CATS})
        profit_terms = []
        for c in MADDPG_CATS:
            el = torch.tensor(BASE_ELASTICITY[c], dtype=torch.float32)
            cost = torch.tensor(costs[c], dtype=torch.float32)
            profit_terms.append(_profit(actions[c].squeeze(), el, cost))
        loss = -torch.stack(profit_terms).mean()
        loss.backward()
        optimizer.step()
        losses.append(float(loss.detach()))

    # good-action > bad-action: the trained policy must beat a fixed bad multiplier.
    model.eval()
    with torch.no_grad():
        trained = model.select_actions({c: obs_by_cat[c] for c in MADDPG_CATS})
        good = bad = 0.0
        for c in MADDPG_CATS:
            el = torch.tensor(BASE_ELASTICITY[c], dtype=torch.float32)
            cost = torch.tensor(costs[c], dtype=torch.float32)
            # The bad baseline is a fixed naive gouge multiplier, held to the SAME
            # guardrail the policy obeys: essentials are HARD-CAPPED at 1.3 (I-6).
            # Essentials are so inelastic (el=-0.3) their unconstrained profit
            # optimum sits at m*=cost-1/el≈3.8 — far past the cap — so an uncapped
            # 2.5 would out-earn the capped policy and make the comparison measure
            # the guardrail, not learning. Capping the baseline identically makes
            # essential a fair tie; the four elastic categories carry the margin.
            bad_mult = min(2.5, ESSENTIAL_CAP) if c == "essential" else 2.5
            good += float(_profit(trained[c].squeeze(), el, cost))
            bad += float(_profit(torch.tensor(bad_mult), el, cost))
    good_beats_bad = good > bad

    CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
    ckpt_path = CHECKPOINT_DIR / f"{SERVING_NAME}.pt"
    sha = save_checkpoint(model, ckpt_path)
    sidecar = {
        "version": f"{'smoke' if smoke else 'full'}_{sha}",
        "smoke": smoke,
        "arch": {"obs_dim": OBS_DIM, "num_agents": len(MADDPG_CATS), "action_dim": 1},
        "elasticity": {"weights": weights, "bias": bias},
    }
    (CHECKPOINT_DIR / f"{SERVING_NAME}.serving.json").write_text(
        json.dumps(sidecar, sort_keys=True, separators=(",", ":")), encoding="utf-8"
    )

    result = TrainResult(
        agent="pricing_oracle",
        gradient_steps=steps,
        start_loss=losses[0] if losses else float("nan"),
        end_loss=losses[-1] if losses else float("nan"),
        epochs=1,
        seed=seed,
        smoke=smoke,
        checkpoint_path=ckpt_path,
        checkpoint_sha=sha,
        metrics={"elasticity_r2": r2, "good_beats_bad": float(good_beats_bad)},
    )
    logger.info("pricing_training_complete", sha=sha, **result.to_dict()["metrics"])
    result.assert_learned()
    if not good_beats_bad:  # the env-response substance check (ADR-043)
        raise RuntimeError("pricing policy did not beat the bad-action baseline (vacuous training)")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Train Pricing Oracle MADDPG actor + elasticity")
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args()
    train(smoke=args.smoke)


if __name__ == "__main__":
    sys.exit(main())  # type: ignore[func-returns-value]
