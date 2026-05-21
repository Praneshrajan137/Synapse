"""
SYNAPSE Freshness Guardian — Independent Reward Function (I-2).
This reward function is ENTIRELY SELF-CONTAINED.
NO CROSS-AGENT IMPORTS. Cross-agent import = automatic PR rejection.

R = freshness_accuracy + 0.4*markdown_timing - 2.0*fssai_violation - 0.3*unnecessary_markdown
"""

from __future__ import annotations

import structlog
import torch
from torch import Tensor

logger = structlog.get_logger(__name__)


def freshness_accuracy_reward(
    predicted_quality: Tensor,
    actual_quality: Tensor,
) -> Tensor:
    """Reward for accurate quality score prediction."""
    mape = torch.abs(predicted_quality - actual_quality) / (actual_quality + 1e-8)
    return torch.clamp(1.0 - mape.mean(), min=0.0)


def markdown_timing_reward(
    markdown_applied: Tensor,
    days_to_expiry: Tensor,
    was_sold: Tensor,
) -> Tensor:
    """Reward for well-timed markdowns.
    Positive: markdown applied AND item sold before expiry.
    Negative: markdown too early (lost revenue) or too late (wasted).
    """
    timely = (markdown_applied > 0.5) & (was_sold > 0.5) & (days_to_expiry > 0)
    too_late = (days_to_expiry <= 0) & (was_sold < 0.5)

    reward = timely.float().mean() - 0.5 * too_late.float().mean()
    return reward


def fssai_violation_penalty(
    temperature_deviation_hours: Tensor,
    fssai_logged: Tensor,
    threshold_hours: float = 4.0,
) -> Tensor:
    """Penalty for FSSAI cold chain violations not properly logged.
    INV-FG-003: temp deviation > 4h AND not logged = violation.
    """
    violation = (temperature_deviation_hours > threshold_hours) & (fssai_logged < 0.5)
    return violation.float().mean()


def unnecessary_markdown_penalty(
    markdown_applied: Tensor,
    days_to_expiry: Tensor,
    quality_score: Tensor,
    expiry_threshold: float = 0.75,
) -> Tensor:
    """Penalty for applying markdown when item is still fresh."""
    unnecessary = (
        (markdown_applied > 0.5) & (days_to_expiry > 7) & (quality_score > expiry_threshold)
    )
    return unnecessary.float().mean()


def compute_reward(
    predicted_quality: Tensor,
    actual_quality: Tensor,
    markdown_applied: Tensor,
    days_to_expiry: Tensor,
    was_sold: Tensor,
    temperature_deviation_hours: Tensor,
    fssai_logged: Tensor,
    accuracy_weight: float | None = None,
    timing_weight: float | None = None,
    fssai_weight: float | None = None,
    unnecessary_weight: float | None = None,
) -> dict[str, Tensor]:
    """Compute full Freshness Guardian reward.

    THIS IS THE ONLY REWARD FUNCTION FOR FRESHNESS GUARDIAN (I-2).
    It imports NOTHING from other agents.

    Sprint 9 (ADR-031 cutover): spec-generated WEIGHTS is source-of-truth.
    """
    from synapse_common.reward_shadow import shadow_check

    from agents.freshness_guardian.training import reward_config

    if accuracy_weight is None:
        accuracy_weight = reward_config.WEIGHTS["accuracy_weight"]
    if timing_weight is None:
        timing_weight = reward_config.WEIGHTS["timing_weight"]
    if fssai_weight is None:
        fssai_weight = reward_config.WEIGHTS["fssai_weight"]
    if unnecessary_weight is None:
        unnecessary_weight = reward_config.WEIGHTS["unnecessary_weight"]

    shadow_check(
        "freshness_guardian",
        reward_config.WEIGHTS,
        accuracy_weight=accuracy_weight,
        timing_weight=timing_weight,
        fssai_weight=fssai_weight,
        unnecessary_weight=unnecessary_weight,
    )

    accuracy = freshness_accuracy_reward(predicted_quality, actual_quality)
    timing = markdown_timing_reward(markdown_applied, days_to_expiry, was_sold)
    fssai = fssai_violation_penalty(temperature_deviation_hours, fssai_logged)
    unnecessary = unnecessary_markdown_penalty(markdown_applied, days_to_expiry, predicted_quality)

    total = (
        accuracy_weight * accuracy
        + timing_weight * timing
        - fssai_weight * fssai
        - unnecessary_weight * unnecessary
    )

    return {
        "total_reward": total,
        "freshness_accuracy": accuracy,
        "markdown_timing": timing,
        "fssai_violation": fssai,
        "unnecessary_markdown": unnecessary,
    }
