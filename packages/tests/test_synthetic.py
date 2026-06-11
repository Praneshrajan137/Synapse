"""Tests for synapse_common.synthetic — the single owner of the
traffic-generator detection rule (ADR-044 D5).

The rule must behave identically for live ``ContextMessage`` objects (the
orchestrator's outbox path) and their JSONB-round-tripped dict form (the
decisions API read path) — that duality is the whole point of the module.
"""

from __future__ import annotations

from synapse_common.models import ContextMessage
from synapse_common.synthetic import (
    SYNTHETIC_ORDER_PREFIX,
    is_synthetic_decision,
    is_synthetic_order_id,
)


class TestOrderIdRule:
    def test_traffic_generator_id_matches(self) -> None:
        assert is_synthetic_order_id("synthetic-1718000000-42") is True

    def test_prefix_constant_is_the_rule(self) -> None:
        assert is_synthetic_order_id(SYNTHETIC_ORDER_PREFIX + "x") is True

    def test_real_order_id_does_not_match(self) -> None:
        assert is_synthetic_order_id("ORD-2026-000123") is False

    def test_prefix_must_be_at_start(self) -> None:
        assert is_synthetic_order_id("real-synthetic-1") is False

    def test_non_string_is_real(self) -> None:
        assert is_synthetic_order_id(None) is False
        assert is_synthetic_order_id(12345) is False
        assert is_synthetic_order_id(["synthetic-1"]) is False


def _request_message(order_id: object) -> dict[str, object]:
    """JSONB-shaped decision_request context message (the API read path)."""
    return {
        "source": "orchestrator",
        "content": {
            "type": "decision_request",
            "tier": "tier_2",
            "request": {"order_id": order_id, "store_id": "STORE_BLR_001"},
        },
        "status": "active",
    }


class TestDecisionDetection:
    def test_synthetic_request_detected_in_dict_form(self) -> None:
        messages = [_request_message("synthetic-1718000000-7")]
        assert is_synthetic_decision(messages) is True

    def test_real_request_is_real(self) -> None:
        assert is_synthetic_decision([_request_message("ORD-1")]) is False

    def test_detects_among_other_messages(self) -> None:
        messages = [
            {"source": "demand_prophet", "content": {"type": "proposal"}},
            _request_message("synthetic-1-1"),
            {"source": "orchestrator", "content": {"type": "pareto_result"}},
        ]
        assert is_synthetic_decision(messages) is True

    def test_live_context_message_objects(self) -> None:
        """The orchestrator outbox path passes ContextMessage objects."""
        msg = ContextMessage(
            source="orchestrator",
            content={
                "type": "decision_request",
                "tier": "tier_1",
                "request": {"order_id": "synthetic-2-9"},
            },
        )
        assert is_synthetic_decision([msg]) is True

    def test_missing_order_id_is_real(self) -> None:
        messages = [
            {
                "source": "orchestrator",
                "content": {"type": "decision_request", "request": {"store_id": "s1"}},
            }
        ]
        assert is_synthetic_decision(messages) is False

    def test_empty_context_is_real(self) -> None:
        assert is_synthetic_decision([]) is False

    def test_malformed_entries_never_raise(self) -> None:
        """A missing tag must never hide (or crash) a real decision."""
        messages = [
            {"no_content": True},
            {"content": "not-a-mapping"},
            {"content": {"type": "decision_request", "request": "not-a-mapping"}},
            None,
        ]
        assert is_synthetic_decision(messages) is False
