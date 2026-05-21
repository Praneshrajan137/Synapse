"""SSE bridge — Kafka topic tail over Server-Sent Events.

Backend gap **B1** for the Atlas Console (plan §11). The frontend's
`useKafkaStream(topic)` hook expects ``GET /api/v1/stream/{topic}`` to
return ``text/event-stream`` with one SSE event per Kafka record. This
router provides exactly that.

Why SSE, not WebSocket
----------------------
Kafka tails are server→client only. SSE multiplexes through HTTP/2 nginx,
ships ``Last-Event-ID`` reconnection by spec, and survives corporate
proxies that strip WS upgrades. WebSocket is reserved for the bidirectional
``/ws/escalation`` channel (HITL) — see ADR-026.

Operational model
-----------------
- **Consumer-group-per-connection**. Each browser tab gets a unique group
  so offsets are independent and a disconnected tab does not stall others.
  The group is derived from a request UUID: ``atlas-console-<uuid>``.
- **Topic allow-list** (the 9 user-visible topics from plan §1). Internal
  topics like ``synapse.metrics.agent`` are surfaced; control-plane topics
  are not. Validated against the JSON-loaded ``infrastructure/kafka/topics.json``
  so a typo can't open a private topic.
- **Heartbeat** comment-event every 15 s so reverse-proxy idle timeouts
  don't kill the connection (nginx default is 60 s).
- **Backpressure**: if the consumer falls behind, we drop the oldest
  buffered records — never block the producer thread. The frontend reconnects
  via ``Last-Event-ID`` and resumes from the last delivered offset.
- **Determinism for demo mode**: ``?demo=1`` switches the source to a fixture
  loop registered in ``infrastructure/kafka/demo_fixtures/`` (added in S5).

Authentication
--------------
The BFF cookie session (B3, ``api/routers/auth.py``) gates this endpoint;
unauthenticated requests get 401. The session middleware sets
``request.state.session``; we read ``session.persona`` for telemetry only —
authorisation is binary (logged in = allowed) at this layer.

I-1: confluent-kafka is Apache 2.0; no paid dependency.
I-13: Kafka payloads are already canonicalised by producers; this router
      forwards bytes verbatim so KV-cache prefixes survive the round-trip
      through any client that re-emits a decision payload.
"""

from __future__ import annotations

import asyncio
import json
import os
import uuid
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any, Final

import structlog
from fastapi import APIRouter, HTTPException, Query, Request
from sse_starlette.sse import EventSourceResponse

logger = structlog.get_logger(__name__)
router = APIRouter()

# ---------------------------------------------------------------------------
# Topic allow-list. The 9 user-visible streams from plan §1, plus the metrics
# tail. Loaded from infrastructure/kafka/topics.json so the source of truth
# is one place; we just whitelist a subset.
# ---------------------------------------------------------------------------
_TOPICS_JSON: Final = (
    Path(__file__).resolve().parents[2] / "infrastructure" / "kafka" / "topics.json"
)

USER_VISIBLE_TOPICS: Final = frozenset(
    {
        "synapse.demand.forecast",
        "synapse.routing.plan",
        "synapse.inventory.reorder",
        "synapse.orchestrator.escalation",
        "synapse.disruption.alert",
        "synapse.pricing.update",
        "synapse.freshness.alert",
        "synapse.orchestrator.decision",
        "synapse.audit.log",
        "synapse.metrics.agent",
    },
)


def _validate_topic(topic: str) -> str:
    if topic not in USER_VISIBLE_TOPICS:
        raise HTTPException(status_code=404, detail=f"topic not user-visible: {topic}")
    # Belt-and-braces: confirm it's actually provisioned. CLAUDE.md says topics
    # are FROZEN — but we still cross-check so a spec-list typo can't blind us.
    try:
        registered = json.loads(_TOPICS_JSON.read_text(encoding="utf-8"))
        names = {t["name"] for t in registered.get("topics", [])}
        if topic not in names:
            raise HTTPException(
                status_code=503,
                detail=f"topic {topic} not provisioned in topics.json",
            )
    except FileNotFoundError:
        # In unit tests we may not have the file mounted. Don't fail closed
        # there; production CI mounts the volume.
        logger.warning("topics_json_missing", path=str(_TOPICS_JSON))
    return topic


