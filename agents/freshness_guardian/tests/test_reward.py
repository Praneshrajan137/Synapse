"""
SYNAPSE Freshness Guardian — Reward function tests.
Verifies I-2 (independent reward) and reward component correctness.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest
import torch

from agents.freshness_guardian.training.rewards import compute_reward

_REWARDS_PATH = Path(__file__).resolve().parents[1] / "training" / "rewards.py"


class TestRewardIsolation:
    """Verify I-2: No cross-agent imports in rewards.py."""

    def test_inv_fg_006_no_cross_agent_imports(self) -> None:
        tree = ast.parse(_REWARDS_PATH.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                assert "agents." not in node.module or "freshness_guardian" in node.module, (
                    f"Cross-agent import: {node.module} — violates I-2"
                )


class TestRewardComponents:
    """Test individual reward components."""

    def test_reward_returns_all_components(self) -> None:
        result = compute_reward(
            predicted_quality=torch.tensor([0.8, 0.6, 0.4]),
            actual_quality=torch.tensor([0.85, 0.55, 0.35]),
            markdown_applied=torch.tensor([0.0, 1.0, 1.0]),
            days_to_expiry=torch.tensor([10.0, 3.0, 0.5]),
            was_sold=torch.tensor([1.0, 1.0, 0.0]),
            temperature_deviation_hours=torch.tensor([0.0, 2.0, 6.0]),
            fssai_logged=torch.tensor([1.0, 1.0, 0.0]),
        )
        assert "total_reward" in result
        assert "freshness_accuracy" in result
        assert "markdown_timing" in result
        assert "fssai_violation" in result
        assert "unnecessary_markdown" in result

    def test_fssai_violation_penalized(self) -> None:
        result_compliant = compute_reward(
            predicted_quality=torch.tensor([0.8]),
            actual_quality=torch.tensor([0.8]),
            markdown_applied=torch.tensor([0.0]),
            days_to_expiry=torch.tensor([10.0]),
            was_sold=torch.tensor([1.0]),
            temperature_deviation_hours=torch.tensor([1.0]),
            fssai_logged=torch.tensor([1.0]),
        )
        result_violation = compute_reward(
            predicted_quality=torch.tensor([0.8]),
            actual_quality=torch.tensor([0.8]),
            markdown_applied=torch.tensor([0.0]),
            days_to_expiry=torch.tensor([10.0]),
            was_sold=torch.tensor([1.0]),
            temperature_deviation_hours=torch.tensor([10.0]),
            fssai_logged=torch.tensor([0.0]),
        )
        assert result_violation["total_reward"] < result_compliant["total_reward"]
