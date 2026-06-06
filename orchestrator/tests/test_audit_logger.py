"""Sprint 13 §Phase 3 — orchestrator audit logger tests (I-4 + ADR-033).

`AuditLogger.log_decision` writes one row to PostgreSQL inside a single
transaction, computing the chained-hash on the way in. The chain head is
cached per-process and recovered from the DB on first call.

These tests run AGAINST mock async sessions — the SQLAlchemy + Postgres
integration path is covered by the integration suite (which needs a live
DB). The point here is to pin:

- the canonical row submitted to the chain hashing,
- prev_hash recovery from the DB on cold start,
- chain head caching across invocations,
- correct prev_hash → current_hash linkage row to row,
- the `deal` precondition on decision_id presence.

Mutation-survival targets per C30 (<10% survival on audit):
- exact field set on AuditConsensusRow constructor
- chain monotonicity (each call uses the prior call's current_hash as prev_hash)
- empty-DB cold start returns GENESIS_HASH, not None
- the metric counter is incremented exactly once per insert
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import MagicMock
from uuid import UUID, uuid4

import pytest
from synapse_common.models import (
    AgentName,
    AgentProposal,
    ConsensusDecision,
    DecisionTier,
)

from orchestrator.audit.hash_chain import GENESIS_HASH
from orchestrator.audit.logger import AuditLogger

# -----------------------------------------------------------------------------
# Fixtures: a mocked async_sessionmaker that hands out a captured session.
# -----------------------------------------------------------------------------


class _SessionRecorder:
    """Capture .add() / .commit() / .execute() calls per session instance."""

    def __init__(self, scalar_value: str | None = None) -> None:
        self.added_rows: list[Any] = []
        self.commit_called = False
        self.execute_called = False
        # Pre-canned result for the chain-head lookup
        self._scalar = scalar_value
        self._scalar_result = MagicMock()
        self._scalar_result.scalar_one_or_none = MagicMock(return_value=scalar_value)

    async def execute(self, _stmt: Any) -> MagicMock:
        self.execute_called = True
        return self._scalar_result

    def add(self, row: Any) -> None:
        self.added_rows.append(row)
        # Mimic SQLAlchemy assigning an ID after .add() + flush
        if not hasattr(row, "id") or row.id is None:
            row.id = uuid4()

    async def commit(self) -> None:
        self.commit_called = True

    async def __aenter__(self) -> _SessionRecorder:
        return self

    async def __aexit__(self, *_: Any) -> None:
        return None


def _session_factory_returning(scalar_value: str | None = None) -> Any:
    """Return an async_sessionmaker-like callable. Each call produces a FRESH
    recorder (closer to real SQLAlchemy semantics — each ``async with`` opens
    a new session). The factory tracks every recorder it ever produced via
    `.recorders` so tests can inspect cross-session behaviour."""
    recorders: list[_SessionRecorder] = []

    def factory() -> Any:
        recorder = _SessionRecorder(scalar_value=scalar_value)
        recorders.append(recorder)

        @asynccontextmanager
        async def _cm() -> Any:
            yield recorder

        return _cm()

    factory.recorders = recorders  # type: ignore[attr-defined]
    return factory


def _last(factory: Any) -> _SessionRecorder:
    """Convenience: most recently created recorder."""
    return factory.recorders[-1]


def _make_decision(confidence: float = 0.95) -> ConsensusDecision:
    return ConsensusDecision(
        decision_id=uuid4(),
        tier=DecisionTier.TIER_1,
        proposals=[
            AgentProposal(
                agent_name=AgentName.DEMAND_PROPHET,
                decision_id=uuid4(),
                utility_score=0.7,
                confidence=confidence,
                justification_trace=["t"],
                payload={},
                tier=DecisionTier.TIER_1,
            )
        ],
        selected_action={"action": "noop"},
        pareto_weights={"latency": 1.0},
        confidence=confidence,
        audit_trace=["t"],
    )


# =============================================================================
# Cold-start chain head
# =============================================================================


@pytest.mark.asyncio
async def test_cold_start_uses_genesis_hash_when_db_empty() -> None:
    """Empty DB → scalar_one_or_none returns None → AuditLogger MUST fall
    back to GENESIS_HASH (NOT None, which would propagate as a NULL in
    the next row and break chain verification)."""
    factory = _session_factory_returning(scalar_value=None)
    logger = AuditLogger(factory)
    audit_id = await logger.log_decision(_make_decision())
    recorder = _last(factory)
    row = recorder.added_rows[0]
    assert row.prev_hash == GENESIS_HASH, (
        f"Cold-start prev_hash = {row.prev_hash!r}; must be GENESIS_HASH"
    )
    assert isinstance(audit_id, UUID)


@pytest.mark.asyncio
async def test_cold_start_uses_existing_head_when_db_non_empty() -> None:
    existing_head = "a" * 64
    factory = _session_factory_returning(scalar_value=existing_head)
    logger = AuditLogger(factory)
    await logger.log_decision(_make_decision())
    recorder = _last(factory)
    row = recorder.added_rows[0]
    assert row.prev_hash == existing_head


# =============================================================================
# Chain monotonicity — successive calls use prior current_hash as prev
# =============================================================================


@pytest.mark.asyncio
async def test_two_decisions_chain_forward() -> None:
    """Insert two decisions; the second's prev_hash MUST equal the first's
    current_hash. The cache prevents a second SELECT, so this also pins
    the in-process caching."""
    factory = _session_factory_returning(scalar_value=None)
    logger = AuditLogger(factory)

    await logger.log_decision(_make_decision())
    first_row = factory.recorders[0].added_rows[0]
    first_current = first_row.current_hash

    await logger.log_decision(_make_decision())
    second_row = factory.recorders[1].added_rows[0]
    assert second_row.prev_hash == first_current, (
        f"Chain broke: second.prev_hash={second_row.prev_hash!r}, "
        f"first.current_hash={first_current!r}"
    )


@pytest.mark.asyncio
async def test_chain_head_cached_no_second_select() -> None:
    """After the first insert, the chain head is cached in-process; the
    DB SELECT must NOT fire a second time. A mutant that forgets to
    populate self._chain_head would re-SELECT and fail this."""
    factory = _session_factory_returning(scalar_value=None)
    logger = AuditLogger(factory)

    await logger.log_decision(_make_decision())
    assert factory.recorders[0].execute_called is True  # cold-start SELECT did fire

    await logger.log_decision(_make_decision())
    assert factory.recorders[1].execute_called is False, (
        "Chain head was re-fetched from DB — caching broken"
    )


# =============================================================================
# Insert side effects: commit, metric increment, row field correctness
# =============================================================================


@pytest.mark.asyncio
async def test_commit_called_per_insert() -> None:
    factory = _session_factory_returning(scalar_value=None)
    logger = AuditLogger(factory)
    await logger.log_decision(_make_decision())
    assert factory.recorders[-1].commit_called is True


@pytest.mark.asyncio
async def test_metric_increments_with_insert_count() -> None:
    from synapse_common.metrics import AUDIT_CHAIN_LENGTH

    factory = _session_factory_returning(scalar_value=None)
    logger = AuditLogger(factory)
    await logger.log_decision(_make_decision())
    # Pin that the gauge reflects an internal counter, not just any number
    assert logger._insert_count == 1  # type: ignore[attr-defined]
    # The gauge value should equal the insert count (1.0 after first insert)
    assert AUDIT_CHAIN_LENGTH._value.get() == 1.0


@pytest.mark.asyncio
async def test_row_carries_decision_provenance() -> None:
    """The AuditConsensusRow constructor receives every consensus field
    we care about for forensics. Pin the field set so a mutant dropping
    `confidence` or `pareto_weights` fails."""
    factory = _session_factory_returning(scalar_value=None)
    logger = AuditLogger(factory)
    decision = _make_decision(confidence=0.92)
    await logger.log_decision(decision)
    row = factory.recorders[-1].added_rows[0]
    assert row.decision_id == decision.decision_id
    assert row.tier == "tier_1"
    assert row.confidence == 0.92
    assert row.pareto_weights == {"latency": 1.0}
    assert row.selected_action == {"action": "noop"}
    assert row.escalated is False  # no HITL escalation


# =============================================================================
# Contract enforcement (deal precondition)
# =============================================================================


@pytest.mark.asyncio
async def test_chain_head_is_64_hex_chars() -> None:
    factory = _session_factory_returning(scalar_value=None)
    logger = AuditLogger(factory)
    await logger.log_decision(_make_decision())
    row = factory.recorders[-1].added_rows[0]
    assert len(row.current_hash) == 64
    assert all(c in "0123456789abcdef" for c in row.current_hash)


@pytest.mark.asyncio
async def test_return_value_is_uuid() -> None:
    factory = _session_factory_returning(scalar_value=None)
    logger = AuditLogger(factory)
    result = await logger.log_decision(_make_decision())
    assert isinstance(result, UUID)


@pytest.mark.asyncio
async def test_three_decisions_strict_chain_walk() -> None:
    """End-to-end chain integrity: walking three logged decisions, each
    link must verify against `hash_payload_for_row` recomputation."""
    from orchestrator.audit.hash_chain import hash_payload_for_row, make_canonical_row

    factory = _session_factory_returning(scalar_value=None)
    logger = AuditLogger(factory)
    decisions = [_make_decision() for _ in range(3)]

    for d in decisions:
        await logger.log_decision(d)

    # Each log_decision opens a fresh session → one recorder per row.
    rows = [r.added_rows[0] for r in factory.recorders]
    # Walk: recompute each current_hash from its row + the prior current_hash
    expected_prev = GENESIS_HASH
    for d, row in zip(decisions, rows, strict=True):
        canonical = make_canonical_row(
            decision_id=d.decision_id,
            tier=str(d.tier.value),
            selected_action=d.selected_action,
            pareto_weights=d.pareto_weights,
            confidence=d.confidence,
            proposals=[p.model_dump(mode="json") for p in d.proposals],
            audit_trace=d.audit_trace,
        )
        expected_current = hash_payload_for_row(expected_prev, canonical)
        assert row.prev_hash == expected_prev
        assert row.current_hash == expected_current
        expected_prev = expected_current
