"""
SYNAPSE -- Consumer-Driven Contract: Pricing Oracle -> Freshness Guardian.
Pricing Oracle EXPECTS these fields from Freshness Guardian alerts.
"""

from __future__ import annotations

import pytest

from agents.freshness_guardian.inference.pipeline import (
    FreshnessGuardianPipeline,
    FreshnessRequest,
)

pytestmark = pytest.mark.contract


class TestPricingOracleContract:
    """Contract test: what Pricing Oracle expects from Freshness Guardian."""

    def _make_sample_alert(self) -> object:
        pipeline = FreshnessGuardianPipeline()
        return pipeline.assess(
            FreshnessRequest(
                store_id="BLR-DS-001",
                sku_id="SKU-0001",
                days_since_receipt=5.0,
                initial_shelf_life_days=7,
            )
        )

    def test_days_to_expiry_present_and_non_negative(self) -> None:
        alert = self._make_sample_alert()
        assert hasattr(alert, "days_to_expiry")
        assert alert.days_to_expiry >= 0  # type: ignore[union-attr]

    def test_quality_score_bounded(self) -> None:
        alert = self._make_sample_alert()
        assert 0.0 <= alert.quality_score <= 1.0  # type: ignore[union-attr]

    def test_markdown_applied_is_boolean(self) -> None:
        alert = self._make_sample_alert()
        assert isinstance(alert.markdown_applied, bool)  # type: ignore[union-attr]

    def test_markdown_pct_bounded(self) -> None:
        alert = self._make_sample_alert()
        assert 0.0 <= alert.markdown_pct <= 100.0  # type: ignore[union-attr]
