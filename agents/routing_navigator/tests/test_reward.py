"""SYNAPSE Routing Navigator -- Reward function tests (I-2 isolation)."""

from __future__ import annotations

import ast
from pathlib import Path

import torch

from agents.routing_navigator.training.rewards import compute_reward, gini_coefficient


class TestRewardIsolation:
    def test_no_cross_agent_imports(self) -> None:
        rewards_path = Path("agents/routing_navigator/training/rewards.py")
        tree = ast.parse(rewards_path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                assert "agents." not in node.module or "routing_navigator" in node.module, (
                    f"Cross-agent import: {node.module} -- violates I-2"
                )


class TestGiniCoefficient:
    def test_perfect_equality(self) -> None:
        earnings = torch.tensor([100.0, 100.0, 100.0, 100.0])
        gini = gini_coefficient(earnings)
        assert abs(gini.item()) < 0.01

    def test_max_inequality(self) -> None:
        earnings = torch.tensor([0.0, 0.0, 0.0, 100.0])
        gini = gini_coefficient(earnings)
        assert gini.item() > 0.5


class TestComputeReward:
    def test_components(self) -> None:
        result = compute_reward(
            route_times=torch.tensor([20.0, 25.0]),
            baseline_times=torch.tensor([30.0, 35.0]),
            route_fuel=torch.tensor([1.0, 1.5]),
            baseline_fuel=torch.tensor([2.0, 2.5]),
            rider_earnings=torch.tensor([100.0, 100.0]),
            freshness_violations=0,
            total_routes=2,
        )
        assert "total_reward" in result
        assert "gini_coefficient" in result
        assert result["fairness_score"].item() > 0.9
