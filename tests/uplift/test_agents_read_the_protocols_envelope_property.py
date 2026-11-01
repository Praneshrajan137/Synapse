"""The real agents read the request the consensus protocol sends them (finding 112).

``ConsensusProtocol._request_proposal`` sends every agent ``params={"decision_context": request}``.
Until this repair each handler passed ``params`` straight to ``proposal``, which read its keys at
the top level, so no agent read its request (CLAUDE.md E-DQP-02). The tests that should have
caught it sent flat params, a shape the protocol never sends.

So nothing here builds an envelope by hand. Every enveloped call goes through the protocol's own
``_request_proposal``, over the arm's :class:`~uplift.consensus_arm.InProcessA2ATransport`, to
the handlers :func:`~uplift.consensus_arm.build_agent_handlers` assembles for the E5 consensus
arm. The tests cover the seven agents this repair touches. The Inventory Sentinel is repaired
and tested in ``agents/inventory_sentinel/tests``, and nothing here asserts on it.

What would make each test wrong:

* the forecasts property, if Demand Prophet forecasts any SKU set but the one sent, or refuses
  it, as it did when it read the envelope flat and found no SKUs (``PRE-DP-001``);
* the refusal property, if any of the seven reads a flat request instead of refusing it, or
  refuses without naming ``decision_context``;
* the envelope test, if an agent given the envelope fails with an error that names none of the
  preconditions its ``spec.yaml`` states, as the Pricing Oracle's bare ``IndexError`` on a
  request without ``categories`` did.

Not ``slow``: no twin and no ``run_consensus``, only one protocol method and one agent's
``proposal`` per call, with the handlers and the protocol built once per module. The Disruption
Shield's reasoner is the offline one :func:`~uplift.consensus_arm.build_agent_handlers` gives it
(finding 116), so no call waits on a lookup of ``ollama`` (CLAUDE.md E-DQP-01).
"""

from __future__ import annotations

import asyncio
import re
import string
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest
import yaml
from hypothesis import given
from hypothesis import strategies as st
from synapse_common.a2a_envelope import PROPOSAL_ENVELOPE_KEY
from synapse_common.models import DecisionTier

from orchestrator.consensus import protocol as protocol_mod
from uplift.consensus_arm import (
    InProcessA2ATransport,
    build_agent_handlers,
    build_consensus_protocol,
    observation_to_decision_request,
)
from uplift.interfaces import Observation

if TYPE_CHECKING:
    from collections.abc import Iterator

    from synapse_common.a2a_sdk import A2AResponse
    from synapse_common.models import AgentProposal

#: Every agent the protocol dials but the Inventory Sentinel, which is repaired and tested in
#: agents/inventory_sentinel/tests. Derived, so an agent added to AGENT_ENDPOINTS is covered.
_REPAIRED: tuple[str, ...] = tuple(
    name for name in protocol_mod.AGENT_ENDPOINTS if name != "inventory_sentinel"
)

_REPO_ROOT = Path(__file__).resolve().parents[2]
_PRECONDITION_ID = re.compile(r"\bPRE-[A-Z]{2}-\d{3}\b")


@dataclass(frozen=True)
class _Network:
    """The arm's real agent handlers behind its transport, and a real protocol."""

    transport: InProcessA2ATransport
    protocol: protocol_mod.ConsensusProtocol


@pytest.fixture(scope="module")
def network() -> Iterator[_Network]:
    """Build the eight handlers and the protocol once, with the protocol dialing the transport."""
    with pytest.MonkeyPatch.context() as patch:
        # The code alone is checked: the arm's handlers carry the offline reasoner (finding 116),
        # so the variable E5's job once pointed at a refused port is cleared. With no Pinecone
        # key the playbook retriever builds no client, as in E5's job.
        patch.delenv("DS_OLLAMA_BASE_URL", raising=False)
        patch.delenv("PINECONE_API_KEY", raising=False)
        transport = InProcessA2ATransport.from_agents(build_agent_handlers())
        # `_request_proposal` dials the module-level `send_a2a_request`, the same symbol
        # ConsensusArm._run_consensus rebinds to install its transport.
        patch.setattr(protocol_mod, "send_a2a_request", transport)
        yield _Network(transport=transport, protocol=build_consensus_protocol())


def _propose(network: _Network, agent: str, request: dict[str, Any]) -> AgentProposal:
    """One agent's proposal for ``request``, in the envelope the protocol itself builds.

    Raises:
        RuntimeError: the agent answered with an error, as ``_request_proposal`` raises it.
    """
    url = protocol_mod.AGENT_ENDPOINTS[agent]
    coroutine = network.protocol._request_proposal(agent, url, request, DecisionTier.TIER_2)
    return asyncio.run(coroutine)


