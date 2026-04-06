"""
SYNAPSE Disruption Shield — Reward function tests.
Verifies I-2 (independent reward) and reward component correctness.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest
import torch

from agents.disruption_shield.training.rewards import compute_reward

_REWARDS_PATH = Path(__file__).resolve().parents[1] / "training" / "rewards.py"


class TestRewardIsolation:
    """Verify I-2: No cross-agent imports in rewards.py."""

    def test_inv_ds_004_no_cross_agent_imports(self) -> None:
        tree = ast.parse(_REWARDS_PATH.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                assert "agents." not in node.module or "disruption_shield" in node.module, (
                    f"Cross-agent import: {node.module} — violates I-2"
                )


class TestRewardComponents:
    """Test individual reward components."""

    def test_reward_returns_all_components(self) -> None:
        result = compute_reward(
            predicted_alert=torch.tensor([1.0, 0.0, 1.0, 0.0]),
            actual_disruption=torch.tensor([1.0, 0.0, 0.0, 1.0]),
            hours_before_impact=torch.tensor([24.0, 0.0, 0.0, 0.0]),
            time_to_recovery_hours=torch.tensor([12.0, 48.0, 48.0, 48.0]),
            playbook_applied=torch.tensor([1.0, 0.0, 0.0, 0.0]),
        )
        assert "total_reward" in result
        assert "early_detection" in result
        assert "false_positive" in result
        assert "missed_disruption" in result
        assert "recovery_speed" in result

    def test_perfect_detection_positive_reward(self) -> None:
        result = compute_reward(
            predicted_alert=torch.tensor([1.0, 1.0]),
            actual_disruption=torch.tensor([1.0, 1.0]),
            hours_before_impact=torch.tensor([48.0, 36.0]),
            time_to_recovery_hours=torch.tensor([6.0, 12.0]),
            playbook_applied=torch.tensor([1.0, 1.0]),
        )
        assert result["total_reward"] > 0
        assert result["false_positive"] == 0.0
        assert result["missed_disruption"] == 0.0

    def test_missed_disruption_severe_penalty(self) -> None:
        result_detected = compute_reward(
            predicted_alert=torch.tensor([1.0]),
            actual_disruption=torch.tensor([1.0]),
            hours_before_impact=torch.tensor([24.0]),
            time_to_recovery_hours=torch.tensor([12.0]),
            playbook_applied=torch.tensor([1.0]),
        )
        result_missed = compute_reward(
            predicted_alert=torch.tensor([0.0]),
            actual_disruption=torch.tensor([1.0]),
            hours_before_impact=torch.tensor([0.0]),
            time_to_recovery_hours=torch.tensor([48.0]),
            playbook_applied=torch.tensor([0.0]),
        )
        assert result_missed["total_reward"] < result_detected["total_reward"]

    def test_false_positive_penalized(self) -> None:
        result_clean = compute_reward(
            predicted_alert=torch.tensor([0.0]),
            actual_disruption=torch.tensor([0.0]),
            hours_before_impact=torch.tensor([0.0]),
            time_to_recovery_hours=torch.tensor([48.0]),
            playbook_applied=torch.tensor([0.0]),
        )
        result_fp = compute_reward(
            predicted_alert=torch.tensor([1.0]),
            actual_disruption=torch.tensor([0.0]),
            hours_before_impact=torch.tensor([0.0]),
            time_to_recovery_hours=torch.tensor([48.0]),
            playbook_applied=torch.tensor([0.0]),
        )
        assert result_fp["total_reward"] < result_clean["total_reward"]

    def test_early_detection_rewarded(self) -> None:
        result_late = compute_reward(
            predicted_alert=torch.tensor([1.0]),
            actual_disruption=torch.tensor([1.0]),
            hours_before_impact=torch.tensor([1.0]),
            time_to_recovery_hours=torch.tensor([24.0]),
            playbook_applied=torch.tensor([1.0]),
        )
        result_early = compute_reward(
            predicted_alert=torch.tensor([1.0]),
            actual_disruption=torch.tensor([1.0]),
            hours_before_impact=torch.tensor([72.0]),
            time_to_recovery_hours=torch.tensor([24.0]),
            playbook_applied=torch.tensor([1.0]),
        )
        assert result_early["early_detection"] >= result_late["early_detection"]
