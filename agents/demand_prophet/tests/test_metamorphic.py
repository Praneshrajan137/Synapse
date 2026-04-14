"""
SYNAPSE Demand Prophet -- Metamorphic Tests (Layer 4).
Behavioral invariants that must hold across model retraining.
"""

from __future__ import annotations

import pytest

from agents.demand_prophet.inference.pipeline import DemandProphetPipeline

pytestmark = pytest.mark.metamorphic


class TestMetamorphicRelations:
    @pytest.fixture()
    def pipeline(self) -> DemandProphetPipeline:
        return DemandProphetPipeline()

    def test_mr_dp_004_order_invariance(self, pipeline: DemandProphetPipeline) -> None:
        """MR-DP-004: Permuting SKU ID order does not change per-SKU forecasts."""
        sku_ids = ["SKU001", "SKU002", "SKU003"]
        sku_ids_shuffled = ["SKU003", "SKU001", "SKU002"]

        forecasts_original = pipeline.predict(sku_ids, "STORE_BLR_001")
        forecasts_shuffled = pipeline.predict(sku_ids_shuffled, "STORE_BLR_001")

        original_map = {f.sku_id: f for f in forecasts_original}
        shuffled_map = {f.sku_id: f for f in forecasts_shuffled}

        for sku_id in sku_ids:
            orig = original_map[sku_id]
            shuf = shuffled_map[sku_id]
            for horizon in orig.horizons:
                assert orig.horizons[horizon] == shuf.horizons[horizon], (
                    f"MR-DP-004 violated: forecast for {sku_id}/{horizon} changed with permutation"
                )

    def test_mr_dp_001_demand_doubling(self, pipeline: DemandProphetPipeline) -> None:
        """MR-DP-001: Structure validation -- full check requires trained model."""
        forecasts = pipeline.predict(["SKU001"], "STORE_BLR_001")
        assert len(forecasts) == 1
        assert "24h" in forecasts[0].horizons
