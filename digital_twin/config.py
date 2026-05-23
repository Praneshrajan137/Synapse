"""
SYNAPSE Digital Twin — Configuration via Pydantic BaseSettings.
All thresholds, connection strings, and simulation params are environment-configurable.
"""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings


class TwinConfig(BaseSettings):
    """Digital Twin configuration — all values overridable via TW_ env vars."""

    model_config = {"env_prefix": "TW_", "frozen": True}

    # -- Neo4j (Aura Free) --
    neo4j_uri: str = Field(default="bolt://neo4j:7687")
    neo4j_user: str = Field(default="neo4j")
    neo4j_password: str = Field(default="synapse_graph_2026")

    # -- Kafka --
    kafka_bootstrap: str = Field(default="kafka:9092")
    kafka_group_id: str = Field(default="synapse-digital-twin")

    # -- Simulation --
    simpy_default_duration_hours: int = Field(default=24, ge=1)
    order_arrival_rate: float = Field(
        default=2.0, gt=0.0, description="Poisson λ: orders per minute"
    )
    pick_pack_mean_min: float = Field(default=8.0, gt=0.0)
    pick_pack_std_min: float = Field(default=2.0, gt=0.0)

    # -- Monte Carlo (INV-TW-002) --
    monte_carlo_min_scenarios: int = Field(default=1000, ge=1000)
    monte_carlo_max_workers: int = Field(default=4, ge=1)

    # -- Divergence (INV-TW-003) --
    kl_divergence_threshold: float = Field(
        default=0.1, gt=0.0, description="KL divergence alert threshold (I-12)"
    )
    divergence_check_interval_s: float = Field(default=30.0, gt=0.0)

    # -- What-If API (INV-TW-004) --
    what_if_sla_seconds: float = Field(default=10.0, gt=0.0)

    # -- Domain Randomization (RL sandbox) --
    domain_randomization_pct: float = Field(
        default=0.30, ge=0.0, le=1.0, description="+/-30% on lead times, demand, failures"
    )

    # -- Server --
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8009)
