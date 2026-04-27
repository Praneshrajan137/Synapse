"""Layer 5 (Design-by-Contract) -- guardrails contracts.

Exercises the ``@deal.pre`` / ``@deal.post`` contracts on
``orchestrator.guardrails.rules.execute_consensus`` and on the
``GuardrailEngine`` invariants (I-5 confidence floor, I-6 essential price cap,
rider shift limit, fill-rate floor).

The DbC layer is intentionally narrow -- it asserts that contract violations
are *raised*, not silently passed. It complements:

* the unit layer (``orchestrator/tests/test_guardrails.py``) which checks
  business logic, and
* the mutation layer which mutates ``rules.py`` and verifies these very tests
  catch the mutations (CLAUDE.md gate: <10% surviving on guardrails).
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import deal
import pytest
from synapse_common.models import (
    AgentName,
    AgentProposal,
    ConsensusDecision,
    DecisionTier,
)

from orchestrator.guardrails.rules import (
    ESSENTIAL_CATEGORIES,
    GuardrailEngine,
    execute_consensus,
)

pytestmark = pytest.mark.dbc


# --------------------------------------------------------------------------- helpers


def _decision(
    *,
    confidence: float = 0.9,
    escalated: bool = False,
    action: dict[str, Any] | None = None,
) -> ConsensusDecision:
    """Build a ConsensusDecision with sensible defaults for contract testing."""
    proposal = AgentProposal(
        agent_name=AgentName.PRICING_ORACLE,
        decision_id=uuid4(),
        utility_score=0.8,
        confidence=confidence,
        justification_trace=["dbc-test"],
        payload={},
        tier=DecisionTier.TIER_2,
    )
    return ConsensusDecision(
        timestamp=datetime.now(UTC),
        tier=DecisionTier.TIER_2,
        proposals=[proposal],
        selected_action=action or {"pricing_actions": [], "routing_actions": []},
        pareto_weights={"pricing_oracle": 1.0},
        confidence=confidence,
        escalated_to_human=escalated,
        audit_trace=["dbc-test"],
        audit_id=uuid4(),
    )


# --------------------------------------------------------------------------- execute_consensus


class TestExecuteConsensusContracts:
    """``@deal.pre`` / ``@deal.post`` contracts on the execute_consensus entry."""

    def test_high_confidence_decision_passes(self) -> None:
        decision = _decision(confidence=0.95)
        out = execute_consensus(decision)
        assert out.confidence == 0.95

    def test_low_confidence_without_escalation_violates_pre(self) -> None:
        decision = _decision(confidence=0.5, escalated=False)
        with pytest.raises(deal.PreContractError):
            execute_consensus(decision)

    def test_low_confidence_with_escalation_passes(self) -> None:
        # I-5: low confidence is allowed iff escalated to a human.
        decision = _decision(confidence=0.5, escalated=True)
        out = execute_consensus(decision)
        assert out.confidence == 0.5
        assert out.escalated_to_human is True

    def test_post_requires_audit_id(self) -> None:
        # The @deal.post requires a non-None audit_id; building a Pydantic
        # ConsensusDecision with audit_id=None and confidence high enough
        # would still violate the postcondition.
        proposal = AgentProposal(
            agent_name=AgentName.PRICING_ORACLE,
            decision_id=uuid4(),
            utility_score=0.8,
            confidence=0.9,
            justification_trace=["dbc-test"],
            payload={},
            tier=DecisionTier.TIER_2,
        )
        decision = ConsensusDecision(
            tier=DecisionTier.TIER_2,
            proposals=[proposal],
            selected_action={"pricing_actions": [], "routing_actions": []},
            pareto_weights={"pricing_oracle": 1.0},
            confidence=0.9,
            audit_trace=["dbc-test"],
            audit_id=None,  # <-- violates @deal.post
        )
        with pytest.raises(deal.PostContractError):
            execute_consensus(decision)


# --------------------------------------------------------------------------- GuardrailEngine


class TestGuardrailEngineContracts:
    """Invariant-level contract tests on GuardrailEngine.validate_decision."""

    def test_essential_price_cap_clip(self) -> None:
        engine = GuardrailEngine()
        category = next(iter(ESSENTIAL_CATEGORIES))
        decision = _decision(
            action={
                "pricing_actions": [{"category": category, "multiplier": 1.7}],
                "routing_actions": [],
            },
        )
        passed, violations = engine.validate_decision(decision)
        # CLIP path: violation recorded but the decision still "passes".
        assert passed is True
        assert any("CLIPPED" in v for v in violations)
        # The action mutated in place to the cap value.
        assert decision.selected_action["pricing_actions"][0]["multiplier"] == 1.3

    def test_rider_shift_limit_rejects(self) -> None:
        engine = GuardrailEngine()
        decision = _decision(
            action={
                "pricing_actions": [],
                "routing_actions": [{"rider_shift_hours": 12}],
            },
        )
        passed, violations = engine.validate_decision(decision)
        assert passed is False
        assert any("Rider shift" in v for v in violations)

    def test_confidence_floor_rejects_low_confidence(self) -> None:
        engine = GuardrailEngine(confidence_threshold=0.7)
        decision = _decision(
            confidence=0.5,
            escalated=True,  # makes ConsensusDecision build OK
        )
        passed, violations = engine.validate_decision(decision)
        assert passed is False
        assert any("Confidence" in v for v in violations)

    def test_service_level_records_violation_but_clips(self) -> None:
        engine = GuardrailEngine()
        decision = _decision(
            action={
                "pricing_actions": [],
                "routing_actions": [],
                "predicted_fill_rate": 0.6,
            },
        )
        passed, violations = engine.validate_decision(decision)
        # service-level violation is informational (not in the early-return path),
        # so passed remains True with violations attached.
        assert any("fill rate" in v.lower() for v in violations)
        assert passed is False  # not all violations are clip-only -> not passed

    @pytest.mark.parametrize("multiplier", [1.0, 1.15, 1.30])
    def test_essential_below_or_at_cap_no_clip(self, multiplier: float) -> None:
        engine = GuardrailEngine()
        category = next(iter(ESSENTIAL_CATEGORIES))
        decision = _decision(
            action={
                "pricing_actions": [{"category": category, "multiplier": multiplier}],
                "routing_actions": [],
            },
        )
        _, violations = engine.validate_decision(decision)
        assert not any("CLIPPED" in v for v in violations)
        assert decision.selected_action["pricing_actions"][0]["multiplier"] == multiplier
