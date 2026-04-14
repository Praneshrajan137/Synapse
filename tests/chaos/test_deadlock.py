from __future__ import annotations

import time
from collections.abc import Callable
from enum import IntEnum
from typing import Any

import pytest
import structlog
import structlog.testing

logger = structlog.get_logger()

pytestmark = pytest.mark.chaos


class AgentPriority(IntEnum):
    """Fixed priority for deadlock tie-breaking (higher = more authoritative)."""
    DEMAND_PROPHET = 8
    INVENTORY_SENTINEL = 7
    ROUTING_NAVIGATOR = 6
    PRICING_ORACLE = 5
    FRESHNESS_GUARDIAN = 4
    DISRUPTION_SHIELD = 3
    SUPPLIER_TRUST = 2
    SUSTAINABILITY = 1


class DebateRound:
    """Represents a single round of agent debate."""

    def __init__(self, round_number: int) -> None:
        self.round_number = round_number
        self.proposals: dict[str, dict] = {}
        self.has_conflict: bool = False

    def add_proposal(self, agent_name: str, proposal: dict) -> None:
        self.proposals[agent_name] = proposal

    def detect_conflicts(self) -> list[tuple[str, str, str]]:
        conflicts: list[tuple[str, str, str]] = []
        agents = list(self.proposals.keys())
        for i in range(len(agents)):
            for j in range(i + 1, len(agents)):
                a, b = agents[i], agents[j]
                if self.proposals[a].get("preferred_action") != self.proposals[b].get(
                    "preferred_action"
                ):
                    conflicts.append((a, b, "action_conflict"))
        self.has_conflict = len(conflicts) > 0
        return conflicts


class DeadlockDetector:
    """Detects circular dependencies and resolves via priority tie-breaking."""

    MAX_ROUNDS = 3
    TIMEOUT_SECONDS = 5.0

    def __init__(
        self,
        proposal_modifier: Callable[[dict[str, dict], int], dict[str, dict]] | None = None,
    ) -> None:
        self.rounds: list[DebateRound] = []
        self.resolution_method: str | None = None
        self.deadlock_detected: bool = False
        self._proposal_modifier = proposal_modifier

    def run_debate(self, agent_proposals: dict[str, dict]) -> dict:
        start = time.monotonic()
        current_proposals = dict(agent_proposals)

        for round_num in range(1, self.MAX_ROUNDS + 1):
            if time.monotonic() - start > self.TIMEOUT_SECONDS:
                self.deadlock_detected = True
                return self._priority_tiebreak(current_proposals)

            debate_round = DebateRound(round_num)
            for agent, proposal in current_proposals.items():
                debate_round.add_proposal(agent, proposal)

            conflicts = debate_round.detect_conflicts()
            self.rounds.append(debate_round)

            if not conflicts:
                self.resolution_method = "convergence"
                return self._select_converged(current_proposals)

            logger.info(
                "debate_round_conflict",
                round=round_num,
                conflicts=len(conflicts),
                agents=[c[0] for c in conflicts],
            )

            if self._proposal_modifier is not None:
                current_proposals = self._proposal_modifier(current_proposals, round_num)

        self.deadlock_detected = True
        self.resolution_method = "priority_tiebreak"
        return self._priority_tiebreak(current_proposals)

    def _priority_tiebreak(self, proposals: dict[str, dict]) -> dict:
        priority_map = {p.name.lower(): p.value for p in AgentPriority}
        ranked = sorted(
            proposals.items(),
            key=lambda x: priority_map.get(x[0], 0),
            reverse=True,
        )
        winner_name, winner_proposal = ranked[0]
        logger.warning(
            "deadlock_resolved_via_priority",
            winner=winner_name,
            priority=priority_map.get(winner_name, 0),
        )
        return {
            "winner": winner_name,
            "proposal": winner_proposal,
            "resolution": "priority_tiebreak",
            "rounds_exhausted": len(self.rounds),
        }

    def _select_converged(self, proposals: dict[str, dict]) -> dict:
        first_agent = next(iter(proposals))
        return {
            "winner": first_agent,
            "proposal": proposals[first_agent],
            "resolution": "convergence",
            "rounds_exhausted": len(self.rounds),
        }


