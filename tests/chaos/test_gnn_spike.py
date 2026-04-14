from __future__ import annotations

import json
from unittest.mock import MagicMock

import numpy as np
import pytest
import structlog
import structlog.testing

logger = structlog.get_logger()

pytestmark = pytest.mark.chaos

# ---------------------------------------------------------------------------
# Simulated Demand Prophet components for chaos injection
# ---------------------------------------------------------------------------


class ConformalValidator:
    """Validates forecast outputs against conformal prediction intervals."""

    def __init__(self, sigma_threshold: float = 3.0) -> None:
        self.sigma_threshold = sigma_threshold
        self.historical_mean: float = 100.0
        self.historical_std: float = 15.0

    def is_anomalous(self, forecast_value: float) -> bool:
        return self._z_score(forecast_value) > self.sigma_threshold

    def _z_score(self, forecast_value: float) -> float:
        return abs(forecast_value - self.historical_mean) / self.historical_std


class EMAFallback:
    """Exponential Moving Average fallback when GNN produces anomalous output."""

    def __init__(self, alpha: float = 0.3) -> None:
        self.alpha = alpha
        self._history: list[float] = []

    def update(self, value: float) -> None:
        self._history.append(value)

    def predict(self) -> float:
        if not self._history:
            return 0.0
        ema = self._history[0]
        for val in self._history[1:]:
            ema = self.alpha * val + (1 - self.alpha) * ema
        return ema


def _expected_ema(values: list[float], alpha: float = 0.3) -> float:
    """Compute EMA analytically for test assertions."""
    ema = values[0]
    for val in values[1:]:
        ema = alpha * val + (1 - alpha) * ema
    return ema


_EMA_SEED = [95.0, 102.0, 98.0, 105.0, 100.0, 97.0, 103.0, 99.0, 101.0, 96.0]
_EXPECTED_EMA = _expected_ema(_EMA_SEED)


class DemandProphetInferencePipeline:
    """Simplified inference pipeline with anomaly detection and fallback."""

    def __init__(self) -> None:
        self.validator = ConformalValidator(sigma_threshold=3.0)
        self.ema_fallback = EMAFallback(alpha=0.3)
        self.fallback_triggered: bool = False
        self.gnn_model = MagicMock()

        for val in _EMA_SEED:
            self.ema_fallback.update(val)

    def predict(self, sku_id: str, store_id: str) -> dict:
        gnn_forecast: float = self.gnn_model.forward(sku_id, store_id)

        if self.validator.is_anomalous(gnn_forecast):
            logger.warning(
                "gnn_anomalous_spike_detected",
                sku_id=sku_id,
                store_id=store_id,
                gnn_value=gnn_forecast,
                z_score=self.validator._z_score(gnn_forecast),
                action="fallback_to_ema",
            )
            self.fallback_triggered = True
            fallback_value = self.ema_fallback.predict()
            return {
                "sku_id": sku_id,
                "store_id": store_id,
                "forecast": fallback_value,
                "source": "ema_fallback",
                "confidence": 0.6,
                "gnn_rejected_value": gnn_forecast,
                "rejection_reason": "conformal_interval_exceeded_3sigma",
            }

        self.ema_fallback.update(gnn_forecast)
        return {
            "sku_id": sku_id,
            "store_id": store_id,
            "forecast": gnn_forecast,
            "source": "gnn_hgt_tft",
            "confidence": 0.92,
        }


