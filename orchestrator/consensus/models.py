"""
SYNAPSE Orchestrator — Consensus-specific Pydantic models.

Canonical domain models (ContextMessage, AgentProposal, ConsensusDecision, etc.)
are imported from ``synapse_common.models`` and re-exported here for convenience.
Orchestrator-only models are defined below.
"""
from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import Field

from synapse_common.models import (
    AgentName,
    AgentProposal,
    ConsensusDecision,
    ContextMessage,
    DecisionTier,
    HitlTimeoutAction,
    MessageStatus,
    SynapseBaseModel,
)

__all__ = [
    "AgentName",
    "AgentProposal",
    "ConsensusDecision",
    "ContextMessage",
    "ConflictReport",
    "DebateRound",
    "DecisionTier",
    "HitlTimeoutAction",
    "MessageStatus",
    "ParetoResult",
    "SynapseBaseModel",
    "TierClassification",
]


class TierClassification(SynapseBaseModel):
    """Output of the tier router."""

    tier: DecisionTier
    confidence: float = Field(ge=0.0, le=1.0)
    reasons: list[str]
    model: str | None = None
    latency_budget_ms: int


class ConflictReport(SynapseBaseModel):
    """Result of inter-proposal conflict detection."""

    has_conflict: bool
    max_utility_divergence: float = 0.0
    conflicting_pairs: list[tuple[str, str]] = Field(default_factory=list)
    descriptions: list[str] = Field(default_factory=list)


class DebateRound(SynapseBaseModel):
    """One round of LLM-mediated debate."""

    round_number: int = Field(ge=1, le=3)
    revisions: dict[str, Any] = Field(default_factory=dict)
    convergence_score: float = Field(ge=0.0)
    llm_model_used: str | None = None


class ParetoResult(SynapseBaseModel):
    """Output of NSGA-II Pareto arbitration."""

    selected_weights: dict[str, float]
    pareto_front: list[dict[str, float]]
    knee_index: int
    n_solutions: int


class EscalationPayload(SynapseBaseModel):
    """Payload sent to HITL console via WebSocket."""

    decision_id: UUID
    confidence: float
    proposals: list[dict[str, Any]]
    recommended_action: dict[str, Any]
    tier: DecisionTier
    violations: list[str] = Field(default_factory=list)
