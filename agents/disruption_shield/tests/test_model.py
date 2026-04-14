"""
SYNAPSE Disruption Shield — Model Tests.
Tests anomaly ensemble forward pass and individual model components.
"""

from __future__ import annotations

import numpy as np
import pytest
import torch

from agents.disruption_shield.models.anomaly_ensemble import (
    AnomalyEnsemble,
    GNNStructuralAnomaly,
    IsolationForestDetector,
    LSTMAutoencoder,
)


class TestIsolationForestDetector:
    """Test IsolationForest wrapper."""

    @pytest.fixture
    def fitted_detector(self) -> IsolationForestDetector:
        det = IsolationForestDetector()
        rng = np.random.default_rng(42)
        data = rng.standard_normal((200, 12))
        det.fit(data)
        return det

    def test_score_returns_valid_range(self, fitted_detector: IsolationForestDetector) -> None:
        rng = np.random.default_rng(99)
        features = rng.standard_normal((10, 12))
        scores = fitted_detector.score(features)
        assert scores.shape == (10,)
        assert np.all(scores >= 0.0)
        assert np.all(scores <= 1.0)

    def test_unfitted_returns_fallback(self) -> None:
        det = IsolationForestDetector()
        features = np.zeros((5, 12))
        scores = det.score(features)
        assert scores.shape == (5,)
        assert np.allclose(scores, 0.5)


class TestLSTMAutoencoder:
    """Test LSTM Autoencoder forward pass and anomaly scoring."""

    @pytest.fixture
    def model(self) -> LSTMAutoencoder:
        return LSTMAutoencoder(input_dim=12, hidden_dim=64, latent_dim=16, seq_len=24)

    def test_forward_pass_shape(self, model: LSTMAutoencoder) -> None:
        x = torch.randn(4, 24, 12)
        out = model(x)
        assert out.shape == (4, 24, 12)

    def test_anomaly_score_range(self, model: LSTMAutoencoder) -> None:
        x = torch.randn(8, 24, 12)
        scores = model.anomaly_score(x)
        assert scores.shape == (8,)
        assert torch.all(scores >= 0.0)
        assert torch.all(scores <= 1.0)

    def test_encoder_decoder_consistency(self, model: LSTMAutoencoder) -> None:
        x = torch.randn(2, 24, 12)
        z = model.encoder(x)
        assert z.shape == (2, 16)
        recon = model.decoder(z)
        assert recon.shape == (2, 24, 12)


class TestGNNStructuralAnomaly:
    """Test GNN structural anomaly detector."""

    def test_anomaly_score_range(self) -> None:
        model = GNNStructuralAnomaly(in_channels=12, hidden_channels=32)
        try:
            from torch_geometric.data import Data

            data = Data(
                x=torch.randn(10, 12),
                edge_index=torch.tensor([[0, 1, 2, 3], [1, 2, 3, 0]], dtype=torch.long),
            )
            scores = model.anomaly_score(data)
            assert scores.shape == (10,)
            assert torch.all(scores >= 0.0)
            assert torch.all(scores <= 1.0)
        except ImportError:
            pytest.skip("torch_geometric not installed")


class TestAnomalyEnsemble:
    """Test ensemble scoring."""

    @pytest.fixture
    def ensemble(self) -> AnomalyEnsemble:
        return AnomalyEnsemble()

    def test_ensemble_weights_sum_to_one(self, ensemble: AnomalyEnsemble) -> None:
        total = ensemble.if_weight + ensemble.lstm_weight + ensemble.gnn_weight
        assert abs(total - 1.0) < 1e-6

    def test_ensemble_score_in_valid_range(self, ensemble: AnomalyEnsemble) -> None:
        rng = np.random.default_rng(42)
        features = rng.standard_normal((20, 12))
        ensemble.isolation_forest.fit(features)

        result = ensemble.score(
            tabular_features=features,
            node_ids=[f"node-{i}" for i in range(20)],
        )
        assert 0.0 <= result.ensemble_score <= 1.0
        assert 0.0 <= result.isolation_forest_score <= 1.0

    def test_ensemble_with_temporal_data(self, ensemble: AnomalyEnsemble) -> None:
        rng = np.random.default_rng(42)
        tabular = rng.standard_normal((5, 12))
        temporal = torch.randn(5, 24, 12)
        ensemble.isolation_forest.fit(tabular)

        result = ensemble.score(
            tabular_features=tabular,
            temporal_sequences=temporal,
        )
        assert 0.0 <= result.ensemble_score <= 1.0
        assert isinstance(result.anomalous_nodes, list)

    def test_invalid_weights_rejected(self) -> None:
        with pytest.raises(AssertionError):
            AnomalyEnsemble(if_weight=0.5, lstm_weight=0.5, gnn_weight=0.5)
