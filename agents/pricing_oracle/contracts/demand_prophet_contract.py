"""
SYNAPSE -- Consumer-Driven Contract: Pricing Oracle -> Demand Prophet.
Pricing Oracle EXPECTS these fields and properties from Demand Prophet forecasts.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from synapse_common.models import DemandForecast

pytestmark = pytest.mark.contract


class TestDemandProphetContract:
    """Contract test: what Pricing Oracle expects from Demand Prophet."""

    def _make_sample_forecast(self) -> DemandForecast:
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

    def test_forecast_has_24h_horizon(self) -> None:
        """PO needs 24h horizon for daily pricing decisions."""
        f = self._make_sample_forecast()
        assert "24h" in f.horizons, "Contract: PO requires 24h horizon from DP"

    def test_forecast_values_non_negative(self) -> None:
        """PO uses forecast values as demand input; negatives are nonsensical."""
        f = self._make_sample_forecast()
        for h, v in f.horizons.items():
            assert v >= 0, f"Contract: forecast value for {h} must be >= 0"

    def test_confidence_bounded(self) -> None:
        """PO uses confidence for HITL gating (I-5)."""
        f = self._make_sample_forecast()
        assert 0.0 <= f.confidence <= 1.0

    def test_conformal_intervals_present(self) -> None:
        """PO uses uncertainty to adjust pricing aggressiveness."""
        f = self._make_sample_forecast()
        assert f.lower_90 is not None
        assert f.upper_90 is not None

    def test_conformal_interval_width_positive(self) -> None:
        """PO uses interval width to scale multiplier conservatism."""
        f = self._make_sample_forecast()
        for horizon in f.horizons:
            width = f.upper_90[horizon] - f.lower_90[horizon]
            assert width > 0, f"Contract: interval width for {horizon} must be > 0"

    def test_drift_detected_field(self) -> None:
        """PO reduces pricing aggressiveness when drift is detected."""
        f = self._make_sample_forecast()
        assert isinstance(f.drift_detected, bool)

    def test_deterministic_serialization(self) -> None:
        """PO depends on deterministic JSON for cache keys (I-13)."""
        f = self._make_sample_forecast()
        json1 = f.to_deterministic_json()
        json2 = f.to_deterministic_json()
        assert json1 == json2
