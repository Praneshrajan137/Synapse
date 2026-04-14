"""
SYNAPSE Orchestrator — Append-only PostgreSQL audit logger (I-4).

Every consensus decision is persisted with full provenance.
DELETE and UPDATE are revoked at the database level.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import deal
import structlog

from orchestrator.audit.models import AuditConsensusRow

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
    from synapse_common.models import ConsensusDecision

logger = structlog.get_logger(__name__)


class AuditLogger:
    """Append-only audit writer backed by PostgreSQL."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory
        self._insert_count: int = 0

    @deal.pre(
        lambda self, decision: decision.decision_id is not None,
        message="I-4: decision_id must be present",
    )
    @deal.post(
        lambda result: result is not None,
        message="I-4: Audit row must be inserted",
    )
    async def log_decision(self, decision: ConsensusDecision) -> UUID:
        """Insert a decision row and return the audit row UUID."""
        async with self._session_factory() as session:
            row = AuditConsensusRow(
                decision_id=decision.decision_id,
                tier=str(decision.tier.value),
                phase_reached=decision.phase_reached,
                proposals=[p.model_dump(mode="json") for p in decision.proposals],
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
            )
            session.add(row)
            await session.commit()
            self._insert_count += 1

            logger.info(
                "audit_decision_logged",
                decision_id=str(decision.decision_id),
                audit_id=str(row.id),
                tier=str(decision.tier.value),
            )
            return row.id  # type: ignore[return-value]
