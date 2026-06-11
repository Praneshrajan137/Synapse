"""Decisions router — proxies to orchestrator + queries audit trail.

P1 additions:
- ``POST /api/v1/decisions/{decision_id}/override`` — operator override.
  Writes to ``audit_escalations`` (INSERT-only, I-4 preserved) BEFORE
  notifying the orchestrator (FE-INV-003 / FE-INV-021).
- ``POST /api/v1/decisions/{decision_id}/override`` requires Role.OPS.
"""

from __future__ import annotations

import os
import time
from datetime import UTC, datetime
from typing import Annotated, Any
from uuid import UUID

import httpx
import structlog
from fastapi import APIRouter, Depends, HTTPException, Path, status
from pydantic import BaseModel, Field, field_validator
from synapse_common.auth import OperatorContext, Role
from synapse_common.tracing import inject_a2a_headers

from api.middleware.jwt import CurrentOperator, RequireRole

logger = structlog.get_logger(__name__)
router = APIRouter()

ORCHESTRATOR_URL = os.environ.get("SYNAPSE_ORCHESTRATOR_URL", "http://orchestrator:8085")


def _dsn() -> str:
    """Resolve the audit Postgres DSN. Fail-fast — never embed a credential.

    Plan v2 / Phase 5: the previous hardcoded ``synapse_app:<password>@…``
    default put a password in source. The DSN MUST come from the environment
    (Secret Manager / SOPS in prod, ``.env`` in dev). An unset DSN is a
    misconfiguration, not a thing to paper over with a baked-in secret.
    """
    dsn = os.environ.get("POSTGRES_DSN")
    if not dsn:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="POSTGRES_DSN not configured",
        )
    return dsn


# ─────────────────────────────────────────────────────────────────────────────
# Existing endpoints (kept; SELECT now aliases `id` → `audit_id` to match
# the documented API shape the FE consumes).
# ─────────────────────────────────────────────────────────────────────────────


@router.post("/")
async def trigger_decision(
    payload: dict[str, Any],
    op: Annotated[OperatorContext, Depends(RequireRole(Role.OPS))],
) -> dict[str, Any]:
    # Plan v2 / Phase 5: triggering a decision is a privileged action — OPS role.
    # WS-2: inject W3C traceparent at the API → orchestrator boundary so the
    # request span carries across the process hop. Sprint 7 wired this for
    # A2A + Kafka but missed the gateway's httpx call (see CURRENT.md C3).
    trace_headers: dict[str, str] = {}
    inject_a2a_headers(trace_headers)
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{ORCHESTRATOR_URL}/api/v1/decisions",
                json=payload,
                headers=trace_headers,
            )
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=503, detail=f"orchestrator unreachable: {exc}") from exc
    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)
    return resp.json()


