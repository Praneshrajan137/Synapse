"""
SYNAPSE Freshness Guardian — Model Tests.
Tests shelf life prediction and markdown engine.
"""

from __future__ import annotations

import pytest

from agents.freshness_guardian.models.markdown import DynamicMarkdownEngine
from agents.freshness_guardian.models.shelf_life import ShelfLifeModel


class TestShelfLifeModel:
    """Test Weibull AFT shelf life model."""

    @pytest.fixture
    def fitted_model(self) -> ShelfLifeModel:
        model = ShelfLifeModel()
        data = model.generate_synthetic_training_data(n_samples=1000)
        model.fit(data)
        return model

    def test_predict_returns_valid_quality(self, fitted_model: ShelfLifeModel) -> None:
        pred = fitted_model.predict(
            sku_id="SKU-0001",
            store_id="BLR-DS-001",
            temperature_deviation_hours=0.0,
            humidity_deviation_pct=0.0,
            initial_shelf_life_days=7,
            is_cold_chain=True,
            days_since_receipt=1.0,
        )
        assert 0 <= pred.quality_score <= 1
        assert pred.days_to_expiry >= 0

    def test_higher_temp_deviation_lower_quality(self, fitted_model: ShelfLifeModel) -> None:
        """MR-FG-002: Higher temperature deviation -> lower quality score."""
        pred_good = fitted_model.predict(
            "SKU-0001",
            "BLR-DS-001",
            temperature_deviation_hours=0.0,
            humidity_deviation_pct=0.0,
            initial_shelf_life_days=7,
            is_cold_chain=True,
            days_since_receipt=3.0,
        )
        pred_bad = fitted_model.predict(
            "SKU-0001",
            "BLR-DS-001",
            temperature_deviation_hours=10.0,
            humidity_deviation_pct=0.0,
            initial_shelf_life_days=7,
            is_cold_chain=True,
            days_since_receipt=3.0,
        )
        assert pred_bad.quality_score <= pred_good.quality_score

    def test_unfitted_model_uses_fallback(self) -> None:
        """I-7: Graceful degradation when model not fitted."""
        model = ShelfLifeModel()
        pred = model.predict("SKU-0001", "BLR-DS-001", 0.0, 0.0, 7, True, 1.0)
        assert 0 <= pred.quality_score <= 1
        assert pred.days_to_expiry >= 0


class TestMarkdownEngine:
    """Test dynamic markdown engine."""

    @pytest.fixture
    def engine(self) -> DynamicMarkdownEngine:
        return DynamicMarkdownEngine()

    def test_inv_fg_002_expired_item_must_markdown(self, engine: DynamicMarkdownEngine) -> None:
        """INV-FG-002: days_to_expiry = 0 -> markdown_applied = True."""
        result = engine.compute_markdown(
            days_to_expiry=0,
            initial_shelf_life_days=7,
            quality_score=0.0,
            current_stock=10,
            daily_demand_forecast=5.0,
        )
        assert result.markdown_applied is True
        assert result.markdown_pct == 100.0

    def test_inv_fg_004_monotonic_markdown(self, engine: DynamicMarkdownEngine) -> None:
        """INV-FG-004: markdown_pct increases as days_to_expiry decreases."""
        markdowns = []
        for days in [14, 7, 3, 1, 0.5, 0]:
            result = engine.compute_markdown(
                days_to_expiry=days,
                initial_shelf_life_days=14,
                quality_score=0.8,
                current_stock=50,
                daily_demand_forecast=5.0,
            )
            markdowns.append(result.markdown_pct)

        for i in range(1, len(markdowns)):
            assert markdowns[i] >= markdowns[i - 1], (
                f"Non-monotonic at index {i}: {markdowns[i]} < {markdowns[i - 1]}"
            )

    def test_fresh_item_no_markdown(self, engine: DynamicMarkdownEngine) -> None:
        result = engine.compute_markdown(
            days_to_expiry=14,
            initial_shelf_life_days=14,
            quality_score=0.95,
            current_stock=20,
            daily_demand_forecast=10.0,
        )
        assert result.markdown_applied is False
        assert result.markdown_pct == 0.0
