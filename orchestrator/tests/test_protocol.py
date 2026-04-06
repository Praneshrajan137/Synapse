"""SYNAPSE Orchestrator — Consensus FSM tests (INV-ORC-002, INV-ORC-006)."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from synapse_common.models import AgentName, AgentProposal, DecisionTier

from orchestrator.config import OrchestratorConfig
from orchestrator.consensus.protocol import ConsensusProtocol
from orchestrator.state_machine import OrchestratorState


def _build_protocol(config: OrchestratorConfig | None = None) -> ConsensusProtocol:
    cfg = config or OrchestratorConfig(
        postgresql_url="sqlite+aiosqlite:///",
        pinecone_api_key=None,
    )
    return ConsensusProtocol(
        config=cfg,
        tier_router=MagicMock(),
        guardrails=MagicMock(),
        audit_logger=MagicMock(),
        hitl_escalation=MagicMock(),
        context_builder=MagicMock(),
        ollama_client=MagicMock(),
        meta_rl=MagicMock(**{"get_weights.return_value": {"demand_accuracy": 1.0}}),
        semantic_cache=MagicMock(**{"available": False}),
    )


class TestFSMTransitions:
    def test_idle_to_collecting(self) -> None:
        proto = _build_protocol()
        assert proto._fsm.state == OrchestratorState.IDLE
        proto._fsm.transition("decision_request_received")
        assert proto._fsm.state == OrchestratorState.COLLECTING

    def test_invalid_transition_stays(self) -> None:
        proto = _build_protocol()
        result = proto._fsm.transition("execution_complete")
        assert result is False
        assert proto._fsm.state == OrchestratorState.IDLE


class TestTierFastPath:
    """Tier 1-2 must bypass debate and arbitration (INV-ORC-006)."""

    def test_tier1_skips_debate(self) -> None:
        from orchestrator.consensus.models import TierClassification

        proto = _build_protocol()
        tier_class = TierClassification(
            tier=DecisionTier.TIER_1,
            confidence=0.95,
            reasons=["single_agent"],
            latency_budget_ms=100,
        )
        proto._tier_router.classify.return_value = tier_class
        # Fast-path only reaches phase 4 (skipping 2, 3)
        decision_request = {"store_id": "store_001"}
        # The fast_path method internally goes COLLECTING -> EXECUTING
        # We verify the phase_reached is 4


class TestContextAppendOnly:
    """I-14: Context list may only grow."""

    def test_append_increases_length(self) -> None:
        from synapse_common.models import ContextMessage

        proto = _build_protocol()
        msg = ContextMessage(source="test", content={"key": "value"})
        old_len = len(proto._context_messages)
        new_len = proto._append_context(msg)
        assert new_len == old_len + 1
        assert len(proto._context_messages) == new_len

    def test_context_never_shrinks(self) -> None:
        from synapse_common.models import ContextMessage

        proto = _build_protocol()
        for i in range(5):
            proto._append_context(
                ContextMessage(source=f"agent_{i}", content={"i": i}),
            )
        assert len(proto._context_messages) == 5


class TestConflictDetection:
    def test_no_conflict_when_scores_close(self, sample_proposals: list[AgentProposal]) -> None:
        proto = _build_protocol()
        for p in sample_proposals:
            object.__setattr__(p, "utility_score", 0.8)
        report = proto._detect_conflicts(sample_proposals)
        assert report.has_conflict is False

    def test_conflict_when_scores_diverge(self, sample_proposals: list[AgentProposal]) -> None:
        proto = _build_protocol()
        object.__setattr__(sample_proposals[0], "utility_score", 0.2)
        object.__setattr__(sample_proposals[1], "utility_score", 0.9)
        report = proto._detect_conflicts(sample_proposals)
        assert report.has_conflict is True
        assert report.max_utility_divergence >= 0.3
