"""SYNAPSE Inventory Sentinel -- Metamorphic Tests (Layer 4)."""
from __future__ import annotations

import pytest

from agents.inventory_sentinel.inference.pipeline import InventorySentinelPipeline

pytestmark = pytest.mark.metamorphic


class TestMetamorphicRelations:
    @pytest.fixture()
    def pipeline(self) -> InventorySentinelPipeline:
        return InventorySentinelPipeline()

    def test_mr_is_002_zero_demand(self, pipeline: InventorySentinelPipeline) -> None:
        """MR-IS-002: Structure validation -- zero demand scenario."""
        actions = pipeline.decide(["SKU001"], "STORE_BLR_001")
        assert len(actions) == 1
        assert actions[0].action_type in {"reorder", "transfer", "markdown"}
