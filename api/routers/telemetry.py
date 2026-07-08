"""FE Web Vitals + structured-log sink (P4.B24).

The frontend posts `web_vitals`, `error`, and `audit_view` events here.
Body is bounded to 16KB; only allow-listed keys are kept; structlog
forwards the result to Loki / stdout (FE-INV-030).
"""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Body, HTTPException, Response, status

logger = structlog.get_logger(__name__)
router = APIRouter()

MAX_BYTES = 16 * 1024
ALLOWED_FIELDS = {
    "kind",
    "metric",
    "value",
    "id",
    "rating",
    "path",
    "ts",
    "name",
    "message",
    "stack",
    "component_stack",
    "trace_id",
    "build_sha",
    # Schema-violation detail (FE http-client emits these; kept in lock-step
    # with the frontend whitelist in frontend/src/lib/log.ts). Safe metadata
    # only — never a raw payload or field value.
    "error",
    "schemaId",
    "issueCount",
    "paths",
}
ALLOWED_KIND = {"web_vitals", "error", "audit_view", "demo_event"}


@router.post("/telemetry", status_code=status.HTTP_202_ACCEPTED)
async def telemetry(payload: dict[str, Any] = Body(default={})) -> dict[str, str]:
    raw = repr(payload).encode("utf-8")
    if len(raw) > MAX_BYTES:
        raise HTTPException(status_code=413, detail="telemetry payload too large")
    kind = payload.get("kind")
    if kind not in ALLOWED_KIND:
        raise HTTPException(status_code=422, detail=f"unknown telemetry kind: {kind!r}")
    sanitized: dict[str, Any] = {k: v for k, v in payload.items() if k in ALLOWED_FIELDS}
    if "stack" in sanitized and isinstance(sanitized["stack"], str):
        sanitized["stack"] = sanitized["stack"][:2_000]
    if "component_stack" in sanitized and isinstance(sanitized["component_stack"], str):
        sanitized["component_stack"] = sanitized["component_stack"][:2_000]
    logger.info("fe_telemetry", **sanitized)
    return {"status": "accepted"}


@router.post("/csp-report", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def csp_report(payload: dict[str, Any] = Body(default={})) -> Response:
    """Receives CSP violation reports referenced by frontend/nginx.conf."""
    logger.warning("csp_violation", report=payload)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
