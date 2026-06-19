"""Property-based tests for debate revision via rule-based concession (ADR-052, R3).

These properties exercise the orchestrator-side debate coordinator
(``ConsensusProtocol._phase_debate`` / ``_run_concession_round`` /
``_apply_debate_result`` in ``orchestrator/consensus/protocol.py``) and the shared
agent-side ``build_debate_response`` handler
(``packages/synapse_common/debate/response.py``).

Properties implemented here (numbers match the design document):

  * Property 7 — Debate replaces a proposal only with a schema-valid revision
    (Validates: Requirements 3.1, 3.10)
  * Property 9 — Debate terminates within the round bound
    (Validates: Requirements 3.5)
  * Property 10 — Every emitted or revised payload is schema-valid
    (Validates: Requirements 3.6, 10.1)

The A2A transport (``send_a2a_request``) is mocked so the concession rounds run
deterministically without live agents; for the round-bound property the mocked
agents never concede so the debate is driven to the ``debate_max_rounds`` cap.

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

from synapse_common.debate.concession import concede_toward, consensus_position
from synapse_common.debate.response import build_debate_response
from synapse_common.models import AgentName, AgentProposal, DecisionTier
from synapse_common.schemas import (
    SchemaValidationError,
    validate_agent_payload,
)

from orchestrator.config import OrchestratorConfig
from orchestrator.consensus import protocol as protocol_module
from orchestrator.consensus.models import TierClassification
from orchestrator.consensus.protocol import AGENT_ENDPOINTS, ConsensusProtocol

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

    from hypothesis.strategies import DrawFn

# ---------------------------------------------------------------------------
# Agents whose ``proto/domain/`` schema validates the WHOLE payload object
# (``list_key=None`` in ``AGENT_PAYLOAD_SCHEMAS``). Using these lets us build
# unambiguously valid / invalid revised payloads: an arbitrary garbage dict
# reliably FAILS validation (missing required fields + ``additionalProperties:
# false``), which is not true for the list-keyed agents whose validation is a
# no-op when the list key is absent.
# ---------------------------------------------------------------------------
WHOLE_SCHEMA_AGENTS: list[AgentName] = [
    AgentName.SUPPLIER_TRUST,
    AgentName.DISRUPTION_SHIELD,
    AgentName.SUSTAINABILITY_AGENT,
]

# Reverse map so a mocked ``send_a2a_request`` can recover the agent from the
# ``target_url`` the coordinator dials.
_URL_TO_AGENT: dict[str, str] = {url: name for name, url in AGENT_ENDPOINTS.items()}

_TIMESTAMP = "2025-01-01T00:00:00+00:00"

# A payload that fails every whole-object schema (no required fields present and
# ``additionalProperties: false`` rejects the stray key).
_INVALID_PAYLOAD: dict[str, Any] = {"__not_a_valid_field__": 1}


def _valid_supplier_score(tag: int) -> dict[str, Any]:
    return {
        "score_id": f"score-{tag}",
        "supplier_id": f"supplier-{tag}",
        "trust_score": 0.7,
        "lead_time_posterior": {"mean_days": 2.0, "std_days": 0.5},
        "delivery_reliability": 0.9,
        "timestamp": _TIMESTAMP,
        "confidence": 0.8,
    }


def _valid_disruption_alert(tag: int) -> dict[str, Any]:
    return {
        "alert_id": f"alert-{tag}",
        "alert_level": 3,
        "anomaly_scores": {
            "isolation_forest": 0.1,
            "lstm_autoencoder": 0.1,
            "gnn_structural": 0.1,
            "ensemble_weighted": 0.1,
        },
        "affected_nodes": [f"node-{tag}"],
        "playbook_id": f"playbook-{tag}",
        "reasoning_chain": "anomaly ensemble exceeded threshold",
        "timestamp": _TIMESTAMP,
        "confidence": 0.6,
    }


def _valid_carbon_report(tag: int) -> dict[str, Any]:
    return {
        "report_id": f"report-{tag}",
        "scope": "aggregate",
        "co2_kg": 1.0,
        "energy_kwh": 2.0,
        "timestamp": _TIMESTAMP,
    }


_VALID_FACTORY: dict[str, Callable[[int], dict[str, Any]]] = {
    AgentName.SUPPLIER_TRUST.value: _valid_supplier_score,
    AgentName.DISRUPTION_SHIELD.value: _valid_disruption_alert,
    AgentName.SUSTAINABILITY_AGENT.value: _valid_carbon_report,
}


def _valid_payload(agent: str, tag: int) -> dict[str, Any]:
    """A schema-valid payload for ``agent`` (one of the whole-schema agents)."""
    return _VALID_FACTORY[agent](tag)


def _make_proposal(
    agent: AgentName, score: float, payload: dict[str, Any], decision_id: Any
) -> AgentProposal:
    """Build a proposal for a mapped agent with an explicit payload marker."""
    return AgentProposal(
        agent_name=agent,
        decision_id=decision_id,
        utility_score=score,
        confidence=0.8,
        justification_trace=[f"{agent.value} proposal"],
        payload=payload,
        tier=DecisionTier.TIER_3,
    )


def _a2a(*, result: dict[str, Any] | None = None, error: dict[str, Any] | None = None) -> Any:
    """Mimic the ``A2AResponse`` shape consumed by ``_request_debate_response``."""
    return mock.Mock(result=result, error=error)


def _build_protocol(*, debate_max_rounds: int = 3) -> ConsensusProtocol:
    """A real ``ConsensusProtocol`` with mocked collaborators (matches the
    convention in ``test_debate_degradation.py``). Only ``_phase_debate`` /
    ``_run_concession_round`` are exercised here, so the heavy dependencies are
    inert mocks."""
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


def _classification(model: str | None = None) -> TierClassification:
    return TierClassification(
        tier=DecisionTier.TIER_3,
        confidence=0.9,
        reasons=["test"],
        model=model,
        latency_budget_ms=30_000,
    )


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------
_util_st = st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)
_tag_st = st.integers(min_value=0, max_value=1_000_000)

# The five mutually-exclusive outcomes a mocked ``debate_respond`` can return.
_OUTCOMES = ("maintained", "revised_valid", "revised_invalid", "revised_missing", "error")


@st.composite
def _debate_cases(draw: DrawFn) -> list[dict[str, Any]]:
    """A set of per-agent debate cases (distinct whole-schema agents, >= 2)."""
    agents = draw(
        st.lists(
            st.sampled_from(WHOLE_SCHEMA_AGENTS),
            min_size=2,
            max_size=len(WHOLE_SCHEMA_AGENTS),
            unique=True,
        )
    )
    cases: list[dict[str, Any]] = []
    for agent in agents:
        cases.append(
            {
                "agent": agent,
                "prior_score": draw(_util_st),
                "revised_score": draw(_util_st),
                "tag": draw(_tag_st),
                "outcome": draw(st.sampled_from(_OUTCOMES)),
            }
        )
    return cases


def _response_for(case: dict[str, Any]) -> Any:
    """Build the mocked A2A response for one agent's debate case."""
    agent = case["agent"].value
    outcome = case["outcome"]
    if outcome == "error":
        return _a2a(error={"code": -32000, "message": "debate boom"})
    if outcome == "maintained":
        return _a2a(result={"status": "maintained", "rationale": "within_band"})
    if outcome == "revised_missing":
        # ``"revised"`` status but no payload / utility_score → coordinator retains.
        return _a2a(result={"status": "revised"})
    if outcome == "revised_invalid":
        return _a2a(
            result={
                "status": "revised",
                "utility_score": case["revised_score"],
                "payload": dict(_INVALID_PAYLOAD),
            }
        )
    # revised_valid
    return _a2a(
        result={
            "status": "revised",
            "utility_score": case["revised_score"],
            "payload": _valid_payload(agent, case["tag"]),
        }
    )


