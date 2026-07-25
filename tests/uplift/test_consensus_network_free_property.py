"""Property-based test that the assembled consensus arm decides network-free.

Feature: core-purpose-uplift
Property 1: Consensus arm decides only through the in-process transport (network-free)

    *For any* reachable :class:`~uplift.interfaces.Observation` fed to an assembled
    :class:`~uplift.consensus_arm.ConsensusArm`, ``decide`` produces its result by
    invoking only the injected in-process transport (recorded transport calls > 0) and
    never opens a network socket.

    The arm is assembled through :func:`uplift.consensus_arm.build_consensus_arm` with
    injected stub agent/twin ``handle_request`` handlers, so the run stays fast and
    in-process while the REAL :class:`ConsensusProtocol` (real tier router, guardrails,
    audit logger, HITL escalation, context builder, meta-RL, semantic cache) drives the
    decision. Every socket entry point is monkeypatched to fail for the duration of
    ``decide``, so any attempt to dial the network fails the test loudly.

    Requirement 1.2: "WHEN the consensus arm is assembled through the assembly
    function, THE Consensus_Arm SHALL make each decision by invoking
    ``ConsensusProtocol.run_consensus`` over the In_Process_Transport, without opening
    any network socket or contacting any external service."

**Validates: Requirements 1.2**
"""
from __future__ import annotations

import socket
from typing import Any
from uuid import uuid4

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from synapse_common.models import AgentName, AgentProposal, DecisionTier

from uplift.consensus_arm import (
    ConsensusArmUnavailable,
    build_consensus_arm,
    build_consensus_protocol,
)
from uplift.interfaces import Observation, PolicyAction

_AGENT_NAMES: tuple[str, ...] = tuple(str(name) for name in AgentName)


# ---------------------------------------------------------------------------
# Stub in-process handlers — record every transport dispatch they receive
# ---------------------------------------------------------------------------
class _RecordingAgentHandler:
    """A stub agent ``handle_request`` recording each in-process transport call.

    Answers ``proposal`` with a schema-valid :class:`AgentProposal` (so consensus
    reaches a binding decision) and ``execute`` with an honest confirmation. Nothing is
    fabricated about the *world*: the harness applies the returned action itself.
    """

    def __init__(self, agent_name: str, *, price: float) -> None:
        self._agent_name = agent_name
        self._price = price
        self.calls: list[str] = []

    def handle_request(self, request: dict[str, Any]) -> dict[str, Any]:
        method = str(request.get("method", ""))
        self.calls.append(method)
        request_id = request.get("id") or str(uuid4())
        if method == "proposal":
            proposal = AgentProposal(
                agent_name=AgentName(self._agent_name),
                decision_id=uuid4(),
                utility_score=0.7,
                confidence=0.7,
                justification_trace=[f"{self._agent_name}: stub in-process proposal"],
                payload={"price": self._price, "sku_id": "sku-1", "quantity": 1},
                tier=DecisionTier.TIER_2,
            )
            result: dict[str, Any] = proposal.model_dump(mode="json")
        elif method == "execute":
            result = {"status": "acknowledged"}
        else:
            return {
                "jsonrpc": "2.0",
                "error": {"code": -32601, "message": f"unsupported method {method}"},
                "id": request_id,
            }
        return {"jsonrpc": "2.0", "result": result, "id": request_id}