class TestGNNNonsensicalSpike:
    """Chaos logic validation: GNN produces 10x demand spike. System must
    detect via conformal intervals and fallback to EMA within <1 minute SLA."""

    def test_spike_detected_via_conformal_interval(self, chaos_clock) -> None:
        """10x spike triggers conformal interval > 3-sigma detection."""
        pipeline = DemandProphetInferencePipeline()
        pipeline.gnn_model.forward = MagicMock(return_value=1000.0)

        chaos_clock.start()
        with structlog.testing.capture_logs() as captured:
            result = pipeline.predict(sku_id="SKU-001", store_id="STORE-BLR-01")

        assert result["source"] == "ema_fallback", (
            "GNN spike was NOT detected — system used anomalous GNN output"
        )
        assert result["rejection_reason"] == "conformal_interval_exceeded_3sigma"
        assert pipeline.fallback_triggered is True
        chaos_clock.assert_within_sla(60.0, "GNN nonsensical spike fallback")

        assert any(
            e.get("event") == "gnn_anomalous_spike_detected" for e in captured
        ), "Expected structured log event not emitted"

    def test_fallback_produces_exact_ema_forecast(self) -> None:
        """EMA fallback matches analytically computed value."""
        pipeline = DemandProphetInferencePipeline()
        pipeline.gnn_model.forward = MagicMock(return_value=1000.0)

        result = pipeline.predict(sku_id="SKU-001", store_id="STORE-BLR-01")

        assert abs(result["forecast"] - _EXPECTED_EMA) < 1.0, (
            f"EMA fallback {result['forecast']:.4f} deviates from "
            f"expected {_EXPECTED_EMA:.4f}"
        )

    def test_normal_forecast_bypasses_fallback(self) -> None:
        """Non-anomalous GNN outputs pass through without fallback."""
        pipeline = DemandProphetInferencePipeline()
        pipeline.gnn_model.forward = MagicMock(return_value=105.0)

        result = pipeline.predict(sku_id="SKU-001", store_id="STORE-BLR-01")

        assert result["source"] == "gnn_hgt_tft"
        assert pipeline.fallback_triggered is False

    def test_multiple_spikes_all_caught(self, chaos_clock) -> None:
        """All spikes in a batch are caught, not just the first."""
        pipeline = DemandProphetInferencePipeline()
        spike_values = [1000.0, 2000.0, 500.0, 1500.0]

        chaos_clock.start()
        for i, spike in enumerate(spike_values):
            pipeline.gnn_model.forward = MagicMock(return_value=spike)
            result = pipeline.predict(sku_id=f"SKU-{i:03d}", store_id="STORE-BLR-01")
            assert result["source"] == "ema_fallback", (
                f"Spike {spike} at index {i} was NOT caught"
            )

        chaos_clock.assert_within_sla(60.0, "Batch GNN spike detection")

    def test_gnn_rejected_value_preserved_in_output(self) -> None:
        """Rejected GNN value is logged for audit (I-4 append-only audit)."""
        pipeline = DemandProphetInferencePipeline()
        pipeline.gnn_model.forward = MagicMock(return_value=1000.0)

        result = pipeline.predict(sku_id="SKU-001", store_id="STORE-BLR-01")

        assert "gnn_rejected_value" in result
        assert result["gnn_rejected_value"] == 1000.0

    def test_confidence_reduced_on_fallback(self) -> None:
        """Fallback predictions carry lower confidence than GNN predictions."""
        pipeline = DemandProphetInferencePipeline()
        pipeline.gnn_model.forward = MagicMock(return_value=100.0)
        normal = pipeline.predict(sku_id="SKU-001", store_id="STORE-BLR-01")

        pipeline2 = DemandProphetInferencePipeline()
        pipeline2.gnn_model.forward = MagicMock(return_value=1000.0)
        fallback = pipeline2.predict(sku_id="SKU-001", store_id="STORE-BLR-01")

        assert fallback["confidence"] < normal["confidence"], (
            "Fallback confidence must be lower than normal GNN confidence"
        )

    def test_boundary_spike_at_exactly_3sigma(self) -> None:
        """Forecast at exactly 3-sigma boundary is NOT flagged (threshold is >)."""
        pipeline = DemandProphetInferencePipeline()
        boundary_value = 100.0 + 3.0 * 15.0  # exactly 3 sigma
        pipeline.gnn_model.forward = MagicMock(return_value=boundary_value)

        result = pipeline.predict(sku_id="SKU-001", store_id="STORE-BLR-01")
        assert result["source"] == "gnn_hgt_tft"

    def test_negative_spike_also_caught(self) -> None:
        """Negative anomalous values (demand crash) are also detected."""
        pipeline = DemandProphetInferencePipeline()
        pipeline.gnn_model.forward = MagicMock(return_value=-500.0)

        result = pipeline.predict(sku_id="SKU-001", store_id="STORE-BLR-01")
        assert result["source"] == "ema_fallback"
