"""
SYNAPSE Digital Twin — Kafka sync layer tests.

Covers Kafka subscription, message processing, and sync lifecycle.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

from digital_twin.sync.kafka_sync import SYNAPSE_STATE_TOPICS, TwinKafkaSync

if TYPE_CHECKING:
    from digital_twin.config import TwinConfig


class TestTwinKafkaSync:
    """Tests for TwinKafkaSync Kafka subscription and graph updates."""

    def test_subscribes_to_all_state_topics(
        self,
        twin_config: TwinConfig,
        mock_neo4j_driver: MagicMock,
        mock_kafka_consumer: MagicMock,
    ) -> None:
        """Sync should subscribe to all 8 synapse.*.state topics."""
        sync = TwinKafkaSync(config=twin_config)
        assert sync._topics == SYNAPSE_STATE_TOPICS
        assert len(sync._topics) == 8

    def test_process_message_updates_graph(
        self,
        twin_config: TwinConfig,
        mock_neo4j_driver: MagicMock,
        mock_kafka_consumer: MagicMock,
    ) -> None:
        """A valid state message should trigger a graph node update."""
        sync = TwinKafkaSync(config=twin_config)
        mock_graph = MagicMock()
        sync._graph = mock_graph

        message = {
            "agent_name": "demand_prophet",
            "confidence": 0.95,
            "forecast_drift": False,
        }
        sync._process_message(message)

        mock_graph.update_node.assert_called_once_with(
            node_id="demand_prophet",
            properties={"confidence": 0.95, "forecast_drift": False},
        )

    def test_process_message_skips_no_id(
        self,
        twin_config: TwinConfig,
        mock_neo4j_driver: MagicMock,
        mock_kafka_consumer: MagicMock,
    ) -> None:
        """Messages without agent_name or node_id should be skipped."""
        sync = TwinKafkaSync(config=twin_config)
        mock_graph = MagicMock()
        sync._graph = mock_graph

        sync._process_message({"value": 42})

        mock_graph.update_node.assert_not_called()

    def test_start_stop_lifecycle(
        self,
        twin_config: TwinConfig,
        mock_neo4j_driver: MagicMock,
        mock_kafka_consumer: MagicMock,
    ) -> None:
        """Sync should start and stop gracefully."""
        sync = TwinKafkaSync(config=twin_config)

        assert not sync.is_running

        sync.start()
        assert sync.is_running

        sync.stop()
        assert not sync.is_running
        mock_kafka_consumer.close.assert_called_once()

    def test_all_topics_follow_naming_convention(self) -> None:
        """All state topics must follow synapse.<agent>.state naming."""
        for topic in SYNAPSE_STATE_TOPICS:
            parts = topic.split(".")
            assert len(parts) == 3, f"Bad topic format: {topic}"
            assert parts[0] == "synapse"
            assert parts[2] == "state"
