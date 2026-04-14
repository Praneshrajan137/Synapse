"""
SYNAPSE Pricing Oracle -- Configuration via Pydantic BaseSettings.
All thresholds, model paths, and connection strings are environment-configurable.
"""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings


class PricingOracleConfig(BaseSettings):
    """Pricing Oracle configuration -- all values overridable via env vars."""

    model_config = {"env_prefix": "PO_", "frozen": True}

    # -- Essential Cap (I-6: hard guardrail, NEVER learned) --
    essential_cap: float = Field(
        default=1.3,
        description="Maximum price multiplier for essential items (INV-PO-001)",
    )

    # -- Product Categories --
    categories: frozenset[str] = Field(
        default=frozenset({"essential", "snack", "beverage", "dairy", "produce"})
    )

    # -- MADDPG Architecture --
    actor_hidden_dim: int = Field(default=128, description="Actor network hidden dim")
    actor_num_layers: int = Field(default=3, description="Actor network depth")
    critic_hidden_dim: int = Field(default=256, description="Critic network hidden dim")
    critic_num_layers: int = Field(default=3, description="Critic network depth")
    action_dim: int = Field(default=1, description="Price multiplier per agent")
    obs_dim: int = Field(default=24, description="Observation dimension per agent")
    num_agents: int = Field(default=5, description="One per category")
    gamma: float = Field(default=0.99, ge=0.0, le=1.0, description="Discount factor")
    tau: float = Field(default=0.01, ge=0.0, le=1.0, description="Soft update rate")
    actor_lr: float = Field(default=1e-4, gt=0.0, description="Actor learning rate")
    critic_lr: float = Field(default=1e-3, gt=0.0, description="Critic learning rate")
    buffer_size: int = Field(default=100_000, ge=1000, description="Replay buffer size")
    batch_size: int = Field(default=64, ge=1)

    # -- Causal Estimation --
    dml_cv_folds: int = Field(default=5, ge=2, description="DML cross-validation folds")
    dml_max_iter: int = Field(default=1000, ge=100, description="LassoCV max iterations")

    # -- Training --
    max_episodes: int = Field(default=5000, ge=1)
    learning_rate: float = Field(default=1e-3, gt=0.0)
    weight_decay: float = Field(default=1e-5, ge=0.0)
    gradient_clip_norm: float = Field(default=1.0, gt=0.0)

    # -- Reward Weights (I-2: agent-scoped) --
    reward_revenue_weight: float = Field(default=1.0)
    reward_elasticity_weight: float = Field(default=0.5)
    reward_essential_cap_penalty: float = Field(default=-5.0)
    reward_competitor_gap_penalty: float = Field(default=-2.0)

    # -- Inference --
    max_batch_size: int = Field(default=200, description="Max SKUs per batch (PRE-PO-004)")
    inference_timeout_ms: int = Field(default=500, description="Tier 2 SLA")
    confidence_threshold: float = Field(default=0.7, description="HITL escalation threshold (I-5)")

    # -- Infrastructure --
    kafka_bootstrap: str = Field(default="kafka:9092")
    feast_repo_path: str = Field(default="/app/data_fabric/feast")
    neo4j_uri: str = Field(default="bolt://neo4j:7687")
    neo4j_user: str = Field(default="neo4j")
    neo4j_password: str = Field(default="synapse_graph_2026")
    mlflow_tracking_uri: str = Field(default="http://mlflow:5000")
    model_checkpoint_path: str = Field(default="/app/models/pricing_oracle_best.pt")

    # -- Server --
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8005)
