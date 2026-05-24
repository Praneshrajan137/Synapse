"""Pricing Oracle reward-hacking counterfactual tests (Sprint 8 WS-5 §M10).

PO is the highest-blast-radius agent for I-6 enforcement (essential price
cap ≤ 1.3x). These tests construct counterfactuals where the agent might
try to game the reward by:

  - masking an essential SKU as non-essential to bypass the cap penalty,
  - inflating the elasticity-alignment term via a degenerate batch,
  - overriding ``essential_penalty_weight`` toward zero to numb the cap,
  - claiming a competitor multiplier higher than ours to zero the gap.

All four are guarded; each test asserts the safety property holds.
"""

from __future__ import annotations

import torch
from synapse_common.metrics import REWARD_WEIGHT_DIVERGENCE_TOTAL

from agents.pricing_oracle.training import reward_config
from agents.pricing_oracle.training.rewards import (
    ESSENTIAL_CAP,
    competitor_gap,
    compute_reward,
    elasticity_alignment,
    essential_cap_violation,
)


def _reset_divergence_counter() -> None:
    import contextlib

    with contextlib.suppress(AttributeError):
        REWARD_WEIGHT_DIVERGENCE_TOTAL._metrics.clear()  # type: ignore[attr-defined]


# --- counterfactual 1: essential SKU at 1.45x must yield a violation --------


def test_essential_sku_above_cap_emits_violation() -> None:
    """An essential SKU priced at 1.45x base must register as a cap violation."""
    multipliers = torch.tensor([1.45, 1.0, 1.20])
    is_essential = torch.tensor([1.0, 1.0, 0.0])
    violation = essential_cap_violation(multipliers, is_essential, cap=ESSENTIAL_CAP)
    assert violation.item() > 0.0, "Essential cap violation must surface in the reward signal."


# --- counterfactual 2: masking is_essential=0 cannot eliminate violation
# (the hard clamp in pricing_oracle/inference is the true safety net;
# the test exists to ensure ESSENTIAL_CAP constant is not silently mutated).


def test_essential_cap_constant_is_pinned() -> None:
    assert ESSENTIAL_CAP == 1.3, (
        "ESSENTIAL_CAP must remain 1.3 (I-6). Tampering would silently widen the "
        "cap; this constant is non-learnable."
    )


# --- counterfactual 3: degenerate elasticity batch returns 0 not +inf -------


def test_degenerate_elasticity_returns_zero_not_unbounded() -> None:
    """If elasticity_estimates has zero variance, alignment must be 0 (no
    bonus to game) — not NaN/inf which could pollute the total."""
    multipliers = torch.tensor([1.0, 1.1, 1.2])
    flat_elasticity = torch.tensor([1.5, 1.5, 1.5])
    result = elasticity_alignment(multipliers, flat_elasticity)
    assert result.item() == 0.0, f"Zero-variance batch should yield 0, got {result.item()}"


# --- counterfactual 4: competitor gap is asymmetric (only penalises higher) -


def test_competitor_gap_does_not_reward_undercutting() -> None:
    """Pricing below competitor should NOT produce a negative gap (which
    would be claimed as an alignment bonus). Gap is clamped at 0."""
    ours = torch.tensor([0.9, 0.95, 1.0])
    theirs = torch.tensor([1.1, 1.1, 1.1])
    gap = competitor_gap(ours, theirs)
    assert gap.item() == 0.0, f"Undercutting must NOT register as a bonus, got {gap.item()}"


# --- counterfactual 5: essential penalty weight override is observable -----


def test_essential_penalty_override_triggers_divergence_counter() -> None:
    """Calling compute_reward with essential_penalty_weight=0.0 (numbed) must
    increment ``synapse_reward_weight_divergence_total{key=essential_penalty_weight}``."""
    _reset_divergence_counter()
    multipliers = torch.tensor([1.0, 1.1])
    base_prices = torch.tensor([100.0, 200.0])
    demand_quantities = torch.tensor([10.0, 5.0])
    elasticity = torch.tensor([1.5, 1.7])
    is_essential = torch.tensor([1.0, 0.0])

    compute_reward(
        multipliers=multipliers,
        base_prices=base_prices,
        demand_quantities=demand_quantities,
        elasticity_estimates=elasticity,
        is_essential=is_essential,
        essential_penalty_weight=0.0,  # numbed — diverges from spec config
    )

    samples = list(REWARD_WEIGHT_DIVERGENCE_TOTAL.collect())
    total = sum(
        sample.value
        for metric in samples
        for sample in metric.samples
        if sample.labels.get("agent") == "pricing_oracle"
        and sample.labels.get("key") == "essential_penalty_weight"
        and sample.name.endswith("_total")
    )
    assert total >= 1.0, (
        "Numbing essential_penalty_weight must increment the divergence counter "
        "(shadow mode ADR-031)."
    )


# --- counterfactual 6: matching weights — no divergence --------------------


def test_matching_weights_do_not_emit_divergence() -> None:
    _reset_divergence_counter()
    multipliers = torch.tensor([1.0, 1.1])
    base_prices = torch.tensor([100.0, 200.0])
    demand_quantities = torch.tensor([10.0, 5.0])
    elasticity = torch.tensor([1.5, 1.7])
    is_essential = torch.tensor([1.0, 0.0])
    compute_reward(
        multipliers=multipliers,
        base_prices=base_prices,
        demand_quantities=demand_quantities,
        elasticity_estimates=elasticity,
        is_essential=is_essential,
        revenue_weight=reward_config.WEIGHTS["revenue_weight"],
        elasticity_weight=reward_config.WEIGHTS["elasticity_weight"],
        essential_penalty_weight=reward_config.WEIGHTS["essential_penalty_weight"],
        competitor_gap_weight=reward_config.WEIGHTS["competitor_gap_weight"],
    )
    samples = list(REWARD_WEIGHT_DIVERGENCE_TOTAL.collect())
    total = sum(
        sample.value
        for metric in samples
        for sample in metric.samples
        if sample.labels.get("agent") == "pricing_oracle" and sample.name.endswith("_total")
    )
    assert total == 0.0, f"Matching weights must keep divergence at 0, got {total}"
