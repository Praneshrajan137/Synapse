"""
SYNAPSE Inventory Sentinel -- Three Independent Reward Functions (I-2).
EACH LEVEL has its own reward. NO CROSS-AGENT IMPORTS.

L1 Strategic: R = fill_rate - 0.3*holding_cost - 2.0*stockout - 0.5*waste_rate
L2 Tactical:  R = service_level + freshness - 0.4*holding_cost - 3.0*perishable_waste
L3 Operational: R = -avg_pick_time + freshness_exposure_bonus
"""
from __future__ import annotations

import torch
from torch import Tensor


def compute_l1_strategic_reward(
    fill_rate: Tensor,
    holding_cost: Tensor,
    stockout_count: Tensor,
    waste_rate: Tensor,
) -> dict[str, Tensor]:
    """L1 Strategic reward -- cluster-level optimization."""
    total = fill_rate - 0.3 * holding_cost - 2.0 * stockout_count - 0.5 * waste_rate
    return {
        "total_reward": total,
        "fill_rate": fill_rate,
        "holding_cost": holding_cost,
        "stockout": stockout_count,
        "waste_rate": waste_rate,
    }


def compute_l2_tactical_reward(
    service_level: Tensor,
    freshness_score: Tensor,
    holding_cost: Tensor,
    perishable_waste: Tensor,
) -> dict[str, Tensor]:
    """L2 Tactical reward -- per-store per-SKU optimization."""
    total = service_level + freshness_score - 0.4 * holding_cost - 3.0 * perishable_waste
    return {
        "total_reward": total,
        "service_level": service_level,
        "freshness_score": freshness_score,
        "perishable_waste": perishable_waste,
    }


def compute_l3_operational_reward(
    avg_pick_time: Tensor,
    freshness_exposure: Tensor,
) -> dict[str, Tensor]:
    """L3 Operational reward -- real-time shelf management."""
    total = -avg_pick_time + freshness_exposure
    return {
        "total_reward": total,
        "avg_pick_time": avg_pick_time,
        "freshness_exposure": freshness_exposure,
    }
