"""
SYNAPSE Demand Prophet -- Configuration via Pydantic BaseSettings.
All thresholds, model paths, and connection strings are environment-configurable.
"""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings


class DemandProphetConfig(BaseSettings):
    """Demand Prophet configuration -- all values overridable via env vars."""

    model_config = {"env_prefix": "DP_", "frozen": True}

    # -- Model Architecture --
    hgt_hidden_dim: int = Field(default=128, description="HGT hidden dimension")
    hgt_num_heads: int = Field(default=4, description="HGT attention heads")
    hgt_num_layers: int = Field(default=3, description="HGT message passing layers")
    hgt_dropout: float = Field(default=0.1, ge=0.0, le=0.5)

    tft_hidden_size: int = Field(default=160, description="TFT hidden units")
    tft_attention_heads: int = Field(default=4, description="TFT attention heads")
    tft_num_static: int = Field(default=8, description="Static input features")
    tft_num_time_known: int = Field(default=12, description="Known time-varying features")
    tft_num_time_observed: int = Field(default=5, description="Observed time-varying features")

    gating_hidden: int = Field(default=64, description="Fusion gating MLP hidden dim")

    # -- Training --
    batch_size: int = Field(default=64, ge=1)
    learning_rate: float = Field(default=1e-3, gt=0.0)
    weight_decay: float = Field(default=1e-5, ge=0.0)
    max_epochs: int = Field(default=50, ge=1)
    patience: int = Field(default=10, ge=1, description="Early stopping patience")
    gradient_clip_norm: float = Field(default=1.0, gt=0.0)
    quantile_levels: list[float] = Field(default=[0.1, 0.5, 0.9])

    # -- Conformal Prediction (I-5) --
    conformal_alpha: float = Field(default=0.1, gt=0.0, lt=1.0, description="90% coverage")
    conformal_coverage_target: float = Field(default=0.85, description="Min empirical coverage")

    # -- Inference --
    max_batch_size: int = Field(default=500, description="Max SKUs per batch (PRE-DP-001)")
    inference_timeout_ms: int = Field(default=500, description="Tier 2 SLA")
    confidence_threshold: float = Field(default=0.7, description="HITL escalation threshold (I-5)")

    # -- Drift Detection --
    kl_divergence_threshold: float = Field(default=0.1, description="Drift alert threshold")

    # -- Infrastructure --
    kafka_bootstrap: str = Field(default="kafka:9092")
    feast_repo_path: str = Field(default="/app/data_fabric/feast")
    neo4j_uri: str = Field(default="bolt://neo4j:7687")
    neo4j_user: str = Field(default="neo4j")
    neo4j_password: str = Field(default="synapse_graph_2026")
    mlflow_tracking_uri: str = Field(default="http://mlflow:5000")
    model_checkpoint_path: str = Field(default="/app/models/demand_prophet_best.pt")

    # -- Reward Function (I-2: independent, agent-scoped) --
    reward_crps_weight: float = Field(default=1.0)
    reward_calibration_weight: float = Field(default=0.5)
    reward_event_bonus: float = Field(default=0.1)

    # -- Forecast Horizons --
    valid_horizons: frozenset[str] = Field(default=frozenset({"15min", "1h", "6h", "24h", "7d"}))

    # -- Server --
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8001)
