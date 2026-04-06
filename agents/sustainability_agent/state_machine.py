"""
SYNAPSE Sustainability Agent -- Agent Lifecycle FSM with Objective Recitation (ADR-024).
Uses shared BaseAgentStateMachine from synapse_common.fsm (I-2: no cross-agent imports).
"""
from __future__ import annotations

from synapse_common.fsm import AgentState, BaseAgentStateMachine, Transition

TRANSITIONS: list[Transition] = [
    Transition(
        AgentState.IDLE,
        AgentState.PROPOSING,
        "carbon_report_requested",
        guard="kafka_healthy and codecarbon_available",
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


class SustainabilityAgentStateMachine(BaseAgentStateMachine):
    """Agent lifecycle FSM for Sustainability Agent. Inherits shared base (I-2)."""

    AGENT_NAME = "sustainability_agent"
    TRANSITIONS = TRANSITIONS
    ACTIVE_OBJECTIVE = (
        "Track carbon footprint per delivery, predict food waste via survival analysis, "
        "and generate ESG reports with full provenance within Tier 2 SLA (<500ms)"
    )
    ACTIVE_CONSTRAINTS = [
        "INV-SA-001: Carbon cost as first-class Pareto objective (weight > 0)",
        "INV-SA-002: CO2 estimate within 10% of Digital Twin",
        "INV-SA-003: ESG report with provenance chain",
        "INV-SA-004: All CO2 values non-negative",
    ]
