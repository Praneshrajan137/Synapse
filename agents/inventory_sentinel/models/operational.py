"""
SYNAPSE Inventory Sentinel -- L3 Operational Agent.
Scope: Real-time shelf management per store.
Action: SKU priority ranking for front-of-shelf placement (permutation).
"""

from __future__ import annotations

import torch.nn as nn
from torch import Tensor


class OperationalAgent(nn.Module):
    """L3 Operational: real-time shelf priority ranking."""

    def __init__(self, obs_dim: int = 50, hidden_dim: int = 64, max_skus: int = 100) -> None:
        super().__init__()
        self.scorer = nn.Sequential(
            nn.Linear(obs_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, max_skus),
        )

    def forward(self, obs: Tensor) -> Tensor:
        return self.scorer(obs)

    def get_ranking(self, obs: Tensor, num_skus: int) -> Tensor:
        scores = self.forward(obs)[:, :num_skus]
        _, ranking = scores.sort(dim=-1, descending=True)
        return ranking