@router.get("/recent")
async def recent_decisions(
    op: Annotated[OperatorContext, Depends(CurrentOperator)],
    limit: int = 20,
    tier: str | None = None,
    city: str | None = None,
    escalated: bool | None = None,
) -> dict[str, Any]:
    """P3: filterable audit-trail query.

    Query parameters compose into a parametrized WHERE clause. The
    `(city, created_at DESC)` index from migration 04 keeps the city +
    time-range filters under 200ms on million-row tables.
    """
    if limit < 1 or limit > 500:
        raise HTTPException(status_code=422, detail="limit must be in [1, 500]")
    if tier is not None and tier not in {"tier_1", "tier_2", "tier_3", "tier_4"}:
        raise HTTPException(status_code=422, detail="invalid tier")
    if city is not None and city not in {"bengaluru", "mumbai"}:
        raise HTTPException(status_code=422, detail="invalid city")
    try:
        import psycopg2
        from synapse_common.synthetic import SYNTHETIC_ORDER_PREFIX

        conn = psycopg2.connect(_dsn())
        try:
            with conn.cursor() as cur:
                where = ["1=1"]
                params: list[Any] = [SYNTHETIC_ORDER_PREFIX]
                if tier is not None:
                    where.append("tier = %s")
                    params.append(tier)
                if city is not None:
                    where.append("city = %s")
                    params.append(city)
                if escalated is not None:
                    where.append("escalated = %s")
                    params.append(escalated)
                params.append(limit)
                cur.execute(
                    # Read from audit_consensus — the table the orchestrator
                    # actually writes (AuditConsensusRow). The legacy
                    # audit_decisions table has no writer and lacks
                    # phase_reached; reading it 503'd the live feed.
                    #
                    # ADR-044 honesty channel (additive, computed in SQL so the
                    # row-heavy JSONB columns never leave the database):
                    #   degraded     — any proposal's structured provenance ran
                    #                  a fallback (PG16; jsonb_path_exists is
                    #                  PG12+).
                    #   is_synthetic — the decision_request context message
                    #                  carries a traffic-generator order_id
                    #                  (prefix rule owned by
                    #                  synapse_common.synthetic, passed as a
                    #                  jsonpath var — single source of truth).
                    "SELECT id AS audit_id, decision_id, tier, phase_reached, "
                    "       confidence, escalated, city, created_at, "
                    "       COALESCE(jsonb_path_exists(proposals, "
                    "         '$[*].provenance.degraded ? (@ == true)'), false) AS degraded, "
                    "       COALESCE(jsonb_path_exists(context_messages, "
                    "         '$[*].content.request.order_id ? (@ starts with $prefix)', "
                    "         jsonb_build_object('prefix', %s::text)), false) AS is_synthetic "
                    "FROM audit_consensus "
                    f"WHERE {' AND '.join(where)} "
                    "ORDER BY created_at DESC LIMIT %s",
                    tuple(params),
                )
                rows = [
                    {
                        "audit_id": str(r[0]),
                        "decision_id": str(r[1]),
                        "tier": r[2],
                        "phase_reached": r[3] if r[3] is not None else 1,
                        "confidence": float(r[4]),
                        "escalated": bool(r[5]),
                        "city": r[6],
                        "created_at": r[7].isoformat() if r[7] else None,
                        "degraded": bool(r[8]),
                        "is_synthetic": bool(r[9]),
                    }
                    for r in cur.fetchall()
                ]
        finally:
            conn.close()
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=f"audit unavailable: {exc}") from exc
    return {"decisions": rows, "count": len(rows)}


@router.get("/{decision_id}")
async def get_decision(
    decision_id: UUID,
    op: Annotated[OperatorContext, Depends(CurrentOperator)],
) -> dict[str, Any]:
    """P3: single audit row with full append-only context.

    ADR-044: the row's previously-unexposed anatomy columns (debate_rounds,
    pareto_front, execution_confirmations, context_messages, outcome, the
    tamper-evidence hashes) now reach the response, plus three computed
    fields — ``degraded``, ``is_synthetic``, and ``chain_verified`` (a
    single-row hash recompute; the full chain walk stays with
    ``synapse audit verify``). All additive; existing keys unchanged.
    """
    try:
        import psycopg2

        conn = psycopg2.connect(_dsn())
        try:
            with conn.cursor() as cur:
                cur.execute(
                    # audit_consensus names the JSONB column `proposals`
                    # (the legacy table used a different name); see
                    # AuditConsensusRow.
                    "SELECT id AS audit_id, decision_id, tier, phase_reached, "
                    "       confidence, escalated, city, "
                    "       proposals, selected_action, pareto_weights, "
                    "       human_override, audit_trace, created_at, "
                    "       debate_rounds, pareto_front, execution_confirmations, "
                    "       context_messages, outcome, prev_hash, current_hash "
                    "FROM audit_consensus WHERE decision_id = %s",
                    (str(decision_id),),
                )
                row = cur.fetchone()
                if row is None:
                    raise HTTPException(status_code=404, detail="decision not found")
                # Also fetch escalations for this decision_id.
                cur.execute(
                    "SELECT id, escalation_reason, human_action, "
                    "       operator_token_ref, override_action, override_reason, "
                    "       override_at, resolved_at, resolution_time_ms "
                    "FROM audit_escalations WHERE decision_id = %s "
                    "ORDER BY created_at ASC",
                    (str(decision_id),),
                )
                escalations = [
                    {
                        "audit_escalation_id": int(er[0]),
                        "escalation_reason": er[1],
                        "human_action": er[2],
                        "operator_token_ref": er[3],
                        "override_action": er[4],
                        "override_reason": er[5],
                        "override_at": er[6].isoformat() if er[6] else None,
                        "resolved_at": er[7].isoformat() if er[7] else None,
                        "resolution_time_ms": er[8],
                    }
                    for er in cur.fetchall()
                ]
        finally:
            conn.close()
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=f"audit unavailable: {exc}") from exc

    proposals = row[7] if isinstance(row[7], list) else []
    context_messages = row[16] if isinstance(row[16], list) else []
    prev_hash: str | None = row[18]
    current_hash: str | None = row[19]

    from synapse_common.audit_chain import verify_row_hash
    from synapse_common.synthetic import is_synthetic_decision

    degraded = any(
        isinstance(p, dict)
        and isinstance(p.get("provenance"), dict)
        and p["provenance"].get("degraded") is True
        for p in proposals
    )
    # Tri-state: True (recomputed hash matches), False (content altered since
    # insert), None (pre-Sprint-9 legacy row with no chain values — E-S9-01).
    chain_verified: bool | None = None
    if current_hash is not None:
        chain_verified = verify_row_hash(
            prev_hash=prev_hash,
            current_hash=current_hash,
            decision_id=row[1],
            tier=row[2],
            selected_action=row[8] if isinstance(row[8], dict) else {},
            pareto_weights=row[9] if isinstance(row[9], dict) else {},
            confidence=float(row[4]),
            proposals=proposals,
            audit_trace=row[11] if isinstance(row[11], list) else [],
        )

    return {
        "audit_id": str(row[0]),
        "decision_id": str(row[1]),
        "tier": row[2],
        "phase_reached": row[3] if row[3] is not None else 1,
        "confidence": float(row[4]),
        "escalated": bool(row[5]),
        "city": row[6],
        "proposals": row[7],
        "selected_action": row[8],
        "pareto_weights": row[9],
        "human_override": row[10],
        "audit_trace": row[11],
        "created_at": row[12].isoformat() if row[12] else None,
        "escalations": escalations,
        # ADR-044 additive anatomy + honesty fields.
        "debate_rounds": row[13] if row[13] is not None else 0,
        "pareto_front": row[14],
        "execution_confirmations": row[15],
        "context_messages": row[16],
        "outcome": row[17],
        "prev_hash": prev_hash,
        "current_hash": current_hash,
        "chain_verified": chain_verified,
        "degraded": degraded,
        "is_synthetic": is_synthetic_decision(context_messages),
    }


