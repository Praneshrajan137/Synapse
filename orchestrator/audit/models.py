"""
SYNAPSE Orchestrator — SQLAlchemy ORM models for the append-only audit trail (I-4).

Sprint 7 addition: ``AuditOutboxRow`` — workflow primitive that bridges the
orchestrator's Postgres audit transaction and the Kafka publish step.
The outbox row is INSERTed in the SAME transaction as the audit row so we
can never commit an audit decision without queuing its Kafka publication.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import ENUM, JSONB, UUID
from sqlalchemy.orm import DeclarativeBase

OUTBOX_STATUSES: tuple[str, ...] = ("PENDING", "IN_FLIGHT", "PUBLISHED", "FAILED")


class Base(DeclarativeBase):
    pass


class AuditConsensusRow(Base):
    """Maps to ``audit_consensus`` table (Sprint 4 addition).

    INSERT + SELECT only — DELETE and UPDATE are revoked at the DB level.
    """

    __tablename__ = "audit_consensus"

    id: Any = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    decision_id: Any = Column(UUID(as_uuid=True), nullable=False, unique=True)
    timestamp: Any = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    tier: Any = Column(String(10), nullable=False)
    phase_reached: Any = Column(Integer, nullable=False, default=1)
    proposals: Any = Column(JSONB, nullable=False)
    selected_action: Any = Column(JSONB, nullable=False)
    pareto_weights: Any = Column(JSONB, nullable=False)
    confidence: Any = Column(Float, nullable=False)
    debate_rounds: Any = Column(Integer, nullable=False, default=0)
    escalated: Any = Column(Boolean, nullable=False, default=False)
    human_override: Any = Column(JSONB, nullable=True)
    execution_confirmations: Any = Column(JSONB, nullable=False, server_default="[]")
    context_messages: Any = Column(JSONB, nullable=False)
    audit_trace: Any = Column(JSONB, nullable=False)
    pareto_front: Any = Column(JSONB, nullable=True)
    outcome: Any = Column(JSONB, nullable=True)
    created_at: Any = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    # Sprint 9 §M-sec-4 (ADR-033) — tamper-evidence chained hashes.
    # Existing rows have NULL chain values; new rows always populate.
    prev_hash: Any = Column(String(64), nullable=True)
    current_hash: Any = Column(String(64), nullable=True)


class AuditOutboxRow(Base):
    """Maps to ``audit_outbox`` table (Sprint 7 addition, WS-2).

    Workflow row: INSERTed alongside the audit row, then mutated by the
    dispatcher (PENDING -> IN_FLIGHT -> PUBLISHED|FAILED). NEVER deleted —
    the audit_outbox table holds the publish history; archival belongs to
    a separate retention worker (WS-7).
    """

    __tablename__ = "audit_outbox"

    id: Any = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    audit_id: Any = Column(
        UUID(as_uuid=True),
        ForeignKey("audit_consensus.id", ondelete="RESTRICT"),
        nullable=False,
    )
    decision_id: Any = Column(UUID(as_uuid=True), nullable=False)
    topic: Any = Column(String(128), nullable=False)
    partition_key: Any = Column(String(256), nullable=True)
    payload: Any = Column(JSONB, nullable=False)
    headers: Any = Column(JSONB, nullable=False, server_default="{}")
    status: Any = Column(
        ENUM(*OUTBOX_STATUSES, name="outbox_status", create_type=False),
        nullable=False,
        default="PENDING",
    )
    retries: Any = Column(Integer, nullable=False, default=0)
    last_error: Any = Column(Text, nullable=True)
    next_attempt_at: Any = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    published_at: Any = Column(DateTime(timezone=True), nullable=True)
    created_at: Any = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    updated_at: Any = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
