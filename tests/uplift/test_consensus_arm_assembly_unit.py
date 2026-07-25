"""Example test for the assembly wiring shape of ``build_consensus_arm`` (R1.1).

Feature: core-purpose-uplift, Task 1.4 — the assembly seam must stand up the *whole*
in-process network the real :class:`ConsensusProtocol` dials: every one of the eight
canonical agent URLs in :data:`AGENT_ENDPOINTS` plus :data:`TWIN_ENDPOINT`, and nothing
else. The returned object must satisfy the arm-agnostic
:class:`~uplift.interfaces.DecisionPolicy` protocol (``name`` + ``decide``) so the
harness can run it exactly like a baseline arm.

Stub agent/twin handlers and a stub protocol are injected so the test stays in-process
and fast, but the URL-coverage assertion is derived from the real ``AGENT_ENDPOINTS`` /
``TWIN_ENDPOINT`` values and the real ``_AGENT_HANDLER_SPECS`` agent names — so a
missing or misnamed agent in the default assembly fails here.

_Requirements: 1.1_
"""
from __future__ import annotations

from typing import Any
from uuid import uuid4

from orchestrator.consensus.protocol import AGENT_ENDPOINTS, TWIN_ENDPOINT
from synapse_common.models import AgentName, AgentProposal, ConsensusDecision, DecisionTier

from uplift.consensus_arm import (
    _AGENT_HANDLER_SPECS,
    ConsensusArm,
    build_consensus_arm,
)
from uplift.harness import DEFAULT_CONSENSUS_ARM
from uplift.interfaces import DecisionPolicy, Observation, PolicyAction


# ---------------------------------------------------------------------------
# Stubs (keep the assembly in-process and fast; no real models, no sockets)
# ---------------------------------------------------------------------------
def _stub_handler(request: dict[str, Any]) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "result": {}, "id": request["id"]}


class _StubProtocol:
    """Minimal ``run_consensus``-shaped protocol returning one binding proposal."""

    async def run_consensus(self, decision_request: dict[str, Any]) -> ConsensusDecision:
        action = {"price": 3.5}
        return ConsensusDecision(
            decision_id=uuid4(),
            tier=DecisionTier.TIER_2,
            proposals=[
                AgentProposal(
                    agent_name=AgentName.PRICING_ORACLE,
                    decision_id=uuid4(),
                    utility_score=0.9,
                    confidence=0.8,
                    justification_trace=["stub"],
                    payload=action,
                    tier=DecisionTier.TIER_2,
                )
            ],
            selected_action=action,
            pareto_weights={"pricing_revenue": 1.0},
            confidence=0.8,
            audit_trace=["tier=2"],
            phase_reached=4,
        )


def _build_stub_arm() -> ConsensusArm:
    return build_consensus_arm(
        agent_handlers={name: _stub_handler for name in AGENT_ENDPOINTS},
        twin_handler=_stub_handler,
        protocol=_StubProtocol(),
    )


# ---------------------------------------------------------------------------
# Wiring shape: exactly the 8 agent URLs + the twin endpoint
# ---------------------------------------------------------------------------
def test_assembled_transport_covers_eight_agents_plus_twin() -> None:
    arm = _build_stub_arm()

    registered = set(arm._transport._handlers)  # type: ignore[attr-defined]
    expected = set(AGENT_ENDPOINTS.values()) | {TWIN_ENDPOINT}

    assert len(AGENT_ENDPOINTS) == 8, "the protocol fan-out must cover eight agents"
    assert registered == expected
    assert len(registered) == 9


def test_default_agent_specs_match_agent_endpoints() -> None:
    """The default assembly builds a handler for every URL the protocol dials."""
    spec_names = {name for name, _module, _cls in _AGENT_HANDLER_SPECS}
    assert spec_names == set(AGENT_ENDPOINTS)


# ---------------------------------------------------------------------------
# Return value satisfies the DecisionPolicy protocol (name + decide)
# ---------------------------------------------------------------------------
def test_assembled_arm_satisfies_decision_policy() -> None:
    arm = _build_stub_arm()

    assert isinstance(arm, DecisionPolicy)
    assert arm.name == DEFAULT_CONSENSUS_ARM
    assert callable(arm.decide)

    action = arm.decide(
        Observation(
            inventory={"sku-1": 5},
            sim_time=1.0,
            delivery_count=0,
            spoilage_count=0,
            stockout_count=0,
            unit_costs={"sku-1": 2.0},
        )
    )
    assert isinstance(action, PolicyAction)
    assert action.price == 3.5
