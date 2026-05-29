"""
SYNAPSE Digital Twin — Kafka state synchronization.

Subscribes to ALL synapse.*.state topics and mirrors live agent states
into the Neo4j supply-network graph in real-time.
"""
from __future__ import annotations

import json
import threading
from typing import TYPE_CHECKING, Any

import numpy as np
import structlog

from digital_twin.config import TwinConfig
from digital_twin.graph.supply_network import SupplyNetworkGraph
from synapse_common.kafka_client import KafkaConfig, SynapseConsumer

if TYPE_CHECKING:
    from digital_twin.sync.divergence_monitor import DivergenceMonitor

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
        divergence_monitor: DivergenceMonitor | None = None,
    ) -> None:
        self._config = config or TwinConfig()
        self._graph = graph or SupplyNetworkGraph(self._config)
        self._topics = topics or SYNAPSE_STATE_TOPICS
        # Plan v2 / Phase 3: the previously-missing I-12 edge. When a monitor is
        # supplied, every state message also updates the live distribution and
        # triggers a KL-divergence check, emitting synapse_digital_twin_kl_divergence.
        self._divergence_monitor = divergence_monitor
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

        properties = {
            k: v for k, v in message.items() if k not in ("agent_name", "node_id")
        }
        self._graph.update_node(node_id=str(node_id), properties=properties)
        logger.debug("kafka_sync_applied", node_id=node_id)

        self._update_divergence(str(node_id), message)

    def _update_divergence(self, agent_name: str, message: dict[str, Any]) -> None:
        """Feed the live agent-state distribution into the divergence monitor (I-12).

        A state message may carry an explicit ``state_distribution`` (list of
        floats) — the agent's reported state histogram. When present we update
        the monitor's live state and run a KL check, which emits the metric and
        fires the re-sync alert above threshold. No-op when no monitor is wired
        or the message carries no distribution (keeps non-distribution state
        updates cheap).
        """
        if self._divergence_monitor is None:
            return
        dist = message.get("state_distribution")
        if dist is None:
            return
        try:
            live = np.asarray(dist, dtype=np.float64)
            self._divergence_monitor.update_live_state(agent_name, live)
            self._divergence_monitor.check_divergence(agent_name)
        except Exception as exc:  # noqa: BLE001 — monitoring must never break sync (I-7)
            logger.warning("divergence_update_failed", agent=agent_name, error=str(exc))

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
        self._thread = threading.Thread(
            target=self._poll_loop, name="twin-kafka-sync", daemon=True
        )
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
