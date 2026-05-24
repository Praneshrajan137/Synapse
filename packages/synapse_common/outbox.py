"""
SYNAPSE outbox write-side helper (WS-2 §3, ADR-026).

Callers enqueue an outbox row inside the SAME ``AsyncSession`` transaction
as their primary write (e.g. ``audit_consensus``). The orchestrator's
``orchestrator/outbox/dispatcher.py`` worker drains ``status='PENDING'``
rows and publishes them to Kafka with ``enable.idempotence=true``,
preserving exactly-once delivery semantics.

This module is intentionally minimal — the SQLAlchemy ORM model lives in
``orchestrator.audit.models.AuditOutboxRow``, and we import it lazily so
``synapse_common`` does not depend on the orchestrator package at
import-time.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger(__name__)


_JSON_KWARGS: dict[str, Any] = {"sort_keys": True, "separators": (",", ":")}


def canonical_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Return a deterministically-serialisable copy of ``payload`` (I-13).

    SQLAlchemy's JSONB column accepts a dict; downstream Kafka delivery
    re-serialises with the same ``sort_keys`` discipline so the byte
    stream is stable.
    """
    result: dict[str, Any] = json.loads(json.dumps(payload, **_JSON_KWARGS, default=str))
    return result


async def enqueue(
    session: AsyncSession,
    decision_id: UUID,
    topic: str,
    payload: dict[str, Any],
    message_key: str | None = None,
    trace_id: str | None = None,
) -> UUID:
    """Insert an outbox row in the caller's session. Returns the new row id.

    The caller is responsible for ``session.commit()`` — the outbox row
    becomes visible to the dispatcher only after commit. This is the
    invariant that ties Kafka delivery to audit row existence.
    """
    from orchestrator.audit.models import AuditOutboxRow

    row = AuditOutboxRow(
        decision_id=decision_id,
        topic=topic,
        message_key=message_key,
        payload=canonical_payload(payload),
        status="PENDING",
        trace_id=trace_id,
    )
    session.add(row)
    await session.flush()
    logger.info(
        "outbox_enqueued",
        outbox_id=str(row.id),
        decision_id=str(decision_id),
        topic=topic,
    )
    return row.id  # type: ignore[no-any-return]
