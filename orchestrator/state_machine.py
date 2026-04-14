"""
SYNAPSE Orchestrator — Lifecycle FSM with objective recitation (ADR-024).

The Orchestrator has additional states (COLLECTING, ARBITRATING, ESCALATED) beyond
the standard agent FSM.  It mirrors ``BaseAgentStateMachine`` interface from
``synapse_common.fsm`` while using an extended state enum.
"""

from __future__ import annotations

import time
from enum import Enum
from typing import Any

import structlog
from synapse_common.fsm import RECITATION_INTERVAL

logger = structlog.get_logger(__name__)


class OrchestratorState(str, Enum):
    """Extended state enum for the Orchestrator consensus lifecycle."""

    IDLE = "IDLE"
    COLLECTING = "COLLECTING"
    DEBATING = "DEBATING"
    ARBITRATING = "ARBITRATING"
    EXECUTING = "EXECUTING"
    LEARNING = "LEARNING"
    ERROR = "ERROR"
    ESCALATED = "ESCALATED"


class OrchestratorTransition:
    """State transition descriptor."""

    __slots__ = ("from_state", "to_state", "trigger", "guard", "timeout_seconds")

    def __init__(
        self,
        from_state: OrchestratorState,
        to_state: OrchestratorState,
        trigger: str,
        guard: str | None = None,
        timeout_seconds: float | None = None,
    ) -> None:
        self.from_state = from_state
        self.to_state = to_state
        self.trigger = trigger
        self.guard = guard
        self.timeout_seconds = timeout_seconds


ORCHESTRATOR_TRANSITIONS: list[OrchestratorTransition] = [
    OrchestratorTransition(
        OrchestratorState.IDLE,
        OrchestratorState.COLLECTING,
        "decision_request_received",
        guard="kafka_healthy",
    ),
    OrchestratorTransition(
        OrchestratorState.COLLECTING,
        OrchestratorState.DEBATING,
        "all_proposals_received",
        guard="tier >= 3 and conflict_detected",
        timeout_seconds=2.0,
    ),
    OrchestratorTransition(
        OrchestratorState.COLLECTING,
        OrchestratorState.EXECUTING,
        "all_proposals_received",
        guard="tier <= 2 or not conflict_detected",
        timeout_seconds=2.0,
    ),
    OrchestratorTransition(
        OrchestratorState.DEBATING,
        OrchestratorState.ARBITRATING,
        "convergence_or_max_rounds",
        timeout_seconds=30.0,
    ),
    OrchestratorTransition(
        OrchestratorState.ARBITRATING,
        OrchestratorState.EXECUTING,
        "pareto_solution_selected",
        guard="guardrails_passed and confidence >= threshold",
        timeout_seconds=5.0,
    ),
    OrchestratorTransition(
        OrchestratorState.ARBITRATING,
        OrchestratorState.ESCALATED,
        "guardrails_failed_or_low_confidence",
    ),
    OrchestratorTransition(
        OrchestratorState.ESCALATED,
        OrchestratorState.EXECUTING,
        "human_approved",
        timeout_seconds=300.0,
    ),
    OrchestratorTransition(
        OrchestratorState.ESCALATED,
        OrchestratorState.EXECUTING,
        "timeout_expired",
    ),
    OrchestratorTransition(
        OrchestratorState.EXECUTING,
        OrchestratorState.LEARNING,
        "execution_complete",
        timeout_seconds=10.0,
    ),
    OrchestratorTransition(
        OrchestratorState.LEARNING,
        OrchestratorState.IDLE,
        "updates_applied",
    ),
    OrchestratorTransition(
        OrchestratorState.COLLECTING,
        OrchestratorState.ERROR,
        "exception_raised",
    ),
    OrchestratorTransition(
        OrchestratorState.DEBATING,
        OrchestratorState.ERROR,
        "exception_raised",
    ),
    OrchestratorTransition(
        OrchestratorState.EXECUTING,
        OrchestratorState.ERROR,
        "exception_raised",
    ),
    OrchestratorTransition(
        OrchestratorState.ERROR,
        OrchestratorState.IDLE,
        "error_handled",
        timeout_seconds=30.0,
    ),
]


class OrchestratorStateMachine:
    """Lifecycle FSM for the Orchestrator meta-agent.

    Follows the interface of ``BaseAgentStateMachine`` but uses
    ``OrchestratorState`` which includes COLLECTING, ARBITRATING, and ESCALATED.
    """

    AGENT_NAME: str = "orchestrator"
    TRANSITIONS: list[OrchestratorTransition] = ORCHESTRATOR_TRANSITIONS
    ACTIVE_OBJECTIVE: str = (
        "Resolve multi-agent consensus for the current decision request "
        "by collecting proposals, mediating debate, Pareto-arbitrating, "
        "and dispatching execution across 8 supply-chain agents"
    )
    ACTIVE_CONSTRAINTS: list[str] = [
        "I-4: Every decision logged to append-only audit trail",
        "I-5: Below-threshold confidence triggers HITL escalation",
        "I-6: Essential price cap 1.3x clipped, not learned",
        "I-10: Tier 1-2 bypass debate + arbitration (<100ms / <500ms)",
        "I-13: KV-cache stable prefix, deterministic serialization",
        "I-14: Context messages append-only during active lifecycle",
    ]

    def __init__(self) -> None:
        self._state: OrchestratorState = OrchestratorState.IDLE
        self._tool_call_count: int = 0
        self._transition_history: list[dict[str, Any]] = []
        self._state_entry_time: float = time.monotonic()

    @property
    def state(self) -> OrchestratorState:
        return self._state

    @property
    def tool_call_count(self) -> int:
        return self._tool_call_count

    def transition(self, trigger: str) -> bool:
        """Attempt state transition.  Returns ``True`` on success."""
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
                        self._state = OrchestratorState.ERROR
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
        """Record tool call; returns recitation dict if interval reached (ADR-024)."""
        self._tool_call_count += 1
        if self._tool_call_count % RECITATION_INTERVAL == 0:
            return self.recite_objective()
        return None

    def recite_objective(self) -> dict[str, Any]:
        """Structured objective recitation (ADR-024)."""
        recitation: dict[str, Any] = {
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
        steps_map: dict[OrchestratorState, list[str]] = {
            OrchestratorState.IDLE: ["Await decision request"],
            OrchestratorState.COLLECTING: [
                "Collect proposals",
                "Classify tier",
                "Debate or execute",
            ],
            OrchestratorState.DEBATING: [
                "LLM-mediated debate",
                "Arbitrate",
                "Execute",
                "Learn",
            ],
            OrchestratorState.ARBITRATING: [
                "Pareto optimize",
                "Guardrail check",
                "Execute",
                "Learn",
            ],
            OrchestratorState.EXECUTING: [
                "Dispatch actions",
                "Log audit",
                "Learn",
            ],
            OrchestratorState.LEARNING: [
                "Update Meta-RL",
                "Update semantic cache",
                "Return to IDLE",
            ],
            OrchestratorState.ESCALATED: ["Await human response", "Execute or defer"],
            OrchestratorState.ERROR: ["Handle error", "Return to IDLE"],
        }
        return steps_map.get(self._state, ["Unknown"])

    def reset(self) -> None:
        """Reset FSM to IDLE for a new consensus round."""
        self._state = OrchestratorState.IDLE
        self._tool_call_count = 0
        self._state_entry_time = time.monotonic()
