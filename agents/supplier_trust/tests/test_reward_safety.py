"""Supplier Trust reward-hacking counterfactual tests (Sprint 13 §Phase 1.1).

Reward formula: R = prediction_accuracy - 2.0 * trust_bias + 0.5 * calibration

Each scenario constructs an input designed to game one component and asserts the
reward fails to improve or moves in the corrected direction. Plus mutation-
survival hardening per CLAUDE.md "Mutation survival <15% rewards":
- Coefficient preservation (concrete numeric values pin formula)
- Sign preservation (penalty cannot become bonus)
- Bound preservation (accuracy and calibration clamps cannot be removed)
"""

from __future__ import annotations

import pytest
import torch

from agents.supplier_trust.training.rewards import (
    compute_calibration_score,
    compute_prediction_accuracy,
    compute_supplier_trust_reward,
    compute_trust_bias,
)


# --- counterfactual 1: trust_bias cannot be exchanged for accuracy -----------


def test_trust_bias_penalty_dominates_accuracy_gain() -> None:
    """Coefficients: accuracy=+1.0, bias=-2.0. A 0.1 bias increase (cost = 0.2)
    must outweigh a 0.1 accuracy gain (benefit = 0.1). The 2× ratio is the
    safety margin against mutation on the -2.0 coefficient."""
    low_bias = compute_supplier_trust_reward(
        prediction_accuracy=torch.tensor(0.8),
        trust_bias=torch.tensor(0.05),
        calibration=torch.tensor(0.7),
    )["total_reward"]
    higher_bias_higher_acc = compute_supplier_trust_reward(
        prediction_accuracy=torch.tensor(0.9),  # +0.1 accuracy
        trust_bias=torch.tensor(0.15),  # +0.1 bias (costs 0.2)
        calibration=torch.tensor(0.7),
    )["total_reward"]
    # Net: +0.1 (acc) - 0.2 (bias) = -0.1
    assert low_bias.item() > higher_bias_higher_acc.item() + 0.05, (
        f"trust_bias penalty insufficient to dominate matching accuracy gain "
        f"(low_bias={low_bias}, higher_bias={higher_bias_higher_acc}); "
        f"mutant on -2.0 coefficient may survive"
    )


# --- counterfactual 2: reward formula pinned numerically ---------------------


def test_reward_formula_exact_value() -> None:
    """Pin R = accuracy - 2.0*bias + 0.5*calibration with concrete inputs.
    Any coefficient mutation (-2.0 → -1.0, +0.5 → +1.0, etc.) breaks this."""
    result = compute_supplier_trust_reward(
        prediction_accuracy=torch.tensor(1.0),
        trust_bias=torch.tensor(0.5),
        calibration=torch.tensor(1.0),
    )["total_reward"]
    # 1.0 - 2.0*0.5 + 0.5*1.0 = 1.0 - 1.0 + 0.5 = 0.5
    assert result.item() == pytest.approx(0.5, abs=1e-6), (
        f"Reward formula deviated from expected 0.5 (got {result.item()}); coefficient mutated?"
    )


# --- counterfactual 3: sMAPE-accuracy is clamped to [0, 1] -------------------


def test_prediction_accuracy_clamped_to_unit_interval() -> None:
    """compute_prediction_accuracy uses torch.clamp(..., min=0.0, max=1.0).
    A mutant that removes the clamp would let extreme observations push the
    return out of [0, 1]. Construct an adversarial case."""
    # Heavy mismatch — without clamp, 1 - sMAPE could go negative
    acc = compute_prediction_accuracy(
        predicted_days=torch.tensor([1.0, 1.0, 1.0]),
        observed_days=torch.tensor([100.0, 100.0, 100.0]),
    )
    assert 0.0 <= acc.item() <= 1.0, (
        f"Accuracy escaped [0, 1] clamp: {acc.item()} — mutation on clamp surviving?"
    )


def test_prediction_accuracy_perfect_match_is_one() -> None:
    """Identity case pins the formula and the upper-clamp bound."""
    acc = compute_prediction_accuracy(
        predicted_days=torch.tensor([3.0, 5.0, 7.0]),
        observed_days=torch.tensor([3.0, 5.0, 7.0]),
    )
    assert acc.item() == pytest.approx(1.0, abs=1e-6)


# --- counterfactual 4: trust_bias is non-negative (uses abs) -----------------


