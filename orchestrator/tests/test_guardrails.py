"""SYNAPSE Orchestrator — NeMo Guardrails tests (I-6, I-5)."""

from __future__ import annotations

import pytest
from synapse_common.models import ConsensusDecision, DecisionTier

from orchestrator.guardrails.rules import GuardrailEngine


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


# =============================================================================
# Sprint 13 §Phase 3 — mutation-resistant boundary + structure pins.
# Target: <10% mutmut survival on guardrails (CLAUDE.md). Each assertion
# pinpoints one mutation class (comparator flip, coefficient bump,
# essential-set tampering, enforcement-action change, short-circuit drop).
# =============================================================================


from orchestrator.guardrails.rules import (  # noqa: E402
    ESSENTIAL_CATEGORIES,
    HARD_GUARDRAILS,
)


class TestRuleCatalogueStructure:
    """Pin the static rule catalogue — drift here = guardrail relaxation."""

    def test_essential_categories_exact_membership(self) -> None:
        expected = {
            "rice", "dal", "milk", "bread", "eggs",
            "cooking_oil", "vegetables", "fruits",
        }
        assert set(ESSENTIAL_CATEGORIES) == expected

    def test_essential_price_cap_value_pinned(self) -> None:
        assert HARD_GUARDRAILS["essential_price_cap"]["max_multiplier"] == 1.3

    def test_rider_shift_limit_value_pinned(self) -> None:
        assert HARD_GUARDRAILS["rider_shift_limit"]["max_hours"] == 10

    def test_service_level_floor_pinned(self) -> None:
        assert HARD_GUARDRAILS["service_level_minimum"]["min_fill_rate"] == 0.85

    def test_confidence_default_pinned(self) -> None:
        assert HARD_GUARDRAILS["confidence_floor"]["default_threshold"] == 0.7

    def test_hard_guardrail_keys_complete(self) -> None:
        assert set(HARD_GUARDRAILS.keys()) == {
            "essential_price_cap", "rider_shift_limit",
            "service_level_minimum", "privacy_boundary", "confidence_floor",
        }


class TestPriceCapBoundary:
    """Three-point boundary sweep on the 1.3 price-cap. A mutant flipping
    `>` to `>=` (or `1.3` to `1.4`) gets caught by one of the three."""

    def test_just_under_cap_no_clip(self, engine: GuardrailEngine) -> None:
        d = _decision(pricing_actions=[{"category": "milk", "multiplier": 1.299}])
        engine.validate_decision(d)
        assert d.selected_action["pricing_actions"][0]["multiplier"] == 1.299

    def test_exactly_at_cap_no_clip(self, engine: GuardrailEngine) -> None:
        d = _decision(pricing_actions=[{"category": "milk", "multiplier": 1.3}])
        engine.validate_decision(d)
        assert d.selected_action["pricing_actions"][0]["multiplier"] == 1.3

    def test_just_above_cap_clips(self, engine: GuardrailEngine) -> None:
        d = _decision(pricing_actions=[{"category": "milk", "multiplier": 1.301}])
        engine.validate_decision(d)
        assert d.selected_action["pricing_actions"][0]["multiplier"] == 1.3


@pytest.mark.parametrize("category", sorted(ESSENTIAL_CATEGORIES))
def test_every_essential_category_capped(category: str, engine: GuardrailEngine) -> None:
    """A mutant that removes any single category from ESSENTIAL_CATEGORIES
    leaves that staple unpriced-capped. Parametrise over every category."""
    d = _decision(pricing_actions=[{"category": category, "multiplier": 5.0}])
    engine.validate_decision(d)
    assert d.selected_action["pricing_actions"][0]["multiplier"] == 1.3, (
        f"Essential {category!r} not clipped"
    )


class TestRiderShiftBoundary:
    def test_just_under_limit_passes(self, engine: GuardrailEngine) -> None:
        d = _decision(routing_actions=[{"rider_shift_hours": 9.999}])
        passed, _ = engine.validate_decision(d)
        assert passed is True

    def test_at_limit_passes(self, engine: GuardrailEngine) -> None:
        d = _decision(routing_actions=[{"rider_shift_hours": 10}])
        passed, _ = engine.validate_decision(d)
        assert passed is True

    def test_just_above_limit_fails(self, engine: GuardrailEngine) -> None:
        d = _decision(routing_actions=[{"rider_shift_hours": 10.001}])
        passed, _ = engine.validate_decision(d)
        assert passed is False


class TestConfidenceBoundary:
    def test_just_under_threshold_fails(self, engine: GuardrailEngine) -> None:
        d = _decision(confidence=0.699)
        passed, _ = engine.validate_decision(d)
        assert passed is False

    def test_at_threshold_passes(self, engine: GuardrailEngine) -> None:
        d = _decision(confidence=0.7)
        passed, _ = engine.validate_decision(d)
        assert passed is True

    def test_custom_threshold_higher(self) -> None:
        """A mutant that ignores the constructor arg fails this."""
        eng = GuardrailEngine(confidence_threshold=0.95)
        d = _decision(confidence=0.90)
        passed, _ = eng.validate_decision(d)
        assert passed is False


class TestServiceLevelMinimum:
    def test_fill_rate_just_under_min_violates(self, engine: GuardrailEngine) -> None:
        d = _decision()
        d.selected_action["predicted_fill_rate"] = 0.849
        _, violations = engine.validate_decision(d)
        assert any("Predicted fill rate" in v for v in violations)

    def test_fill_rate_at_min_no_violation(self, engine: GuardrailEngine) -> None:
        d = _decision()
        d.selected_action["predicted_fill_rate"] = 0.85
        _, violations = engine.validate_decision(d)
        assert not any("Predicted fill rate" in v for v in violations)


class TestEarlyExitContract:
    """If rider-shift or confidence fails, service_level check MUST be
    skipped — pin the short-circuit so a mutant that drops the early
    return doesn't silently report extra violations."""

    def test_rider_shift_fail_short_circuits(self, engine: GuardrailEngine) -> None:
        d = _decision(routing_actions=[{"rider_shift_hours": 12}])
        d.selected_action["predicted_fill_rate"] = 0.1  # would normally violate
        passed, violations = engine.validate_decision(d)
        assert passed is False
        # Service level violation MUST NOT pile on top
        assert not any("Predicted fill rate" in v for v in violations)

    def test_confidence_fail_short_circuits(self, engine: GuardrailEngine) -> None:
        d = _decision(confidence=0.1)
        d.selected_action["predicted_fill_rate"] = 0.1
        passed, violations = engine.validate_decision(d)
        assert passed is False
        assert not any("Predicted fill rate" in v for v in violations)


class TestMultiViolationComposite:
    def test_two_routing_actions_one_violates(self, engine: GuardrailEngine) -> None:
        d = _decision(routing_actions=[
            {"rider_shift_hours": 8}, {"rider_shift_hours": 12},
        ])
        passed, _ = engine.validate_decision(d)
        assert passed is False

    def test_clip_only_passes_with_violation_recorded(
        self, engine: GuardrailEngine,
    ) -> None:
        """When the only violation is a CLIP, `passed` is True but the
        violations list is non-empty. Pin the dual return."""
        d = _decision(pricing_actions=[{"category": "rice", "multiplier": 2.0}])
        passed, violations = engine.validate_decision(d)
        assert passed is True
        assert len(violations) == 1
