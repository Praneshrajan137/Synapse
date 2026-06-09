"""Agents router — health + readiness + per-agent metrics across the 8 agents.

P0 returned only `{name: status_string}`. P2 enriches with latency
percentiles + decisions/min + calibration coverage, merged from
``api.routers.metrics`` so the FE has one fetch per refresh.
"""

from __future__ import annotations

import asyncio
import os
from typing import Any

import httpx
import structlog
from fastapi import APIRouter

from api.routers import metrics as metrics_router

logger = structlog.get_logger(__name__)
router = APIRouter()

# Names use underscores so they match agent_card.json / FE AGENT_NAMES.
AGENTS = [
    "demand_prophet",
    "routing_navigator",
    "inventory_sentinel",
    "freshness_guardian",
    "pricing_oracle",
    "disruption_shield",
    "supplier_trust",
    "sustainability_agent",
]


def _probe_host(name: str, overlay: str | None) -> str:
    """Docker DNS hostname — uses dashes per agent_card convention."""
    dashed = name.replace("_", "-")
    return f"{dashed}{'-' + overlay if overlay else ''}"


async def _probe(name: str, overlay: str | None) -> tuple[str, str]:
    host = _probe_host(name, overlay)
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            r = await client.get(f"http://{host}:8080/health")
            return name, "healthy" if r.status_code == 200 else f"http_{r.status_code}"
    except Exception as exc:  # noqa: BLE001
        return name, f"unreachable: {exc.__class__.__name__}"


# Empty path (not "/") so the canonical route is exactly the prefix
# "/api/v1/agents" — matching the frontend's no-trailing-slash call
# (frontend/src/transport/synapse-api.ts) instead of 307-redirecting it.
@router.get("")
async def list_agents() -> dict[str, Any]:
    overlay = os.environ.get("SYNAPSE_CITY_OVERLAY")
    health_results = await asyncio.gather(*[_probe(a, overlay) for a in AGENTS])
    health: dict[str, str] = dict(health_results)

    # Best-effort metric overlay.
    try:
        metric_body = await metrics_router.per_agent_metrics()
        metric_map: dict[str, dict[str, Any]] = metric_body.get("agents", {})
    except Exception as exc:  # noqa: BLE001
        logger.warning("agent_metrics_overlay_failed", error=str(exc))
        metric_map = {}

    agents: dict[str, dict[str, Any]] = {}
    for name in AGENTS:
        agents[name] = {
            "status": health.get(name, "unknown"),
            "latency_p50_ms": metric_map.get(name, {}).get("p50_ms"),
            "latency_p95_ms": metric_map.get(name, {}).get("p95_ms"),
            "latency_p99_ms": metric_map.get(name, {}).get("p99_ms"),
            "decisions_per_min": metric_map.get(name, {}).get("decisions_per_min"),
            "calibration_coverage_90": metric_map.get(name, {}).get("calibration_coverage_90"),
        }
    return {"agents": agents, "count": len(AGENTS)}
