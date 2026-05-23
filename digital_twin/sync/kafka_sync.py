"""
SYNAPSE Digital Twin — Kafka state synchronization.

Subscribes to ALL synapse.*.state topics and mirrors live agent states
into the Neo4j supply-network graph in real-time.
"""

from __future__ import annotations

import threading
from typing import Any

import structlog
from synapse_common.kafka_client import KafkaConfig, SynapseConsumer

from digital_twin.config import TwinConfig
from digital_twin.graph.supply_network import SupplyNetworkGraph

logger = structlog.get_logger(__name__)

SYNAPSE_STATE_TOPICS: list[str] = [
    "synapse.demand_prophet.state",
    "synapse.routing_navigator.state",
    "synapse.inventory_sentinel.state",
    "synapse.freshness_guardian.state",
    "synapse.pricing_oracle.state",
    "synapse.disruption_shield.state",
    "synapse.supplier_trust.state",
    "synapse.sustainability_agent.state",
]


class TwinKafkaSync:
    """Subscribes to all synapse.*.state topics and updates Neo4j graph.

    INV-TW-001: Keeps twin within 5% divergence at steady state by
    applying every state update to the graph in real-time.
    """

    def __init__(
        self,
        config: TwinConfig | None = None,
        graph: SupplyNetworkGraph | None = None,
        topics: list[str] | None = None,
    ) -> None:
        self._config = config or TwinConfig()
        self._graph = graph or SupplyNetworkGraph(self._config)
        self._topics = topics or SYNAPSE_STATE_TOPICS
        self._running = False
        self._thread: threading.Thread | None = None

        kafka_cfg = KafkaConfig(
            bootstrap_servers=self._config.kafka_bootstrap,
            group_id=self._config.kafka_group_id,
        )
        self._consumer = SynapseConsumer(config=kafka_cfg, topics=self._topics)

        logger.info(
            "kafka_sync_init",
            topics=self._topics,
            group_id=self._config.kafka_group_id,
        )

    def _process_message(self, message: dict[str, Any]) -> None:
        """Apply a state-update message to the Neo4j graph."""
        node_id = message.get("agent_name") or message.get("node_id")
        if not node_id:
            logger.warning("kafka_sync_skip_no_id", message_keys=list(message.keys()))
            return

        properties = {k: v for k, v in message.items() if k not in ("agent_name", "node_id")}
        self._graph.update_node(node_id=str(node_id), properties=properties)
        logger.debug("kafka_sync_applied", node_id=node_id)

    def _poll_loop(self) -> None:
        """Continuous polling loop running in a background thread."""
        while self._running:
            message = self._consumer.poll(timeout=1.0)
            if message is not None:
                self._process_message(message)

    def start(self) -> None:
        """Start the background sync thread."""
        if self._running:
            logger.warning("kafka_sync_already_running")
            return
        self._running = True
        self._thread = threading.Thread(target=self._poll_loop, name="twin-kafka-sync", daemon=True)
        self._thread.start()
        logger.info("kafka_sync_started")

    def stop(self) -> None:
        """Gracefully stop the sync thread and close resources."""
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=10.0)
        self._consumer.close()
        logger.info("kafka_sync_stopped")

    @property
    def is_running(self) -> bool:
        return self._running
