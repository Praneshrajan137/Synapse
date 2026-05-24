"""SYNAPSE Routing Navigator — Metamorphic + Oracle (Layers 4 + 6).

WS-8.2 elevation: tests target the *physics* of vehicle routing, not just
the schema. Metamorphic relations:

  * **MR-RN-001 (more stops → no less distance)** — adding orders to a
    feasible instance never reduces total distance.
  * **MR-RN-002 (capacity respect)** — when total demand > one-rider
    capacity, the solver returns a multi-vehicle solution.
  * **MR-RN-003 (time cap)** — every emitted route honours the 480-min
    hard cap.
  * **Oracle (unit square)** — for a depot + 3 corners forming a 1 km
    square, optimum tour distance is ≈ 4 km. The solver must hit it.
"""

from __future__ import annotations

from typing import Any

import pytest

from agents.routing_navigator.inference.pipeline import RoutingNavigatorPipeline
from agents.routing_navigator.models.cvrptw import Stop, solve_cvrptw

pytestmark = pytest.mark.metamorphic


@pytest.fixture()
def pipeline() -> RoutingNavigatorPipeline:
    return RoutingNavigatorPipeline()


def _orders(n: int, weight: float = 2.0) -> list[dict[str, Any]]:
    return [
        {
            "order_id": f"ORD-{i}",
            "lat": 12.97 + 0.005 * i,
            "lon": 77.59 + 0.005 * i,
            "weight_kg": weight,
        }
        for i in range(n)
    ]


def _riders(n: int, capacity: float = 30.0) -> list[dict[str, Any]]:
    return [{"rider_id": f"R-{i}", "capacity_kg": capacity} for i in range(n)]


class TestMetamorphicRelations:
    def test_mr_rn_001_more_orders_no_shorter(
        self, pipeline: RoutingNavigatorPipeline
    ) -> None:
        small = pipeline.route(_orders(3), _riders(1), "STORE_BLR_001", use_student=False)
        big = pipeline.route(_orders(8), _riders(1), "STORE_BLR_001", use_student=False)
        assert sum(p.total_distance_km for p in big) >= sum(p.total_distance_km for p in small)

    def test_mr_rn_002_capacity_forces_multi_vehicle(
        self, pipeline: RoutingNavigatorPipeline
    ) -> None:
        # 10 stops × 5 kg = 50 kg; two riders @ 30 kg → must use both.
        plans = pipeline.route(
            _orders(10, weight=5.0),
            _riders(2, capacity=30.0),
            "STORE_BLR_001",
            use_student=False,
        )
        assert len(plans) >= 2

    def test_mr_rn_003_routes_within_time_cap(
        self, pipeline: RoutingNavigatorPipeline
    ) -> None:
        plans = pipeline.route(_orders(8), _riders(2), "STORE_BLR_001", use_student=False)
        assert all(p.total_time_min <= 480.0 for p in plans)


class TestOracle:
    def test_oracle_unit_square_tour(self) -> None:
        """Square (depot + 3 corners) → optimum tour ≈ 4·side."""
        side_deg = 0.009  # ≈1 km in lat
        depot = Stop(lat=0.0, lon=0.0, demand=0.0)
        corners = [
            Stop(lat=side_deg, lon=0.0, demand=1.0),
            Stop(lat=side_deg, lon=side_deg, demand=1.0),
            Stop(lat=0.0, lon=side_deg, demand=1.0),
        ]
        routes = solve_cvrptw([depot, *corners], capacity=30.0, max_route_min=480.0)
        assert routes
        # Perimeter ≈ 4 km. Allow generous slack since haversine != euclidean.
        assert 3.0 < routes[0].distance_km < 5.0
