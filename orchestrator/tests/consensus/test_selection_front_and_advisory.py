"""ADR-054 D3 / R13.5, R13.8: selection and debate records are consequential.

Two findings from `purpose-achievement-audit` Requirement 13 are closed here:

* **R13.5** - `pareto_front` was the NSGA-II front over *weight vectors*, so the
  decision recorded a set the ratified action was never selected from (and could not
  be a member of). `_build_decision` now records the set `select_binding_action`
  actually ran over and asserts membership, raising `SelectionIntegrityError`
  otherwise.
* **R13.8** - a debate round was counted whether or not it moved anything, so
  `debate_rounds=3` read as three consequential rounds. A round that changed no
  proposal value and no selection is now stamped `advisory: true`.

These are example-class unit tests. The universal statement is Property 26
(task 8.8), which is `@pytest.mark.slow` and runs in CI.
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest
from synapse_common.models import AgentName, AgentProposal, DecisionTier

from orchestrator.config import OrchestratorConfig
from orchestrator.consensus.pareto import (
    FRONT_INDEX_KEY,
    OBJECTIVES,
    SelectionFront,
    build_selection_front,
    select_binding_action,
)
from orchestrator.consensus.protocol import (
    ConsensusProtocol,
    DebateRoundChange,
    SelectionIntegrityError,
    changed_proposal_values,
)
from orchestrator.state_machine import OrchestratorStateMachine

_WEIGHTS: dict[str, float] = {obj: 1.0 for obj in OBJECTIVES}


def _protocol() -> ConsensusProtocol:
    """A protocol carrying only what these methods read (no heavy dependencies)."""
    proto = object.__new__(ConsensusProtocol)
    proto._config = OrchestratorConfig(
        postgresql_url="sqlite+aiosqlite:///",
        pinecone_api_key=None,
    )
    proto._decision_id = None
    proto._context_messages = []
    proto._tool_call_count = 0
    proto._debate_rounds_log = []
    # Real: `_append_context` reaches the objective recitation on every
    # `recitation_interval`-th append, which reads the state machine.
    proto._fsm = OrchestratorStateMachine()
    return proto


def _proposal(
    agent: AgentName,
    score: float,
    payload: dict[str, Any] | None = None,
) -> AgentProposal:
    return AgentProposal(
        agent_name=agent,
        decision_id=uuid4(),
        utility_score=score,
        confidence=score,
        justification_trace=[f"{agent.value} proposal"],
        payload=payload if payload is not None else {"action": f"{agent.value}_action"},
        tier=DecisionTier.TIER_4,
    )


def _proposals() -> list[AgentProposal]:
    return [
        _proposal(AgentName.DEMAND_PROPHET, 0.4),
        _proposal(AgentName.INVENTORY_SENTINEL, 0.9),
        _proposal(AgentName.PRICING_ORACLE, 0.6),
    ]


class TestRecordedFrontIsTheSetSelectionRanOver:
    """R13.5."""

    def test_front_has_one_member_per_evaluated_candidate(self) -> None:
        proposals = _proposals()
        selection = select_binding_action(proposals, _WEIGHTS)
        decision = _protocol()._build_decision(
            proposals=proposals,
            tier=DecisionTier.TIER_4,
            phase_reached=4,
            pareto_weights=_WEIGHTS,
            selection=selection,
        )

        front = decision.pareto_front
        assert front is not None
        assert len(front) == len(proposals)
        # Each row identifies the candidate it projects, so membership is decidable
        # from the recorded row alone.
        assert [int(row[FRONT_INDEX_KEY]) for row in front] == [0, 1, 2]

    def test_ratified_action_is_a_member_of_the_recorded_front(self) -> None:
        proposals = _proposals()
        selection = select_binding_action(proposals, _WEIGHTS)
        decision = _protocol()._build_decision(
            proposals=proposals,
            tier=DecisionTier.TIER_4,
            phase_reached=4,
            pareto_weights=_WEIGHTS,
            selection=selection,
        )

        front = decision.pareto_front
        assert front is not None
        member_indexes = [int(row[FRONT_INDEX_KEY]) for row in front]
        assert selection.selected_index in member_indexes
        # The ratified payload is the payload of the member the front names.
        assert decision.selected_action == proposals[selection.selected_index or 0].payload
        assert f"selection_front_size={len(front)}" in decision.audit_trace
        assert any(t.startswith("selection_front_member=") for t in decision.audit_trace)

    def test_fast_path_records_no_front(self) -> None:
        """Tier 1/2 runs no Pareto arbitration, so it claims no front (R1.6)."""
        proposals = _proposals()
        decision = _protocol()._build_decision(
            proposals=proposals,
            tier=DecisionTier.TIER_1,
            phase_reached=4,
            pareto_weights=_WEIGHTS,
            fast_best=proposals[1],
        )
        assert decision.pareto_front is None

    def test_front_that_omits_the_ratified_action_is_rejected(self) -> None:
        """A front drifted from selection is an audit record that misdescribes itself."""
        proposals = _proposals()
        selection = select_binding_action(proposals, _WEIGHTS)
        drifted = SelectionFront(
            members=build_selection_front(proposals, selection).members,
            ratified_member_index=None,
            excluded_agents=(),
        )
        with pytest.raises(SelectionIntegrityError, match="not a member"):
            ConsensusProtocol._assert_ratified_front_member(drifted, selection, ratified=True)

    def test_front_naming_the_wrong_candidate_is_rejected(self) -> None:
        proposals = _proposals()
        selection = select_binding_action(proposals, _WEIGHTS)
        honest = build_selection_front(proposals, selection)
        wrong_index = (honest.ratified_member_index or 0) + 1
        drifted = SelectionFront(
            members=honest.members,
            ratified_member_index=wrong_index % len(honest.members),
            excluded_agents=(),
        )
        if drifted.ratified_member_index == honest.ratified_member_index:
            pytest.skip("single-member front cannot express this drift")
        with pytest.raises(SelectionIntegrityError, match="candidate index"):
            ConsensusProtocol._assert_ratified_front_member(drifted, selection, ratified=True)


class TestDebateAdvisoryStamp:
    """R13.8."""

    def test_round_that_changed_nothing_is_advisory(self) -> None:
        proposals = _proposals()
        proto = _protocol()
        proto._debate_rounds_log = [
            DebateRoundChange(round_number=1, values_changed=False),
            DebateRoundChange(round_number=2, values_changed=False),
        ]
        selection = select_binding_action(proposals, _WEIGHTS)

        advisory = proto._record_debate_consequence(
            pre_debate=proposals,
            post_debate=proposals,
            weights=_WEIGHTS,
            selection=selection,
        )

        assert advisory == (1, 2)
        record = proto._context_messages[-1].content
        assert record["type"] == "debate_consequence"
        assert record["selection_changed"] is False
        assert all(r["advisory"] is True for r in record["rounds"])

    def test_round_that_changed_a_payload_is_not_advisory(self) -> None:
        before = _proposals()
        after = [
            before[0],
            before[1].model_copy(update={"payload": {"action": "revised"}}),
            before[2],
        ]
        proto = _protocol()
        proto._debate_rounds_log = [DebateRoundChange(round_number=1, values_changed=True)]

        advisory = proto._record_debate_consequence(
            pre_debate=before,
            post_debate=after,
            weights=_WEIGHTS,
            selection=select_binding_action(after, _WEIGHTS),
        )

        assert advisory == ()
        assert proto._context_messages[-1].content["rounds"][0]["advisory"] is False

    def test_round_that_changed_the_selection_is_not_advisory(self) -> None:
        """A round can move the selection without the round's own values changing
        in the last round; the debate's selection change still denies advisory."""
        before = _proposals()
        # Raise the pricing_oracle utility above the incumbent so the knee-weighted
        # selection moves.
        after = [before[0], before[1], before[2].model_copy(update={"utility_score": 1.0})]
        after[1] = after[1].model_copy(update={"utility_score": 0.1})
        proto = _protocol()
        proto._debate_rounds_log = [DebateRoundChange(round_number=1, values_changed=False)]

        advisory = proto._record_debate_consequence(
            pre_debate=before,
            post_debate=after,
            weights=_WEIGHTS,
            selection=select_binding_action(after, _WEIGHTS),
        )

        record = proto._context_messages[-1].content
        assert record["selection_changed"] is True
        assert advisory == ()

    def test_no_debate_records_nothing(self) -> None:
        proposals = _proposals()
        proto = _protocol()
        advisory = proto._record_debate_consequence(
            pre_debate=proposals,
            post_debate=proposals,
            weights=_WEIGHTS,
            selection=select_binding_action(proposals, _WEIGHTS),
        )
        assert advisory == ()
        assert proto._context_messages == []


class TestChangedProposalValues:
    """R13.8's decidable half: values, not the status an agent reported."""

    def test_identical_proposals_changed_nothing(self) -> None:
        proposals = _proposals()
        assert changed_proposal_values(proposals, list(proposals)) == ()

    def test_payload_change_is_named(self) -> None:
        before = _proposals()
        after = [before[0].model_copy(update={"payload": {"action": "other"}}), *before[1:]]
        assert changed_proposal_values(before, after) == ("demand_prophet",)

    def test_utility_change_is_named(self) -> None:
        before = _proposals()
        after = [*before[:2], before[2].model_copy(update={"utility_score": 0.61})]
        assert changed_proposal_values(before, after) == ("pricing_oracle",)


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
