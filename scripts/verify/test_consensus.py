"""
Multi-agent conflict resolution verification.
Run: python scripts/verify/test_consensus.py
"""
from __future__ import annotations

import asyncio
from uuid import uuid4

import httpx
import structlog

logger = structlog.get_logger(__name__)

BASE = "http://localhost:8085"


async def verify_consensus() -> None:
    # Tier 3 decision: multiple agents, moderate confidence
    request = {
        "order_id": str(uuid4()),
        "store_id": "store_002",
        "items": [{"sku_id": f"SKU_{i:03d}", "qty": 1} for i in range(10)],
        "agents_involved": [
            "demand_prophet", "routing_navigator", "inventory_sentinel",
            "pricing_oracle",
        ],
        "disruption_active": False,
    }

    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(f"{BASE}/api/v1/decisions", json=request)
        assert resp.status_code == 200, f"Consensus failed: {resp.text}"
        decision = resp.json()
        logger.info("consensus_result", decision=decision)

        assert decision.get("phase_reached", 0) >= 1
        assert decision.get("confidence", 0) >= 0

    logger.info("consensus_verification_passed")


if __name__ == "__main__":
    asyncio.run(verify_consensus())
