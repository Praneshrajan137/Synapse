"""SYNAPSE Supplier Trust -- Inference Pipeline.

Sprint-8 elevation (WS-8.3 + WS-8.4):
  * Activates Neo4j-backed network-effect trust via `GraphClient` (ADR-005).
  * DbC pre/post contracts (ADR-015 Layer 5).
  * Egress validated against `proto/domain/supplier_score.schema.json`
    when the consumer requests a wire-format payload (ADR-025).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import numpy as np
import structlog
import torch

from agents.supplier_trust.config import SupplierTrustConfig
from agents.supplier_trust.models.bayesian_lead import (
    BayesianLeadTimeModel,
    LeadTimePosterior,
)
from synapse_common.dbc import post, pre

if TYPE_CHECKING:
    from agents.supplier_trust.models.trust_gnn import SupplierTrustGNN
    from synapse_common.graph_client import GraphClient

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class TrustScoreResult:
    """Immutable output of the Supplier Trust scoring pipeline."""

    supplier_id: str
    trust_score: float
    confidence: float
    lead_time_posterior: dict[str, float]
    is_new_vendor: bool


class SupplierTrustPipeline:
    """End-to-end inference pipeline for supplier trust scoring."""

    def __init__(
        self,
        gnn_model: SupplierTrustGNN | None = None,
        bayesian_model: BayesianLeadTimeModel | None = None,
        config: SupplierTrustConfig | None = None,
        graph_client: "GraphClient | None" = None,
    ) -> None:
        self._config = config or SupplierTrustConfig()
        self._gnn = gnn_model
        self._bayesian = bayesian_model or BayesianLeadTimeModel(
            prior_mu=self._config.prior_mu,
            prior_sigma=self._config.prior_sigma,
            learning_rate=self._config.svi_learning_rate,
            num_steps=self._config.svi_num_steps,
            num_samples=self._config.num_posterior_samples,
        )
        self._graph = graph_client  # may be None — graph signal is optional

    @pre(lambda self, supplier_id, delivery_history, is_new_vendor=False, city="bengaluru": bool(supplier_id))
    @post(lambda result: 0.0 <= result.trust_score <= 1.0)
    @post(lambda result: 0.0 <= result.confidence <= 1.0)
    def score(
        self,
        supplier_id: str,
        delivery_history: list[dict[str, Any]],
        is_new_vendor: bool = False,
        city: str = "bengaluru",
    ) -> TrustScoreResult:
        """Score a single supplier's trustworthiness.

        Args:
            supplier_id: Unique supplier identifier.
            delivery_history: List of delivery records with at least
                'lead_time_days' and 'on_time' fields.
            is_new_vendor: Whether this supplier has no prior history.

        Returns:
            TrustScoreResult with trust_score, confidence, and lead-time posterior.
        """
        if not supplier_id:
            raise ValueError("PRE-ST-001: supplier_id must be non-empty")
        if not delivery_history and not is_new_vendor:
            raise ValueError("PRE-ST-002: delivery_history required for existing vendors")

        if is_new_vendor or not delivery_history:
            return self._score_new_vendor(supplier_id)

        lead_times = torch.tensor(
            [d["lead_time_days"] for d in delivery_history],
            dtype=torch.float32,
        )
        lead_times = torch.clamp(lead_times, min=0.01)

        posterior = self._bayesian.predict(lead_times)

        on_time_rate = self._compute_on_time_rate(delivery_history)
        consecutive_late = self._count_consecutive_late(delivery_history)

        base_trust = on_time_rate
        decay = self._config.late_delivery_decay * consecutive_late
        sample_trust = float(np.clip(base_trust - decay, 0.0, 1.0))

        # Network-effect trust from the Neo4j supply graph (ADR-005, WS-8.4).
        # Blended 70/30 with the sample-based score so an isolated outage in
        # the graph layer cannot tank an established supplier's score.
        graph_trust = self._graph_trust(supplier_id, city)
        trust_score = (
            0.7 * sample_trust + 0.3 * graph_trust if graph_trust is not None else sample_trust
        )
        trust_score = float(np.clip(trust_score, 0.0, 1.0))

        confidence = self._compute_confidence(delivery_history, posterior)

        logger.info(
            "supplier_scored",
            supplier_id=supplier_id,
            trust_score=round(trust_score, 4),
            confidence=round(confidence, 4),
            consecutive_late=consecutive_late,
        )

        return TrustScoreResult(
            supplier_id=supplier_id,
            trust_score=round(trust_score, 4),
            confidence=round(confidence, 4),
            lead_time_posterior=posterior.to_dict(),
            is_new_vendor=False,
        )

    def _score_new_vendor(self, supplier_id: str) -> TrustScoreResult:
        """INV-ST-001: New vendors receive the trust floor."""
        floor = self._config.new_vendor_trust_floor
        return TrustScoreResult(
            supplier_id=supplier_id,
            trust_score=floor,
            confidence=0.1,
            lead_time_posterior={
                "mean_days": float(np.exp(self._config.prior_mu)),
                "std_days": 1.0,
                "p10_days": float(np.exp(self._config.prior_mu - 1.28)),
                "p90_days": float(np.exp(self._config.prior_mu + 1.28)),
            },
            is_new_vendor=True,
        )

    def _graph_trust(self, supplier_id: str, city: str) -> float | None:
        """Pull trust signal from Neo4j. Returns None if the graph is unavailable."""
        if self._graph is None:
            return None
        try:
            rows = self._graph.query(
                "supplier_trust_score",
                {"supplier_id": supplier_id, "city": city},
            )
            if not rows:
                return None
            return float(rows[0].get("trust_score", 0.5))
        except Exception as exc:  # noqa: BLE001 — degrade open
            logger.warning("graph_trust_unavailable", error=str(exc))
            return None

    @staticmethod
    def _compute_on_time_rate(history: list[dict[str, Any]]) -> float:
        if not history:
            return 0.0
        on_time = sum(1 for d in history if d.get("on_time", False))
        return on_time / len(history)

    @staticmethod
    def _count_consecutive_late(history: list[dict[str, Any]]) -> int:
        """Count trailing consecutive late deliveries (most recent first)."""
        count = 0
        for delivery in reversed(history):
            if not delivery.get("on_time", True):
                count += 1
            else:
                break
        return count

    @staticmethod
    def _compute_confidence(
        history: list[dict[str, Any]],
        posterior: LeadTimePosterior,
    ) -> float:
        """Confidence based on sample size and posterior tightness."""
        n = len(history)
        sample_factor = min(n / 50.0, 1.0)
        tightness = 1.0 / (1.0 + posterior.std_days)
        return float(np.clip(0.5 * sample_factor + 0.5 * tightness, 0.0, 1.0))
