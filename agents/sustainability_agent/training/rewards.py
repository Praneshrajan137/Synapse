"""
SYNAPSE Sustainability Agent -- Independent Reward Function (I-2).
This reward function is ENTIRELY SELF-CONTAINED within the Sustainability Agent.
NO CROSS-AGENT IMPORTS. Cross-agent import = automatic PR rejection.

Reward: R = -carbon_per_delivery - 0.5*waste_rate + 0.3*prediction_accuracy
"""

from __future__ import annotations

import structlog

logger = structlog.get_logger(__name__)


def carbon_penalty(co2_kg: float, baseline_co2_kg: float = 1.0) -> float:
    """
    Penalty proportional to CO2 emitted per delivery, normalized by baseline.
    Higher emissions -> larger negative contribution.
    """
    if baseline_co2_kg <= 0.0:
        raise ValueError(f"baseline_co2_kg must be > 0, got {baseline_co2_kg}")
    return co2_kg / baseline_co2_kg


def waste_rate_penalty(
    items_wasted: int,
    items_total: int,
) -> float:
    """
    Fraction of items wasted. Range [0, 1].
    Higher waste -> larger negative contribution.
    """
    if items_total <= 0:
        return 0.0
    return items_wasted / items_total


def prediction_accuracy_bonus(
    predicted_co2_kg: float,
    actual_co2_kg: float,
    tolerance: float = 0.10,
) -> float:
    """
    Bonus for accurate CO2 predictions (within tolerance of actual).
    Returns value in [0, 1]. 1.0 = perfect prediction.
    """
    if actual_co2_kg <= 0.0:
        return 1.0 if predicted_co2_kg <= 0.0 else 0.0

    relative_error = abs(predicted_co2_kg - actual_co2_kg) / actual_co2_kg
    accuracy = max(1.0 - (relative_error / tolerance), 0.0)
    return min(accuracy, 1.0)


def compute_reward(
    co2_kg: float,
    items_wasted: int,
    items_total: int,
    predicted_co2_kg: float,
    actual_co2_kg: float,
    baseline_co2_kg: float = 1.0,
    carbon_weight: float = 1.0,
    waste_weight: float = 0.5,
    accuracy_weight: float = 0.3,
) -> dict[str, float]:
    """
    Compute the full Sustainability Agent reward.
    R = -carbon_weight * carbon_per_delivery
        - waste_weight * waste_rate
        + accuracy_weight * prediction_accuracy

    THIS IS THE ONLY REWARD FUNCTION FOR SUSTAINABILITY AGENT (I-2).
    """
    c_penalty = carbon_penalty(co2_kg, baseline_co2_kg)
    w_penalty = waste_rate_penalty(items_wasted, items_total)
    a_bonus = prediction_accuracy_bonus(predicted_co2_kg, actual_co2_kg)

    total = -carbon_weight * c_penalty - waste_weight * w_penalty + accuracy_weight * a_bonus

    logger.info(
        "reward_computed",
        total_reward=round(total, 4),
        carbon_penalty=round(c_penalty, 4),
        waste_rate=round(w_penalty, 4),
        prediction_accuracy=round(a_bonus, 4),
    )

    return {
        "total_reward": total,
        "carbon_penalty": c_penalty,
        "waste_rate": w_penalty,
        "prediction_accuracy": a_bonus,
    }