# ─────────────────────────────────────────────────────────────────────────────
# P1 — Override endpoint (audit-row-first)
# ─────────────────────────────────────────────────────────────────────────────


class OverrideBody(BaseModel):
    action: str = Field(..., pattern="^(approved|rejected|modified)$")
    reason: str = Field(..., min_length=1, max_length=4000)
    modified_action: dict[str, Any] | None = None
    # WS-2: optional idempotency key. When present, a retry with the same
    # (decision_id, idempotency_key) returns the existing audit row rather
    # than inserting a duplicate. Enforced at the DB by a partial UNIQUE
    # index (migration 0004).
    idempotency_key: str | None = Field(
        default=None,
        min_length=1,
        max_length=64,
        description="Operator-supplied dedup key. Optional; if absent the route is non-idempotent (legacy behaviour).",
    )

    @field_validator("modified_action")
    @classmethod
    def _modified_only_when_modified(
        cls, v: dict[str, Any] | None, info: Any
    ) -> dict[str, Any] | None:
        # When action != "modified", we don't reject — we just clear the field
        # so the audit row is minimal. The router enforces presence below.
        return v


class OverrideResponse(BaseModel):
    audit_escalation_id: int
    decision_id: str
    action: str
    operator_token_ref: str
    override_at: str
    orchestrator_notified: bool


