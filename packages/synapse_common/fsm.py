"""
SYNAPSE -- Shared Agent Finite State Machine base types.
All agents import AgentState and Transition from here, NOT from each other.
This prevents cross-agent coupling while maintaining FSM consistency.
"""

from __future__ import annotations

import time
from enum import StrEnum
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

RECITATION_INTERVAL: int = 10


class AgentState(StrEnum):
    """Six-state FSM shared across all SYNAPSE agents."""

    IDLE = "IDLE"
    PROPOSING = "PROPOSING"
    DEBATING = "DEBATING"
    EXECUTING = "EXECUTING"
    LEARNING = "LEARNING"
    ERROR = "ERROR"


class Transition:
    """State transition with guard condition and timeout."""

    def __init__(
        self,
        from_state: AgentState,
        to_state: AgentState,
        trigger: str,
        guard: str | None = None,
        timeout_seconds: float | None = None,
    ) -> None:
        self.from_state = from_state
        self.to_state = to_state
        self.trigger = trigger
        self.guard = guard
        self.timeout_seconds = timeout_seconds


class BaseAgentStateMachine:
    """
    Base FSM for all SYNAPSE agents.
    Subclasses must set AGENT_NAME, TRANSITIONS, ACTIVE_OBJECTIVE, and ACTIVE_CONSTRAINTS.
    Implements structured recitation per ADR-024.
    """

    AGENT_NAME: str = "base"
    TRANSITIONS: list[Transition] = []
    ACTIVE_OBJECTIVE: str = ""
    ACTIVE_CONSTRAINTS: list[str] = []

    def __init__(self) -> None:
        self._state: AgentState = AgentState.IDLE
        self._tool_call_count: int = 0
        self._transition_history: list[dict[str, Any]] = []
        self._state_entry_time: float = time.monotonic()

    @property
    def state(self) -> AgentState:
        return self._state

    @property
    def tool_call_count(self) -> int:
        return self._tool_call_count

    def transition(self, trigger: str, context: dict[str, Any] | None = None) -> bool:
        """Attempt state transition. Returns True on success."""
        for t in self.TRANSITIONS:
            if t.from_state == self._state and t.trigger == trigger:
                if t.timeout_seconds is not None:
                    elapsed = time.monotonic() - self._state_entry_time
                    if elapsed > t.timeout_seconds:
                        logger.warning(
                            "state_timeout",
                            agent=self.AGENT_NAME,
                            from_state=self._state.value,
                            elapsed=elapsed,
                            timeout=t.timeout_seconds,
                        )
                        self._state = AgentState.ERROR
                        self._state_entry_time = time.monotonic()
                        return False

                prev = self._state
                self._state = t.to_state
                self._state_entry_time = time.monotonic()
                self._transition_history.append(
                    {
                        "from": prev.value,
                        "to": t.to_state.value,
                        "trigger": trigger,
                        "timestamp": time.time(),
                    }
                )
                logger.info(
                    "state_transition",
                    agent=self.AGENT_NAME,
                    from_state=prev.value,
                    to_state=t.to_state.value,
                    trigger=trigger,
                )
                return True

        logger.warning(
            "invalid_transition",
            agent=self.AGENT_NAME,
            current_state=self._state.value,
            trigger=trigger,
        )
        return False

    def record_tool_call(self) -> dict[str, Any] | None:
        """Record tool call. Returns recitation dict if interval reached (ADR-024)."""
        self._tool_call_count += 1
        if self._tool_call_count % RECITATION_INTERVAL == 0:
            return self.recite_objective()
        return None

    def recite_objective(self) -> dict[str, Any]:
        """Structured objective recitation (ADR-024)."""
        recitation = {
            "agent": self.AGENT_NAME,
            "current_state": self._state.value,
            "tool_calls_completed": self._tool_call_count,
            "active_objective": self.ACTIVE_OBJECTIVE,
            "active_constraints": self.ACTIVE_CONSTRAINTS,
            "remaining_steps": self._remaining_steps(),
        }
        logger.info("objective_recitation", **recitation)
        return recitation

    def _remaining_steps(self) -> list[str]:
        """Determine remaining steps based on current state."""
        steps_map: dict[AgentState, list[str]] = {
            AgentState.IDLE: ["Await request"],
            AgentState.PROPOSING: ["Submit proposal", "Enter debate", "Execute", "Learn"],
            AgentState.DEBATING: ["Revise proposal", "Reach consensus", "Execute", "Learn"],
            AgentState.EXECUTING: ["Publish result", "Log to MLflow", "Learn"],
            AgentState.LEARNING: ["Update policy", "Return to IDLE"],
            AgentState.ERROR: ["Handle error", "Return to IDLE"],
        }
        return steps_map.get(self._state, ["Unknown"])

    def reset(self) -> None:
        """Reset FSM to IDLE state."""
        self._state = AgentState.IDLE
        self._tool_call_count = 0
        self._state_entry_time = time.monotonic()
