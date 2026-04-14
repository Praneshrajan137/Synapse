"""
SYNAPSE -- Consumer-Driven Contract: Sustainability Agent -> Routing Navigator.
Sustainability Agent EXPECTS fuel_estimate_liters and distance_km from route plans.
"""

from __future__ import annotations

import pytest
from synapse_common.models import RoutePlan

pytestmark = pytest.mark.contract


class TestRoutingNavigatorContract:
    """Contract test: what Sustainability Agent expects from Routing Navigator."""

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

    def test_fuel_estimate_present_and_non_negative(self) -> None:
        r = self._make_route()
        assert hasattr(r, "fuel_estimate_liters")
        assert r.fuel_estimate_liters >= 0.0

    def test_distance_present_and_non_negative(self) -> None:
        r = self._make_route()
        assert hasattr(r, "total_distance_km")
        assert r.total_distance_km >= 0.0

    def test_fuel_and_distance_consistent(self) -> None:
        r = self._make_route()
        if r.total_distance_km == 0.0:
            assert r.fuel_estimate_liters == 0.0, "Contract: zero distance must mean zero fuel"

    def test_deterministic_serialization(self) -> None:
        r = self._make_route()
        assert r.to_deterministic_json() == r.to_deterministic_json()

    def test_route_plan_has_stops(self) -> None:
        r = self._make_route()
        assert len(r.stops) > 0, "Contract: route must have at least one stop"