# ---------------------------------------------------------------------------
# Property 7: Debate replaces a proposal only with a schema-valid revision
# Validates: Requirements 3.1, 3.10
# ---------------------------------------------------------------------------
@given(cases=_debate_cases())
@settings()
def test_debate_replaces_only_valid_revision(cases: list[dict[str, Any]]) -> None:
    """The coordinator uses a returned revision for the next round if and only if
    its status is ``"revised"`` AND its payload passes ``proto/domain/`` schema
    validation; otherwise it retains the agent's prior proposal."""
    decision_id = uuid4()
    # Each prior proposal carries a distinct, deliberately NON-schema-valid marker
    # payload so "retained" is unambiguously distinguishable from "replaced".
    prior_payloads: dict[str, dict[str, Any]] = {
        case["agent"].value: {"__prior__": case["agent"].value} for case in cases
    }
    proposals = [
        _make_proposal(
            case["agent"], case["prior_score"], prior_payloads[case["agent"].value], decision_id
        )
        for case in cases
    ]
    response_by_url = {AGENT_ENDPOINTS[case["agent"].value]: _response_for(case) for case in cases}

    async def _fake_send(*, target_url: str, **_kwargs: Any) -> Any:
        return response_by_url[target_url]

    proto = _build_protocol()
    with mock.patch.object(protocol_module, "send_a2a_request", _fake_send):
        revised = asyncio.run(proto._run_concession_round(proposals, DecisionTier.TIER_3, 1))

    by_agent = {str(p.agent_name): p for p in revised}
    for case in cases:
        agent = case["agent"].value
        result = by_agent[agent]
        if case["outcome"] == "revised_valid":
            # Replaced: the next-round proposal carries the revised payload + score.
            expected_payload = _valid_payload(agent, case["tag"])
            assert result.payload == expected_payload
            assert result.utility_score == pytest.approx(case["revised_score"], abs=1e-9)
            # The replacement payload is itself schema-valid (the IFF condition).
            validate_agent_payload(agent, result.payload)
        else:
            # Retained: prior payload + prior score are unchanged (R3.1/R3.10/I-7).
            assert result.payload == prior_payloads[agent]
            assert result.utility_score == pytest.approx(case["prior_score"], abs=1e-9)


