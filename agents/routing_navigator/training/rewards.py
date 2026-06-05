"""
SYNAPSE Routing Navigator -- Independent Reward Function (I-2).
NO CROSS-AGENT IMPORTS. Cross-agent import = automatic PR rejection.

R = w1*time_saved + w2*fuel_saved + w3*freshness + w4*Gini(rider_earnings)
"""

from __future__ import annotations

import torch
from synapse_common.reward_shadow import resolve_weights
from torch import Tensor

from agents.routing_navigator.training import reward_config


def gini_coefficient(earnings: Tensor) -> Tensor:
    """
    Compute Gini coefficient for rider earnings fairness.
    Gini in [0, 1]: 0 = perfect equality, 1 = maximum inequality.
    """
    if earnings.numel() <= 1:
        return torch.tensor(0.0, device=earnings.device)

    sorted_earnings, _ = torch.sort(earnings)
    n = sorted_earnings.size(0)
    index = torch.arange(1, n + 1, dtype=torch.float32, device=earnings.device)
    total = sorted_earnings.sum()

    if total == 0:
        return torch.tensor(0.0, device=earnings.device)

    return (2.0 * (index * sorted_earnings).sum() / (n * total)) - (n + 1.0) / n


def compute_time_saved(route_times: Tensor, baseline_times: Tensor) -> Tensor:
    savings = (baseline_times - route_times) / (baseline_times + 1e-8)
    return torch.clamp(savings.mean(), 0.0, 1.0)


def compute_fuel_saved(route_fuel: Tensor, baseline_fuel: Tensor) -> Tensor:
    savings = (baseline_fuel - route_fuel) / (baseline_fuel + 1e-8)
    return torch.clamp(savings.mean(), 0.0, 1.0)


def compute_freshness(violations: int, total_routes: int) -> Tensor:
    if total_routes == 0:
        return torch.tensor(1.0)
    return torch.tensor(1.0 - violations / total_routes)


def compute_reward(
    route_times: Tensor,
    baseline_times: Tensor,
    route_fuel: Tensor,
    baseline_fuel: Tensor,
    rider_earnings: Tensor,
    freshness_violations: int,
    total_routes: int,
    w_time: float | None = None,
    w_fuel: float | None = None,
    w_freshness: float | None = None,
    w_fairness: float | None = None,
) -> dict[str, Tensor]:
    """Compute full Routing Navigator reward (I-2: agent-scoped only)."""
    time_saved = compute_time_saved(route_times, baseline_times)
    fuel_saved = compute_fuel_saved(route_fuel, baseline_fuel)
    freshness = compute_freshness(freshness_violations, total_routes)
    gini = gini_coefficient(rider_earnings)
    fairness = 1.0 - gini
    weights = resolve_weights(
        "routing_navigator",
        reward_config.WEIGHTS,
        w_time=w_time,
        w_fuel=w_fuel,
        w_freshness=w_freshness,
        w_fairness=w_fairness,
    )

    total = (
        weights["w_time"] * time_saved
        + weights["w_fuel"] * fuel_saved
        + weights["w_freshness"] * freshness
        + weights["w_fairness"] * fairness
    )

    return {
        "total_reward": total,
        "time_saved": time_saved,
        "fuel_saved": fuel_saved,
        "freshness_score": freshness,
        "gini_coefficient": gini,
        "fairness_score": fairness,
    }
