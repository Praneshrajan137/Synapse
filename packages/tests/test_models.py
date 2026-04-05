"""Tests for SYNAPSE domain models — validates I-3, I-6, I-13, I-14."""
from __future__ import annotations

from uuid import uuid4

import pytest

from synapse_common.models import (
    AgentName,
    AgentProposal,
    ContextMessage,
    DecisionTier,
    DemandForecast,
    MessageStatus,
    PricingDecision,
)


class TestDeterministicSerialization:
    """I-13: KV-cache preservation requires deterministic JSON."""

    def test_sort_keys_produces_identical_bytes(self) -> None:
        forecast = DemandForecast(
            sku_id="sku_001",
            store_id="ds_kor_01",
            forecast_timestamp="2026-04-01T00:00:00",
            horizons={"1h": 45.0, "15min": 12.5, "24h": 180.0},
            lower_90={"1h": 30.0, "15min": 8.0, "24h": 120.0},
            upper_90={"1h": 60.0, "15min": 17.0, "24h": 240.0},
            confidence=0.85,
            drift_detected=False,
        )
        json_1 = forecast.to_deterministic_json()
        json_2 = forecast.to_deterministic_json()
        assert json_1 == json_2, "Deterministic serialization must be byte-identical"

    def test_no_whitespace_in_serialization(self) -> None:
        msg = ContextMessage(
            source="demand_prophet",
            content={"key": "value", "nested": {"a": 1}},
        )
        serialized = msg.to_deterministic_json()
        assert ": " not in serialized
        assert ", " not in serialized


class TestPricingGuardrail:
    """I-6: Hard 1.3x cap on essentials. NOT learnable. NOT overridable."""

    def test_essential_item_at_cap_succeeds(self) -> None:
        decision = PricingDecision(
            sku_id="sku_rice", store_id="ds_kor_01", category_id="cat_essentials",
            is_essential=True, base_price=100.0, multiplier=1.3, final_price=130.0,
        )
        assert decision.multiplier == 1.3

    def test_essential_item_above_cap_raises(self) -> None:
        with pytest.raises(ValueError, match="hard cap 1.3x"):
            PricingDecision(
                sku_id="sku_rice", store_id="ds_kor_01", category_id="cat_essentials",
                is_essential=True, base_price=100.0, multiplier=1.5, final_price=150.0,
            )

    def test_non_essential_above_cap_succeeds(self) -> None:
        decision = PricingDecision(
            sku_id="sku_chips", store_id="ds_kor_01", category_id="cat_snacks",
            is_essential=False, base_price=50.0, multiplier=1.8, final_price=90.0,
        )
        assert decision.multiplier == 1.8


class TestContextMessageImmutability:
    """I-14: Context messages are frozen (immutable once created)."""

    def test_context_message_is_frozen(self) -> None:
        msg = ContextMessage(
            source="orchestrator",
            content={"action": "test"},
        )
        with pytest.raises(Exception):
            msg.status = MessageStatus.ERROR  # type: ignore[misc]


class TestAgentProposalValidation:
    """I-3: Ontology-bound outputs validated against typed schemas."""

    def test_confidence_bounds(self) -> None:
        with pytest.raises(Exception):
            AgentProposal(
                agent_name=AgentName.DEMAND_PROPHET,
                decision_id=uuid4(),
                utility_score=0.8,
                confidence=1.5,
                justification_trace=["test"],
                payload={},
                tier=DecisionTier.TIER_1,
            )

    def test_valid_proposal(self) -> None:
        proposal = AgentProposal(
            agent_name=AgentName.DEMAND_PROPHET,
            decision_id=uuid4(),
            utility_score=0.8,
            confidence=0.9,
            justification_trace=["Forecast indicates high demand"],
            payload={"forecast": 45.0},
            tier=DecisionTier.TIER_2,
        )
        assert proposal.confidence == 0.9
