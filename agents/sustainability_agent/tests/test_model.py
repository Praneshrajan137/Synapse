"""
SYNAPSE Sustainability Agent -- Model unit tests.
Verifies carbon tracking, waste prediction, and invariant compliance.
"""
from __future__ import annotations

import numpy as np
import pytest

from agents.sustainability_agent.models.carbon import CarbonTracker
from agents.sustainability_agent.models.waste import WastePredictionModel


class TestCarbonTracker:
    """Tests for the CarbonTracker class."""

    def test_track_route_basic(self) -> None:
        tracker = CarbonTracker(co2_per_liter_kg=2.68)
        co2 = tracker.track_route(fuel_liters=1.0, distance_km=10.0)
        assert co2 == pytest.approx(2.68, rel=1e-4)

    def test_track_route_zero_fuel(self) -> None:
        tracker = CarbonTracker()
        co2 = tracker.track_route(fuel_liters=0.0, distance_km=5.0)
        assert co2 == 0.0

    def test_track_route_zero_distance(self) -> None:
        tracker = CarbonTracker()
        co2 = tracker.track_route(fuel_liters=0.0, distance_km=0.0)
        assert co2 == 0.0

    def test_track_route_negative_fuel_raises(self) -> None:
        tracker = CarbonTracker()
        with pytest.raises(ValueError, match="fuel_liters must be >= 0"):
            tracker.track_route(fuel_liters=-1.0, distance_km=10.0)

    def test_track_route_negative_distance_raises(self) -> None:
        tracker = CarbonTracker()
        with pytest.raises(ValueError, match="distance_km must be >= 0"):
            tracker.track_route(fuel_liters=1.0, distance_km=-5.0)

    def test_co2_non_negative(self) -> None:
        """INV-SA-004: All CO2 values non-negative."""
        tracker = CarbonTracker()
        for fuel in [0.0, 0.1, 1.0, 10.0]:
            co2 = tracker.track_route(fuel_liters=fuel, distance_km=50.0)
            assert co2 >= 0.0, f"CO2 must be >= 0 for fuel={fuel}"

    def test_track_compute_fallback(self) -> None:
        """I-7: Graceful degradation when CodeCarbon unavailable."""
        tracker = CarbonTracker()
        co2 = tracker.track_compute()
        assert co2 >= 0.0

    def test_estimate_from_route_plan(self) -> None:
        tracker = CarbonTracker(co2_per_liter_kg=2.68)
        payload = {"fuel_estimate_liters": 2.0, "total_distance_km": 20.0}
        co2 = tracker.estimate_from_route_plan(payload)
        assert co2 == pytest.approx(5.36, rel=1e-4)

    def test_linear_scaling(self) -> None:
        """MR-SA-001: Doubling fuel doubles CO2."""
        tracker = CarbonTracker()
        co2_base = tracker.track_route(fuel_liters=1.0, distance_km=10.0)
        co2_double = tracker.track_route(fuel_liters=2.0, distance_km=10.0)
        assert co2_double == pytest.approx(2 * co2_base, rel=1e-4)


class TestWastePredictionModel:
    """Tests for the WastePredictionModel class."""

    def test_fallback_prediction(self) -> None:
        model = WastePredictionModel()
        result = model.predict_waste_probability(days_ahead=7)
        assert 0.0 <= result["waste_probability"] <= 1.0
        assert result["survival_at_t"] >= 0.0
        assert len(result["survival_curve"]) == 8  # 0..7

    def test_fallback_zero_days(self) -> None:
        model = WastePredictionModel()
        result = model.predict_waste_probability(days_ahead=0)
        assert result["waste_probability"] == pytest.approx(0.0, abs=1e-6)

    def test_fallback_increasing_waste(self) -> None:
        """More days -> higher waste probability."""
        model = WastePredictionModel()
        prob_3 = model.predict_waste_probability(days_ahead=3)["waste_probability"]
        prob_14 = model.predict_waste_probability(days_ahead=14)["waste_probability"]
        assert prob_14 >= prob_3

    def test_waste_probability_bounded(self) -> None:
        """INV-SA-005: Waste prediction probability in [0, 1]."""
        model = WastePredictionModel()
        for days in [1, 7, 30, 90, 365]:
            result = model.predict_waste_probability(days_ahead=days)
            assert 0.0 <= result["waste_probability"] <= 1.0

    def test_fit_and_predict(self) -> None:
        """Test with actual lifelines fitting."""
        rng = np.random.default_rng(42)
        durations = rng.exponential(scale=10, size=100)
        events = rng.binomial(1, 0.7, size=100)

        model = WastePredictionModel()
        model.fit(durations, events)

        result = model.predict_waste_probability(days_ahead=7)
        assert 0.0 <= result["waste_probability"] <= 1.0
        assert result["survival_at_t"] >= 0.0
        assert len(result["survival_curve"]) > 0

    def test_survival_curve_monotonic(self) -> None:
        """Survival curve should be non-increasing."""
        rng = np.random.default_rng(42)
        durations = rng.exponential(scale=10, size=200)
        events = rng.binomial(1, 0.7, size=200)

        model = WastePredictionModel()
        model.fit(durations, events)

        result = model.predict_waste_probability(days_ahead=20)
        curve = result["survival_curve"]
        for i in range(1, len(curve)):
            assert curve[i] <= curve[i - 1] + 1e-9, (
                f"Survival curve not monotonic at t={i}: {curve[i]} > {curve[i-1]}"
            )
