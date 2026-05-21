"""Freshness Guardian reward-hacking counterfactuals (Sprint 9 §M6)."""

from __future__ import annotations

import contextlib

import torch
from synapse_common.metrics import REWARD_WEIGHT_DIVERGENCE_TOTAL

from agents.freshness_guardian.training import reward_config
from agents.freshness_guardian.training.rewards import compute_reward


def _reset_counter() -> None:
    with contextlib.suppress(AttributeError):
        REWARD_WEIGHT_DIVERGENCE_TOTAL._metrics.clear()  # type: ignore[attr-defined]


def test_fssai_weight_pinned_above_other_components() -> None:
    """fssai_weight must dominate other components — regulatory requirement."""
    w = reward_config.WEIGHTS
    assert w["fssai_weight"] >= w["accuracy_weight"], (
        f"FSSAI weight must dominate; got {w['fssai_weight']} vs accuracy {w['accuracy_weight']}"
    )
    assert w["fssai_weight"] >= w["timing_weight"]


def test_kwarg_override_triggers_divergence() -> None:
    _reset_counter()
    compute_reward(
        predicted_quality=torch.tensor([0.5]),
        actual_quality=torch.tensor([0.5]),
        markdown_applied=torch.tensor([0.0]),
        days_to_expiry=torch.tensor([2.0]),
        was_sold=torch.tensor([1.0]),
        temperature_deviation_hours=torch.tensor([0.0]),
        fssai_logged=torch.tensor([1.0]),
        fssai_weight=0.0,  # numbed — divergence
    )
    samples = list(REWARD_WEIGHT_DIVERGENCE_TOTAL.collect())
    total = sum(
        s.value
        for m in samples
        for s in m.samples
        if s.labels.get("agent") == "freshness_guardian"
        and s.labels.get("key") == "fssai_weight"
        and s.name.endswith("_total")
    )
    assert total >= 1.0


def test_matching_kwargs_no_divergence() -> None:
    _reset_counter()
    compute_reward(
        predicted_quality=torch.tensor([0.5]),
        actual_quality=torch.tensor([0.5]),
        markdown_applied=torch.tensor([0.0]),
        days_to_expiry=torch.tensor([2.0]),
        was_sold=torch.tensor([1.0]),
        temperature_deviation_hours=torch.tensor([0.0]),
        fssai_logged=torch.tensor([1.0]),
        accuracy_weight=reward_config.WEIGHTS["accuracy_weight"],
        timing_weight=reward_config.WEIGHTS["timing_weight"],
        fssai_weight=reward_config.WEIGHTS["fssai_weight"],
        unnecessary_weight=reward_config.WEIGHTS["unnecessary_weight"],
    )
    samples = list(REWARD_WEIGHT_DIVERGENCE_TOTAL.collect())
    total = sum(
        s.value
        for m in samples
        for s in m.samples
        if s.labels.get("agent") == "freshness_guardian" and s.name.endswith("_total")
    )
    assert total == 0.0


def test_unnecessary_weight_is_a_penalty_not_a_bonus() -> None:
    """unnecessary_weight enters the reward with a minus sign — it cannot be
    weaponised into a bonus by inverting its sign in spec.yaml without
    the divergence counter catching it."""
    assert reward_config.WEIGHTS["unnecessary_weight"] > 0.0
