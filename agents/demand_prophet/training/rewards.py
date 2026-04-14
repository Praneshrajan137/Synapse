"""
SYNAPSE Demand Prophet -- Independent Reward Function (I-2).
This reward function is ENTIRELY SELF-CONTAINED within the Demand Prophet agent.
NO CROSS-AGENT IMPORTS. Cross-agent import = automatic PR rejection.

Reward: R = -CRPS_loss - 0.5*calibration_gap + event_bonus
"""

from __future__ import annotations

import structlog
import torch
from torch import Tensor

logger = structlog.get_logger(__name__)


def crps_loss(
    predictions: Tensor,
    actuals: Tensor,
    quantile_levels: list[float] | None = None,
) -> Tensor:
    """
    Continuous Ranked Probability Score loss.
    Lower is better. Used as primary forecast accuracy metric.
    """
    if quantile_levels is None:
        quantile_levels = [0.1, 0.5, 0.9]

    losses: list[Tensor] = []
    for i, q in enumerate(quantile_levels):
        errors = actuals - predictions[:, i]
        losses.append(
            torch.where(
                errors >= 0,
                q * errors,
                (q - 1.0) * errors,
            ).mean()
        )

    return torch.stack(losses).mean()


def calibration_gap(
    lower: Tensor,
    upper: Tensor,
    actuals: Tensor,
    target_coverage: float = 0.9,
) -> Tensor:
    """Calibration gap: |empirical_coverage - target_coverage|."""
    covered = ((actuals >= lower) & (actuals <= upper)).float()
    empirical = covered.mean()
    return torch.abs(empirical - target_coverage)


def event_bonus(
    predictions: Tensor,
    event_signals: Tensor,
    actuals: Tensor,
) -> Tensor:
    """Bonus reward for correctly predicting event-driven demand surges."""
    event_mask = event_signals > 0.5
    if not event_mask.any():
        return torch.tensor(0.0, device=predictions.device)

    event_preds = predictions[event_mask]
    event_actuals = actuals[event_mask]
    event_mape = (torch.abs(event_preds - event_actuals) / (event_actuals + 1e-8)).mean()

    return torch.clamp(1.0 - event_mape, min=0.0, max=1.0)


def compute_reward(
    predictions: Tensor,
    actuals: Tensor,
    lower_bound: Tensor,
    upper_bound: Tensor,
    event_signals: Tensor | None = None,
    crps_weight: float = 1.0,
    calibration_weight: float = 0.5,
    event_weight: float = 0.1,
) -> dict[str, Tensor]:
    """
    Compute the full Demand Prophet reward.
    R = -crps_weight*CRPS - calibration_weight*calibration_gap + event_weight*event_bonus

    THIS IS THE ONLY REWARD FUNCTION FOR DEMAND PROPHET (I-2).
    """
    crps = crps_loss(predictions, actuals)
    cal_gap = calibration_gap(lower_bound, upper_bound, actuals)

    evt_bonus = torch.tensor(0.0, device=predictions.device)
    if event_signals is not None:
        median_pred = predictions[:, 1]
        evt_bonus = event_bonus(median_pred, event_signals, actuals)

    total = -crps_weight * crps - calibration_weight * cal_gap + event_weight * evt_bonus

    return {
        "total_reward": total,
        "crps_loss": crps,
        "calibration_gap": cal_gap,
        "event_bonus": evt_bonus,
    }
