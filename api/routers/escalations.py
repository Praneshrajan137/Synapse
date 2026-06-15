"""Escalations analytics router (Sprint 19, ADR-047).

``GET /api/v1/escalations/analytics`` aggregates the HITL escalation pressure
over a window for the Standing Watch surface: how many escalations, how the
operator resolved them, how fast, and the dominant reasons. It is a pure SQL
read over the existing append-only ``audit_escalations`` table (joined to
``audit_consensus`` for the city dimension) — no new write path, no new topic.

Read-only (VIEWER): an escalation-pressure read is exactly what the operators
who staff the wall need to see.
"""

from __future__ import annotations

import os
import time
from typing import Annotated, Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from synapse_common.auth import OperatorContext

from api.middleware.jwt import CurrentOperator

logger = structlog.get_logger(__name__)
router = APIRouter()

_VALID_CITIES = {"bengaluru", "mumbai"}


def _dsn() -> str:
    """Resolve the audit Postgres DSN. Fail-fast — never embed a credential.

    Same contract as ``api.routers.decisions._dsn``: the DSN comes from the
    environment (Secret Manager / SOPS in prod, ``.env`` in dev); an unset DSN
    is a 503 misconfiguration, not something to paper over with a baked-in
    password.
    """
    dsn = os.environ.get("POSTGRES_DSN")
    if not dsn:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="POSTGRES_DSN not configured",
        )
    return dsn


@router.get("/analytics")
async def escalation_analytics(
    op: Annotated[OperatorContext, Depends(CurrentOperator)],
    window_hours: int = 24,
    city: str | None = None,
) -> dict[str, Any]:
    """Escalation pressure + resolution analytics over the last ``window_hours``."""
    if window_hours < 1 or window_hours > 720:
        raise HTTPException(status_code=422, detail="window_hours must be in [1, 720]")
    if city is not None and city not in _VALID_CITIES:
        raise HTTPException(status_code=422, detail="invalid city")

    try:
        import psycopg2

        conn = psycopg2.connect(_dsn())
        try:
            with conn.cursor() as cur:
                # `c.city` is on audit_consensus (audit_escalations has no city
                # column); LEFT JOIN so escalations whose decision row is absent
                # still count. The window filters on the escalation row's own
                # created_at.
                where = ["e.created_at >= now() - make_interval(hours => %s)"]
                params: list[Any] = [window_hours]
                if city is not None:
                    where.append("c.city = %s")
                    params.append(city)
                where_sql = " AND ".join(where)

                cur.execute(
                    f"""
                    SELECT
                        count(*) AS total,
                        count(*) FILTER (WHERE e.override_action IS NOT NULL) AS overridden,
                        count(*) FILTER (WHERE e.override_action = 'approved') AS approved,
                        count(*) FILTER (WHERE e.override_action = 'rejected') AS rejected,
                        count(*) FILTER (WHERE e.override_action = 'modified') AS modified,
                        percentile_cont(0.5) WITHIN GROUP (ORDER BY e.resolution_time_ms)
                            AS p50_ms,
                        percentile_cont(0.9) WITHIN GROUP (ORDER BY e.resolution_time_ms)
                            AS p90_ms,
                        max(e.resolution_time_ms) AS max_ms
                    FROM audit_escalations e
                    LEFT JOIN audit_consensus c ON e.decision_id = c.decision_id
                    WHERE {where_sql}
                    """,
                    tuple(params),
                )
                agg = cur.fetchone()

                cur.execute(
                    f"""
                    SELECT e.escalation_reason, count(*) AS n
                    FROM audit_escalations e
                    LEFT JOIN audit_consensus c ON e.decision_id = c.decision_id
                    WHERE {where_sql} AND e.escalation_reason IS NOT NULL
                    GROUP BY e.escalation_reason
                    ORDER BY n DESC, e.escalation_reason ASC
                    LIMIT 8
                    """,
                    tuple(params),
                )
                top_reasons = [{"reason": r[0], "count": int(r[1])} for r in cur.fetchall()]
        finally:
            conn.close()
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=f"audit unavailable: {exc}") from exc

    total = int(agg[0]) if agg and agg[0] is not None else 0
    overridden = int(agg[1]) if agg and agg[1] is not None else 0
    approved = int(agg[2]) if agg and agg[2] is not None else 0
    rejected = int(agg[3]) if agg and agg[3] is not None else 0
    modified = int(agg[4]) if agg and agg[4] is not None else 0

    def _ms(value: Any) -> float | None:
        return None if value is None else float(value)

    return {
        "window_hours": window_hours,
        "city": city,
        "total": total,
        "overridden": overridden,
        "pending": max(0, total - overridden),
        "override_actions": {
            "approved": approved,
            "rejected": rejected,
            "modified": modified,
            "none": max(0, total - approved - rejected - modified),
        },
        "resolution_time_ms": {
            "p50": _ms(agg[5]) if agg else None,
            "p90": _ms(agg[6]) if agg else None,
            "max": int(agg[7]) if agg and agg[7] is not None else None,
        },
        "top_reasons": top_reasons,
        "ts": time.time(),
    }
