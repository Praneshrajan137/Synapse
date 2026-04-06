"""
SYNAPSE Pricing Oracle -- Model unit tests.
Verifies MADDPG forward pass, essential cap enforcement, and causal elasticity.
"""
from __future__ import annotations

import math

import numpy as np
import pytest
import torch

from agents.pricing_oracle.models.maddpg import (
    CATEGORIES,
    ESSENTIAL_CAP,
    MIN_MULTIPLIER,
    ActorNetwork,
    CriticNetwork,
    PricingMADDPG,
)


class TestActorNetwork:
    """Tests for the per-category actor network."""

    def test_forward_pass_shape(self) -> None:
        actor = ActorNetwork(obs_dim=24, action_dim=1, hidden_dim=64, num_layers=2)
        obs = torch.randn(8, 24)
        actions = actor(obs)
        assert actions.shape == (8, 1)

    def test_output_in_valid_range(self) -> None:
        actor = ActorNetwork(obs_dim=24, action_dim=1, hidden_dim=64, num_layers=2)
        obs = torch.randn(100, 24)
        actions = actor(obs)
        assert (actions >= MIN_MULTIPLIER).all()
        assert (actions <= 2.5).all()


class TestCriticNetwork:
    """Tests for the centralised critic network."""

    def test_forward_pass_shape(self) -> None:
        total_obs = 5 * 24
        total_act = 5 * 1
        critic = CriticNetwork(total_obs, total_act, hidden_dim=64, num_layers=2)
        obs_all = torch.randn(8, total_obs)
        act_all = torch.randn(8, total_act)
        q_values = critic(obs_all, act_all)
        assert q_values.shape == (8, 1)


class TestPricingMADDPG:
    """Tests for the full MADDPG model."""

    @pytest.fixture()
    def model(self) -> PricingMADDPG:
        return PricingMADDPG(
            num_agents=5,
            obs_dim=24,
            action_dim=1,
            actor_hidden_dim=64,
            actor_num_layers=2,
            critic_hidden_dim=64,
            critic_num_layers=2,
        )

    @pytest.fixture()
    def dummy_observations(self) -> dict[str, torch.Tensor]:
        return {cat: torch.randn(4, 24) for cat in CATEGORIES}

    def test_forward_pass(
        self, model: PricingMADDPG, dummy_observations: dict[str, torch.Tensor]
    ) -> None:
        actions = model.forward(dummy_observations)
        assert set(actions.keys()) == set(CATEGORIES)
        for cat, act in actions.items():
            assert act.shape == (4, 1), f"Category {cat}: expected (4, 1)"

    def test_essential_cap_enforced_in_forward(
        self, model: PricingMADDPG, dummy_observations: dict[str, torch.Tensor]
    ) -> None:
        """INV-PO-001: Essential multiplier MUST be <= 1.3 after forward pass."""
        for _ in range(10):
            actions = model.forward(dummy_observations)
            essential_actions = actions["essential"]
            assert (essential_actions <= ESSENTIAL_CAP).all(), (
                f"INV-PO-001 violated: essential multiplier {essential_actions.max().item()} > {ESSENTIAL_CAP}"
            )

    def test_essential_cap_enforced_in_select_actions(
        self, model: PricingMADDPG, dummy_observations: dict[str, torch.Tensor]
    ) -> None:
        """INV-PO-001: Essential cap holds even with exploration noise."""
        for noise in [0.0, 0.1, 0.5, 1.0, 5.0]:
            actions = model.select_actions(dummy_observations, noise_scale=noise)
            essential = actions["essential"]
            assert (essential <= ESSENTIAL_CAP).all(), (
                f"INV-PO-001 violated with noise={noise}: max={essential.max().item()}"
            )

    def test_all_multipliers_positive(
        self, model: PricingMADDPG, dummy_observations: dict[str, torch.Tensor]
    ) -> None:
        """INV-PO-002: All multipliers must be strictly positive."""
        actions = model.forward(dummy_observations)
        for cat, act in actions.items():
            assert (act > 0).all(), f"INV-PO-002 violated for {cat}"

    def test_soft_update(self, model: PricingMADDPG) -> None:
        pre_target = [p.clone() for p in model.target_actors[0].parameters()]
        model.soft_update(tau=0.5)
        for old, new in zip(pre_target, model.target_actors[0].parameters(), strict=True):
            assert not torch.equal(old, new), "Target network should have changed after soft update"

    def test_model_summary(self, model: PricingMADDPG) -> None:
        summary = model.get_model_summary()
        assert summary["total_trainable"] > 0
        assert summary["num_agents"] == 5
        assert summary["actor_params"] > 0
        assert summary["critic_params"] > 0

    def test_deterministic_output(
        self, model: PricingMADDPG, dummy_observations: dict[str, torch.Tensor]
    ) -> None:
        model.eval()
        with torch.no_grad():
            out1 = model.forward(dummy_observations)
            out2 = model.forward(dummy_observations)
        for cat in CATEGORIES:
            assert torch.allclose(out1[cat], out2[cat]), (
                f"Non-deterministic output for {cat}"
            )

    def test_enforce_essential_cap_utility(self) -> None:
        assert PricingMADDPG.enforce_essential_cap(1.5) == ESSENTIAL_CAP
        assert PricingMADDPG.enforce_essential_cap(1.0) == 1.0
        assert PricingMADDPG.enforce_essential_cap(0.3) == MIN_MULTIPLIER


class TestCausalElasticity:
    """Tests for the causal elasticity estimator."""

    def test_validate_elasticity_finite(self) -> None:
        from agents.pricing_oracle.models.causal import CausalElasticityEstimator

        assert CausalElasticityEstimator.validate_elasticity(-1.5) is True
        assert CausalElasticityEstimator.validate_elasticity(0.0) is True
        assert CausalElasticityEstimator.validate_elasticity(float("inf")) is False
        assert CausalElasticityEstimator.validate_elasticity(float("nan")) is False

    def test_unfitted_raises(self) -> None:
        from agents.pricing_oracle.models.causal import CausalElasticityEstimator

        estimator = CausalElasticityEstimator()
        with pytest.raises(RuntimeError, match="fitted"):
            estimator.estimate_elasticity(np.zeros((5, 3)))

    def test_is_fitted_flag(self) -> None:
        from agents.pricing_oracle.models.causal import CausalElasticityEstimator

        estimator = CausalElasticityEstimator()
        assert estimator.is_fitted is False
