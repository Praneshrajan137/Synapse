"""
SYNAPSE Supplier Trust -- Consumer-Driven Contract Tests (Layer 3).
Verifies that Supplier Trust outputs satisfy consumer expectations.

Consumers:
  - Inventory Sentinel: expects trust_score in [0, 1], lead_time_posterior
  - Disruption Shield: expects trust_score, supplier_id, is_new_vendor
"""
from __future__ import annotations

import pytest

from agents.supplier_trust.inference.pipeline import (
    SupplierTrustPipeline,
    TrustScoreResult,
)


@pytest.fixture
def pipeline() -> SupplierTrustPipeline:
    return SupplierTrustPipeline()


def _make_delivery_history(n: int, on_time: bool = True) -> list[dict[str, object]]:
    return [{"lead_time_days": 3.0 + i * 0.1, "on_time": on_time} for i in range(n)]


@pytest.mark.contract
class TestInventorySentinelContract:
    """Inventory Sentinel expects: trust_score in [0, 1], lead_time_posterior with mean/std/p10/p90."""

    def test_trust_score_bounded(self, pipeline: SupplierTrustPipeline) -> None:
        result = pipeline.score(
            supplier_id="SUP-001",
            delivery_history=_make_delivery_history(10),
        )
        assert 0.0 <= result.trust_score <= 1.0

    def test_lead_time_posterior_fields(self, pipeline: SupplierTrustPipeline) -> None:
        result = pipeline.score(
            supplier_id="SUP-002",
            delivery_history=_make_delivery_history(10),
        )
        posterior = result.lead_time_posterior
        assert "mean_days" in posterior
        assert "std_days" in posterior
        assert "p10_days" in posterior
        assert "p90_days" in posterior

    def test_lead_time_posterior_std_positive(self, pipeline: SupplierTrustPipeline) -> None:
        """INV-ST-003: std_days > 0."""
        result = pipeline.score(
            supplier_id="SUP-003",
            delivery_history=_make_delivery_history(10),
        )
        assert result.lead_time_posterior["std_days"] > 0

    def test_confidence_bounded(self, pipeline: SupplierTrustPipeline) -> None:
        result = pipeline.score(
            supplier_id="SUP-004",
            delivery_history=_make_delivery_history(10),
        )
        assert 0.0 <= result.confidence <= 1.0


@pytest.mark.contract
class TestDisruptionShieldContract:
    """Disruption Shield expects: supplier_id, trust_score, is_new_vendor flag."""

    def test_output_has_required_fields(self, pipeline: SupplierTrustPipeline) -> None:
        result = pipeline.score(
            supplier_id="SUP-010",
            delivery_history=_make_delivery_history(5),
        )
        assert result.supplier_id == "SUP-010"
        assert isinstance(result.trust_score, float)
        assert isinstance(result.is_new_vendor, bool)

    def test_new_vendor_flag(self, pipeline: SupplierTrustPipeline) -> None:
        result = pipeline.score(
            supplier_id="SUP-NEW",
            delivery_history=[],
            is_new_vendor=True,
        )
        assert result.is_new_vendor is True
        assert result.trust_score >= 0.3


@pytest.mark.contract
class TestNewVendorTrustFloor:
    """INV-ST-001: New vendors must have trust_score >= 0.3."""

    def test_new_vendor_floor(self, pipeline: SupplierTrustPipeline) -> None:
        result = pipeline.score(
            supplier_id="SUP-BRAND-NEW",
            delivery_history=[],
            is_new_vendor=True,
        )
        assert result.trust_score >= 0.3
