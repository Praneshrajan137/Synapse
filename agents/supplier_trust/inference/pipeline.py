"""SYNAPSE Supplier Trust -- Inference Pipeline."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import structlog
import torch
from torch import Tensor

from agents.supplier_trust.config import SupplierTrustConfig
from agents.supplier_trust.models.bayesian_lead import (
    BayesianLeadTimeModel,
    LeadTimePosterior,
)
from agents.supplier_trust.models.trust_gnn import SupplierTrustGNN

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

    def score(
        self,
        supplier_id: str,
        delivery_history: list[dict[str, Any]],
        is_new_vendor: bool = False,
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
        trust_score = float(np.clip(base_trust - decay, 0.0, 1.0))

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
