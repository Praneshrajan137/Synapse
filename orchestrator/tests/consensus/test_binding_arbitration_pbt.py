"""Property-based tests for binding Pareto-knee arbitration.

These properties exercise the pure binding selector ``select_binding_action``
(``orchestrator/consensus/pareto.py``) and the binding audit trace produced by
``ConsensusProtocol._build_decision`` (``orchestrator/consensus/protocol.py``).

Properties implemented here (numbers match the design document):

  * Property 1 — Binding selection maximizes the knee-weighted score
    (Validates: Requirements 1.1, 1.3)
  * Property 2 — Binding tie-break is deterministic
    (Validates: Requirements 1.4, 2.5)
  * Property 3 — Unmapped proposals are excluded without a fabricated score
    (Validates: Requirements 1.5)
  * Property 4 — Binding selection is deterministic and byte-stable
    (Validates: Requirements 2.1, 2.3, 10.6)
  * Property 5 — The binding decision's audit trace is complete
    (Validates: Requirements 2.2)

The example budget is inherited from the active Hypothesis profile (see the
root ``conftest.py``): ``dev`` (10), ``default``/``ci`` (500), ``nightly``
(5_000). Select one with ``HYPOTHESIS_PROFILE=dev`` or
``--hypothesis-profile=nightly``.
"""

from __future__ import annotations

import json
import math
from typing import TYPE_CHECKING, Any
from uuid import uuid4

import pytest

try:
    from hypothesis import given, settings
    from hypothesis import strategies as st
except ImportError:  # hypothesis is optional in some environments
    pytest.skip("hypothesis not installed", allow_module_level=True)

from synapse_common.models import AgentName, AgentProposal, DecisionTier

from orchestrator.consensus.pareto import (
    _AGENT_TO_OBJECTIVE,
    OBJECTIVES,
    BindingSelection,
    select_binding_action,
)
from orchestrator.consensus.protocol import ConsensusProtocol

if TYPE_CHECKING:
    from hypothesis.strategies import DrawFn, SearchStrategy

# Every ``AgentName`` value has an objective-map entry, so the eight enum
# members are exactly the "mapped" agents the selector can score.
MAPPED_AGENTS: list[AgentName] = list(AgentName)

# A neutral baseline matching ``_build_utility_matrix`` / ``select_binding_action``.
NEUTRAL_BASELINE = 0.5
TOLERANCE = 1e-9

# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------
_util_st = st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)
_weight_st = st.floats(min_value=0.1, max_value=2.0, allow_nan=False, allow_infinity=False)

_json_scalar_st = st.one_of(
    st.integers(min_value=-1000, max_value=1000),
    st.floats(allow_nan=False, allow_infinity=False, width=32),
    st.text(max_size=10),
    st.booleans(),
)
_payload_st = st.dictionaries(st.text(min_size=1, max_size=8), _json_scalar_st, max_size=4)


def _make_proposal(
    agent: AgentName, score: float, payload: dict[str, Any] | None = None
) -> AgentProposal:
    """Build a real, schema-valid proposal for a mapped agent."""
    return AgentProposal(
        agent_name=agent,
        decision_id=uuid4(),
        utility_score=score,
        confidence=score,
        justification_trace=[f"{agent.value} proposal"],
        payload=payload if payload is not None else {"action": f"{agent.value}_action"},
        tier=DecisionTier.TIER_2,
    )


def _make_unmapped(name: str, score: float) -> AgentProposal:
    """Build a proposal whose ``agent_name`` is not in ``_AGENT_TO_OBJECTIVE``.

    Uses ``model_construct`` to bypass the ``AgentName`` enum constraint so we
    can exercise the selector's defensive exclusion path (R1.5). The selector
    only reads ``agent_name`` and ``utility_score``, both of which are set here.
    """
    return AgentProposal.model_construct(
        agent_name=name,
        decision_id=uuid4(),
        utility_score=score,
        confidence=score,
        justification_trace=[],
        payload={},
        tier=DecisionTier.TIER_2,
    )


@st.composite
def _knee_weights(draw: DrawFn) -> dict[str, float]:
    """A positive weight for every objective in ``OBJECTIVES``."""
    return {obj: draw(_weight_st) for obj in OBJECTIVES}


@st.composite
def _proposal_sets(draw: DrawFn, *, min_size: int = 1) -> list[AgentProposal]:
    """A set of proposals from distinct mapped agents with random payloads."""
    agents = draw(
        st.lists(st.sampled_from(MAPPED_AGENTS), min_size=min_size, max_size=8, unique=True)
    )
    return [_make_proposal(a, draw(_util_st), draw(_payload_st)) for a in agents]


