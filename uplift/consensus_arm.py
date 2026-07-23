"""
SYNAPSE Decision-Integrity Uplift Proof — the in-process consensus arm (R1.6, R2.2, R2.7).

The Consensus_Arm must exercise SYNAPSE's *real* four-tier consensus
(:meth:`orchestrator.consensus.protocol.ConsensusProtocol.run_consensus`), which in
production reaches the eight agents and the twin over A2A HTTP. A ``$0``,
self-contained, one-command harness cannot stand up the live network stack, so this
adapter resolves the tension with an **in-process A2A transport**: the
:class:`ConsensusProtocol` is driven with its proposal / debate / execute / twin
calls dispatched directly to the agents' and twin's in-process A2A *handler
functions* (the same ``handle_request`` callables the FastAPI servers wrap) instead
of over the wire. This keeps the real tier routing, debate, Pareto arbitration and
Tier-4 twin verification logic intact while remaining network-free and free of any
external service.

Standing up the full eight-agent + twin network in-process may not be feasible in
every environment, so — per the design's error-handling contract — this adapter is
built on **dependency injection** and **fails loudly** rather than fabricating a
decision:

* A configured :class:`ConsensusProtocol` (or a factory that builds one) MUST be
  injected. If neither is supplied, or the factory raises, construction fails with
  :class:`ConsensusArmUnavailable`.
* An in-process transport (a callable matching
  :func:`synapse_common.a2a_sdk.send_a2a_request`) MUST be injected. If it is
  missing, construction fails with :class:`ConsensusArmUnavailable`.
* If ``run_consensus`` raises for a scenario, the exception propagates — the harness
  records that ``(arm, seed)`` as a **failed run** (R2.7), excludes it from
  aggregation, and continues. The arm NEVER fabricates a consensus decision.
* If consensus completes but reached no agent (zero proposals), that is treated as an
  unavailable in-process network and surfaced as :class:`ConsensusArmUnavailable`
  — again a failed run, never a fabricated no-op passed off as a real decision.

The adapter implements the arm-agnostic :class:`~uplift.interfaces.DecisionPolicy`
protocol (``name`` + ``decide``): it maps each :class:`~uplift.interfaces.Observation`
to a ``decision_request`` dict, runs ``run_consensus`` on a per-scenario event loop,
and translates the binding :class:`~synapse_common.models.ConsensusDecision` action
into a :class:`~uplift.interfaces.PolicyAction` applied back into the twin.
"""
from __future__ import annotations

import asyncio
import dataclasses
import inspect
from typing import TYPE_CHECKING, Any, Awaitable, Callable, Mapping
from uuid import uuid4

from synapse_common.a2a_sdk import A2AResponse

from uplift.interfaces import (
    Observation,
    PolicyAction,
    RoutingAssignment,
)

if TYPE_CHECKING:  # imported lazily at runtime to avoid a heavy import at module load
    from synapse_common.models import ConsensusDecision
    from orchestrator.consensus.protocol import ConsensusProtocol


# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------
#: An in-process A2A handler: the agent/twin ``handle_request`` callable that maps a
#: JSON-RPC request dict to a JSON-RPC response dict. May be sync or async.
A2AHandler = Callable[[dict[str, Any]], "dict[str, Any] | Awaitable[dict[str, Any]]"]

#: An in-process transport callable matching :func:`send_a2a_request`'s keyword call
#: surface (``target_url``, ``method``, ``params`` plus optional ``timeout``/``tier``).
Transport = Callable[..., Awaitable[A2AResponse]]

#: Builds the orchestrator ``decision_request`` dict from a twin observation.
RequestBuilder = Callable[[Observation], "dict[str, Any]"]

#: Translates a binding consensus decision (+ the observation) into a PolicyAction.
ActionTranslator = Callable[["ConsensusDecision", Observation], PolicyAction]


class ConsensusArmUnavailable(RuntimeError):
    """The consensus arm could not be constructed or reached for a scenario.

    Raised on construction failure (missing protocol / transport, or a raising
    factory) and when consensus completes without reaching any agent. The harness
    treats this as a **failed run** (R2.7) — it is never swallowed into a fabricated
    decision.
    """


