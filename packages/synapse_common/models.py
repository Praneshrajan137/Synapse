"""
SYNAPSE Domain Models — Pydantic v2 models for all domain entities.
Every agent output MUST validate against these models (I-3).
All serialization uses sort_keys=True, separators=(',',':') for KV-cache preservation (I-13).
"""
from __future__ import annotations

import json
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, ValidationInfo, field_validator


class SynapseBaseModel(BaseModel):
    """Base model enforcing deterministic JSON serialization (I-13)."""

    model_config = {"frozen": True, "extra": "forbid"}

    def to_deterministic_json(self) -> str:
        """Serialize with sorted keys and compact separators for KV-cache preservation."""
        return json.dumps(
            self.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        )


class DecisionTier(StrEnum):
    """Four decision tiers with explicit latency SLAs (I-10)."""
    TIER_1 = "tier_1"
    TIER_2 = "tier_2"
    TIER_3 = "tier_3"
    TIER_4 = "tier_4"


class AgentName(StrEnum):
    """All eight SYNAPSE agents."""
    DEMAND_PROPHET = "demand_prophet"
    ROUTING_NAVIGATOR = "routing_navigator"
    INVENTORY_SENTINEL = "inventory_sentinel"
    FRESHNESS_GUARDIAN = "freshness_guardian"
    PRICING_ORACLE = "pricing_oracle"
    DISRUPTION_SHIELD = "disruption_shield"
    SUPPLIER_TRUST = "supplier_trust"
    SUSTAINABILITY_AGENT = "sustainability_agent"


class MessageStatus(StrEnum):
    """Status for context messages — append-only, never deleted (I-14)."""
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    REJECTED = "rejected"
    ERROR = "error"


class HitlTimeoutAction(StrEnum):
    """Configurable action on HITL escalation timeout."""
    DEFER = "defer"
    EXECUTE_TIER1 = "execute_tier1"
    EXECUTE_LAST_KNOWN_GOOD = "execute_last_known_good"


class ContextMessage(SynapseBaseModel):
    """
    Immutable context message for Orchestrator runtime context.
    Once created, NEVER modified or deleted (I-14, ADR-023).
    """
    message_id: UUID = Field(default_factory=uuid4)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    source: str
    content: dict[str, Any]
    status: MessageStatus = MessageStatus.ACTIVE
    rejection_reason: str | None = None
    superseded_by: UUID | None = None


class AgentProposal(SynapseBaseModel):
    """Standard A2A proposal from any agent to the Orchestrator."""
    agent_name: AgentName
    decision_id: UUID
    utility_score: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    justification_trace: list[str]
    payload: dict[str, Any]
    tier: DecisionTier


class ConsensusDecision(SynapseBaseModel):
    """Final Orchestrator decision with full provenance (I-4)."""
    decision_id: UUID = Field(default_factory=uuid4)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    tier: DecisionTier
    proposals: list[AgentProposal]
    selected_action: dict[str, Any]
    pareto_weights: dict[str, float]
    confidence: float = Field(ge=0.0, le=1.0)
    escalated_to_human: bool = False
    human_override: dict[str, Any] | None = None
    audit_trace: list[str]
    phase_reached: int = Field(default=1, ge=1, le=5)
    debate_rounds: int = Field(default=0, ge=0)
    pareto_front: list[dict[str, float]] | None = None
    context_messages: list[ContextMessage] = Field(default_factory=list)
    execution_confirmations: list[str] = Field(default_factory=list)
    audit_id: UUID | None = None


class DemandForecast(SynapseBaseModel):
    """Demand Prophet output — consumed by 5 agents."""
    sku_id: str
    store_id: str
    forecast_timestamp: datetime
    horizons: dict[str, float]
    lower_90: dict[str, float]
    upper_90: dict[str, float]
    confidence: float = Field(ge=0.0, le=1.0)
    drift_detected: bool = False


class RoutePlan(SynapseBaseModel):
    """Routing Navigator output."""
    route_id: UUID = Field(default_factory=uuid4)
    rider_id: str
    store_id: str
    stops: list[dict[str, Any]]
    total_distance_km: float = Field(ge=0.0)
    total_time_min: float = Field(ge=0.0)
    fuel_estimate_liters: float = Field(ge=0.0)
    freshness_violations: int = Field(ge=0)


class InventoryAction(SynapseBaseModel):
    """Inventory Sentinel output."""
    store_id: str
    sku_id: str
    action_type: str
    quantity: float = Field(ge=0.0)
    safety_stock_multiplier: float = Field(ge=1.0, le=3.0)
    reorder_point: float = Field(ge=0.0)
    confidence: float = Field(ge=0.0, le=1.0)


class PricingDecision(SynapseBaseModel):
    """Pricing Oracle output — Hard 1.3x cap on essentials enforced (I-6)."""
    sku_id: str
    store_id: str
    category_id: str
    is_essential: bool
    base_price: float = Field(gt=0.0)
    multiplier: float = Field(gt=0.0)
    final_price: float = Field(gt=0.0)

    @field_validator("multiplier")
    @classmethod
    def essential_cap(cls, v: float, info: ValidationInfo) -> float:
        """HARD GUARDRAIL: Essential items capped at 1.3x (I-6). Not learnable."""
        if info.data.get("is_essential") and v > 1.3:
            raise ValueError(
                f"Essential item price multiplier {v} exceeds hard cap 1.3x (I-6). "
                "This cap is NON-NEGOTIABLE and cannot be overridden by any RL agent."
            )
        return v
