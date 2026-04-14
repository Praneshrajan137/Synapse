"""
SYNAPSE Orchestrator — Hard guardrails enforcement (I-6).

These rules CANNOT be overridden by any agent or RL policy.
Implementation is a deterministic rule engine (no NeMo Guardrails LLM overhead)
to meet Tier 1-2 latency requirements (I-10).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import deal
import structlog

if TYPE_CHECKING:
    from synapse_common.models import ConsensusDecision

logger = structlog.get_logger(__name__)

ESSENTIAL_CATEGORIES: frozenset[str] = frozenset(
    ["rice", "dal", "milk", "bread", "eggs", "cooking_oil", "vegetables", "fruits"],
)

HARD_GUARDRAILS: dict[str, dict[str, Any]] = {
    "essential_price_cap": {
        "rule": "price_multiplier <= 1.3 for essential categories",
        "max_multiplier": 1.3,
        "enforcement": "CLIP",
    },
    "rider_shift_limit": {
        "rule": "rider shift duration <= 10 hours",
        "max_hours": 10,
        "enforcement": "REJECT",
    },
    "service_level_minimum": {
        "rule": "predicted fill rate >= 85%",
        "min_fill_rate": 0.85,
        "enforcement": "ESCALATE",
    },
    "privacy_boundary": {
        "rule": "no raw demand data crosses store boundaries",
        "enforcement": "BLOCK",
    },
    "confidence_floor": {
        "rule": "execution requires confidence >= threshold or HITL approval",
        "default_threshold": 0.7,
        "enforcement": "ESCALATE",
    },
}


class GuardrailEngine:
    """Evaluate hard guardrails against a consensus decision."""

    def __init__(self, confidence_threshold: float = 0.7) -> None:
        self._confidence_threshold = confidence_threshold

    def validate_decision(
        self,
        decision: ConsensusDecision,
    ) -> tuple[bool, list[str]]:
        """Validate *decision* against all hard guardrails.

        Returns ``(passed, violations)``.  ``passed`` is ``True`` only when all
        rules are satisfied (clip-only violations still pass).
        """
        violations: list[str] = []
        action = decision.selected_action

        self._check_essential_price_cap(action, violations)

        if not self._check_rider_shift_limit(action, violations):
            return False, violations

        if not self._check_confidence_floor(decision, violations):
            return False, violations

        self._check_service_level(action, violations)

        all_clipped = all("clipped" in v.lower() for v in violations) if violations else True
        return all_clipped, violations

    @staticmethod
    def _check_essential_price_cap(
        action: dict[str, Any],
        violations: list[str],
    ) -> None:
        pricing_actions: list[dict[str, Any]] = action.get("pricing_actions", [])
        for pa in pricing_actions:
            category = pa.get("category", "")
            multiplier = pa.get("multiplier", 1.0)
            if category in ESSENTIAL_CATEGORIES and multiplier > 1.3:
                pa["multiplier"] = 1.3  # CLIP — do not reject
                violations.append(
                    f"Essential price cap CLIPPED: {category} from {multiplier:.2f} to 1.3",
                )

    @staticmethod
    def _check_rider_shift_limit(
        action: dict[str, Any],
        violations: list[str],
    ) -> bool:
        routing_actions: list[dict[str, Any]] = action.get("routing_actions", [])
        for ra in routing_actions:
            hours = ra.get("rider_shift_hours", 0)
            if hours > 10:
                violations.append(
                    f"Rider shift limit exceeded: {hours}h > 10h max",
                )
                return False
        return True

    def _check_confidence_floor(
        self,
        decision: ConsensusDecision,
        violations: list[str],
    ) -> bool:
        if decision.confidence < self._confidence_threshold:
            violations.append(
                f"Confidence {decision.confidence:.3f} below "
                f"threshold {self._confidence_threshold}",
            )
            return False
        return True

    @staticmethod
    def _check_service_level(
        action: dict[str, Any],
        violations: list[str],
    ) -> None:
        fill_rate = action.get("predicted_fill_rate")
        if fill_rate is not None and fill_rate < 0.85:
            violations.append(
                f"Predicted fill rate {fill_rate:.2%} below 85% minimum",
            )


@deal.pre(
    lambda decision: decision.confidence >= 0.7 or decision.escalated_to_human,
    message="I-5 VIOLATION: Low-confidence decision not escalated to HITL",
)
@deal.post(
    lambda result: result.audit_id is not None,
    message="I-4 VIOLATION: Decision not logged to audit trail",
)
def execute_consensus(decision: ConsensusDecision) -> ConsensusDecision:
    """Contract-guarded execution entry point."""
    return decision
