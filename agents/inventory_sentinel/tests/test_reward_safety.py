"""Inventory Sentinel reward-hacking counterfactual tests (Sprint 13 §Phase 1.1).

Three independent reward functions (L1 strategic, L2 tactical, L3 operational)
per I-2. Each scenario constructs an input designed to game one component and
asserts the reward either fails to improve or moves in the corrected direction.

Plus mutation-survival hardening per CLAUDE.md "Mutation survival <15% rewards":
- Reward orientation (better metrics produce strictly higher reward by a margin)
- Coefficient preservation (specific reward values pin the formula)
- Sign preservation (a known-good vs known-bad bracket cannot collapse)
"""

from __future__ import annotations

import pytest
import torch

from agents.inventory_sentinel.training.rewards import (
    compute_l1_strategic_reward,
    compute_l2_tactical_reward,
    compute_l3_operational_reward,
)

# --- counterfactual 1: a stockout cannot be hidden by higher fill_rate -------


def test_stockout_dominates_fill_rate_gain() -> None:
    """L1 weights stockout at -2.0 and fill_rate at +1.0. A single stockout
    must out-cost any fill-rate improvement smaller than 2.0 percentage points.
    Mutant `-2.0` → `-1.0` survives only if this margin is enforced."""
    no_stockout = compute_l1_strategic_reward(
        fill_rate=torch.tensor(0.95),
        holding_cost=torch.tensor(0.1),
        stockout_count=torch.tensor(0.0),
        waste_rate=torch.tensor(0.02),
    )["total_reward"]
    with_stockout = compute_l1_strategic_reward(
        fill_rate=torch.tensor(0.96),  # better fill rate by 0.01
        holding_cost=torch.tensor(0.1),
        stockout_count=torch.tensor(1.0),  # but a stockout
        waste_rate=torch.tensor(0.02),
    )["total_reward"]
    # No-stockout must beat with-stockout by at least 1.9 (≈ 2.0 stockout cost minus 0.01 fill bonus)
    assert no_stockout.item() > with_stockout.item() + 1.5, (
        f"Stockout-penalty coefficient too weak (no_stockout={no_stockout}, "
        f"with_stockout={with_stockout}); mutant on the -2.0 coefficient may survive"
    )


# --- counterfactual 2: L1 reward formula pinned numerically ------------------


def test_l1_formula_exact_value() -> None:
    """Pin the L1 formula: R = fill_rate - 0.3*holding_cost - 2.0*stockout - 0.5*waste.
    Concrete coefficients catch any mutation to the constants."""
    result = compute_l1_strategic_reward(
        fill_rate=torch.tensor(1.0),
        holding_cost=torch.tensor(1.0),
        stockout_count=torch.tensor(1.0),
        waste_rate=torch.tensor(1.0),
    )["total_reward"]
    # 1.0 - 0.3 - 2.0 - 0.5 = -1.8
    assert result.item() == pytest.approx(-1.8, abs=1e-6), (
        f"L1 formula deviated from expected -1.8 (got {result.item()}); coefficient mutated?"
    )


# --- counterfactual 3: perishable_waste outweighs holding_cost in L2 ---------


def test_l2_perishable_waste_outweighs_holding_cost() -> None:
    """L2: holding_cost coeff = -0.4, perishable_waste coeff = -3.0.
    The 7.5× ratio must be visible in the reward delta."""
    light_waste = compute_l2_tactical_reward(
        service_level=torch.tensor(0.9),
        freshness_score=torch.tensor(0.8),
        holding_cost=torch.tensor(1.0),
        perishable_waste=torch.tensor(0.1),
    )["total_reward"]
    heavy_waste = compute_l2_tactical_reward(
        service_level=torch.tensor(0.9),
        freshness_score=torch.tensor(0.8),
        holding_cost=torch.tensor(0.5),  # half the holding cost
        perishable_waste=torch.tensor(0.3),  # but 3x the perishable waste
    )["total_reward"]
    # delta_holding = -0.4 * (-0.5) = +0.20 ; delta_waste = -3.0 * (+0.2) = -0.60
    # heavy_waste should be ~0.40 lower
    assert light_waste.item() > heavy_waste.item() + 0.3, (
        f"perishable_waste/holding_cost coefficient ratio collapsed "
        f"(light={light_waste}, heavy={heavy_waste})"
    )


