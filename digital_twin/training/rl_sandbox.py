"""
SYNAPSE Digital Twin — Gymnasium wrapper around SimPy for RL training.

SupplyChainGymEnv provides a standard Gymnasium interface with domain
randomization (+/-30%) on lead times, demand, and failure rates.
"""
from __future__ import annotations

from typing import Any

import gymnasium as gym
import numpy as np
import structlog
from gymnasium import spaces

from digital_twin.config import TwinConfig
from digital_twin.simulation.engine import SupplyChainSimulation

logger = structlog.get_logger(__name__)

OBS_DIM = 6
ACTION_DIM = 3


class SupplyChainGymEnv(gym.Env[np.ndarray, np.ndarray]):
    """Gymnasium environment wrapping the SimPy supply chain simulation.

    Observation space (6-dim):
      [inventory_level, pending_orders, avg_delivery_time,
       spoilage_rate, restock_count, demand_rate]

    Action space (3-dim continuous):
      [order_quantity_delta, restock_threshold_delta, dispatch_priority]

    Domain randomization: +/-30% on lead times, demand, and failure rates
    per episode reset (configurable via TW_DOMAIN_RANDOMIZATION_PCT).
    """

    metadata: dict[str, Any] = {"render_modes": []}

    def __init__(
        self,
        config: TwinConfig | None = None,
        step_duration_hours: float = 1.0,
        max_steps: int = 168,
    ) -> None:
        super().__init__()
        self._base_config = config or TwinConfig()
        self._step_duration = step_duration_hours
        self._max_steps = max_steps
        self._current_step = 0
        self._rng = np.random.default_rng()
        self._sim: SupplyChainSimulation | None = None
        self._randomization_pct = self._base_config.domain_randomization_pct

        self.observation_space = spaces.Box(
            low=np.zeros(OBS_DIM, dtype=np.float32),
            high=np.full(OBS_DIM, 1000.0, dtype=np.float32),
            dtype=np.float32,
        )
        self.action_space = spaces.Box(
            low=-1.0 * np.ones(ACTION_DIM, dtype=np.float32),
            high=np.ones(ACTION_DIM, dtype=np.float32),
            dtype=np.float32,
        )

        logger.info(
            "gym_env_init",
            step_duration_h=step_duration_hours,
            max_steps=max_steps,
            domain_randomization_pct=self._randomization_pct,
        )

    def _randomize_config(self) -> TwinConfig:
        """Apply domain randomization to simulation parameters."""
        pct = self._randomization_pct

        def _jitter(base: float) -> float:
            return float(base * (1.0 + self._rng.uniform(-pct, pct)))

        return TwinConfig(
            order_arrival_rate=_jitter(self._base_config.order_arrival_rate),
            pick_pack_mean_min=_jitter(self._base_config.pick_pack_mean_min),
            pick_pack_std_min=max(0.5, _jitter(self._base_config.pick_pack_std_min)),
        )

    def _get_obs(self) -> np.ndarray:
        """Extract observation from current simulation state."""
        if self._sim is None:
            return np.zeros(OBS_DIM, dtype=np.float32)

        m = self._sim._metrics
        inv_values = list(self._sim._inventory.values())
        avg_inv = float(np.mean(inv_values)) if inv_values else 0.0

        return np.array(
            [
                avg_inv,
                float(m.orders_created - m.orders_delivered),
                m.avg_delivery_time_min,
                m.spoilage_rate,
                float(m.restocks_triggered),
                self._base_config.order_arrival_rate,
            ],
            dtype=np.float32,
        )

    def _compute_reward(self) -> float:
        """Reward = delivery throughput - spoilage penalty - latency penalty."""
        if self._sim is None:
            return 0.0
        m = self._sim._metrics
        throughput_bonus = float(m.orders_delivered) * 0.1
        spoilage_penalty = float(m.orders_spoiled) * -0.5
        latency_penalty = max(0.0, m.avg_delivery_time_min - 30.0) * -0.01
        return throughput_bonus + spoilage_penalty + latency_penalty

    def reset(
        self,
        *,
        seed: int | None = None,
        options: dict[str, Any] | None = None,
    ) -> tuple[np.ndarray, dict[str, Any]]:
        """Reset environment with domain randomization."""
        super().reset(seed=seed)
        if seed is not None:
            self._rng = np.random.default_rng(seed)

        randomized_config = self._randomize_config()
        self._sim = SupplyChainSimulation(
            config=randomized_config,
            seed=seed,
        )
        # Start the persistent env so step() advances the SAME simulation rather
        # than re-running from scratch each time (the E-DT state-persistence fix).
        self._sim.start()
        self._current_step = 0

        obs = self._get_obs()
        info: dict[str, Any] = {"randomized_config": {
            "order_arrival_rate": randomized_config.order_arrival_rate,
            "pick_pack_mean_min": randomized_config.pick_pack_mean_min,
        }}
        return obs, info

    def step(
        self, action: np.ndarray
    ) -> tuple[np.ndarray, float, bool, bool, dict[str, Any]]:
        """Execute one step (run sim for step_duration hours)."""
        if self._sim is None:
            raise RuntimeError("Must call reset() before step()")

        # Map the 3-d action onto the simulation's supply-policy levers so the
        # policy actually affects the dynamics (the action was previously ignored).
        a = np.clip(np.asarray(action, dtype=np.float64), -1.0, 1.0)
        self._sim.set_policy(
            order_qty_mult=float(1.0 + 0.5 * a[0]),      # [0.5, 1.5]
            restock_threshold=float(50.0 + 40.0 * a[1]),  # [10, 90]
            dispatch_speed=float(1.0 + 0.5 * a[2]),       # [0.5, 1.5] (higher = faster)
        )
        # Advance the SAME persistent env (state carries over between steps).
        self._sim.advance(self._step_duration)
        self._current_step += 1

        obs = self._get_obs()
        reward = self._compute_reward()
        terminated = False
        truncated = self._current_step >= self._max_steps

        info: dict[str, Any] = {
            "step": self._current_step,
            "metrics": self._sim._metrics.to_dict(),
        }
        return obs, reward, terminated, truncated, info
