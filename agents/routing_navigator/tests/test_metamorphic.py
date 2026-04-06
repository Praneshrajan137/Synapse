"""SYNAPSE Routing Navigator -- Metamorphic Tests (Layer 4)."""
from __future__ import annotations

import pytest

from agents.routing_navigator.inference.pipeline import RoutingNavigatorPipeline

pytestmark = pytest.mark.metamorphic


class TestMetamorphicRelations:
    @pytest.fixture()
    def pipeline(self) -> RoutingNavigatorPipeline:
        return RoutingNavigatorPipeline()

    def test_mr_rn_001_adding_order(self, pipeline: RoutingNavigatorPipeline) -> None:
        """MR-RN-001: Adding order cannot decrease total time by >5%."""
        base_orders = [{"order_id": f"O-{i}", "lat": 12.97, "lon": 77.59} for i in range(3)]
        riders = [{"rider_id": "R-1"}]

        routes_base = pipeline.route(base_orders, riders, "S1")
        base_time = sum(r.total_time_min for r in routes_base)

        extra_orders = base_orders + [{"order_id": "O-extra", "lat": 12.98, "lon": 77.60}]
        routes_extra = pipeline.route(extra_orders, riders, "S1")
        extra_time = sum(r.total_time_min for r in routes_extra)

        if base_time > 0:
            decrease_pct = (base_time - extra_time) / base_time
            assert decrease_pct <= 0.05, f"MR-RN-001 violated: time decreased by {decrease_pct:.1%}"
