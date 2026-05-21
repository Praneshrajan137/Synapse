"""Decisions router — proxies to orchestrator + queries audit trail.

Sprint 7 hardening:
    * No more ``requests``: orchestrator hop uses the bulkheaded
      ``httpx.AsyncClient`` from ``synapse_common.clients``.
    * No more ``psycopg2.connect`` in async handlers: audit reads use the
      ``asyncpg`` pool created in the API lifespan.
    * Idempotency-Key support on POST.
    * Trace context propagated to the orchestrator via W3C ``traceparent``.
"""

from __future__ import annotations

from typing import Any

import httpx
import structlog
from fastapi import APIRouter, HTTPException, Request
from synapse_common.idempotency import idempotent

logger = structlog.get_logger(__name__)
router = APIRouter()

ORCHESTRATOR_PATH = "/api/v1/decisions"


def _trace_headers() -> dict[str, str]:
    try:
        from opentelemetry.propagate import inject
    except Exception:  # noqa: BLE001
        return {}
    carrier: dict[str, str] = {}
    try:
        inject(carrier)
    except Exception as exc:  # noqa: BLE001
        logger.debug("trace_inject_failed", error=str(exc))
        return {}
    return carrier


@router.post("/")
@idempotent(scope="decisions")
async def trigger_decision(payload: dict[str, Any], request: Request) -> dict[str, Any]:
    """Forward a decision request to the orchestrator over the bulkhead client."""
    client: httpx.AsyncClient | None = getattr(request.app.state, "orchestrator_client", None)
    base_url: str = getattr(request.app.state, "orchestrator_url", "http://orchestrator:8085")
    if client is None:
        raise HTTPException(status_code=503, detail="orchestrator client not initialized")

    headers = {"Content-Type": "application/json"}
    headers.update(_trace_headers())
    forwarded_idem = request.headers.get("Idempotency-Key")
    if forwarded_idem:
        headers["Idempotency-Key"] = forwarded_idem

    try:
        resp = await client.post(
            f"{base_url}{ORCHESTRATOR_PATH}",
            json=payload,
            headers=headers,
        )
    except httpx.TransportError as exc:
        raise HTTPException(status_code=503, detail=f"orchestrator unreachable: {exc}") from exc
    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)
    return resp.json()  # type: ignore[no-any-return]


@router.get("/recent")
async def recent_decisions(request: Request, limit: int = 20) -> dict[str, Any]:
    """List recent audit-trail decisions; degrades gracefully when Postgres is down."""
    if limit < 1 or limit > 500:
        raise HTTPException(status_code=400, detail="limit must be in [1, 500]")

    pool: Any = getattr(request.app.state, "postgres_pool", None)
    if pool is None:
        raise HTTPException(status_code=503, detail="audit unavailable: postgres pool not ready")

    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT audit_id, decision_id, tier, created_at "
                "FROM audit_decisions ORDER BY created_at DESC LIMIT $1",
                limit,
            )
    except Exception as exc:  # noqa: BLE001
        logger.warning("audit_query_failed", error=str(exc))
        raise HTTPException(status_code=503, detail=f"audit unavailable: {exc}") from exc

    return {
        "decisions": [
            {
                "audit_id": str(row["audit_id"]),
                "decision_id": str(row["decision_id"]),
                "tier": row["tier"],
                "created_at": row["created_at"].isoformat() if row["created_at"] else None,
            }
            for row in rows
        ],
        "count": len(rows),
    }