# ---------------------------------------------------------------------------
# In-process A2A transport
# ---------------------------------------------------------------------------
class InProcessA2ATransport:
    """Dispatch A2A JSON-RPC calls to in-process handler functions (no HTTP).

    ``handlers`` maps a target base URL (the same URLs the protocol dials, e.g.
    ``http://pricing-oracle:8005``) to that agent's / the twin's ``handle_request``
    callable. On a call, the transport reconstructs the JSON-RPC request dict the
    HTTP servers would have received, invokes the handler in-process (awaiting it if
    it is a coroutine), and wraps the reply in an :class:`A2AResponse`.

    A call to a URL with no registered handler returns an *error* response (not an
    exception): this mirrors an unreachable agent so the protocol's per-agent
    ``return_exceptions`` fan-out and the Tier-4 twin-verify degrade honestly (I-7)
    exactly as they would against a down HTTP peer. Whole-arm unavailability is
    handled up front by :class:`ConsensusArm` construction, not here.
    """

    def __init__(self, handlers: Mapping[str, A2AHandler]) -> None:
        self._handlers: dict[str, A2AHandler] = dict(handlers)

    @classmethod
    def from_agents(
        cls,
        agent_handlers: Mapping[str, A2AHandler],
        *,
        twin_handler: A2AHandler | None = None,
    ) -> "InProcessA2ATransport":
        """Build a transport from ``agent_name -> handler`` (and an optional twin).

        Agent names are resolved to their canonical A2A URLs via the protocol's
        ``AGENT_ENDPOINTS`` map; the twin handler (if given) is registered on
        ``TWIN_ENDPOINT``. Unknown agent names raise :class:`ConsensusArmUnavailable`
        so a typo fails loudly instead of silently dropping an agent.
        """
        from orchestrator.consensus.protocol import AGENT_ENDPOINTS, TWIN_ENDPOINT

        resolved: dict[str, A2AHandler] = {}
        for name, handler in agent_handlers.items():
            url = AGENT_ENDPOINTS.get(name)
            if url is None:
                raise ConsensusArmUnavailable(
                    f"unknown agent name for in-process transport: {name!r}"
                )
            resolved[url] = handler
        if twin_handler is not None:
            resolved[TWIN_ENDPOINT] = twin_handler
        return cls(resolved)

    async def __call__(
        self,
        target_url: str,
        method: str,
        params: dict[str, Any],
        timeout: float | None = None,
        tier: Any = None,
        max_retries: int = 2,
        **_: Any,
    ) -> A2AResponse:
        request_id = str(uuid4())
        handler = self._handlers.get(target_url)
        if handler is None:
            return A2AResponse(
                id=request_id,
                error={"code": -32004, "message": f"no in-process handler for {target_url}"},
            )
        request = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
            "id": request_id,
        }
        raw = handler(request)
        if inspect.isawaitable(raw):
            raw = await raw
        return A2AResponse.model_validate(raw)


# ---------------------------------------------------------------------------
# Observation -> decision_request
# ---------------------------------------------------------------------------
def observation_to_decision_request(obs: Observation) -> dict[str, Any]:
    """Map a twin :class:`Observation` to an orchestrator ``decision_request`` dict.

    The keys mirror what :meth:`TierRouter.classify` reads (``disruption_active`` /
    ``requires_twin_simulation`` drive the tier) and what the agents' ``proposal``
    handlers consume (``sku_ids`` / ``inventory`` / ``unit_costs``). An active shock
    routes the decision to Tier 4 so the real twin-verification phase engages. All
    values are plain JSON-safe primitives so the request round-trips through the
    protocol's canonical-JSON audit path unchanged.
    """
    shocked = obs.active_shock is not None
    request: dict[str, Any] = {
        "sku_ids": list(obs.inventory.keys()),
        "inventory": {sku: int(level) for sku, level in obs.inventory.items()},
        "unit_costs": {sku: float(cost) for sku, cost in obs.unit_costs.items()},
        "sim_time": float(obs.sim_time),
        "delivery_count": int(obs.delivery_count),
        "spoilage_count": int(obs.spoilage_count),
        "stockout_count": int(obs.stockout_count),
        "disruption_active": shocked,
        "requires_twin_simulation": shocked,
    }
    if obs.active_shock is not None:
        request["shock"] = {
            key: float(val)
            for key, val in dataclasses.asdict(obs.active_shock).items()
        }
    if obs.pending_order is not None:
        request["pending_order"] = {
            "order_id": obs.pending_order.order_id,
            "destination": list(obs.pending_order.destination),
        }
        request["eligible_stores"] = [
            {"store_id": store.store_id, "location": list(store.location)}
            for store in obs.eligible_stores
        ]
    return request


