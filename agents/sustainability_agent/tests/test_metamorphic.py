"""
SYNAPSE Sustainability Agent -- Metamorphic Tests (Layer 4).
Behavioral invariants that must hold across model retraining.
"""

from __future__ import annotations

import pytest

from agents.sustainability_agent.inference.pipeline import SustainabilityPipeline
from agents.sustainability_agent.models.carbon import CarbonTracker

pytestmark = pytest.mark.metamorphic


class TestMetamorphicRelations:
    @pytest.fixture()
    def pipeline(self) -> SustainabilityPipeline:
        return SustainabilityPipeline()

    @pytest.fixture()
    def tracker(self) -> CarbonTracker:
        return CarbonTracker()

    def test_mr_sa_001_double_fuel_doubles_co2(self, tracker: CarbonTracker) -> None:
        """MR-SA-001: Doubling fuel consumption doubles delivery CO2."""
        co2_base = tracker.track_route(fuel_liters=1.0, distance_km=10.0)
        co2_double = tracker.track_route(fuel_liters=2.0, distance_km=10.0)
        assert co2_double == pytest.approx(2 * co2_base, rel=0.01)

    def test_mr_sa_002_zero_distance_zero_co2(self, tracker: CarbonTracker) -> None:
        """MR-SA-002: Zero distance + zero fuel yields zero delivery CO2."""
        co2 = tracker.track_route(fuel_liters=0.0, distance_km=0.0)
        assert co2 == 0.0

    def test_mr_sa_003_higher_fuel_higher_report_co2(
        self, pipeline: SustainabilityPipeline
    ) -> None:
        """More fuel -> higher total CO2 in report."""
        report_low = pipeline.report(fuel_liters=0.5, distance_km=5.0)
        report_high = pipeline.report(fuel_liters=5.0, distance_km=50.0)
        assert report_high.delivery_co2_kg >= report_low.delivery_co2_kg

    def test_mr_sa_004_longer_horizon_higher_waste(self, pipeline: SustainabilityPipeline) -> None:
        """MR-SA-004: Longer prediction horizon -> higher waste probability."""
        report_short = pipeline.report(fuel_liters=1.0, distance_km=10.0, days_ahead=3)
        report_long = pipeline.report(fuel_liters=1.0, distance_km=10.0, days_ahead=14)
        assert report_long.waste_probability >= report_short.waste_probability

    def test_carbon_report_has_provenance(self, pipeline: SustainabilityPipeline) -> None:
        """INV-SA-003: Every report must include provenance chain."""
        report = pipeline.report(fuel_liters=1.0, distance_km=10.0)
        assert len(report.provenance_chain) > 0
        for entry in report.provenance_chain:
            assert entry.source != ""

    def test_pareto_weight_positive(self, pipeline: SustainabilityPipeline) -> None:
        """INV-SA-001: Carbon Pareto weight > 0."""
        report = pipeline.report(fuel_liters=1.0, distance_km=10.0)
        assert report.pareto_weights.get("carbon", 0.0) > 0.0

    def test_deterministic_serialization(self, pipeline: SustainabilityPipeline) -> None:
        """INV-SA-009: Deterministic JSON output."""
        report = pipeline.report(fuel_liters=1.0, distance_km=10.0)
        json1 = report.to_deterministic_json()
        json2 = report.to_deterministic_json()
        assert json1 == json2
