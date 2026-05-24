"""
SYNAPSE Kafka Client — Unified producer/consumer with schema validation (I-3).
All agents use this client. Direct kafka-python usage is a PR rejection.

Sprint-7 hardening (WS-2 §1, WS-8 §3):
  - Idempotent producer (``enable.idempotence=true``) + batched delivery.
  - W3C ``traceparent`` injection into Kafka headers via the OTel composite
    propagator (``synapse_common.tracing.KafkaHeaderCarrier``).
  - Optional explicit ``headers`` argument for callers that want to add
    their own correlation IDs.
"""

from __future__ import annotations

import json
from typing import Any

import structlog
from confluent_kafka import Consumer, Producer
from pydantic import BaseModel

from synapse_common.metrics import KAFKA_PRODUCE_TOTAL
from synapse_common.tracing import KafkaHeaderCarrier

logger = structlog.get_logger(__name__)

SERIALIZATION_KWARGS: dict[str, Any] = {
    "sort_keys": True,
    "separators": (",", ":"),
    "default": str,
}


class KafkaConfig(BaseModel):
    """Kafka connection configuration."""

    bootstrap_servers: str = "localhost:9092"
    group_id: str = "synapse-default"
    auto_offset_reset: str = "earliest"
    enable_auto_commit: bool = True


def _producer_settings(config: KafkaConfig) -> dict[str, Any]:
    return {
        "bootstrap.servers": config.bootstrap_servers,
        "message.max.bytes": 10485760,
        # Sprint-7 batching + exactly-once-by-producer.
        "enable.idempotence": True,
        "acks": "all",
        "linger.ms": 10,
        "batch.size": 65536,
        "compression.type": "zstd",
        "max.in.flight.requests.per.connection": 5,
    }


def _inject_traceparent_headers(extra: list[tuple[str, bytes]] | None) -> list[tuple[str, bytes]]:
    carrier = KafkaHeaderCarrier()
    try:
        from opentelemetry import propagate

        propagate.inject(carrier)
    except ImportError:
        pass
    headers = carrier.as_kafka_headers()
    if extra:
        headers.extend(extra)
    return headers


class SynapseProducer:
    """Thread-safe Kafka producer with deterministic serialization."""

    def __init__(self, config: KafkaConfig) -> None:
        self._producer = Producer(_producer_settings(config))
        self._config = config

    def produce(
        self,
        topic: str,
        value: dict[str, Any] | BaseModel,
        key: str | None = None,
        headers: list[tuple[str, bytes]] | None = None,
    ) -> None:
        """Produce message with deterministic JSON serialization (I-13)."""
        if isinstance(value, BaseModel):
            serialized = json.dumps(value.model_dump(mode="json"), **SERIALIZATION_KWARGS)
        else:
            serialized = json.dumps(value, **SERIALIZATION_KWARGS)

        kafka_headers = _inject_traceparent_headers(headers)
        self._producer.produce(
            topic=topic,
            value=serialized.encode("utf-8"),
            key=key.encode("utf-8") if key else None,
            headers=kafka_headers,  # type: ignore[arg-type]
        )
        # Background poll lets librdkafka invoke delivery callbacks.
        self._producer.poll(0)
        KAFKA_PRODUCE_TOTAL.labels(topic=topic).inc()

    def flush(self, timeout: float = 10.0) -> int:
        """Flush buffered messages. Returns the number of messages still in queue."""
        return int(self._producer.flush(timeout=timeout))

    def close(self) -> None:
        self._producer.flush(timeout=10.0)


class SynapseConsumer:
    """Kafka consumer with type-safe deserialization."""

    def __init__(self, config: KafkaConfig, topics: list[str]) -> None:
        self._consumer = Consumer(
            {
                "bootstrap.servers": config.bootstrap_servers,
                "group.id": config.group_id,
                "auto.offset.reset": config.auto_offset_reset,
                "enable.auto.commit": config.enable_auto_commit,
            }
        )
        self._consumer.subscribe(topics)

    def poll(self, timeout: float = 1.0) -> dict[str, Any] | None:
        """Poll for next message, return deserialized dict or None."""
        msg = self._consumer.poll(timeout)
        if msg is None or msg.error():
            return None
        try:
            raw: dict[str, Any] = json.loads(msg.value().decode("utf-8"))  # type: ignore[union-attr]
            return raw
        except (json.JSONDecodeError, AttributeError) as e:
            logger.error("kafka_deserialize_failed", error=str(e))
            return None

    def poll_with_headers(
        self, timeout: float = 1.0
    ) -> tuple[dict[str, Any], list[tuple[str, bytes]]] | None:
        """Poll and return both the deserialized value and Kafka header list.

        Use this entry point when downstream code needs to ``attach`` the
        upstream OTel trace context. ``synapse_common.tracing.extract_kafka_context``
        accepts the returned header list.
        """
        msg = self._consumer.poll(timeout)
        if msg is None or msg.error():
            return None
        try:
            raw: dict[str, Any] = json.loads(msg.value().decode("utf-8"))  # type: ignore[union-attr]
        except (json.JSONDecodeError, AttributeError) as e:
            logger.error("kafka_deserialize_failed", error=str(e))
            return None
        raw_headers = msg.headers() or []
        headers: list[tuple[str, bytes]] = []
        for entry in raw_headers:
            # confluent-kafka's typeshed annotates ``headers()`` as
            # ``list[str | bytes]`` even though every runtime payload is
            # ``(key, value)`` tuples. Guard at runtime so mypy --strict
            # accepts both shapes.
            if not isinstance(entry, tuple) or len(entry) != 2:
                continue
            key, value = entry
            if isinstance(value, bytes):
                headers.append((str(key), value))
            elif isinstance(value, str):
                headers.append((str(key), value.encode("utf-8")))
            else:
                headers.append((str(key), b""))
        return raw, headers

    def close(self) -> None:
        self._consumer.close()
