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


# ─────────────────────────────────────────────────────────────────────────────
# Sprint 19 (ADR-047) — SLO burn (the supervisory "is it healthy over time" read)
# ─────────────────────────────────────────────────────────────────────────────

PROM_URL = os.environ.get("SYNAPSE_PROMETHEUS_URL", "http://prometheus:9090")

# Per-tier SLO config — the SINGLE source of truth shared with the gauge math
# below. Mirrors infrastructure/observability/slos/orchestrator-tier{1..4}.slo.yaml
# and the multi-window thresholds in
# infrastructure/prometheus/rules/orchestrator_burn.yml. The objective is
# recoverable from the file's fast threshold: threshold_fast = 14.4 * budget,
# budget = 1 - objective (tier1 0.072/14.4 = 0.005 → 99.5%, etc).
_TIER_SLO: dict[str, dict[str, Any]] = {
    "tier_1": {"metric": "synapse_inference_latency_seconds", "le": "0.1", "objective": 0.995},
    "tier_2": {"metric": "synapse_inference_latency_seconds", "le": "0.5", "objective": 0.99},
    "tier_3": {"metric": "synapse_consensus_duration_seconds", "le": "15", "objective": 0.97},
    "tier_4": {"metric": "synapse_consensus_duration_seconds", "le": "120", "objective": 0.95},
}
# Multi-window burn thresholds (SRE): a fast (1h) burn ≥14.4x exhausts a 30d
# budget in ~2 days (page); a slow (6h) burn ≥6x is a ticket-grade trend.
_FAST_WINDOW = "1h"
_SLOW_WINDOW = "6h"
_BUDGET_WINDOW = "30d"
_FAST_BURN_PAGE = 14.4
_SLOW_BURN_TICKET = 6.0


def _error_ratio_expr(metric: str, le: str, tier: str, window: str) -> str:
    """PromQL for the fraction of requests OUTSIDE the latency target.

    ``1 - good/total`` over ``window``. Identical shape to the alert rules in
    orchestrator_burn.yml so the gauge and the page agree by construction.
    """
    return (
        f'1 - (sum(rate({metric}_bucket{{tier="{tier}",le="{le}"}}[{window}])) '
        f'/ sum(rate({metric}_count{{tier="{tier}"}}[{window}])))'
    )


async def _prom_scalar(client: httpx.AsyncClient, expr: str) -> float | None:
    """Run an instant query and return the single scalar, or None.

    None means "no data / Prometheus unreachable" — NEVER a fabricated 0. The
    FE renders a null window as "burn unknown" (FE-INV-042), not silent-green.
    """
    import math

    try:
        resp = await client.get(f"{PROM_URL}/api/v1/query", params={"query": expr})
        resp.raise_for_status()
        body = resp.json()
    except Exception as exc:  # noqa: BLE001
        logger.warning("prometheus_slo_query_failed", error=str(exc))
        return None
    if body.get("status") != "success":
        return None
    result = body.get("data", {}).get("result", [])
    if not result:
        return None
    try:
        value = float(result[0]["value"][1])
    except (KeyError, IndexError, ValueError, TypeError):
        return None
    return None if math.isnan(value) else value


def _severity(burn_fast: float | None, burn_slow: float | None) -> str:
    """Map the two burn windows to an honest severity word (never colour-only)."""
    if burn_fast is None and burn_slow is None:
        return "unknown"
    if burn_fast is not None and burn_fast >= _FAST_BURN_PAGE:
        return "critical"
    if burn_slow is not None and burn_slow >= _SLOW_BURN_TICKET:
        return "warning"
    return "ok"


@router.get("/slo")
async def system_slo(
    op: Annotated[OperatorContext, Depends(CurrentOperator)],
) -> dict[str, Any]:
    """Per-tier multi-window SLO burn for the Standing Watch surface (ADR-047).

    Read-only (VIEWER). Computes burn inline from the raw histogram metrics so
    it does not depend on the recording rules being loaded; an unreachable
    Prometheus yields nulls + ``source: "unknown"`` rather than a healthy lie.
    """
    tiers: dict[str, Any] = {}
    any_data = False
    async with httpx.AsyncClient(timeout=5.0) as client:
        for tier, cfg in _TIER_SLO.items():
            metric, le, objective = cfg["metric"], cfg["le"], cfg["objective"]
            budget = 1.0 - objective
            err_fast = await _prom_scalar(
                client, _error_ratio_expr(metric, le, tier, _FAST_WINDOW)
            )
            err_slow = await _prom_scalar(
                client, _error_ratio_expr(metric, le, tier, _SLOW_WINDOW)
            )
            err_budget = await _prom_scalar(
                client, _error_ratio_expr(metric, le, tier, _BUDGET_WINDOW)
            )
            burn_fast = (err_fast / budget) if err_fast is not None else None
            burn_slow = (err_slow / budget) if err_slow is not None else None
            budget_remaining = (
                max(0.0, min(1.0, 1.0 - err_budget / budget)) if err_budget is not None else None
            )
            any_data = any_data or any(v is not None for v in (err_fast, err_slow, err_budget))
            tiers[tier] = {
                "objective": objective,
                "latency_target_s": float(le),
                "windows": {
                    "fast": {
                        "window": _FAST_WINDOW,
                        "error_rate": err_fast,
                        "burn_rate": burn_fast,
                    },
                    "slow": {
                        "window": _SLOW_WINDOW,
                        "error_rate": err_slow,
                        "burn_rate": burn_slow,
                    },
                },
                "budget_remaining_30d": budget_remaining,
                "severity": _severity(burn_fast, burn_slow),
            }
    import time

    return {"tiers": tiers, "ts": time.time(), "source": "prometheus" if any_data else "unknown"}


