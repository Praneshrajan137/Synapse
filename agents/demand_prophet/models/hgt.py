"""
SYNAPSE Demand Prophet -- Heterogeneous Graph Transformer Encoder.
Node types: SKU, DarkStore, Zone, WeatherRegion, EventVenue
Edge types: co_purchased, substitutes, stored_at, weather_affected, near_event
I-3: All outputs are ontology-bound -- validated against typed schema.
"""
from __future__ import annotations

from typing import Any

import structlog
import torch
import torch.nn as nn
from torch import Tensor

try:
    from torch_geometric.data import HeteroData  # noqa: F401
    from torch_geometric.nn import HGTConv, Linear

    HAS_PYG = True
except ImportError:
    HAS_PYG = False

logger = structlog.get_logger(__name__)

NODE_TYPES: list[str] = ["sku", "dark_store", "zone", "weather_region", "event_venue"]
EDGE_TYPES: list[tuple[str, str, str]] = [
    ("sku", "co_purchased", "sku"),
    ("sku", "substitutes", "sku"),
    ("sku", "stored_at", "dark_store"),
    ("dark_store", "in_zone", "zone"),
    ("zone", "weather_affected", "weather_region"),
    ("dark_store", "near_event", "event_venue"),
]


class HGTEncoder(nn.Module):
    """
    Heterogeneous Graph Transformer encoder for demand forecasting.
    Produces per-SKU node embeddings that capture relational structure.

    Parameters from config: hidden_dim=128, num_heads=4, num_layers=3, dropout=0.1
    """

    def __init__(
        self,
        hidden_dim: int = 128,
        num_heads: int = 4,
        num_layers: int = 3,
        dropout: float = 0.1,
        node_feature_dims: dict[str, int] | None = None,
    ) -> None:
        super().__init__()

        if not HAS_PYG:
            raise ImportError(
                "torch_geometric is required for HGTEncoder. "
                "Install with: pip install torch-geometric"
            )

        self.hidden_dim = hidden_dim
        self.num_heads = num_heads
        self.num_layers = num_layers

        if node_feature_dims is None:
            node_feature_dims = {
                "sku": 32,
                "dark_store": 16,
                "zone": 8,
                "weather_region": 6,
                "event_venue": 10,
            }

        self.input_projections = nn.ModuleDict(
            {ntype: Linear(dim, hidden_dim) for ntype, dim in node_feature_dims.items()}
        )

        metadata = (NODE_TYPES, EDGE_TYPES)
        self.convs = nn.ModuleList(
            [
                HGTConv(
                    in_channels=hidden_dim,
                    out_channels=hidden_dim,
                    metadata=metadata,
                    heads=num_heads,
                )
                for _ in range(num_layers)
            ]
        )

        self.norms = nn.ModuleList(
            [
                nn.ModuleDict({ntype: nn.LayerNorm(hidden_dim) for ntype in NODE_TYPES})
                for _ in range(num_layers)
            ]
        )

        self.dropout = nn.Dropout(dropout)

    def forward(self, data: Any) -> Tensor:
        """
        Args:
            data: HeteroData with node features and edge indices per type.
        Returns:
            Tensor of shape (num_sku_nodes, hidden_dim).
        """
        x_dict: dict[str, Tensor] = {}
        for ntype in NODE_TYPES:
            if ntype in data.node_types and hasattr(data[ntype], "x"):
                x_dict[ntype] = self.input_projections[ntype](data[ntype].x)
            else:
                logger.debug("missing_node_type", node_type=ntype)

        edge_index_dict = {
            etype: data[etype].edge_index
            for etype in EDGE_TYPES
            if etype in data.edge_types
        }

        for i, conv in enumerate(self.convs):
            x_dict_new = conv(x_dict, edge_index_dict)
            for ntype in x_dict:
                if ntype in x_dict_new:
                    x_dict[ntype] = self.dropout(
                        self.norms[i][ntype](x_dict_new[ntype] + x_dict[ntype])
                    )

        if "sku" not in x_dict:
            raise ValueError("No SKU nodes found in graph -- cannot produce embeddings")

        return x_dict["sku"]

    def get_embedding_dim(self) -> int:
        """Return the output embedding dimension."""
        return self.hidden_dim
