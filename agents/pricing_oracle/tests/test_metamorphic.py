"""
SYNAPSE Pricing Oracle -- Metamorphic Tests (Layer 4).
Behavioral invariants that must hold across model retraining.
"""
from __future__ import annotations

import pytest

from agents.pricing_oracle.inference.pipeline import (
    ESSENTIAL_CAP,
    PricingOraclePipeline,
)

pytestmark = pytest.mark.metamorphic


class TestMetamorphicRelations:
    @pytest.fixture()
    def pipeline(self) -> PricingOraclePipeline:
        return PricingOraclePipeline()

    def test_mr_po_001_essential_cap(self, pipeline: PricingOraclePipeline) -> None:
        """MR-PO-001: Essential category items always have multiplier <= 1.3x."""
        sku_ids = ["SKU001", "SKU002", "SKU003"]
        categories = ["essential", "essential", "essential"]
        base_prices = [100.0, 200.0, 50.0]

        updates = pipeline.price(
            sku_ids=sku_ids,
            store_id="STORE_BLR_001",
            categories=categories,
            base_prices=base_prices,
        )

        for update in updates:
            assert update.multiplier <= ESSENTIAL_CAP, (
                f"MR-PO-001 violated: essential item {update.sku_id} has "
                f"multiplier {update.multiplier} > {ESSENTIAL_CAP}"
            )

    def test_mr_po_001_essential_cap_repeated(self, pipeline: PricingOraclePipeline) -> None:
        """MR-PO-001: Essential cap holds across 50 repeated requests."""
        for _ in range(50):
            updates = pipeline.price(
                sku_ids=["SKU_E1"],
                store_id="STORE_MUM_001",
                categories=["essential"],
                base_prices=[999.0],
            )
            assert updates[0].multiplier <= ESSENTIAL_CAP

    def test_mr_po_003_order_invariance(self, pipeline: PricingOraclePipeline) -> None:
        """MR-PO-003: Permuting SKU ID order does not change per-SKU pricing."""
        sku_ids = ["SKU001", "SKU002", "SKU003"]
        categories = ["snack", "beverage", "dairy"]
        base_prices = [100.0, 50.0, 75.0]

        updates_original = pipeline.price(
            sku_ids=sku_ids,
            store_id="STORE_BLR_001",
            categories=categories,
            base_prices=base_prices,
        )

        perm = [2, 0, 1]
        sku_ids_perm = [sku_ids[i] for i in perm]
        categories_perm = [categories[i] for i in perm]
        base_prices_perm = [base_prices[i] for i in perm]

        updates_permuted = pipeline.price(
            sku_ids=sku_ids_perm,
            store_id="STORE_BLR_001",
            categories=categories_perm,
            base_prices=base_prices_perm,
        )

        orig_map = {u.sku_id: u.multiplier for u in updates_original}
        perm_map = {u.sku_id: u.multiplier for u in updates_permuted}

        for sku_id in sku_ids:
            assert abs(orig_map[sku_id] - perm_map[sku_id]) < 1e-6, (
                f"MR-PO-003 violated: pricing for {sku_id} changed with permutation"
            )

    def test_mr_po_004_determinism(self, pipeline: PricingOraclePipeline) -> None:
        """MR-PO-004: Identical inputs produce identical outputs."""
        kwargs = {
            "sku_ids": ["SKU001"],
            "store_id": "STORE_BLR_001",
            "categories": ["snack"],
            "base_prices": [100.0],
        }

        updates1 = pipeline.price(**kwargs)
        updates2 = pipeline.price(**kwargs)

        assert updates1[0].multiplier == updates2[0].multiplier
        assert updates1[0].final_price == updates2[0].final_price

    def test_essential_mixed_categories(self, pipeline: PricingOraclePipeline) -> None:
        """Essential cap applies only to essentials, not other categories."""
        updates = pipeline.price(
            sku_ids=["SKU_E1", "SKU_S1"],
            store_id="STORE_BLR_001",
            categories=["essential", "snack"],
            base_prices=[100.0, 100.0],
        )

        essential = [u for u in updates if u.category == "essential"]
        non_essential = [u for u in updates if u.category != "essential"]

        for u in essential:
            assert u.multiplier <= ESSENTIAL_CAP
        for u in non_essential:
            assert u.multiplier > 0
