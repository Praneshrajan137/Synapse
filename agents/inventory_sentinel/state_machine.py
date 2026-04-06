"""SYNAPSE Inventory Sentinel -- Agent Lifecycle FSM (ADR-024). Shared base (I-2)."""
from __future__ import annotations

from synapse_common.fsm import AgentState, BaseAgentStateMachine, Transition

TRANSITIONS: list[Transition] = [
    Transition(AgentState.IDLE, AgentState.PROPOSING, "inventory_check_triggered",
               guard="kafka_healthy and feast_available", timeout_seconds=2.0),
    Transition(AgentState.PROPOSING, AgentState.DEBATING, "proposal_submitted",
               timeout_seconds=5.0),
    Transition(AgentState.DEBATING, AgentState.EXECUTING, "consensus_reached",
               timeout_seconds=30.0),
    Transition(AgentState.EXECUTING, AgentState.LEARNING, "execution_confirmed",
               timeout_seconds=10.0),
    Transition(AgentState.LEARNING, AgentState.IDLE, "policy_updated",
               timeout_seconds=5.0),
    Transition(AgentState.PROPOSING, AgentState.ERROR, "exception_raised"),
    Transition(AgentState.EXECUTING, AgentState.ERROR, "exception_raised"),
    Transition(AgentState.ERROR, AgentState.IDLE, "error_handled", timeout_seconds=30.0),
]


class InventorySentinelStateMachine(BaseAgentStateMachine):
    """Agent lifecycle FSM for Inventory Sentinel. Inherits shared base (I-2)."""

    AGENT_NAME = "inventory_sentinel"
    TRANSITIONS = TRANSITIONS
    ACTIVE_OBJECTIVE = (
        "Optimize inventory levels across 3-level hierarchy (strategic, tactical, operational) "
        "with safety stock within [1.0, 3.0] bounds and federated cross-store learning"
    )
    ACTIVE_CONSTRAINTS = [
        "INV-IS-001: Safety stock multiplier in [1.0, 3.0]",
        "INV-IS-002: Reorder quantity non-negative",
        "INV-IS-006: Flower gradient-only aggregation -- no raw data leaves store (I-11)",
    ]
