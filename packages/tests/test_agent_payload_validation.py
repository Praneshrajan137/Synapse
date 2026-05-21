"""Tests for the per-agent payload-schema helper (Sprint 7, WS-2 / I-3)."""

from __future__ import annotations

import pytest
from synapse_common.schemas import (
    AGENT_PAYLOAD_SCHEMAS,
    PENDING_AGENT_PAYLOAD_SCHEMAS,
    SchemaValidationError,
    validate_agent_payload,
)

_ALL_EIGHT_AGENTS = {
    "demand_prophet",
    "routing_navigator",
    "inventory_sentinel",
    "pricing_oracle",
    "freshness_guardian",
    "disruption_shield",
    "supplier_trust",
    "sustainability_agent",
}


class TestRegistration:
    def test_all_eight_agents_strictly_enforced(self) -> None:
        assert set(AGENT_PAYLOAD_SCHEMAS) == _ALL_EIGHT_AGENTS

    def test_pending_map_is_empty(self) -> None:
        assert PENDING_AGENT_PAYLOAD_SCHEMAS == {}

    def test_strict_and_pending_are_disjoint(self) -> None:
        assert not (
            set(AGENT_PAYLOAD_SCHEMAS) & set(PENDING_AGENT_PAYLOAD_SCHEMAS)
        )

    def test_all_eight_agents_are_covered(self) -> None:
        covered = set(AGENT_PAYLOAD_SCHEMAS) | set(PENDING_AGENT_PAYLOAD_SCHEMAS)
        assert covered == _ALL_EIGHT_AGENTS, (
            "Every agent must be in either AGENT_PAYLOAD_SCHEMAS (enforced) "
            "or PENDING_AGENT_PAYLOAD_SCHEMAS (follow-up)."
        )


class TestDemandProphetValidation:
    def _valid_forecast(self) -> dict[str, object]:
        return {
            "sku_id": "SKU-1",
            "store_id": "STORE-1",
            "forecast_timestamp": "2026-05-06T12:00:00Z",
            "horizons": {"15min": 1.0, "1h": 5.0, "6h": 30.0, "24h": 100.0, "7d": 700.0},
            "lower_90": {},
            "upper_90": {},
            "confidence": 0.9,
            "drift_detected": False,
        }

    def test_valid_payload_accepts(self) -> None:
        payload = {
            "forecasts": [self._valid_forecast(), self._valid_forecast()],
            "store_id": "STORE-1",
            "num_skus": 2,
        }
        validate_agent_payload("demand_prophet", payload)

    def test_one_bad_forecast_fails(self) -> None:
        bad = self._valid_forecast()
        bad["confidence"] = 1.5  # out of range
        payload = {"forecasts": [self._valid_forecast(), bad], "store_id": "x", "num_skus": 2}
        with pytest.raises(SchemaValidationError):
            validate_agent_payload("demand_prophet", payload)

    def test_missing_forecasts_key_is_a_no_op(self) -> None:
        # The proposal-envelope schema (separate concern) should catch this;
        # validate_agent_payload only validates the *items* under the key.
        validate_agent_payload("demand_prophet", {"store_id": "x"})


class TestInventorySentinelValidation:
    def test_valid_actions_accept(self) -> None:
        payload = {
            "actions": [
                {
                    "store_id": "S1",
                    "sku_id": "K1",
                    "action_type": "reorder",
                    "quantity": 50,
                    "safety_stock_multiplier": 1.5,
                    "reorder_point": 20,
                    "confidence": 0.9,
                }
            ]
        }
        validate_agent_payload("inventory_sentinel", payload)

    def test_invalid_action_type_rejected(self) -> None:
        payload = {
            "actions": [
                {
                    "store_id": "S1",
                    "sku_id": "K1",
                    "action_type": "yeet",  # not in enum
                    "quantity": 10,
                    "safety_stock_multiplier": 1.5,
                    "reorder_point": 5,
                    "confidence": 0.5,
                }
            ]
        }
        with pytest.raises(SchemaValidationError):
            validate_agent_payload("inventory_sentinel", payload)


class TestRoutingNavigatorValidation:
    def test_valid_routes_accept(self) -> None:
        payload = {
            "routes": [
                {
                    "route_id": "00000000-0000-0000-0000-000000000001",
                    "rider_id": "R1",
                    "store_id": "S1",
                    "stops": [{"lat": 12.97, "lon": 77.59}],
                    "total_distance_km": 5.0,
                    "total_time_min": 12.0,
                }
            ]
        }
        validate_agent_payload("routing_navigator", payload)

    def test_empty_stops_rejected(self) -> None:
        payload = {
            "routes": [
                {
                    "route_id": "00000000-0000-0000-0000-000000000001",
                    "rider_id": "R1",
                    "store_id": "S1",
                    "stops": [],  # minItems: 1
                    "total_distance_km": 0.0,
                    "total_time_min": 0.0,
                }
            ]
        }
        with pytest.raises(SchemaValidationError):
            validate_agent_payload("routing_navigator", payload)


class TestNoOpForUnregisteredAgent:
    def test_unregistered_agent_is_passthrough(self) -> None:
        # Calling for an agent not in either map is a no-op (helper is
        # deliberately permissive so callers can route safely without
        # branching).
        validate_agent_payload("nonexistent_agent", {"foo": "bar"})
