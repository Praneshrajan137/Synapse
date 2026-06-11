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

    async def flush(self) -> None:
        # log_decision now enqueues an outbox row in the same transaction
        # (synapse_common.outbox.enqueue calls session.flush()).
        return None

    async def commit(self) -> None:
        self.commit_called = True

    async def rollback(self) -> None:
        return None

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


# =============================================================================
# ADR-044 — honesty fields on the outbox payload + provenance-bearing chains
# =============================================================================


def _make_decision_with(
    *,
    provenance: Any = None,
    order_id: str | None = None,
    confidence: float = 0.95,
) -> ConsensusDecision:
    """Decision factory with optional structured provenance + request context."""
    from synapse_common.models import ContextMessage

    context = []
    if order_id is not None:
        context.append(
            ContextMessage(
                source="orchestrator",
                content={
                    "type": "decision_request",
                    "tier": "tier_1",
                    "request": {"order_id": order_id},
                },
            )
        )
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
                provenance=provenance,
            )
        ],
        selected_action={"action": "noop"},
        pareto_weights={"latency": 1.0},
        confidence=confidence,
        audit_trace=["t"],
        context_messages=context,
    )


@pytest.mark.asyncio
async def test_outbox_payload_carries_honesty_fields_false_case() -> None:
    """ADR-044: the firehose envelope (outbox payload) MUST carry degraded +
    is_synthetic. Default decision: both False — and the keys must EXIST
    (a mutant dropping them would make the FE render undefined as falsy,
    silently disabling the honesty channel)."""
    factory = _session_factory_returning(scalar_value=None)
    logger = AuditLogger(factory)
    await logger.log_decision(_make_decision())
    outbox_row = factory.recorders[-1].added_rows[1]
    assert outbox_row.payload["degraded"] is False
    assert outbox_row.payload["is_synthetic"] is False


@pytest.mark.asyncio
async def test_outbox_payload_degraded_true_when_any_proposal_degraded() -> None:
    from synapse_common.provenance import Provenance

    factory = _session_factory_returning(scalar_value=None)
    logger = AuditLogger(factory)
    await logger.log_decision(_make_decision_with(provenance=Provenance.degraded_fallback()))
    outbox_row = factory.recorders[-1].added_rows[1]
    assert outbox_row.payload["degraded"] is True


@pytest.mark.asyncio
async def test_outbox_payload_carries_timestamp_and_agent_summary() -> None:
    """The live-feed envelope needs a render timestamp and the lean per-agent
    summary (agent_name + confidence + degraded) — the full proposals carry
    whole forecast arrays and must NOT ride the firehose."""
    from synapse_common.provenance import Provenance

    factory = _session_factory_returning(scalar_value=None)
    logger = AuditLogger(factory)
    decision = _make_decision_with(provenance=Provenance.degraded_fallback(), confidence=0.9)
    await logger.log_decision(decision)
    payload = factory.recorders[-1].added_rows[1].payload
    assert payload["timestamp"] == decision.timestamp.isoformat()
    assert payload["agents"] == [
        {"agent_name": "demand_prophet", "confidence": 0.9, "degraded": True}
    ]
    assert "proposals" not in payload, "full proposals must not ride the firehose"


