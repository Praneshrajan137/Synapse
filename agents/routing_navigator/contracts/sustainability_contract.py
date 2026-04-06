"""SYNAPSE -- Consumer Contract: Sustainability Agent -> Routing Navigator."""
from __future__ import annotations

import pytest

from synapse_common.models import RoutePlan

pytestmark = pytest.mark.contract


class TestSustainabilityAgentContract:
    def _make_route(self) -> RoutePlan:
        return RoutePlan(
            rider_id="R-1",
            store_id="S-1",
            stops=[{"order_id": "O-1", "lat": 12.97, "lon": 77.59}],
            total_distance_km=5.0,
            total_time_min=20.0,
            fuel_estimate_liters=0.2,
            freshness_violations=0,
        )

    def test_fuel_estimate_present(self) -> None:
        r = self._make_route()
        assert r.fuel_estimate_liters >= 0

    def test_distance_present(self) -> None:
        r = self._make_route()
        assert r.total_distance_km >= 0

    def test_deterministic_serialization(self) -> None:
        r = self._make_route()
        assert r.to_deterministic_json() == r.to_deterministic_json()
