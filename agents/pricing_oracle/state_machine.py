"""
SYNAPSE Pricing Oracle -- Agent Lifecycle FSM with Objective Recitation (ADR-024).
Uses shared BaseAgentStateMachine from synapse_common.fsm (I-2: no cross-agent imports).
"""

from __future__ import annotations

from synapse_common.fsm import AgentState, BaseAgentStateMachine, Transition

TRANSITIONS: list[Transition] = [
    Transition(
        AgentState.IDLE,
        AgentState.PROPOSING,
        "pricing_request_received",
        guard="kafka_healthy and feast_available",
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


class PricingOracleStateMachine(BaseAgentStateMachine):
    """Agent lifecycle FSM for Pricing Oracle. Inherits shared base (I-2)."""

    AGENT_NAME = "pricing_oracle"
    TRANSITIONS = TRANSITIONS
    ACTIVE_OBJECTIVE = (
        "Generate optimal per-category price multipliers using MADDPG with "
        "causal elasticity estimates while enforcing essential cap 1.3x (I-6)"
    )
    ACTIVE_CONSTRAINTS = [
        "INV-PO-001: Essential category multiplier <= 1.3x (hard clamp)",
        "INV-PO-002: All multipliers strictly positive",
        "INV-PO-003: Confidence in [0, 1]",
        "INV-PO-007: Latency < 500ms",
    ]
