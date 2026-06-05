"""
SYNAPSE Disruption Shield — Independent Reward Function (I-2).
This reward function is ENTIRELY SELF-CONTAINED.
NO CROSS-AGENT IMPORTS. Cross-agent import = automatic PR rejection.

R = early_detection - 10*false_positive - 50*missed_disruption + recovery_speed
"""

from __future__ import annotations

import structlog
import torch
from synapse_common.reward_shadow import resolve_weights
from torch import Tensor

from agents.disruption_shield.training import reward_config

logger = structlog.get_logger(__name__)


def early_detection_reward(
    predicted_alert: Tensor,
    actual_disruption: Tensor,
    hours_before_impact: Tensor,
) -> Tensor:
    """Reward for detecting disruptions early.

    Higher reward when alert is raised well before actual impact.
    Normalized by a 72-hour planning horizon.
    """
    correct_detection = (predicted_alert > 0.5) & (actual_disruption > 0.5)
    normalized_lead_time = torch.clamp(hours_before_impact / 72.0, min=0.0, max=1.0)
    return (correct_detection.float() * normalized_lead_time).mean()


def false_positive_penalty(
    predicted_alert: Tensor,
    actual_disruption: Tensor,
) -> Tensor:
    """Penalty for raising alerts when no disruption occurred.

    False positives erode trust and waste operational resources.
    """
    fp = (predicted_alert > 0.5) & (actual_disruption < 0.5)
    return fp.float().mean()


def missed_disruption_penalty(
    predicted_alert: Tensor,
    actual_disruption: Tensor,
) -> Tensor:
    """Severe penalty for missing actual disruptions.

    This is the most critical failure mode — undetected disruptions
    cascade through the supply chain.
    """
    fn = (predicted_alert < 0.5) & (actual_disruption > 0.5)
    return fn.float().mean()


def recovery_speed_reward(
    time_to_recovery_hours: Tensor,
    playbook_applied: Tensor,
    baseline_recovery_hours: float = 48.0,
) -> Tensor:
    """Reward for faster recovery when playbook is applied.

    Measures improvement over baseline recovery time.
    """
    improvement = torch.clamp(
        (baseline_recovery_hours - time_to_recovery_hours) / baseline_recovery_hours,
        min=0.0,
        max=1.0,
    )
    return (playbook_applied.float() * improvement).mean()


def compute_reward(
    predicted_alert: Tensor,
    actual_disruption: Tensor,
    hours_before_impact: Tensor,
    time_to_recovery_hours: Tensor,
    playbook_applied: Tensor,
    early_detection_weight: float | None = None,
    false_positive_weight: float | None = None,
    missed_disruption_weight: float | None = None,
    recovery_speed_weight: float | None = None,
) -> dict[str, Tensor]:
    """Compute full Disruption Shield reward.

    THIS IS THE ONLY REWARD FUNCTION FOR DISRUPTION SHIELD (I-2).
    It imports NOTHING from other agents.
    """
    early = early_detection_reward(predicted_alert, actual_disruption, hours_before_impact)
    fp = false_positive_penalty(predicted_alert, actual_disruption)
    missed = missed_disruption_penalty(predicted_alert, actual_disruption)
    recovery = recovery_speed_reward(time_to_recovery_hours, playbook_applied)
    weights = resolve_weights(
        "disruption_shield",
        reward_config.WEIGHTS,
        early_detection_weight=early_detection_weight,
        false_positive_weight=false_positive_weight,
        missed_disruption_weight=missed_disruption_weight,
        recovery_speed_weight=recovery_speed_weight,
    )

    total = (
        weights["early_detection_weight"] * early
        - weights["false_positive_weight"] * fp
        - weights["missed_disruption_weight"] * missed
        + weights["recovery_speed_weight"] * recovery
    )

    return {
        "total_reward": total,
        "early_detection": early,
        "false_positive": fp,
        "missed_disruption": missed,
        "recovery_speed": recovery,
    }
