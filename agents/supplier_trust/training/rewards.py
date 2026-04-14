"""
SYNAPSE Supplier Trust -- Agent-Scoped Reward Function (I-2).
NO CROSS-AGENT IMPORTS. This module stands alone.

R = prediction_accuracy - 2.0 * trust_bias + 0.5 * calibration

Components:
  - prediction_accuracy: how well predicted lead-time matches observed
  - trust_bias: penalises systematic over/under-trust of suppliers
  - calibration: rewards well-calibrated posterior uncertainty intervals
"""

from __future__ import annotations

import torch
from torch import Tensor


def compute_supplier_trust_reward(
    prediction_accuracy: Tensor,
    trust_bias: Tensor,
    calibration: Tensor,
) -> dict[str, Tensor]:
    """Compute agent-scoped reward for Supplier Trust.

    R = prediction_accuracy - 2.0 * trust_bias + 0.5 * calibration

    Args:
        prediction_accuracy: How accurately the model predicted lead times.
            Higher is better.  Range [0, 1].
        trust_bias: Absolute magnitude of systematic trust bias.
            Lower is better.  Range [0, inf).
        calibration: Calibration score for posterior intervals (coverage vs width).
            Higher is better.  Range [0, 1].

    Returns:
        Dict with 'total_reward' and per-component breakdown.
    """
    total = prediction_accuracy - 2.0 * trust_bias + 0.5 * calibration
    return {
        "total_reward": total,
        "prediction_accuracy": prediction_accuracy,
        "trust_bias": trust_bias,
        "calibration": calibration,
    }


def compute_prediction_accuracy(
    predicted_days: Tensor,
    observed_days: Tensor,
) -> Tensor:
    """Symmetric MAPE-based accuracy: 1 - sMAPE."""
    epsilon = 1e-8
    smape = torch.mean(
        2.0
        * torch.abs(predicted_days - observed_days)
        / (torch.abs(predicted_days) + torch.abs(observed_days) + epsilon)
    )
    return torch.clamp(1.0 - smape, min=0.0, max=1.0)


def compute_trust_bias(
    trust_scores: Tensor,
    actual_reliability: Tensor,
) -> Tensor:
    """Mean absolute deviation between trust scores and actual reliability."""
    return torch.mean(torch.abs(trust_scores - actual_reliability))


def compute_calibration_score(
    observed_days: Tensor,
    p10: Tensor,
    p90: Tensor,
) -> Tensor:
    """Empirical coverage calibration for the 80% prediction interval [p10, p90]."""
    in_interval = ((observed_days >= p10) & (observed_days <= p90)).float()
    coverage = torch.mean(in_interval)
    target = 0.8
    return 1.0 - torch.abs(coverage - target)
