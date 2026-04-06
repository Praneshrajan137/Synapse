"""
SYNAPSE Orchestrator — Consumer-driven contract: all 8 agents' proposal() responses.

The Orchestrator (consumer) expects every agent (producer) to return proposals
conforming to ``synapse_common.models.AgentProposal``.
"""
from __future__ import annotations

from uuid import uuid4

import pytest

from synapse_common.models import AgentName, AgentProposal, DecisionTier

AGENT_NAMES: list[str] = [a.value for a in AgentName]


def _mock_agent_response(agent_name: str) -> dict:
    return {
        "agent_name": agent_name,
        "decision_id": str(uuid4()),
        "utility_score": 0.8,
        "confidence": 0.85,
        "justification_trace": [f"{agent_name} proposal generated"],
        "payload": {"action": f"{agent_name}_action"},
        "tier": "tier_2",
    }


class TestAgentProposalContract:
    """Consumer-driven: Orchestrator expects these fields from all agents."""

    @pytest.mark.contract()
    @pytest.mark.parametrize("agent_name", AGENT_NAMES)
    def test_proposal_has_utility_score(self, agent_name: str) -> None:
        response = _mock_agent_response(agent_name)
        proposal = AgentProposal(**response)
        assert 0.0 <= proposal.utility_score <= 1.0

    @pytest.mark.contract()
    @pytest.mark.parametrize("agent_name", AGENT_NAMES)
    def test_proposal_has_confidence(self, agent_name: str) -> None:
        response = _mock_agent_response(agent_name)
        proposal = AgentProposal(**response)
        assert 0.0 <= proposal.confidence <= 1.0

    @pytest.mark.contract()
    @pytest.mark.parametrize("agent_name", AGENT_NAMES)
    def test_proposal_has_justification(self, agent_name: str) -> None:
        response = _mock_agent_response(agent_name)
        proposal = AgentProposal(**response)
        assert len(proposal.justification_trace) > 0

    @pytest.mark.contract()
    @pytest.mark.parametrize("agent_name", AGENT_NAMES)
    def test_proposal_has_payload(self, agent_name: str) -> None:
        response = _mock_agent_response(agent_name)
        proposal = AgentProposal(**response)
        assert len(proposal.payload) > 0

    @pytest.mark.contract()
    @pytest.mark.parametrize("agent_name", AGENT_NAMES)
    def test_proposal_has_valid_tier(self, agent_name: str) -> None:
        response = _mock_agent_response(agent_name)
        proposal = AgentProposal(**response)
        assert proposal.tier in list(DecisionTier)
