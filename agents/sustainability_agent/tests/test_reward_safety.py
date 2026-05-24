"""Sustainability Agent reward-hacking counterfactuals (Sprint 9 §M6)."""

from __future__ import annotations

import contextlib

from synapse_common.metrics import REWARD_WEIGHT_DIVERGENCE_TOTAL

from agents.sustainability_agent.training import reward_config
from agents.sustainability_agent.training.rewards import compute_reward


def _reset_counter() -> None:
    with contextlib.suppress(AttributeError):
        REWARD_WEIGHT_DIVERGENCE_TOTAL._metrics.clear()  # type: ignore[attr-defined]


def test_carbon_weight_dominates_other_components() -> None:
    """Carbon dominates — environmental priority. Spec invariant."""
    w = reward_config.WEIGHTS
    assert w["carbon_weight"] >= w["waste_weight"]
    assert w["carbon_weight"] >= w["accuracy_weight"]


def test_lower_carbon_yields_higher_reward() -> None:
    """Reward is monotone decreasing in CO2; agent cannot game by inflating CO2."""
    high = compute_reward(
        co2_kg=20.0,
        items_wasted=5,
        items_total=100,
        predicted_co2_kg=20.0,
        actual_co2_kg=20.0,
        baseline_co2_kg=10.0,
    )
    low = compute_reward(
        co2_kg=5.0,
        items_wasted=5,
        items_total=100,
        predicted_co2_kg=5.0,
        actual_co2_kg=5.0,
        baseline_co2_kg=10.0,
    )
    assert low["total_reward"] > high["total_reward"], (
        f"Lower CO2 must yield higher reward; got high_co2={high['total_reward']} "
        f"low_co2={low['total_reward']}"
    )


def test_kwarg_override_triggers_divergence() -> None:
    _reset_counter()
    compute_reward(
        co2_kg=5.0,
        items_wasted=2,
        items_total=100,
        predicted_co2_kg=5.0,
        actual_co2_kg=5.0,
        baseline_co2_kg=10.0,
        carbon_weight=0.0,  # numbed — divergence
    )
    samples = list(REWARD_WEIGHT_DIVERGENCE_TOTAL.collect())
    total = sum(
        s.value
        for m in samples
        for s in m.samples
        if s.labels.get("agent") == "sustainability_agent"
        and s.labels.get("key") == "carbon_weight"
        and s.name.endswith("_total")
    )
    assert total >= 1.0


def test_matching_kwargs_no_divergence() -> None:
    _reset_counter()
    compute_reward(
        co2_kg=5.0,
        items_wasted=2,
        items_total=100,
        predicted_co2_kg=5.0,
        actual_co2_kg=5.0,
        baseline_co2_kg=10.0,
        carbon_weight=reward_config.WEIGHTS["carbon_weight"],
        waste_weight=reward_config.WEIGHTS["waste_weight"],
        accuracy_weight=reward_config.WEIGHTS["accuracy_weight"],
    )
    samples = list(REWARD_WEIGHT_DIVERGENCE_TOTAL.collect())
    total = sum(
        s.value
        for m in samples
        for s in m.samples
        if s.labels.get("agent") == "sustainability_agent" and s.name.endswith("_total")
    )
    assert total == 0.0
