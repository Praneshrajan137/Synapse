"""
SYNAPSE Sustainability Agent -- Reward function unit tests.
Verifies I-2 (independent reward) and reward component correctness.
"""
from __future__ import annotations

import ast
from pathlib import Path

from agents.sustainability_agent.training.rewards import (
    carbon_penalty,
    compute_reward,
    prediction_accuracy_bonus,
    waste_rate_penalty,
)


class TestRewardIsolation:
    """Verify I-2: No cross-agent imports in rewards.py."""

    def test_no_cross_agent_imports(self) -> None:
        rewards_path = Path("agents/sustainability_agent/training/rewards.py")
        tree = ast.parse(rewards_path.read_text())

        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                assert "agents." not in node.module or "sustainability_agent" in node.module, (
                    f"Cross-agent import detected: {node.module} -- violates I-2"
                )

    def test_no_torch_dependency(self) -> None:
        """Sustainability reward uses plain Python, not torch tensors."""
        rewards_path = Path("agents/sustainability_agent/training/rewards.py")
        tree = ast.parse(rewards_path.read_text())

        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                assert "torch" not in node.module, (
                    "Sustainability reward should use plain Python math"
                )


class TestCarbonPenalty:
    def test_zero_emissions(self) -> None:
        assert carbon_penalty(0.0, baseline_co2_kg=1.0) == 0.0

    def test_baseline_emissions(self) -> None:
        assert carbon_penalty(1.0, baseline_co2_kg=1.0) == 1.0

    def test_double_emissions(self) -> None:
        assert carbon_penalty(2.0, baseline_co2_kg=1.0) == 2.0

    def test_invalid_baseline_raises(self) -> None:
        import pytest

        with pytest.raises(ValueError):
            carbon_penalty(1.0, baseline_co2_kg=0.0)


class TestWasteRatePenalty:
    def test_no_waste(self) -> None:
        assert waste_rate_penalty(0, 100) == 0.0

    def test_total_waste(self) -> None:
        assert waste_rate_penalty(100, 100) == 1.0

    def test_partial_waste(self) -> None:
        rate = waste_rate_penalty(25, 100)
        assert rate == 0.25

    def test_zero_items(self) -> None:
        assert waste_rate_penalty(0, 0) == 0.0


class TestPredictionAccuracy:
    def test_perfect_prediction(self) -> None:
        assert prediction_accuracy_bonus(1.0, 1.0) == 1.0

    def test_within_tolerance(self) -> None:
        bonus = prediction_accuracy_bonus(1.05, 1.0, tolerance=0.1)
        assert bonus > 0.0

    def test_outside_tolerance(self) -> None:
        bonus = prediction_accuracy_bonus(2.0, 1.0, tolerance=0.1)
        assert bonus == 0.0

    def test_zero_actual(self) -> None:
        assert prediction_accuracy_bonus(0.0, 0.0) == 1.0
        assert prediction_accuracy_bonus(1.0, 0.0) == 0.0


class TestComputeReward:
    def test_reward_components(self) -> None:
        result = compute_reward(
            co2_kg=1.0,
            items_wasted=10,
            items_total=100,
            predicted_co2_kg=1.0,
            actual_co2_kg=1.0,
        )
        assert "total_reward" in result
        assert "carbon_penalty" in result
        assert "waste_rate" in result
        assert "prediction_accuracy" in result

    def test_perfect_scenario(self) -> None:
        result = compute_reward(
            co2_kg=0.0,
            items_wasted=0,
            items_total=100,
            predicted_co2_kg=0.0,
            actual_co2_kg=0.0,
        )
        assert result["carbon_penalty"] == 0.0
        assert result["waste_rate"] == 0.0
        assert result["prediction_accuracy"] == 1.0
        assert result["total_reward"] > 0.0

    def test_worst_scenario(self) -> None:
        result = compute_reward(
            co2_kg=10.0,
            items_wasted=100,
            items_total=100,
            predicted_co2_kg=0.0,
            actual_co2_kg=10.0,
        )
        assert result["total_reward"] < 0.0

    def test_reward_formula(self) -> None:
        """Verify R = -carbon_weight*carbon - waste_weight*waste + accuracy_weight*accuracy."""
        result = compute_reward(
            co2_kg=2.0,
            items_wasted=20,
            items_total=100,
            predicted_co2_kg=2.0,
            actual_co2_kg=2.0,
            baseline_co2_kg=1.0,
            carbon_weight=1.0,
            waste_weight=0.5,
            accuracy_weight=0.3,
        )
        expected = -1.0 * 2.0 - 0.5 * 0.2 + 0.3 * 1.0
        assert abs(result["total_reward"] - expected) < 1e-6
