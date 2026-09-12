"""Guardrail configuration totality and the I-11 privacy boundary (R5.2, R5.3).

Unit-level companion to Property 23 (task 8.4). Covers the two facts the audit
finding turns on: a declared guardrail with no check function is a construction
failure naming the rule, and the `privacy_boundary` BLOCK declaration is now
backed by an implementation.
"""

from __future__ import annotations

from typing import Any

import pytest
from synapse_common.models import ConsensusDecision, DecisionTier

from orchestrator.guardrails.rules import (
    BLOCKING_ENFORCEMENTS,
    HARD_GUARDRAILS,
    GuardrailConfigurationError,
    GuardrailEngine,
    check_method_name,
    scan_privacy_boundary,
    unimplemented_guardrails,
)


def _decision(action: dict[str, Any], confidence: float = 0.9) -> ConsensusDecision:
    return ConsensusDecision(
        tier=DecisionTier.TIER_1,
        proposals=[],
        selected_action=action,
        pareto_weights={"demand_accuracy": 1.0},
        confidence=confidence,
        audit_trace=["test"],
    )


class TestConfigurationTotality:
    """Every declared rule resolves to a check function, or construction fails."""

    def test_shipped_configuration_is_total(self) -> None:
        missing = unimplemented_guardrails(
            HARD_GUARDRAILS,
            GuardrailEngine.available_check_functions(),
        )
        assert missing == ()
        GuardrailEngine(confidence_threshold=0.7)  # constructs without raising

    def test_every_declared_rule_has_a_check_function(self) -> None:
        available = GuardrailEngine.available_check_functions()
        for rule_name in HARD_GUARDRAILS:
            assert check_method_name(rule_name) in available, rule_name

    def test_declared_block_without_implementation_fails_construction(self) -> None:
        config = dict(HARD_GUARDRAILS)
        config["cross_city_transfer_ban"] = {"rule": "invented", "enforcement": "BLOCK"}

        with pytest.raises(GuardrailConfigurationError) as excinfo:
            GuardrailEngine(guardrails=config)

        message = str(excinfo.value)
        assert "cross_city_transfer_ban" in message
        assert "_check_cross_city_transfer_ban" in message

    def test_blocking_only_reading_names_the_same_rule(self) -> None:
        config = {"cross_city_transfer_ban": {"enforcement": "BLOCK"}}
        missing = unimplemented_guardrails(
            config,
            GuardrailEngine.available_check_functions(),
            enforcements_requiring_check=BLOCKING_ENFORCEMENTS,
        )
        assert missing == (("cross_city_transfer_ban", "BLOCK"),)

    def test_privacy_boundary_declaration_is_backed_by_an_implementation(self) -> None:
        assert HARD_GUARDRAILS["privacy_boundary"]["enforcement"] == "BLOCK"
        assert "_check_privacy_boundary" in GuardrailEngine.available_check_functions()

    def test_essential_price_cap_is_still_a_clip(self) -> None:
        assert HARD_GUARDRAILS["essential_price_cap"]["enforcement"] == "CLIP"


class TestPrivacyBoundary:
    """I-11: no raw demand payload crosses a store boundary."""

    def test_single_store_raw_demand_passes(self) -> None:
        engine = GuardrailEngine()
        decision = _decision(
            {"store_id": "blr_001", "demand_history": [4, 7, 2], "action_type": "reorder"},
        )
        passed, violations = engine.validate_decision(decision)
        assert passed is True
        assert violations == []

    def test_cross_store_raw_demand_blocks(self) -> None:
        engine = GuardrailEngine()
        decision = _decision(
            {
                "source_store_id": "blr_001",
                "target_store_id": "blr_002",
                "demand_history": [4, 7, 2],
            },
        )
        passed, violations = engine.validate_decision(decision)
        assert passed is False
        assert any("privacy boundary blocked" in v.lower() for v in violations)
        assert any("demand_history" in v for v in violations)

    def test_declared_recipient_blocks_even_with_one_store(self) -> None:
        engine = GuardrailEngine()
        decision = _decision(
            {"store_id": "blr_001", "share_with": ["blr_002"], "order_ids": ["o-1"]},
        )
        passed, violations = engine.validate_decision(decision)
        assert passed is False
        assert any("order_ids" in v for v in violations)

    def test_cross_store_aggregate_without_raw_demand_passes(self) -> None:
        engine = GuardrailEngine()
        decision = _decision(
            {
                "source_store_id": "blr_001",
                "target_store_id": "blr_002",
                "transfer_quantity": 40,
                "forecast_mean": 12.5,
            },
        )
        passed, violations = engine.validate_decision(decision)
        assert passed is True
        assert violations == []

    def test_empty_raw_demand_field_is_not_a_payload(self) -> None:
        scan = scan_privacy_boundary(
            {"source_store_id": "a", "target_store_id": "b", "raw_demand": []},
        )
        assert scan.raw_demand_paths == ()
        assert scan.violates_privacy_boundary is False

    def test_nested_raw_demand_is_found(self) -> None:
        scan = scan_privacy_boundary(
            {
                "actions": [
                    {"store_id": "a", "payload": {"customer_ids": ["c-1"]}},
                    {"store_id": "b"},
                ],
            },
        )
        assert scan.store_ids == ("a", "b")
        assert scan.raw_demand_paths == ("actions[0].payload.customer_ids",)
        assert scan.violates_privacy_boundary is True

    def test_exhausted_scan_budget_fails_closed(self) -> None:
        scan = scan_privacy_boundary({"nested": {"deep": {"store_id": "a"}}}, max_nodes=1)
        assert scan.truncated is True
        assert scan.violates_privacy_boundary is True

    def test_empty_action_passes(self) -> None:
        engine = GuardrailEngine()
        passed, violations = engine.validate_decision(_decision({}))
        assert passed is True
        assert violations == []
