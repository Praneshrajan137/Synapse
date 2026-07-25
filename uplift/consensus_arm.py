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

:func:`build_consensus_arm` is the assembly seam that actually stands that network up:
it builds the eight real agent ``handle_request`` handlers plus the twin's A2A handler,
wraps them in an :class:`InProcessA2ATransport`, constructs a real
:class:`ConsensusProtocol` from its real collaborators, and returns a ready
:class:`ConsensusArm`. Standing up the full eight-agent + twin network in-process may not
be feasible in every environment, so — per the design's error-handling contract — the
adapter is built on **dependency injection** and **fails loudly** rather than fabricating
a decision:

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

from uplift.harness import DEFAULT_CONSENSUS_ARM
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


# ---------------------------------------------------------------------------
# Assembly — build the real in-process consensus arm (R1.1, R1.2, R1.6)
# ---------------------------------------------------------------------------
#: ``(agent name, module, handler class)`` for the eight real agent A2A handlers. The
#: names are exactly the :data:`AGENT_ENDPOINTS` keys the protocol dials, so the
#: assembled transport covers the full fan-out with no endpoint left unregistered.
_AGENT_HANDLER_SPECS: tuple[tuple[str, str, str], ...] = (
    ("demand_prophet", "agents.demand_prophet.a2a.handler", "DemandProphetA2AHandler"),
    ("routing_navigator", "agents.routing_navigator.a2a.handler", "RoutingNavigatorA2AHandler"),
    ("inventory_sentinel", "agents.inventory_sentinel.a2a.handler", "InventorySentinelA2AHandler"),
    ("freshness_guardian", "agents.freshness_guardian.a2a.handler", "FreshnessGuardianA2AHandler"),
    ("pricing_oracle", "agents.pricing_oracle.a2a.handler", "PricingOracleA2AHandler"),
    ("disruption_shield", "agents.disruption_shield.a2a.handler", "DisruptionShieldA2AHandler"),
    ("supplier_trust", "agents.supplier_trust.a2a.handler", "SupplierTrustA2AHandler"),
    (
        "sustainability_agent",
        "agents.sustainability_agent.a2a.handler",
        "SustainabilityAgentA2AHandler",
    ),
)


class _OfflineActuator:
    """Honest no-world actuator for the network-free arm (I-1, I-7).

    An agent's ``execute()`` normally POSTs ``apply_action`` to the twin's standing
    world over HTTP. The uplift harness *is* the world here (it applies the returned
    :class:`PolicyAction` to its own seeded twin), and the run must open no socket, so
    every actuation reports honestly that no world effect was applied. Nothing is
    fabricated: the shared honesty rule in ``synapse_common.world.actuation`` reads
    ``applied=False`` and returns a truthful ``"diverged"`` status.
    """

    reason = "world actuation unavailable: in-process uplift arm is network-free ($0)"

    def apply(self, action: Any) -> dict[str, Any]:  # noqa: ARG002 — always unavailable
        return {"applied": False, "error": self.reason}


class _OfflineLLMClient:
    """Honest no-LLM client for the network-free arm (I-1, I-7).

    The debate phase's LLM analysis is best-effort: the protocol bounds each attempt
    and records ``debate_llm_unavailable`` when it fails, continuing with the
    LLM-independent rule-based concession round. Raising here keeps that degradation
    honest (no fabricated analysis) while guaranteeing no Ollama socket is opened.
    """

    reason = "no local LLM in the network-free in-process consensus arm ($0)"

    async def chat(self, **_: Any) -> dict[str, Any]:
        raise RuntimeError(self.reason)

    async def warm_model(self, *_: Any, **__: Any) -> None:
        return None

    async def close(self) -> None:
        return None


#: HITL wait budget for the *unattended* uplift run, in seconds. Confidence-gated
#: escalation stays fully intact (I-5): a guardrail-violating decision still escalates,
#: still records ``escalated_to_human`` and the honest timeout override, and is still
#: deferred rather than executed. Only the wait is shortened — nobody is attached to a
#: harness run, so the production 300s operator window would just stall it.
_UNATTENDED_HITL_TIMEOUT_S: float = 1.0


class _InProcessAuditSession:
    """An ``AsyncSession``-shaped, append-only in-process sink for audit rows (I-4).

    The real :class:`~orchestrator.audit.logger.AuditLogger` is reused unchanged — it
    still builds the canonical row, walks the ``prev_hash → current_hash`` chain, and
    enqueues the outbox row in the same "transaction". Only the *destination* degrades
    honestly: a ``$0``, network-free run has no PostgreSQL, so rows are appended to an
    in-process list instead of being persisted. Rows are never dropped silently and
    never mutated (append-only), and nothing about the decision is fabricated.
    """

    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows

    async def execute(self, _stmt: Any) -> Any:
        # Chain-head lookup on cold start: no persisted history in-process, so the
        # logger starts the chain at its GENESIS hash and caches the head thereafter.
        class _Empty:
            @staticmethod
            def scalar_one_or_none() -> None:
                return None

        return _Empty()

    def add(self, row: Any) -> None:
        if getattr(row, "id", None) is None:
            row.id = uuid4()
        self._rows.append(row)

    async def flush(self) -> None:
        return None

    async def commit(self) -> None:
        return None

    async def rollback(self) -> None:
        return None

    async def __aenter__(self) -> _InProcessAuditSession:
        return self

    async def __aexit__(self, *_: Any) -> None:
        return None


