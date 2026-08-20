"""
SYNAPSE Orchestrator — SQLAlchemy ORM models for the append-only audit trail (I-4).

Sprint 7 addition: ``AuditOutboxRow`` — workflow primitive that bridges the
orchestrator's Postgres audit transaction and the Kafka publish step.
The outbox row is INSERTed in the SAME transaction as the audit row so we
can never commit an audit decision without queuing its Kafka publication.

purpose-achievement-audit task 7.8 addition: ``DecisionDataProvenance`` — the
record written to the new append-only ``decision_data_provenance`` table
(design AD-10, conflict CF-1). It is deliberately a **Pydantic** model rather
than an ORM row: ``orchestrator/inference/serve.py`` runs ``create_all`` on a
connection held by the non-owner ``synapse_app`` role, so DDL for this table
comes from the migration
(``orchestrator/audit/migrations/0007_decision_data_provenance.sql``, mirrored
at ``infrastructure/postgres/09_decision_data_provenance.sql`` per E-S9-14),
exactly as ``decision_outcomes`` does.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any, Final, Literal

from pydantic import BaseModel, ConfigDict, field_validator
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


# ---------------------------------------------------------------------------
# decision_data_provenance (purpose-achievement-audit, AD-10 / CF-1, R4.4)
# ---------------------------------------------------------------------------

SOURCE_CLASSES: tuple[str, ...] = ("SEEDED", "EXTERNAL", "STUB")
"""The three world-source classes a decision's input state can come from.

Mirrors the ``SourceProvenance`` enum that ``packages/synapse_common/world/source.py``
gains in task 10.11 (design AD-11) and the ``CHECK`` constraint in the migration.
Declared as a tuple here for the same reason ``OUTBOX_STATUSES`` is: one committed
list that the DDL, the model, and the tests all read.
"""

SourceClass = Literal["SEEDED", "EXTERNAL", "STUB"]

PROVENANCE_FIELDS: Final[tuple[str, ...]] = (
    "decision_id",
    "feed_revision",
    "is_synthetic",
    "observed_at",
    "source_class",
)
"""The frozen canonical field set, in canonical (sorted) key order.

Property 21 asserts that a round-tripped provenance payload's key set is exactly
this tuple. The storage columns ``id`` and ``created_at`` are deliberately absent:
they are bookkeeping assigned by Postgres, not part of the recorded fact.
"""


class DecisionDataProvenance(BaseModel):
    """One append-only ``decision_data_provenance`` row: where a decision's input came from.

    R4.4 wants a data-provenance value on "the audit record for that decision".
    ``make_canonical_row`` is byte-pinned by a literal-digest test, and adding a
    field to it is a chain-rewrite migration rather than a field bump (I-4,
    E-S9-02) - so provenance lands in its own append-only table keyed by
    ``decision_id``, exactly as ``decision_outcomes`` did for realized outcomes
    (ADR-047 D2). The hashed canonical audit row is untouched; a reader joins
    ``audit_consensus`` to this table on ``decision_id``. Conflict **CF-1** records
    that this reading of "the audit record" needs operator confirmation.

    Frozen, because a recorded provenance is evidence: the row is INSERTed once and
    never edited (the table grants ``synapse_app`` SELECT + INSERT only, with
    UPDATE/DELETE revoked and a migration-time self-test). A correction appends a
    newer row; readers take the latest ``observed_at``.

    ``extra="forbid"`` plus :data:`PROVENANCE_FIELDS` is what makes the round trip
    total: an unknown key is rejected rather than silently dropped, so
    :meth:`to_canonical_json` -> :meth:`from_canonical_json` cannot lose or invent a
    field.

    ``is_synthetic`` is *derived* by the caller from the active source's declared
    class (AD-11) and recorded here; this model stores the pair it was handed rather
    than recomputing it, so a disagreement between the two stays visible in the
    audit trail instead of being quietly normalised away.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    decision_id: uuid.UUID
    """The ``audit_consensus.decision_id`` this provenance describes."""

    source_class: SourceClass
    """``SEEDED`` | ``EXTERNAL`` | ``STUB`` - the distinguishing value R4.4 requires."""

    is_synthetic: bool
    """The perceived state's ``is_synthetic`` flag as derived from the active source."""

    feed_revision: str | None = None
    """Feed offset/revision identifier where the source exposes one; ``None`` otherwise."""

    observed_at: datetime
    """When the input state was observed. Timezone-aware; normalised to UTC."""

    @field_validator("observed_at")
    @classmethod
    def _require_utc(cls, value: datetime) -> datetime:
        """Reject a naive timestamp and normalise to UTC.

        A naive ``observed_at`` would round-trip to a different instant depending on
        the reader's locale, which is exactly the kind of silent drift an audit row
        must not carry. ``TIMESTAMPTZ`` in the DDL enforces the same thing.
        """
        if value.tzinfo is None:
            msg = "observed_at must be timezone-aware (audit timestamps are TIMESTAMPTZ)"
            raise ValueError(msg)
        return value.astimezone(UTC)

    def to_canonical_dict(self) -> dict[str, Any]:
        """Project to JSON primitives, keys exactly :data:`PROVENANCE_FIELDS`.

        Pure: no clock, no I/O, no defaults filled in at call time.
        """
        return {
            "decision_id": str(self.decision_id),
            "feed_revision": self.feed_revision,
            "is_synthetic": self.is_synthetic,
            "observed_at": self.observed_at.isoformat(),
            "source_class": self.source_class,
        }

    def to_canonical_json(self) -> str:
        """Canonical serialisation - byte-stable across runs and processes."""
        return json.dumps(self.to_canonical_dict(), sort_keys=True, separators=(",", ":"))

    @classmethod
    def from_canonical_dict(cls, payload: dict[str, Any]) -> DecisionDataProvenance:
        """Inverse of :meth:`to_canonical_dict`. An unknown key raises."""
        return cls.model_validate(payload)

    @classmethod
    def from_canonical_json(cls, payload: str) -> DecisionDataProvenance:
        """Inverse of :meth:`to_canonical_json`."""
        parsed: Any = json.loads(payload)
        if not isinstance(parsed, dict):
            msg = f"expected a JSON object for a provenance row, got {type(parsed).__name__}"
            raise ValueError(msg)
        return cls.from_canonical_dict(parsed)
