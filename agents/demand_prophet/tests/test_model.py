"""
SYNAPSE Demand Prophet -- Model unit tests.
Verifies forward pass, output shapes, and invariant compliance.
"""

from __future__ import annotations

import pytest
import torch

from agents.demand_prophet.models.hgt import HGTEncoder
from agents.demand_prophet.models.hybrid import DemandProphetHybrid
from agents.demand_prophet.models.tft import VALID_HORIZONS, TemporalFusionTransformer


def _make_dummy_hetero_data(num_skus: int = 10) -> object:
    """Create minimal HeteroData for testing."""
    from torch_geometric.data import HeteroData

    data = HeteroData()

    data["sku"].x = torch.randn(num_skus, 32)
    data["dark_store"].x = torch.randn(5, 16)
    data["zone"].x = torch.randn(3, 8)
    data["weather_region"].x = torch.randn(2, 6)
    data["event_venue"].x = torch.randn(4, 10)

    data["sku", "co_purchased", "sku"].edge_index = torch.tensor(
        [[0, 1, 2], [1, 2, 0]], dtype=torch.long
    )
    data["sku", "stored_at", "dark_store"].edge_index = torch.tensor(
        [[0, 1, 2, 3, 4], [0, 1, 2, 3, 4]], dtype=torch.long
    )
    data["dark_store", "in_zone", "zone"].edge_index = torch.tensor(
        [[0, 1, 2, 3, 4], [0, 0, 1, 1, 2]], dtype=torch.long
    )

    return data


class TestHGTEncoder:
    """Tests for the Heterogeneous Graph Transformer encoder."""

    def test_forward_pass(self) -> None:
        encoder = HGTEncoder(hidden_dim=64, num_heads=2, num_layers=2)
        data = _make_dummy_hetero_data(num_skus=10)
        embeddings = encoder(data)
        assert embeddings.shape == (10, 64), f"Expected (10, 64), got {embeddings.shape}"

    def test_embedding_dim(self) -> None:
        encoder = HGTEncoder(hidden_dim=128)
        assert encoder.get_embedding_dim() == 128

    def test_no_sku_nodes_raises(self) -> None:
        from torch_geometric.data import HeteroData

        encoder = HGTEncoder(hidden_dim=64, num_heads=2, num_layers=1)
        data = HeteroData()
        data["dark_store"].x = torch.randn(5, 16)
        with pytest.raises((ValueError, KeyError)):
            encoder(data)


class TestTFT:
    """Tests for the Temporal Fusion Transformer backbone."""

    def test_forward_pass(self) -> None:
        tft = TemporalFusionTransformer(
            num_static=4,
            num_time_known=6,
            num_time_observed=3,
            hidden_size=32,
            num_heads=2,
            graph_embed_dim=64,
        )
        batch_size = 4
        seq_len = 30

        static = [torch.randn(batch_size, 1) for _ in range(4)]
        temporal = [torch.randn(batch_size, seq_len, 1) for _ in range(9)]
        graph_emb = torch.randn(batch_size, 64)

        outputs = tft(static, temporal, graph_emb)
        assert set(outputs.keys()) == set(VALID_HORIZONS)
        for h, tensor in outputs.items():
            assert tensor.shape == (batch_size, 3), f"Horizon {h}: expected (4, 3)"

    def test_temporal_input_count_must_match_contract(self) -> None:
        tft = TemporalFusionTransformer(
            num_static=4,
            num_time_known=6,
            num_time_observed=3,
            hidden_size=32,
            num_heads=2,
            graph_embed_dim=64,
        )
        batch_size = 4
        seq_len = 30

        static = [torch.randn(batch_size, 1) for _ in range(4)]
        temporal = [torch.randn(batch_size, seq_len, 1) for _ in range(10)]
        graph_emb = torch.randn(batch_size, 64)

        with pytest.raises(ValueError, match="expected 9 inputs"):
            tft(static, temporal, graph_emb)


class TestHybrid:
    """Tests for the full HGT-TFT hybrid model."""

    def test_forward_pass(self) -> None:
        model = DemandProphetHybrid(
            hgt_hidden_dim=64,
            hgt_num_heads=2,
            hgt_num_layers=1,
            tft_hidden_size=32,
            tft_num_heads=2,
            tft_num_static=4,
            tft_num_time_known=6,
            tft_num_time_observed=3,
        )
        data = _make_dummy_hetero_data(num_skus=4)
        static = [torch.randn(4, 1) for _ in range(4)]
        temporal = [torch.randn(4, 30, 1) for _ in range(9)]

        outputs = model(data, static, temporal)

        assert set(outputs.keys()) == set(VALID_HORIZONS)

        for h, tensor in outputs.items():
            assert (tensor >= 0).all(), f"Horizon {h} has negative values (violates INV-DP-006)"

    def test_model_summary(self) -> None:
        model = DemandProphetHybrid(
            hgt_hidden_dim=64,
            hgt_num_heads=2,
            hgt_num_layers=1,
            tft_hidden_size=32,
            tft_num_heads=2,
            tft_num_static=4,
            tft_num_time_known=6,
            tft_num_time_observed=3,
        )
        summary = model.get_model_summary()
        assert summary["total_params"] > 0
        assert summary["trainable_params"] > 0
        assert summary["total_params"] == (
            summary["hgt_params"] + summary["tft_params"] + summary["fusion_params"]
        )

    def test_deterministic_output(self) -> None:
        torch.manual_seed(42)
        model = DemandProphetHybrid(
            hgt_hidden_dim=64,
            hgt_num_heads=2,
            hgt_num_layers=1,
            tft_hidden_size=32,
            tft_num_heads=2,
            tft_num_static=4,
            tft_num_time_known=6,
            tft_num_time_observed=3,
        )
        model.eval()

        data = _make_dummy_hetero_data(num_skus=4)
        static = [torch.randn(4, 1) for _ in range(4)]
        temporal = [torch.randn(4, 30, 1) for _ in range(9)]

        with torch.no_grad():
            out1 = model(data, static, temporal)
            out2 = model(data, static, temporal)

        for h in VALID_HORIZONS:
            assert torch.allclose(out1[h], out2[h]), f"Non-deterministic output for {h}"
