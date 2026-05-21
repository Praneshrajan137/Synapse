"""Tests for synapse_common.schema_registry — Layer 3 (Contract).

Pydantic↔schema round-trip parity is the central invariant of ADR-025: a
payload that validates against the JSON Schema must Pydantic-parse, and a
payload Pydantic produces must validate against the JSON Schema.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from synapse_common.models import InventoryAction, RoutePlan
from synapse_common.schema_registry import (
    SchemaRegistry,
    SchemaViolation,
    get_registry,
    validate,
    validates_schema,
)

pytestmark = pytest.mark.contract


def test_registry_loads_all_schemas() -> None:
    reg = SchemaRegistry()
    # Sanity: at minimum the documented domain + a2a schemas are present.
    assert "domain.inventory_action" in reg.names
    assert "domain.route_plan" in reg.names
    assert "domain.consensus_decision" in reg.names
    assert "a2a.jsonrpc" in reg.names
    assert "a2a.agent_card" in reg.names


def test_inventory_action_pydantic_roundtrip() -> None:
    action = InventoryAction(
        store_id="store_42",
        sku_id="sku_7",
        action_type="reorder",
        quantity=12.0,
        safety_stock_multiplier=1.5,
        reorder_point=20.0,
        confidence=0.91,
    )
    validate(action, "domain.inventory_action")  # must not raise


def test_inventory_action_rejects_bad_action_type() -> None:
    payload: dict[str, Any] = {
        "store_id": "s",
        "sku_id": "k",
        "action_type": "not-a-real-action",
        "quantity": 1.0,
        "safety_stock_multiplier": 1.0,
        "reorder_point": 0.0,
        "confidence": 0.5,
    }
    with pytest.raises(SchemaViolation) as excinfo:
        validate(payload, "domain.inventory_action")
    assert "action_type" in str(excinfo.value)


def test_inventory_action_rejects_extra_fields() -> None:
    payload = {
        "store_id": "s",
        "sku_id": "k",
        "action_type": "reorder",
        "quantity": 1.0,
        "safety_stock_multiplier": 1.0,
        "reorder_point": 0.0,
        "confidence": 0.5,
        "rogue_field": "should fail",
    }
    with pytest.raises(SchemaViolation):
        validate(payload, "domain.inventory_action")


def test_route_plan_pydantic_roundtrip() -> None:
    plan = RoutePlan(
        rider_id="r1",
        store_id="s1",
        stops=[{"sku": "x", "lat": 12.97, "lon": 77.59}],
        total_distance_km=8.4,
        total_time_min=23.5,
        fuel_estimate_liters=0.6,
        freshness_violations=0,
    )
    validate(plan, "domain.route_plan")


def test_unknown_schema_raises() -> None:
    with pytest.raises(KeyError):
        validate({"foo": "bar"}, "domain.does_not_exist")


def test_a2a_envelope_schema_accepts_causal_ids() -> None:
    envelope = {
        "jsonrpc": "2.0",
        "method": "proposal",
        "params": {"x": 1},
        "id": "abc",
        "correlation_id": "corr-42",
        "causation_id": "parent-7",
    }
    validate(envelope, "a2a.jsonrpc")


def test_a2a_envelope_rejects_bad_method() -> None:
    envelope = {"jsonrpc": "2.0", "method": "not-a-method", "id": "abc"}
    with pytest.raises(SchemaViolation):
        validate(envelope, "a2a.jsonrpc")


def test_validates_schema_decorator_sync() -> None:
    @validates_schema("domain.inventory_action")
    def make_action() -> InventoryAction:
        return InventoryAction(
            store_id="s",
            sku_id="k",
            action_type="reorder",
            quantity=1.0,
            safety_stock_multiplier=1.0,
            reorder_point=0.0,
            confidence=0.5,
        )

    out = make_action()
    assert out.quantity == 1.0


def test_validates_schema_decorator_rejects_bad_payload() -> None:
    @validates_schema("domain.inventory_action")
    def bad() -> dict[str, Any]:
        return {"store_id": "s"}  # missing required fields

    with pytest.raises(SchemaViolation):
        bad()


def test_validates_schema_decorator_async() -> None:
    @validates_schema("domain.inventory_action")
    async def make_action() -> InventoryAction:
        return InventoryAction(
            store_id="s",
            sku_id="k",
            action_type="reorder",
            quantity=1.0,
            safety_stock_multiplier=1.0,
            reorder_point=0.0,
            confidence=0.5,
        )

    out = asyncio.run(make_action())
    assert out.action_type == "reorder"


def test_validates_schema_list_payload() -> None:
    @validates_schema("domain.inventory_action")
    def batch() -> list[InventoryAction]:
        return [
            InventoryAction(
                store_id="s",
                sku_id=f"k{i}",
                action_type="reorder",
                quantity=float(i),
                safety_stock_multiplier=1.1,
                reorder_point=0.0,
                confidence=0.5,
            )
            for i in range(3)
        ]

    out = batch()
    assert len(out) == 3


def test_global_registry_is_cached() -> None:
    a = get_registry()
    b = get_registry()
    assert a is b
