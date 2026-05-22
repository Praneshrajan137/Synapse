"""
SYNAPSE Orchestrator — Decision tier classifier and tool masking (ADR-022).

Classifies incoming decisions into one of four tiers, determining whether
the fast-path (Tier 1-2) or full consensus (Tier 3-4) is used.
80 % of decisions MUST be Tier 1 to satisfy I-10.
"""

from __future__ import annotations

import asyncio
from typing import Any, cast

import structlog
from synapse_common.models import DecisionTier

from orchestrator.consensus.models import TierClassification

logger = structlog.get_logger(__name__)

TIER_CRITERIA: dict[str, dict[str, Any]] = {
    DecisionTier.TIER_1: {
        "conditions": [
            "single_agent_sufficient",
            "no_cross_agent_conflict",
            "historical_precedent_exists",
            "confidence_above_0.9",
        ],
        "model": None,
        "latency_budget_ms": 100,
    },
    DecisionTier.TIER_2: {
        "conditions": [
            "two_to_three_agents_involved",
            "low_conflict_probability",
            "moderate_confidence",
        ],
        "model": "phi3:mini",
        "latency_budget_ms": 500,
    },
    DecisionTier.TIER_3: {
        "conditions": [
            "multi_agent_conflict",
            "novel_scenario",
            "moderate_to_low_confidence",
        ],
        "model": "deepseek-r1:14b",
        "latency_budget_ms": 15_000,
    },
    DecisionTier.TIER_4: {
        "conditions": [
            "system_wide_impact",
            "disruption_scenario",
            "requires_monte_carlo",
            "low_confidence",
        ],
        "model": "llama3.3:70b-instruct-q4_K_M",
        "latency_budget_ms": 120_000,
    },
}


class TierRouter:
    """Classifies incoming decisions into tiers and applies tool masking."""

    def __init__(self, semantic_cache: Any = None) -> None:
        self._semantic_cache = semantic_cache

    def classify(self, decision_request: dict[str, Any]) -> TierClassification:
        """Classify a decision request into the appropriate tier."""
        agents_involved = decision_request.get("agents_involved", [])
        n_agents = len(agents_involved) if agents_involved else 1
        avg_confidence = float(decision_request.get("avg_confidence", 0.5))
        disruption_active = bool(decision_request.get("disruption_active", False))
        requires_twin = bool(decision_request.get("requires_twin_simulation", False))

        reasons: list[str] = []

        if disruption_active or requires_twin:
            tier = DecisionTier.TIER_4
            reasons.append("disruption_active" if disruption_active else "requires_twin")
        elif n_agents > 3 or avg_confidence < 0.4:
            tier = DecisionTier.TIER_3
            reasons.append(f"agents={n_agents}, confidence={avg_confidence:.2f}")
        elif n_agents > 1 or avg_confidence < 0.9:
            tier = DecisionTier.TIER_2
            reasons.append(f"agents={n_agents}, confidence={avg_confidence:.2f}")
        else:
            tier = DecisionTier.TIER_1
            reasons.append("single_agent, high_confidence")

        criteria = TIER_CRITERIA[tier]
        classification = TierClassification(
            tier=tier,
            confidence=avg_confidence,
            reasons=reasons,
            model=criteria["model"],
            latency_budget_ms=criteria["latency_budget_ms"],
        )
        logger.info(
            "tier_classified",
            tier=tier.value,
            model=criteria["model"],
            latency_budget_ms=criteria["latency_budget_ms"],
            reasons=reasons,
        )
        return classification

    def get_tool_mask(self, tier: DecisionTier) -> dict[str, str]:
        """Return prefill constraint for Ollama based on tier (ADR-022)."""
        if tier in (DecisionTier.TIER_1, DecisionTier.TIER_2):
            return {"prefill": '{"name": "rl_'}
        return {}

    def get_model_for_tier(self, tier: DecisionTier) -> str | None:
        """Return Ollama model name.  ``None`` for Tier 1 (no LLM)."""
        return cast("str | None", TIER_CRITERIA[tier]["model"])

    async def maybe_prewarm(
        self,
        tier: DecisionTier,
        escalation_prob: float,
        ollama_client: Any,
    ) -> None:
        """Pre-load DeepSeek-R1 when a Tier 2 decision looks likely to escalate."""
        if tier == DecisionTier.TIER_2 and escalation_prob > 0.3:
            asyncio.create_task(ollama_client.warm_model("deepseek-r1:14b"))
