"""I-12 integration: the TwinKafkaSync -> DivergenceMonitor edge (Plan v2 Phase 3).

Before this wiring `DivergenceMonitor.update_live_state` had no production caller
(verified by grep), so KL divergence was never computed from the live Kafka
stream and `synapse_digital_twin_kl_divergence` never emitted. These tests prove
the edge: a state message with a `state_distribution` updates live state, runs a
KL check against the twin's expected distribution, emits the metric, and fires
the re-sync alert above threshold (INV-TW-003).
"""

from __future__ import annotations

from unittest.mock import MagicMock

import numpy as np
import pytest

from digital_twin.config import TwinConfig
from digital_twin.sync.divergence_monitor import DivergenceMonitor
from digital_twin.sync.kafka_sync import TwinKafkaSync
from synapse_common.metrics import DIGITAL_TWIN_KL_DIVERGENCE


@pytest.fixture()
def monitor(twin_config: TwinConfig, mock_kafka_producer: MagicMock) -> DivergenceMonitor:
    return DivergenceMonitor(config=twin_config, producer=mock_kafka_producer)


def test_state_message_updates_live_and_emits_metric(
    twin_config: TwinConfig,
    mock_neo4j_driver: MagicMock,
    mock_kafka_consumer: MagicMock,
    mock_kafka_producer: MagicMock,
    monitor: DivergenceMonitor,
) -> None:
    # Twin expects a near-uniform distribution; the live message is identical,
    # so KL ~ 0 and no alert fires — but the metric must still be emitted.
    twin_dist = np.array([0.25, 0.25, 0.25, 0.25])
    monitor.update_twin_state("demand_prophet", twin_dist)

    sync = TwinKafkaSync(config=twin_config, divergence_monitor=monitor)
    sync._graph = MagicMock()

    sync._process_message(
        {"agent_name": "demand_prophet", "state_distribution": [0.25, 0.25, 0.25, 0.25]}
    )

    assert "demand_prophet" in monitor.last_divergence
    assert monitor.last_divergence["demand_prophet"] == pytest.approx(0.0, abs=1e-9)
    # Metric emitted (gauge value readable back).
    val = DIGITAL_TWIN_KL_DIVERGENCE.labels(agent_name="demand_prophet")._value.get()
    assert val == pytest.approx(0.0, abs=1e-9)
    mock_kafka_producer.produce.assert_not_called()  # KL=0 < threshold


def test_divergent_live_state_fires_resync_alert(
    twin_config: TwinConfig,
    mock_neo4j_driver: MagicMock,
    mock_kafka_consumer: MagicMock,
    mock_kafka_producer: MagicMock,
    monitor: DivergenceMonitor,
) -> None:
    # Twin expects mass on state 0; live reports mass on state 3 — large KL.
    monitor.update_twin_state("pricing_oracle", np.array([0.97, 0.01, 0.01, 0.01]))

    sync = TwinKafkaSync(config=twin_config, divergence_monitor=monitor)
    sync._graph = MagicMock()
    sync._process_message(
        {"agent_name": "pricing_oracle", "state_distribution": [0.01, 0.01, 0.01, 0.97]}
    )

    kl = monitor.last_divergence["pricing_oracle"]
    assert kl > 0.1  # above re-sync threshold
    # Alert published to synapse.twin.divergence (INV-TW-003).
    mock_kafka_producer.produce.assert_called_once()
    _, kwargs = mock_kafka_producer.produce.call_args
    assert kwargs["topic"] == "synapse.twin.divergence"
    assert kwargs["key"] == "pricing_oracle"


def test_message_without_distribution_is_graph_only(
    twin_config: TwinConfig,
    mock_neo4j_driver: MagicMock,
    mock_kafka_consumer: MagicMock,
    monitor: DivergenceMonitor,
) -> None:
    """A plain state update (no distribution) updates the graph but does not
    invoke the divergence path — the edge is opt-in per message."""
    sync = TwinKafkaSync(config=twin_config, divergence_monitor=monitor)
    sync._graph = MagicMock()
    sync._process_message({"agent_name": "demand_prophet", "confidence": 0.9})
    sync._graph.update_node.assert_called_once()
    assert "demand_prophet" not in monitor.last_divergence


def test_no_monitor_is_safe(
    twin_config: TwinConfig,
    mock_neo4j_driver: MagicMock,
    mock_kafka_consumer: MagicMock,
) -> None:
    """Sync without a monitor still works (backward compatible)."""
    sync = TwinKafkaSync(config=twin_config)
    sync._graph = MagicMock()
    sync._process_message(
        {"agent_name": "demand_prophet", "state_distribution": [0.5, 0.5]}
    )
    sync._graph.update_node.assert_called_once()  # no crash, graph still updated
