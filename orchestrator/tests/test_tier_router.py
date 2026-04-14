"""SYNAPSE Orchestrator — Tier classification tests (I-10)."""

from __future__ import annotations

import pytest
from synapse_common.models import DecisionTier

from orchestrator.consensus.tier_router import TierRouter


@pytest.fixture()
def router() -> TierRouter:
    return TierRouter()


class TestTierClassification:
    def test_single_agent_high_confidence_is_tier1(self, router: TierRouter) -> None:
        result = router.classify({"agents_involved": ["demand_prophet"], "avg_confidence": 0.95})
        assert result.tier == DecisionTier.TIER_1

    def test_two_agents_moderate_confidence_is_tier2(self, router: TierRouter) -> None:
        result = router.classify(
            {
                "agents_involved": ["demand_prophet", "inventory_sentinel"],
                "avg_confidence": 0.8,
            }
        )
        assert result.tier == DecisionTier.TIER_2

    def test_many_agents_low_confidence_is_tier3(self, router: TierRouter) -> None:
        result = router.classify(
            {
                "agents_involved": ["a", "b", "c", "d"],
                "avg_confidence": 0.35,
            }
        )
        assert result.tier == DecisionTier.TIER_3

    def test_disruption_active_is_tier4(self, router: TierRouter) -> None:
        result = router.classify({"disruption_active": True, "avg_confidence": 0.9})
        assert result.tier == DecisionTier.TIER_4

    def test_twin_simulation_required_is_tier4(self, router: TierRouter) -> None:
        result = router.classify({"requires_twin_simulation": True})
        assert result.tier == DecisionTier.TIER_4


class TestToolMasking:
    def test_tier1_forces_rl_prefill(self, router: TierRouter) -> None:
        mask = router.get_tool_mask(DecisionTier.TIER_1)
        assert "prefill" in mask
        assert mask["prefill"].startswith('{"name": "rl_')

    def test_tier3_no_constraint(self, router: TierRouter) -> None:
        mask = router.get_tool_mask(DecisionTier.TIER_3)
        assert mask == {}


class TestModelSelection:
    def test_tier1_no_model(self, router: TierRouter) -> None:
        assert router.get_model_for_tier(DecisionTier.TIER_1) is None

    def test_tier2_lightweight_model(self, router: TierRouter) -> None:
        model = router.get_model_for_tier(DecisionTier.TIER_2)
        assert model in ("phi3:mini", "qwen2.5:7b")

    def test_tier3_deepseek(self, router: TierRouter) -> None:
        assert router.get_model_for_tier(DecisionTier.TIER_3) == "deepseek-r1:14b"

    def test_tier4_llama(self, router: TierRouter) -> None:
        assert "70b" in (router.get_model_for_tier(DecisionTier.TIER_4) or "")
