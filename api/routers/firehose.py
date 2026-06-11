"""Kafka → WebSocket firehose multiplex (P2).

Exposes a single WS endpoint that fans out a curated set of Kafka topics
to one connected client. The FE opens one socket per browser tab and
multiplexes channels client-side (frontend/src/transport/firehose.ts).

Topics are city-filterable server-side via the ``city`` field in each
event payload (Bengaluru + Mumbai overlay per E-S6-05). Sequence numbers
are assigned by the server so FE-INV-008 can de-dupe on reconnect.

Falls back to in-process polling against `aiokafka` if available, or to
a no-op subscription if Kafka is unreachable (the WS stays open so the
FE shows "Live" rather than "Offline" — degrades gracefully).
"""

from __future__ import annotations

import asyncio
import json
import os
from typing import Any

import structlog
from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect, status

logger = structlog.get_logger(__name__)
router = APIRouter()

KAFKA_BOOTSTRAP = os.environ.get("SYNAPSE_KAFKA_BOOTSTRAP", "kafka:9092")

# Curated FE channel → Kafka topic map. Keys are stable across versions
# (the FE binds to them); changing values requires migration.
CHANNEL_TOPIC: dict[str, str] = {
    "decision": "synapse.orchestrator.decision",
    "disruption": "synapse.disruption.alert",
    "routing": "synapse.routing.plan",
    "metric": "synapse.metrics.agent",
    "twin": "synapse.twin.divergence",
    "demand": "synapse.demand.forecast",
    "freshness": "synapse.freshness.alert",
    "pricing": "synapse.pricing.update",
    # ADR-044: HITL escalations push to the cockpit through the same
    # multiplexed socket instead of a separate orchestrator WS connection.
    # The topic itself is Sprint-1 frozen (#9); this is a consumer addition.
    "escalation": "synapse.orchestrator.escalation",
}


@router.websocket("/firehose")
async def firehose(
    websocket: WebSocket,
    topics: str = Query(default="decision"),
    city: str = Query(default="bengaluru"),
    since_seq: int = Query(default=0),
) -> None:
    """Multiplexed Kafka fan-out.

    Query:
      topics      — comma-separated channel names (see CHANNEL_TOPIC keys)
      city        — bengaluru | mumbai (server-side filter)
      since_seq   — replay floor; the FE caches the last seq per channel
    """
    await websocket.accept()
    requested = [t.strip() for t in topics.split(",") if t.strip()]
    valid = [t for t in requested if t in CHANNEL_TOPIC]
    if not valid:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="no valid topics")
        return

    logger.info("firehose_connect", topics=valid, city=city, since_seq=since_seq)
    seq = max(0, int(since_seq))
    seq_lock = asyncio.Lock()

    async def send_event(channel: str, payload: dict[str, Any]) -> None:
        nonlocal seq
        async with seq_lock:
            seq += 1
            envelope = {
                "topic": channel,
                "seq": seq,
                "ts": _now_iso(),
                "payload": payload,
            }
        await websocket.send_text(_canonical_json(envelope))

    consumer_task = asyncio.create_task(_consume(valid, city, send_event))
    try:
        # Block on client disconnect; consumer task runs in parallel.
        while True:
            msg = await websocket.receive_text()
            if msg == '{"type":"ping"}':
                await websocket.send_text('{"type":"pong"}')
    except WebSocketDisconnect:
        logger.info("firehose_disconnect")
    finally:
        consumer_task.cancel()
        try:
            await consumer_task
        except (asyncio.CancelledError, Exception):
            pass


async def _consume(
    channels: list[str],
    city: str,
    send_event: Any,
) -> None:
    """Subscribe to the requested Kafka topics and forward to the WS.

    Uses aiokafka when available; otherwise emits a heartbeat every 15s so
    the FE's connection pill stays green even when Kafka is unavailable in
    smoke environments.
    """
    try:
        from aiokafka import AIOKafkaConsumer  # type: ignore[import-not-found]
    except ImportError:
        logger.warning("aiokafka_missing_heartbeat_only")
        while True:
            await asyncio.sleep(15)
            await send_event("metric", {"city": city, "type": "heartbeat"})

    topic_names = [CHANNEL_TOPIC[c] for c in channels]
    reverse = {CHANNEL_TOPIC[c]: c for c in channels}
    consumer = AIOKafkaConsumer(
        *topic_names,
        bootstrap_servers=KAFKA_BOOTSTRAP,
        enable_auto_commit=False,
        auto_offset_reset="latest",
        value_deserializer=lambda v: json.loads(v.decode("utf-8")),
    )
    try:
        await consumer.start()
    except Exception as exc:  # noqa: BLE001
        logger.warning("aiokafka_start_failed", error=str(exc))
        while True:
            await asyncio.sleep(15)
            await send_event("metric", {"city": city, "type": "heartbeat"})

    try:
        async for msg in consumer:
            payload = msg.value if isinstance(msg.value, dict) else {"raw": str(msg.value)}
            msg_city = payload.get("city")
            if msg_city and msg_city != city:
                continue
            channel = reverse.get(msg.topic, "metric")
            await send_event(channel, payload)
    finally:
        await consumer.stop()


def _now_iso() -> str:
    from datetime import UTC, datetime

    return datetime.now(UTC).isoformat()


def _canonical_json(obj: dict[str, Any]) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))