def test_trust_bias_returns_non_negative() -> None:
    """compute_trust_bias is `mean(abs(scores - reality))`. A mutant removing
    abs() could produce a negative bias which would flip into a reward bonus."""
    bias_pos = compute_trust_bias(
        trust_scores=torch.tensor([0.9, 0.8]),
        actual_reliability=torch.tensor([0.5, 0.4]),
    )
    bias_neg = compute_trust_bias(
        trust_scores=torch.tensor([0.5, 0.4]),
        actual_reliability=torch.tensor([0.9, 0.8]),
    )
    assert bias_pos.item() >= 0.0
    assert bias_neg.item() >= 0.0
    # And both directions of error should produce the SAME magnitude (abs symmetry)
    assert bias_pos.item() == pytest.approx(bias_neg.item(), abs=1e-6), (
        f"Symmetry broken — abs() removed from trust_bias? ({bias_pos} vs {bias_neg})"
    )


# --- counterfactual 5: calibration score is anchored at target 0.8 -----------


def test_calibration_score_peaks_at_target_coverage() -> None:
    """1 - |coverage - 0.8| peaks at coverage=0.8. Verify that an
    over-confident (narrow) interval scores LOWER than a well-calibrated one."""
    # Wide interval — coverage = 1.0 → score = 1 - |1.0 - 0.8| = 0.8
    wide = compute_calibration_score(
        observed_days=torch.tensor([5.0, 5.0, 5.0, 5.0, 5.0]),
        p10=torch.tensor([1.0, 1.0, 1.0, 1.0, 1.0]),
        p90=torch.tensor([10.0, 10.0, 10.0, 10.0, 10.0]),
    )
    # Narrow interval missing every observation — coverage = 0.0 → score = 1 - 0.8 = 0.2
    narrow = compute_calibration_score(
        observed_days=torch.tensor([5.0, 5.0, 5.0, 5.0, 5.0]),
        p10=torch.tensor([100.0, 100.0, 100.0, 100.0, 100.0]),
        p90=torch.tensor([200.0, 200.0, 200.0, 200.0, 200.0]),
    )
    assert wide.item() == pytest.approx(0.8, abs=1e-6), (
        f"Calibration anchor at 0.8 broken (wide={wide.item()}); target_coverage mutated?"
    )
    assert narrow.item() == pytest.approx(0.2, abs=1e-6), (
        f"Calibration miss penalty broken (narrow={narrow.item()})"
    )
    assert wide.item() > narrow.item() + 0.5


# --- counterfactual 6: total_reward strict monotonicity in accuracy ----------


@pytest.mark.parametrize("accuracy", [0.5, 0.7, 0.9, 0.99])
def test_reward_monotone_in_accuracy(accuracy: float) -> None:
    """Holding bias and calibration fixed, higher accuracy yields strictly
    higher reward. Mutant on the accuracy coefficient (1.0 → 0.0) collapses
    the slope to zero and fails this."""
    bias = torch.tensor(0.1)
    cal = torch.tensor(0.8)
    r = compute_supplier_trust_reward(
        prediction_accuracy=torch.tensor(accuracy),
        trust_bias=bias,
        calibration=cal,
    )["total_reward"]
    r_lower = compute_supplier_trust_reward(
        prediction_accuracy=torch.tensor(accuracy - 0.1),
        trust_bias=bias,
        calibration=cal,
    )["total_reward"]
    assert r.item() > r_lower.item(), (
        f"Reward not monotone in accuracy at {accuracy} (r={r}, r-0.1={r_lower}); "
        f"accuracy coefficient mutated to 0?"
    )


# --- counterfactual 7: returned dict carries the contract keys ---------------


def test_reward_dict_contract() -> None:
    """Pin the dict shape so a mutant dropping a key (or returning a tensor
    instead of a dict) fails immediately."""
    r = compute_supplier_trust_reward(
        prediction_accuracy=torch.tensor(0.9),
        trust_bias=torch.tensor(0.05),
        calibration=torch.tensor(0.85),
    )
    assert set(r.keys()) == {"total_reward", "prediction_accuracy", "trust_bias", "calibration"}, (
        f"Reward dict contract broken: {r.keys()}"
    )
    for k, v in r.items():
        assert isinstance(v, torch.Tensor), f"Value at {k} not a tensor: {type(v)}"
