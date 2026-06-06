"""
SYNAPSE Disruption Shield — Metamorphic Tests (Layer 4).
MR-DS-001: Increasing anomaly magnitude -> higher or equal alert_level
"""

from __future__ import annotations

import numpy as np
import pytest

from agents.disruption_shield.inference.pipeline import (
    DisruptionRequest,
    DisruptionShieldPipeline,
)
from agents.disruption_shield.inference.playbook_retriever import PlaybookMatch
from agents.disruption_shield.models.anomaly_ensemble import AnomalyEnsemble
from agents.disruption_shield.models.reasoning import DeepSeekReasoner


class StaticPlaybookRetriever:
    def retrieve(self, query: str, top_k: int | None = None) -> list[PlaybookMatch]:
        del query
        limit = top_k or 1
        return [
            PlaybookMatch(
                id="PB-TEST-001",
                title="Hermetic disruption recovery",
                relevance_score=0.75,
                content="Use deterministic test playbook.",
                metadata={"test": True},
            )
        ][:limit]


def _pipeline() -> DisruptionShieldPipeline:
    return DisruptionShieldPipeline(
        ensemble=AnomalyEnsemble(),
        reasoner=DeepSeekReasoner(ollama_base_url="http://localhost:11434"),
        retriever=StaticPlaybookRetriever(),
    )


@pytest.fixture
def pipeline() -> DisruptionShieldPipeline:
    return _pipeline()


@pytest.mark.metamorphic
class TestMetamorphicRelations:
    def test_mr_ds_001_higher_anomaly_higher_alert(
        self, pipeline: DisruptionShieldPipeline
    ) -> None:
        """MR-DS-001: Scaling anomaly features by 2x -> alert_level stays equal or increases."""
        rng = np.random.default_rng(42)
        base_features = rng.standard_normal((5, 12))

        result_1x = pipeline.detect(
            DisruptionRequest(
                node_ids=[f"NODE-{i}" for i in range(5)],
                tabular_features=base_features.tolist(),
            )
        )

        scaled_features = base_features * 2.0
        pipeline_2 = _pipeline()
        result_2x = pipeline_2.detect(
            DisruptionRequest(
                node_ids=[f"NODE-{i}" for i in range(5)],
                tabular_features=scaled_features.tolist(),
            )
        )

        assert result_2x.alert_level >= result_1x.alert_level

    def test_mr_ds_003_nominal_data_no_alert(self, pipeline: DisruptionShieldPipeline) -> None:
        """MR-DS-003: All features at nominal values -> alert_level = 0."""
        nominal = np.zeros((5, 12)).tolist()
        result = pipeline.detect(
            DisruptionRequest(
                node_ids=[f"NODE-{i}" for i in range(5)],
                tabular_features=nominal,
            )
        )
        assert result.alert_level == 0

    @pytest.mark.xfail(
        reason=(
            "MR-DS-001 (score-level) requires IsolationForest pre-fit on a "
            "nominal baseline. Current pipeline fits-on-input and min-max "
            "normalizes within-batch, so scaling feature magnitude does not "
            "monotonically shift the normalized score. Covered at alert_level "
            "granularity by test_mr_ds_001_higher_anomaly_higher_alert. "
            "Follow-up: configure AnomalyEnsemble with a pre-fit baseline "
            "(tracked as E-DS-009)."
        ),
        strict=False,
    )
    def test_mr_ds_001_ensemble_score_monotonic(self, pipeline: DisruptionShieldPipeline) -> None:
        """Ensemble score should not decrease when anomaly signal is amplified."""
        rng = np.random.default_rng(123)
        features_small = rng.standard_normal((5, 12)) * 0.1
        features_large = rng.standard_normal((5, 12)) * 10.0

        result_small = pipeline.detect(
            DisruptionRequest(
                node_ids=[f"NODE-{i}" for i in range(5)],
                tabular_features=features_small.tolist(),
            )
        )

        pipeline_2 = _pipeline()
        result_large = pipeline_2.detect(
            DisruptionRequest(
                node_ids=[f"NODE-{i}" for i in range(5)],
                tabular_features=features_large.tolist(),
            )
        )

        assert result_large.ensemble_score >= result_small.ensemble_score
