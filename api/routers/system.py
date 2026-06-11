"""System posture router (ADR-044).

``GET /api/v1/system/posture`` proxies the orchestrator's degradation
posture (brownout level per city + circuit-breaker states) to the
authenticated frontend. The FE polls this every ~15s to drive the
DegradedBanner — the honesty channel's system-level signal.

Polled, not pushed: posture changes on the order of seconds-to-minutes,
and pushing it would require either a new Kafka topic (frozen set,
Sprint 1) or abusing the ``metric`` channel. A 15s poll against a
sub-millisecond in-process read is honest engineering (ADR-044 D4).
"""

from __future__ import annotations

import os
from typing import Annotated, Any

import httpx
import structlog
from fastapi import APIRouter, Depends, HTTPException
from synapse_common.auth import OperatorContext

from api.middleware.jwt import CurrentOperator

logger = structlog.get_logger(__name__)
router = APIRouter()

ORCHESTRATOR_URL = os.environ.get("SYNAPSE_ORCHESTRATOR_URL", "http://orchestrator:8085")


@router.get("/posture")
async def system_posture(
    op: Annotated[OperatorContext, Depends(CurrentOperator)],
) -> dict[str, Any]:
    """Read-only degradation posture (VIEWER role suffices)."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{ORCHESTRATOR_URL}/api/v1/status/posture")
    except httpx.HTTPError as exc:
        # An unreachable orchestrator IS a degraded posture, but inventing
        # one here would fabricate brownout/breaker detail the gateway does
        # not have. 503 with an honest reason; the FE banner treats a posture
        # fetch failure as "posture unknown" (which it renders degraded-side).
        raise HTTPException(
            status_code=503, detail=f"orchestrator unreachable: {exc}"
        ) from exc
    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)
    payload: dict[str, Any] = resp.json()
    return payload
