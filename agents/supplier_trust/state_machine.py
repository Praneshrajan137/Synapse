"""SYNAPSE Supplier Trust -- Agent Lifecycle FSM (ADR-024). Shared base (I-2)."""
from __future__ import annotations

from synapse_common.fsm import AgentState, BaseAgentStateMachine, Transition

TRANSITIONS: list[Transition] = [
    Transition(AgentState.IDLE, AgentState.PROPOSING, "trust_evaluation_triggered",
               guard="neo4j_healthy and kafka_healthy", timeout_seconds=2.0),
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


class SupplierTrustStateMachine(BaseAgentStateMachine):
    """Agent lifecycle FSM for Supplier Trust. Inherits shared base (I-2)."""

    AGENT_NAME = "supplier_trust"
    TRANSITIONS = TRANSITIONS
    ACTIVE_OBJECTIVE = (
        "Score supplier trustworthiness via GNN embeddings on temporal knowledge graph "
        "and Bayesian lead-time posterior, ensuring new vendor floor of 0.3 and monotonic "
        "trust decay on consecutive late deliveries"
    )
    ACTIVE_CONSTRAINTS = [
        "INV-ST-001: New vendor trust floor >= 0.3",
        "INV-ST-002: Consecutive late deliveries decrease trust monotonically",
        "INV-ST-003: Lead-time posterior std_days > 0",
    ]