# ---------------------------------------------------------------------------
# Property 9: Debate terminates within the round bound
# Validates: Requirements 3.5
# ---------------------------------------------------------------------------
@given(max_rounds=st.integers(min_value=1, max_value=6))
@settings()
def test_debate_round_bound(max_rounds: int) -> None:
    """For non-converging proposals and any ``debate_max_rounds`` >= 1, the number
    of debate rounds executed never exceeds ``debate_max_rounds`` (and reaches it
    exactly when convergence is never achieved)."""
    decision_id = uuid4()
    # Maximally divergent, non-converging proposals: variance(0.0, 1.0) = 0.25,
    # well above the 0.1 convergence threshold. Every agent maintains, so the
    # proposals never move and convergence is never reached → the cap is hit.
    proposals = [
        _make_proposal(AgentName.SUPPLIER_TRUST, 0.0, {"__prior__": "a"}, decision_id),
        _make_proposal(AgentName.DISRUPTION_SHIELD, 1.0, {"__prior__": "b"}, decision_id),
    ]

    async def _fake_send(*, target_url: str, **_kwargs: Any) -> Any:
        return _a2a(result={"status": "maintained", "rationale": "hold"})

    proto = _build_protocol(debate_max_rounds=max_rounds)
    # ``model=None`` skips the LLM-mediated analysis entirely; only rule-based
    # concession (which is LLM-independent) drives the rounds.
    with mock.patch.object(protocol_module, "send_a2a_request", _fake_send):
        result, rounds = asyncio.run(
            proto._phase_debate(proposals, DecisionTier.TIER_3, _classification(model=None))
        )

    # Hard upper bound (R3.5): rounds executed never exceeds the configured cap.
    assert rounds <= max_rounds
    # Non-converging ⇒ the cap is the stopping condition.
    assert rounds == max_rounds

    # The number of rounds actually executed (one ``debate_revisions`` context
    # entry is appended per concession round) matches the reported count and is
    # itself bounded by the cap.
    executed = sum(
        1
        for msg in proto._context_messages
        if isinstance(msg.content, dict) and msg.content.get("type") == "debate_revisions"
    )
    assert executed == rounds <= max_rounds
    # Maintained-only debate leaves the proposals unchanged.
    assert [p.utility_score for p in result] == [0.0, 1.0]


