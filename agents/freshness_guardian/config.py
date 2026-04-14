"""
SYNAPSE Freshness Guardian -- Configuration via Pydantic BaseSettings.
All thresholds, model paths, and connection strings are environment-configurable.
"""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings


class FreshnessGuardianConfig(BaseSettings):
    """Freshness Guardian configuration -- all values overridable via env vars."""

    model_config = {"env_prefix": "FG_", "frozen": True}

    fssai_temp_threshold_hours: float = Field(
        default=4.0, description="Hours of temperature deviation before FSSAI violation"
    )
    rebalance_quality_floor: float = Field(
        default=0.5, description="Min quality_score for cross-store rebalance"
    )
    rebalance_overstock_factor: float = Field(
        default=3.0, description="Stock > factor * daily_demand triggers rebalance"
    )
    rebalance_min_days: float = Field(
        default=2.0, description="Min days_to_expiry for rebalance to be viable"
    )

    confidence_fitted: float = Field(default=0.85, description="Confidence when model is fitted")
    confidence_fallback: float = Field(default=0.5, description="Confidence on fallback path")

    kafka_bootstrap: str = Field(default="kafka:9092")
    feast_repo_path: str = Field(default="/app/data_fabric/feast")
    mlflow_tracking_uri: str = Field(default="http://mlflow:5000")

    reward_accuracy_weight: float = Field(default=1.0)
    reward_timing_weight: float = Field(default=0.4)
    reward_fssai_weight: float = Field(default=2.0)
    reward_unnecessary_weight: float = Field(default=0.3)

    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8004)
