"""Agents router — health + readiness across the 8 agent services."""

from __future__ import annotations

import os
from typing import Any

import structlog
from fastapi import APIRouter

logger = structlog.get_logger(__name__)
router = APIRouter()

AGENTS = [
    "demand-prophet",
    "routing-navigator",
    "inventory-sentinel",
    "pricing-oracle",
    "disruption-shield",
    "supplier-trust",
    "sustainability-agent",
    "freshness-guardian",
]


@router.get("/")
async def list_agents() -> dict[str, Any]:
    try:
        import requests

        overlay = os.environ.get("SYNAPSE_CITY_OVERLAY")
        statuses: dict[str, str] = {}
        for agent in AGENTS:
            host = f"{agent}{'-' + overlay if overlay else ''}"
            try:
                r = requests.get(f"http://{host}:8080/health", timeout=2)
                statuses[agent] = "ok" if r.status_code == 200 else f"http_{r.status_code}"
            except Exception as exc:  # noqa: BLE001
                statuses[agent] = f"unreachable: {exc.__class__.__name__}"
        return {"agents": statuses, "count": len(AGENTS)}
    except Exception as exc:  # noqa: BLE001
        return {"agents": {}, "count": 0, "error": str(exc)}
