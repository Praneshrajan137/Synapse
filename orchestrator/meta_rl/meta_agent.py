"""
SYNAPSE Orchestrator — Meta-RL agent for arbitration weight learning.

Learns the optimal Pareto weight vector over time using a simple policy
gradient on the rolling decision-outcome history.  NEVER modifies per-agent
reward functions (I-2).
"""

from __future__ import annotations

from collections import deque
from typing import Any

import numpy as np
import numpy.typing as npt
import structlog

logger = structlog.get_logger(__name__)

OBJECTIVES: list[str] = [
    "demand_accuracy",
    "route_efficiency",
    "inventory_fill_rate",
    "freshness_score",
    "pricing_revenue",
    "disruption_readiness",
    "supplier_reliability",
    "carbon_efficiency",
]


class MetaRLAgent:
    """Learns optimal Pareto arbitration weights via policy gradient.

    State:  current weight vector + system features + recent outcomes.
    Action: new 8-D weight vector (normalised to sum to ``n_objectives``).
    Reward: aggregate system KPI improvement vs previous vector.
    """

    def __init__(
        self,
        n_objectives: int = 8,
        lr: float = 0.001,
        history_size: int = 100,
    ) -> None:
        self.n_objectives = n_objectives
        self.weights = np.ones(n_objectives, dtype=np.float64)
        self.lr = lr
        self.outcome_history: deque[dict[str, float]] = deque(maxlen=history_size)
        self.weight_history: deque[npt.NDArray[np.float64]] = deque(maxlen=history_size)

    def get_weights(self, system_state: dict[str, Any]) -> dict[str, float]:
        """Return the current weight vector adjusted for system state."""
        adjusted = self.weights.copy()

        if system_state.get("active_disruptions", 0) > 0:
            adjusted[5] *= 1.5  # disruption_readiness
        if system_state.get("avg_fill_rate", 1.0) < 0.9:
            adjusted[2] *= 1.3  # inventory_fill_rate
        hour = system_state.get("hour_of_day", 12)
        if 11 <= hour < 14:
            adjusted[1] *= 1.2  # route_efficiency during lunch peak

        adjusted = adjusted / adjusted.sum() * self.n_objectives
        return dict(zip(OBJECTIVES, adjusted.tolist(), strict=False))

    def update(self, outcome: dict[str, float]) -> None:
        """Update weights based on an observed decision outcome."""
        self.outcome_history.append(outcome)
        if len(self.outcome_history) < 10:
            return

        recent = list(self.outcome_history)[-10:]
        for i, obj in enumerate(OBJECTIVES):
            avg_score = float(np.mean([o.get(obj, 0.5) for o in recent]))
            if avg_score < 0.5:
                self.weights[i] *= 1.0 + self.lr
            elif avg_score > 0.8:
                self.weights[i] *= 1.0 - self.lr * 0.5

        self.weights = self.weights / self.weights.sum() * self.n_objectives
        self.weight_history.append(self.weights.copy())

        logger.info(
            "meta_rl_weights_updated",
            weights=dict(zip(OBJECTIVES, self.weights.tolist(), strict=False)),
            history_len=len(self.outcome_history),
        )

    def get_raw_weights(self) -> npt.NDArray[np.float64]:
        """Return raw weight array (for serialisation / checkpoint)."""
        return self.weights.copy()
