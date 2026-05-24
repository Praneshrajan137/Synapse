"""
SYNAPSE Disruption Shield — Inference Pipeline.
Orchestrates anomaly ensemble, reasoning chain, and playbook retrieval
to produce a DisruptionAlert.

Sprint-8 elevation:
  * Optional `GraphClient` for Neo4j blast-radius queries (ADR-005, WS-8.4).
  * DbC pre/post contracts (ADR-015 Layer 5).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import numpy as np
import structlog
import torch
from pydantic import BaseModel, Field
from synapse_common.dbc import post, pre

from agents.disruption_shield.config import DisruptionShieldConfig
from agents.disruption_shield.inference.playbook_retriever import (
    PlaybookRetriever,
)
from agents.disruption_shield.models.anomaly_ensemble import AnomalyEnsemble
from agents.disruption_shield.models.reasoning import DeepSeekReasoner

if TYPE_CHECKING:
    from synapse_common.graph_client import GraphClient

logger = structlog.get_logger(__name__)


class DisruptionRequest(BaseModel):
    """Input request for disruption detection."""

    node_ids: list[str] = Field(..., min_length=1)
    tabular_features: list[list[float]] = Field(..., min_length=1)
    temporal_sequences: list[list[list[float]]] | None = None
    edge_index: list[list[int]] | None = None
    graph_node_features: list[list[float]] | None = None
    context: dict[str, Any] = Field(default_factory=dict)
    anomaly_threshold: float = Field(default=0.65, gt=0.0, lt=1.0)


class PlaybookSummary(BaseModel):
    """Playbook summary in disruption alert output."""

    id: str
    title: str
    relevance_score: float = Field(ge=0.0, le=1.0)


class DisruptionAlert(BaseModel):
    """Output disruption alert — validates against disruption_alert.schema.json."""

    alert_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    alert_level: int = Field(ge=0, le=3)
    ensemble_score: float = Field(ge=0.0, le=1.0)
    isolation_forest_score: float = Field(ge=0.0, le=1.0)
    lstm_autoencoder_score: float = Field(ge=0.0, le=1.0)
    gnn_structural_score: float = Field(ge=0.0, le=1.0)
    anomalous_nodes: list[str]
    reasoning_chain: list[str] = Field(min_length=1)
    severity: str
    summary: str
    playbooks: list[PlaybookSummary]
    timestamp: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    confidence: float = Field(ge=0.0, le=1.0)


class DisruptionShieldPipeline:
    """End-to-end disruption detection pipeline."""

    def __init__(
        self,
        config: DisruptionShieldConfig | None = None,
        ensemble: AnomalyEnsemble | None = None,
        reasoner: DeepSeekReasoner | None = None,
        retriever: PlaybookRetriever | None = None,
        graph_client: GraphClient | None = None,
    ) -> None:
        self._config = config or DisruptionShieldConfig()
        self._graph = graph_client

        self.ensemble = ensemble or AnomalyEnsemble(
            if_weight=self._config.if_weight,
            lstm_weight=self._config.lstm_weight,
            gnn_weight=self._config.gnn_weight,
            lstm_kwargs={
                "input_dim": self._config.lstm_input_dim,
                "hidden_dim": self._config.lstm_hidden_dim,
                "latent_dim": self._config.lstm_latent_dim,
                "seq_len": self._config.lstm_seq_len,
            },
            gnn_kwargs={
                "in_channels": self._config.gnn_in_channels,
                "hidden_channels": self._config.gnn_hidden_channels,
            },
        )

        self.reasoner = reasoner or DeepSeekReasoner(
            ollama_base_url=self._config.ollama_base_url,
            model=self._config.ollama_model,
            timeout_seconds=self._config.ollama_timeout_seconds,
        )

        self.retriever = retriever or PlaybookRetriever(
            index_name=self._config.pinecone_index_name,
            embedding_model=self._config.embedding_model,
            top_k=self._config.pinecone_top_k,
            sla_ms=self._config.pinecone_sla_ms,
        )

    @pre(lambda self, request: len(request.node_ids) >= 1)
    @post(lambda result: 0 <= result.alert_level <= 3)
    @post(lambda result: 0.0 <= result.confidence <= 1.0)
    def detect(self, request: DisruptionRequest) -> DisruptionAlert:
        """Run full disruption detection pipeline."""
        tabular = np.array(request.tabular_features)

        temporal_tensor: torch.Tensor | None = None
        if request.temporal_sequences is not None:
            temporal_tensor = torch.tensor(request.temporal_sequences, dtype=torch.float32)

        graph_data: Any = None
        if request.graph_node_features is not None and request.edge_index is not None:
            try:
                from torch_geometric.data import Data

                graph_data = Data(
                    x=torch.tensor(request.graph_node_features, dtype=torch.float32),
                    edge_index=torch.tensor(request.edge_index, dtype=torch.long),
                )
            except ImportError:
                logger.warning("torch_geometric_unavailable", fallback="gnn_skipped")

        if not self.ensemble.isolation_forest.fitted:
            self.ensemble.isolation_forest.fit(tabular)

        result = self.ensemble.score(
            tabular_features=tabular,
            temporal_sequences=temporal_tensor,
            graph_data=graph_data,
            node_ids=request.node_ids,
            anomaly_threshold=request.anomaly_threshold,
        )

        alert_level = self._compute_alert_level(result.ensemble_score)

        reasoning = self.reasoner.reason(
            ensemble_score=result.ensemble_score,
            anomalous_nodes=result.anomalous_nodes,
            context=request.context,
        )

        query = (
            f"Supply chain disruption: score={result.ensemble_score:.3f}, "
            f"affected_nodes={len(result.anomalous_nodes)}, "
            f"severity={reasoning.get('severity', 'unknown')}"
        )
        playbook_matches = self.retriever.retrieve(query)
        playbooks = [
            PlaybookSummary(
                id=p.id,
                title=p.title,
                relevance_score=min(p.relevance_score, 1.0),
            )
            for p in playbook_matches
        ]

        confidence = self._config.confidence_full
        if graph_data is None or temporal_tensor is None:
            confidence = self._config.confidence_degraded

        return DisruptionAlert(
            alert_level=alert_level,
            ensemble_score=result.ensemble_score,
            isolation_forest_score=result.isolation_forest_score,
            lstm_autoencoder_score=result.lstm_autoencoder_score,
            gnn_structural_score=result.gnn_structural_score,
            anomalous_nodes=result.anomalous_nodes,
            reasoning_chain=reasoning.get("reasoning_steps", ["No reasoning available"]),
            severity=reasoning.get("severity", "unknown"),
            summary=reasoning.get("summary", ""),
            playbooks=playbooks,
            confidence=confidence,
        )

    def blast_radius(
        self,
        node_id: str,
        *,
        city: str = "bengaluru",
        hops: int = 2,
    ) -> list[dict[str, Any]]:
        """Query Neo4j for downstream nodes within `hops` of `node_id` (WS-8.4).

        Returns a list of `{kind, id}` dicts the orchestrator can use to gate
        Tier-3/4 mitigation playbooks. Empty list when the graph is offline.
        """
        if self._graph is None:
            return []
        return self._graph.query(
            "disruption_blast_radius",
            {"node_id": node_id, "city": city, "hops": hops},
        )

    def _compute_alert_level(self, ensemble_score: float) -> int:
        """Map ensemble score to alert level 0-3 using config thresholds."""
        level = 0
        for threshold in self._config.alert_level_thresholds:
            if ensemble_score >= threshold:
                level += 1
            else:
                break
        return level
