"""Property test: a reachable observation is translated, never surfaced as unavailable.

Feature: core-purpose-uplift
Property 2: A reachable observation yields a translated PolicyAction, not unavailability

    *For any* reachable ``Observation`` with an in-process agent network that returns at
    least one proposal, :meth:`uplift.consensus_arm.ConsensusArm.decide` returns a
    :class:`~uplift.interfaces.PolicyAction` instance and does not raise
    :class:`~uplift.consensus_arm.ConsensusArmUnavailable`.

    Requirement 1.3: "WHEN the assembled Consensus_Arm runs a scenario whose observation
    is reachable by the assembled agents, THE Consensus_Arm SHALL return a translated
    ``PolicyAction`` derived from a binding ``ConsensusDecision`` rather than raising
    ``ConsensusArmUnavailable``."

    The arm under test is assembled through the real seam
    :func:`uplift.consensus_arm.build_consensus_arm` with **injected stub agent/twin
    handlers**, so the real four-tier :class:`ConsensusProtocol` runs unchanged while the
    run stays in-process, network-free and $0 (I-1): every A2A call is dispatched to a
    local callable by :class:`InProcessA2ATransport`. The stubs stand in only for the
    eight agents' and the twin's ``handle_request`` — the decision logic, tier routing,
    arbitration, guardrails, audit chain and translation are all the real modules.

Validates: Requirements 1.3
"""
from __future__ import annotations

from functools import lru_cache
from typing import Any
from uuid import uuid4

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from synapse_common.models import AgentName, AgentProposal, DecisionTier

from digital_twin.simulation.monte_carlo import ShockParams
from uplift.consensus_arm import (
    A2AHandler,
    ConsensusArm,
    build_consensus_arm,
)
from uplift.interfaces import Observation, PendingOrder, PolicyAction, Store

# Confidence comfortably above the guardrail confidence floor (0.7) so a reachable
# observation exercises the ratify-and-execute path rather than HITL escalation.
_CONFIDENCE = 0.9

# Utility spread kept under the 0.3 conflict threshold: the agents agree, so the full
# path skips the debate phase. Distinct values still give arbitration a strict winner.
_BASE_UTILITY = 0.60
_UTILITY_STEP = 0.01

# The price and store the stub payloads carry, so the translated action can be checked
# against what the binding decision actually said (translation, never fabrication).
_STUB_PRICE = 7.25
_STUB_STORE_ID = 11


def _stub_payload(decision_context: dict[str, Any]) -> dict[str, Any]:
    """A proposal payload expressing every twin lever, derived from the request.

    Every agent proposes the same levers so the translated action is checkable no matter
    which agent wins the binding selection. Reorder quantities are derived from the
    observed SKUs, so the payload really is a function of the observation.
    """
    inventory: dict[str, Any] = decision_context.get("inventory", {})
    return {
        "price": _STUB_PRICE,
        "reorder_quantities": {sku: 12.0 for sku in inventory},
        "store_id": _STUB_STORE_ID,
        "disruption_actions": ["hold_dispatch"],
    }


def _agent_handler(agent_name: str, utility: float) -> A2AHandler:
    """An in-process ``handle_request`` stub for one agent (JSON-RPC dict in/out)."""

    def handler(request: dict[str, Any]) -> dict[str, Any]:
        request_id = request.get("id")
        method = request.get("method")
        params: dict[str, Any] = request.get("params") or {}
        if method == "proposal":
            context: dict[str, Any] = params.get("decision_context") or {}
            proposal = AgentProposal(
                agent_name=AgentName(agent_name),
                decision_id=uuid4(),
                utility_score=utility,
                confidence=_CONFIDENCE,
                justification_trace=[f"{agent_name}: in-process stub proposal"],
                payload=_stub_payload(context),
                tier=DecisionTier.TIER_2,
            )
            result: dict[str, Any] = proposal.model_dump(mode="json")
        elif method == "execute":
            result = {"status": "acknowledged"}
        else:
            # ``debate_respond`` and anything else: hold the prior proposal honestly.
            result = {"status": "hold"}
        return {"jsonrpc": "2.0", "result": result, "id": request_id}

    return handler


