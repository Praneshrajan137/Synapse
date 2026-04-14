"""
SYNAPSE Demand Prophet -- Temporal Fusion Transformer Backbone.
Custom implementation with graph-augmented variable selection:
GNN neighbor embeddings modulate TFT variable selection weights.

Components: Variable Selection Networks, Gated Residual Networks,
Interpretable Multi-Head Attention, Quantile output heads.
"""

from __future__ import annotations

import math

import structlog
import torch
import torch.nn as nn
import torch.nn.functional as F  # noqa: N812
from torch import Tensor

logger = structlog.get_logger(__name__)

VALID_HORIZONS: list[str] = ["15min", "1h", "6h", "24h", "7d"]
NUM_HORIZONS: int = len(VALID_HORIZONS)


class GatedResidualNetwork(nn.Module):
    """Gated Residual Network (GRN) -- core TFT building block."""

    def __init__(
        self,
        input_dim: int,
        hidden_dim: int,
        output_dim: int,
        context_dim: int | None = None,
        dropout: float = 0.1,
    ) -> None:
        super().__init__()
        self.fc1 = nn.Linear(input_dim, hidden_dim)
        self.elu = nn.ELU()
        self.fc2 = nn.Linear(hidden_dim, output_dim)
        self.dropout = nn.Dropout(dropout)
        self.gate = nn.Linear(output_dim, output_dim)
        self.layer_norm = nn.LayerNorm(output_dim)

        self.context_projection: nn.Linear | None = None
        if context_dim is not None:
            self.context_projection = nn.Linear(context_dim, hidden_dim, bias=False)

        self.residual_projection: nn.Linear | None = None
        if input_dim != output_dim:
            self.residual_projection = nn.Linear(input_dim, output_dim)

    def forward(self, x: Tensor, context: Tensor | None = None) -> Tensor:
        residual = x if self.residual_projection is None else self.residual_projection(x)

        hidden = self.fc1(x)
        if self.context_projection is not None and context is not None:
            hidden = hidden + self.context_projection(context)
        hidden = self.elu(hidden)
        hidden = self.fc2(self.dropout(hidden))

        gate_values = torch.sigmoid(self.gate(hidden))
        gated = gate_values * hidden

        return self.layer_norm(gated + residual)


class VariableSelectionNetwork(nn.Module):
    """Variable Selection Network -- selects and weights input features."""

    def __init__(
        self,
        num_inputs: int,
        input_dim: int,
        hidden_dim: int,
        context_dim: int | None = None,
        dropout: float = 0.1,
    ) -> None:
        super().__init__()
        self.num_inputs = num_inputs
        self.hidden_dim = hidden_dim

        self.variable_grns = nn.ModuleList(
            [
                GatedResidualNetwork(input_dim, hidden_dim, hidden_dim, dropout=dropout)
                for _ in range(num_inputs)
            ]
        )

        self.selection_grn = GatedResidualNetwork(
            num_inputs * hidden_dim,
            hidden_dim,
            num_inputs,
            context_dim=context_dim,
            dropout=dropout,
        )

    def forward(self, inputs: list[Tensor], context: Tensor | None = None) -> tuple[Tensor, Tensor]:
        processed = [grn(inp) for grn, inp in zip(self.variable_grns, inputs, strict=False)]
        stacked = torch.stack(processed, dim=-2)
        flattened = stacked.reshape(*stacked.shape[:-2], -1)

        weights = self.selection_grn(flattened, context)
        weights = F.softmax(weights, dim=-1)

        selected = (stacked * weights.unsqueeze(-1)).sum(dim=-2)
        return selected, weights


