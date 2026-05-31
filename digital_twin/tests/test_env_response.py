"""Env-truth: the Gym env's action genuinely affects the reward (ADR-042 §Phase 3).

The precondition for honest "twin-as-gym" RL. Before the fix, SupplyChainGymEnv
ignored its action and re-ran the simulation from scratch each step, so any RL
trained against it learned nothing. These tests prove (a) state now persists
across steps, and (b) a good policy (fast dispatch) beats a bad one (slow
dispatch) in mean return over multiple seeds — otherwise training is vacuous.

Needs simpy + gymnasium; skipped on a runner without them (runs in CI).
"""

from __future__ import annotations

import pytest

pytest.importorskip("simpy")
pytest.importorskip("gymnasium")

import numpy as np  # noqa: E402

from digital_twin.training.rl_sandbox import SupplyChainGymEnv  # noqa: E402


def _episode_return(env: SupplyChainGymEnv, action: np.ndarray, seed: int, steps: int) -> float:
    env.reset(seed=seed)
    total = 0.0
    for _ in range(steps):
        _obs, reward, terminated, truncated, _info = env.step(action)
        total += reward
        if terminated or truncated:
            break
    return total


def test_state_persists_across_steps() -> None:
    """orders_created accumulates across steps — proof the env isn't reset each step."""
    env = SupplyChainGymEnv(max_steps=6)
    env.reset(seed=1)
    neutral = np.zeros(3, dtype=np.float32)
    _, _, _, _, info1 = env.step(neutral)
    _, _, _, _, info2 = env.step(neutral)
    created1 = info1["metrics"]["orders_created"]
    created2 = info2["metrics"]["orders_created"]
    assert created1 > 0
    assert created2 >= created1  # accumulates, not reset to a single step's worth


def test_good_action_beats_bad_over_seeds() -> None:
    """Fast-dispatch policy must out-earn slow-dispatch in mean return (non-vacuous)."""
    fast = np.array([0.0, 0.0, 1.0], dtype=np.float32)   # high dispatch speed
    slow = np.array([0.0, 0.0, -1.0], dtype=np.float32)  # low dispatch speed
    steps = 24
    fast_returns, slow_returns = [], []
    for seed in range(5):
        fast_returns.append(_episode_return(SupplyChainGymEnv(max_steps=steps), fast, seed, steps))
        slow_returns.append(_episode_return(SupplyChainGymEnv(max_steps=steps), slow, seed, steps))
    assert np.mean(fast_returns) > np.mean(slow_returns), (
        f"env is action-insensitive: fast={np.mean(fast_returns):.3f} "
        f"slow={np.mean(slow_returns):.3f}"
    )


def test_different_actions_yield_different_returns() -> None:
    """A sanity guard that the action is read at all (would catch a re-introduced ignore)."""
    env_a = SupplyChainGymEnv(max_steps=12)
    env_b = SupplyChainGymEnv(max_steps=12)
    ra = _episode_return(env_a, np.array([0.0, 0.0, 1.0], dtype=np.float32), 7, 12)
    rb = _episode_return(env_b, np.array([0.0, 0.0, -1.0], dtype=np.float32), 7, 12)
    assert ra != rb
