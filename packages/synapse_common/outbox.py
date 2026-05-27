"""SYNAPSE outbox write-side helper (WS-2 §3, ADR-026).

Callers enqueue an outbox row inside the SAME ``AsyncSession`` transaction
as their primary write (e.g. ``audit_consensus``). The orchestrator's
``orchestrator/outbox/dispatcher.py`` worker drains ``status='PENDING'``
rows and publishes them to Kafka with ``enable.idempotence=true``,
preserving exactly-once delivery semantics.

This module is intentionally minimal — the SQLAlchemy ORM model lives in
``orchestrator.audit.models.AuditOutboxRow``, and we import it lazily so
``synapse_common`` does not depend on the orchestrator package at
import-time.

WS-2 fix: the previous helper passed ``message_key=`` and ``trace_id=``
which did not exist on ``AuditOutboxRow`` — the row has ``partition_key``
and ``headers`` (a JSONB dict). The helper is now schema-correct and
also supports ``audit_id=None`` for ingress events (orders) that do not
correspond to a consensus decision.
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
    *,
    decision_id: UUID,
    topic: str,
    payload: dict[str, Any],
    audit_id: UUID | None = None,
    partition_key: str | None = None,
    headers: dict[str, str] | None = None,
) -> UUID:
    """Insert an outbox row in the caller's session. Returns the new row id.

    The caller is responsible for ``session.commit()`` — the outbox row
    becomes visible to the dispatcher only after commit. This is the
    invariant that ties Kafka delivery to audit row existence.

    Args:
        decision_id: logical correlation id. For consensus rows this is
            the same UUID as ``audit_consensus.decision_id``. For ingress
            events (orders) it is a freshly-minted UUID — the dispatcher
            still uses it as Kafka partition key default.
        audit_id: optional FK to ``audit_consensus.id``. Required for
            consensus-row publications; left ``None`` for pre-decision
            ingress events (WS-2 migration 0004 made the column nullable).
        partition_key: explicit Kafka partition key. Defaults to
            ``str(decision_id)`` when not supplied.
        headers: trace-propagation headers (``traceparent``, ``tracestate``,
            ``baggage``). Persisted as JSONB and replayed onto the Kafka
            message by the dispatcher so the trace stays joined across the
            commit→publish gap.
    """
    from orchestrator.audit.models import AuditOutboxRow

    row = AuditOutboxRow(
        audit_id=audit_id,
        decision_id=decision_id,
        topic=topic,
        partition_key=partition_key if partition_key is not None else str(decision_id),
        payload=canonical_payload(payload),
        headers=dict(headers or {}),
        status="PENDING",
    )
    session.add(row)
    await session.flush()
    logger.info(
        "outbox_enqueued",
        outbox_id=str(row.id),
        decision_id=str(decision_id),
        audit_id=str(audit_id) if audit_id else None,
        topic=topic,
    )
    return row.id  # type: ignore[no-any-return]
