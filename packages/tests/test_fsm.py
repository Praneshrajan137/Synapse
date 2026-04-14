"""Tests for shared Agent FSM base types (ADR-024)."""
from __future__ import annotations

import time
from unittest.mock import patch

from synapse_common.fsm import (
    RECITATION_INTERVAL,
    AgentState,
    BaseAgentStateMachine,
    Transition,
)


class _TestFSM(BaseAgentStateMachine):
    """Concrete subclass with real transitions for testing."""

    AGENT_NAME = "test_agent"
    ACTIVE_OBJECTIVE = "Minimise waste"
    ACTIVE_CONSTRAINTS = ["I-6", "I-14"]
    TRANSITIONS = [
        Transition(AgentState.IDLE, AgentState.PROPOSING, "request_received"),
        Transition(AgentState.PROPOSING, AgentState.DEBATING, "proposal_submitted"),
        Transition(AgentState.DEBATING, AgentState.EXECUTING, "consensus_reached"),
        Transition(AgentState.EXECUTING, AgentState.LEARNING, "execution_done"),
        Transition(AgentState.LEARNING, AgentState.IDLE, "learning_done"),
        Transition(
            AgentState.IDLE,
            AgentState.PROPOSING,
            "timed_request",
            timeout_seconds=0.0,
        ),
    ]


class TestAgentState:

    def test_all_states_exist(self) -> None:
        expected = {"IDLE", "PROPOSING", "DEBATING", "EXECUTING", "LEARNING", "ERROR"}
        assert {s.value for s in AgentState} == expected

    def test_str_enum_behaviour(self) -> None:
        assert str(AgentState.IDLE) == "IDLE"


class TestTransition:

    def test_construction(self) -> None:
        t = Transition(AgentState.IDLE, AgentState.PROPOSING, "go", guard="ready")
        assert t.from_state == AgentState.IDLE
        assert t.to_state == AgentState.PROPOSING
        assert t.trigger == "go"
        assert t.guard == "ready"
        assert t.timeout_seconds is None

    def test_timeout_optional(self) -> None:
        t = Transition(AgentState.IDLE, AgentState.ERROR, "fail", timeout_seconds=5.0)
        assert t.timeout_seconds == 5.0


class TestBaseAgentStateMachine:

    def test_initial_state_is_idle(self) -> None:
        fsm = _TestFSM()
        assert fsm.state == AgentState.IDLE
        assert fsm.tool_call_count == 0

    def test_successful_transition(self) -> None:
        fsm = _TestFSM()
        assert fsm.transition("request_received") is True
        assert fsm.state == AgentState.PROPOSING

    def test_invalid_trigger_returns_false(self) -> None:
        fsm = _TestFSM()
        assert fsm.transition("nonexistent_trigger") is False
        assert fsm.state == AgentState.IDLE

    def test_wrong_state_returns_false(self) -> None:
        fsm = _TestFSM()
        assert fsm.transition("consensus_reached") is False
        assert fsm.state == AgentState.IDLE

    def test_timeout_triggers_error(self) -> None:
        fsm = _TestFSM()
        time.sleep(0.01)
        assert fsm.transition("timed_request") is False
        assert fsm.state == AgentState.ERROR

    def test_full_lifecycle(self) -> None:
        fsm = _TestFSM()
        assert fsm.transition("request_received")
        assert fsm.transition("proposal_submitted")
        assert fsm.transition("consensus_reached")
        assert fsm.transition("execution_done")
        assert fsm.transition("learning_done")
        assert fsm.state == AgentState.IDLE

    def test_record_tool_call_increments(self) -> None:
        fsm = _TestFSM()
        for _ in range(RECITATION_INTERVAL - 1):
            assert fsm.record_tool_call() is None
        assert fsm.tool_call_count == RECITATION_INTERVAL - 1

    def test_record_tool_call_returns_recitation_at_interval(self) -> None:
        fsm = _TestFSM()
        for _ in range(RECITATION_INTERVAL - 1):
            fsm.record_tool_call()
        result = fsm.record_tool_call()
        assert result is not None
        assert result["agent"] == "test_agent"
        assert result["active_objective"] == "Minimise waste"
        assert result["active_constraints"] == ["I-6", "I-14"]

    def test_recite_objective_shape(self) -> None:
        fsm = _TestFSM()
        rec = fsm.recite_objective()
        assert set(rec.keys()) == {
            "agent",
            "current_state",
            "tool_calls_completed",
            "active_objective",
            "active_constraints",
            "remaining_steps",
        }
        assert rec["current_state"] == "IDLE"

    def test_remaining_steps_per_state(self) -> None:
        fsm = _TestFSM()
        for state in AgentState:
            fsm._state = state
            steps = fsm._remaining_steps()
            assert isinstance(steps, list)
            assert len(steps) >= 1

    def test_reset(self) -> None:
        fsm = _TestFSM()
        fsm.transition("request_received")
        for _ in range(5):
            fsm.record_tool_call()
        fsm.reset()
        assert fsm.state == AgentState.IDLE
        assert fsm.tool_call_count == 0
