"""Decisions router — proxies to orchestrator + queries audit trail."""

from __future__ import annotations

import os
from typing import Any

import structlog
from fastapi import APIRouter, HTTPException

logger = structlog.get_logger(__name__)
router = APIRouter()

ORCHESTRATOR_URL = os.environ.get("SYNAPSE_ORCHESTRATOR_URL", "http://orchestrator:8085")


@router.post("/")
async def trigger_decision(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        import requests

        resp = requests.post(f"{ORCHESTRATOR_URL}/api/v1/decisions", json=payload, timeout=30)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=f"orchestrator unreachable: {exc}") from exc
    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)
    return resp.json()


@router.get("/recent")
async def recent_decisions(limit: int = 20) -> dict[str, Any]:
    try:
        import psycopg2

        dsn = os.environ.get(
            "POSTGRES_DSN",
            "postgresql://synapse:synapse_audit_2026@postgres:5432/synapse_audit",
        )
        conn = psycopg2.connect(dsn)
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT audit_id, decision_id, tier, created_at "
                    "FROM audit_decisions ORDER BY created_at DESC LIMIT %s",
                    (limit,),
                )
                rows = [
                    {
                        "audit_id": str(r[0]),
                        "decision_id": str(r[1]),
                        "tier": r[2],
                        "created_at": r[3].isoformat() if r[3] else None,
                    }
                    for r in cur.fetchall()
                ]
        finally:
            conn.close()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=f"audit unavailable: {exc}") from exc
    return {"decisions": rows, "count": len(rows)}