@st.composite
def _tied_sets(draw: DrawFn) -> tuple[list[AgentProposal], dict[str, float]]:
    """Distinct mapped agents sharing one utility and one uniform weight.

    Identical utility + uniform weights ⇒ exactly-equal weighted scores, forcing
    the deterministic tie-break to decide the winner.
    """
    agents = draw(
        st.lists(st.sampled_from(MAPPED_AGENTS), min_size=2, max_size=8, unique=True)
    )
    util = draw(_util_st)
    weight = draw(_weight_st)
    proposals = [_make_proposal(a, util) for a in agents]
    weights = {obj: weight for obj in OBJECTIVES}
    return proposals, weights


_unmapped_name_st: SearchStrategy[str] = st.sampled_from(
    ["ghost_agent", "unknown_agent", "phantom", "mystery_meat", "rogue", "nobody"]
).filter(lambda name: name not in _AGENT_TO_OBJECTIVE)


@st.composite
def _mixed_sets(
    draw: DrawFn,
) -> tuple[list[AgentProposal], set[str], set[str]]:
    """A mix of mapped proposals and at least one unmapped proposal."""
    mapped_agents = draw(
        st.lists(st.sampled_from(MAPPED_AGENTS), max_size=8, unique=True)
    )
    unmapped_names = draw(
        st.lists(_unmapped_name_st, min_size=1, max_size=4, unique=True)
    )
    proposals: list[AgentProposal] = [_make_proposal(a, draw(_util_st)) for a in mapped_agents]
    proposals.extend(_make_unmapped(n, draw(_util_st)) for n in unmapped_names)
    return proposals, {str(a) for a in mapped_agents}, set(unmapped_names)


def _expected_score(proposal: AgentProposal, weights: dict[str, float]) -> float:
    """Independent re-derivation of the knee-weighted score (R1.1, R1.3)."""
    objective = _AGENT_TO_OBJECTIVE[str(proposal.agent_name)]
    own = weights.get(objective, 0.0)
    others = sum(weights.get(obj, 0.0) for obj in OBJECTIVES if obj != objective)
    return own * float(proposal.utility_score) + NEUTRAL_BASELINE * others


def _bare_protocol() -> ConsensusProtocol:
    """A ConsensusProtocol with only the attributes ``_build_decision`` reads.

    ``_build_decision`` is effectively pure over ``(proposals, tier, weights,
    selection)``; it only touches ``self._decision_id`` and
    ``self._context_messages``. Building those directly avoids the heavy
    dependency graph of ``__init__`` while exercising the real method.
    """
    proto = object.__new__(ConsensusProtocol)
    proto._decision_id = None
    proto._context_messages = []
    return proto


# ---------------------------------------------------------------------------
# Property 1: Binding selection maximizes the knee-weighted score
# Validates: Requirements 1.1, 1.3
# ---------------------------------------------------------------------------
@given(proposals=_proposal_sets(), weights=_knee_weights())
@settings()
def test_property1_selection_maximizes_weighted_score(
    proposals: list[AgentProposal], weights: dict[str, float]
) -> None:
    """The selected proposal has the highest knee-weighted score, where each
    proposal's own objective contributes its ``utility_score`` and every other
    objective contributes the neutral baseline (0.5)."""
    selection = select_binding_action(proposals, weights)

    # All proposals here are mapped, so one must be selected.
    assert selection.selected_index is not None
    assert selection.selected_agent is not None

    # The function's per-candidate scores match the independent formula (R1.3).
    for proposal in proposals:
        agent = str(proposal.agent_name)
        assert selection.weighted_scores[agent] == pytest.approx(
            _expected_score(proposal, weights), abs=1e-9
        )

    # The selected candidate attains the maximum weighted score (R1.1).
    best_score = max(selection.weighted_scores.values())
    assert selection.weighted_scores[selection.selected_agent] == pytest.approx(
        best_score, abs=1e-9
    )

    # And the selected index points at the selected agent's proposal.
    assert str(proposals[selection.selected_index].agent_name) == selection.selected_agent


# ---------------------------------------------------------------------------
# Property 2: Binding tie-break is deterministic
# Validates: Requirements 1.4, 2.5
# ---------------------------------------------------------------------------
@given(case=_tied_sets())
@settings()
def test_property2_tie_break_is_deterministic(
    case: tuple[list[AgentProposal], dict[str, float]],
) -> None:
    """When top scores are equal within 1e-9, the proposal whose mapped
    objective appears earliest in ``OBJECTIVES`` wins, and the outcome is
    recorded and reproducible."""
    proposals, weights = case
    selection = select_binding_action(proposals, weights)

    # By construction every eligible candidate has an identical score → a tie.
    scores = list(selection.weighted_scores.values())
    assert max(scores) - min(scores) <= TOLERANCE
    assert selection.tie_break_applied is True

    # The winner is the agent whose objective is earliest in OBJECTIVES.
    expected_agent = min(
        (str(p.agent_name) for p in proposals),
        key=lambda name: OBJECTIVES.index(_AGENT_TO_OBJECTIVE[name]),
    )
    assert selection.selected_agent == expected_agent

    # The tie-break was resolved by objective order, and recorded (R2.5).
    expected_obj = _AGENT_TO_OBJECTIVE[expected_agent]
    assert selection.tie_break_reason == f"objective_order:{expected_obj}"

    # Reproducible: a second evaluation yields the identical outcome.
    assert select_binding_action(proposals, weights) == selection


