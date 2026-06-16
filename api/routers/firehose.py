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
import contextlib
import json
import os
from typing import Any

import structlog
from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect, status
from synapse_common.auth import Role, TokenError

from api.middleware.jwt import manager

logger = structlog.get_logger(__name__)
router = APIRouter()

KAFKA_BOOTSTRAP = os.environ.get("SYNAPSE_KAFKA_BOOTSTRAP", "kafka:9092")

# PR-5 backpressure tunables. A slow WS client must not back up the shared Kafka
# consumer loop; bound the per-send wait and the consumer's per-poll buffer.
SEND_TIMEOUT_S = float(os.environ.get("SYNAPSE_FIREHOSE_SEND_TIMEOUT", "5"))
MAX_POLL_RECORDS = int(os.environ.get("SYNAPSE_FIREHOSE_MAX_POLL_RECORDS", "200"))
FETCH_MAX_BYTES = int(os.environ.get("SYNAPSE_FIREHOSE_FETCH_MAX_BYTES", str(1024 * 1024)))

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
    # ADR-048: the live Cognition Channel — the orchestrator's FSM phase
    # transitions (collecting → debating → arbitrating → executing → learning),
    # so the AUX can show the council thinking/debating live, not just the verdict.
    "cognition": "synapse.orchestrator.phase",
}


def _firehose_auth_required() -> bool:
    """F1 (ADR-050): whether the firehose WS demands a VIEWER JWT.

    Default OFF for Tier-D safe rollout — the FE/verify_live token-passing lands
    alongside the demo-boot verification (a coordinated, live-verified step).
    Tier-P MUST set this true (ADR-049/050 gate) once every consumer presents a
    token. Read per-connection so the operator can flip it without a redeploy.
    """
    return os.environ.get("SYNAPSE_FIREHOSE_AUTH_REQUIRED", "").lower() in {"1", "true", "yes"}


_WS_JWT_SUBPROTOCOL_PREFIX = "synapse-jwt."


def _ws_token(websocket: WebSocket) -> tuple[str | None, str | None]:
    """Extract a bearer token from the WS handshake.

    Preferred: a ``synapse-jwt.<token>`` subprotocol (keeps the token out of URLs
    and access logs). Fallback: a ``?token=<jwt>`` query param. Returns
    ``(token, subprotocol_to_echo)``.
    """
    for proto in websocket.scope.get("subprotocols", []) or []:
        if isinstance(proto, str) and proto.startswith(_WS_JWT_SUBPROTOCOL_PREFIX):
            return proto[len(_WS_JWT_SUBPROTOCOL_PREFIX) :], proto
    return websocket.query_params.get("token"), None


def _authorize_ws(websocket: WebSocket) -> tuple[bool, str | None]:
    """Return ``(authorized, subprotocol_to_echo)``.

    Requires a valid VIEWER access token; a missing / invalid / under-privileged
    token is unauthorized — the firehose never opens on doubt (the F1 fix).
    """
    token, subprotocol = _ws_token(websocket)
    if not token:
        return False, None
    try:
        ctx = manager().verify(token, expected_type="access")
    except TokenError:
        return False, None
    return ctx.role.satisfies(Role.VIEWER), subprotocol


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
    # F1 (ADR-050): gate the live data stream behind a VIEWER JWT when required.
    # Default-off in Tier-D; reject unauthenticated/under-privileged on Tier-P.
    subprotocol: str | None = None
    if _firehose_auth_required():
        authorized, subprotocol = _authorize_ws(websocket)
        if not authorized:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="auth required")
            return
    await websocket.accept(subprotocol=subprotocol)
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
        # PR-5 backpressure: bound the send. A consumer too slow to drain within
        # SEND_TIMEOUT_S is dropped (socket closed) rather than stalling the shared
        # Kafka consumer loop for everyone; the FE reconnects with since_seq.
        try:
            await asyncio.wait_for(
                websocket.send_text(_canonical_json(envelope)),
                timeout=SEND_TIMEOUT_S,
            )
        except TimeoutError:
            logger.warning("firehose_slow_consumer_dropped", channel=channel, seq=seq)
            with contextlib.suppress(Exception):
                await websocket.close(code=status.WS_1011_INTERNAL_ERROR)
            raise

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
        max_poll_records=MAX_POLL_RECORDS,
        fetch_max_bytes=FETCH_MAX_BYTES,
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
