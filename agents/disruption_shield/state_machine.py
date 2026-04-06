"""
SYNAPSE Disruption Shield -- Agent Lifecycle FSM with Objective Recitation (ADR-024).
Uses shared BaseAgentStateMachine from synapse_common.fsm (I-2: no cross-agent imports).
"""
from __future__ import annotations

from synapse_common.fsm import AgentState, BaseAgentStateMachine, Transition

TRANSITIONS: list[Transition] = [
    Transition(
        AgentState.IDLE,
        AgentState.PROPOSING,
        "disruption_signal_received",
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


class DisruptionShieldStateMachine(BaseAgentStateMachine):
    """Agent lifecycle FSM for Disruption Shield. Inherits shared base (I-2)."""

    AGENT_NAME = "disruption_shield"
    TRANSITIONS = TRANSITIONS
    ACTIVE_OBJECTIVE = (
        "Detect supply chain disruptions via anomaly ensemble, retrieve recovery "
        "playbooks from Pinecone, and generate reasoning chains via DeepSeek-R1"
    )
    ACTIVE_CONSTRAINTS = [
        "INV-DS-001: anomaly above threshold -> alert_level > 0",
        "INV-DS-002: Pinecone retrieval latency < 200ms",
        "INV-DS-003: every alert includes non-empty reasoning chain",
        "INV-DS-007: ensemble score in [0, 1]",
    ]
