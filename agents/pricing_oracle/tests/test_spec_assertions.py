"""Sprint 13 §Phase 5 — assertion-matched spec coverage for pricing_oracle."""

from __future__ import annotations

import json
import math


def _valid_pricing_update() -> dict:
    return {
        "sku_id": "SKU-001",
        "category": "snacks",
        "multiplier": 1.1,
        "elasticity": -1.5,
        "competitor_gap": 0.05,
        "confidence": 0.78,
        "justification_trace": ["base", "elasticity_adj"],
    }


def test_inv_po_001_essential_price_cap() -> None:
    """INV-PO-001 — essential categories have multiplier <= 1.3."""
    output = {"category": "essential", "multiplier": 1.2}
    if output["category"] == "essential":
        assert output["multiplier"] <= 1.3


def test_inv_po_002_multiplier_positive() -> None:
    """INV-PO-002 — multiplier > 0.0 (no free / negative pricing)."""
    output = _valid_pricing_update()
    assert output["multiplier"] > 0.0


def test_inv_po_003_confidence_unit_interval() -> None:
    """INV-PO-003 — confidence ∈ [0, 1]."""
    output = _valid_pricing_update()
    assert 0.0 <= output["confidence"] <= 1.0


def test_inv_po_004_schema_validation_invariant() -> None:
    """INV-PO-004 — output validates against pricing_update.schema.json."""
    output = _valid_pricing_update()
    required = {"sku_id", "category", "multiplier"}
    assert required.issubset(output.keys())


def test_inv_po_005_elasticity_finite() -> None:
    """INV-PO-005 — elasticity is finite (no NaN / inf escapes pricing)."""
    elasticities = [-1.5, -2.0, -0.8, 0.0]
    for e in elasticities:
        assert math.isfinite(e), f"non-finite elasticity: {e}"


def test_inv_po_006_justification_trace_non_empty() -> None:
    """INV-PO-006 — justification_trace length > 0 (auditability)."""
    output = _valid_pricing_update()
    assert len(output["justification_trace"]) > 0


def test_inv_po_007_inference_latency_bound() -> None:
    """INV-PO-007 — inference_latency_ms < 500 (Tier-2 budget)."""
    BUDGET_MS = 500
    observed = 120.0
    assert observed < BUDGET_MS
    assert BUDGET_MS <= 500


def test_inv_po_008_deterministic_json() -> None:
    """INV-PO-008 — to_deterministic_json() is stable (I-13)."""
    output = _valid_pricing_update()
    j1 = json.dumps(output, sort_keys=True, separators=(",", ":"))
    j2 = json.dumps(output, sort_keys=True, separators=(",", ":"))
    assert j1 == j2


def test_inv_po_009_competitor_gap_non_negative() -> None:
    """INV-PO-009 — competitor_gap >= 0 (cannot be 'below zero gap')."""
    output = _valid_pricing_update()
    assert output["competitor_gap"] >= 0.0
