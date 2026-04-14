"""
SYNAPSE Inventory Sentinel -- L2 Tactical Agent.
Scope: Per-store, per-SKU decisions conditioned on L1 strategic output.
Action: reorder_point (continuous), safety_stock_mult (1.0-3.0), reorder_qty (discrete).
"""

from __future__ import annotations

import torch
import torch.nn as nn
from torch import Tensor


class TacticalAgent(nn.Module):
    """L2 Tactical: per-store SKU-level inventory decisions."""

    def __init__(self, obs_dim: int = 120, hidden_dim: int = 128, l1_dim: int = 100) -> None:
        super().__init__()
        combined_dim = obs_dim + l1_dim

        self.reorder_head = nn.Sequential(
            nn.Linear(combined_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, 1),
            nn.Softplus(),
        )
        # Output [0,1] -> scale to [1,3] for INV-IS-001
        self.safety_head = nn.Sequential(
            nn.Linear(combined_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, 1),
            nn.Sigmoid(),
        )
        self.qty_head = nn.Sequential(
            nn.Linear(combined_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, 50),
        )
        self.critic = nn.Sequential(
            nn.Linear(combined_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, 1),
        )

    def forward(self, obs: Tensor, l1_output: Tensor) -> dict[str, Tensor]:
        x = torch.cat([obs, l1_output], dim=-1)
        reorder_point = self.reorder_head(x).squeeze(-1)
        safety_raw = self.safety_head(x).squeeze(-1)
        safety_mult = 1.0 + safety_raw * 2.0  # Scale [0,1] -> [1.0, 3.0]
        qty_logits = self.qty_head(x)
        value = self.critic(x)
        return {
            "reorder_point": reorder_point,
            "safety_stock_multiplier": safety_mult,
            "qty_logits": qty_logits,
            "value": value,
        }