def _in_process_session_factory() -> Callable[[], _InProcessAuditSession]:
    """Return an ``async_sessionmaker``-shaped factory over one append-only row list."""
    rows: list[Any] = []

    def factory() -> _InProcessAuditSession:
        return _InProcessAuditSession(rows)

    factory.rows = rows  # type: ignore[attr-defined]
    return factory


def _supports_kwarg(func: Any, name: str) -> bool:
    """True when ``func`` accepts a keyword argument called ``name``."""
    try:
        return name in inspect.signature(func).parameters
    except (TypeError, ValueError):  # pragma: no cover — builtins without signatures
        return False


def build_agent_handlers() -> dict[str, A2AHandler]:
    """Build the eight real agent ``handle_request`` handlers keyed by agent name (R1.1).

    Each agent's existing ``*A2AHandler`` class is constructed with its default
    pipeline (which degrades honestly to a fallback when no trained model is published,
    I-7), no Kafka producer, and — where the handler supports actuation — the
    :class:`_OfflineActuator`, so nothing dials the network. The returned mapping's keys
    are exactly the :data:`AGENT_ENDPOINTS` names.

    Raises:
        ConsensusArmUnavailable: if any agent handler cannot be imported or constructed
            in this environment — the arm is never silently assembled short of the full
            eight-agent network.
    """
    import importlib

    handlers: dict[str, A2AHandler] = {}
    for name, module_path, class_name in _AGENT_HANDLER_SPECS:
        try:
            module = importlib.import_module(module_path)
            handler_cls = getattr(module, class_name)
            kwargs: dict[str, Any] = {"kafka_producer": None}
            if _supports_kwarg(handler_cls.__init__, "actuator"):
                kwargs["actuator"] = _OfflineActuator()
            handler = handler_cls(**kwargs)
        except Exception as exc:  # noqa: BLE001 — assembly failure is loud, never a stub
            raise ConsensusArmUnavailable(
                f"cannot assemble in-process agent handler for {name!r}: "
                f"{type(exc).__name__}: {exc}"
            ) from exc
        handlers[name] = handler.handle_request
    return handlers


def build_twin_handler() -> A2AHandler:
    """Build the twin's in-process A2A handler so Tier-4 twin-verify engages (R1.1).

    Reuses the twin's own A2A dispatch (:func:`digital_twin.inference.serve.a2a_handler`
    — the same ``monte_carlo`` / ``simulate`` logic the HTTP server wraps) by adapting
    the JSON-RPC dict envelope to the twin's :class:`A2ARequest` / :class:`A2AResponse`
    models. No twin logic is forked and no socket is opened.

    Cost note (INV-TW-002): the twin honours the invariant that a Monte-Carlo query runs
    at least :data:`MIN_SCENARIOS` (1000) scenarios, and the protocol asks for
    ``SYNAPSE_TWIN_SCENARIOS`` (default 1000) of them per Tier-4 decision — measured at
    roughly 20s per shocked (Tier-4) decision on a laptop CPU. A request below the floor
    is refused by the twin, which the protocol records as an honest ``twin_unavailable``
    verdict rather than a cheapened "verification"; a caller that needs a cheaper run
    injects its own ``twin_handler`` through :func:`build_consensus_arm` instead.

    Raises:
        ConsensusArmUnavailable: if the twin's A2A dispatch cannot be imported here.
    """
    try:
        from synapse_common.a2a_sdk import A2ARequest

        from digital_twin.inference import serve as twin_serve

        twin_dispatch = twin_serve.a2a_handler
    except Exception as exc:  # noqa: BLE001 — assembly failure is loud, never a stub
        raise ConsensusArmUnavailable(
            f"cannot assemble in-process twin handler: {type(exc).__name__}: {exc}"
        ) from exc

    async def handler(request: dict[str, Any]) -> dict[str, Any]:
        a2a_request = A2ARequest(
            method=str(request.get("method", "")),
            params=request.get("params") or {},
            id=str(request.get("id") or uuid4()),
        )
        response = await twin_dispatch(a2a_request)
        payload: dict[str, Any] = response.model_dump(mode="json")
        return payload

    return handler