# ---------------------------------------------------------------------------
# ConsensusDecision -> PolicyAction
# ---------------------------------------------------------------------------
_PRICE_KEYS = ("price", "new_price", "recommended_price", "unit_price")
_REORDER_MAP_KEYS = ("reorder_quantities", "order_quantities", "reorder", "quantities")
_STORE_KEYS = ("store_id", "assigned_store", "selected_store")
_DISRUPTION_KEYS = ("disruption_actions", "actions", "mitigations")


def _coerce_price(payload: Mapping[str, Any]) -> float | None:
    for key in _PRICE_KEYS:
        value = payload.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return float(value)
    return None


def _coerce_reorder_quantities(payload: Mapping[str, Any]) -> dict[str, float]:
    for key in _REORDER_MAP_KEYS:
        value = payload.get(key)
        if isinstance(value, Mapping):
            out: dict[str, float] = {}
            for sku, qty in value.items():
                if isinstance(qty, (int, float)) and not isinstance(qty, bool):
                    out[str(sku)] = float(qty)
            if out:
                return out
    # Single (sku_id, quantity) shape used by InventoryAction-style payloads.
    sku = payload.get("sku_id")
    qty = payload.get("quantity", payload.get("reorder_qty"))
    if isinstance(sku, str) and isinstance(qty, (int, float)) and not isinstance(qty, bool):
        return {sku: float(qty)}
    return {}


def _coerce_disruption_actions(payload: Mapping[str, Any]) -> frozenset[str]:
    for key in _DISRUPTION_KEYS:
        value = payload.get(key)
        if isinstance(value, (list, tuple, set, frozenset)):
            return frozenset(str(item) for item in value)
        if isinstance(value, str) and value:
            return frozenset({value})
    return frozenset()


def _coerce_routing(payload: Mapping[str, Any], obs: Observation) -> RoutingAssignment | None:
    if obs.pending_order is None:
        return None
    for key in _STORE_KEYS:
        value = payload.get(key)
        if isinstance(value, bool):
            continue
        if isinstance(value, int):
            return RoutingAssignment(order_id=obs.pending_order.order_id, store_id=value)
        if isinstance(value, str) and value.isdigit():
            return RoutingAssignment(order_id=obs.pending_order.order_id, store_id=int(value))
    return None


def consensus_decision_to_policy_action(
    decision: "ConsensusDecision",
    obs: Observation,
) -> PolicyAction:
    """Translate a binding :class:`ConsensusDecision` into a :class:`PolicyAction`.

    The decision's ``selected_action`` is the binding (Pareto-knee-selected) agent's
    payload. This best-effort translator extracts whichever twin actuation levers the
    binding action expresses — reorder quantities, a price, a routing assignment, and
    a disruption action set — leaving unset levers at their neutral defaults (a
    :class:`PolicyAction` MAY be partial). It only ever *translates* a real decision;
    it never fabricates one.
    """
    payload = decision.selected_action if isinstance(decision.selected_action, Mapping) else {}
    return PolicyAction(
        reorder_quantities=_coerce_reorder_quantities(payload),
        price=_coerce_price(payload),
        routing_assignment=_coerce_routing(payload, obs),
        disruption_actions=_coerce_disruption_actions(payload),
    )


