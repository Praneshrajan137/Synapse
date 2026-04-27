"""Layer 5 (Design-by-Contract) -- audit logger contracts.

Exercises ``@deal.pre`` / ``@deal.post`` on
``orchestrator.audit.logger.AuditLogger.log_decision``. These contracts are
how I-4 (immutable audit log) is enforced *in code*; the corresponding
PostgreSQL REVOKE on UPDATE/DELETE is enforced at the database level and is
exercised by the integration suite.
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import deal
import pytest
from synapse_common.models import (
    AgentName,
    AgentProposal,
    ConsensusDecision,
    DecisionTier,
)

pytestmark = pytest.mark.dbc


def _decision(*, decision_id: Any = None) -> ConsensusDecision:
    proposal = AgentProposal(
        agent_name=AgentName.PRICING_ORACLE,
        decision_id=uuid4(),
        utility_score=0.8,
        confidence=0.9,
        justification_trace=["dbc-test"],
        payload={},
        tier=DecisionTier.TIER_2,
    )
    kwargs: dict[str, Any] = {
        "timestamp": datetime.now(UTC),
        "tier": DecisionTier.TIER_2,
        "proposals": [proposal],
        "selected_action": {},
        "pareto_weights": {"pricing_oracle": 1.0},
        "confidence": 0.9,
        "audit_trace": ["dbc-test"],
    }
    if decision_id is not None:
        kwargs["decision_id"] = decision_id
    return ConsensusDecision(**kwargs)


@pytest.mark.asyncio
async def test_log_decision_returns_audit_id_for_valid_decision() -> None:
    """Postcondition: log_decision MUST return a non-None UUID."""
    from orchestrator.audit.logger import AuditLogger

    # Async session factory that yields a session whose `add` and `commit`
    # are mocks; the row instance gets a UUID assigned at construction time.
    mock_session = MagicMock()
    mock_session.commit = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)

    def _factory() -> Any:
        return mock_session

    audit = AuditLogger(session_factory=_factory)  # type: ignore[arg-type]
    decision = _decision(decision_id=uuid4())

    audit_id = await audit.log_decision(decision)
    assert audit_id is not None


@pytest.mark.asyncio
async def test_log_decision_pre_rejects_none_decision_id() -> None:
    """Pre-contract: decision_id must be present.

    We have to bypass Pydantic's auto-uuid default to drive a None into the
    contract. ``object.__setattr__`` is required because the model is frozen.
    """
    from orchestrator.audit.logger import AuditLogger

    mock_session = MagicMock()
    mock_session.commit = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)

    audit = AuditLogger(session_factory=lambda: mock_session)  # type: ignore[arg-type]
    decision = _decision()
    object.__setattr__(decision, "decision_id", None)

    with pytest.raises(deal.PreContractError):
        await audit.log_decision(decision)
