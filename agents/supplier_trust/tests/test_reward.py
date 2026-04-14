"""SYNAPSE Supplier Trust -- Reward function tests (I-2 isolation)."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
import torch

from agents.supplier_trust.training.rewards import (
    compute_calibration_score,
    compute_prediction_accuracy,
    compute_supplier_trust_reward,
    compute_trust_bias,
)


class TestRewardIsolation:
    """I-2: Agent-scoped reward -- no cross-agent imports allowed."""

    def test_no_cross_agent_imports(self) -> None:
        rewards_path = Path("agents/supplier_trust/training/rewards.py")
        tree = ast.parse(rewards_path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                assert "agents." not in node.module or "supplier_trust" in node.module, (
                    f"Cross-agent import: {node.module} -- violates I-2"
                )

    def test_no_synapse_common_model_imports(self) -> None:
        """Reward functions must not import domain models -- pure tensor math only."""
        rewards_path = Path("agents/supplier_trust/training/rewards.py")
        tree = ast.parse(rewards_path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                assert "synapse_common" not in node.module, (
                    f"Reward imports synapse_common: {node.module} -- keep reward pure"
                )


class TestSupplierTrustReward:
    """Test the composite reward formula: R = accuracy - 2.0*bias + 0.5*calibration."""

    def test_positive_total_reward(self) -> None:
        result = compute_supplier_trust_reward(
            prediction_accuracy=torch.tensor(0.9),
            trust_bias=torch.tensor(0.05),
            calibration=torch.tensor(0.85),
        )
        assert "total_reward" in result
        assert result["total_reward"].item() > 0

    def test_high_bias_penalises(self) -> None:
        low_bias = compute_supplier_trust_reward(
            prediction_accuracy=torch.tensor(0.9),
            trust_bias=torch.tensor(0.01),
            calibration=torch.tensor(0.8),
        )
        high_bias = compute_supplier_trust_reward(
            prediction_accuracy=torch.tensor(0.9),
            trust_bias=torch.tensor(0.5),
            calibration=torch.tensor(0.8),
        )
        assert low_bias["total_reward"].item() > high_bias["total_reward"].item()

    def test_reward_components_present(self) -> None:
        result = compute_supplier_trust_reward(
            prediction_accuracy=torch.tensor(0.8),
            trust_bias=torch.tensor(0.1),
            calibration=torch.tensor(0.7),
        )
        assert "prediction_accuracy" in result
        assert "trust_bias" in result
        assert "calibration" in result


class TestPredictionAccuracy:
    def test_perfect_prediction(self) -> None:
        acc = compute_prediction_accuracy(
            predicted_days=torch.tensor([3.0, 5.0]),
            observed_days=torch.tensor([3.0, 5.0]),
        )
        assert acc.item() == pytest.approx(1.0, abs=1e-6)

    def test_bounded_zero_one(self) -> None:
        acc = compute_prediction_accuracy(
            predicted_days=torch.tensor([1.0, 100.0]),
            observed_days=torch.tensor([100.0, 1.0]),
        )
        assert 0.0 <= acc.item() <= 1.0


class TestTrustBias:
    def test_zero_bias(self) -> None:
        bias = compute_trust_bias(
            trust_scores=torch.tensor([0.8, 0.9]),
            actual_reliability=torch.tensor([0.8, 0.9]),
        )
        assert bias.item() == pytest.approx(0.0, abs=1e-6)


class TestCalibrationScore:
    def test_perfect_calibration(self) -> None:
        observed = torch.tensor([2.0, 3.0, 4.0, 5.0, 6.0])
        p10 = torch.tensor([1.0, 1.0, 1.0, 1.0, 1.0])
        p90 = torch.tensor([10.0, 10.0, 10.0, 10.0, 10.0])
        score = compute_calibration_score(observed, p10, p90)
        assert score.item() > 0.5
