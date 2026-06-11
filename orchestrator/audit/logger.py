"""
SYNAPSE Orchestrator — Append-only PostgreSQL audit logger (I-4 + ADR-033).

Every consensus decision is persisted with full provenance.
DELETE and UPDATE are revoked at the database level.

Sprint 9 (ADR-033) adds chained-hash tamper-evidence: every row carries
``prev_hash`` and ``current_hash`` so ``synapse audit verify`` can walk
the chain and detect tampering between any two anchor points.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

# Runtime import — used by ``log_decision`` to cast the SQLAlchemy column
# value back to a concrete UUID for the return signature.
from uuid import UUID  # noqa: E402  (placed after structlog imports for clarity)

import deal
import structlog
from sqlalchemy import desc, select
from synapse_common.metrics import AUDIT_CHAIN_LENGTH

from orchestrator.audit.hash_chain import (
    GENESIS_HASH,
    hash_payload_for_row,
    make_canonical_row,
)
from orchestrator.audit.models import AuditConsensusRow

if TYPE_CHECKING:
    pass

    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
    from synapse_common.models import ConsensusDecision

logger = structlog.get_logger(__name__)


class AuditLogger:
    """Append-only audit writer backed by PostgreSQL.

    Sprint 9: chained-hash population at insert time. Chain head is
    cached in-process; recovered from the database on first call so the
    chain survives restarts.
    """

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory
        self._insert_count: int = 0
        self._chain_head: str | None = None

    async def _load_chain_head(self, session: AsyncSession) -> str:
        """Return the most recent ``current_hash`` (or GENESIS_HASH on empty)."""
        if self._chain_head is not None:
            return self._chain_head
        stmt = (
            select(AuditConsensusRow.current_hash)
            .where(AuditConsensusRow.current_hash.is_not(None))
            .order_by(desc(AuditConsensusRow.created_at), desc(AuditConsensusRow.id))
            .limit(1)
        )
        result = await session.execute(stmt)
        head = result.scalar_one_or_none()
        self._chain_head = head or GENESIS_HASH
        return self._chain_head

    @deal.pre(
        lambda self, decision: decision.decision_id is not None,
        message="I-4: decision_id must be present",
    )
    @deal.post(
        lambda result: result is not None,
        message="I-4: Audit row must be inserted",
    )
    async def log_decision(self, decision: ConsensusDecision) -> UUID:
        """Insert a decision row + chain hash; return the audit row UUID."""
        async with self._session_factory() as session:
            prev_hash = await self._load_chain_head(session)
            canonical = make_canonical_row(
                decision_id=decision.decision_id,
                tier=str(decision.tier.value),
                selected_action=decision.selected_action,
                pareto_weights=decision.pareto_weights,
                confidence=decision.confidence,
                proposals=[p.model_dump(mode="json") for p in decision.proposals],
                audit_trace=decision.audit_trace,
            )
            current_hash = hash_payload_for_row(prev_hash, canonical)
            row = AuditConsensusRow(
                decision_id=decision.decision_id,
                tier=str(decision.tier.value),
                phase_reached=decision.phase_reached,
                proposals=canonical["proposals"],
                selected_action=decision.selected_action,
                pareto_weights=decision.pareto_weights,
                confidence=decision.confidence,
                debate_rounds=decision.debate_rounds,
                escalated=decision.escalated_to_human,
                human_override=decision.human_override,
                execution_confirmations=decision.execution_confirmations,
                context_messages=[m.model_dump(mode="json") for m in decision.context_messages],
                audit_trace=decision.audit_trace,
                pareto_front=decision.pareto_front,
                prev_hash=prev_hash,
                current_hash=current_hash,
            )
            session.add(row)
            # Publish the decision to the real-time firehose in the SAME
            # transaction (the outbox pattern): the dispatcher drains PENDING
            # rows → synapse.orchestrator.decision → api firehose WS → cockpit /
            # Living Map. Without this enqueue the rich real-time UI renders
            # empty even though decisions are being made. One commit covers both
            # the audit row and the outbox row (atomic; ties Kafka delivery to
            # audit-row existence — ADR-026).
            from synapse_common.outbox import enqueue as _outbox_enqueue
            from synapse_common.synthetic import is_synthetic_decision

            await _outbox_enqueue(
                session,
                decision_id=decision.decision_id,
                audit_id=row.id,
                topic="synapse.orchestrator.decision",
                payload={
                    "decision_id": str(decision.decision_id),
                    "tier": str(decision.tier.value),
                    "confidence": decision.confidence,
                    "phase_reached": decision.phase_reached,
                    "escalated": decision.escalated_to_human,
                    "selected_action": decision.selected_action,
                    # ADR-044 honesty channel: the firehose envelope tells the
                    # UI whether ANY input proposal ran degraded, and whether
                    # the decision is traffic-generator synthetic — without
                    # these the live feed renders fallbacks and demo pulses
                    # indistinguishably from real, fully-modelled commerce.
                    "degraded": any(
                        p.provenance is not None and p.provenance.degraded
                        for p in decision.proposals
                    ),
                    "is_synthetic": is_synthetic_decision(decision.context_messages),
                },
            )
            await session.commit()
            self._insert_count += 1
            self._chain_head = current_hash
            AUDIT_CHAIN_LENGTH.set(float(self._insert_count))

            logger.info(
                "audit_decision_logged",
                decision_id=str(decision.decision_id),
                audit_id=str(row.id),
                tier=str(decision.tier.value),
                chain_head=current_hash[:12],
            )
            # row.id is a SQLAlchemy Column → its runtime value is a UUID,
            # but the descriptor type is Any. Cast to satisfy --strict.
            return UUID(str(row.id))