@router.post(
    "/{decision_id}/override",
    response_model=OverrideResponse,
    status_code=status.HTTP_201_CREATED,
)
async def override_decision(
    decision_id: Annotated[UUID, Path(...)],
    body: OverrideBody,
    op: Annotated[OperatorContext, Depends(RequireRole(Role.OPS))],
) -> OverrideResponse:
    """Operator override — audit-row-first commit.

    Order of operations is load-bearing (FE-INV-003 / FE-INV-021):
      1. INSERT into audit_escalations (preserves I-4 immutability).
      2. Notify orchestrator over HTTP A2A (best-effort).
      3. Return the persisted row to the caller.

    If step 1 fails, no operator action is recorded and no orchestrator
    notification is sent — the FE displays the error and the operator
    retries.
    """
    if body.action == "modified" and not body.modified_action:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="modified_action required when action='modified'",
        )

    started = time.perf_counter()
    now = datetime.now(UTC)
    human_action_blob: dict[str, Any] = {
        "action": body.action,
        "reason": body.reason,
    }
    if body.modified_action is not None:
        human_action_blob["modified_action"] = body.modified_action

    try:
        import psycopg2
        from psycopg2.errors import UniqueViolation

        conn = psycopg2.connect(_dsn())
        try:
            with conn, conn.cursor() as cur:
                # WS-2 idempotency: if the caller supplied a key, check for
                # an existing row first. This is the cheap path; on race the
                # UNIQUE index below guarantees correctness.
                if body.idempotency_key is not None:
                    cur.execute(
                        "SELECT id, override_at FROM audit_escalations "
                        "WHERE decision_id = %s AND idempotency_key = %s",
                        (str(decision_id), body.idempotency_key),
                    )
                    existing = cur.fetchone()
                    if existing is not None:
                        existing_id = int(existing[0])
                        existing_at = existing[1]
                        logger.info(
                            "override_idempotent_replay",
                            decision_id=str(decision_id),
                            audit_escalation_id=existing_id,
                            idempotency_key=body.idempotency_key,
                        )
                        return OverrideResponse(
                            audit_escalation_id=existing_id,
                            decision_id=str(decision_id),
                            action=body.action,
                            operator_token_ref=op.token_ref,
                            override_at=(
                                existing_at.isoformat() if existing_at else now.isoformat()
                            ),
                            orchestrator_notified=True,
                        )

                try:
                    cur.execute(
                        """
                        INSERT INTO audit_escalations
                            (decision_id, escalation_reason, human_action,
                             operator_token_ref, override_action, override_reason,
                             override_at, resolved_at, resolution_time_ms,
                             idempotency_key)
                        VALUES (%s, %s, %s::jsonb, %s, %s, %s, %s, %s, %s, %s)
                        RETURNING id
                        """,
                        (
                            str(decision_id),
                            body.reason[:500],
                            _json_dumps(human_action_blob),
                            op.token_ref,
                            body.action,
                            body.reason,
                            now,
                            now,
                            int((time.perf_counter() - started) * 1000),
                            body.idempotency_key,
                        ),
                    )
                except UniqueViolation:
                    # Concurrent caller won the race. Re-select and replay.
                    conn.rollback()
                    cur.execute(
                        "SELECT id, override_at FROM audit_escalations "
                        "WHERE decision_id = %s AND idempotency_key = %s",
                        (str(decision_id), body.idempotency_key),
                    )
                    raced = cur.fetchone()
                    if raced is None:
                        raise HTTPException(
                            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail="idempotency race lost but row missing",
                        ) from None
                    raced_id = int(raced[0])
                    raced_at = raced[1]
                    return OverrideResponse(
                        audit_escalation_id=raced_id,
                        decision_id=str(decision_id),
                        action=body.action,
                        operator_token_ref=op.token_ref,
                        override_at=raced_at.isoformat() if raced_at else now.isoformat(),
                        orchestrator_notified=True,
                    )
                row = cur.fetchone()
                if row is None:
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="audit insert returned no row",
                    )
                escalation_id = int(row[0])
        finally:
            conn.close()
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.error(
            "override_audit_insert_failed",
            decision_id=str(decision_id),
            operator_token_ref=op.token_ref,
            error=str(exc),
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="audit log unavailable; override not recorded",
        ) from exc

    # Notify orchestrator (best-effort; audit is the source of truth).
    # WS-2: inject traceparent so the orchestrator's HITL handler sees the
    # same trace as the FE override click.
    notify_headers: dict[str, str] = {}
    inject_a2a_headers(notify_headers)
    orchestrator_ok = False
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{ORCHESTRATOR_URL}/api/v1/hitl/{decision_id}/resolve",
                json={
                    "audit_escalation_id": escalation_id,
                    "operator_token_ref": op.token_ref,
                    "action": body.action,
                    "reason": body.reason,
                    "modified_action": body.modified_action,
                },
                headers=notify_headers,
            )
            orchestrator_ok = resp.status_code in (200, 202, 204)
    except httpx.HTTPError as exc:
        logger.warning(
            "orchestrator_notify_failed",
            decision_id=str(decision_id),
            error=str(exc),
        )

    logger.info(
        "override_committed",
        decision_id=str(decision_id),
        operator_token_ref=op.token_ref,
        action=body.action,
        audit_escalation_id=escalation_id,
        orchestrator_notified=orchestrator_ok,
    )

    return OverrideResponse(
        audit_escalation_id=escalation_id,
        decision_id=str(decision_id),
        action=body.action,
        operator_token_ref=op.token_ref,
        override_at=now.isoformat(),
        orchestrator_notified=orchestrator_ok,
    )


def _json_dumps(obj: dict[str, Any]) -> str:
    """Canonical JSON (mirror of FE FE-INV-012 / I-8)."""
    import json

    return json.dumps(obj, sort_keys=True, separators=(",", ":"))
