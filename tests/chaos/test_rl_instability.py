from __future__ import annotations

from collections import deque

import numpy as np
import pytest
import structlog
import structlog.testing

logger = structlog.get_logger()

pytestmark = pytest.mark.chaos


class RewardStabilityMonitor:
    """Monitors reward signal variance and triggers policy freeze/revert."""

    VARIANCE_SPIKE_THRESHOLD = 3.0
    WINDOW_SIZE = 100

    def __init__(self) -> None:
        self.reward_history: deque[float] = deque(maxlen=self.WINDOW_SIZE)
        self.baseline_variance: float | None = None
        self.frozen: bool = False
        self.reverted: bool = False
        self.last_stable_checkpoint: str = "checkpoint_stable_v1"

    def calibrate_baseline(self, rewards: list[float]) -> None:
        """Set baseline variance from stable training period."""
        self.baseline_variance = float(np.var(rewards))
        self.reward_history.extend(rewards)

    def observe_reward(self, reward: float) -> dict:
        self.reward_history.append(reward)

        if self.baseline_variance is None or self.baseline_variance == 0:
            return {"status": "calibrating", "action": None}

        current_var = float(np.var(list(self.reward_history)))
        variance_ratio = current_var / self.baseline_variance

        if variance_ratio > self.VARIANCE_SPIKE_THRESHOLD:
            self.frozen = True
            self.reverted = True
            logger.warning(
                "rl_policy_instability_detected",
                variance_ratio=variance_ratio,
                threshold=self.VARIANCE_SPIKE_THRESHOLD,
                action="freeze_and_revert",
                checkpoint=self.last_stable_checkpoint,
            )
            return {
                "status": "unstable",
                "action": "freeze_and_revert",
                "variance_ratio": variance_ratio,
                "checkpoint": self.last_stable_checkpoint,
            }

        return {"status": "stable", "action": None, "variance_ratio": variance_ratio}


class TestRLInstability:
    """Chaos logic validation: Adversarial reward signal causes variance spike.
    System freezes policy and reverts to last stable checkpoint. SLA: <60s."""

    def test_adversarial_reward_detected(self, chaos_clock) -> None:
        """Adversarial rewards spike variance beyond threshold."""
        rng = np.random.default_rng(42)
        monitor = RewardStabilityMonitor()

        stable_rewards = list(rng.normal(1.0, 0.1, 50))
        monitor.calibrate_baseline(stable_rewards)

        chaos_clock.start()
        with structlog.testing.capture_logs() as captured:
            for _ in range(60):
                adversarial = float(rng.uniform(-10.0, 10.0))
                result = monitor.observe_reward(adversarial)
                if result["action"] == "freeze_and_revert":
                    break

        assert monitor.frozen is True, "Policy was NOT frozen after adversarial rewards"
        assert monitor.reverted is True
        chaos_clock.assert_within_sla(60.0, "RL instability detection and revert")
        assert any(e.get("event") == "rl_policy_instability_detected" for e in captured)

    def test_stable_rewards_no_freeze(self) -> None:
        """Stable reward signal does not trigger false positive."""
        rng = np.random.default_rng(99)
        monitor = RewardStabilityMonitor()
        stable_rewards = list(rng.normal(1.0, 0.1, 50))
        monitor.calibrate_baseline(stable_rewards)

        for _ in range(50):
            reward = float(rng.normal(1.0, 0.15))
            result = monitor.observe_reward(reward)
            assert result["action"] is None, "False positive: stable rewards triggered freeze"

    def test_revert_checkpoint_specified(self, chaos_clock) -> None:
        """Revert action includes the correct checkpoint identifier."""
        rng = np.random.default_rng(42)
        monitor = RewardStabilityMonitor()
        monitor.calibrate_baseline(list(rng.normal(1.0, 0.1, 50)))

        chaos_clock.start()
        for _ in range(60):
            result = monitor.observe_reward(float(rng.uniform(-10, 10)))
            if result.get("action") == "freeze_and_revert":
                assert result["checkpoint"] == "checkpoint_stable_v1"
                break

        chaos_clock.assert_within_sla(60.0, "RL checkpoint revert")

    def test_zero_baseline_variance_stays_calibrating(self) -> None:
        """If baseline variance is zero, monitor stays in calibrating state."""
        monitor = RewardStabilityMonitor()
        monitor.calibrate_baseline([1.0, 1.0, 1.0, 1.0, 1.0])

        result = monitor.observe_reward(100.0)
        assert result["status"] == "calibrating"

    def test_gradual_drift_eventually_triggers(self) -> None:
        """Slowly increasing reward variance eventually crosses threshold."""
        rng = np.random.default_rng(7)
        monitor = RewardStabilityMonitor()
        monitor.calibrate_baseline(list(rng.normal(1.0, 0.1, 50)))

        triggered = False
        for i in range(200):
            scale = 0.1 + i * 0.1
            reward = float(rng.normal(1.0, scale))
            result = monitor.observe_reward(reward)
            if result.get("action") == "freeze_and_revert":
                triggered = True
                break

        assert triggered, "Gradual drift should eventually trigger freeze"
