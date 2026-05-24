"""Replay-equivalence test (Sprint 8 WS-5 §M9).

Seeds an in-memory SQLite audit DB (reusing Sprint 7's JSONB shim at
``tests/integration/conftest.py``) with 5 selected golden traces' audit
rows; calls ``replay_decision``; asserts ``diverged is False`` for all.

This validates that Sprint 7's replay engine is byte-stable when fed
the deterministic outputs the eval runner produces. The Sprint-9
follow-up extends to all 20 traces once real consensus output capture
exists.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

# Reuse the Sprint-7 JSONB-on-SQLite shim by importing the conftest module.
import tests.integration.conftest  # noqa: F401
from orchestrator.audit.models import AuditConsensusRow, Base
from orchestrator.replay.replay import replay_decision
from tests.eval.run import load_traces


@pytest_asyncio.fixture
async def session_factory() -> Any:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield factory
    await engine.dispose()


def _seed_row(decision_id: UUID, tier: str, city: str) -> AuditConsensusRow:
    return AuditConsensusRow(
        id=uuid4(),
        decision_id=decision_id,
        timestamp=datetime.now(UTC),
        tier=tier,
        phase_reached=3,
        proposals=[{"agent": "demand_prophet", "utility": 0.91}],
        selected_action={"action": "reorder", "city": city, "qty": 42},
        pareto_weights={"demand_prophet": 1.0},
        confidence=0.92,
        debate_rounds=0,
        escalated=False,
        human_override=None,
        execution_confirmations=[],
        context_messages=[],
        audit_trace=[f"t1:{city}"],
        pareto_front=None,
        outcome=None,
        created_at=datetime.now(UTC),
    )


@pytest.mark.eval
@pytest.mark.asyncio
async def test_replay_equivalence_on_selected_traces(session_factory: Any) -> None:
    traces = load_traces()
    # Sprint-8 cut: 5 traces — first 3 Tier-1 + first 2 Tier-2 / Tier-3.
    selected = [t for t in traces if t.expected_tier.value == "tier_1"][:3]
    selected += [t for t in traces if t.expected_tier.value in ("tier_2", "tier_3")][:2]
    assert len(selected) == 5

    decision_ids: list[UUID] = []
    async with session_factory() as session:
        for trace in selected:
            decision_id = uuid4()
            decision_ids.append(decision_id)
            session.add(_seed_row(decision_id, trace.expected_tier.value, trace.city))
        await session.commit()

    async with session_factory() as session:
        for decision_id in decision_ids:
            result = await replay_decision(session, decision_id)
            assert result.diverged is False, (
                f"replay diverged for {decision_id}: {result.divergences}"
            )
            assert result.original_hash == result.replay_hash
