"""Decision replay determinism test (WS-4 §3 acceptance).

Inserts a synthetic ``audit_consensus`` row into an in-memory SQLite
audit database, then calls ``replay_decision`` and asserts:

  - the original and replayed hashes are byte-identical,
  - the resulting ``ReplayResult.diverged`` is False,
  - missing decisions return a structured error rather than raising.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from orchestrator.audit.models import AuditConsensusRow, Base
from orchestrator.replay.replay import replay_decision


@pytest_asyncio.fixture
async def session_factory() -> Any:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield factory
    await engine.dispose()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_replay_returns_byte_identical_hash(session_factory: Any) -> None:
    decision_id = uuid4()
    async with session_factory() as session:
        row = AuditConsensusRow(
            id=uuid4(),
            decision_id=decision_id,
            timestamp=datetime.now(UTC),
            tier="tier_2",
            phase_reached=3,
            proposals=[{"agent": "demand_prophet", "utility": 0.91}],
            selected_action={"action": "reorder", "sku": "SKU1", "qty": 42},
            pareto_weights={"demand_prophet": 1.0},
            confidence=0.92,
            debate_rounds=0,
            escalated=False,
            human_override=None,
            execution_confirmations=[],
            context_messages=[],
            audit_trace=["t1"],
            pareto_front=None,
            outcome=None,
            created_at=datetime.now(UTC),
        )
        session.add(row)
        await session.commit()

    async with session_factory() as session:
        result = await replay_decision(session, decision_id)
    assert result.diverged is False
    assert result.original_hash == result.replay_hash
    assert result.divergences == []


@pytest.mark.integration
@pytest.mark.asyncio
async def test_replay_missing_decision_returns_note(session_factory: Any) -> None:
    async with session_factory() as session:
        result = await replay_decision(session, uuid4())
    assert result.diverged is True
    assert result.note is not None
    assert "not found" in result.note
