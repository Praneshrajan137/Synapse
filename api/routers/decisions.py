"""Decisions router — proxies to orchestrator + queries audit trail.

Endpoints
---------
- ``POST /``          — proxy to orchestrator decision endpoint.
- ``GET  /recent``    — recent rows from the legacy ``audit_decisions`` table.
- ``GET  /{decision_id}`` — full ``audit_consensus`` row (B2 — plan §11).

The two GET endpoints intentionally read from different tables. ``/recent``
keeps the cheap ``audit_decisions`` summary read so the dashboard table can
page quickly; the deep-fetch returns the much richer ``audit_consensus``
row needed for Decision Trace / Audit Vault drawers.
"""

from __future__ import annotations

import os
import re
from typing import Any

import structlog
from fastapi import APIRouter, HTTPException, Path

logger = structlog.get_logger(__name__)
router = APIRouter()

ORCHESTRATOR_URL = os.environ.get("SYNAPSE_ORCHESTRATOR_URL", "http://orchestrator:8085")

# RFC 4122 UUID — guard the path param. Fail fast on garbage so we don't burn
# a database connection on a bad request id.
_UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$",
)


def _audit_dsn() -> str:
    return os.environ.get(
        "POSTGRES_DSN",
        "postgresql://synapse:synapse_audit_2026@postgres:5432/synapse_audit",
    )


@router.post("/")
async def trigger_decision(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        import requests

        resp = requests.post(
            f"{ORCHESTRATOR_URL}/api/v1/decisions", json=payload, timeout=30
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=f"orchestrator unreachable: {exc}") from exc
    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)
    return resp.json()


def _decode_cursor(cursor: str | None) -> tuple[str, str] | None:
    """Decode an opaque cursor `<created_at_iso>:<audit_id>` for keyset pagination.

    Returns ``(created_at_iso, audit_id)`` or ``None``. Raises 400 on malformed
    cursors so a poisoned client can't silently fall off the page.
    """
    if not cursor:
        return None
    try:
        # Cursors are base64url-encoded to keep them URL-safe and to discourage
        # clients from poking at the internals.
        import base64

        raw = base64.urlsafe_b64decode(cursor.encode("ascii") + b"==").decode("ascii")
        ts, aid = raw.split("|", 1)
        # Cheap sanity — both halves must be non-empty.
        if not ts or not aid:
            raise ValueError("empty halves")
        return ts, aid
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"invalid cursor: {exc}") from exc


def _encode_cursor(created_at_iso: str, audit_id: str) -> str:
    import base64

    return (
        base64.urlsafe_b64encode(f"{created_at_iso}|{audit_id}".encode("ascii"))
        .rstrip(b"=")
        .decode("ascii")
    )


@router.get("/recent")
async def recent_decisions(
    limit: int = 20,
    cursor: str | None = None,
    tier: str | None = None,
    escalated: bool | None = None,
) -> dict[str, Any]:
    """Recent decisions for the Decision Trace table.

    Keyset pagination over ``(created_at DESC, audit_id DESC)``. The
    ``cursor`` is opaque (base64url) so clients don't depend on the
    internal layout. ``next_cursor`` is null when fewer than ``limit``
    rows return.

    Filters (S3 — Decision Trace surface):
      * ``tier`` — exactly one of ``tier_1``..``tier_4``.
      * ``escalated`` — ``true``/``false`` to include only escalated rows.
    """
    if not 1 <= limit <= 200:
        raise HTTPException(status_code=400, detail="limit must be 1..200")
    if tier is not None and tier not in {"tier_1", "tier_2", "tier_3", "tier_4"}:
        raise HTTPException(status_code=400, detail="tier must be one of tier_1..tier_4")

    cursor_pair = _decode_cursor(cursor)

    sql = (
        "SELECT audit_id, decision_id, tier, created_at "
        "FROM audit_decisions WHERE TRUE"
    )
    params: list[Any] = []
    if cursor_pair is not None:
        sql += " AND (created_at, audit_id) < (%s, %s)"
        params.extend(cursor_pair)
    if tier is not None:
        sql += " AND tier = %s"
        params.append(tier)
    if escalated is not None:
        sql += " AND escalated = %s"
        params.append(escalated)
    # Fetch one extra to know whether there's a next page.
    sql += " ORDER BY created_at DESC, audit_id DESC LIMIT %s"
    params.append(limit + 1)

    try:
        import psycopg2

        conn = psycopg2.connect(_audit_dsn())
        try:
            with conn.cursor() as cur:
                cur.execute(sql, tuple(params))
                fetched = cur.fetchall()
        finally:
            conn.close()
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=f"audit unavailable: {exc}") from exc

    has_more = len(fetched) > limit
    rows_raw = fetched[:limit]
    rows = [
        {
            "audit_id": str(r[0]),
            "decision_id": str(r[1]),
            "tier": r[2],
            "created_at": r[3].isoformat() if r[3] else None,
        }
        for r in rows_raw
    ]
    next_cursor: str | None = None
    if has_more and rows_raw:
        last = rows_raw[-1]
        last_created = last[3].isoformat() if last[3] else ""
        next_cursor = _encode_cursor(last_created, str(last[0]))

    return {
        "decisions": rows,
        "count": len(rows),
        "next_cursor": next_cursor,
    }


@router.get("/{decision_id}")
async def get_decision(
    decision_id: str = Path(..., description="UUID of the decision (audit_consensus.decision_id)"),
) -> dict[str, Any]:
    """Deep-fetch one row from ``audit_consensus`` for the Decision Trace drawer.

    B2 — plan §11. Returns the full LangGraph trace, debate rounds, Pareto
    front, audit_trace, and override metadata. JSONB columns deserialise to
    native Python objects via psycopg2's default JSONB adapter.

    Errors:
      400 — malformed UUID.
      404 — no such decision.
      503 — audit DB unreachable.
    """
    if not _UUID_RE.match(decision_id):
        raise HTTPException(status_code=400, detail="decision_id must be a UUID")

    try:
        import psycopg2
        from psycopg2.extras import RealDictCursor

        conn = psycopg2.connect(_audit_dsn())
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT id::text                     AS id,
                           decision_id::text            AS decision_id,
                           timestamp,
                           tier,
                           phase_reached,
                           proposals,
                           selected_action,
                           pareto_weights,
                           confidence,
                           debate_rounds,
                           escalated,
                           human_override,
                           execution_confirmations,
                           context_messages,
                           audit_trace,
                           pareto_front,
                           outcome,
                           created_at
                      FROM audit_consensus
                     WHERE decision_id = %s
                    """,
                    (decision_id,),
                )
                row = cur.fetchone()
        finally:
            conn.close()
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.warning("audit_consensus_fetch_failed", decision_id=decision_id, error=str(exc))
        raise HTTPException(status_code=503, detail=f"audit unavailable: {exc}") from exc

    if row is None:
        raise HTTPException(status_code=404, detail=f"no decision with id {decision_id}")

    # Datetime → ISO 8601 (Z-suffixed, UTC). Matches the orders router style
    # so frontend code parses every server timestamp with one helper.
    for key in ("timestamp", "created_at"):
        if row.get(key) is not None:
            row[key] = row[key].isoformat().replace("+00:00", "Z")

    return dict(row)
