"""
SYNAPSE Routing Navigator -- 6-Layer Transformer Encoder.
Encodes order features into contextual embeddings for the pointer-network decoder.
"""

from __future__ import annotations

import math

import torch
import torch.nn as nn
from torch import Tensor

ORDER_FEATURE_DIM: int = 10


class PositionalEncoding(nn.Module):
    """Sinusoidal positional encoding for order sequences."""

    def __init__(self, d_model: int, max_len: int = 200, dropout: float = 0.1) -> None:
        super().__init__()
        self.dropout = nn.Dropout(dropout)
        pe = torch.zeros(max_len, d_model)
        position = torch.arange(0, max_len, dtype=torch.float).unsqueeze(1)
        div_term = torch.exp(torch.arange(0, d_model, 2).float() * (-math.log(10000.0) / d_model))
        pe[:, 0::2] = torch.sin(position * div_term)
        pe[:, 1::2] = torch.cos(position * div_term)
        self.register_buffer("pe", pe.unsqueeze(0))

    def forward(self, x: Tensor) -> Tensor:
        x = x + self.pe[:, : x.size(1)]
        return self.dropout(x)


class RouteEncoder(nn.Module):
    """
    6-Layer Transformer encoder for order batch embedding.
    Input: (batch, num_orders, feature_dim)
    Output: (batch, num_orders, embed_dim) contextual order embeddings
    """

    def __init__(
        self,
        feature_dim: int = ORDER_FEATURE_DIM,
        embed_dim: int = 128,
        num_heads: int = 8,
        num_layers: int = 6,
        ff_dim: int = 512,
        dropout: float = 0.1,
        max_orders: int = 200,
    ) -> None:
        super().__init__()
        self.embed_dim = embed_dim
        self.input_projection = nn.Linear(feature_dim, embed_dim)
        self.pos_encoding = PositionalEncoding(embed_dim, max_orders, dropout)

        encoder_layer = nn.TransformerEncoderLayer(
            d_model=embed_dim,
            nhead=num_heads,
            dim_feedforward=ff_dim,
            dropout=dropout,
            batch_first=True,
            activation="gelu",
        )
        self.transformer = nn.TransformerEncoder(encoder_layer, num_layers=num_layers)
        self.layer_norm = nn.LayerNorm(embed_dim)

    def forward(self, orders: Tensor, mask: Tensor | None = None) -> Tensor:
        x = self.input_projection(orders)
        x = self.pos_encoding(x)
        if mask is not None:
            x = self.transformer(x, src_key_padding_mask=mask)
        else:
            x = self.transformer(x)
        return self.layer_norm(x)

    def get_embedding_dim(self) -> int:
        return self.embed_dim