@pytest.mark.asyncio
async def test_outbox_payload_degraded_if_any_proposal_degraded() -> None:
    """Mutation guard: the honesty envelope is an ANY over proposals, and the
    per-agent summaries preserve each proposal's own degraded state."""
    from synapse_common.provenance import ConfidenceBasis, Provenance

    decision = _make_decision()
    decision = decision.model_copy(
        update={
            "proposals": [
                AgentProposal(
                    agent_name=AgentName.DEMAND_PROPHET,
                    decision_id=uuid4(),
                    utility_score=0.7,
                    confidence=0.91,
                    justification_trace=["real"],
                    payload={},
                    tier=DecisionTier.TIER_1,
                    provenance=Provenance.real(
                        model_version="registry-v9",
                        confidence_basis=ConfidenceBasis.CONFORMAL_INTERVAL,
                    ),
                ),
                AgentProposal(
                    agent_name=AgentName.ROUTING_NAVIGATOR,
                    decision_id=uuid4(),
                    utility_score=0.4,
                    confidence=0.5,
                    justification_trace=["fallback"],
                    payload={},
                    tier=DecisionTier.TIER_1,
                    provenance=Provenance.degraded_fallback(),
                ),
            ]
        }
    )
    factory = _session_factory_returning(scalar_value=None)
    logger = AuditLogger(factory)
    await logger.log_decision(decision)

    payload = factory.recorders[-1].added_rows[1].payload
    assert payload["degraded"] is True
    assert payload["agents"] == [
        {"agent_name": "demand_prophet", "confidence": 0.91, "degraded": False},
        {"agent_name": "routing_navigator", "confidence": 0.5, "degraded": True},
    ]


@pytest.mark.asyncio
async def test_outbox_payload_is_synthetic_for_traffic_generator_order() -> None:
    factory = _session_factory_returning(scalar_value=None)
    logger = AuditLogger(factory)
    await logger.log_decision(_make_decision_with(order_id="synthetic-1718000000-3"))
    outbox_row = factory.recorders[-1].added_rows[1]
    assert outbox_row.payload["is_synthetic"] is True


@pytest.mark.asyncio
async def test_real_provenance_not_degraded_in_outbox() -> None:
    from synapse_common.provenance import ConfidenceBasis, Provenance

    factory = _session_factory_returning(scalar_value=None)
    logger = AuditLogger(factory)
    await logger.log_decision(
        _make_decision_with(
            provenance=Provenance.real(
                model_version="registry-v9",
                confidence_basis=ConfidenceBasis.CONFORMAL_INTERVAL,
            )
        )
    )
    outbox_row = factory.recorders[-1].added_rows[1]
    assert outbox_row.payload["degraded"] is False


@pytest.mark.asyncio
async def test_mixed_legacy_and_provenance_chain_verifies() -> None:
    """ADR-044 D2 chain-safety: a legacy-shaped decision (no provenance)
    followed by a provenance-bearing one must verify link-by-link with the
    SAME recompute the verifier CLI uses — stored == hashed, both shapes."""
    from synapse_common.audit_chain import verify_row_hash
    from synapse_common.provenance import Provenance

    factory = _session_factory_returning(scalar_value=None)
    logger = AuditLogger(factory)

    legacy_shaped = _make_decision()
    provenance_bearing = _make_decision_with(provenance=Provenance.degraded_fallback())
    await logger.log_decision(legacy_shaped)
    await logger.log_decision(provenance_bearing)

    rows = [r.added_rows[0] for r in factory.recorders]
    assert rows[1].prev_hash == rows[0].current_hash
    for row in rows:
        assert verify_row_hash(
            prev_hash=row.prev_hash,
            current_hash=row.current_hash,
            decision_id=row.decision_id,
            tier=row.tier,
            selected_action=row.selected_action,
            pareto_weights=row.pareto_weights,
            confidence=row.confidence,
            proposals=row.proposals,
            audit_trace=row.audit_trace,
        )


@pytest.mark.asyncio
async def test_stored_proposals_include_structured_provenance() -> None:
    """The audit row's proposals JSONB carries the provenance dict — the
    decisions API reads it from there (no regex over trace strings)."""
    from synapse_common.provenance import Provenance

    factory = _session_factory_returning(scalar_value=None)
    logger = AuditLogger(factory)
    await logger.log_decision(_make_decision_with(provenance=Provenance.degraded_fallback()))
    row = factory.recorders[-1].added_rows[0]
    assert row.proposals[0]["provenance"]["degraded"] is True
    assert row.proposals[0]["provenance"]["confidence_basis"] == "fallback_floor"


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
