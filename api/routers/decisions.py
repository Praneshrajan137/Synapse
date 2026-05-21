"""Decisions router — proxies to orchestrator + queries audit trail.

Sprint-7 hardening (WS-1 §1, WS-2 §2):
- ``requests.post(...)`` (blocking) → shared ``httpx.AsyncClient`` from
  ``synapse_common.clients`` (bulkhead) with W3C ``traceparent`` injected.
- ``psycopg2.connect(...)`` (blocking) → ``async_sessionmaker`` session
  from ``app.state.session_factory`` (asyncpg engine wired in
  ``api.main``).
- Idempotency-Key required on ``POST /``.
"""

from __future__ import annotations

import os
from typing import Any
from uuid import UUID

import httpx
import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import text
from synapse_common.clients import get_client
from synapse_common.idempotency import (
    enforce_idempotency,
    record_idempotent_response,
)
from synapse_common.tracing import inject_a2a_headers

logger = structlog.get_logger(__name__)
router = APIRouter()

ORCHESTRATOR_URL = os.environ.get("SYNAPSE_ORCHESTRATOR_URL", "http://orchestrator:8085")


@router.post("/")
async def trigger_decision(
    request: Request,
    payload: dict[str, Any],
    idem: tuple[str, str] | None = Depends(enforce_idempotency),
) -> dict[str, Any]:
    if idem is None:
        cached = request.state.idempotent_response
        return cached["response"]  # type: ignore[no-any-return]

    idempotency_key, request_hash = idem
    headers: dict[str, str] = {
        "Content-Type": "application/json",
        "Idempotency-Key": idempotency_key,
    }
    inject_a2a_headers(headers)
    client = await get_client("orchestrator")
    try:
        resp = await client.post(
            f"{ORCHESTRATOR_URL}/api/v1/decisions",
            json=payload,
            headers=headers,
            timeout=30.0,
        )
    except httpx.TransportError as exc:
        raise HTTPException(status_code=503, detail=f"orchestrator unreachable: {exc}") from exc
    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)
    body: dict[str, Any] = resp.json()
    await record_idempotent_response(
        idempotency_key=idempotency_key,
        request_hash=request_hash,
        response_body=body,
        status_code=200,
    )
    return body


@router.get("/recent")
async def recent_decisions(request: Request, limit: int = 20) -> dict[str, Any]:
    session_factory = getattr(request.app.state, "session_factory", None)
    if session_factory is None:
        raise HTTPException(status_code=503, detail="audit unavailable: session not initialised")
    try:
        async with session_factory() as session:
            result = await session.execute(
                text(
                    "SELECT decision_id, tier, created_at "
                    "FROM audit_consensus "
                    "ORDER BY created_at DESC "
                    "LIMIT :limit"
                ),
                {"limit": int(limit)},
            )
            rows = [
                {
                    "decision_id": _stringify(row[0]),
                    "tier": row[1],
                    "created_at": row[2].isoformat() if row[2] is not None else None,
                }
                for row in result.fetchall()
            ]
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=f"audit unavailable: {exc}") from exc
    return {"decisions": rows, "count": len(rows)}


def _stringify(value: Any) -> str:
    if isinstance(value, UUID):
        return str(value)
    return str(value) if value is not None else ""
