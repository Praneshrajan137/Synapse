"""Disruption Shield reward-hacking counterfactuals (Sprint 9 §M6)."""

from __future__ import annotations

import contextlib

import pytest
import torch
from synapse_common.metrics import REWARD_WEIGHT_DIVERGENCE_TOTAL

from agents.disruption_shield.training import reward_config
from agents.disruption_shield.training.rewards import (
    compute_reward,
    false_positive_penalty,
    missed_disruption_penalty,
)


def _reset_counter() -> None:
    with contextlib.suppress(AttributeError):
        REWARD_WEIGHT_DIVERGENCE_TOTAL._metrics.clear()  # type: ignore[attr-defined]


def test_missed_disruption_dominates_false_positive() -> None:
    """A missed real disruption must hurt more than a false positive,
    per the asymmetric weights in the spec (50.0 vs 10.0)."""
    actual = torch.tensor([1.0])
    no_alert = torch.tensor([0.0])
    false_alert = torch.tensor([1.0])
    no_disrupt = torch.tensor([0.0])
    missed = missed_disruption_penalty(no_alert, actual)
    fp = false_positive_penalty(false_alert, no_disrupt)
    # weighted comparison: missed_disruption_weight * missed vs false_positive_weight * fp
    weighted_missed = reward_config.WEIGHTS["missed_disruption_weight"] * float(missed)
    weighted_fp = reward_config.WEIGHTS["false_positive_weight"] * float(fp)
    assert weighted_missed >= weighted_fp, (
        f"Missed-disruption penalty must dominate false-positive (50:10 asymmetry); "
        f"got missed={weighted_missed} fp={weighted_fp}"
    )


def test_recovery_speed_weight_pinned() -> None:
    """Recovery weight stays positive; otherwise a fast recovery hurts utility."""
    assert reward_config.WEIGHTS["recovery_speed_weight"] > 0.0


def test_kwarg_override_triggers_divergence() -> None:
    _reset_counter()
    compute_reward(
        predicted_alert=torch.tensor([1.0]),
        actual_disruption=torch.tensor([1.0]),
        hours_before_impact=torch.tensor([2.0]),
        time_to_recovery_hours=torch.tensor([0.5]),
        playbook_applied=torch.tensor([1.0]),
        missed_disruption_weight=999.0,  # divergence
    )
    samples = list(REWARD_WEIGHT_DIVERGENCE_TOTAL.collect())
    total = sum(
        s.value
        for m in samples
        for s in m.samples
        if s.labels.get("agent") == "disruption_shield"
        and s.labels.get("key") == "missed_disruption_weight"
        and s.name.endswith("_total")
    )
    assert total >= 1.0


def test_matching_kwargs_no_divergence() -> None:
    _reset_counter()
    compute_reward(
        predicted_alert=torch.tensor([1.0]),
        actual_disruption=torch.tensor([1.0]),
        hours_before_impact=torch.tensor([2.0]),
        time_to_recovery_hours=torch.tensor([0.5]),
        playbook_applied=torch.tensor([1.0]),
        early_detection_weight=reward_config.WEIGHTS["early_detection_weight"],
        false_positive_weight=reward_config.WEIGHTS["false_positive_weight"],
        missed_disruption_weight=reward_config.WEIGHTS["missed_disruption_weight"],
        recovery_speed_weight=reward_config.WEIGHTS["recovery_speed_weight"],
    )
    samples = list(REWARD_WEIGHT_DIVERGENCE_TOTAL.collect())
    total = sum(
        s.value
        for m in samples
        for s in m.samples
        if s.labels.get("agent") == "disruption_shield" and s.name.endswith("_total")
    )
    assert total == 0.0


@pytest.mark.parametrize("seed", [0, 1])
def test_no_alert_when_no_disruption_yields_zero_penalty(seed: int) -> None:
    torch.manual_seed(seed)
    no_alert = torch.tensor([0.0])
    no_disrupt = torch.tensor([0.0])
    fp = false_positive_penalty(no_alert, no_disrupt)
    missed = missed_disruption_penalty(no_alert, no_disrupt)
    assert fp.item() == 0.0
    assert missed.item() == 0.0
