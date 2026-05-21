"""
SYNAPSE Orchestrator — SQLAlchemy ORM models for the append-only audit trail (I-4).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Boolean, Column, DateTime, Float, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase


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
    """Transactional outbox row (WS-2 §3, ADR-026).

    Written in the SAME Postgres transaction as the audit_consensus row by
    ``synapse_common.outbox.enqueue`` so audit existence and Kafka delivery
    cannot diverge. The dispatcher updates ``status`` and ``sent_at`` —
    ``synapse_app`` therefore has INSERT + SELECT + UPDATE on this table
    (DELETE is still revoked at the DB level).
    """

    __tablename__ = "audit_outbox"

    id: Any = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    decision_id: Any = Column(UUID(as_uuid=True), nullable=False)
    topic: Any = Column(String(200), nullable=False)
    message_key: Any = Column(String(200), nullable=True)
    payload: Any = Column(JSONB, nullable=False)
    status: Any = Column(String(20), nullable=False, default="PENDING")
    attempts: Any = Column(Integer, nullable=False, default=0)
    last_error: Any = Column(String(2000), nullable=True)
    trace_id: Any = Column(String(64), nullable=True)
    created_at: Any = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    sent_at: Any = Column(DateTime(timezone=True), nullable=True)
