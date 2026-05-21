"""Orders router — accepts demand orders and publishes to Kafka.

Sprint-7 refactor (ADR-029, WS-2 §7):
- Uses the shared ``SynapseProducer`` singleton from
  ``app.state.kafka_producer`` (no more per-request bare
  ``confluent_kafka.Producer()``).
- Produces to ``synapse.orders.demand`` (topic #17, registered in
  ``infrastructure/kafka/topics.json``).
- Validates the payload against
  ``proto/domain/order_request.schema.json`` via the handler-boundary
  validator (``synapse_common.schemas.validate_handler_input``).
- Requires ``Idempotency-Key`` and replays cached responses for
  duplicate keys.
- Injects W3C traceparent into the Kafka message headers via
  ``SynapseProducer`` (handled inside the producer).
"""

from __future__ import annotations

from datetime import UTC, datetime

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from synapse_common.idempotency import (
    enforce_idempotency,
    record_idempotent_response,
)
from synapse_common.schemas import ORDER_REQUEST_SCHEMA, validate_handler_input

logger = structlog.get_logger(__name__)
router = APIRouter()


ORDERS_TOPIC = "synapse.orders.demand"


class OrderRequest(BaseModel):
    city: str = Field(..., description="bengaluru | mumbai")
    store_id: str
    sku_id: str
    quantity: int = Field(..., gt=0)


@router.post("/")
async def create_order(
    request: Request,
    req: OrderRequest,
    idem: tuple[str, str] | None = Depends(enforce_idempotency),
) -> dict[str, str]:
    if idem is None:
        cached = request.state.idempotent_response
        return cached["response"]  # type: ignore[no-any-return]
    idempotency_key, request_hash = idem

    payload: dict[str, object] = {
        "city": req.city,
        "store_id": req.store_id,
        "sku_id": req.sku_id,
        "quantity": req.quantity,
        "timestamp": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "idempotency_key": idempotency_key,
    }
    validate_handler_input(ORDER_REQUEST_SCHEMA, payload)

    producer = getattr(request.app.state, "kafka_producer", None)
    if producer is None:
        raise HTTPException(status_code=503, detail="kafka producer not initialised")

    try:
        producer.produce(
            topic=ORDERS_TOPIC,
            value=payload,
            key=req.store_id,
        )
        producer.flush(timeout=5.0)
    except Exception as exc:  # noqa: BLE001
        logger.warning("order_publish_failed", error=str(exc))
        raise HTTPException(status_code=503, detail=f"kafka unavailable: {exc}") from exc

    response = {"status": "accepted", "city": req.city, "idempotency_key": idempotency_key}
    await record_idempotent_response(
        idempotency_key=idempotency_key,
        request_hash=request_hash,
        response_body=response,
        status_code=200,
    )
    return response
