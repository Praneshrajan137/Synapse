"""
SYNAPSE Demand Prophet -- HGT-TFT Hybrid Fusion Module.
output = gate * tft_out + (1 - gate) * hgt_projected_out

The gate learns to balance spatial vs temporal features per-sample.
"""

from __future__ import annotations

from typing import Any

import structlog
import torch
import torch.nn as nn
from torch import Tensor

from agents.demand_prophet.models.hgt import HGTEncoder
from agents.demand_prophet.models.tft import VALID_HORIZONS, TemporalFusionTransformer

logger = structlog.get_logger(__name__)


class FusionGate(nn.Module):
    """Learned sigmoid gating: input_dim -> hidden -> 1 (sigmoid)."""

    def __init__(self, input_dim: int, hidden_dim: int = 64) -> None:
        super().__init__()
        self.mlp = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, 1),
            nn.Sigmoid(),
        )

    def forward(self, x: Tensor) -> Tensor:
        return self.mlp(x)


class DemandProphetHybrid(nn.Module):
    """
    HGT-TFT Hybrid model for multi-horizon demand forecasting.
    Forward: graph -> temporal -> fusion -> multi-horizon quantile output.

    Invariants:
        INV-DP-004: All 5 horizons present in output
        INV-DP-006: Non-negative forecasts (ReLU on output)
    """

    def __init__(
        self,
        hgt_hidden_dim: int = 128,
        hgt_num_heads: int = 4,
        hgt_num_layers: int = 3,
        hgt_dropout: float = 0.1,
        tft_hidden_size: int = 160,
        tft_num_heads: int = 4,
        tft_num_static: int = 8,
        tft_num_time_known: int = 12,
        tft_num_time_observed: int = 5,
        tft_dropout: float = 0.1,
        num_quantiles: int = 3,
        gating_hidden: int = 64,
        node_feature_dims: dict[str, int] | None = None,
    ) -> None:
        super().__init__()

        self.hgt = HGTEncoder(
            hidden_dim=hgt_hidden_dim,
            num_heads=hgt_num_heads,
            num_layers=hgt_num_layers,
            dropout=hgt_dropout,
            node_feature_dims=node_feature_dims,
        )

        self.tft = TemporalFusionTransformer(
            num_static=tft_num_static,
            num_time_known=tft_num_time_known,
            num_time_observed=tft_num_time_observed,
            hidden_size=tft_hidden_size,
            num_heads=tft_num_heads,
            dropout=tft_dropout,
            num_quantiles=num_quantiles,
            graph_embed_dim=hgt_hidden_dim,
        )

        self.hgt_projection = nn.ModuleDict(
            {horizon: nn.Linear(hgt_hidden_dim, num_quantiles) for horizon in VALID_HORIZONS}
        )

        self.fusion_gates = nn.ModuleDict(
            {horizon: FusionGate(num_quantiles * 2, gating_hidden) for horizon in VALID_HORIZONS}
        )

        self.num_quantiles = num_quantiles

    def forward(
        self,
        graph_data: Any,
        static_inputs: list[Tensor],
        temporal_inputs: list[Tensor],
        sku_indices: Tensor | None = None,
    ) -> dict[str, Tensor]:
        sku_embeddings = self.hgt(graph_data)

        if sku_indices is not None:
            sku_embeddings = sku_embeddings[sku_indices]

        tft_outputs = self.tft(static_inputs, temporal_inputs, sku_embeddings)

        hgt_predictions: dict[str, Tensor] = {
            h: self.hgt_projection[h](sku_embeddings) for h in VALID_HORIZONS
        }

        fused_outputs: dict[str, Tensor] = {}
        for horizon in VALID_HORIZONS:
            tft_h = tft_outputs[horizon]
            hgt_h = hgt_predictions[horizon]

            gate_input = torch.cat([tft_h, hgt_h], dim=-1)
            gate = self.fusion_gates[horizon](gate_input)

            fused = gate * tft_h + (1 - gate) * hgt_h
            fused_outputs[horizon] = torch.relu(fused)  # INV-DP-006

        return fused_outputs

    def get_model_summary(self) -> dict[str, int]:
        """Return model parameter counts for MLflow logging."""
        total = sum(p.numel() for p in self.parameters())
        trainable = sum(p.numel() for p in self.parameters() if p.requires_grad)
        hgt_params = sum(p.numel() for p in self.hgt.parameters())
        tft_params = sum(p.numel() for p in self.tft.parameters())
        return {
            "total_params": total,
            "trainable_params": trainable,
            "hgt_params": hgt_params,
            "tft_params": tft_params,
            "fusion_params": total - hgt_params - tft_params,
        }
