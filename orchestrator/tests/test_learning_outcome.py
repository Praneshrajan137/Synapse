"""ADR-052 P5: meta-RL learns from the REALIZED world, not the predicted utility_score.

Tests ``ConsensusProtocol._build_learning_outcome`` in isolation (it is pure given its
inputs), bypassing the heavy protocol constructor via ``__new__``.
"""

from __future__ import annotations

from uuid import uuid4

from synapse_common.models import AgentName, AgentProposal, ConsensusDecision, DecisionTier

from orchestrator.consensus.protocol import ConsensusProtocol


def _proposal(name: AgentName, utility: float) -> AgentProposal:
    return AgentProposal(
        agent_name=name, decision_id=uuid4(), utility_score=utility, confidence=utility,
        justification_trace=["t"], payload={}, tier=DecisionTier.TIER_2,
    )


def _decision(proposals: list[AgentProposal]) -> ConsensusDecision:
    return ConsensusDecision(
        tier=DecisionTier.TIER_2, proposals=proposals, selected_action={},
        pareto_weights={}, confidence=0.8, audit_trace=["t"],
    )


def test_observable_objectives_use_realized_world_not_predicted_utility() -> None:
    proto = ConsensusProtocol.__new__(ConsensusProtocol)  # bypass heavy __init__
    decision = _decision(
        [_proposal(AgentName.INVENTORY_SENTINEL, 0.9), _proposal(AgentName.DEMAND_PROPHET, 0.4)]
    )
    world = {"fill_rate": 0.55, "spoilage_rate": 0.2, "avg_delivery_min": 30.0}

    outcome = proto._build_learning_outcome(decision, world)

    # The realized world (0.55) overrides the agent's optimistic prediction (0.9).
    assert outcome["inventory_fill_rate"] == 0.55
    assert outcome["freshness_score"] == 0.8  # 1 - spoilage 0.2
    assert outcome["route_efficiency"] == 0.5  # 1 - 30/60
    # demand_accuracy has no world signal → honest fallback to the agent's predicted utility.
    assert outcome["demand_accuracy"] == 0.4


def test_degrades_to_predicted_utility_when_world_absent() -> None:
    proto = ConsensusProtocol.__new__(ConsensusProtocol)
    decision = _decision([_proposal(AgentName.INVENTORY_SENTINEL, 0.9)])
    outcome = proto._build_learning_outcome(decision, None)
    # No world → predicted utility (the honest I-7 fallback), via the CORRECT agent→
    # objective map (the old substring match silently produced nothing here).
    assert outcome["inventory_fill_rate"] == 0.9
