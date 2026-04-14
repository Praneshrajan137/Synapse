"""
SYNAPSE Freshness Guardian — Consumer-Driven Contract Tests (Layer 3).
Verifies that Freshness Guardian outputs satisfy consumer expectations.

Consumers:
  - Pricing Oracle: expects approaching-expiry SKU list
  - Inventory Sentinel: expects quality_score, markdown_applied
"""

from __future__ import annotations

import pytest

from agents.freshness_guardian.inference.pipeline import (
    FreshnessGuardianPipeline,
    FreshnessRequest,
)


@pytest.fixture
def pipeline() -> FreshnessGuardianPipeline:
    return FreshnessGuardianPipeline()


@pytest.mark.contract
class TestPricingOracleContract:
    """Pricing Oracle expects: days_to_expiry, quality_score, markdown_applied."""

    def test_output_has_required_fields(self, pipeline: FreshnessGuardianPipeline) -> None:
        result = pipeline.assess(
            FreshnessRequest(
                store_id="BLR-DS-001",
                sku_id="SKU-0001",
                days_since_receipt=5.0,
                initial_shelf_life_days=7,
            )
        )
        assert hasattr(result, "days_to_expiry")
        assert hasattr(result, "quality_score")
        assert hasattr(result, "markdown_applied")
        assert result.days_to_expiry >= 0
        assert 0 <= result.quality_score <= 1
        assert isinstance(result.markdown_applied, bool)


@pytest.mark.contract
class TestInventorySentinelContract:
    """Inventory Sentinel expects: quality_score in [0,1], markdown_applied boolean."""

    def test_quality_score_bounded(self, pipeline: FreshnessGuardianPipeline) -> None:
        result = pipeline.assess(
            FreshnessRequest(
                store_id="BLR-DS-001",
                sku_id="SKU-0042",
                days_since_receipt=3.0,
                initial_shelf_life_days=5,
                temperature_deviation_hours=2.0,
            )
        )
        assert 0 <= result.quality_score <= 1
        assert isinstance(result.markdown_applied, bool)
