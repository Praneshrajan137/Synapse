"""Kafka per-topic retention contract test (Sprint 9 §M-life-2).

Reads ``infrastructure/kafka/topics.json`` and asserts each topic's
``retention_hours * 3.6e6`` matches the live broker's ``retention.ms``.
Marked ``@pytest.mark.integration`` because it needs a Kafka admin
client; CI runs it against the docker-compose stack.

When Kafka is unreachable (no admin client, no broker), the test is
SKIPPED rather than failed — this keeps local pytest runs green for
contributors without infra.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
TOPICS_JSON = REPO_ROOT / "infrastructure" / "kafka" / "topics.json"


def _registered_topics() -> dict[str, int]:
    """Map topic name → declared retention_hours from topics.json."""
    data = json.loads(TOPICS_JSON.read_text(encoding="utf-8"))
    return {entry["name"]: int(entry["retention_hours"]) for entry in data["topics"]}


@pytest.mark.integration
@pytest.mark.contract
def test_kafka_topic_retention_matches_registry() -> None:
    registered = _registered_topics()
    try:
        from confluent_kafka.admin import RESOURCE_TOPIC, AdminClient, ConfigResource
    except ImportError:
        pytest.skip("confluent_kafka admin client unavailable")

    import os

    bootstrap = os.environ.get("KAFKA_BOOTSTRAP", "localhost:9092")
    try:
        client = AdminClient({"bootstrap.servers": bootstrap})
        cluster = client.list_topics(timeout=5)
    except Exception:  # noqa: BLE001
        pytest.skip(f"Kafka unreachable at {bootstrap}")
    live_topics = set(cluster.topics.keys())
    missing = [t for t in registered if t not in live_topics]
    if missing:
        pytest.skip(f"topics not provisioned yet: {missing}")

    drift: list[str] = []
    for topic, retention_hours in registered.items():
        expected_ms = -1 if retention_hours == -1 else retention_hours * 3_600_000
        resource = ConfigResource(RESOURCE_TOPIC, topic)
        futures = client.describe_configs([resource])
        config = futures[resource].result(timeout=10)
        actual = config.get("retention.ms")
        if actual is None:
            drift.append(f"{topic}: retention.ms not present in broker config")
            continue
        actual_value = int(actual.value)
        if actual_value != expected_ms:
            drift.append(f"{topic}: expected={expected_ms} actual={actual_value}")
    assert not drift, "Kafka topic retention drift:\n" + "\n".join(drift)
