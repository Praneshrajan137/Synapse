"""
SYNAPSE Supplier Trust -- GNN Trust Embeddings on Temporal Knowledge Graph.

Uses PyG HeteroConv with typed nodes: Supplier, SKU, DarkStore.
Message-passing on heterogeneous edges captures supplier–product–store
relationships over time windows.
"""
from __future__ import annotations

from typing import Any

import structlog
import torch
from torch import Tensor, nn
from torch_geometric.data import HeteroData
from torch_geometric.nn import HeteroConv, SAGEConv

logger = structlog.get_logger(__name__)


class SupplierTrustGNN(nn.Module):
    """Heterogeneous GNN producing trust-relevant embeddings per supplier node.

    Graph schema (3 node types, 4 edge types):
      - Supplier  --[supplies]--> SKU
      - SKU       --[stocked_at]--> DarkStore
      - Supplier  --[delivers_to]--> DarkStore
      - DarkStore --[orders_from]--> Supplier
    """

    def __init__(
        self,
        supplier_in_dim: int = 16,
        sku_in_dim: int = 12,
        store_in_dim: int = 10,
        hidden_dim: int = 128,
        out_dim: int = 64,
        num_layers: int = 3,
        dropout: float = 0.1,
    ) -> None:
        super().__init__()
        self.num_layers = num_layers

        self.projections = nn.ModuleDict({
            "supplier": nn.Linear(supplier_in_dim, hidden_dim),
            "sku": nn.Linear(sku_in_dim, hidden_dim),
            "darkstore": nn.Linear(store_in_dim, hidden_dim),
        })

        self.convs = nn.ModuleList()
        self.norms = nn.ModuleList()
        for _ in range(num_layers):
            conv_dict: dict[str, SAGEConv] = {
                ("supplier", "supplies", "sku"): SAGEConv(hidden_dim, hidden_dim),
                ("sku", "stocked_at", "darkstore"): SAGEConv(hidden_dim, hidden_dim),
                ("supplier", "delivers_to", "darkstore"): SAGEConv(hidden_dim, hidden_dim),
                ("darkstore", "orders_from", "supplier"): SAGEConv(hidden_dim, hidden_dim),
            }
            self.convs.append(HeteroConv(conv_dict, aggr="mean"))
            self.norms.append(nn.ModuleDict({
                "supplier": nn.LayerNorm(hidden_dim),
                "sku": nn.LayerNorm(hidden_dim),
                "darkstore": nn.LayerNorm(hidden_dim),
            }))

        self.dropout = nn.Dropout(dropout)
        self.head = nn.Linear(hidden_dim, out_dim)

    def forward(self, data: HeteroData) -> dict[str, Tensor]:
        """Forward pass returning embeddings per node type.

        Args:
            data: PyG HeteroData with node features keyed by type and
                  edge_index keyed by (src_type, rel, dst_type).

        Returns:
            Dict mapping node type name to embedding tensor.
        """
        x_dict: dict[str, Tensor] = {}
        for ntype, proj in self.projections.items():
            if ntype in data.node_types and hasattr(data[ntype], "x"):
                x_dict[ntype] = proj(data[ntype].x)

        edge_index_dict = {
            etype: data[etype].edge_index
            for etype in data.edge_types
            if hasattr(data[etype], "edge_index")
        }

        for i in range(self.num_layers):
            x_dict_new = self.convs[i](x_dict, edge_index_dict)
            for ntype in x_dict_new:
                x_dict_new[ntype] = self.norms[i][ntype](x_dict_new[ntype])
                x_dict_new[ntype] = torch.relu(x_dict_new[ntype])
                x_dict_new[ntype] = self.dropout(x_dict_new[ntype])
                if ntype in x_dict:
                    x_dict_new[ntype] = x_dict_new[ntype] + x_dict[ntype]
            x_dict = x_dict_new

        out: dict[str, Tensor] = {}
        for ntype, emb in x_dict.items():
            out[ntype] = self.head(emb)

        return out

    def get_supplier_embeddings(self, data: HeteroData) -> Tensor:
        """Convenience: extract only supplier node embeddings."""
        all_emb = self.forward(data)
        if "supplier" not in all_emb:
            logger.warning("no_supplier_nodes_in_graph")
            return torch.empty(0, self.head.out_features)
        return all_emb["supplier"]
