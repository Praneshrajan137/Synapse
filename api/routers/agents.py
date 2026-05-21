"""Agents router — health + readiness across the 8 agent services.

Sprint-7 hardening (WS-1 §1): synchronous ``requests.get`` per agent
inside an ``async def`` blocked the event loop. Replaced with the
shared ``httpx.AsyncClient`` bulkhead profile registered for agent
health probes (uses the ``a2a`` profile — health endpoints are
lightweight and re-use the same pool).
"""

from __future__ import annotations

import asyncio
import os
from typing import Any

import httpx
import structlog
from fastapi import APIRouter
from synapse_common.clients import get_client

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


async def _probe_one(client: httpx.AsyncClient, host: str) -> str:
    try:
        resp = await client.get(f"http://{host}:8080/health", timeout=2.0)
        return "ok" if resp.status_code == 200 else f"http_{resp.status_code}"
    except httpx.TransportError as exc:
        return f"unreachable: {exc.__class__.__name__}"


@router.get("/")
async def list_agents() -> dict[str, Any]:
    try:
        overlay = os.environ.get("SYNAPSE_CITY_OVERLAY")
        client = await get_client("a2a")
        hosts = [f"{agent}{'-' + overlay if overlay else ''}" for agent in AGENTS]
        results = await asyncio.gather(*(_probe_one(client, host) for host in hosts))
        statuses = dict(zip(AGENTS, results, strict=True))
        return {"agents": statuses, "count": len(AGENTS)}
    except Exception as exc:  # noqa: BLE001
        return {"agents": {}, "count": 0, "error": str(exc)}
