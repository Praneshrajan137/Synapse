"""
SYNAPSE Disruption Shield -- Configuration via Pydantic BaseSettings.
All thresholds, model paths, and connection strings are environment-configurable.
"""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings


class DisruptionShieldConfig(BaseSettings):
    """Disruption Shield configuration -- all values overridable via env vars."""

    model_config = {"env_prefix": "DS_", "frozen": True}

    anomaly_threshold: float = Field(
        default=0.65, description="Ensemble score above which alert is raised"
    )
    alert_level_thresholds: list[float] = Field(
        default=[0.65, 0.80, 0.95],
        description="Thresholds for alert levels 1, 2, 3",
    )

    if_weight: float = Field(default=0.3, description="IsolationForest ensemble weight")
    lstm_weight: float = Field(default=0.3, description="LSTM Autoencoder ensemble weight")
    gnn_weight: float = Field(default=0.4, description="GNN Structural Anomaly ensemble weight")

    lstm_hidden_dim: int = Field(default=64, description="LSTM hidden dimension")
    lstm_latent_dim: int = Field(default=16, description="LSTM latent space dimension")
    lstm_seq_len: int = Field(default=24, description="Time-series sequence length")
    lstm_input_dim: int = Field(default=12, description="Number of input features")

    gnn_in_channels: int = Field(default=12, description="GNN input feature channels")
    gnn_hidden_channels: int = Field(default=32, description="GNN hidden layer channels")

    pinecone_index_name: str = Field(default="synapse-playbooks")
    pinecone_top_k: int = Field(default=3, description="Number of playbooks to retrieve")
    pinecone_sla_ms: float = Field(default=200.0, description="Pinecone retrieval SLA in ms")
    embedding_model: str = Field(default="all-mpnet-base-v2")

    ollama_base_url: str = Field(default="http://ollama:11434")
    ollama_model: str = Field(default="deepseek-r1:14b")
    ollama_timeout_seconds: float = Field(default=60.0)

    confidence_full: float = Field(default=0.85, description="Confidence when all models healthy")
    confidence_degraded: float = Field(default=0.5, description="Confidence on fallback path")

    kafka_bootstrap: str = Field(default="kafka:9092")
    feast_repo_path: str = Field(default="/app/data_fabric/feast")
    mlflow_tracking_uri: str = Field(default="http://mlflow:5000")

    reward_early_detection_weight: float = Field(default=1.0)
    reward_false_positive_weight: float = Field(default=10.0)
    reward_missed_disruption_weight: float = Field(default=50.0)
    reward_recovery_speed_weight: float = Field(default=1.0)

    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8006)
