"""Unit tests for the in-process consensus arm adapter (uplift/consensus_arm.py).

Covers the design's error-handling contract (R2.7): the arm fails loudly on missing
dependencies and on ``run_consensus`` raising, never fabricates a decision, maps an
Observation to a decision_request, dispatches through an in-process A2A transport
(no HTTP), and translates a binding ConsensusDecision into a PolicyAction.
"""
from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest
from synapse_common.a2a_sdk import A2AResponse
from synapse_common.models import AgentName, AgentProposal, ConsensusDecision, DecisionTier

from uplift.consensus_arm import (
    ConsensusArm,
    ConsensusArmUnavailable,
    InProcessA2ATransport,
    consensus_decision_to_policy_action,
    observation_to_decision_request,
)
from uplift.interfaces import DecisionPolicy, Observation, PendingOrder, Store
from digital_twin.simulation.monte_carlo import ShockParams


# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------
def _decision(selected_action: dict[str, Any], *, with_proposal: bool = True) -> ConsensusDecision:
    proposals: list[AgentProposal] = []
    if with_proposal:
        proposals.append(
            AgentProposal(
                agent_name=AgentName.PRICING_ORACLE,
                decision_id=uuid4(),
                utility_score=0.8,
                confidence=0.7,
                justification_trace=["p"],
                payload=selected_action,
                tier=DecisionTier.TIER_2,
            )
        )
    return ConsensusDecision(
        decision_id=uuid4(),
        tier=DecisionTier.TIER_2,
        proposals=proposals,
        selected_action=selected_action,
        pareto_weights={"pricing_revenue": 1.0},
        confidence=0.7,
        audit_trace=["tier=2"],
        phase_reached=4,
    )


class _FakeProtocol:
    """Records the decision_request it received and returns a canned decision."""

    def __init__(self, decision: ConsensusDecision | None = None, *, raises: Exception | None = None):
        self._decision = decision
        self._raises = raises
        self.seen_request: dict[str, Any] | None = None

    async def run_consensus(self, decision_request: dict[str, Any]) -> ConsensusDecision:
        self.seen_request = decision_request
        if self._raises is not None:
            raise self._raises
        assert self._decision is not None
        return self._decision


async def _noop_transport(**_: Any) -> A2AResponse:
    return A2AResponse(id="x", result={})


def _obs(**overrides: Any) -> Observation:
    base: dict[str, Any] = {
        "inventory": {"sku-1": 5},
        "sim_time": 1.0,
        "delivery_count": 0,
        "spoilage_count": 0,
        "stockout_count": 0,
        "unit_costs": {"sku-1": 2.0},
    }
    base.update(overrides)
    return Observation(**base)


# ---------------------------------------------------------------------------
# Construction — fail loudly (never fabricate)
# ---------------------------------------------------------------------------
def test_missing_transport_raises() -> None:
    with pytest.raises(ConsensusArmUnavailable):
        ConsensusArm(protocol=_FakeProtocol(_decision({})), transport=None)


def test_missing_protocol_raises() -> None:
    with pytest.raises(ConsensusArmUnavailable):
        ConsensusArm(transport=_noop_transport)


def test_raising_factory_surfaces_as_unavailable() -> None:
    def boom() -> Any:
        raise RuntimeError("cannot build")

    with pytest.raises(ConsensusArmUnavailable):
        ConsensusArm(protocol_factory=boom, transport=_noop_transport)


def test_is_decision_policy() -> None:
    arm = ConsensusArm(protocol=_FakeProtocol(_decision({})), transport=_noop_transport)
    assert arm.name == "consensus"
    assert isinstance(arm, DecisionPolicy)


# ---------------------------------------------------------------------------
# decide — surface failures, translate real decisions
# ---------------------------------------------------------------------------
def test_run_consensus_raise_propagates() -> None:
    arm = ConsensusArm(
        protocol=_FakeProtocol(raises=RuntimeError("consensus exploded")),
        transport=_noop_transport,
    )
    with pytest.raises(RuntimeError, match="consensus exploded"):
        arm.decide(_obs())


