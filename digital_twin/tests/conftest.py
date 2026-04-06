"""
SYNAPSE Digital Twin — Shared test fixtures.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from digital_twin.config import TwinConfig


@pytest.fixture()
def twin_config() -> TwinConfig:
    """Minimal TwinConfig for unit tests."""
    return TwinConfig(
        neo4j_uri="bolt://localhost:7687",
        kafka_bootstrap="localhost:9092",
        simpy_default_duration_hours=1,
        monte_carlo_min_scenarios=1000,
        monte_carlo_max_workers=2,
    )


@pytest.fixture()
def mock_neo4j_driver() -> MagicMock:
    """Mock Neo4j driver to avoid real DB connections in tests."""
    with patch("digital_twin.graph.supply_network.GraphDatabase") as mock_gdb:
        mock_driver = MagicMock()
        mock_gdb.driver.return_value = mock_driver
        yield mock_driver


@pytest.fixture()
def mock_kafka_consumer() -> MagicMock:
    """Mock SynapseConsumer for sync tests."""
    with patch("digital_twin.sync.kafka_sync.SynapseConsumer") as mock_cls:
        mock_consumer = MagicMock()
        mock_cls.return_value = mock_consumer
        yield mock_consumer


@pytest.fixture()
def mock_kafka_producer() -> MagicMock:
    """Mock SynapseProducer for divergence tests."""
    return MagicMock()


@pytest.fixture()
def sample_distributions() -> tuple[np.ndarray, np.ndarray]:
    """Two probability distributions for divergence testing."""
    rng = np.random.default_rng(42)
    p = rng.dirichlet(np.ones(10))
    q = rng.dirichlet(np.ones(10))
    return p, q
