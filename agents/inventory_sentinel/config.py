"""SYNAPSE Inventory Sentinel -- Configuration."""
from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings


class InventorySentinelConfig(BaseSettings):
    """Inventory Sentinel configuration -- all values overridable via env vars."""

    model_config = {"env_prefix": "IS_", "frozen": True}

    # -- H-MARL Architecture --
    l1_obs_dim: int = Field(default=550)
    l1_action_dim: int = Field(default=100)
    l2_obs_dim: int = Field(default=120)
    l2_action_dim: int = Field(default=3)
    l3_obs_dim: int = Field(default=50)
    l3_action_dim: int = Field(default=100)

    # -- Training --
    l1_hidden_dim: int = Field(default=256)
    l2_hidden_dim: int = Field(default=128)
    l3_hidden_dim: int = Field(default=64)
    learning_rate: float = Field(default=3e-4)
    ppo_epochs: int = Field(default=10)
    ppo_clip: float = Field(default=0.2)
    gamma: float = Field(default=0.99)

    # -- Safety Stock Bounds (INV-IS-001) --
    safety_stock_min: float = Field(default=1.0)
    safety_stock_max: float = Field(default=3.0)

    # -- Flower Federated Learning (I-11) --
    flower_server_address: str = Field(default="flower-server:8080")
    flower_min_clients: int = Field(default=3)
    flower_min_available: int = Field(default=5)
    flower_fraction_fit: float = Field(default=0.5)
    flower_fraction_evaluate: float = Field(default=0.25)

    # -- Infrastructure --
    kafka_bootstrap: str = Field(default="kafka:9092")
    feast_repo_path: str = Field(default="/app/data_fabric/feast")
    mlflow_tracking_uri: str = Field(default="http://mlflow:5000")
    confidence_threshold: float = Field(default=0.7)

    # -- Server --
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8003)