def test_zero_proposals_surface_as_unavailable() -> None:
    arm = ConsensusArm(
        protocol=_FakeProtocol(_decision({}, with_proposal=False)),
        transport=_noop_transport,
    )
    with pytest.raises(ConsensusArmUnavailable):
        arm.decide(_obs())


def test_decide_translates_price() -> None:
    arm = ConsensusArm(
        protocol=_FakeProtocol(_decision({"price": 9.5})),
        transport=_noop_transport,
    )
    action = arm.decide(_obs())
    assert action.price == 9.5


def test_decide_builds_request_and_routes_tier4_on_shock() -> None:
    proto = _FakeProtocol(_decision({"price": 1.0}))
    arm = ConsensusArm(protocol=proto, transport=_noop_transport)
    arm.decide(_obs(active_shock=ShockParams(demand_multiplier=2.0)))
    assert proto.seen_request is not None
    assert proto.seen_request["disruption_active"] is True
    assert proto.seen_request["requires_twin_simulation"] is True
    assert proto.seen_request["sku_ids"] == ["sku-1"]
    assert proto.seen_request["shock"]["demand_multiplier"] == 2.0


# ---------------------------------------------------------------------------
# request builder + translator (pure)
# ---------------------------------------------------------------------------
def test_request_builder_includes_routing_context() -> None:
    obs = _obs(
        pending_order=PendingOrder(order_id="o-1", destination=(1.0, 2.0)),
        eligible_stores=(Store(store_id=3, location=(0.0, 0.0)),),
    )
    req = observation_to_decision_request(obs)
    assert req["pending_order"]["order_id"] == "o-1"
    assert req["eligible_stores"][0]["store_id"] == 3
    assert req["disruption_active"] is False


def test_translator_extracts_all_levers() -> None:
    obs = _obs(pending_order=PendingOrder(order_id="o-9", destination=(0.0, 0.0)))
    decision = _decision(
        {
            "price": 4.0,
            "reorder_quantities": {"sku-1": 10},
            "store_id": 7,
            "disruption_actions": ["reroute", "hold"],
        }
    )
    action = consensus_decision_to_policy_action(decision, obs)
    assert action.price == 4.0
    assert action.reorder_quantities == {"sku-1": 10.0}
    assert action.routing_assignment is not None
    assert action.routing_assignment.store_id == 7
    assert action.disruption_actions == frozenset({"reroute", "hold"})


# ---------------------------------------------------------------------------
# in-process transport
# ---------------------------------------------------------------------------
def test_transport_dispatches_to_handler() -> None:
    seen: dict[str, Any] = {}

    def handler(request: dict[str, Any]) -> dict[str, Any]:
        seen.update(request)
        return {"jsonrpc": "2.0", "result": {"echo": request["method"]}, "id": request["id"]}

    transport = InProcessA2ATransport({"http://pricing-oracle:8005": handler})
    import asyncio

    resp = asyncio.run(
        transport(target_url="http://pricing-oracle:8005", method="proposal", params={"a": 1})
    )
    assert resp.error is None
    assert resp.result == {"echo": "proposal"}
    assert seen["method"] == "proposal"


def test_transport_unknown_url_returns_error_not_raise() -> None:
    transport = InProcessA2ATransport({})
    import asyncio

    resp = asyncio.run(transport(target_url="http://nope:1", method="proposal", params={}))
    assert resp.result is None
    assert resp.error is not None


def test_transport_from_agents_resolves_endpoints() -> None:
    def handler(request: dict[str, Any]) -> dict[str, Any]:
        return {"jsonrpc": "2.0", "result": {}, "id": request["id"]}

    transport = InProcessA2ATransport.from_agents({"pricing_oracle": handler})
    assert "http://pricing-oracle:8005" in transport._handlers


def test_transport_from_agents_unknown_agent_raises() -> None:
    with pytest.raises(ConsensusArmUnavailable):
        InProcessA2ATransport.from_agents({"not_an_agent": lambda r: {}})