# ---------------------------------------------------------------------------
# Property 3: Unmapped proposals are excluded without a fabricated score
# Validates: Requirements 1.5
# ---------------------------------------------------------------------------
@given(case=_mixed_sets())
@settings()
def test_property3_unmapped_proposals_excluded(
    case: tuple[list[AgentProposal], set[str], set[str]],
) -> None:
    """Every proposal whose agent has no objective-map entry is excluded, never
    receives a score, and is never selected."""
    proposals, mapped_names, unmapped_names = case
    selection = select_binding_action(proposals, {obj: 1.0 for obj in OBJECTIVES})

    # Each unmapped agent is recorded as excluded (no fabricated score, I-7).
    for name in unmapped_names:
        assert name in selection.excluded_agents
        assert name not in selection.weighted_scores

    # Only mapped agents are ever scored or selected.
    assert set(selection.weighted_scores).issubset(mapped_names)
    if selection.selected_agent is not None:
        assert selection.selected_agent in mapped_names
        assert selection.selected_agent not in unmapped_names
    else:
        # No eligible candidate ⇒ no mapped proposals were supplied.
        assert mapped_names == set()


# ---------------------------------------------------------------------------
# Property 4: Binding selection is deterministic and byte-stable
# Validates: Requirements 2.1, 2.3, 10.6
# ---------------------------------------------------------------------------
@given(proposals=_proposal_sets(), weights=_knee_weights())
@settings()
def test_property4_selection_is_deterministic_and_byte_stable(
    proposals: list[AgentProposal], weights: dict[str, float]
) -> None:
    """Repeated evaluation yields the identical selection, and the selected
    payload serialized via ``to_deterministic_json`` is byte-identical."""
    results: list[BindingSelection] = [
        select_binding_action(proposals, weights) for _ in range(5)
    ]

    first = results[0]
    for other in results[1:]:
        assert other == first
        assert other.selected_index == first.selected_index
        assert other.selected_agent == first.selected_agent

    # Byte-identical serialized action across all repeated evaluations (R2.3).
    assert first.selected_index is not None
    serialized = {
        proposals[r.selected_index].to_deterministic_json()
        for r in results
        if r.selected_index is not None
    }
    assert len(serialized) == 1


# ---------------------------------------------------------------------------
# Property 5: The binding decision's audit trace is complete
# Validates: Requirements 2.2
# ---------------------------------------------------------------------------
@given(proposals=_proposal_sets(), weights=_knee_weights())
@settings()
def test_property5_audit_trace_is_complete(
    proposals: list[AgentProposal], weights: dict[str, float]
) -> None:
    """A full-path decision's ``audit_trace`` records the knee-weight vector, a
    weighted score for every evaluated candidate, and the selected identity."""
    selection = select_binding_action(proposals, weights)
    protocol = _bare_protocol()
    decision = protocol._build_decision(
        proposals=proposals,
        tier=DecisionTier.TIER_4,
        phase_reached=4,
        pareto_weights=weights,
        selection=selection,
    )
    trace = decision.audit_trace

    # (a) The knee-weight vector is present and carries every objective.
    knee_line = _single_trace_line(trace, "knee_weights=")
    knee_payload = json.loads(knee_line[len("knee_weights=") :])
    assert set(knee_payload) == set(OBJECTIVES)
    for obj in OBJECTIVES:
        assert knee_payload[obj] == pytest.approx(weights[obj], abs=1e-6)

    # (b) A weighted score for every evaluated candidate.
    scores_line = _single_trace_line(trace, "weighted_scores=")
    scores_payload = json.loads(scores_line[len("weighted_scores=") :])
    assert set(scores_payload) == set(selection.weighted_scores)
    for agent, score in selection.weighted_scores.items():
        assert scores_payload[agent] == pytest.approx(score, abs=1e-6)

    # (c) The identity of the selected proposal.
    assert f"binding_selected={selection.selected_agent}" in trace


def _single_trace_line(trace: list[str], prefix: str) -> str:
    """Return the one audit-trace line starting with ``prefix`` (asserts exactly one)."""
    matches = [line for line in trace if line.startswith(prefix)]
    assert len(matches) == 1, f"expected exactly one {prefix!r} line, got {len(matches)}"
    return matches[0]


# A small import-time guard so an accidental NaN never silently passes the
# float comparisons above during local experimentation.
assert not math.isnan(NEUTRAL_BASELINE)