def _send_flat(network: _Network, agent: str, params: dict[str, Any]) -> A2AResponse:
    """One ``proposal`` call with ``params`` sent as they are, in no envelope."""
    url = protocol_mod.AGENT_ENDPOINTS[agent]
    return asyncio.run(network.transport(target_url=url, method="proposal", params=params))


@cache
def _stated_preconditions(agent: str) -> frozenset[str]:
    """The precondition ids ``agents/<agent>/spec.yaml`` states."""
    path = _REPO_ROOT / "agents" / agent / "spec.yaml"
    spec = yaml.safe_load(path.read_text(encoding="utf-8"))
    return frozenset(str(entry["id"]) for entry in spec["preconditions"])


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------
#: Lower-case, so the upper-case ``SKU001`` that agents and old tests default to is never drawn:
#: a forecast naming it can only be a default leaking through.
#: Drawn with ``st.text`` over an explicit alphabet rather than ``st.from_regex``: the regex
#: strategy tripped Hypothesis's ``too_slow`` health check on its first draws (measured locally,
#: session 13), and the alphabet alone carries the property's precondition.
_SKUS = st.text(alphabet=string.ascii_lowercase + string.digits + "_-", min_size=1, max_size=12)
_STORES = st.text(alphabet=string.ascii_uppercase + string.digits + "_", min_size=1, max_size=16)
_SCALARS = st.one_of(st.none(), st.booleans(), st.integers(), st.text(max_size=8))


@st.composite
def _observations(draw: st.DrawFn) -> Observation:
    """A twin observation as the E5 arm sees one, over zero to four stocked SKUs."""
    skus = draw(st.lists(_SKUS, max_size=4, unique=True))
    return Observation(
        inventory={sku: draw(st.integers(min_value=0, max_value=500)) for sku in skus},
        sim_time=draw(st.floats(min_value=0.0, max_value=1440.0)),
        delivery_count=draw(st.integers(min_value=0, max_value=1000)),
        spoilage_count=draw(st.integers(min_value=0, max_value=1000)),
        stockout_count=draw(st.integers(min_value=0, max_value=1000)),
        unit_costs={sku: draw(st.floats(min_value=0.1, max_value=50.0)) for sku in skus},
        on_order={sku: draw(st.floats(min_value=0.0, max_value=100.0)) for sku in skus},
        start_weekday=draw(st.none() | st.integers(min_value=0, max_value=6)),
    )


#: Proposal params in no envelope: the request the E5 arm builds, sent as it is, and arbitrary
#: objects that lack the key.
_FLAT_PARAMS = st.one_of(
    _observations().map(observation_to_decision_request),
    st.dictionaries(
        st.text(max_size=12).filter(lambda key: key != PROPOSAL_ENVELOPE_KEY),
        _SCALARS,
        max_size=5,
    ),
)


# ---------------------------------------------------------------------------
# Fixed requests. Each runs all seven pipelines, and between them they hold the cases an
# agent's outcome turns on, so a generated budget would only repeat them.
# ---------------------------------------------------------------------------
#: A store. Freshness Guardian's PRE-FG-001 needs one, and the arm's request never names one:
#: the last test pins what the Guardian does without it.
_STORE_ID = "STORE_BLR_001"

_STOCKED = Observation(
    inventory={"sku-a": 12, "sku-b": 0},
    sim_time=90.0,
    delivery_count=3,
    spoilage_count=0,
    stockout_count=1,
    unit_costs={"sku-a": 2.5, "sku-b": 4.0},
    on_order={"sku-b": 20.0},
)
_UNSTOCKED = Observation(
    inventory={},
    sim_time=0.0,
    delivery_count=0,
    spoilage_count=0,
    stockout_count=0,
    unit_costs={},
)

#: What each agent finds inside the envelope. An agent's outcome turns on whether the request
#: names SKUs, whether it names a store, and whether a field is unset. These three cover each of
#: those, but not SKUs without a store, which the Freshness Guardian refuses without naming a
#: stated precondition (the last test pins it). The third is unset fields: the live route builds
#: its request with ``DecisionRequest.model_dump()`` (orchestrator/inference/serve.py), which
#: sends an unset field as ``None`` rather than leaving it out, and an agent that read that
#: ``None`` would fail validation instead of taking its default.
_ENVELOPED: dict[str, dict[str, Any]] = {
    "arm-request-stocked-with-a-store": {
        **observation_to_decision_request(_STOCKED),
        "store_id": _STORE_ID,
    },
    "arm-request-unstocked-with-a-store": {
        **observation_to_decision_request(_UNSTOCKED),
        "store_id": _STORE_ID,
    },
    "fields-left-unset": {
        "sku_ids": None,
        "store_id": None,
        "decision_id": None,
        "order_id": None,
    },
}


