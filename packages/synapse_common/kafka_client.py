"""
SYNAPSE Kafka Client — Unified producer/consumer with schema validation (I-3).
All agents use this client. Direct kafka-python usage is a PR rejection.

Sprint 7 (WS-2) addition: every produced message carries W3C trace-context
headers so a single ``trace_id`` flows API -> orchestrator -> A2A -> Kafka
-> consumers -> twin -> audit. The consumer side exposes
``poll_with_context()`` so callers can attach the extracted span context
to their work and produce continuation spans.
"""

from __future__ import annotations

import json
from typing import Any

import structlog
from confluent_kafka import Consumer, Producer
from pydantic import BaseModel

logger = structlog.get_logger(__name__)

SERIALIZATION_KWARGS: dict[str, Any] = {
    "sort_keys": True,
    "separators": (",", ":"),
    "default": str,
}

# Header keys we consider trace-context. We accept both W3C and B3 (so the
# client interoperates with services that emit either).
_TRACE_HEADER_KEYS: frozenset[str] = frozenset(
    {
        "traceparent",
        "tracestate",
        "b3",
        "x-b3-traceid",
        "x-b3-spanid",
        "x-b3-sampled",
        "x-b3-parentspanid",
    }
)


class KafkaConfig(BaseModel):
    """Kafka connection configuration."""

    bootstrap_servers: str = "localhost:9092"
    group_id: str = "synapse-default"
    auto_offset_reset: str = "earliest"
    enable_auto_commit: bool = True


def _inject_trace_headers() -> dict[str, str]:
    """Pull the active OTel context into a W3C traceparent/tracestate dict."""
    try:
        from opentelemetry.propagate import inject
    except Exception:  # noqa: BLE001 — OTel optional in tests/CI strip-down
        return {}
    carrier: dict[str, str] = {}
    try:
        inject(carrier)
    except Exception as exc:  # noqa: BLE001
        logger.debug("kafka_trace_inject_failed", error=str(exc))
        return {}
    return carrier


def _encode_headers(headers: dict[str, str] | None) -> list[tuple[str, bytes]]:
    if not headers:
        return []
    return [(k, v.encode("utf-8")) for k, v in headers.items()]


def _decode_headers(raw: Any) -> dict[str, str]:
    """Best-effort decode of confluent_kafka headers into a str/str dict."""
    if not raw:
        return {}
    out: dict[str, str] = {}
    for entry in raw:
        try:
            key, value = entry
        except (TypeError, ValueError):
            continue
        if isinstance(value, bytes):
            try:
                out[key] = value.decode("utf-8")
            except UnicodeDecodeError:
                continue
        elif isinstance(value, str):
            out[key] = value
    return out


class SynapseProducer:
    """Thread-safe Kafka producer with deterministic serialization + trace headers."""

    def __init__(self, config: KafkaConfig) -> None:
        self._producer = Producer(
            {
                "bootstrap.servers": config.bootstrap_servers,
                "message.max.bytes": 10485760,
            }
        )
        self._config = config

    def produce(
        self,
        topic: str,
        value: dict[str, Any] | BaseModel,
        key: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        """Produce a message with deterministic JSON + W3C trace headers (I-13).

        Args:
            topic: Registered Kafka topic name (CI enforces it exists).
            value: Pydantic model or dict; serialised with sort_keys.
            key: Partition key.
            headers: Optional caller-supplied headers (e.g. ``Idempotency-Key``).
                W3C ``traceparent``/``tracestate`` are auto-injected from the
                active OpenTelemetry context and merged with these.
        """
        if isinstance(value, BaseModel):
            serialized = json.dumps(value.model_dump(mode="json"), **SERIALIZATION_KWARGS)
        else:
            serialized = json.dumps(value, **SERIALIZATION_KWARGS)

        merged_headers: dict[str, str] = dict(headers or {})
        # Auto-inject trace context. Caller-supplied trace headers win on a
        # tie because the caller may be replaying a known trace.
        for k, v in _inject_trace_headers().items():
            merged_headers.setdefault(k, v)

        self._producer.produce(
            topic=topic,
            value=serialized.encode("utf-8"),
            key=key.encode("utf-8") if key else None,
            headers=_encode_headers(merged_headers),  # type: ignore[arg-type]
        )
        self._producer.flush(timeout=5.0)

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
        """Poll for next message, return deserialized dict or None.

        Trace headers are silently dropped here; use ``poll_with_context`` if
        you need them.
        """
        result = self.poll_with_context(timeout=timeout)
        return result[0] if result is not None else None

    def poll_with_context(
        self,
        timeout: float = 1.0,
    ) -> tuple[dict[str, Any], dict[str, str]] | None:
        """Poll and return ``(payload, trace_headers)`` for trace-aware consumers.

        ``trace_headers`` contains every W3C / B3 trace-context header
        observed on the message (``traceparent``, ``tracestate``,
        ``x-b3-*``). Pass it to the OTel propagator's ``extract()`` to
        attach this span to its parent.
        """
        msg = self._consumer.poll(timeout)
        if msg is None or msg.error():
            return None
        try:
            raw: dict[str, Any] = json.loads(msg.value().decode("utf-8"))  # type: ignore[union-attr]
        except (json.JSONDecodeError, AttributeError) as e:
            logger.error("kafka_deserialize_failed", error=str(e))
            return None
        try:
            headers = _decode_headers(msg.headers())
        except Exception as exc:  # noqa: BLE001
            logger.warning("kafka_headers_decode_failed", error=str(exc))
            headers = {}
        return raw, headers

    @staticmethod
    def trace_headers_only(headers: dict[str, str]) -> dict[str, str]:
        """Filter a headers dict down to recognised trace-context keys."""
        return {k: v for k, v in headers.items() if k in _TRACE_HEADER_KEYS}

    def close(self) -> None:
        self._consumer.close()
