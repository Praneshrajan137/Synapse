"""SYNAPSE Orchestrator — deal pre/postcondition verification."""
from __future__ import annotations

from uuid import uuid4

import deal
import pytest

from synapse_common.models import ConsensusDecision, ContextMessage, DecisionTier

from orchestrator.guardrails.rules import execute_consensus


class TestExecuteConsensusContract:
    """Verify that deal.pre/post fire correctly on execute_consensus."""

    def test_low_confidence_not_escalated_raises(self) -> None:
        decision = ConsensusDecision(
            tier=DecisionTier.TIER_2,
            proposals=[],
            selected_action={},
            pareto_weights={},
            confidence=0.4,
            escalated_to_human=False,
            audit_trace=["test"],
        )
        with pytest.raises(deal.PreContractError):
            execute_consensus(decision)

    def test_high_confidence_passes_pre(self) -> None:
        decision = ConsensusDecision(
            tier=DecisionTier.TIER_2,
            proposals=[],
            selected_action={},
            pareto_weights={},
            confidence=0.9,
            escalated_to_human=False,
            audit_trace=["test"],
            audit_id=uuid4(),
        )
        result = execute_consensus(decision)
        assert result.audit_id is not None

    def test_escalated_low_confidence_passes(self) -> None:
        decision = ConsensusDecision(
            tier=DecisionTier.TIER_3,
            proposals=[],
            selected_action={},
            pareto_weights={},
            confidence=0.3,
            escalated_to_human=True,
            audit_trace=["test"],
            audit_id=uuid4(),
        )
        result = execute_consensus(decision)
        assert result.escalated_to_human is True


class TestContextAppendOnlyContract:
    def test_append_context_rejects_non_context_message(self) -> None:
        from orchestrator.consensus.protocol import ConsensusProtocol
        from unittest.mock import MagicMock

        from orchestrator.config import OrchestratorConfig

        cfg = OrchestratorConfig(postgresql_url="sqlite+aiosqlite:///", pinecone_api_key=None)
        proto = ConsensusProtocol(
            config=cfg,
            tier_router=MagicMock(),
            guardrails=MagicMock(),
            audit_logger=MagicMock(),
            hitl_escalation=MagicMock(),
            context_builder=MagicMock(),
            ollama_client=MagicMock(),
            meta_rl=MagicMock(**{"get_weights.return_value": {}}),
            semantic_cache=MagicMock(**{"available": False}),
        )
        with pytest.raises(deal.PreContractError):
            proto._append_context("not_a_context_message")  # type: ignore[arg-type]
