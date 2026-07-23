"""Tests for synapse_common.synthetic — the single owner of the
traffic-generator detection rule (ADR-044 D5).

The rule must behave identically for live ``ContextMessage`` objects (the
orchestrator's outbox path) and their JSONB-round-tripped dict form (the
decisions API read path) — that duality is the whole point of the module.
"""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st
from synapse_common.models import ContextMessage
from synapse_common.synthetic import (
    AUTONOMOUS_ORDER_PREFIX,
    SYNTHETIC_ORDER_PREFIX,
    initiator_of_decision,
    initiator_of_order_id,
    is_autonomous_order_id,
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


class TestInitiatorRule:
    """ADR-053 — the three-way origin classifier."""

    def test_autonomous_id_matches(self) -> None:
        assert is_autonomous_order_id("auto-bengaluru-reorder_point-3") is True
        assert is_autonomous_order_id(AUTONOMOUS_ORDER_PREFIX + "x") is True

    def test_autonomous_id_does_not_match_others(self) -> None:
        assert is_autonomous_order_id("synthetic-1-1") is False
        assert is_autonomous_order_id("ORD-1") is False
        assert is_autonomous_order_id(None) is False

    def test_initiator_of_order_id_three_ways(self) -> None:
        assert initiator_of_order_id("auto-blr-reorder_point-1") == "autonomous"
        assert initiator_of_order_id("synthetic-1718000000-7") == "synthetic"
        assert initiator_of_order_id("ORD-2026-000123") == "operator"
        assert initiator_of_order_id(None) == "operator"

    def test_autonomous_is_never_synthetic(self) -> None:
        """The load-bearing honesty guarantee: an autonomous decision must not
        be reported as a demo pulse (ADR-053)."""
        auto_id = "auto-mumbai-reorder_point-9"
        assert is_synthetic_order_id(auto_id) is False
        assert initiator_of_order_id(auto_id) == "autonomous"


class TestInitiatorDecisionDetection:
    def test_autonomous_decision_detected(self) -> None:
        messages = [_request_message("auto-bengaluru-reorder_point-2")]
        assert initiator_of_decision(messages) == "autonomous"
        # ...and it is NOT flagged synthetic.
        assert is_synthetic_decision(messages) is False

    def test_synthetic_decision_classified(self) -> None:
        messages = [_request_message("synthetic-1718000000-7")]
        assert initiator_of_decision(messages) == "synthetic"

    def test_operator_decision_is_default(self) -> None:
        assert initiator_of_decision([_request_message("ORD-1")]) == "operator"
        assert initiator_of_decision([]) == "operator"

    def test_live_context_message_object(self) -> None:
        msg = ContextMessage(
            source="orchestrator",
            content={
                "type": "decision_request",
                "tier": "tier_1",
                "request": {"order_id": "auto-blr-reorder_point-1"},
            },
        )
        assert initiator_of_decision([msg]) == "autonomous"

    def test_malformed_never_raises(self) -> None:
        assert initiator_of_decision([{"no_content": True}, None]) == "operator"


class TestInitiatorProperties:
    """The classifier is TOTAL and its outputs are mutually exclusive."""

    @given(st.text())
    def test_total_and_disjoint(self, order_id: str) -> None:
        result = initiator_of_order_id(order_id)
        assert result in ("autonomous", "synthetic", "operator")
        # Exactly one predicate holds, consistently with the classifier.
        auto = is_autonomous_order_id(order_id)
        synth = is_synthetic_order_id(order_id)
        assert not (auto and synth)  # prefixes cannot overlap
        if auto:
            assert result == "autonomous"
        elif synth:
            assert result == "synthetic"
        else:
            assert result == "operator"

    @given(st.one_of(st.none(), st.integers(), st.lists(st.text()), st.text()))
    def test_never_raises_on_any_input(self, order_id: object) -> None:
        assert initiator_of_order_id(order_id) in ("autonomous", "synthetic", "operator")
