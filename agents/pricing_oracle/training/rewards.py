"""
SYNAPSE Pricing Oracle -- Independent Reward Function (I-2).
This reward function is ENTIRELY SELF-CONTAINED within the Pricing Oracle agent.
NO CROSS-AGENT IMPORTS. Cross-agent import = automatic PR rejection.

Reward: R = revenue + 0.5*elasticity_alignment - 5.0*essential_cap_violation - 2.0*competitor_gap

The -5.0 weight on essential_cap_violation makes any violation catastrophically
negative, ensuring the RL policy learns to NEVER approach the hard cap boundary.
The hard clamp in the model is the true safety net; the reward penalty is defense-in-depth.
"""
from __future__ import annotations

import structlog
import torch
from torch import Tensor

logger = structlog.get_logger(__name__)

ESSENTIAL_CAP: float = 1.3


def revenue_component(
    multipliers: Tensor,
    base_prices: Tensor,
    demand_quantities: Tensor,
) -> Tensor:
    """
    Revenue component: total revenue from priced items.
    Normalized by batch size for stable gradients.
    """
    revenue = (multipliers * base_prices * demand_quantities).sum(dim=-1)
    return revenue.mean()


def elasticity_alignment(
    multipliers: Tensor,
    elasticity_estimates: Tensor,
) -> Tensor:
    """
    Reward for aligning pricing with causal elasticity estimates.
    Higher elasticity (more sensitive) -> lower multiplier should be preferred.
    Alignment = -correlation(multiplier, |elasticity|).
    """
    abs_elasticity = elasticity_estimates.abs()

    if abs_elasticity.std() < 1e-8 or multipliers.std() < 1e-8:
        return torch.tensor(0.0, device=multipliers.device)

    mult_centered = multipliers - multipliers.mean()
    elast_centered = abs_elasticity - abs_elasticity.mean()

    correlation = (mult_centered * elast_centered).mean() / (
        multipliers.std() * abs_elasticity.std() + 1e-8
    )

    return -correlation


def essential_cap_violation(
    multipliers: Tensor,
    is_essential: Tensor,
    cap: float = ESSENTIAL_CAP,
) -> Tensor:
    """
    Penalty for essential items exceeding the 1.3x cap.
    Returns the total violation magnitude (0 if all within cap).
    This should NEVER fire if the hard clamp works, but exists as defense-in-depth.
    """
    violations = torch.clamp(multipliers - cap, min=0.0) * is_essential.float()
    total_violation = violations.sum()

    if total_violation > 0:
        logger.error(
            "essential_cap_violation_in_reward",
            violation_sum=total_violation.item(),
            hint="Hard clamp should prevent this — check model output pipeline",
        )

    return total_violation


def competitor_gap(
    multipliers: Tensor,
    competitor_multipliers: Tensor,
) -> Tensor:
    """
    Penalty for pricing significantly above competitors.
    Gap = max(0, our_price - competitor_price).
    """
    gaps = torch.clamp(multipliers - competitor_multipliers, min=0.0)
    return gaps.mean()


def compute_reward(
    multipliers: Tensor,
    base_prices: Tensor,
    demand_quantities: Tensor,
    elasticity_estimates: Tensor,
    is_essential: Tensor,
    competitor_multipliers: Tensor | None = None,
    revenue_weight: float = 1.0,
    elasticity_weight: float = 0.5,
    essential_penalty_weight: float = -5.0,
    competitor_gap_weight: float = -2.0,
) -> dict[str, Tensor]:
    """
    Compute the full Pricing Oracle reward.

    R = revenue_weight * revenue
      + elasticity_weight * elasticity_alignment
      + essential_penalty_weight * essential_cap_violation
      + competitor_gap_weight * competitor_gap

    The essential_penalty_weight is -5.0 by default, making any cap violation
    catastrophically negative. THIS IS THE ONLY REWARD FUNCTION FOR PRICING ORACLE (I-2).
    """
    rev = revenue_component(multipliers, base_prices, demand_quantities)
    elast = elasticity_alignment(multipliers, elasticity_estimates)
    cap_viol = essential_cap_violation(multipliers, is_essential)

    comp_gap = torch.tensor(0.0, device=multipliers.device)
    if competitor_multipliers is not None:
        comp_gap = competitor_gap(multipliers, competitor_multipliers)

    total = (
        revenue_weight * rev
        + elasticity_weight * elast
        + essential_penalty_weight * cap_viol
        + competitor_gap_weight * comp_gap
    )

    return {
        "total_reward": total,
        "revenue": rev,
        "elasticity_alignment": elast,
        "essential_cap_violation": cap_viol,
        "competitor_gap": comp_gap,
    }