def _twin_handler(request: dict[str, Any]) -> dict[str, Any]:
    """An in-process twin ``handle_request`` stub for Tier-4 twin verification."""
    return {
        "jsonrpc": "2.0",
        "result": {
            "n_scenarios": 1000,
            "kpi_means": {"fill_rate": 0.9, "spoilage_rate": 0.02},
        },
        "id": request.get("id"),
    }


@lru_cache(maxsize=1)
def _arm() -> ConsensusArm:
    """The assembled in-process consensus arm (built once; the protocol resets per run)."""
    handlers = {
        name: _agent_handler(name, _BASE_UTILITY + index * _UTILITY_STEP)
        for index, name in enumerate(agent.value for agent in AgentName)
    }
    return build_consensus_arm(agent_handlers=handlers, twin_handler=_twin_handler)


# ---------------------------------------------------------------------------
# Observation strategy — reachable observations across the tier space
# ---------------------------------------------------------------------------
_skus = st.lists(
    st.sampled_from(["sku-milk", "sku-rice", "sku-bread", "sku-eggs"]),
    min_size=1,
    max_size=4,
    unique=True,
)


@st.composite
def _observations(draw: st.DrawFn) -> Observation:
    skus = draw(_skus)
    inventory = {
        sku: draw(st.integers(min_value=0, max_value=200)) for sku in skus
    }
    unit_costs = {
        sku: draw(st.floats(min_value=0.5, max_value=50.0, allow_nan=False))
        for sku in skus
    }
    shocked = draw(st.booleans())
    shock = (
        ShockParams(
            demand_multiplier=draw(st.floats(min_value=1.0, max_value=3.0)),
            lead_time_multiplier=draw(st.floats(min_value=1.0, max_value=3.0)),
        )
        if shocked
        else None
    )
    routing = draw(st.booleans())
    pending_order = (
        PendingOrder(order_id=f"o-{draw(st.integers(min_value=0, max_value=999))}",
                     destination=(1.5, 2.5))
        if routing
        else None
    )
    stores = (
        (Store(store_id=_STUB_STORE_ID, location=(0.0, 0.0)),) if routing else ()
    )
    return Observation(
        inventory=inventory,
        sim_time=draw(st.floats(min_value=0.0, max_value=1440.0, allow_nan=False)),
        delivery_count=draw(st.integers(min_value=0, max_value=500)),
        spoilage_count=draw(st.integers(min_value=0, max_value=100)),
        stockout_count=draw(st.integers(min_value=0, max_value=100)),
        unit_costs=unit_costs,
        active_shock=shock,
        pending_order=pending_order,
        eligible_stores=stores,
    )


# ``max_examples`` is deliberately NOT hardcoded: every example runs the real four-tier
# consensus (including NSGA-II arbitration), so the count is inherited from the active
# Hypothesis profile (see the root ``conftest.py``) — ``dev`` = 10 for light local runs,
# ``ci``/``default`` = 500 for the CI budget that satisfies the >= 100-iteration obligation.
@pytest.mark.slow
@settings(
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
)
@given(obs=_observations())
def test_reachable_observation_yields_translated_policy_action(obs: Observation) -> None:
    """A reachable observation is translated into a PolicyAction, never unavailability."""
    action = _arm().decide(obs)

    # The property: a translated PolicyAction, not a ConsensusArmUnavailable (which
    # would propagate out of ``decide`` and fail this test).
    assert isinstance(action, PolicyAction)

    # The action is a *translation* of the binding decision's payload, not invention.
    assert action.price == _STUB_PRICE
    assert set(action.reorder_quantities) == set(obs.inventory)
    assert action.disruption_actions == frozenset({"hold_dispatch"})
    if obs.pending_order is None:
        assert action.routing_assignment is None
    else:
        assert action.routing_assignment is not None
        assert action.routing_assignment.order_id == obs.pending_order.order_id
        assert action.routing_assignment.store_id == _STUB_STORE_ID