def build_consensus_protocol() -> ConsensusProtocol:
    """Construct a real :class:`ConsensusProtocol` for the in-process arm (R1.6, R9.8).

    Every collaborator is the real module, unchanged: the real :class:`TierRouter`
    (tier classification), :class:`GuardrailEngine`, :class:`AuditLogger` (hash-chained,
    append-only), :class:`HITLEscalation` (confidence-gated escalation, I-5),
    :class:`ContextBuilder` (append-only context, I-14), :class:`MetaRLAgent`, and
    :class:`SemanticDecisionCache`. No decision logic is forked.

    Collaborators that would require an external or paid service degrade honestly
    (I-1, I-7) instead of dialing out: audit rows land in an in-process append-only
    sink, the LLM client reports unavailability so debate degrades to its rule-based
    concession round, the semantic cache is constructed without a Pinecone key (so it
    reports itself unavailable), and there is no Kafka producer and no world observer.
    Escalation keeps its real confidence gate; only its operator wait is shortened to
    :data:`_UNATTENDED_HITL_TIMEOUT_S` because a harness run is unattended.

    Raises:
        ConsensusArmUnavailable: if the protocol cannot be constructed here.
    """
    try:
        from orchestrator.audit.logger import AuditLogger
        from orchestrator.config import OrchestratorConfig
        from orchestrator.consensus.protocol import ConsensusProtocol
        from orchestrator.consensus.tier_router import TierRouter
        from orchestrator.guardrails.rules import GuardrailEngine
        from orchestrator.hitl.escalation import HITLEscalation, WebSocketManager
        from orchestrator.llm.context_builder import ContextBuilder
        from orchestrator.llm.semantic_cache import SemanticDecisionCache
        from orchestrator.meta_rl.meta_agent import MetaRLAgent

        config = OrchestratorConfig()
        return ConsensusProtocol(
            config=config,
            tier_router=TierRouter(),
            guardrails=GuardrailEngine(confidence_threshold=config.confidence_threshold),
            audit_logger=AuditLogger(_in_process_session_factory()),  # type: ignore[arg-type]
            hitl_escalation=HITLEscalation(
                kafka_producer=None,
                ws_manager=WebSocketManager(),
                timeout_seconds=_UNATTENDED_HITL_TIMEOUT_S,
                timeout_action=config.hitl_timeout_action,
            ),
            context_builder=ContextBuilder(),
            ollama_client=_OfflineLLMClient(),  # type: ignore[arg-type]
            meta_rl=MetaRLAgent(
                lr=config.meta_rl_learning_rate,
                history_size=config.meta_rl_history_size,
            ),
            # No Pinecone key ⇒ the cache reports itself unavailable (no paid service).
            semantic_cache=SemanticDecisionCache(api_key=None),
            kafka_producer=None,
            world_observer=None,
        )
    except Exception as exc:  # noqa: BLE001 — assembly failure is loud, never a stub
        raise ConsensusArmUnavailable(
            f"cannot assemble in-process consensus protocol: {type(exc).__name__}: {exc}"
        ) from exc


def build_consensus_arm(
    *,
    name: str = DEFAULT_CONSENSUS_ARM,
    agent_handlers: Mapping[str, A2AHandler] | None = None,
    twin_handler: A2AHandler | None = None,
    protocol: "ConsensusProtocol | None" = None,
) -> ConsensusArm:
    """Assemble a real in-process consensus arm (R1.1, R1.2, R1.6).

    Builds (or accepts injected) the eight agent ``handle_request`` handlers keyed by
    :data:`AGENT_ENDPOINTS` and the twin ``handle_request`` handler, wraps them in an
    :meth:`InProcessA2ATransport.from_agents` transport, constructs a real
    :class:`ConsensusProtocol` (reusing the real tier router, guardrails, audit logger,
    HITL escalation, context builder, meta-RL and semantic cache unchanged), and returns
    a ready :class:`ConsensusArm` — a :class:`~uplift.interfaces.DecisionPolicy` whose
    every decision runs SYNAPSE's real four-tier consensus with no socket opened and no
    external paid service (I-1).

    Args:
        name: the arm name result assembly identifies the consensus arm by.
        agent_handlers: ``agent name -> handle_request`` override; defaults to the eight
            real agent handlers (:func:`build_agent_handlers`).
        twin_handler: twin ``handle_request`` override; defaults to the real twin A2A
            dispatch (:func:`build_twin_handler`).
        protocol: an already-configured protocol; defaults to
            :func:`build_consensus_protocol`.

    Returns:
        A :class:`ConsensusArm` wired to the in-process network.

    Raises:
        ConsensusArmUnavailable: if the agent/twin network or the protocol cannot be
            assembled in this environment (R1.5). The caller records the affected runs
            as failed runs; no stub arm is fabricated and no decision is invented.
    """
    handlers = dict(agent_handlers) if agent_handlers is not None else build_agent_handlers()
    if not handlers:
        raise ConsensusArmUnavailable(
            "no in-process agent handlers were assembled; the consensus network is "
            "unavailable in this environment"
        )
    twin = twin_handler if twin_handler is not None else build_twin_handler()
    transport = InProcessA2ATransport.from_agents(handlers, twin_handler=twin)
    resolved_protocol = protocol if protocol is not None else build_consensus_protocol()
    return ConsensusArm(protocol=resolved_protocol, transport=transport, name=name)


__all__ = [
    "A2AHandler",
    "ActionTranslator",
    "ConsensusArm",
    "ConsensusArmUnavailable",
    "DEFAULT_CONSENSUS_ARM",
    "InProcessA2ATransport",
    "RequestBuilder",
    "Transport",
    "build_agent_handlers",
    "build_consensus_arm",
    "build_consensus_protocol",
    "build_twin_handler",
    "consensus_decision_to_policy_action",
    "observation_to_decision_request",
]
