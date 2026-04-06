"""SYNAPSE Orchestrator — Append-only context tests (I-14)."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from synapse_common.models import ContextMessage, MessageStatus

from orchestrator.consensus.protocol import ConsensusProtocol
from orchestrator.config import OrchestratorConfig


def _proto() -> ConsensusProtocol:
    cfg = OrchestratorConfig(postgresql_url="sqlite+aiosqlite:///", pinecone_api_key=None)
    return ConsensusProtocol(
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


class TestAppendOnlyContext:
    def test_append_only_grows(self) -> None:
        proto = _proto()
        msg = ContextMessage(source="test", content={"x": 1})
        n1 = proto._append_context(msg)
        assert n1 == 1
        n2 = proto._append_context(ContextMessage(source="test", content={"x": 2}))
        assert n2 == 2

    def test_rejected_proposal_stays_in_context(self) -> None:
        proto = _proto()
        original = ContextMessage(source="agent_a", content={"proposal": "v1"})
        proto._append_context(original)

        rejection = ContextMessage(
            source="orchestrator",
            content={"original_id": str(original.message_id), "reason": "conflict"},
            status=MessageStatus.REJECTED,
            rejection_reason="conflict",
        )
        proto._append_context(rejection)
        assert len(proto._context_messages) == 2
        assert proto._context_messages[0].status == MessageStatus.ACTIVE
        assert proto._context_messages[1].status == MessageStatus.REJECTED

    def test_superseded_proposal_kept(self) -> None:
        proto = _proto()
        proto._append_context(ContextMessage(source="a", content={"v": 1}))
        revision = ContextMessage(
            source="a",
            content={"v": 2},
            status=MessageStatus.ACTIVE,
        )
        proto._append_context(revision)
        supersede_notice = ContextMessage(
            source="orchestrator",
            content={"superseded": str(proto._context_messages[0].message_id)},
            status=MessageStatus.SUPERSEDED,
            superseded_by=revision.message_id,
        )
        proto._append_context(supersede_notice)
        assert len(proto._context_messages) == 3

    def test_recitation_appended_at_interval(self) -> None:
        proto = _proto()
        proto._config = OrchestratorConfig(
            postgresql_url="sqlite+aiosqlite:///",
            pinecone_api_key=None,
            recitation_interval=3,
        )
        for i in range(6):
            proto._append_context(ContextMessage(source=f"a{i}", content={"i": i}))
        recitations = [
            m for m in proto._context_messages
            if m.content.get("type") == "objective_recitation"
        ]
        assert len(recitations) >= 1
