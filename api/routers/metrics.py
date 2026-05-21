"""Per-agent metric proxy (P2).

Queries Prometheus for ``synapse_inference_latency_seconds`` (defined in
``packages/synapse_common/metrics.py``) at p50/p95/p99 per agent and
returns a stable, FE-friendly shape. Cached for 5s to keep load light.

Falls back to a synthesized "unknown" response if Prometheus is unreachable
so the Mission Control surface degrades gracefully.
"""

from __future__ import annotations

import os
import time
from typing import Any

import httpx
import structlog
from fastapi import APIRouter, HTTPException

logger = structlog.get_logger(__name__)
router = APIRouter()

PROM_URL = os.environ.get("SYNAPSE_PROMETHEUS_URL", "http://prometheus:9090")
CACHE_TTL_S = 5.0
_cache: dict[str, tuple[float, dict[str, Any]]] = {}

AGENT_NAMES = [
    "demand_prophet",
    "routing_navigator",
    "inventory_sentinel",
    "freshness_guardian",
    "pricing_oracle",
    "disruption_shield",
    "supplier_trust",
    "sustainability_agent",
]


@router.get("/agents")
async def per_agent_metrics() -> dict[str, Any]:
    cached = _cache.get("agents")
    if cached and time.monotonic() - cached[0] < CACHE_TTL_S:
        return cached[1]

    async def query(q: str) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                resp = await client.get(f"{PROM_URL}/api/v1/query", params={"query": q})
                resp.raise_for_status()
                return resp.json()
        except Exception as exc:  # noqa: BLE001
            logger.warning("prometheus_query_failed", error=str(exc), query=q)
            return {"status": "error", "data": {"result": []}}

    p50 = await query(
        'histogram_quantile(0.5, sum by (le, agent_name) '
        '(rate(synapse_inference_latency_seconds_bucket[5m])))'
    )
    p95 = await query(
        'histogram_quantile(0.95, sum by (le, agent_name) '
        '(rate(synapse_inference_latency_seconds_bucket[5m])))'
    )
    p99 = await query(
        'histogram_quantile(0.99, sum by (le, agent_name) '
        '(rate(synapse_inference_latency_seconds_bucket[5m])))'
    )
    rate = await query(
        'sum by (agent_name) (rate(synapse_inference_latency_seconds_count[1m])) * 60'
    )
    coverage = await query(
        'avg by (agent_name) (synapse_calibration_coverage_90)'
    )

    out: dict[str, dict[str, Any]] = {n: {} for n in AGENT_NAMES}
    _ingest(out, p50, "p50_ms", lambda v: round(v * 1000, 1))
    _ingest(out, p95, "p95_ms", lambda v: round(v * 1000, 1))
    _ingest(out, p99, "p99_ms", lambda v: round(v * 1000, 1))
    _ingest(out, rate, "decisions_per_min", lambda v: round(v, 2))
    _ingest(out, coverage, "calibration_coverage_90", lambda v: round(v, 4))

    body = {
        "agents": out,
        "ts": time.time(),
        "source": "prometheus" if PROM_URL else "unknown",
    }
    _cache["agents"] = (time.monotonic(), body)
    return body


def _ingest(
    out: dict[str, dict[str, Any]],
    response: dict[str, Any],
    field: str,
    cast: Any,
) -> None:
    if response.get("status") != "success":
        return
    for sample in response.get("data", {}).get("result", []):
        agent = sample.get("metric", {}).get("agent_name")
        if agent not in out:
            continue
        try:
            value = float(sample["value"][1])
        except (KeyError, IndexError, ValueError, TypeError):
            continue
        out[agent][field] = cast(value)


@router.get("/healthz")
async def metrics_healthz() -> dict[str, str]:
    return {"status": "ok"}