# ---------------------------------------------------------------------------
# The consensus arm
# ---------------------------------------------------------------------------
class ConsensusArm:
    """In-process adapter exposing SYNAPSE consensus as a :class:`DecisionPolicy`.

    Construct with an injected :class:`ConsensusProtocol` (or ``protocol_factory``)
    and an in-process ``transport``. ``decide`` maps the observation to a
    ``decision_request``, runs the real ``run_consensus`` on a fresh per-scenario
    event loop with the in-process transport installed, and translates the binding
    decision into a :class:`PolicyAction`.
    """

    def __init__(
        self,
        *,
        protocol: "ConsensusProtocol | None" = None,
        protocol_factory: "Callable[[], ConsensusProtocol] | None" = None,
        transport: Transport | None = None,
        request_builder: RequestBuilder = observation_to_decision_request,
        action_translator: ActionTranslator = consensus_decision_to_policy_action,
        name: str = "consensus",
    ) -> None:
        if transport is None:
            raise ConsensusArmUnavailable(
                "ConsensusArm requires an in-process A2A transport; none was injected"
            )
        resolved = self._resolve_protocol(protocol, protocol_factory)
        if not hasattr(resolved, "run_consensus"):
            raise ConsensusArmUnavailable(
                "injected consensus protocol does not expose run_consensus"
            )
        self.name = name
        self._protocol = resolved
        self._transport = transport
        self._build_request = request_builder
        self._translate = action_translator

    @staticmethod
    def _resolve_protocol(
        protocol: "ConsensusProtocol | None",
        protocol_factory: "Callable[[], ConsensusProtocol] | None",
    ) -> "ConsensusProtocol":
        if protocol is not None:
            return protocol
        if protocol_factory is None:
            raise ConsensusArmUnavailable(
                "ConsensusArm requires a protocol or protocol_factory; neither was injected"
            )
        try:
            built = protocol_factory()
        except Exception as exc:  # construction failure surfaces as a failed run
            raise ConsensusArmUnavailable(
                f"consensus protocol construction failed: {exc}"
            ) from exc
        if built is None:
            raise ConsensusArmUnavailable("protocol_factory returned None")
        return built

    def decide(self, obs: Observation) -> PolicyAction:
        """Run real consensus for ``obs`` and return the binding decision's action.

        On any failure to reach a decision — ``run_consensus`` raising, or consensus
        completing without reaching a single agent — the failure is surfaced (raised),
        so the harness records the run as failed (R2.7) and never applies a fabricated
        consensus decision.
        """
        decision_request = self._build_request(obs)
        decision = self._run_consensus(decision_request)
        if not decision.proposals:
            # No agent could be reached in-process: honest failure, not a no-op.
            raise ConsensusArmUnavailable(
                "consensus completed without any agent proposals; "
                "in-process agent network unavailable"
            )
        return self._translate(decision, obs)

    def _run_consensus(self, decision_request: dict[str, Any]) -> "ConsensusDecision":
        """Run ``run_consensus`` on a fresh event loop with the transport installed.

        The protocol dials the module-level ``send_a2a_request``; installing the
        in-process transport means temporarily binding that symbol to the injected
        transport for the duration of the run and restoring it afterwards. A brand-new
        event loop is created per scenario step and always closed, so the harness's
        process-pool workers never leak or reuse a loop.
        """
        from orchestrator.consensus import protocol as protocol_mod

        original_transport = protocol_mod.send_a2a_request
        protocol_mod.send_a2a_request = self._transport  # type: ignore[assignment]
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(
                self._protocol.run_consensus(decision_request)
            )
        finally:
            protocol_mod.send_a2a_request = original_transport  # type: ignore[assignment]
            asyncio.set_event_loop(None)
            loop.close()


__all__ = [
    "A2AHandler",
    "ActionTranslator",
    "ConsensusArm",
    "ConsensusArmUnavailable",
    "InProcessA2ATransport",
    "RequestBuilder",
    "Transport",
    "consensus_decision_to_policy_action",
    "observation_to_decision_request",
]
