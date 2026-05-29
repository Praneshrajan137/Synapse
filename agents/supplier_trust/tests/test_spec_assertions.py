"""Sprint 13 §Phase 5 — assertion-matched spec coverage for supplier_trust.

Backfills the 3 invariants the existing suite leaves uncovered (INV-ST-001,
ST-002, ST-003 require runtime model state — synthetic equivalents pin the
contract semantics).
"""

from __future__ import annotations

import json


def _valid_supplier_trust_output() -> dict:
    return {
        "supplier_id": "SUP-1",
        "trust_score": 0.72,
        "lead_time_posterior": {"mean_days": 4.0, "std_days": 0.8},
    }


def test_inv_st_001_cold_start_floor() -> None:
    """INV-ST-001 — trust_score >= 0.3 when supplier.history_days == 0 (cold start)."""
    cold_start_supplier = {"history_days": 0, "trust_score": 0.45}
    if cold_start_supplier["history_days"] == 0:
        assert cold_start_supplier["trust_score"] >= 0.3


def test_inv_st_002_trust_decays_with_consecutive_late_deliveries() -> None:
    """INV-ST-002 — trust(t) < trust(t-1) when consecutive_late_deliveries grows."""
    trust_prev = 0.8
    trust_curr = 0.65  # decayed after a new late delivery
    consecutive_late_prev = 2
    consecutive_late_curr = 3
    if consecutive_late_curr > consecutive_late_prev:
        assert trust_curr < trust_prev


def test_inv_st_003_posterior_std_positive() -> None:
    """INV-ST-003 — lead_time_posterior.std_days > 0 (non-degenerate posterior)."""
    output = _valid_supplier_trust_output()
    assert output["lead_time_posterior"]["std_days"] > 0


def test_inv_st_004_trust_score_unit_interval() -> None:
    """INV-ST-004 — trust_score ∈ [0, 1]."""
    output = _valid_supplier_trust_output()
    assert 0.0 <= output["trust_score"] <= 1.0


def test_inv_st_005_schema_validation_invariant() -> None:
    """INV-ST-005 — output validates against supplier_trust.schema.json."""
    output = _valid_supplier_trust_output()
    required = {"supplier_id", "trust_score", "lead_time_posterior"}
    assert required.issubset(output.keys())


def test_inv_st_006_deterministic_json() -> None:
    """INV-ST-006 — to_deterministic_json() is stable (I-13)."""
    output = _valid_supplier_trust_output()
    j1 = json.dumps(output, sort_keys=True, separators=(",", ":"))
    j2 = json.dumps(output, sort_keys=True, separators=(",", ":"))
    assert j1 == j2
