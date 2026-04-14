"""SYNAPSE Routing Navigator -- Configuration via Pydantic BaseSettings."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings


class RoutingNavigatorConfig(BaseSettings):
    """Routing Navigator configuration -- all values overridable via env vars."""

    model_config = {"env_prefix": "RN_", "frozen": True}

    # -- Encoder Architecture --
    encoder_layers: int = Field(default=6)
    encoder_heads: int = Field(default=8)
    encoder_dim: int = Field(default=128)
    encoder_dropout: float = Field(default=0.1)

    # -- Decoder --
    decoder_hidden: int = Field(default=128)

    # -- Student (distilled MLP for Tier 1) --
    student_hidden_1: int = Field(default=256)
    student_hidden_2: int = Field(default=128)
    student_temperature: float = Field(default=3.0, description="Distillation temperature")

    # -- Training --
    num_episodes: int = Field(default=500_000)
    batch_size: int = Field(default=64)
    learning_rate: float = Field(default=1e-4)
    gamma: float = Field(default=0.99, description="Discount factor")
    entropy_coeff: float = Field(default=0.01)
    max_orders_per_batch: int = Field(default=50)

    # -- Reward Weights (I-2: independent) --
    w_time: float = Field(default=0.4)
    w_fuel: float = Field(default=0.2)
    w_freshness: float = Field(default=0.25)
    w_fairness: float = Field(default=0.15)

    # -- Inference --
    tier1_latency_ms: int = Field(default=100, description="Tier 1 SLA for student MLP")
    tier2_latency_ms: int = Field(default=500, description="Tier 2 SLA for expert model")
    max_orders: int = Field(default=200)
    max_shift_minutes: int = Field(default=480, description="8-hour shift cap (I-6)")
    confidence_threshold: float = Field(default=0.7)

    # -- OSRM --
    osrm_endpoint: str = Field(default="http://osrm:5000")

    # -- Infrastructure --
    kafka_bootstrap: str = Field(default="kafka:9092")
    feast_repo_path: str = Field(default="/app/data_fabric/feast")
    mlflow_tracking_uri: str = Field(default="http://mlflow:5000")
    model_checkpoint_path: str = Field(default="/app/models/routing_expert.pt")
    student_checkpoint_path: str = Field(default="/app/models/routing_student.pt")

    # -- Server --
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8002)
