"""Tests for SYNAPSE domain models — validates I-3, I-6, I-13, I-14."""
from __future__ import annotations

from uuid import uuid4

import pytest

from synapse_common.models import (
    AgentName,
    AgentProposal,
    ConsensusDecision,
    ContextMessage,
    DecisionTier,
    DemandForecast,
    HitlTimeoutAction,
    InventoryAction,
    MessageStatus,
    PricingDecision,
    RoutePlan,
    SynapseBaseModel,
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


class TestHitlTimeoutAction:

    def test_enum_values(self) -> None:
        assert HitlTimeoutAction.DEFER == "defer"
        assert HitlTimeoutAction.EXECUTE_TIER1 == "execute_tier1"
        assert HitlTimeoutAction.EXECUTE_LAST_KNOWN_GOOD == "execute_last_known_good"


class TestConsensusDecision:

    def test_valid_construction(self) -> None:
        proposal = AgentProposal(
            agent_name=AgentName.PRICING_ORACLE,
            decision_id=uuid4(),
            utility_score=0.7,
            confidence=0.85,
            justification_trace=["demand up"],
            payload={"price": 120},
            tier=DecisionTier.TIER_2,
        )
        decision = ConsensusDecision(
            tier=DecisionTier.TIER_2,
            proposals=[proposal],
            selected_action={"apply_price": 120},
            pareto_weights={"pricing_oracle": 0.6},
            confidence=0.85,
            audit_trace=["round-1"],
        )
        assert decision.confidence == 0.85
        assert decision.phase_reached == 1
        assert decision.debate_rounds == 0

    def test_frozen(self) -> None:
        decision = ConsensusDecision(
            tier=DecisionTier.TIER_1,
            proposals=[],
            selected_action={},
            pareto_weights={},
            confidence=0.5,
            audit_trace=[],
        )
        with pytest.raises(Exception):
            decision.confidence = 0.99  # type: ignore[misc]


class TestRoutePlan:

    def test_valid_construction(self) -> None:
        plan = RoutePlan(
            rider_id="rider-1",
            store_id="store-1",
            stops=[{"lat": 37.0, "lon": 127.0}],
            total_distance_km=15.5,
            total_time_min=30.0,
            fuel_estimate_liters=2.0,
            freshness_violations=0,
        )
        assert plan.total_distance_km == 15.5

    def test_negative_distance_rejected(self) -> None:
        with pytest.raises(Exception):
            RoutePlan(
                rider_id="r",
                store_id="s",
                stops=[],
                total_distance_km=-1.0,
                total_time_min=0.0,
                fuel_estimate_liters=0.0,
                freshness_violations=0,
            )


class TestInventoryAction:

    def test_valid_construction(self) -> None:
        action = InventoryAction(
            store_id="s1",
            sku_id="sku_001",
            action_type="reorder",
            quantity=50.0,
            safety_stock_multiplier=1.5,
            reorder_point=20.0,
            confidence=0.9,
        )
        assert action.action_type == "reorder"

    def test_safety_stock_out_of_range(self) -> None:
        with pytest.raises(Exception):
            InventoryAction(
                store_id="s1",
                sku_id="sku_001",
                action_type="reorder",
                quantity=10.0,
                safety_stock_multiplier=5.0,
                reorder_point=5.0,
                confidence=0.8,
            )

    def test_safety_stock_below_minimum(self) -> None:
        with pytest.raises(Exception):
            InventoryAction(
                store_id="s1",
                sku_id="sku_001",
                action_type="reorder",
                quantity=10.0,
                safety_stock_multiplier=0.5,
                reorder_point=5.0,
                confidence=0.8,
            )


class TestSynapseBaseModelExtra:

    def test_extra_fields_forbidden(self) -> None:
        with pytest.raises(Exception):
            ContextMessage(
                source="test",
                content={},
                unknown_field="boom",  # type: ignore[call-arg]
            )
