"""Orders router — accepts demand orders and publishes to Kafka."""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime

import structlog
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

logger = structlog.get_logger(__name__)
router = APIRouter()


class OrderRequest(BaseModel):
    city: str = Field(..., description="bengaluru | mumbai")
    store_id: str
    sku_id: str
    quantity: int = Field(..., gt=0)


@router.post("/")
async def create_order(req: OrderRequest) -> dict[str, str]:
    payload = {
        "city": req.city,
        "store_id": req.store_id,
        "sku_id": req.sku_id,
        "quantity": req.quantity,
        "timestamp": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
    }
    try:
        from confluent_kafka import Producer

        bootstrap = os.environ.get("KAFKA_BOOTSTRAP", "kafka:9092")
        producer = Producer({"bootstrap.servers": bootstrap, "message.timeout.ms": 3000})
        producer.produce(
            "synapse.orders.demand",
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8"),
        )
        producer.flush(timeout=5)
    except Exception as exc:  # noqa: BLE001
        logger.warning("order_publish_failed", error=str(exc))
        raise HTTPException(status_code=503, detail=f"kafka unavailable: {exc}") from exc
    return {"status": "accepted", "city": req.city}
