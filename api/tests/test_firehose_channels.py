"""Firehose channel-map truth tests (ADR-044 D3).

The ``CHANNEL_TOPIC`` map is the FE's binding contract (channel names are
stable across versions). These tests pin:

  * the escalation channel exists and maps to the Sprint-1-frozen topic;
  * every channel's Kafka topic is REGISTERED in topics.json with
    ``api_firehose`` in its consumers — the registry/code drift that WS-3
    (ADR-038) exists to kill cannot re-arm through this map.
"""

from __future__ import annotations

import json
from pathlib import Path

from api.routers.firehose import CHANNEL_TOPIC

_ROOT = Path(__file__).resolve().parents[2]
_REGISTRY = _ROOT / "infrastructure" / "kafka" / "topics.json"


def _registry_topics() -> dict[str, dict[str, object]]:
    registry = json.loads(_REGISTRY.read_text(encoding="utf-8"))
    return {entry["name"]: entry for entry in registry["topics"]}


def test_escalation_channel_maps_to_frozen_topic() -> None:
    assert CHANNEL_TOPIC["escalation"] == "synapse.orchestrator.escalation"


def test_every_channel_topic_is_registered() -> None:
    registered = _registry_topics()
    unregistered = [t for t in CHANNEL_TOPIC.values() if t not in registered]
    assert not unregistered, (
        f"firehose consumes unregistered topics {unregistered} — add them to "
        "infrastructure/kafka/topics.json (ADR-038 truth)"
    )


def test_api_firehose_declared_consumer_for_every_channel() -> None:
    registered = _registry_topics()
    missing = [
        topic
        for topic in CHANNEL_TOPIC.values()
        if "api_firehose" not in registered[topic].get("consumers", [])
    ]
    assert not missing, (
        f"topics consumed by the firehose but not declaring api_firehose: {missing}"
    )


def test_channel_names_are_stable() -> None:
    """FE binds to these keys; removal is a breaking contract change."""
    assert {
        "decision",
        "disruption",
        "routing",
        "metric",
        "twin",
        "demand",
        "freshness",
        "pricing",
        "escalation",
    } <= set(CHANNEL_TOPIC)
