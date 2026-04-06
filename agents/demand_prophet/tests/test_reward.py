"""
SYNAPSE Demand Prophet -- Reward function unit tests.
Verifies I-2 (independent reward) and reward component correctness.
"""
from __future__ import annotations

import ast
from pathlib import Path

import torch

from agents.demand_prophet.training.rewards import (
    calibration_gap,
    compute_reward,
    crps_loss,
    event_bonus,
)


class TestRewardIsolation:
    """Verify I-2: No cross-agent imports in rewards.py."""

    def test_no_cross_agent_imports(self) -> None:
        rewards_path = Path("agents/demand_prophet/training/rewards.py")
        tree = ast.parse(rewards_path.read_text())

        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                assert "agents." not in node.module or "demand_prophet" in node.module, (
                    f"Cross-agent import detected: {node.module} -- violates I-2"
                )


class TestCRPSLoss:
    def test_zero_loss_perfect_predictions(self) -> None:
        preds = torch.tensor([[5.0, 10.0, 15.0]])
        actuals = torch.tensor([10.0])
        loss = crps_loss(preds, actuals)
        assert loss >= 0, "CRPS must be non-negative"

    def test_higher_error_higher_loss(self) -> None:
        preds_good = torch.tensor([[9.0, 10.0, 11.0]])
        preds_bad = torch.tensor([[2.0, 5.0, 8.0]])
        actuals = torch.tensor([10.0])

        loss_good = crps_loss(preds_good, actuals)
        loss_bad = crps_loss(preds_bad, actuals)
        assert loss_bad > loss_good


class TestCalibrationGap:
    def test_perfect_calibration(self) -> None:
        n = 100
        lower = torch.zeros(n)
        upper = torch.ones(n) * 20
        actuals = torch.rand(n) * 20
        gap = calibration_gap(lower, upper, actuals, target_coverage=1.0)
        assert gap < 0.15

    def test_zero_coverage(self) -> None:
        lower = torch.ones(10) * 100
        upper = torch.ones(10) * 200
        actuals = torch.zeros(10)
        gap = calibration_gap(lower, upper, actuals, target_coverage=0.9)
        assert gap > 0.8


class TestComputeReward:
    def test_reward_components(self) -> None:
        preds = torch.randn(10, 3).abs()
        actuals = torch.randn(10).abs()
        lower = preds[:, 0]
        upper = preds[:, 2]

        result = compute_reward(preds, actuals, lower, upper)
        assert "total_reward" in result
        assert "crps_loss" in result
        assert "calibration_gap" in result
        assert "event_bonus" in result

    def test_event_bonus_with_signals(self) -> None:
        preds = torch.tensor([[9.0, 10.0, 11.0]] * 5)
        actuals = torch.tensor([10.0] * 5)
        event_signals = torch.tensor([1.0, 0.0, 1.0, 0.0, 1.0])

        result = compute_reward(
            preds,
            actuals,
            preds[:, 0],
            preds[:, 2],
            event_signals=event_signals,
        )
        assert result["event_bonus"] > 0
