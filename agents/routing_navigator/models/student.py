"""
SYNAPSE Routing Navigator -- Distilled 2-Layer MLP Student.
Target: Tier 1 inference under 100ms (INV-RN-006).
"""
from __future__ import annotations

import torch
import torch.nn as nn
from torch import Tensor


class DistilledStudent(nn.Module):
    """
    2-layer MLP student network for Tier 1 sub-100ms routing.
    Input: (batch, num_orders * feature_dim + rider_features)
    Output: (batch, num_orders) priority scores for greedy assignment
    """

    def __init__(
        self,
        input_dim: int = 2048,
        hidden_1: int = 256,
        hidden_2: int = 128,
        max_orders: int = 200,
        dropout: float = 0.1,
    ) -> None:
        super().__init__()
        self.max_orders = max_orders

        self.network = nn.Sequential(
            nn.Linear(input_dim, hidden_1),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_1, hidden_2),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_2, max_orders),
        )

    def forward(self, x: Tensor) -> Tensor:
        return self.network(x)

    @torch.no_grad()
    def predict_route(self, x: Tensor, num_orders: int) -> Tensor:
        """Generate route as greedy permutation from priority scores."""
        scores = self.forward(x)[:, :num_orders]
        _, route = scores.sort(dim=-1, descending=True)
        return route
