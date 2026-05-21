"""Orders router — accepts customer orders and publishes to synapse.orders.demand.

Sprint 7 hardening (ADR-029):
    * Topic is now registered as #17 in the Kafka topic registry.
    * Uses the ``SynapseProducer`` singleton from app lifespan (one producer
      per process, not per request).
    * Validates payload against ``proto/domain/order_request.schema.json``
      before producing (I-3 schema-at-handler-boundary).
    * Idempotency-Key header support so retried HTTP requests dedupe both
      at the API gateway and downstream consumers.
    * W3C traceparent propagated through the payload so downstream consumers
      can join the same trace.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import structlog
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from synapse_common.idempotency import idempotent
from synapse_common.schemas import SchemaValidationError, validate_payload

logger = structlog.get_logger(__name__)
router = APIRouter()

TOPIC = "synapse.orders.demand"


class OrderRequest(BaseModel):
    city: str = Field(..., description="bengaluru | mumbai")
    store_id: str
    sku_id: str
    quantity: int = Field(..., gt=0, le=1000)
    customer_hash: str | None = Field(
        default=None,
        description="Hashed customer identifier (no PII per WS-7).",
    )


def _trace_id() -> str | None:
    try:
        from opentelemetry import trace
    except Exception:  # noqa: BLE001
        return None
    span = trace.get_current_span()
    ctx = span.get_span_context()
    if not ctx or not ctx.trace_id:
        return None
    return f"00-{ctx.trace_id:032x}-{ctx.span_id:016x}-01"


def _trace_kafka_headers() -> list[tuple[str, bytes]]:
    try:
        from opentelemetry.propagate import inject
    except Exception:  # noqa: BLE001
        return []
    carrier: dict[str, str] = {}
    try:
        inject(carrier)
    except Exception:  # noqa: BLE001
        return []
    return [(k, v.encode("utf-8")) for k, v in carrier.items()]


@router.post("/")
@idempotent(scope="orders")
async def create_order(req: OrderRequest, request: Request) -> dict[str, str]:
    """Accept an order, validate, and publish to synapse.orders.demand."""
    if req.city not in {"bengaluru", "mumbai"}:
        raise HTTPException(status_code=400, detail=f"unsupported city: {req.city}")

    producer: Any = getattr(request.app.state, "producer", None)
    if producer is None:
        raise HTTPException(status_code=503, detail="kafka producer not initialized")

    payload: dict[str, Any] = {
        "order_id": str(uuid4()),
        "city": req.city,
        "store_id": req.store_id,
        "sku_id": req.sku_id,
        "quantity": req.quantity,
        "timestamp": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
    }
    idem = request.headers.get("Idempotency-Key")
    if idem:
        payload["idempotency_key"] = idem
    trace = _trace_id()
    if trace:
        payload["trace_id"] = trace
    if req.customer_hash:
        payload["customer_hash"] = req.customer_hash

    try:
        validate_payload("order_request", payload)
    except SchemaValidationError as exc:
        logger.warning("order_schema_validation_failed", error=str(exc))
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    try:
        producer.produce(
            topic=TOPIC,
            value=payload,
            key=req.store_id,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("order_publish_failed", error=str(exc))
        raise HTTPException(status_code=503, detail=f"kafka unavailable: {exc}") from exc

    return {
        "status": "accepted",
        "order_id": payload["order_id"],
        "city": req.city,
    }
