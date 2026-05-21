"""
SYNAPSE Orchestrator — Append-only PostgreSQL audit logger (I-4).

Sprint 7 (WS-2): Every consensus decision is written to TWO rows in the
same transaction:

    audit_consensus  — the immutable record of truth.
    audit_outbox     — the Kafka publish queue, drained by OutboxDispatcher.

Both must commit together. Either both rows land or neither does. This
closes the orchestrator's previous split-brain risk where an audit row
could exist without its Kafka publication, or vice versa.

DELETE and UPDATE on audit_consensus remain revoked at the DB level.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import deal
import structlog

from orchestrator.audit.models import AuditConsensusRow, AuditOutboxRow

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
    from synapse_common.models import ConsensusDecision

logger = structlog.get_logger(__name__)

DEFAULT_DECISION_TOPIC = "synapse.orchestrator.decision"

JSON_KWARGS: dict[str, Any] = {"sort_keys": True, "separators": (",", ":")}


class AuditLogger:
    """Append-only audit writer + outbox enqueue, atomic in one transaction."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        decision_topic: str = DEFAULT_DECISION_TOPIC,
    ) -> None:
        self._session_factory = session_factory
        self._decision_topic = decision_topic
        self._insert_count: int = 0

    @deal.pre(
        lambda self, decision, headers=None: decision.decision_id is not None,
        message="I-4: decision_id must be present",
    )
    @deal.post(
        lambda result: result is not None,
        message="I-4: Audit row must be inserted",
    )
    async def log_decision(
        self,
        decision: ConsensusDecision,
        headers: dict[str, str] | None = None,
    ) -> UUID:
        """Insert audit + outbox rows atomically; return the audit row UUID.

        Args:
            decision: The fully-formed ConsensusDecision to persist.
            headers: Optional W3C trace headers (``traceparent``,
                ``tracestate``) plus any other Kafka headers (e.g.
                ``Idempotency-Key``). Stored verbatim on the outbox row so
                the dispatcher can replay them onto the Kafka message.

        The two INSERTs share one Postgres transaction. If either fails,
        the transaction rolls back and *neither* row exists. The caller
        gets the exception and can retry; the next successful call will
        produce a fresh ``decision_id``-keyed audit row (UNIQUE) so a
        partial-state replay never duplicates the audit record.
        """
        kafka_payload = json.loads(
            json.dumps(
                {
                    "decision_id": str(decision.decision_id),
                    "tier": str(decision.tier.value),
                    "selected_action": decision.selected_action,
                    "confidence": decision.confidence,
                    "escalated": decision.escalated_to_human,
                    "phase_reached": decision.phase_reached,
                    "debate_rounds": decision.debate_rounds,
                },
                **JSON_KWARGS,
                default=str,
            )
        )
        partition_key = str(decision.decision_id)

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
            # Flush so row.id is populated before we reference it from the
            # outbox FK, but stay inside the transaction.
            await session.flush()

            outbox = AuditOutboxRow(
                audit_id=row.id,
                decision_id=decision.decision_id,
                topic=self._decision_topic,
                partition_key=partition_key,
                payload=kafka_payload,
                headers=dict(headers or {}),
                status="PENDING",
                retries=0,
            )
            session.add(outbox)

            await session.commit()
            self._insert_count += 1

            logger.info(
                "audit_decision_logged",
                decision_id=str(decision.decision_id),
                audit_id=str(row.id),
                outbox_id=str(outbox.id),
                tier=str(decision.tier.value),
                topic=self._decision_topic,
            )
            audit_id: UUID = row.id  # SQLAlchemy column types are typed Any
            return audit_id
