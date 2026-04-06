"""
SYNAPSE Sustainability Agent -- Configuration via Pydantic BaseSettings.
All thresholds, model paths, and connection strings are environment-configurable.
"""
from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings


class SustainabilityAgentConfig(BaseSettings):
    """Sustainability Agent configuration -- all values overridable via env vars."""

    model_config = {"env_prefix": "SA_", "frozen": True}

    # -- Carbon Tracking --
    co2_per_liter_diesel_kg: float = Field(
        default=2.68, description="kg CO2 per liter of diesel fuel"
    )
    co2_twin_tolerance: float = Field(
        default=0.10, ge=0.0, le=1.0, description="Max relative deviation from Digital Twin (INV-SA-002)"
    )
    carbon_pareto_weight: float = Field(
        default=0.25, gt=0.0, description="Pareto weight for carbon objective (INV-SA-001)"
    )

    # -- Waste Prediction --
    default_shelf_life_days: int = Field(default=7, ge=1, description="Default shelf life")
    waste_hazard_threshold: float = Field(
        default=0.5, ge=0.0, le=1.0, description="Hazard rate threshold for waste alert"
    )

    # -- Reward Function (I-2: independent, agent-scoped) --
    reward_carbon_weight: float = Field(default=1.0)
    reward_waste_weight: float = Field(default=0.5)
    reward_accuracy_weight: float = Field(default=0.3)

    # -- Inference --
    inference_timeout_ms: int = Field(default=500, description="Tier 2 SLA")
    confidence_threshold: float = Field(
        default=0.7, description="HITL escalation threshold (I-5)"
    )

    # -- Infrastructure --
    kafka_bootstrap: str = Field(default="kafka:9092")
    feast_repo_path: str = Field(default="/app/data_fabric/feast")
    mlflow_tracking_uri: str = Field(default="http://mlflow:5000")
    model_checkpoint_path: str = Field(
        default="/app/models/sustainability_agent_best.pt"
    )

    # -- Server --
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8008)
