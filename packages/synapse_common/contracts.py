"""
SYNAPSE Design-by-Contract — Runtime invariant enforcement via deal (ADR-015, Layer 5).
"""

from __future__ import annotations

from typing import Any

import deal


@deal.post(lambda result: result is not None and hasattr(result, "id"))
def validate_audit_insertion(result: Any) -> Any:
    """Every audit insertion must return a non-None result with an id."""
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
