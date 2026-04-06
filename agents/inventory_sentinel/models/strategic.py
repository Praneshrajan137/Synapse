"""
SYNAPSE Inventory Sentinel -- L1 Strategic Agent.
Scope: Cluster of 5 stores. Network-wide optimization.
Action: Inter-store transfer quantities, warehouse reorder binary per SKU.
"""
from __future__ import annotations

import torch.nn as nn
from torch import Tensor


class StrategicAgent(nn.Module):
    """L1 Strategic: cluster-level inventory optimization."""

    def __init__(
        self, obs_dim: int = 550, hidden_dim: int = 256, action_dim: int = 100
    ) -> None:
        super().__init__()
        self.actor = nn.Sequential(
            nn.Linear(obs_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, action_dim),
            nn.Tanh(),
        )
        self.critic = nn.Sequential(
            nn.Linear(obs_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, 1),
        )

    def forward(self, obs: Tensor) -> tuple[Tensor, Tensor]:
        return self.actor(obs), self.critic(obs)

    def get_action(self, obs: Tensor) -> Tensor:
        action, _ = self.forward(obs)
        return action
