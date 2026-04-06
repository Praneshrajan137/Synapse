"""SYNAPSE Supplier Trust -- Configuration."""
from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings


class SupplierTrustConfig(BaseSettings):
    """Supplier Trust configuration -- all values overridable via env vars."""

    model_config = {"env_prefix": "ST_", "frozen": True}

    # -- GNN Architecture --
    gnn_hidden_dim: int = Field(default=128)
    gnn_out_dim: int = Field(default=64)
    gnn_num_layers: int = Field(default=3)
    gnn_dropout: float = Field(default=0.1)

    # -- Bayesian Lead-Time --
    svi_num_steps: int = Field(default=1000)
    svi_learning_rate: float = Field(default=0.01)
    prior_mu: float = Field(default=2.0)
    prior_sigma: float = Field(default=0.5)
    num_posterior_samples: int = Field(default=500)

    # -- Trust Scoring --
    new_vendor_trust_floor: float = Field(default=0.3)
    late_delivery_decay: float = Field(default=0.05)
    trust_ema_alpha: float = Field(default=0.3)
    confidence_threshold: float = Field(default=0.7)

    # -- Infrastructure --
    neo4j_uri: str = Field(default="bolt://neo4j:7687")
    neo4j_user: str = Field(default="neo4j")
    neo4j_password: str = Field(default="synapse")
    kafka_bootstrap: str = Field(default="kafka:9092")
    feast_repo_path: str = Field(default="/app/data_fabric/feast")
    mlflow_tracking_uri: str = Field(default="http://mlflow:5000")

    # -- Server --
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8007)
