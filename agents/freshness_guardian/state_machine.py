"""
SYNAPSE Freshness Guardian -- Agent Lifecycle FSM with Objective Recitation (ADR-024).
Uses shared BaseAgentStateMachine from synapse_common.fsm (I-2: no cross-agent imports).
"""
from __future__ import annotations

from synapse_common.fsm import AgentState, BaseAgentStateMachine, Transition

TRANSITIONS: list[Transition] = [
    Transition(
        AgentState.IDLE,
        AgentState.PROPOSING,
        "freshness_request_received",
        guard="kafka_healthy",
        timeout_seconds=2.0,
    ),
    Transition(
        AgentState.PROPOSING,
        AgentState.DEBATING,
        "proposal_submitted",
        guard="confidence >= 0.0",
        timeout_seconds=5.0,
    ),
    Transition(
        AgentState.DEBATING,
        AgentState.EXECUTING,
        "consensus_reached",
        guard="orchestrator_approved",
        timeout_seconds=30.0,
    ),
    Transition(
        AgentState.EXECUTING,
        AgentState.LEARNING,
        "execution_confirmed",
        timeout_seconds=10.0,
    ),
    Transition(
        AgentState.LEARNING,
        AgentState.IDLE,
        "policy_updated",
        timeout_seconds=5.0,
    ),
    Transition(AgentState.PROPOSING, AgentState.ERROR, "exception_raised"),
    Transition(AgentState.EXECUTING, AgentState.ERROR, "exception_raised"),
    Transition(
        AgentState.ERROR,
        AgentState.IDLE,
        "error_handled",
        timeout_seconds=30.0,
    ),
]


class FreshnessGuardianStateMachine(BaseAgentStateMachine):
    """Agent lifecycle FSM for Freshness Guardian. Inherits shared base (I-2)."""

    AGENT_NAME = "freshness_guardian"
    TRANSITIONS = TRANSITIONS
    ACTIVE_OBJECTIVE = (
        "Monitor perishable inventory shelf life, apply markdown pricing, "
        "trigger cross-store rebalancing, and enforce FSSAI cold chain compliance"
    )
    ACTIVE_CONSTRAINTS = [
        "INV-FG-001: quality_score in [0, 1]",
        "INV-FG-002: expired items MUST have markdown_applied = True",
        "INV-FG-003: FSSAI violation when temp deviation > 4h",
        "INV-FG-004: Markdown monotonically increases as expiry approaches",
    ]
