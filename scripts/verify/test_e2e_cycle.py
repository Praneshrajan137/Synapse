"""
End-to-end verification: full decision cycle.
Run: python scripts/verify/test_e2e_cycle.py

Order -> forecast -> inventory -> route -> consensus -> audit trail entry.
"""
from __future__ import annotations

import asyncio
from uuid import uuid4

import httpx
import structlog

logger = structlog.get_logger(__name__)

BASE = "http://localhost:8085"


async def verify_e2e() -> None:
    order = {
        "order_id": str(uuid4()),
        "store_id": "store_001",
        "items": [{"sku_id": "SKU_001", "qty": 2}, {"sku_id": "SKU_042", "qty": 1}],
    }

    async with httpx.AsyncClient(timeout=30) as client:
        # 1. Submit decision request
        resp = await client.post(f"{BASE}/api/v1/decisions", json=order)
        assert resp.status_code == 200, f"Decision request failed: {resp.text}"
        decision = resp.json()
        logger.info("decision_received", decision=decision)

        # 2. Verify decision has audit trail
        assert decision.get("audit_id") is not None, "I-4 FAIL: No audit_id"

        # 3. Verify tier assigned
        assert decision.get("tier") in [
            "tier_1", "tier_2", "tier_3", "tier_4",
        ], "Tier not assigned"

        # 4. Verify health endpoint
        health = await client.get(f"{BASE}/health")
        assert health.status_code == 200

    logger.info("e2e_decision_cycle_passed")


if __name__ == "__main__":
    asyncio.run(verify_e2e())
