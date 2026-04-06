"""
SYNAPSE Disruption Shield — Three-Model Anomaly Ensemble.

Models:
  1. IsolationForest (scikit-learn) — point anomaly detection on tabular features
  2. LSTMAutoencoder (PyTorch) — temporal anomaly via reconstruction error
  3. GNNStructuralAnomaly (torch_geometric) — structural anomaly on supply graph

Ensemble score = 0.3*IF + 0.3*LSTM + 0.4*GNN  (INV-DS-007: result in [0, 1])
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import structlog
import torch
import torch.nn as nn
from sklearn.ensemble import IsolationForest
from torch import Tensor

logger = structlog.get_logger(__name__)

try:
    from torch_geometric.data import Data
    from torch_geometric.nn import GCNConv

    _HAS_TORCH_GEOMETRIC = True
except ImportError:
    _HAS_TORCH_GEOMETRIC = False
    logger.warning("torch_geometric_unavailable", fallback="GNN scores default to 0.0")


@dataclass(frozen=True)
class EnsembleResult:
    """Immutable result from the anomaly ensemble."""

    isolation_forest_score: float
    lstm_autoencoder_score: float
    gnn_structural_score: float
    ensemble_score: float
    anomalous_nodes: list[str]


# ---------------------------------------------------------------------------
# Model 1: Isolation Forest wrapper
# ---------------------------------------------------------------------------

class IsolationForestDetector:
    """Isolation Forest for point anomaly detection on tabular features."""

    def __init__(
        self,
        n_estimators: int = 100,
        contamination: float = 0.1,
        random_state: int = 42,
    ) -> None:
        self._model = IsolationForest(
            n_estimators=n_estimators,
            contamination=contamination,
            random_state=random_state,
        )
        self._fitted: bool = False

    @property
    def fitted(self) -> bool:
        return self._fitted

    def fit(self, features: np.ndarray) -> None:
        self._model.fit(features)
        self._fitted = True
        logger.info("isolation_forest_fitted", n_samples=features.shape[0])

    def score(self, features: np.ndarray) -> np.ndarray:
        """Return anomaly scores in [0, 1]. Higher = more anomalous."""
        if not self._fitted:
            logger.warning("isolation_forest_not_fitted", fallback="uniform_score")
            return np.full(features.shape[0], 0.5)
        raw = self._model.decision_function(features)
        normalized = 1.0 - (raw - raw.min()) / (raw.ptp() + 1e-8)
        return np.clip(normalized, 0.0, 1.0)


# ---------------------------------------------------------------------------
# Model 2: LSTM Autoencoder
# ---------------------------------------------------------------------------

class LSTMEncoder(nn.Module):
    """LSTM encoder: sequences -> latent representation."""

    def __init__(self, input_dim: int, hidden_dim: int, latent_dim: int) -> None:
        super().__init__()
        self.lstm = nn.LSTM(input_dim, hidden_dim, batch_first=True)
        self.fc = nn.Linear(hidden_dim, latent_dim)

    def forward(self, x: Tensor) -> Tensor:
        _, (hidden, _) = self.lstm(x)
        return self.fc(hidden.squeeze(0))


class LSTMDecoder(nn.Module):
    """LSTM decoder: latent -> reconstructed sequences."""

    def __init__(
        self, latent_dim: int, hidden_dim: int, output_dim: int, seq_len: int
    ) -> None:
        super().__init__()
        self.seq_len = seq_len
        self.fc = nn.Linear(latent_dim, hidden_dim)
        self.lstm = nn.LSTM(hidden_dim, hidden_dim, batch_first=True)
        self.output_fc = nn.Linear(hidden_dim, output_dim)

    def forward(self, z: Tensor) -> Tensor:
        hidden = self.fc(z).unsqueeze(1).repeat(1, self.seq_len, 1)
        output, _ = self.lstm(hidden)
        return self.output_fc(output)


class LSTMAutoencoder(nn.Module):
    """LSTM Autoencoder for temporal anomaly detection via reconstruction error."""

    def __init__(
        self,
        input_dim: int = 12,
        hidden_dim: int = 64,
        latent_dim: int = 16,
        seq_len: int = 24,
    ) -> None:
        super().__init__()
        self.encoder = LSTMEncoder(input_dim, hidden_dim, latent_dim)
        self.decoder = LSTMDecoder(latent_dim, hidden_dim, input_dim, seq_len)

    def forward(self, x: Tensor) -> Tensor:
        z = self.encoder(x)
        return self.decoder(z)

    @torch.no_grad()
    def anomaly_score(self, x: Tensor) -> Tensor:
        """Per-sample reconstruction error normalized to [0, 1]."""
        self.eval()
        recon = self.forward(x)
        mse = ((x - recon) ** 2).mean(dim=(1, 2))
        if mse.max() - mse.min() < 1e-8:
            return torch.zeros(mse.shape[0])
        normalized = (mse - mse.min()) / (mse.max() - mse.min())
        return normalized.clamp(0.0, 1.0)


# ---------------------------------------------------------------------------
# Model 3: GNN Structural Anomaly
# ---------------------------------------------------------------------------

if _HAS_TORCH_GEOMETRIC:

    class GNNStructuralAnomaly(nn.Module):
        """GCN-based structural anomaly detector on supply chain graph."""

        def __init__(self, in_channels: int = 12, hidden_channels: int = 32) -> None:
            super().__init__()
            self.conv1 = GCNConv(in_channels, hidden_channels)
            self.conv2 = GCNConv(hidden_channels, hidden_channels)
            self.decoder = nn.Linear(hidden_channels, in_channels)
            self.relu = nn.ReLU()

        def forward(self, data: Data) -> Tensor:
            x, edge_index = data.x, data.edge_index
            h = self.relu(self.conv1(x, edge_index))
            h = self.relu(self.conv2(h, edge_index))
            return self.decoder(h)

        @torch.no_grad()
        def anomaly_score(self, data: Data) -> Tensor:
            """Per-node reconstruction error normalized to [0, 1]."""
            self.eval()
            recon = self.forward(data)
            mse = ((data.x - recon) ** 2).mean(dim=1)
            if mse.max() - mse.min() < 1e-8:
                return torch.zeros(mse.shape[0])
            normalized = (mse - mse.min()) / (mse.max() - mse.min())
            return normalized.clamp(0.0, 1.0)

else:

    class GNNStructuralAnomaly(nn.Module):  # type: ignore[no-redef]
        """Fallback stub when torch_geometric is unavailable (I-7)."""

        def __init__(self, in_channels: int = 12, hidden_channels: int = 32) -> None:
            super().__init__()
            self._in_channels = in_channels

        def forward(self, data: Any) -> Tensor:
            return torch.zeros(1)

        @torch.no_grad()
        def anomaly_score(self, data: Any) -> Tensor:
            logger.warning("gnn_fallback_stub", reason="torch_geometric not installed")
            n_nodes = data.x.shape[0] if hasattr(data, "x") else 1
            return torch.full((n_nodes,), 0.0)


# ---------------------------------------------------------------------------
# Ensemble
# ---------------------------------------------------------------------------

class AnomalyEnsemble:
    """Weighted three-model ensemble: 0.3*IF + 0.3*LSTM + 0.4*GNN."""

    def __init__(
        self,
        if_weight: float = 0.3,
        lstm_weight: float = 0.3,
        gnn_weight: float = 0.4,
        lstm_kwargs: dict[str, Any] | None = None,
        gnn_kwargs: dict[str, Any] | None = None,
    ) -> None:
        assert abs(if_weight + lstm_weight + gnn_weight - 1.0) < 1e-6, (
            "Ensemble weights must sum to 1.0"
        )
        self.if_weight = if_weight
        self.lstm_weight = lstm_weight
        self.gnn_weight = gnn_weight

        self.isolation_forest = IsolationForestDetector()
        self.lstm_autoencoder = LSTMAutoencoder(**(lstm_kwargs or {}))
        self.gnn_detector = GNNStructuralAnomaly(**(gnn_kwargs or {}))

    def score(
        self,
        tabular_features: np.ndarray,
        temporal_sequences: Tensor | None = None,
        graph_data: Any | None = None,
        node_ids: list[str] | None = None,
        anomaly_threshold: float = 0.65,
    ) -> EnsembleResult:
        """Run ensemble and return weighted anomaly score.

        Each sub-model that is unavailable contributes 0.0 and logs a warning.
        """
        n_samples = tabular_features.shape[0]

        if_scores = self.isolation_forest.score(tabular_features)
        if_mean = float(np.mean(if_scores))

        lstm_mean = 0.0
        if temporal_sequences is not None:
            lstm_scores = self.lstm_autoencoder.anomaly_score(temporal_sequences)
            lstm_mean = float(lstm_scores.mean().item())
        else:
            logger.info("lstm_skipped", reason="no temporal sequences provided")

        gnn_mean = 0.0
        if graph_data is not None:
            gnn_scores = self.gnn_detector.anomaly_score(graph_data)
            gnn_mean = float(gnn_scores.mean().item())
        else:
            logger.info("gnn_skipped", reason="no graph data provided")

        ensemble = (
            self.if_weight * if_mean
            + self.lstm_weight * lstm_mean
            + self.gnn_weight * gnn_mean
        )
        ensemble = max(0.0, min(1.0, ensemble))

        anomalous: list[str] = []
        if node_ids is not None and graph_data is not None:
            gnn_per_node = self.gnn_detector.anomaly_score(graph_data)
            for idx, nid in enumerate(node_ids):
                if idx < len(gnn_per_node) and float(gnn_per_node[idx]) > anomaly_threshold:
                    anomalous.append(nid)

        logger.info(
            "ensemble_scored",
            if_score=round(if_mean, 4),
            lstm_score=round(lstm_mean, 4),
            gnn_score=round(gnn_mean, 4),
            ensemble=round(ensemble, 4),
            anomalous_nodes=len(anomalous),
        )

        return EnsembleResult(
            isolation_forest_score=if_mean,
            lstm_autoencoder_score=lstm_mean,
            gnn_structural_score=gnn_mean,
            ensemble_score=ensemble,
            anomalous_nodes=anomalous,
        )
