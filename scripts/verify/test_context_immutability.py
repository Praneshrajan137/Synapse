"""
Context append-only enforcement verification (I-14).
Run: python scripts/verify/test_context_immutability.py
"""
from __future__ import annotations

import structlog
from synapse_common.models import ContextMessage, MessageStatus

from orchestrator.config import OrchestratorConfig

logger = structlog.get_logger(__name__)


def verify_context_immutability() -> None:
    from unittest.mock import MagicMock

    from orchestrator.consensus.protocol import ConsensusProtocol

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

    lengths = []
    for i in range(20):
        msg = ContextMessage(source=f"agent_{i}", content={"step": i})
        new_len = proto._append_context(msg)
        lengths.append(new_len)

    # Verify strictly increasing
    for i in range(1, len(lengths)):
        assert lengths[i] > lengths[i - 1], f"I-14 VIOLATION at step {i}"

    # Verify rejected proposals not removed
    reject = ContextMessage(
        source="orchestrator",
        content={"rejected": True},
        status=MessageStatus.REJECTED,
        rejection_reason="test",
    )
    before = len(proto._context_messages)
    proto._append_context(reject)
    assert len(proto._context_messages) == before + 1

    logger.info("context_immutability_verified", total_messages=len(proto._context_messages))


if __name__ == "__main__":
    verify_context_immutability()
