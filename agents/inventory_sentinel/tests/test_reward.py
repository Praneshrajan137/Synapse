"""SYNAPSE Inventory Sentinel -- Reward function tests (I-2 isolation)."""
from __future__ import annotations

import ast
from pathlib import Path

import torch

from agents.inventory_sentinel.training.rewards import (
    compute_l1_strategic_reward,
    compute_l2_tactical_reward,
    compute_l3_operational_reward,
)


class TestRewardIsolation:
    def test_no_cross_agent_imports(self) -> None:
        rewards_path = Path("agents/inventory_sentinel/training/rewards.py")
        tree = ast.parse(rewards_path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                assert "agents." not in node.module or "inventory_sentinel" in node.module, (
                    f"Cross-agent import: {node.module} -- violates I-2"
                )


class TestL1StrategicReward:
    def test_components(self) -> None:
        result = compute_l1_strategic_reward(
            fill_rate=torch.tensor(0.95),
            holding_cost=torch.tensor(0.1),
            stockout_count=torch.tensor(0.0),
            waste_rate=torch.tensor(0.02),
        )
        assert "total_reward" in result
        assert result["total_reward"] > 0


class TestL2TacticalReward:
    def test_components(self) -> None:
        result = compute_l2_tactical_reward(
            service_level=torch.tensor(0.9),
            freshness_score=torch.tensor(0.8),
            holding_cost=torch.tensor(0.2),
            perishable_waste=torch.tensor(0.01),
        )
        assert result["total_reward"] > 0


class TestL3OperationalReward:
    def test_components(self) -> None:
        result = compute_l3_operational_reward(
            avg_pick_time=torch.tensor(2.0),
            freshness_exposure=torch.tensor(3.0),
        )
        assert result["total_reward"] > 0
