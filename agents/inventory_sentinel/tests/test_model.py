"""SYNAPSE Inventory Sentinel -- Model unit tests."""
from __future__ import annotations

import torch

from agents.inventory_sentinel.models.operational import OperationalAgent
from agents.inventory_sentinel.models.strategic import StrategicAgent
from agents.inventory_sentinel.models.tactical import TacticalAgent


class TestStrategicAgent:
    def test_forward_pass(self) -> None:
        model = StrategicAgent(obs_dim=100, hidden_dim=64, action_dim=20)
        obs = torch.randn(4, 100)
        action, value = model(obs)
        assert action.shape == (4, 20)
        assert value.shape == (4, 1)


class TestTacticalAgent:
    def test_forward_pass(self) -> None:
        model = TacticalAgent(obs_dim=50, hidden_dim=32, l1_dim=20)
        obs = torch.randn(4, 50)
        l1_out = torch.randn(4, 20)
        result = model(obs, l1_out)
        assert "reorder_point" in result
        assert "safety_stock_multiplier" in result
        assert "qty_logits" in result
        assert "value" in result

    def test_safety_stock_bounds(self) -> None:
        """INV-IS-001: safety stock in [1.0, 3.0]."""
        model = TacticalAgent(obs_dim=50, hidden_dim=32, l1_dim=20)
        obs = torch.randn(100, 50)
        l1_out = torch.randn(100, 20)
        result = model(obs, l1_out)
        ssm = result["safety_stock_multiplier"]
        assert (ssm >= 1.0).all(), f"Min safety stock: {ssm.min()}"
        assert (ssm <= 3.0).all(), f"Max safety stock: {ssm.max()}"


class TestOperationalAgent:
    def test_forward_pass(self) -> None:
        model = OperationalAgent(obs_dim=30, hidden_dim=32, max_skus=50)
        obs = torch.randn(2, 30)
        scores = model(obs)
        assert scores.shape == (2, 50)

    def test_ranking_unique(self) -> None:
        model = OperationalAgent(obs_dim=30, hidden_dim=32, max_skus=50)
        obs = torch.randn(1, 30)
        ranking = model.get_ranking(obs, num_skus=10)
        assert ranking.shape == (1, 10)
        assert len(ranking[0].unique()) == 10
