"""Demand Prophet reward-hacking counterfactual tests (Sprint 8 WS-5 §M10).

Tests assert that no path through ``rewards.py`` lets the agent inflate
its own utility. Each scenario constructs an input designed to game one
component (CRPS, calibration gap, event bonus) and asserts the reward
either fails to improve or moves in the corrected direction.

ADR-031 shadow-mode invariant: tampering with the reward kwargs (e.g.,
overriding ``crps_weight=0.0``) raises a Prometheus counter the runtime
can detect; this test exercises that signal too.
"""

from __future__ import annotations

import pytest
import torch
from synapse_common.metrics import REWARD_WEIGHT_DIVERGENCE_TOTAL

from agents.demand_prophet.training import reward_config
from agents.demand_prophet.training.rewards import (
    calibration_gap,
    compute_reward,
    crps_loss,
    event_bonus,
)


def _reset_divergence_counter() -> None:
    """Reset the Prometheus counter so per-test assertions are clean."""
    import contextlib

    with contextlib.suppress(AttributeError):
        REWARD_WEIGHT_DIVERGENCE_TOTAL._metrics.clear()  # type: ignore[attr-defined]


# --- counterfactual 1: confidence inflation cannot game CRPS -----------------


def test_confidence_inflation_does_not_reduce_crps_loss() -> None:
    """If predictions claim higher confidence (narrower quantiles) but actuals
    are still in the original location, CRPS must not improve. Agent cannot
    game the reward by tightening quantiles without justification."""
    actuals = torch.tensor([10.0, 12.0, 8.0, 11.0])
    honest = torch.tensor([[8.0, 10.0, 12.0]] * 4)
    cheating = torch.tensor([[9.9, 10.0, 10.1]] * 4)
    honest_loss = crps_loss(honest, actuals)
    cheating_loss = crps_loss(cheating, actuals)
    assert cheating_loss > honest_loss, (
        f"Confidence inflation reduced CRPS — possible game (honest={honest_loss}, "
        f"cheating={cheating_loss})"
    )


# --- counterfactual 2: zero-width conformal interval is penalised ------------


def test_zero_width_conformal_interval_is_penalised() -> None:
    """Setting lower==upper makes the interval cover 0% of actuals; calibration
    gap must approach target_coverage (= maximum penalty)."""
    lower = torch.tensor([10.0, 10.0, 10.0, 10.0])
    upper = lower.clone()
    actuals = torch.tensor([5.0, 6.0, 7.0, 8.0])
    gap = calibration_gap(lower, upper, actuals, target_coverage=0.9)
    assert gap.item() >= 0.85, (
        f"Zero-width interval failed to incur expected calibration penalty (gap={gap})"
    )


# --- counterfactual 3: spurious event signal cannot exceed event_bonus cap ---


def test_event_bonus_cannot_exceed_unit_cap() -> None:
    """event_bonus is clamped to [0, 1] (per rewards.py:69). A maliciously
    crafted event signal must not produce >1.0 bonus."""
    predicted = torch.tensor([20.0, 25.0])
    actuals = torch.tensor([0.001, 0.001])  # near-zero actuals — extreme miss
    event_signals = torch.tensor([1.0, 1.0])  # event flagged
    bonus = event_bonus(predicted, event_signals, actuals)
    assert 0.0 <= bonus.item() <= 1.0, f"event_bonus escaped [0,1] cap: {bonus.item()}"


# --- counterfactual 4: kwarg override diverges from spec config --------------


def test_kwarg_override_triggers_divergence_counter() -> None:
    """If a caller passes kwargs that diverge from
    ``reward_config.WEIGHTS``, the divergence counter MUST increment."""
    _reset_divergence_counter()
    actuals = torch.tensor([10.0, 12.0])
    predictions = torch.tensor([[8.0, 10.0, 12.0]] * 2)
    lower = predictions[:, 0]
    upper = predictions[:, 2]

    compute_reward(
        predictions=predictions,
        actuals=actuals,
        lower_bound=lower,
        upper_bound=upper,
        crps_weight=999.0,  # diverges from reward_config.WEIGHTS
    )

    samples = list(REWARD_WEIGHT_DIVERGENCE_TOTAL.collect())
    total = sum(
        sample.value
        for metric in samples
        for sample in metric.samples
        if sample.labels.get("agent") == "demand_prophet"
        and sample.labels.get("key") == "crps_weight"
        and sample.name.endswith("_total")
    )
    assert total >= 1.0, (
        "Expected REWARD_WEIGHT_DIVERGENCE_TOTAL{agent=demand_prophet,key=crps_weight} "
        "to increment on kwarg override"
    )


