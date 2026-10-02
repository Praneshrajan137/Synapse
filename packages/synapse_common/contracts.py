"""
SYNAPSE Design-by-Contract — Runtime invariant enforcement via deal (ADR-015, Layer 5).
"""

from __future__ import annotations

from typing import Any

import deal


@deal.post(
    lambda result: result is not None and getattr(result, "id", None) is not None,
    message="I-4: an audit insertion must return the inserted row carrying a non-None id",
)
def validate_audit_insertion(result: Any) -> Any:
    """Every audit insertion must return a non-None result whose ``id`` is set (I-4).

    ``hasattr(result, "id")`` alone was vacuous for an ORM row: every mapped instance has
    an ``id`` attribute whether or not a key was ever assigned, so only ``result is not
    None`` could fail. Requiring the value itself to be non-None is what lets this catch a
    row that reached the caller without a primary key. Production caller since 2026-10-01:
    ``orchestrator.audit.logger.AuditLogger.log_decision``, after the commit.
    """
    return result


def confidence_gate(confidence: float, threshold: float, escalated: bool) -> bool:
    """Precondition: confidence >= threshold OR escalated to human (I-5)."""
    return confidence >= threshold or escalated


def essential_price_cap(is_essential: bool, multiplier: float) -> bool:
    """Invariant: essential items never exceed 1.3x. NOT learnable (I-6)."""
    if is_essential:
        return multiplier <= 1.3
    return True


def ensure_append_only(old_length: int, new_length: int) -> bool:
    """Context messages list can only grow. Never shrink (I-14)."""
    return new_length >= old_length


def jitter_bounds(delay: float, cap: float, base: float, attempt: int) -> bool:
    """Full Jitter delay must be in [0, min(cap, base * 2^attempt)] (ADR-016)."""
    max_expected = min(cap, base * (2**attempt))
    result: bool = 0 <= delay <= max_expected
    return result


def safe_positive_result(value: float) -> float:
    """Ensure non-negative results for quantities."""
    return max(0.0, value)


__all__ = [
    "deal",
    "validate_audit_insertion",
    "confidence_gate",
    "essential_price_cap",
    "ensure_append_only",
    "jitter_bounds",
    "safe_positive_result",
]
