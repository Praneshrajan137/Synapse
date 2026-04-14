"""
SYNAPSE Disruption Shield — Consumer-Driven Contract Tests (Layer 3).
Verifies that Disruption Shield outputs satisfy consumer expectations.

Consumers:
  - Inventory Sentinel: expects alert_level and affected nodes for stock adjustment
  - Routing Navigator: expects disruption severity for route replanning
"""

from __future__ import annotations

import numpy as np
import pytest

from agents.disruption_shield.inference.pipeline import (
    DisruptionRequest,
    DisruptionShieldPipeline,
)
from agents.disruption_shield.models.anomaly_ensemble import AnomalyEnsemble
from agents.disruption_shield.models.reasoning import DeepSeekReasoner


@pytest.fixture
def pipeline() -> DisruptionShieldPipeline:
    ensemble = AnomalyEnsemble()
    reasoner = DeepSeekReasoner(ollama_base_url="http://localhost:11434")
    return DisruptionShieldPipeline(ensemble=ensemble, reasoner=reasoner, retriever=None)


def _make_request(n_nodes: int = 5) -> DisruptionRequest:
    rng = np.random.default_rng(42)
    return DisruptionRequest(
        node_ids=[f"NODE-{i:03d}" for i in range(n_nodes)],
        tabular_features=rng.standard_normal((n_nodes, 12)).tolist(),
    )


@pytest.mark.contract
class TestInventorySentinelContract:
    """Inventory Sentinel expects: alert_level, anomalous_nodes, ensemble_score."""

    def test_output_has_required_fields(self, pipeline: DisruptionShieldPipeline) -> None:
        result = pipeline.detect(_make_request())
        assert hasattr(result, "alert_level")
        assert hasattr(result, "anomalous_nodes")
        assert hasattr(result, "ensemble_score")
        assert result.alert_level >= 0
        assert 0 <= result.ensemble_score <= 1
        assert isinstance(result.anomalous_nodes, list)

    def test_ensemble_score_bounded(self, pipeline: DisruptionShieldPipeline) -> None:
        result = pipeline.detect(_make_request(n_nodes=10))
        assert 0.0 <= result.ensemble_score <= 1.0


@pytest.mark.contract
class TestRoutingNavigatorContract:
    """Routing Navigator expects: severity, reasoning_chain, playbooks."""

    def test_output_has_severity_and_reasoning(self, pipeline: DisruptionShieldPipeline) -> None:
        result = pipeline.detect(_make_request())
        assert hasattr(result, "severity")
        assert hasattr(result, "reasoning_chain")
        assert hasattr(result, "playbooks")
        assert isinstance(result.reasoning_chain, list)
        assert len(result.reasoning_chain) > 0
        assert isinstance(result.playbooks, list)

    def test_alert_level_in_valid_range(self, pipeline: DisruptionShieldPipeline) -> None:
        result = pipeline.detect(_make_request())
        assert result.alert_level in {0, 1, 2, 3}

    def test_timestamp_is_iso8601(self, pipeline: DisruptionShieldPipeline) -> None:
        from datetime import datetime

        result = pipeline.detect(_make_request())
        datetime.fromisoformat(result.timestamp)
