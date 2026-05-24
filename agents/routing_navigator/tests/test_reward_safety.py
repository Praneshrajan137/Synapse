"""Routing Navigator reward-hacking counterfactuals (Sprint 9 §M6)."""

from __future__ import annotations

import contextlib

import torch
from synapse_common.metrics import REWARD_WEIGHT_DIVERGENCE_TOTAL

from agents.routing_navigator.training import reward_config
from agents.routing_navigator.training.rewards import compute_reward, gini_coefficient


def _reset_counter() -> None:
    with contextlib.suppress(AttributeError):
        REWARD_WEIGHT_DIVERGENCE_TOTAL._metrics.clear()  # type: ignore[attr-defined]


def test_reward_weights_sum_to_one() -> None:
    """Routing weights are intentionally a convex combination; tampering
    that shifts the sum away from 1.0 is observable."""
    w = reward_config.WEIGHTS
    total = w["w_time"] + w["w_fuel"] + w["w_freshness"] + w["w_fairness"]
    assert abs(total - 1.0) < 1e-9, f"routing weights sum {total} != 1.0"


def test_fairness_weight_positive_so_gini_disincentivised() -> None:
    """fairness = 1 - gini; positive weight rewards low-gini (fair) outcomes."""
    assert reward_config.WEIGHTS["w_fairness"] > 0.0


def test_gini_is_zero_on_equal_rider_earnings() -> None:
    """Perfect equality must yield Gini = 0 (and thus fairness = 1)."""
    earnings = torch.tensor([100.0, 100.0, 100.0, 100.0])
    g = gini_coefficient(earnings)
    assert abs(float(g)) < 1e-6


def test_kwarg_override_triggers_divergence() -> None:
    _reset_counter()
    compute_reward(
        route_times=torch.tensor([10.0]),
        baseline_times=torch.tensor([12.0]),
        route_fuel=torch.tensor([5.0]),
        baseline_fuel=torch.tensor([6.0]),
        rider_earnings=torch.tensor([100.0, 110.0, 90.0]),
        freshness_violations=0,
        total_routes=10,
        w_fairness=999.0,  # divergence
    )
    samples = list(REWARD_WEIGHT_DIVERGENCE_TOTAL.collect())
    total = sum(
        s.value
        for m in samples
        for s in m.samples
        if s.labels.get("agent") == "routing_navigator"
        and s.labels.get("key") == "w_fairness"
        and s.name.endswith("_total")
    )
    assert total >= 1.0


def test_matching_kwargs_no_divergence() -> None:
    _reset_counter()
    compute_reward(
        route_times=torch.tensor([10.0]),
        baseline_times=torch.tensor([12.0]),
        route_fuel=torch.tensor([5.0]),
        baseline_fuel=torch.tensor([6.0]),
        rider_earnings=torch.tensor([100.0, 110.0, 90.0]),
        freshness_violations=0,
        total_routes=10,
        w_time=reward_config.WEIGHTS["w_time"],
        w_fuel=reward_config.WEIGHTS["w_fuel"],
        w_freshness=reward_config.WEIGHTS["w_freshness"],
        w_fairness=reward_config.WEIGHTS["w_fairness"],
    )
    samples = list(REWARD_WEIGHT_DIVERGENCE_TOTAL.collect())
    total = sum(
        s.value
        for m in samples
        for s in m.samples
        if s.labels.get("agent") == "routing_navigator" and s.name.endswith("_total")
    )
    assert total == 0.0