class InterpretableMultiHeadAttention(nn.Module):
    """Interpretable Multi-Head Attention for temporal patterns."""

    def __init__(self, embed_dim: int, num_heads: int, dropout: float = 0.1) -> None:
        super().__init__()
        self.embed_dim = embed_dim
        self.num_heads = num_heads
        self.head_dim = embed_dim // num_heads

        self.q_proj = nn.Linear(embed_dim, embed_dim)
        self.k_proj = nn.Linear(embed_dim, embed_dim)
        self.v_proj = nn.Linear(embed_dim, embed_dim)
        self.out_proj = nn.Linear(embed_dim, embed_dim)
        self.dropout = nn.Dropout(dropout)
        self.scale = math.sqrt(self.head_dim)

    def forward(
        self,
        query: Tensor,
        key: Tensor,
        value: Tensor,
        mask: Tensor | None = None,
    ) -> tuple[Tensor, Tensor]:
        batch_size = query.size(0)

        q = self.q_proj(query).view(batch_size, -1, self.num_heads, self.head_dim).transpose(1, 2)
        k = self.k_proj(key).view(batch_size, -1, self.num_heads, self.head_dim).transpose(1, 2)
        v = self.v_proj(value).view(batch_size, -1, self.num_heads, self.head_dim).transpose(1, 2)

        attn_weights = torch.matmul(q, k.transpose(-2, -1)) / self.scale
        if mask is not None:
            attn_weights = attn_weights.masked_fill(mask == 0, float("-inf"))
        attn_weights = F.softmax(attn_weights, dim=-1)
        attn_weights = self.dropout(attn_weights)

        attn_output = torch.matmul(attn_weights, v)
        attn_output = attn_output.transpose(1, 2).contiguous().view(batch_size, -1, self.embed_dim)
        attn_output = self.out_proj(attn_output)

        avg_attn_weights = attn_weights.mean(dim=1)
        return attn_output, avg_attn_weights


class TemporalFusionTransformer(nn.Module):
    """
    Custom TFT backbone with graph-augmented variable selection.
    Output: Multi-horizon quantile predictions for all 5 horizons.
    """

    def __init__(
        self,
        num_static: int = 8,
        num_time_known: int = 12,
        num_time_observed: int = 5,
        hidden_size: int = 160,
        num_heads: int = 4,
        dropout: float = 0.1,
        num_quantiles: int = 3,
        graph_embed_dim: int = 128,
        seq_length: int = 30,
    ) -> None:
        super().__init__()

        self.hidden_size = hidden_size
        self.num_quantiles = num_quantiles
        self.seq_length = seq_length

        self.static_vsn = VariableSelectionNetwork(
            num_inputs=num_static,
            input_dim=1,
            hidden_dim=hidden_size,
            context_dim=graph_embed_dim,
            dropout=dropout,
        )

        self.static_context_enrichment = GatedResidualNetwork(
            hidden_size, hidden_size, hidden_size, dropout=dropout
        )
        self.static_context_state_h = GatedResidualNetwork(
            hidden_size, hidden_size, hidden_size, dropout=dropout
        )
        self.static_context_state_c = GatedResidualNetwork(
            hidden_size, hidden_size, hidden_size, dropout=dropout
        )

        self.temporal_vsn = VariableSelectionNetwork(
            num_inputs=num_time_known + num_time_observed,
            input_dim=1,
            hidden_dim=hidden_size,
            context_dim=hidden_size,
            dropout=dropout,
        )

        self.lstm_encoder = nn.LSTM(
            input_size=hidden_size,
            hidden_size=hidden_size,
            batch_first=True,
            dropout=dropout if dropout > 0 else 0,
        )

        self.post_lstm_gate = GatedResidualNetwork(
            hidden_size, hidden_size, hidden_size, dropout=dropout
        )

        self.attention = InterpretableMultiHeadAttention(hidden_size, num_heads, dropout=dropout)
        self.post_attention_gate = GatedResidualNetwork(
            hidden_size, hidden_size, hidden_size, dropout=dropout
        )

        self.output_heads = nn.ModuleDict(
            {horizon: nn.Linear(hidden_size, num_quantiles) for horizon in VALID_HORIZONS}
        )

    def forward(
        self,
        static_inputs: list[Tensor],
        temporal_inputs: list[Tensor],
        graph_embeddings: Tensor | None = None,
    ) -> dict[str, Tensor]:
        static_selected, _static_weights = self.static_vsn(static_inputs, graph_embeddings)

        context_enrichment = self.static_context_enrichment(static_selected)
        h0 = self.static_context_state_h(static_selected).unsqueeze(0)
        c0 = self.static_context_state_c(static_selected).unsqueeze(0)

        temporal_selected, _temporal_weights = self.temporal_vsn(
            temporal_inputs, context_enrichment
        )

        lstm_out, _ = self.lstm_encoder(temporal_selected, (h0, c0))

        gated = self.post_lstm_gate(lstm_out)

        attn_out, _attn_weights = self.attention(gated, gated, gated)
        enriched = self.post_attention_gate(attn_out + gated)

        final_hidden = enriched[:, -1, :]

        outputs: dict[str, Tensor] = {}
        for horizon in VALID_HORIZONS:
            outputs[horizon] = self.output_heads[horizon](final_hidden)

        return outputs