# ---------------------------------------------------------------------------
# Properties
# ---------------------------------------------------------------------------
@given(skus=st.lists(_SKUS, min_size=1, max_size=8, unique=True), store=_STORES)
def test_demand_prophet_forecasts_exactly_the_skus_and_the_store_the_protocol_sent(
    network: _Network, skus: list[str], store: str
) -> None:
    proposal = _propose(network, "demand_prophet", {"sku_ids": skus, "store_id": store})

    forecasts = proposal.payload["forecasts"]
    assert [forecast["sku_id"] for forecast in forecasts] == skus
    assert {forecast["store_id"] for forecast in forecasts} == {store}
    assert proposal.payload["store_id"] == store


@given(params=_FLAT_PARAMS)
def test_every_repaired_agent_refuses_a_flat_proposal_by_naming_the_envelope_key(
    network: _Network, params: dict[str, Any]
) -> None:
    assert _REPAIRED, "no agent is under test, so this property would pass vacuously"
    for agent in _REPAIRED:
        response = _send_flat(network, agent, params)

        assert response.result is None, f"{agent} read a flat request: {response.result}"
        assert response.error is not None, agent
        assert PROPOSAL_ENVELOPE_KEY in response.error["message"], (agent, response.error)


@pytest.mark.parametrize("label", sorted(_ENVELOPED))
def test_every_repaired_agent_given_the_envelope_proposes_or_refuses_by_a_stated_precondition(
    network: _Network, label: str
) -> None:
    """A stated precondition is one whose id the agent's ``spec.yaml`` lists."""
    outcomes: dict[str, str] = {}
    for agent in _REPAIRED:
        try:
            proposal = _propose(network, agent, _ENVELOPED[label])
        except RuntimeError as refusal:
            named = set(_PRECONDITION_ID.findall(str(refusal))) & _stated_preconditions(agent)
            assert named, f"{agent} refused {label} naming no precondition it states: {refusal}"
            outcomes[agent] = "refused by " + ", ".join(sorted(named))
        else:
            assert proposal.agent_name == agent
            outcomes[agent] = "proposed"

    assert outcomes, "no agent was asked, so this test would pass vacuously"
    assert set(outcomes) == set(_REPAIRED), outcomes


def test_the_pricing_oracle_refuses_the_arms_request_by_naming_the_keys_it_lacks(
    network: _Network,
) -> None:
    """The arm sends SKUs and no ``categories`` or ``base_prices``, and the Oracle says so.

    Read through the envelope, this request reaches the Oracle's pipeline with SKUs and nothing
    to price them by. ``_build_updates`` indexes ``categories`` and ``base_prices`` per SKU, so it
    raised a bare ``IndexError`` until the preconditions were checked by name. PRE-PO-001 and
    PRE-PO-003 hold per SKU, so a SKU with neither fails both, and the refusal names both.
    """
    with pytest.raises(RuntimeError) as refusal:
        _propose(network, "pricing_oracle", _ENVELOPED["arm-request-stocked-with-a-store"])

    message = str(refusal.value)
    for named in ("PRE-PO-001", "'categories'", "PRE-PO-003", "'base_prices'"):
        assert named in message, (named, message)


def test_the_freshness_guardian_refuses_the_arms_own_request_because_it_names_no_store(
    network: _Network,
) -> None:
    """The E5 arm's request names SKUs and no store, so the Guardian assesses none of them.

    Reading the envelope flat, the Guardian found no SKUs and proposed an empty assessment. It
    now finds the SKUs and refuses for want of a store: PRE-FG-001's condition, enforced by
    ``FreshnessRequest.store_id``. The refusal names the field but not PRE-FG-001, which is why
    the envelope test above sends a store and this test pins what happens without one.
    """
    request = observation_to_decision_request(_STOCKED)
    assert request["sku_ids"], "the premise needs SKUs to assess"
    assert "store_id" not in request, "the arm now names a store, so this premise is stale"

    with pytest.raises(RuntimeError) as refusal:
        _propose(network, "freshness_guardian", request)

    assert "store_id" in str(refusal.value)
