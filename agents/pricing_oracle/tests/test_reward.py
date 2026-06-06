"""
SYNAPSE Pricing Oracle -- Reward function unit tests.
Verifies I-2 (independent reward) and reward component correctness.
"""

from __future__ import annotations

import ast
from pathlib import Path

import torch

from agents.pricing_oracle.training.rewards import (
    competitor_gap,
    compute_reward,
    elasticity_alignment,
    essential_cap_violation,
    revenue_component,
)


class TestRewardIsolation:
    """Verify I-2: No cross-agent imports in rewards.py."""

    def test_no_cross_agent_imports(self) -> None:
        rewards_path = Path("agents/pricing_oracle/training/rewards.py")
        tree = ast.parse(rewards_path.read_text())

        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                assert "agents." not in node.module or "pricing_oracle" in node.module, (
                    f"Cross-agent import detected: {node.module} -- violates I-2"
                )

    def test_no_synapse_common_model_imports(self) -> None:
        """Reward function must not import domain models to stay self-contained."""
        rewards_path = Path("agents/pricing_oracle/training/rewards.py")
        tree = ast.parse(rewards_path.read_text())

        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                assert "synapse_common.models" not in node.module, (
                    "Reward function imports synapse_common.models -- violates I-2 isolation"
                )


class TestRevenueComponent:
    def test_positive_revenue(self) -> None:
        mult = torch.tensor([1.2, 1.1, 1.0])
        base = torch.tensor([100.0, 50.0, 200.0])
        demand = torch.tensor([10.0, 20.0, 5.0])
        rev = revenue_component(mult, base, demand)
        assert rev > 0

    def test_dimensionless_baseline_weighted_revenue(self) -> None:
        mult = torch.tensor([[1.5, 1.0], [0.5, 1.0]])
        base = torch.tensor([[100.0, 100.0], [50.0, 150.0]])
        demand = torch.tensor([[2.0, 2.0], [4.0, 4.0]])
        rev = revenue_component(mult, base, demand)
        assert torch.isclose(rev, torch.tensor(1.0625), atol=1e-6).item()

    def test_zero_demand_zero_revenue(self) -> None:
        mult = torch.tensor([1.5, 1.2])
        base = torch.tensor([100.0, 50.0])
        demand = torch.tensor([0.0, 0.0])
        rev = revenue_component(mult, base, demand)
        assert rev.item() == 0.0


class TestElasticityAlignment:
    def test_alignment_returns_tensor(self) -> None:
        mult = torch.tensor([1.0, 1.5, 0.8])
        elast = torch.tensor([-0.5, -2.0, -0.3])
        result = elasticity_alignment(mult, elast)
        assert isinstance(result, torch.Tensor)

    def test_constant_inputs_return_zero(self) -> None:
        mult = torch.ones(10)
        elast = torch.ones(10) * -1.0
        result = elasticity_alignment(mult, elast)
        assert result.item() == 0.0

    def test_population_correlation_penalizes_matching_elasticity_order(self) -> None:
        mult = torch.tensor([1.0, 2.0, 3.0])
        elast = torch.tensor([-1.0, -2.0, -3.0])
        result = elasticity_alignment(mult, elast)
        assert torch.isclose(result, torch.tensor(-1.0), atol=1e-6).item()

    def test_population_correlation_rewards_inverse_elasticity_order(self) -> None:
        mult = torch.tensor([1.0, 2.0, 3.0])
        elast = torch.tensor([-3.0, -2.0, -1.0])
        result = elasticity_alignment(mult, elast)
        assert torch.isclose(result, torch.tensor(1.0), atol=1e-6).item()

    def test_single_sample_returns_finite_zero(self) -> None:
        mult = torch.tensor([1.5])
        elast = torch.tensor([-1.0])
        result = elasticity_alignment(mult, elast)
        assert torch.isfinite(result)
        assert result.item() == 0.0


class TestEssentialCapViolation:
    def test_no_violation_within_cap(self) -> None:
        mult = torch.tensor([1.0, 1.2, 1.3])
        is_essential = torch.tensor([1.0, 1.0, 1.0])
        violation = essential_cap_violation(mult, is_essential)
        assert violation.item() == 0.0

    def test_violation_above_cap(self) -> None:
        mult = torch.tensor([1.5, 1.4])
        is_essential = torch.tensor([1.0, 1.0])
        violation = essential_cap_violation(mult, is_essential)
        assert violation.item() > 0.0

    def test_cap_violation_uses_catastrophic_units(self) -> None:
        mult = torch.tensor([1.3, 1.56, 2.6, 0.9])
        is_essential = torch.tensor([1.0, 1.0, 0.0, 1.0])
        violation = essential_cap_violation(mult, is_essential)
        assert torch.isclose(violation, torch.tensor(1.2), atol=1e-6).item()

    def test_non_essential_not_penalized(self) -> None:
        mult = torch.tensor([2.0, 2.5])
        is_essential = torch.tensor([0.0, 0.0])
        violation = essential_cap_violation(mult, is_essential)
        assert violation.item() == 0.0

    def test_catastrophic_penalty_weight(self) -> None:
        """Essential cap violation with -5.0 weight makes reward catastrophically negative."""
        mult = torch.tensor([1.5])
        base = torch.tensor([100.0])
        demand = torch.tensor([10.0])
        elast = torch.tensor([-1.0])
        is_essential = torch.tensor([1.0])

        result = compute_reward(
            multipliers=mult,
            base_prices=base,
            demand_quantities=demand,
            elasticity_estimates=elast,
            is_essential=is_essential,
        )

        assert result["essential_cap_violation"].item() > 0
        assert result["total_reward"].item() < 0, (
            "Essential cap violation must make total reward negative"
        )


