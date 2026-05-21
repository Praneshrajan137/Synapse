"""Tests for the centralized JSON-schema validator (Sprint 7, WS-2)."""

from __future__ import annotations

import pytest
from synapse_common.schemas import (
    SchemaValidationError,
    get_schema,
    known_schemas,
    validate_payload,
)


class TestRegistry:
    def test_known_schemas_include_demand_forecast(self) -> None:
        assert "demand_forecast" in known_schemas()

    def test_known_schemas_include_order_request(self) -> None:
        assert "order_request" in known_schemas()

    def test_get_schema_round_trips(self) -> None:
        s = get_schema("demand_forecast")
        assert s["type"] == "object"

    def test_get_schema_missing_raises(self) -> None:
        with pytest.raises(KeyError):
            get_schema("does_not_exist")


class TestOrderRequestValidation:
    def _valid_payload(self) -> dict[str, object]:
        return {
            "order_id": "00000000-0000-0000-0000-000000000001",
            "city": "bengaluru",
            "store_id": "store_42",
            "sku_id": "sku_99",
            "quantity": 2,
            "timestamp": "2026-05-06T12:00:00Z",
        }

    def test_valid_payload_passes(self) -> None:
        validate_payload("order_request", self._valid_payload())

    def test_unknown_city_fails(self) -> None:
        payload = self._valid_payload()
        payload["city"] = "delhi"
        with pytest.raises(SchemaValidationError) as exc:
            validate_payload("order_request", payload)
        assert "city" in str(exc.value)

    def test_zero_quantity_fails(self) -> None:
        payload = self._valid_payload()
        payload["quantity"] = 0
        with pytest.raises(SchemaValidationError):
            validate_payload("order_request", payload)

    def test_quantity_above_cap_fails(self) -> None:
        payload = self._valid_payload()
        payload["quantity"] = 9999
        with pytest.raises(SchemaValidationError):
            validate_payload("order_request", payload)

    def test_extra_field_rejected(self) -> None:
        payload = self._valid_payload()
        payload["extra"] = "no"
        with pytest.raises(SchemaValidationError):
            validate_payload("order_request", payload)


class TestDemandForecastValidation:
    def test_minimal_valid_forecast(self) -> None:
        validate_payload(
            "demand_forecast",
            {
                "sku_id": "sku_1",
                "store_id": "store_1",
                "forecast_timestamp": "2026-05-06T12:00:00Z",
                "horizons": {"15min": 1.0, "1h": 5.0, "6h": 30.0, "24h": 100.0, "7d": 700.0},
                "lower_90": {},
                "upper_90": {},
                "confidence": 0.9,
                "drift_detected": False,
            },
        )

    def test_negative_horizon_value_fails(self) -> None:
        with pytest.raises(SchemaValidationError):
            validate_payload(
                "demand_forecast",
                {
                    "sku_id": "x",
                    "store_id": "y",
                    "forecast_timestamp": "2026-05-06T12:00:00Z",
                    "horizons": {"15min": -1.0},
                    "lower_90": {},
                    "upper_90": {},
                    "confidence": 0.5,
                    "drift_detected": False,
                },
            )
