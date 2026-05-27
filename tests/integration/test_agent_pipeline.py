"""
SYNAPSE -- Cross-Agent Integration Tests (Layer 6).
Tests end-to-end data flow: Demand Prophet -> Routing Navigator -> Inventory Sentinel.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


class TestDemandProphetToInventory:
    """DP forecast feeds Inventory Sentinel decisions."""

    def test_forecast_feeds_inventory(self) -> None:
        from agents.demand_prophet.inference.pipeline import DemandProphetPipeline
        from agents.inventory_sentinel.inference.pipeline import InventorySentinelPipeline

        dp = DemandProphetPipeline()
        forecasts = dp.predict(["SKU001", "SKU002"], "STORE_BLR_001")
        assert len(forecasts) == 2
        assert all(f.confidence > 0 for f in forecasts)

        inv_sentinel = InventorySentinelPipeline()
        actions = inv_sentinel.decide(
            [f.sku_id for f in forecasts],
            "STORE_BLR_001",
            demand_forecast={"forecasts": [f.model_dump(mode="json") for f in forecasts]},
        )
        assert len(actions) == 2
        for a in actions:
            assert 1.0 <= a.safety_stock_multiplier <= 3.0
            assert a.quantity >= 0


class TestDemandProphetToRouting:
    """DP forecast drives RN order generation."""

    def test_forecast_feeds_routing(self) -> None:
        from agents.demand_prophet.inference.pipeline import DemandProphetPipeline
        from agents.routing_navigator.inference.pipeline import RoutingNavigatorPipeline

        dp = DemandProphetPipeline()
        forecasts = dp.predict(["SKU001", "SKU002", "SKU003"], "STORE_BLR_001")

        orders = [
            {"order_id": f"ORD-{i}", "lat": 12.97, "lon": 77.59} for i, f in enumerate(forecasts)
        ]
        riders = [{"rider_id": "R-1"}, {"rider_id": "R-2"}]

        rn = RoutingNavigatorPipeline()
        routes = rn.route(orders, riders, "STORE_BLR_001")
        assert len(routes) >= 1
        assert all(r.total_time_min <= 480 for r in routes)


class TestA2AProposalRoundTrip:
    """Test A2A proposal generation for all 3 agents."""

    def test_demand_prophet_a2a(self) -> None:
        from agents.demand_prophet.a2a.handler import DemandProphetA2AHandler

        handler = DemandProphetA2AHandler()
        response = handler.handle_request(
            {
                "jsonrpc": "2.0",
                "method": "proposal",
                "params": {"sku_ids": ["SKU001"], "store_id": "S1"},
                "id": "test-1",
            }
        )
        assert "result" in response
        assert response["id"] == "test-1"

    def test_routing_navigator_a2a(self) -> None:
        from agents.routing_navigator.a2a.handler import RoutingNavigatorA2AHandler

        handler = RoutingNavigatorA2AHandler()
        response = handler.handle_request(
            {
                "jsonrpc": "2.0",
                "method": "proposal",
                "params": {
                    "orders": [{"order_id": "O-1", "lat": 12.97, "lon": 77.59}],
                    "riders": [{"rider_id": "R-1"}],
                    "store_id": "S1",
                },
                "id": "test-2",
            }
        )
        assert "result" in response

    def test_inventory_sentinel_a2a(self) -> None:
        from agents.inventory_sentinel.a2a.handler import InventorySentinelA2AHandler

        handler = InventorySentinelA2AHandler()
        response = handler.handle_request(
            {
                "jsonrpc": "2.0",
                "method": "proposal",
                "params": {"sku_ids": ["SKU001"], "store_id": "S1"},
                "id": "test-3",
            }
        )
        assert "result" in response


class TestSchemaValidation:
    """Verify all agent outputs serialize deterministically (I-13)."""

    def test_demand_forecast_deterministic(self) -> None:
        from agents.demand_prophet.inference.pipeline import DemandProphetPipeline

        dp = DemandProphetPipeline()
        forecasts = dp.predict(["SKU001"], "STORE_BLR_001")
        for f in forecasts:
            json1 = f.to_deterministic_json()
            json2 = f.to_deterministic_json()
            assert json1 == json2, "I-13 violated: non-deterministic serialization"

    def test_route_plan_deterministic(self) -> None:
        from agents.routing_navigator.inference.pipeline import RoutingNavigatorPipeline

        rn = RoutingNavigatorPipeline()
        routes = rn.route(
            [{"order_id": "O-1"}],
            [{"rider_id": "R-1"}],
            "S1",
        )
        for r in routes:
            assert r.to_deterministic_json() == r.to_deterministic_json()

    def test_inventory_action_deterministic(self) -> None:
        from agents.inventory_sentinel.inference.pipeline import InventorySentinelPipeline

        inv = InventorySentinelPipeline()
        actions = inv.decide(["SKU001"], "S1")
        for a in actions:
            assert a.to_deterministic_json() == a.to_deterministic_json()
