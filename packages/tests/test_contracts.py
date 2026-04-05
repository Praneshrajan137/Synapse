"""Tests for design-by-contract invariants (ADR-015, Layer 5)."""
from __future__ import annotations

import pytest

from synapse_common.contracts import (
    confidence_gate,
    ensure_append_only,
    essential_price_cap,
    jitter_bounds,
)


class TestConfidenceGate:

    def test_above_threshold_passes(self) -> None:
        assert confidence_gate(confidence=0.8, threshold=0.7, escalated=False) is True

    def test_below_threshold_fails(self) -> None:
        assert confidence_gate(confidence=0.5, threshold=0.7, escalated=False) is False

    def test_below_threshold_but_escalated_passes(self) -> None:
        assert confidence_gate(confidence=0.5, threshold=0.7, escalated=True) is True


class TestEssentialPriceCap:

    def test_essential_at_cap(self) -> None:
        assert essential_price_cap(is_essential=True, multiplier=1.3) is True

    def test_essential_above_cap(self) -> None:
        assert essential_price_cap(is_essential=True, multiplier=1.5) is False

    def test_non_essential_above_cap(self) -> None:
        assert essential_price_cap(is_essential=False, multiplier=2.0) is True


class TestAppendOnly:

    def test_growth(self) -> None:
        assert ensure_append_only(old_length=5, new_length=6) is True

    def test_same_length(self) -> None:
        assert ensure_append_only(old_length=5, new_length=5) is True

    def test_shrink_violates(self) -> None:
        assert ensure_append_only(old_length=5, new_length=4) is False


class TestJitterBounds:

    def test_within_bounds(self) -> None:
        assert jitter_bounds(delay=0.3, cap=60.0, base=0.5, attempt=0) is True

    def test_zero_delay(self) -> None:
        assert jitter_bounds(delay=0.0, cap=60.0, base=0.5, attempt=0) is True

    def test_exceeds_bounds(self) -> None:
        assert jitter_bounds(delay=100.0, cap=60.0, base=0.5, attempt=0) is False