# --- counterfactual 5: matching kwargs do NOT trigger divergence -------------


def test_matching_kwargs_keep_divergence_at_zero() -> None:
    """When kwargs equal reward_config.WEIGHTS, no divergence is emitted."""
    _reset_divergence_counter()
    actuals = torch.tensor([10.0, 12.0])
    predictions = torch.tensor([[8.0, 10.0, 12.0]] * 2)
    lower = predictions[:, 0]
    upper = predictions[:, 2]

    compute_reward(
        predictions=predictions,
        actuals=actuals,
        lower_bound=lower,
        upper_bound=upper,
        crps_weight=reward_config.WEIGHTS["crps_weight"],
        calibration_weight=reward_config.WEIGHTS["calibration_weight"],
        event_weight=reward_config.WEIGHTS["event_weight"],
    )

    samples = list(REWARD_WEIGHT_DIVERGENCE_TOTAL.collect())
    total = sum(
        sample.value
        for metric in samples
        for sample in metric.samples
        if sample.labels.get("agent") == "demand_prophet" and sample.name.endswith("_total")
    )
    assert total == 0.0, f"Divergence counter should be 0 with matching weights, was {total}"


def test_none_defaults_use_configured_reward_formula() -> None:
    """None-sentinel defaults must resolve to reward_config.WEIGHTS in the total."""
    actuals = torch.tensor([10.0, 12.0, 8.0])
    predictions = torch.tensor(
        [
            [8.0, 10.0, 12.0],
            [10.0, 12.0, 14.0],
            [6.0, 8.0, 10.0],
        ]
    )
    event_signals = torch.tensor([1.0, 0.0, 1.0])

    result = compute_reward(
        predictions=predictions,
        actuals=actuals,
        lower_bound=predictions[:, 0],
        upper_bound=predictions[:, 2],
        event_signals=event_signals,
    )
    expected = (
        -reward_config.WEIGHTS["crps_weight"] * result["crps_loss"]
        - reward_config.WEIGHTS["calibration_weight"] * result["calibration_gap"]
        + reward_config.WEIGHTS["event_weight"] * result["event_bonus"]
    )

    assert torch.isclose(result["total_reward"], expected).item()


# --- counterfactual 6: reward sign — better predictions yield higher reward --


@pytest.mark.parametrize("seed", [0, 1, 2])
def test_better_predictions_yield_higher_reward(seed: int) -> None:
    torch.manual_seed(seed)
    actuals = torch.tensor([10.0, 12.0, 8.0, 11.0, 9.0])

    good = torch.tensor(
        [
            [9.5, 10.0, 10.5],
            [11.5, 12.0, 12.5],
            [7.5, 8.0, 8.5],
            [10.5, 11.0, 11.5],
            [8.5, 9.0, 9.5],
        ]
    )
    bad = torch.tensor(
        [
            [1.0, 2.0, 3.0],
            [1.0, 2.0, 3.0],
            [1.0, 2.0, 3.0],
            [1.0, 2.0, 3.0],
            [1.0, 2.0, 3.0],
        ]
    )

    good_reward = compute_reward(
        predictions=good,
        actuals=actuals,
        lower_bound=good[:, 0],
        upper_bound=good[:, 2],
    )["total_reward"]
    bad_reward = compute_reward(
        predictions=bad,
        actuals=actuals,
        lower_bound=bad[:, 0],
        upper_bound=bad[:, 2],
    )["total_reward"]
    assert good_reward.item() > bad_reward.item(), (
        f"Reward orientation broken (good={good_reward.item()}, bad={bad_reward.item()})"
    )