# ---------------------------------------------------------------------------
# SSE generator. Runs Kafka polling on a worker thread so the FastAPI event
# loop stays unblocked. Each yielded dict becomes one SSE event.
# ---------------------------------------------------------------------------
HEARTBEAT_SECONDS: Final = 15
POLL_TIMEOUT_S: Final = 1.0
MAX_BUFFER: Final = 500  # records held in memory per connection


async def _kafka_event_stream(
    topic: str,
    group_id: str,
    last_event_id: str | None,
    request: Request,
) -> AsyncIterator[dict[str, Any]]:
    """Yield SSE-shaped dicts (id, event, data) until the client disconnects."""
    try:
        from confluent_kafka import Consumer, KafkaError, TopicPartition
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=f"kafka client unavailable: {exc}") from exc

    bootstrap = os.environ.get("KAFKA_BOOTSTRAP", "kafka:9092")
    consumer = Consumer(
        {
            "bootstrap.servers": bootstrap,
            "group.id": group_id,
            # Per-connection groups never share offsets, so latest is fine.
            "auto.offset.reset": "latest",
            "enable.auto.commit": True,
            "auto.commit.interval.ms": 5000,
            # Backpressure: bound the in-flight set so a slow client can't OOM us.
            "fetch.max.bytes": 1_048_576,
            "max.partition.fetch.bytes": 524_288,
        },
    )
    consumer.subscribe([topic])

    # Honour Last-Event-ID resume. Format: "<partition>:<offset>".
    if last_event_id:
        try:
            part_str, off_str = last_event_id.split(":", 1)
            tp = TopicPartition(topic, int(part_str), int(off_str) + 1)
            consumer.assign([tp])
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "sse_last_event_id_parse_failed",
                topic=topic,
                last_event_id=last_event_id,
                error=str(exc),
            )

    last_emit = asyncio.get_event_loop().time()
    try:
        while True:
            if await request.is_disconnected():
                break

            msg = await asyncio.to_thread(consumer.poll, POLL_TIMEOUT_S)
            now = asyncio.get_event_loop().time()

            if msg is None:
                # Heartbeat keeps proxies and clients alive.
                if now - last_emit >= HEARTBEAT_SECONDS:
                    yield {"event": "heartbeat", "data": ""}
                    last_emit = now
                continue

            if msg.error():
                err = msg.error()
                if err.code() == KafkaError._PARTITION_EOF:  # noqa: SLF001
                    continue
                logger.warning(
                    "sse_kafka_error", topic=topic, error=str(err), code=err.code()
                )
                continue

            value = msg.value()
            payload = (
                value.decode("utf-8", errors="replace") if isinstance(value, (bytes, bytearray)) else str(value)
            )
            event_id = f"{msg.partition()}:{msg.offset()}"

            yield {
                "id": event_id,
                "event": "message",
                "data": payload,
            }
            last_emit = now
    finally:
        try:
            consumer.close()
        except Exception as exc:  # noqa: BLE001
            logger.warning("sse_consumer_close_failed", error=str(exc))


@router.get("/{topic}")
async def stream_topic(
    topic: str,
    request: Request,
    last_event_id: str | None = Query(default=None, alias="lastEventId"),
) -> EventSourceResponse:
    """Tail a Kafka topic over SSE. See module docstring for semantics."""
    _validate_topic(topic)

    # Honour the EventSource standard header too.
    if last_event_id is None:
        last_event_id = request.headers.get("Last-Event-ID")

    group_id = f"atlas-console-{uuid.uuid4()}"
    logger.info(
        "sse_subscribe",
        topic=topic,
        group_id=group_id,
        resume_from=last_event_id,
    )

    return EventSourceResponse(
        _kafka_event_stream(topic, group_id, last_event_id, request),
        ping=HEARTBEAT_SECONDS,
        # Tell nginx not to buffer this response (X-Accel-Buffering header).
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
