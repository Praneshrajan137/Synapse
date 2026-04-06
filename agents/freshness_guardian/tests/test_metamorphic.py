"""
SYNAPSE Freshness Guardian — Metamorphic Tests (Layer 4).
MR-FG-001: days_to_expiry = 0 -> markdown_applied = True
MR-FG-002: Higher temperature deviation -> lower quality_score
MR-FG-003: Increasing shelf_life_days -> higher quality_score
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


@pytest.mark.metamorphic
class TestMetamorphicRelations:

    def test_mr_fg_001_expired_implies_markdown(
        self, pipeline: FreshnessGuardianPipeline
    ) -> None:
        """MR-FG-001: days_to_expiry = 0 -> markdown_applied = True."""
        result = pipeline.assess(FreshnessRequest(
            store_id="BLR-DS-001",
            sku_id="SKU-0001",
            days_since_receipt=7.0,
            initial_shelf_life_days=7,
        ))
        if result.days_to_expiry <= 0:
            assert result.markdown_applied is True

    def test_mr_fg_002_temp_deviation_reduces_quality(
        self, pipeline: FreshnessGuardianPipeline
    ) -> None:
        """MR-FG-002: Higher temp deviation -> lower quality_score."""
        result_good = pipeline.assess(FreshnessRequest(
            store_id="BLR-DS-001",
            sku_id="SKU-0001",
            days_since_receipt=3.0,
            initial_shelf_life_days=7,
            temperature_deviation_hours=0.0,
        ))
        result_bad = pipeline.assess(FreshnessRequest(
            store_id="BLR-DS-001",
            sku_id="SKU-0001",
            days_since_receipt=3.0,
            initial_shelf_life_days=7,
            temperature_deviation_hours=12.0,
        ))
        assert result_bad.quality_score <= result_good.quality_score

    def test_mr_fg_003_longer_shelf_life_higher_quality(
        self, pipeline: FreshnessGuardianPipeline
    ) -> None:
        """MR-FG-003: Longer initial shelf life -> higher quality at same age."""
        result_short = pipeline.assess(FreshnessRequest(
            store_id="BLR-DS-001",
            sku_id="SKU-0001",
            days_since_receipt=3.0,
            initial_shelf_life_days=5,
        ))
        result_long = pipeline.assess(FreshnessRequest(
            store_id="BLR-DS-001",
            sku_id="SKU-0001",
            days_since_receipt=3.0,
            initial_shelf_life_days=30,
        ))
        assert result_long.quality_score >= result_short.quality_score
