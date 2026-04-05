"""
SYNAPSE Kafka Client — Unified producer/consumer with schema validation (I-3).
All agents use this client. Direct kafka-python usage is a PR rejection.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from confluent_kafka import Consumer, Producer
from pydantic import BaseModel

logger = logging.getLogger(__name__)

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


class SynapseProducer:
    """Thread-safe Kafka producer with deterministic serialization."""

    def __init__(self, config: KafkaConfig) -> None:
        self._producer = Producer({
            "bootstrap.servers": config.bootstrap_servers,
            "message.max.bytes": 10485760,
        })
        self._config = config

    def produce(
        self,
        topic: str,
        value: dict[str, Any] | BaseModel,
        key: str | None = None,
    ) -> None:
        """Produce message with deterministic JSON serialization (I-13)."""
        if isinstance(value, BaseModel):
            serialized = json.dumps(
                value.model_dump(mode="json"), **SERIALIZATION_KWARGS
            )
        else:
            serialized = json.dumps(value, **SERIALIZATION_KWARGS)

        self._producer.produce(
            topic=topic,
            value=serialized.encode("utf-8"),
            key=key.encode("utf-8") if key else None,
        )
        self._producer.flush(timeout=5.0)

    def close(self) -> None:
        self._producer.flush(timeout=10.0)


class SynapseConsumer:
    """Kafka consumer with type-safe deserialization."""

    def __init__(self, config: KafkaConfig, topics: list[str]) -> None:
        self._consumer = Consumer({
            "bootstrap.servers": config.bootstrap_servers,
            "group.id": config.group_id,
            "auto.offset.reset": config.auto_offset_reset,
            "enable.auto.commit": config.enable_auto_commit,
        })
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
            logger.error("Failed to deserialize Kafka message: %s", e)
            return None

    def close(self) -> None:
        self._consumer.close()
