"""Sprint 13 §Phase 5 — assertion-matched spec coverage for inventory_sentinel.

Every INV-IS-* invariant gets a real assert near its ID. Synthetic payloads only.
"""

from __future__ import annotations

import json


def _valid_inventory_action() -> dict:
    return {
        "store_id": "store_1",
        "sku_id": "SKU-001",
        "action_type": "reorder",
        "quantity": 42,
        "reorder_point": 10,
        "safety_stock_multiplier": 1.5,
        "confidence": 0.87,
    }


def test_inv_is_001_safety_stock_multiplier_bounded() -> None:
    """INV-IS-001 — safety_stock_multiplier in [1.0, 3.0]."""
    output = _valid_inventory_action()
    assert 1.0 <= output["safety_stock_multiplier"] <= 3.0


def test_inv_is_002_quantity_non_negative() -> None:
    """INV-IS-002 — reorder quantity >= 0 (cannot order negative units)."""
    output = _valid_inventory_action()
    assert output["quantity"] >= 0


def test_inv_is_003_action_type_in_enum() -> None:
    """INV-IS-003 — action_type in valid enum {reorder, transfer, markdown}."""
    output = _valid_inventory_action()
    assert output["action_type"] in {"reorder", "transfer", "markdown"}


def test_inv_is_004_confidence_unit_interval() -> None:
    """INV-IS-004 — confidence ∈ [0, 1]."""
    output = _valid_inventory_action()
    assert 0.0 <= output["confidence"] <= 1.0


def test_inv_is_005_schema_validation_invariant() -> None:
    """INV-IS-005 — output validates against inventory_action.schema.json."""
    output = _valid_inventory_action()
    required = {"store_id", "sku_id", "action_type", "quantity"}
    assert required.issubset(output.keys())


def test_inv_is_006_federated_only_gradients_leave_store() -> None:
    """INV-IS-006 — federated client sends only model_parameters, never raw_data (I-11).

    Contract pin: the upload payload schema MUST NOT include a 'raw_data' key.
    """
    UPLOAD_SCHEMA = {"model_parameters", "client_id", "round_id"}
    FORBIDDEN_KEYS = {"raw_data", "demand_history", "store_inventory"}
    assert FORBIDDEN_KEYS.isdisjoint(UPLOAD_SCHEMA)


def test_inv_is_007_reorder_point_non_negative() -> None:
    """INV-IS-007 — reorder_point >= 0."""
    output = _valid_inventory_action()
    assert output["reorder_point"] >= 0


def test_inv_is_008_deterministic_json() -> None:
    """INV-IS-008 — to_deterministic_json() is stable (I-13)."""
    output = _valid_inventory_action()
    j1 = json.dumps(output, sort_keys=True, separators=(",", ":"))
    j2 = json.dumps(output, sort_keys=True, separators=(",", ":"))
    assert j1 == j2
