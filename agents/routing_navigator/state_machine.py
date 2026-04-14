"""SYNAPSE Routing Navigator -- Agent Lifecycle FSM (ADR-024). Shared base (I-2)."""

from __future__ import annotations

from synapse_common.fsm import AgentState, BaseAgentStateMachine, Transition

TRANSITIONS: list[Transition] = [
    Transition(
        AgentState.IDLE,
        AgentState.PROPOSING,
        "route_request_received",
        guard="kafka_healthy and osrm_available",
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
        AgentState.EXECUTING, AgentState.LEARNING, "execution_confirmed", timeout_seconds=10.0
    ),
    Transition(AgentState.LEARNING, AgentState.IDLE, "policy_updated", timeout_seconds=5.0),
    Transition(AgentState.PROPOSING, AgentState.ERROR, "exception_raised"),
    Transition(AgentState.EXECUTING, AgentState.ERROR, "exception_raised"),
    Transition(AgentState.ERROR, AgentState.IDLE, "error_handled", timeout_seconds=30.0),
]


class RoutingNavigatorStateMachine(BaseAgentStateMachine):
    """Agent lifecycle FSM for Routing Navigator. Inherits shared base (I-2)."""

    AGENT_NAME = "routing_navigator"
    TRANSITIONS = TRANSITIONS
    ACTIVE_OBJECTIVE = (
        "Optimize delivery routes minimizing time/fuel while maximizing "
        "rider fairness (Gini) and freshness compliance within Tier 1/2 SLA"
    )
    ACTIVE_CONSTRAINTS = [
        "INV-RN-003: Route time <= 480 min (8h shift)",
        "INV-RN-004: Track Gini coefficient for rider earnings",
        "INV-RN-006: Tier 1 student inference < 100ms",
    ]
