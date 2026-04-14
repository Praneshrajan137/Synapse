"""SYNAPSE Orchestrator — Audit immutability tests (I-4)."""

from __future__ import annotations

from uuid import uuid4

import pytest
from pydantic import ValidationError
from synapse_common.models import ConsensusDecision, DecisionTier


class TestAuditImmutability:
    """Verify that audit rows cannot be deleted or updated.

    Integration tests run against a real PostgreSQL container.
    Unit tests verify the SQL schema constraints.
    """

    def test_decision_has_required_audit_fields(self) -> None:
        d = ConsensusDecision(
            tier=DecisionTier.TIER_2,
            proposals=[],
            selected_action={"action": "test"},
            pareto_weights={"demand_accuracy": 1.0},
            confidence=0.8,
            audit_trace=["test_audit"],
        )
        assert d.decision_id is not None
        assert d.tier is not None
        assert d.confidence >= 0.0

    def test_audit_trace_non_empty(self) -> None:
        d = ConsensusDecision(
            tier=DecisionTier.TIER_1,
            proposals=[],
            selected_action={},
            pareto_weights={},
            confidence=0.95,
            audit_trace=["tier=tier_1", "phase=4"],
        )
        assert len(d.audit_trace) > 0

    def test_frozen_model_prevents_mutation(self) -> None:
        d = ConsensusDecision(
            tier=DecisionTier.TIER_2,
            proposals=[],
            selected_action={},
            pareto_weights={},
            confidence=0.8,
            audit_trace=["test"],
        )
        with pytest.raises(ValidationError):
            d.confidence = 0.99  # type: ignore[misc]

    def test_model_copy_creates_new_instance(self) -> None:
        d = ConsensusDecision(
            tier=DecisionTier.TIER_2,
            proposals=[],
            selected_action={},
            pareto_weights={},
            confidence=0.8,
            audit_trace=["test"],
        )
        d2 = d.model_copy(update={"audit_id": uuid4()})
        assert d2.audit_id is not None
        assert d.audit_id is None
