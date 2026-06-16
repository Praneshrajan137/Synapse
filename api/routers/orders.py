"""Orders router — ingress for demand orders (synapse.orders.demand topic).

WS-2 changes:
  * Uses the shared ``app.state.kafka_producer`` (set up by the
    gateway lifespan) instead of constructing a per-request Producer.
  * Validates the incoming payload against ``proto/domain/order_request.schema.json``
    at the boundary (I-3), not just via Pydantic.
  * Writes through the outbox: the response is 202 only after the row is
    committed in ``audit_outbox``. The orchestrator's OutboxDispatcher
    drains the row and publishes to Kafka with idempotent semantics,
    eliminating the dual-write fault mode of the previous code path.
  * Accepts an ``Idempotency-Key`` header (RFC-style). Echoed into the
    outbox payload so downstream consumers can dedupe.
  * Injects W3C ``traceparent`` into the outbox row's ``headers`` JSONB so
    the published Kafka record carries the same trace as the HTTP request.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Annotated, Any

import structlog
from fastapi import APIRouter, Header, HTTPException, Request, status
from pydantic import BaseModel, Field

from synapse_common.outbox import enqueue
from synapse_common.schemas import SchemaValidationError, validate_handler_input
from synapse_common.tracing import inject_a2a_headers

logger = structlog.get_logger(__name__)
router = APIRouter()

# Domain topic the order flows onto (ADR-029, topic 17).
ORDERS_TOPIC = "synapse.orders.demand"


class OrderRequest(BaseModel):
    city: str = Field(..., description="bengaluru | mumbai")
    store_id: str = Field(..., min_length=1, max_length=64)
    sku_id: str = Field(..., min_length=1, max_length=64)
    quantity: int = Field(..., gt=0, le=1000)


class OrderResponse(BaseModel):
    status: str
    order_id: str
    outbox_id: str


@router.post(
    "/",
    response_model=OrderResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_order(
    req: OrderRequest,
    request: Request,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> OrderResponse:
    """Accept a demand order and enqueue it to the outbox.

    Why 202 not 200: the gateway has only committed the order to the
    *outbox*, not yet to Kafka. The dispatcher will publish; FE consumers
    learn the order arrived via the firehose stream, not via this route.
    """
    order_id = str(uuid.uuid4())
    payload: dict[str, Any] = {
        "order_id": order_id,
        "city": req.city,
        "store_id": req.store_id,
        "sku_id": req.sku_id,
        "quantity": req.quantity,
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    if idempotency_key:
        payload["idempotency_key"] = idempotency_key

    # (1) Validate at the I-3 boundary, not just Pydantic. Pydantic protects
    # the intra-process contract; JSON-Schema protects the Kafka contract.
    # validate_handler_input is the canonical WS-2 §4 boundary validator.
    try:
        validate_handler_input("order_request", payload)
    except SchemaValidationError as exc:
        logger.warning("order_schema_violation", errors=exc.errors, order_id=order_id)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"schema": exc.schema_name, "errors": exc.errors},
        ) from exc

    session_factory = getattr(request.app.state, "session_factory", None)
    if session_factory is None:
        # Hard 503: the gateway lifespan failed to wire postgres. Without it
        # we cannot make the outbox guarantee; surfacing the failure is the
        # right thing rather than silently dropping the order.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="postgres session factory not initialised",
        )

    # (2) Capture trace context so the eventual Kafka publish stays in the
    # same trace as the HTTP request. The dispatcher reads `row.headers`
    # and replays them onto the message.
    trace_headers: dict[str, str] = {}
    inject_a2a_headers(trace_headers)

    # (3) Outbox-first write. Use the order_id as both the logical
    # correlation id and the Kafka partition key — partitions cluster
    # orders for the same SKU+store sequentially without operator config.
    try:
        async with session_factory() as session:
            outbox_id = await enqueue(
                session,
                decision_id=uuid.UUID(order_id),
                topic=ORDERS_TOPIC,
                payload=payload,
                partition_key=f"{req.city}:{req.store_id}",
                headers=trace_headers,
            )
            await session.commit()
    except Exception as exc:  # noqa: BLE001
        logger.error("order_outbox_enqueue_failed", error=str(exc), order_id=order_id)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"audit outbox unavailable: {exc}",
        ) from exc

    logger.info(
        "order_accepted",
        order_id=order_id,
        outbox_id=str(outbox_id),
        city=req.city,
        store_id=req.store_id,
        sku_id=req.sku_id,
        quantity=req.quantity,
    )
    return OrderResponse(status="accepted", order_id=order_id, outbox_id=str(outbox_id))