class TestCompetitorGap:
    def test_no_gap_when_below_competitor(self) -> None:
        mult = torch.tensor([1.0, 0.9])
        comp = torch.tensor([1.2, 1.1])
        gap = competitor_gap(mult, comp)
        assert gap.item() == 0.0

    def test_gap_when_above_competitor(self) -> None:
        mult = torch.tensor([1.5, 1.3])
        comp = torch.tensor([1.0, 1.0])
        gap = competitor_gap(mult, comp)
        assert gap.item() > 0.0

    def test_gap_is_one_sided_mean_excess(self) -> None:
        mult = torch.tensor([1.5, 1.0, 0.7])
        comp = torch.tensor([1.0, 1.2, 0.5])
        gap = competitor_gap(mult, comp)
        assert torch.isclose(gap, torch.tensor(0.7 / 3.0), atol=1e-6).item()


class TestComputeReward:
    def test_reward_components(self) -> None:
        mult = torch.tensor([1.2, 1.1, 1.0])
        base = torch.tensor([100.0, 50.0, 200.0])
        demand = torch.tensor([10.0, 20.0, 5.0])
        elast = torch.tensor([-0.5, -1.2, -0.8])
        is_essential = torch.tensor([1.0, 0.0, 0.0])
        comp = torch.tensor([1.15, 1.1, 1.05])

        result = compute_reward(
            multipliers=mult,
            base_prices=base,
            demand_quantities=demand,
            elasticity_estimates=elast,
            is_essential=is_essential,
            competitor_multipliers=comp,
        )

        assert "total_reward" in result
        assert "revenue" in result
        assert "elasticity_alignment" in result
        assert "essential_cap_violation" in result
        assert "competitor_gap" in result

    def test_no_competitor_data(self) -> None:
        mult = torch.tensor([1.1, 1.2])
        base = torch.tensor([100.0, 50.0])
        demand = torch.tensor([10.0, 20.0])
        elast = torch.tensor([-1.0, -0.5])
        is_essential = torch.tensor([0.0, 0.0])

        result = compute_reward(
            multipliers=mult,
            base_prices=base,
            demand_quantities=demand,
            elasticity_estimates=elast,
            is_essential=is_essential,
            competitor_multipliers=None,
        )

        assert result["competitor_gap"].item() == 0.0

    def test_default_weights_use_exact_dimensionless_components(self) -> None:
        mult = torch.tensor([1.0, 2.0, 3.0])
        base = torch.tensor([10.0, 10.0, 10.0])
        demand = torch.tensor([1.0, 1.0, 1.0])
        elast = torch.tensor([-3.0, -2.0, -1.0])
        is_essential = torch.tensor([0.0, 0.0, 0.0])
        comp = torch.tensor([0.5, 2.5, 2.0])

        result = compute_reward(
            multipliers=mult,
            base_prices=base,
            demand_quantities=demand,
            elasticity_estimates=elast,
            is_essential=is_essential,
            competitor_multipliers=comp,
        )

        assert torch.isclose(result["revenue"], torch.tensor(2.0), atol=1e-6).item()
        assert torch.isclose(result["elasticity_alignment"], torch.tensor(1.0), atol=1e-6).item()
        assert torch.isclose(result["competitor_gap"], torch.tensor(0.5), atol=1e-6).item()
        assert torch.isclose(result["total_reward"], torch.tensor(1.5), atol=1e-6).item()

    def test_essential_cap_penalty_dominates_normalized_revenue(self) -> None:
        result = compute_reward(
            multipliers=torch.tensor([1.31, 1.0]),
            base_prices=torch.tensor([100.0, 100.0]),
            demand_quantities=torch.tensor([1.0, 1.0]),
            elasticity_estimates=torch.tensor([-1.0, -1.0]),
            is_essential=torch.tensor([1.0, 0.0]),
        )

        assert torch.isclose(
            result["essential_cap_violation"], torch.tensor(1.0076923), atol=1e-6
        ).item()
        assert torch.isclose(result["total_reward"], torch.tensor(-3.8834615), atol=1e-6).item()
