"""
SYNAPSE -- Consumer Contract: Inventory Sentinel consumes Demand Prophet forecasts.
This contract verifies the Demand Prophet output format matches what IS expects.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from synapse_common.models import DemandForecast

pytestmark = pytest.mark.contract


class TestDemandProphetContract:
    """What Inventory Sentinel expects from Demand Prophet."""

    def _make_forecast(self) -> DemandForecast:
        return DemandForecast(
            sku_id="SKU001",
            store_id="STORE_BLR_001",
            forecast_timestamp=datetime.now(UTC),
            horizons={"15min": 10.0, "1h": 40.0, "6h": 200.0, "24h": 800.0, "7d": 5000.0},
            lower_90={"15min": 5.0, "1h": 20.0, "6h": 100.0, "24h": 400.0, "7d": 2500.0},
            upper_90={"15min": 15.0, "1h": 60.0, "6h": 300.0, "24h": 1200.0, "7d": 7500.0},
            confidence=0.85,
            drift_detected=False,
        )

    def test_all_horizons_present(self) -> None:
        f = self._make_forecast()
        expected = {"15min", "1h", "6h", "24h", "7d"}
        assert set(f.horizons.keys()) == expected

    def test_conformal_intervals_present(self) -> None:
        f = self._make_forecast()
        assert f.lower_90 is not None
        assert f.upper_90 is not None
        for h in f.horizons:
            assert h in f.lower_90
            assert h in f.upper_90

    def test_confidence_bounded(self) -> None:
        f = self._make_forecast()
        assert 0.0 <= f.confidence <= 1.0

    def test_drift_field_is_bool(self) -> None:
        f = self._make_forecast()
        assert isinstance(f.drift_detected, bool)
