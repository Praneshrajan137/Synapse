"""SYNAPSE Orchestrator — NeMo Guardrails tests (I-6, I-5)."""
from __future__ import annotations

from uuid import uuid4

import pytest

from synapse_common.models import ConsensusDecision, DecisionTier

from orchestrator.guardrails.rules import ESSENTIAL_CATEGORIES, GuardrailEngine


@pytest.fixture()
def engine() -> GuardrailEngine:
    return GuardrailEngine(confidence_threshold=0.7)


def _decision(
    confidence: float = 0.85,
    pricing_actions: list | None = None,
    routing_actions: list | None = None,
) -> ConsensusDecision:
    action: dict = {}
    if pricing_actions is not None:
        action["pricing_actions"] = pricing_actions
    if routing_actions is not None:
        action["routing_actions"] = routing_actions
    return ConsensusDecision(
        tier=DecisionTier.TIER_2,
        proposals=[],
        selected_action=action,
        pareto_weights={"demand_accuracy": 1.0},
        confidence=confidence,
        audit_trace=["test"],
    )


class TestEssentialPriceCap:
    """I-6: Essential price cap 1.3x CLIPPED, not rejected."""

    def test_clips_essential_above_cap(self, engine: GuardrailEngine) -> None:
        d = _decision(pricing_actions=[{"category": "rice", "multiplier": 1.5}])
        passed, violations = engine.validate_decision(d)
        assert passed is True
        assert any("CLIPPED" in v for v in violations)
        assert d.selected_action["pricing_actions"][0]["multiplier"] == 1.3

    def test_passes_essential_at_cap(self, engine: GuardrailEngine) -> None:
        d = _decision(pricing_actions=[{"category": "milk", "multiplier": 1.3}])
        passed, violations = engine.validate_decision(d)
        assert passed is True
        assert len(violations) == 0

    def test_ignores_non_essential(self, engine: GuardrailEngine) -> None:
        d = _decision(pricing_actions=[{"category": "luxury_snack", "multiplier": 2.0}])
        passed, violations = engine.validate_decision(d)
        assert passed is True


class TestRiderShiftLimit:
    def test_rejects_over_10h(self, engine: GuardrailEngine) -> None:
        d = _decision(routing_actions=[{"rider_shift_hours": 12}])
        passed, violations = engine.validate_decision(d)
        assert passed is False
        assert any("shift" in v.lower() for v in violations)

    def test_passes_under_10h(self, engine: GuardrailEngine) -> None:
        d = _decision(routing_actions=[{"rider_shift_hours": 8}])
        passed, _ = engine.validate_decision(d)
        assert passed is True


class TestConfidenceFloor:
    """I-5: Below threshold triggers HITL escalation."""

    def test_rejects_low_confidence(self, engine: GuardrailEngine) -> None:
        d = _decision(confidence=0.5)
        passed, violations = engine.validate_decision(d)
        assert passed is False
        assert any("Confidence" in v for v in violations)

    def test_passes_high_confidence(self, engine: GuardrailEngine) -> None:
        d = _decision(confidence=0.9)
        passed, _ = engine.validate_decision(d)
        assert passed is True

    def test_threshold_boundary(self, engine: GuardrailEngine) -> None:
        d = _decision(confidence=0.7)
        passed, _ = engine.validate_decision(d)
        assert passed is True