# --- counterfactual 4: L2 formula pinned numerically -------------------------


def test_l2_formula_exact_value() -> None:
    """R = service_level + freshness - 0.4*holding - 3.0*perishable_waste."""
    result = compute_l2_tactical_reward(
        service_level=torch.tensor(0.5),
        freshness_score=torch.tensor(0.5),
        holding_cost=torch.tensor(1.0),
        perishable_waste=torch.tensor(0.1),
    )["total_reward"]
    # 0.5 + 0.5 - 0.4 - 0.3 = 0.3
    assert result.item() == pytest.approx(0.3, abs=1e-6)


# --- counterfactual 5: L3 reward is minus pick time plus freshness bonus -----


def test_l3_pick_time_sign() -> None:
    """L3: R = -avg_pick_time + freshness_exposure. Sign on pick_time is
    negative — slower picks must reduce reward."""
    fast = compute_l3_operational_reward(
        avg_pick_time=torch.tensor(1.0),
        freshness_exposure=torch.tensor(2.0),
    )["total_reward"]
    slow = compute_l3_operational_reward(
        avg_pick_time=torch.tensor(5.0),
        freshness_exposure=torch.tensor(2.0),
    )["total_reward"]
    assert fast.item() > slow.item() + 3.5, (
        f"L3 pick-time penalty sign or magnitude broken (fast={fast}, slow={slow}); "
        f"mutant `-avg_pick_time` → `+avg_pick_time` would survive without this margin"
    )


# --- counterfactual 6: waste_rate inflation cannot be hidden -----------------


@pytest.mark.parametrize("waste_inflation", [0.1, 0.5, 1.0])
def test_higher_waste_strictly_lowers_l1_reward(waste_inflation: float) -> None:
    """L1 must be strictly monotone-decreasing in waste_rate."""
    base = compute_l1_strategic_reward(
        fill_rate=torch.tensor(0.9),
        holding_cost=torch.tensor(0.1),
        stockout_count=torch.tensor(0.0),
        waste_rate=torch.tensor(0.05),
    )["total_reward"]
    inflated = compute_l1_strategic_reward(
        fill_rate=torch.tensor(0.9),
        holding_cost=torch.tensor(0.1),
        stockout_count=torch.tensor(0.0),
        waste_rate=torch.tensor(0.05 + waste_inflation),
    )["total_reward"]
    assert inflated.item() < base.item(), (
        f"L1 reward not monotone-decreasing in waste_rate (base={base}, inflated={inflated})"
    )


# --- counterfactual 7: total_reward key is preserved across all 3 levels -----


def test_total_reward_key_present_all_levels() -> None:
    """A mutant that drops the 'total_reward' key from the returned dict
    must be caught by every consumer downstream — pin the contract here."""
    l1 = compute_l1_strategic_reward(
        fill_rate=torch.tensor(0.9),
        holding_cost=torch.tensor(0.1),
        stockout_count=torch.tensor(0.0),
        waste_rate=torch.tensor(0.05),
    )
    l2 = compute_l2_tactical_reward(
        service_level=torch.tensor(0.9),
        freshness_score=torch.tensor(0.8),
        holding_cost=torch.tensor(0.2),
        perishable_waste=torch.tensor(0.01),
    )
    l3 = compute_l3_operational_reward(
        avg_pick_time=torch.tensor(1.0),
        freshness_exposure=torch.tensor(2.0),
    )
    for level, result in (("L1", l1), ("L2", l2), ("L3", l3)):
        assert "total_reward" in result, f"{level} missing 'total_reward' key"
        assert isinstance(result["total_reward"], torch.Tensor), (
            f"{level} total_reward not a tensor — return-type mutated?"
        )