# ─────────────────────────────────────────────────────────────────────────────
# Sprint 19 (ADR-047) — calibration (are the confidences calibrated to reality?)
# ─────────────────────────────────────────────────────────────────────────────

_VALID_CITIES = {"bengaluru", "mumbai"}


def _audit_dsn() -> str:
    """Resolve the audit Postgres DSN. Fail-fast — never embed a credential.

    Mirrors ``api.routers.decisions._dsn``.
    """
    dsn = os.environ.get("POSTGRES_DSN")
    if not dsn:
        raise HTTPException(status_code=503, detail="POSTGRES_DSN not configured")
    return dsn


def _empty_calibration(window_hours: int, include_synthetic: bool, city: str | None) -> dict[str, Any]:
    from synapse_common.outcomes import reliability_bins

    import time

    return {
        "window_hours": window_hours,
        "include_synthetic": include_synthetic,
        "city": city,
        "n_total": 0,
        "n_scored": 0,
        "n_unknown": 0,
        "brier_score": None,
        "bins": reliability_bins([], n_bins=10),
        "as_of": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "note": "outcomes are scored after the settle horizon; unknown = not yet realized",
    }


@router.get("/calibration")
async def system_calibration(
    op: Annotated[OperatorContext, Depends(CurrentOperator)],
    window_hours: int = 168,
    include_synthetic: bool = False,
    city: str | None = None,
) -> dict[str, Any]:
    """System-level confidence calibration from the scored outcomes (ADR-047).

    Reliability curve (predicted confidence vs. realized-correct fraction) +
    Brier score, over the latest outcome per decision in the window. Defaults
    to REAL decisions only (``include_synthetic=false``) so demo pulses do not
    launder the trust read (FE-INV-044); always discloses n + as_of so a small
    sample reads as small (FE-INV-043), never a confident-looking curve on thin
    evidence.
    """
    if window_hours < 1 or window_hours > 2160:
        raise HTTPException(status_code=422, detail="window_hours must be in [1, 2160]")
    if city is not None and city not in _VALID_CITIES:
        raise HTTPException(status_code=422, detail="invalid city")

    from synapse_common.outcomes import brier_score, outcome_correct, reliability_bins
    from synapse_common.synthetic import SYNTHETIC_ORDER_PREFIX

    try:
        import psycopg2
        from psycopg2 import errors as pg_errors

        conn = psycopg2.connect(_audit_dsn())
        try:
            with conn.cursor() as cur:
                where = ["o.scored_at >= now() - make_interval(hours => %s)"]
                params: list[Any] = [SYNTHETIC_ORDER_PREFIX, window_hours]
                if city is not None:
                    where.append("c.city = %s")
                    params.append(city)
                cur.execute(
                    # DISTINCT ON keeps the latest outcome per decision (re-scoring
                    # appends, never mutates). is_synthetic computed in SQL so the
                    # row-heavy context_messages JSONB never leaves the database.
                    "SELECT DISTINCT ON (o.decision_id) c.confidence, o.status, "
                    "  COALESCE(jsonb_path_exists(c.context_messages, "
                    "    '$[*].content.request.order_id ? (@ starts with $prefix)', "
                    "    jsonb_build_object('prefix', %s::text)), false) AS is_synthetic "
                    "FROM decision_outcomes o "
                    "JOIN audit_consensus c ON c.decision_id = o.decision_id "
                    f"WHERE {' AND '.join(where)} "
                    "ORDER BY o.decision_id, o.scored_at DESC",
                    tuple(params),
                )
                rows = cur.fetchall()
        except pg_errors.UndefinedTable:
            # Fresh deploy before the 08_sprint19_outcomes migration applies —
            # honest "no outcomes yet", not a 503.
            conn.rollback()
            return _empty_calibration(window_hours, include_synthetic, city)
        finally:
            conn.close()
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=f"audit unavailable: {exc}") from exc

    samples: list[tuple[float, bool | None]] = []
    n_total = 0
    for confidence, statusv, is_synthetic in rows:
        if is_synthetic and not include_synthetic:
            continue
        n_total += 1
        samples.append((float(confidence), outcome_correct(statusv)))

    n_scored = sum(1 for _conf, correct in samples if correct is not None)

    import time

    return {
        "window_hours": window_hours,
        "include_synthetic": include_synthetic,
        "city": city,
        "n_total": n_total,
        "n_scored": n_scored,
        "n_unknown": n_total - n_scored,
        "brier_score": brier_score(samples),
        "bins": reliability_bins(samples, n_bins=10),
        "as_of": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "note": "outcomes are scored after the settle horizon; unknown = not yet realized",
    }
