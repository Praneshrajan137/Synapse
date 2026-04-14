"""
SYNAPSE Pricing Oracle -- Contract tests (Layer 5).
Consumer-driven contracts: what Pricing Oracle guarantees to its consumers.
"""

from __future__ import annotations

import pytest
from synapse_common.models import PricingDecision

pytestmark = pytest.mark.contract


class TestPricingOracleProducerContract:
    """Contract test: what consumers can expect from Pricing Oracle outputs."""

    def _make_sample_decision(self, is_essential: bool = False) -> PricingDecision:
        multiplier = 1.2 if is_essential else 1.5
        base_price = 100.0
        return PricingDecision(
            sku_id="SKU001",
            store_id="STORE_BLR_001",
            category_id="essential" if is_essential else "snack",
            is_essential=is_essential,
            base_price=base_price,
            multiplier=multiplier,
            final_price=base_price * multiplier,
        )

    def test_multiplier_positive(self) -> None:
        d = self._make_sample_decision()
        assert d.multiplier > 0

    def test_essential_cap_respected(self) -> None:
        """INV-PO-001: Essential items capped at 1.3x."""
        d = self._make_sample_decision(is_essential=True)
        assert d.multiplier <= 1.3

    def test_essential_cap_violation_raises(self) -> None:
        """Pydantic validator rejects essential items above 1.3x."""
        with pytest.raises(ValueError, match="hard cap 1.3x"):
            PricingDecision(
                sku_id="SKU001",
                store_id="STORE_BLR_001",
                category_id="essential",
                is_essential=True,
                base_price=100.0,
                multiplier=1.5,
                final_price=150.0,
            )

    def test_final_price_consistent(self) -> None:
        d = self._make_sample_decision()
        assert abs(d.final_price - d.base_price * d.multiplier) < 0.01

    def test_non_essential_above_cap_allowed(self) -> None:
        d = PricingDecision(
            sku_id="SKU002",
            store_id="STORE_BLR_001",
            category_id="snack",
            is_essential=False,
            base_price=50.0,
            multiplier=1.8,
            final_price=90.0,
        )
        assert d.multiplier > 1.3

    def test_deterministic_serialization(self) -> None:
        d = self._make_sample_decision()
        json1 = d.to_deterministic_json()
        json2 = d.to_deterministic_json()
        assert json1 == json2