class TestAgentDeadlock:
    """Chaos logic validation: Circular proposal dependency causes deadlock.
    Timeout after 3 rounds breaks tie via agent priority. Recovery SLA: <5s."""

    @staticmethod
    def _create_circular_conflict() -> dict[str, dict]:
        """Create proposals where agents mutually conflict."""
        return {
            "demand_prophet": {
                "preferred_action": "increase_inventory",
                "utility_score": 0.85,
                "justification": "Demand surge predicted",
            },
            "routing_navigator": {
                "preferred_action": "reduce_routes",
                "utility_score": 0.82,
                "justification": "Traffic congestion detected",
            },
            "pricing_oracle": {
                "preferred_action": "increase_price",
                "utility_score": 0.80,
                "justification": "Low inventory detected",
            },
        }

    def test_deadlock_detected_within_max_rounds(self, chaos_clock) -> None:
        """Circular dependency is detected within 3 rounds."""
        detector = DeadlockDetector()
        proposals = self._create_circular_conflict()

        chaos_clock.start()
        with structlog.testing.capture_logs() as captured:
            result = detector.run_debate(proposals)

        assert detector.deadlock_detected is True
        assert len(detector.rounds) == 3
        chaos_clock.assert_within_sla(5.0, "Deadlock detection and resolution")
        assert any(e.get("event") == "deadlock_resolved_via_priority" for e in captured)

    def test_tiebreak_uses_priority(self, chaos_clock) -> None:
        """Tie-breaking selects highest-priority agent."""
        detector = DeadlockDetector()
        proposals = self._create_circular_conflict()

        chaos_clock.start()
        result = detector.run_debate(proposals)

        assert result["resolution"] == "priority_tiebreak"
        assert result["winner"] == "demand_prophet"
        chaos_clock.assert_within_sla(5.0, "Priority tiebreak resolution")

    def test_convergence_bypasses_tiebreak(self) -> None:
        """Non-conflicting proposals converge without tiebreak."""
        detector = DeadlockDetector()
        proposals = {
            "demand_prophet": {
                "preferred_action": "increase_inventory",
                "utility_score": 0.9,
            },
            "inventory_sentinel": {
                "preferred_action": "increase_inventory",
                "utility_score": 0.85,
            },
        }

        result = detector.run_debate(proposals)

        assert detector.deadlock_detected is False
        assert result["resolution"] == "convergence"

    def test_rounds_exhausted_count(self) -> None:
        """All 3 rounds are exhausted before tiebreak."""
        detector = DeadlockDetector()
        proposals = self._create_circular_conflict()

        result = detector.run_debate(proposals)

        assert result["rounds_exhausted"] == 3

    def test_proposal_modifier_can_achieve_convergence(self) -> None:
        """If agents adjust proposals mid-debate, convergence is possible."""

        def converge_after_round_2(
            proposals: dict[str, dict], round_num: int
        ) -> dict[str, dict]:
            if round_num >= 2:
                for agent in proposals:
                    proposals[agent]["preferred_action"] = "increase_inventory"
            return proposals

        detector = DeadlockDetector(proposal_modifier=converge_after_round_2)
        proposals = self._create_circular_conflict()

        result = detector.run_debate(proposals)

        assert detector.deadlock_detected is False
        assert result["resolution"] == "convergence"
        assert result["rounds_exhausted"] <= 3

    def test_two_agent_deadlock_resolved_by_priority(self) -> None:
        """Even a two-agent conflict resolves via priority."""
        detector = DeadlockDetector()
        proposals = {
            "pricing_oracle": {
                "preferred_action": "raise_price",
                "utility_score": 0.9,
            },
            "sustainability": {
                "preferred_action": "hold_price",
                "utility_score": 0.88,
            },
        }

        result = detector.run_debate(proposals)

        assert result["winner"] == "pricing_oracle"
        assert result["resolution"] == "priority_tiebreak"