# ---------------------------------------------------------------------------
# Property 10: Every emitted or revised payload is schema-valid
# Validates: Requirements 3.6, 10.1
# ---------------------------------------------------------------------------
@st.composite
def _emit_cases(draw: DrawFn) -> dict[str, Any]:
    """A concession-forcing ``debate_respond`` case for one whole-schema agent.

    The current score and the round consensus are drawn far enough apart that the
    agent is OUTSIDE the convergence band (|current - consensus| > sqrt(0.1) ≈
    0.316), so the handler attempts a revision and schema validity becomes
    decisive. ``payload_valid`` selects whether the agent's current payload is a
    schema-valid object or garbage.
    """
    agent = draw(st.sampled_from(WHOLE_SCHEMA_AGENTS))
    current = draw(st.floats(min_value=0.0, max_value=0.1, allow_nan=False, allow_infinity=False))
    peer = draw(st.floats(min_value=0.8, max_value=1.0, allow_nan=False, allow_infinity=False))
    payload_valid = draw(st.booleans())
    tag = draw(_tag_st)
    return {
        "agent": agent,
        "current": current,
        "round_utilities": [peer, peer],
        "payload_valid": payload_valid,
        "tag": tag,
    }


@given(case=_emit_cases())
@settings()
def test_emitted_revised_payload_schema_valid(case: dict[str, Any]) -> None:
    """Whenever ``build_debate_response`` returns a ``"revised"`` reply, the emitted
    payload passes ``proto/domain/`` schema validation; a candidate payload that
    fails validation is rejected (maintained) and never propagated as a revision."""
    agent = case["agent"].value
    payload = (
        _valid_payload(agent, case["tag"]) if case["payload_valid"] else dict(_INVALID_PAYLOAD)
    )
    params: Mapping[str, Any] = {
        "round_number": 2,
        "round_utilities": case["round_utilities"],
        "current_utility_score": case["current"],
        "current_payload": payload,
    }

    response = build_debate_response(agent, params)

    # Sanity: the case is constructed to force a concession attempt (outside band),
    # so the only thing that can downgrade it to "maintained" is schema validity.
    consensus = consensus_position(case["round_utilities"])
    expected_revised_score = concede_toward(case["current"], consensus)

    if response["status"] == "revised":
        # R3.6 / R10.1: every emitted revised payload is schema-valid.
        validate_agent_payload(agent, response["payload"])
        # The valid case must take this branch, and report the honest revised score.
        assert case["payload_valid"] is True
        assert response["payload"] == payload
        assert response["utility_score"] == pytest.approx(expected_revised_score, abs=1e-9)
    else:
        # R3.10 / R10.1: an invalid candidate payload is rejected, not propagated.
        assert response["status"] == "maintained"
        assert case["payload_valid"] is False
        assert response["rationale"] == "revision_failed_schema"
        assert "payload" not in response


# ---------------------------------------------------------------------------
# Import-time guards: the "valid" factories must really validate, and the
# "invalid" payload must really fail, or the properties above are vacuous.
# ---------------------------------------------------------------------------
for _agent in WHOLE_SCHEMA_AGENTS:
    validate_agent_payload(_agent.value, _valid_payload(_agent.value, 0))
    try:
        validate_agent_payload(_agent.value, dict(_INVALID_PAYLOAD))
    except SchemaValidationError:
        pass
    else:  # pragma: no cover - guards a mistaken "invalid" payload
        raise AssertionError(f"_INVALID_PAYLOAD unexpectedly validated for {_agent.value}")
