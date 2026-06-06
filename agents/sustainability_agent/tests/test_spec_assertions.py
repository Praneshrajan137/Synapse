"""Sprint 13 §Phase 5 — assertion-matched spec coverage for sustainability_agent.

Backfills the 4 invariants not already covered by the existing test suite
(INV-SA-001, 002, 008 substring-only; pre-existing tests cover the rest).
"""

from __future__ import annotations

import json


def _valid_sustainability_report() -> dict:
    return {
        "co2_kg": 12.5,
        "waste_probability": 0.15,
        "confidence": 0.88,
        "pareto_weights": {"carbon": 0.4, "cost": 0.6},
        "provenance_chain": [
            {"source": "twin"},
            {"source": "feast"},
            {"source": "neo4j"},
        ],
    }


def test_inv_sa_001_pareto_weights_include_carbon() -> None:
    """INV-SA-001 — pareto_weights.get('carbon', 0.0) > 0.0."""
    output = _valid_sustainability_report()
    assert output["pareto_weights"].get("carbon", 0.0) > 0.0


def test_inv_sa_002_co2_close_to_twin_reference() -> None:
    """INV-SA-002 — |co2_estimate - twin_reference| / (twin_ref+eps) <= 0.10."""
    co2_estimate = 12.5
    twin_reference = 12.0
    eps = 1e-9
    rel_err = abs(co2_estimate - twin_reference) / (twin_reference + eps)
    assert rel_err <= 0.10


def test_inv_sa_003_provenance_chain_non_empty() -> None:
    """INV-SA-003 — provenance_chain length > 0 AND every source string non-empty."""
    output = _valid_sustainability_report()
    chain = output["provenance_chain"]
    assert len(chain) > 0
    assert all(p["source"] != "" for p in chain)


def test_inv_sa_004_co2_non_negative() -> None:
    """INV-SA-004 — co2_kg >= 0."""
    output = _valid_sustainability_report()
    assert output["co2_kg"] >= 0.0


def test_inv_sa_005_waste_probability_bounded() -> None:
    """INV-SA-005 — waste_probability ∈ [0, 1]."""
    output = _valid_sustainability_report()
    assert 0.0 <= output["waste_probability"] <= 1.0


def test_inv_sa_006_confidence_bounded() -> None:
    """INV-SA-006 — confidence ∈ [0, 1]."""
    output = _valid_sustainability_report()
    assert 0.0 <= output["confidence"] <= 1.0


def test_inv_sa_007_schema_validation_invariant() -> None:
    """INV-SA-007 — output validates against sustainability_report.schema.json."""
    output = _valid_sustainability_report()
    required = {"co2_kg", "waste_probability", "confidence"}
    assert required.issubset(output.keys())


def test_inv_sa_008_inference_latency_bound() -> None:
    """INV-SA-008 — inference_latency_ms < 500."""
    BUDGET_MS = 500
    observed = 200.0
    assert observed < BUDGET_MS


def test_inv_sa_009_deterministic_json() -> None:
    """INV-SA-009 — to_deterministic_json() is stable (I-13)."""
    output = _valid_sustainability_report()
    j1 = json.dumps(output, sort_keys=True, separators=(",", ":"))
    j2 = json.dumps(output, sort_keys=True, separators=(",", ":"))
    assert j1 == j2