class _RecordingTwinHandler:
    """A stub twin ``handle_request`` recording each in-process transport call."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    def handle_request(self, request: dict[str, Any]) -> dict[str, Any]:
        self.calls.append(str(request.get("method", "")))
        return {
            "jsonrpc": "2.0",
            "result": {
                "scenarios_run": 1000,
                "kpis": {"fill_rate": {"mean": 0.9, "p50": 0.9, "p95": 0.95}},
                "recommendation": "proceed",
            },
            "id": request.get("id") or str(uuid4()),
        }


#: Addresses the interpreter itself needs: ``asyncio``'s event-loop self-pipe is a
#: loopback ``socketpair`` on Windows, so a *purely local* loopback connect is not a
#: network dial and must stay permitted or no event loop could be created at all.
_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "::1", "localhost", "0.0.0.0", ""})


class _SocketGuard:
    """Fail every outbound network dial while recording the attempts (R1.2, I-1).

    Installed around ``decide``, so an attempt to reach an agent, the twin, an LLM, or
    any other external service raises instead of silently succeeding:

    * ``httpx`` request/send (the transport :func:`send_a2a_request` really uses) fails
      unconditionally — a network-free arm must never build an HTTP request at all.
    * ``socket.getaddrinfo`` / ``create_connection`` / ``socket.connect`` fail for any
      non-loopback address, so a raw dial is caught too.

    ``attempts`` is asserted empty by the property: a network-free decision touches none
    of these paths.
    """

    def __init__(self) -> None:
        self.attempts: list[str] = []
        self._saved: dict[str, Any] = {}

    @staticmethod
    def _host_of(address: Any) -> str:
        if isinstance(address, tuple) and address:
            return str(address[0])
        return str(address)

    def _fail(self, label: str) -> Any:
        def guard(*_: Any, **__: Any) -> Any:
            self.attempts.append(label)
            raise AssertionError(f"network access attempted via {label}")

        return guard

    def _fail_unless_loopback(self, label: str, original: Any, address_index: int) -> Any:
        def guard(*args: Any, **kwargs: Any) -> Any:
            address = args[address_index] if len(args) > address_index else kwargs.get("address")
            if self._host_of(address) in _LOOPBACK_HOSTS:
                return original(*args, **kwargs)
            self.attempts.append(f"{label}->{address!r}")
            raise AssertionError(f"network access attempted via {label} to {address!r}")

        return guard

    def __enter__(self) -> _SocketGuard:
        import httpx

        self._saved = {
            "socket.create_connection": socket.create_connection,
            "socket.getaddrinfo": socket.getaddrinfo,
            "socket.socket.connect": socket.socket.connect,
            "socket.socket.connect_ex": socket.socket.connect_ex,
            "httpx.AsyncClient.send": httpx.AsyncClient.send,
            "httpx.AsyncClient.request": httpx.AsyncClient.request,
            "httpx.Client.send": httpx.Client.send,
        }
        socket.create_connection = self._fail_unless_loopback(  # type: ignore[assignment]
            "socket.create_connection", self._saved["socket.create_connection"], 0
        )
        socket.getaddrinfo = self._fail_unless_loopback(  # type: ignore[assignment]
            "socket.getaddrinfo", self._saved["socket.getaddrinfo"], 0
        )
        socket.socket.connect = self._fail_unless_loopback(  # type: ignore[method-assign]
            "socket.connect", self._saved["socket.socket.connect"], 1
        )
        socket.socket.connect_ex = self._fail_unless_loopback(  # type: ignore[method-assign]
            "socket.connect_ex", self._saved["socket.socket.connect_ex"], 1
        )
        httpx.AsyncClient.send = self._fail("httpx.AsyncClient.send")  # type: ignore[method-assign]
        httpx.AsyncClient.request = self._fail("httpx.AsyncClient.request")  # type: ignore[method-assign]
        httpx.Client.send = self._fail("httpx.Client.send")  # type: ignore[method-assign]
        return self

    def __exit__(self, *_: Any) -> None:
        import httpx

        socket.create_connection = self._saved["socket.create_connection"]  # type: ignore[assignment]
        socket.getaddrinfo = self._saved["socket.getaddrinfo"]  # type: ignore[assignment]
        socket.socket.connect = self._saved["socket.socket.connect"]  # type: ignore[method-assign]
        socket.socket.connect_ex = self._saved["socket.socket.connect_ex"]  # type: ignore[method-assign]
        httpx.AsyncClient.send = self._saved["httpx.AsyncClient.send"]  # type: ignore[method-assign]
        httpx.AsyncClient.request = self._saved["httpx.AsyncClient.request"]  # type: ignore[method-assign]
        httpx.Client.send = self._saved["httpx.Client.send"]  # type: ignore[method-assign]


# ---------------------------------------------------------------------------
# The assembled arm (built once; the real protocol resets its state per run)
# ---------------------------------------------------------------------------
_AGENT_STUBS: dict[str, _RecordingAgentHandler] = {
    name: _RecordingAgentHandler(name, price=1.0 + index)
    for index, name in enumerate(_AGENT_NAMES)
}
_TWIN_STUB = _RecordingTwinHandler()

try:
    _PROTOCOL = build_consensus_protocol()
    _ARM = build_consensus_arm(
        agent_handlers={name: stub.handle_request for name, stub in _AGENT_STUBS.items()},
        twin_handler=_TWIN_STUB.handle_request,
        protocol=_PROTOCOL,
    )
except ConsensusArmUnavailable as exc:  # pragma: no cover — environment cannot assemble
    _ARM = None  # type: ignore[assignment]
    _UNAVAILABLE_REASON: str | None = str(exc)
else:
    _UNAVAILABLE_REASON = None

pytestmark = pytest.mark.skipif(
    _UNAVAILABLE_REASON is not None,
    reason=f"consensus arm cannot be assembled here: {_UNAVAILABLE_REASON}",
)


def _recorded_transport_calls() -> int:
    """Total in-process dispatches recorded by the stub agent/twin handlers."""
    return sum(len(stub.calls) for stub in _AGENT_STUBS.values()) + len(_TWIN_STUB.calls)


def _reset_recordings() -> None:
    for stub in _AGENT_STUBS.values():
        stub.calls.clear()
    _TWIN_STUB.calls.clear()


# ---------------------------------------------------------------------------
# Reachable observations (no shock ⇒ the fast tier, so the property stays cheap)
# ---------------------------------------------------------------------------
@st.composite
def _observations(draw: st.DrawFn) -> Observation:
    skus = draw(st.lists(st.sampled_from(["sku-1", "sku-2", "sku-3"]), min_size=1, max_size=3, unique=True))
    inventory = {
        sku: draw(st.integers(min_value=0, max_value=500)) for sku in skus
    }
    unit_costs = {
        sku: draw(st.floats(min_value=0.1, max_value=50.0, allow_nan=False, allow_infinity=False))
        for sku in skus
    }
    return Observation(
        inventory=inventory,
        sim_time=draw(st.floats(min_value=0.0, max_value=1440.0, allow_nan=False, allow_infinity=False)),
        delivery_count=draw(st.integers(min_value=0, max_value=1000)),
        spoilage_count=draw(st.integers(min_value=0, max_value=1000)),
        stockout_count=draw(st.integers(min_value=0, max_value=1000)),
        unit_costs=unit_costs,
    )


# ``max_examples`` is deliberately NOT hardcoded: every example runs the real
# ``ConsensusProtocol`` over the in-process transport, so the count is inherited from the
# active Hypothesis profile (see the root ``conftest.py``) — ``dev`` = 10 for light local
# runs, ``ci``/``default`` = 500 for the CI budget that satisfies the >= 100-iteration
# obligation.
@pytest.mark.slow
@settings(
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
)
@given(obs=_observations())
def test_consensus_decides_only_through_in_process_transport(obs: Observation) -> None:
    """Every decision flows through the injected in-process transport, no socket opened."""
    _reset_recordings()

    with _SocketGuard() as guard:
        action = _ARM.decide(obs)

    # The decision was produced (not fabricated around an unreachable network).
    assert isinstance(action, PolicyAction)

    # It was produced by dispatching through the in-process transport.
    assert _recorded_transport_calls() > 0, "no in-process transport dispatch was recorded"

    # And nothing dialed the network.
    assert guard.attempts == [], f"network access attempted: {guard.attempts}"
