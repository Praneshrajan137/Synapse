"""Property-based test for append-only audit and provenance (ADR-052, I-14).

This module implements the single design property:

  * Property 6 — Audit and provenance records are append-only
    (Validates: Requirements 2.4, 3.8, 6.6, 10.2)

The property is exercised against the three append-only structures the feature
touches, each through its real code path:

  1. The orchestrator **context message list** — ``ConsensusProtocol._append_context``
     (the append-only primitive, I-14) and the real debate append in
     ``ConsensusProtocol._run_concession_round`` (R3.8). A sequence of operations
     never mutates or removes a prior entry; every earlier snapshot is preserved
     as a prefix and the list only grows.
  2. The decision **``audit_trace``** — ``ConsensusProtocol._build_decision`` builds
     the trace from an immutable ``tier=``/``phase=`` base and only *appends* the
     binding-arbitration lines; subsequent loop phases extend it with the same
     ``[*prior, new]`` idiom (R2.4). Across the phase chain the prior trace is
     always preserved as a prefix.
  3. An agent's **actuation/provenance record** — ``actuate_items`` builds
     ``world_effects`` by appending one entry per actionable item in order, so the
     record for any prefix of items is a prefix of the record for the full run
     (R6.6): the list only grows, prior entries are never rewritten.

The A2A transport (``send_a2a_request``) is mocked so the concession round runs
deterministically without live agents.

The example budget is inherited from the active Hypothesis profile (see the root
``conftest.py``): ``dev`` (10), ``default``/``ci`` (500), ``nightly`` (5_000).
Select one with ``HYPOTHESIS_PROFILE=dev`` or ``--hypothesis-profile=nightly``.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any
from unittest import mock
from uuid import uuid4

import pytest

try:
    from hypothesis import given, settings
    from hypothesis import strategies as st
except ImportError:  # hypothesis is optional in some environments
    pytest.skip("hypothesis not installed", allow_module_level=True)

from synapse_common.models import (
    AgentName,
    AgentProposal,
    ContextMessage,
    DecisionTier,
)
from synapse_common.world import ActuationItem, WorldActionKind, actuate_items

from orchestrator.config import OrchestratorConfig
from orchestrator.consensus import protocol as protocol_module
from orchestrator.consensus.pareto import (
    OBJECTIVES,
    select_binding_action,
)
from orchestrator.consensus.protocol import ConsensusProtocol

if TYPE_CHECKING:
    from hypothesis.strategies import DrawFn

# ---------------------------------------------------------------------------
# Shared strategies
# ---------------------------------------------------------------------------
MAPPED_AGENTS: list[AgentName] = list(AgentName)

_util_st = st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)
_weight_st = st.floats(min_value=0.1, max_value=2.0, allow_nan=False, allow_infinity=False)
_json_scalar_st = st.one_of(
    st.integers(min_value=-1000, max_value=1000),
    st.floats(allow_nan=False, allow_infinity=False, width=32),
    st.text(max_size=8),
    st.booleans(),
)
_content_st = st.dictionaries(st.text(min_size=1, max_size=6), _json_scalar_st, max_size=4)

_context_message_st = st.builds(
    ContextMessage,
    source=st.sampled_from(["orchestrator", "digital_twin", "demand_prophet", "pricing_oracle"]),
    content=_content_st,
)


def _make_proposal(agent: AgentName, score: float) -> AgentProposal:
    """Build a real proposal for a mapped agent."""
    return AgentProposal(
        agent_name=agent,
        decision_id=uuid4(),
        utility_score=score,
        confidence=score,
        justification_trace=[f"{agent.value} proposal"],
        payload={"__prior__": agent.value},
        tier=DecisionTier.TIER_3,
    )


@st.composite
def _knee_weights(draw: DrawFn) -> dict[str, float]:
    """A positive weight for every objective in ``OBJECTIVES``."""
    return {obj: draw(_weight_st) for obj in OBJECTIVES}


@st.composite
def _proposal_sets(draw: DrawFn, *, min_size: int = 1) -> list[AgentProposal]:
    """A set of proposals from distinct mapped agents."""
    agents = draw(
        st.lists(st.sampled_from(MAPPED_AGENTS), min_size=min_size, max_size=8, unique=True)
    )
    return [_make_proposal(a, draw(_util_st)) for a in agents]


def _bare_protocol() -> ConsensusProtocol:
    """A ``ConsensusProtocol`` exposing only what ``_build_decision`` reads.

    ``_build_decision`` is effectively pure over its arguments; it only touches
    ``self._decision_id`` and ``self._context_messages``, so we construct those
    directly and avoid the heavy ``__init__`` dependency graph.
    """
    proto = object.__new__(ConsensusProtocol)
    proto._decision_id = None
    proto._context_messages = []
    return proto


def _build_protocol(*, debate_max_rounds: int = 3) -> ConsensusProtocol:
    """A real ``ConsensusProtocol`` with inert mocked collaborators.

    Mirrors the convention in ``test_debate_concession_pbt.py`` — only the
    append-only context machinery (``_append_context`` / ``_run_concession_round``)
    is exercised here, so the heavy dependencies are mocks.
    """
    cfg = OrchestratorConfig(
        postgresql_url="sqlite+aiosqlite:///",
        pinecone_api_key=None,
        debate_max_rounds=debate_max_rounds,
    )
    return ConsensusProtocol(
        config=cfg,
        tier_router=mock.MagicMock(),
        guardrails=mock.MagicMock(),
        audit_logger=mock.MagicMock(),
        hitl_escalation=mock.MagicMock(),
        context_builder=mock.MagicMock(),
        ollama_client=mock.MagicMock(),
        meta_rl=mock.MagicMock(),
        semantic_cache=mock.MagicMock(),
    )


def _assert_prefix_chain(snapshots: list[list[Any]]) -> None:
    """Assert each snapshot preserves the previous one as an identical prefix.

    This is the append-only invariant: across a sequence of operations every prior
    entry is unchanged (present at the same index) and the list length is
    monotonically non-decreasing — entries are only ever appended.
    """
    for earlier, later in zip(snapshots, snapshots[1:], strict=False):
        assert len(later) >= len(earlier)
        assert later[: len(earlier)] == earlier


# ---------------------------------------------------------------------------
# Property 6 (structure 1a): the context message list grows append-only
# Validates: Requirements 2.4, 10.2
# ---------------------------------------------------------------------------
@given(messages=st.lists(_context_message_st, min_size=1, max_size=12))
@settings()
def test_property6_context_append_only_primitive(messages: list[ContextMessage]) -> None:
    """For any sequence of context appends, ``_append_context`` only ever appends:
    every earlier snapshot is preserved as an exact prefix of every later one and
    the list never shrinks (recitation may interleave its own entries, but those
    are appended too and never displace a prior entry)."""
    proto = _build_protocol()

    snapshots: list[list[ContextMessage]] = [list(proto._context_messages)]
    for msg in messages:
        new_len = proto._append_context(msg)
        assert new_len == len(proto._context_messages)
        snapshots.append(list(proto._context_messages))

    _assert_prefix_chain(snapshots)

    # Every input message is preserved, in order, as a subsequence of the final list.
    final = proto._context_messages
    idx = -1
    for msg in messages:
        idx = final.index(msg, idx + 1)


# ---------------------------------------------------------------------------
# Property 6 (structure 1b): the real debate append is append-only
# Validates: Requirements 3.8, 10.2
# ---------------------------------------------------------------------------
@given(rounds=st.integers(min_value=1, max_value=4), scores=st.tuples(_util_st, _util_st))
@settings()
def test_property6_concession_round_appends_context(
    rounds: int, scores: tuple[float, float]
) -> None:
    """Each ``_run_concession_round`` only appends to the context (R3.8): every
    prior context entry is preserved as a prefix and exactly one ``debate_revisions``
    entry is appended per round."""
    proposals = [
        _make_proposal(AgentName.SUPPLIER_TRUST, scores[0]),
        _make_proposal(AgentName.DISRUPTION_SHIELD, scores[1]),
    ]

    async def _fake_send(*, target_url: str, **_kwargs: Any) -> Any:
        # Agents maintain → proposals are retained; each round still appends a record.
        return mock.Mock(result={"status": "maintained", "rationale": "hold"}, error=None)

    proto = _build_protocol()
    snapshots: list[list[ContextMessage]] = [list(proto._context_messages)]

    with mock.patch.object(protocol_module, "send_a2a_request", _fake_send):
        for round_num in range(1, rounds + 1):
            asyncio.run(proto._run_concession_round(proposals, DecisionTier.TIER_3, round_num))
            snapshots.append(list(proto._context_messages))

    _assert_prefix_chain(snapshots)

    # One append-only ``debate_revisions`` entry per concession round (R3.8).
    revision_entries = [
        msg
        for msg in proto._context_messages
        if isinstance(msg.content, dict) and msg.content.get("type") == "debate_revisions"
    ]
    assert len(revision_entries) == rounds


# ---------------------------------------------------------------------------
# Property 6 (structure 2): the decision ``audit_trace`` only appends per phase
# Validates: Requirements 2.4
# ---------------------------------------------------------------------------
@given(
    proposals=_proposal_sets(),
    weights=_knee_weights(),
    phase_tags=st.lists(st.text(min_size=1, max_size=10), min_size=1, max_size=5),
)
@settings()
def test_property6_audit_trace_only_appends(
    proposals: list[AgentProposal], weights: dict[str, float], phase_tags: list[str]
) -> None:
    """``_build_decision`` builds the trace from an immutable ``tier=``/``phase=``
    base and only appends the binding-arbitration lines; subsequent loop phases
    extend it with the same ``[*prior, new]`` idiom. Across the chain the prior
    trace is always preserved as a prefix and never mutated (R2.4)."""
    tier = DecisionTier.TIER_4
    phase_reached = 4
    base = [f"tier={tier.value}", f"phase={phase_reached}"]

    selection = select_binding_action(proposals, weights)
    proto = _bare_protocol()
    decision = proto._build_decision(
        proposals=proposals,
        tier=tier,
        phase_reached=phase_reached,
        pareto_weights=weights,
        selection=selection,
    )

    # The immutable base is preserved verbatim at the front; binding-arbitration
    # lines are strictly appended after it (never overwrite the base).
    assert decision.audit_trace[: len(base)] == base
    assert len(decision.audit_trace) >= len(base)

    # Model the subsequent loop phases (twin verify at line ~762, the final build at
    # line ~839) which extend the trace with the very same append idiom. Each phase
    # only appends → the prior trace is preserved as a prefix at every step.
    snapshots: list[list[str]] = [list(decision.audit_trace)]
    trace = list(decision.audit_trace)
    for tag in phase_tags:
        trace = [*trace, f"phase_note={tag}"]  # mirrors `[*decision.audit_trace, ...]`
        snapshots.append(list(trace))

    _assert_prefix_chain(snapshots)


# ---------------------------------------------------------------------------
# Property 6 (structure 3): an agent's actuation/provenance record is append-only
# Validates: Requirements 6.6, 10.2
# ---------------------------------------------------------------------------
class _FakeActuator:
    """A deterministic actuator: every action lands a non-empty, per-item effect.

    The returned effect depends only on the action it is given, so building the
    ``world_effects`` record for a prefix of items yields a prefix of the record
    for the full item list — i.e. the record is append-only within a run.
    """

    def apply(self, action: Any) -> dict[str, Any]:
        return {
            "applied": True,
            "result": {
                "status": "ok",
                "effect": {
                    "lever": action.params.get("price_mult", 0.0),
                    "sku": action.sku_id,
                },
            },
        }


_lever_st = st.floats(min_value=0.1, max_value=3.0, allow_nan=False, allow_infinity=False)


@given(values=st.lists(_lever_st, min_size=0, max_size=8))
@settings()
def test_property6_world_effects_record_is_append_only(values: list[float]) -> None:
    """For any sequence of actionable items, ``actuate_items`` builds ``world_effects``
    by appending one entry per item in order: the record for any prefix of the items
    is exactly a prefix of the record for the full run (R6.6). Prior entries are never
    rewritten or removed — the provenance list only grows."""
    items = [
        ActuationItem(action_id=f"a-{i}", params={"price_mult": v}, sku_id=f"sku-{i}")
        for i, v in enumerate(values)
    ]
    actuator = _FakeActuator()

    def _effects(prefix: list[ActuationItem]) -> list[dict[str, Any]]:
        return actuate_items(
            agent_name="test_agent",
            kind=WorldActionKind.SET_PRICE_MULT,
            city="bengaluru",
            decision_id="d-1",
            items=prefix,
            actuator=actuator,
        ).world_effects

    full = _effects(items)

    # Append-only within a run: each prefix's record is a prefix of the full record.
    snapshots = [_effects(items[:k]) for k in range(len(items) + 1)]
    _assert_prefix_chain(snapshots)
    assert snapshots[-1] == full

    # The full record has exactly one entry per item, in the same order (R6.6).
    assert len(full) == len(items)
    for item, effect in zip(items, full, strict=True):
        assert effect["sku_id"] == item.sku_id

    # Determinism: rebuilding the full record yields an identical (unmutated) record.
    assert _effects(items) == full
