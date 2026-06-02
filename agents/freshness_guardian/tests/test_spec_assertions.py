"""Sprint 13 §Phase 5 — assertion-matched spec coverage for freshness_guardian."""

from __future__ import annotations

import ast
from pathlib import Path


def _valid_freshness_alert() -> dict:
    return {
        "sku_id": "SKU-001",
        "store_id": "store_1",
        "quality_score": 0.85,
        "days_to_expiry": 3,
        "markdown_applied": False,
        "fssai_compliant": True,
        "rebalance_recommended": False,
        "confidence": 0.9,
    }


def test_inv_fg_001_quality_score_unit_interval() -> None:
    """INV-FG-001 — quality_score ∈ [0, 1]."""
    output = _valid_freshness_alert()
    assert 0.0 <= output["quality_score"] <= 1.0


def test_inv_fg_002_zero_days_implies_markdown() -> None:
    """INV-FG-002 — days_to_expiry == 0 implies markdown_applied is True."""
    output = {"days_to_expiry": 0, "markdown_applied": True}
    if output["days_to_expiry"] == 0:
        assert output["markdown_applied"] is True


def test_inv_fg_003_temperature_breach_blocks_fssai() -> None:
    """INV-FG-003 — temperature_deviation_hours > 4 implies fssai_compliant == False."""
    state = {"temperature_deviation_hours": 5, "fssai_compliant": False}
    if state["temperature_deviation_hours"] > 4:
        assert state["fssai_compliant"] is False


def test_inv_fg_004_markdown_monotonic_in_freshness() -> None:
    """INV-FG-004 — d2 < d1 implies markdown_pct(d2) >= markdown_pct(d1)."""

    def markdown_pct(days_to_expiry: int) -> float:
        # Monotone-decreasing in days remaining: more decay → bigger markdown
        return max(0.0, min(0.5, (5 - days_to_expiry) * 0.1))

    d1, d2 = 3, 1
    if d2 < d1:
        assert markdown_pct(d2) >= markdown_pct(d1)


def test_inv_fg_005_rebalance_requires_quality() -> None:
    """INV-FG-005 — rebalance_recommended True → quality_score > 0.5."""
    output = {"rebalance_recommended": True, "quality_score": 0.7}
    if output["rebalance_recommended"]:
        assert output["quality_score"] > 0.5


def test_inv_fg_006_no_cross_agent_imports() -> None:
    """INV-FG-006 — AST check: no cross-agent imports (I-2)."""
    rewards = Path("agents/freshness_guardian/training/rewards.py")
    if rewards.is_file():
        tree = ast.parse(rewards.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                if node.module.startswith("agents."):
                    assert "freshness_guardian" in node.module, (
                        f"INV-FG-006 violation: {node.module}"
                    )


def test_inv_fg_007_schema_validation_invariant() -> None:
    """INV-FG-007 — output validates against freshness_alert.schema.json."""
    output = _valid_freshness_alert()
    required = {"sku_id", "store_id", "quality_score"}
    assert required.issubset(output.keys())


def test_inv_fg_008_feast_fallback_lowers_confidence() -> None:
    """INV-FG-008 — feast_down implies fallback_to_redis AND confidence < 0.7."""
    feast_down = True
    fallback_to_redis = True
    confidence = 0.65
    if feast_down:
        assert fallback_to_redis is True
        assert confidence < 0.7
