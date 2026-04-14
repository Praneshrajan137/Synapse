"""
SYNAPSE Demand Prophet -- Agent Lifecycle FSM with Objective Recitation (ADR-024).
Uses shared BaseAgentStateMachine from synapse_common.fsm (I-2: no cross-agent imports).
"""

from __future__ import annotations

from synapse_common.fsm import AgentState, BaseAgentStateMachine, Transition

TRANSITIONS: list[Transition] = [
    Transition(
        AgentState.IDLE,
        AgentState.PROPOSING,
        "forecast_request_received",
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


class DemandProphetStateMachine(BaseAgentStateMachine):
    """Agent lifecycle FSM for Demand Prophet. Inherits shared base (I-2)."""

    AGENT_NAME = "demand_prophet"
    TRANSITIONS = TRANSITIONS
    ACTIVE_OBJECTIVE = (
        "Generate accurate multi-horizon demand forecasts with calibrated "
        "conformal intervals for all requested SKUs within Tier 2 SLA (<500ms)"
    )
    ACTIVE_CONSTRAINTS = [
        "INV-DP-001: Every forecast includes conformal intervals",
        "INV-DP-003: Confidence in [0, 1]",
        "INV-DP-006: All forecast values non-negative",
        "INV-DP-008: Latency < 500ms",
    ]
