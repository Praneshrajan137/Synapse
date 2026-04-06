"""
SYNAPSE Orchestrator — Shared test fixtures.

Provides mock agents, mock Ollama, mock Kafka, and other test doubles.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from synapse_common.models import (  # noqa: E402
    AgentName,
    AgentProposal,
    ConsensusDecision,
    ContextMessage,
    DecisionTier,
)

from orchestrator.config import OrchestratorConfig  # noqa: E402


@pytest.fixture()
def orchestrator_config() -> OrchestratorConfig:
    return OrchestratorConfig(
        kafka_bootstrap_servers="localhost:9092",
        postgresql_url="sqlite+aiosqlite:///",
        pinecone_api_key=None,
    )


@pytest.fixture()
def sample_proposal() -> AgentProposal:
    return AgentProposal(
        agent_name=AgentName.DEMAND_PROPHET,
        decision_id=uuid4(),
        utility_score=0.85,
        confidence=0.9,
        justification_trace=["forecast generated", "conformal intervals attached"],
        payload={"forecasts": [{"sku": "SKU_001", "qty": 10}]},
        tier=DecisionTier.TIER_2,
    )


@pytest.fixture()
def sample_proposals() -> list[AgentProposal]:
    """Return one proposal per agent for a full consensus round."""
    decision_id = uuid4()
    agents = list(AgentName)
    proposals: list[AgentProposal] = []
    for i, agent in enumerate(agents):
        proposals.append(
            AgentProposal(
                agent_name=agent,
                decision_id=decision_id,
                utility_score=0.5 + i * 0.05,
                confidence=0.6 + i * 0.04,
                justification_trace=[f"{agent.value} proposal"],
                payload={"action": f"action_{agent.value}"},
                tier=DecisionTier.TIER_2,
            ),
        )
    return proposals


@pytest.fixture()
def sample_decision(sample_proposals: list[AgentProposal]) -> ConsensusDecision:
    return ConsensusDecision(
        tier=DecisionTier.TIER_2,
        proposals=sample_proposals,
        selected_action={"action": "test"},
        pareto_weights={"demand_accuracy": 1.0},
        confidence=0.85,
        audit_trace=["tier=tier_2"],
        phase_reached=4,
    )


@pytest.fixture()
def mock_kafka_producer() -> MagicMock:
    producer = MagicMock()
    producer.produce = MagicMock()
    return producer


@pytest.fixture()
def mock_ollama_response() -> dict[str, Any]:
    return {
        "model": "phi3:mini",
        "message": {"role": "assistant", "content": "Analysis complete."},
        "prompt_eval_count": 100,
        "eval_count": 50,
    }


def mock_agent_response(agent_name: str, method: str) -> dict[str, Any]:
    """Generate a mock A2A response from any agent."""
    return {
        "agent_name": agent_name,
        "decision_id": str(uuid4()),
        "utility_score": 0.8,
        "confidence": 0.85,
        "justification_trace": [f"{agent_name} {method} complete"],
        "payload": {"action": f"{agent_name}_action"},
        "tier": "tier_2",
    }
