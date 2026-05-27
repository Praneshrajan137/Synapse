"""Steering audit endpoint (WS-5).

The Atlas Console "Steering" surface lets operators adjust Pareto objective
weights and per-tier confidence thresholds. Until WS-5 these mutations
lived only in localStorage (Zustand persist) and were invisible to the
audit trail — FE-INV-033 was aspirational, not enforced.

This router accepts one POST per operator change and writes an
`audit_steering` row (INSERT-only, mirrors I-4 immutability). The frontend
posts the change BEFORE mutating local state; if the audit insert fails,
the FE shows an error toast and reverts.

The route is guarded by ``Role.OPS`` — viewers see steering values but
cannot change them.
"""

from __future__ import annotations

import os
import time
from datetime import UTC, datetime
from typing import Annotated, Literal

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from api.middleware.jwt import RequireRole
from synapse_common.auth import OperatorContext, Role

logger = structlog.get_logger(__name__)
router = APIRouter()

POSTGRES_DSN_DEFAULT = "postgresql://synapse_app:synapse_app_2026@postgres:5432/synapse_audit"


def _dsn() -> str:
    return os.environ.get("POSTGRES_DSN", POSTGRES_DSN_DEFAULT)


SteeringAction = Literal["set_pareto_weight", "set_tier_threshold", "reset"]


class SteeringChange(BaseModel):
    action: SteeringAction
    target: str | None = Field(
        default=None,
        max_length=64,
        description="The knob being changed — e.g. 'cost' for Pareto weights "
        "or 'tier_2' for tier thresholds. NULL for action='reset'.",
    )
    value: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="New numeric value in [0,1]. NULL for action='reset'.",
    )
    idempotency_key: str | None = Field(
        default=None,
        min_length=1,
        max_length=64,
        description="Optional replay-safe key. When present, a retry with "
        "the same key collapses to the existing row.",
    )


class SteeringResponse(BaseModel):
    steering_id: str
    operator_token_ref: str
    action: SteeringAction
    target: str | None
    value: float | None
    created_at: str


@router.post(
    "/",
    response_model=SteeringResponse,
    status_code=status.HTTP_201_CREATED,
)
async def submit_steering(
    body: SteeringChange,
    op: Annotated[OperatorContext, Depends(RequireRole(Role.OPS))],
) -> SteeringResponse:
    """Record an operator steering change in the audit trail."""
    # action-specific validation
    if body.action in ("set_pareto_weight", "set_tier_threshold"):
        if body.target is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"target required when action='{body.action}'",
            )
        if body.value is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"value required when action='{body.action}'",
            )
    elif body.action == "reset":
        if body.target is not None or body.value is not None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="reset takes no target/value",
            )

    if body.action == "set_pareto_weight" and body.target not in {
        "cost",
        "time",
        "sustainability",
        "fairness",
    }:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"unknown pareto dimension: {body.target!r}",
        )
    if body.action == "set_tier_threshold" and body.target not in {
        "tier_2",
        "tier_3",
        "tier_4",
    }:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"unknown tier: {body.target!r}",
        )

    started = time.perf_counter()
    now = datetime.now(UTC)

    try:
        import psycopg2
        from psycopg2.errors import UniqueViolation

        conn = psycopg2.connect(_dsn())
        try:
            with conn, conn.cursor() as cur:
                # Idempotent replay path.
                if body.idempotency_key is not None:
                    cur.execute(
                        "SELECT id, created_at FROM audit_steering "
                        "WHERE operator_token_ref = %s AND idempotency_key = %s",
                        (op.token_ref, body.idempotency_key),
                    )
                    existing = cur.fetchone()
                    if existing is not None:
                        return SteeringResponse(
                            steering_id=str(existing[0]),
                            operator_token_ref=op.token_ref,
                            action=body.action,
                            target=body.target,
                            value=body.value,
                            created_at=existing[1].isoformat(),
                        )

                try:
                    cur.execute(
                        """
                        INSERT INTO audit_steering
                            (operator_token_ref, action, target, value,
                             idempotency_key, created_at)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        RETURNING id, created_at
                        """,
                        (
                            op.token_ref,
                            body.action,
                            body.target,
                            body.value,
                            body.idempotency_key,
                            now,
                        ),
                    )
                except UniqueViolation:
                    conn.rollback()
                    cur.execute(
                        "SELECT id, created_at FROM audit_steering "
                        "WHERE operator_token_ref = %s AND idempotency_key = %s",
                        (op.token_ref, body.idempotency_key),
                    )
                    raced = cur.fetchone()
                    if raced is None:
                        raise HTTPException(
                            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail="idempotency race lost but row missing",
                        ) from None
                    return SteeringResponse(
                        steering_id=str(raced[0]),
                        operator_token_ref=op.token_ref,
                        action=body.action,
                        target=body.target,
                        value=body.value,
                        created_at=raced[1].isoformat(),
                    )
                row = cur.fetchone()
                if row is None:
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="audit insert returned no row",
                    )
                steering_id = str(row[0])
                created_at = row[1]
        finally:
            conn.close()
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.error(
            "steering_audit_insert_failed",
            operator_token_ref=op.token_ref,
            action=body.action,
            error=str(exc),
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="audit log unavailable; steering change not recorded",
        ) from exc

    logger.info(
        "steering_recorded",
        steering_id=steering_id,
        operator_token_ref=op.token_ref,
        action=body.action,
        target=body.target,
        value=body.value,
        latency_ms=int((time.perf_counter() - started) * 1000),
    )
    return SteeringResponse(
        steering_id=steering_id,
        operator_token_ref=op.token_ref,
        action=body.action,
        target=body.target,
        value=body.value,
        created_at=created_at.isoformat(),
    )
