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

**decision-quality-proof task 29.6 (R7.20, R7.21, finding 68).** Every change is in this arm;
no agent is touched (decision 3=a).

* The request forwards what a planner knows and the world rewards -- on-order stock, inventory
  position, demand to date, supplier lead-time history, the SKU-to-supplier map and the start
  weekday -- every mapping in sorted key order (I-13). It used to be an on-hand snapshot.
* :func:`classify_dispatch` puts each decision in exactly one of four buckets, by the precedence
  blocked > untranslatable > withheld > dispatched. A recommendation withheld for confidence
  alone is applied (decision Q2=a); one a hard guardrail, the Tier-4 twin, or an unreadable
  record withheld is not, because I-6 outranks Q2=a and an ambiguity is never resolved toward
  applying.
* :class:`ConsensusArm` is run-scoped (:class:`~uplift.interfaces.RunScoped`): ``begin_run``
  opens a tally and ``end_run`` returns the run's :class:`~uplift.interfaces.DecisionCounts`.
* ``levers`` names what a suite applies. A binding action expressing a lever outside it is
  untranslatable and applies nothing: executing part of a recommendation is not executing it.
  So is a reorder for a SKU the observed twin does not stock (finding 112: every agent reads its
  request one level too shallow, so the Inventory Sentinel orders its default ``SKU001``).
"""

from __future__ import annotations

import asyncio
import copy
import dataclasses
import inspect
import math
from typing import TYPE_CHECKING, Any, Awaitable, Callable, Final, Literal, Mapping
from uuid import uuid4

from synapse_common.a2a_sdk import A2AResponse

from uplift.harness import DEFAULT_CONSENSUS_ARM
from uplift.interfaces import (
    DecisionCounts,
    Observation,
    PolicyAction,
    RoutingAssignment,
)

if TYPE_CHECKING:  # imported lazily at runtime to avoid a heavy import at module load
    from synapse_common.models import ConsensusDecision

    from agents.disruption_shield.models.reasoning import DeepSeekReasoner
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

#: Every lever a :class:`~uplift.interfaces.PolicyAction` can carry, by the name a suite's lever
#: set uses (task 29.6). :func:`build_consensus_arm`'s default, so an arm built without naming a
#: lever set translates exactly what it translated before the set existed.
ALL_LEVERS: Final[frozenset[str]] = frozenset({"reorder", "price", "routing", "disruption"})

#: The bucket one decision lands in (R7.20). The names are
#: :class:`~uplift.interfaces.DecisionCounts`'s fields, so a tally converts field for field.
DispatchBucket = Literal[
    "dispatched", "withheld_for_confidence", "guardrail_blocked", "untranslatable"
]

#: Every :data:`DispatchBucket`, in :class:`~uplift.interfaces.DecisionCounts` field order.
DISPATCH_BUCKETS: Final[tuple[DispatchBucket, ...]] = (
    "dispatched",
    "withheld_for_confidence",
    "guardrail_blocked",
    "untranslatable",
)

#: The buckets whose binding recommendation reaches the twin. Q2=a adds the second; I-6 keeps
#: ``guardrail_blocked`` out of it whatever Q2 says.
_APPLIED_BUCKETS: Final[frozenset[str]] = frozenset({"dispatched", "withheld_for_confidence"})

# The protocol's own audit vocabulary, restated because the protocol exports no constant for it.
# `ConsensusProtocol._record_withheld_dispatch` is the protocol's ONLY withhold path and stamps
# the first three into `audit_trace` (orchestrator/consensus/protocol.py:962-964); `_phase_execute`
# is its only dispatch path and fills `execution_confirmations`, one entry per proposal.
_WITHHELD_MARKER: Final[str] = "dispatch=withheld"
_WITHHELD_BY_PREFIX: Final[str] = "withheld_by="
_GUARDRAIL_WITHHOLD: Final[str] = "guardrail_violation"
_TWIN_WITHHOLD: Final[str] = "twin_disagreement"
_BINDING_SELECTED_PREFIX: Final[str] = "binding_selected="
#: The context record `_ratify_and_dispatch` appends BEFORE it withholds or dispatches
#: (protocol.py:869-887): `passed`, `violations`, `twin_veto`.
_RATIFICATION_RECORD: Final[str] = "dispatch_ratification"
#: Both confidence-floor violation strings begin with this: the engine's
#: (orchestrator/guardrails/rules.py:462) and the protocol's pre-flight (protocol.py:848). A
#: reworded message reads as "not the confidence floor", which fails toward NOT applying -- the
#: direction I-6 requires.
_CONFIDENCE_VIOLATION_PREFIX: Final[str] = "Confidence "
#: A clip is the one violation that still passes (`validate_decision`'s own rule, rules.py:381).
_CLIP_MARKER: Final[str] = "clipped"


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

    **What the world rewards (task 29.6, R7.21, finding 68).** The request used to be an on-hand
    snapshot: no stock in transit, no demand history, no supplier history. It now forwards all
    five of the observation's task-13.1 fields -- ``on_order``, ``demand_to_date``,
    ``supplier_lead_time_history``, ``sku_supplier``, ``start_weekday`` -- and
    ``inventory_position``, which is ``on hand + on order`` per stocked SKU: the expression
    ``tuned_static.py``, ``baselines/par_level_reorder.py`` and ``oracle_arm.py`` already use, a
    SKU absent from ``on_order`` having nothing in transit. Every mapping is built in sorted key
    order and ``sku_ids`` is sorted, so equal observations give byte-identical requests however
    their mappings were assembled (I-13). ``start_weekday`` is ``None`` when demand has no weekly
    shape: forwarded as unknown, never defaulted to a day. Whether an agent READS these keys is
    the agents' business (decision 3=a); the pathway probe measures it (R7.21).
    """
    shocked = obs.active_shock is not None
    skus = sorted(obs.inventory)
    request: dict[str, Any] = {
        "sku_ids": skus,
        "inventory": {sku: int(obs.inventory[sku]) for sku in skus},
        "unit_costs": {sku: float(obs.unit_costs[sku]) for sku in sorted(obs.unit_costs)},
        "sim_time": float(obs.sim_time),
        "delivery_count": int(obs.delivery_count),
        "spoilage_count": int(obs.spoilage_count),
        "stockout_count": int(obs.stockout_count),
        "disruption_active": shocked,
        "requires_twin_simulation": shocked,
        "on_order": {sku: float(obs.on_order[sku]) for sku in sorted(obs.on_order)},
        "inventory_position": {
            sku: float(obs.inventory[sku]) + float(obs.on_order.get(sku, 0.0)) for sku in skus
        },
        "demand_to_date": {sku: int(obs.demand_to_date[sku]) for sku in sorted(obs.demand_to_date)},
        "supplier_lead_time_history": {
            supplier: [float(minutes) for minutes in obs.supplier_lead_time_history[supplier]]
            for supplier in sorted(obs.supplier_lead_time_history)
        },
        "sku_supplier": {sku: str(obs.sku_supplier[sku]) for sku in sorted(obs.sku_supplier)},
        "start_weekday": None if obs.start_weekday is None else int(obs.start_weekday),
    }
    if obs.active_shock is not None:
        request["shock"] = {
            key: float(val) for key, val in sorted(dataclasses.asdict(obs.active_shock).items())
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

#: The Inventory Sentinel proposes ``{"actions": [InventoryAction, ...]}``, and its own
#: ``execute`` enacts exactly the entries whose ``action_type`` is ``"reorder"``
#: (``agents/inventory_sentinel/a2a/handler.py::execute``), so those are what translate.
_ACTION_LIST_KEY: Final[str] = "actions"
_REORDER_ACTION_TYPE: Final[str] = "reorder"


def _coerce_price(payload: Mapping[str, Any]) -> float | None:
    for key in _PRICE_KEYS:
        value = payload.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return float(value)
    return None


def _coerce_reorder_actions(value: Any) -> dict[str, float]:
    """Per-SKU reorder quantities from an ``actions`` list, as the agent's own execute reads it.

    Task 29.6. Before this, the list reached :func:`_coerce_disruption_actions` instead, which
    stringified each reorder into a "disruption action" the harness never actuates -- so a
    binding Inventory Sentinel reorder applied nothing. Entries for one SKU add, because the
    agent enacts each one. A zero quantity is kept: "reorder nothing" is a recommendation and
    keeps the lever expressed, and :func:`uplift.harness._apply_reorders` places no zero order.
    Markdown and transfer entries, negative and non-finite quantities, are what the agent does
    not enact either, so they translate to nothing.
    """
    if not isinstance(value, (list, tuple)):
        return {}
    out: dict[str, float] = {}
    for item in value:
        if not isinstance(item, Mapping) or item.get("action_type") != _REORDER_ACTION_TYPE:
            continue
        sku = item.get("sku_id")
        qty = item.get("quantity")
        if not isinstance(sku, str) or not sku:
            continue
        if isinstance(qty, bool) or not isinstance(qty, (int, float)):
            continue
        quantity = float(qty)
        if not math.isfinite(quantity) or quantity < 0.0:
            continue
        out[sku] = out.get(sku, 0.0) + quantity
    return out


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
    listed = _coerce_reorder_actions(payload.get(_ACTION_LIST_KEY))
    if listed:
        return listed
    # Single (sku_id, quantity) shape used by InventoryAction-style payloads.
    sku = payload.get("sku_id")
    qty = payload.get("quantity", payload.get("reorder_qty"))
    if isinstance(sku, str) and isinstance(qty, (int, float)) and not isinstance(qty, bool):
        return {sku: float(qty)}
    return {}


def _coerce_disruption_actions(payload: Mapping[str, Any]) -> frozenset[str]:
    """Named disruption actions. A name is a non-empty string; a dict is not a name.

    Task 29.6: the stringified-dict reading (``str(item)`` over any list) turned the Inventory
    Sentinel's reorder list into disruption actions, so a key whose list holds no name now
    yields nothing and the next key is read.
    """
    for key in _DISRUPTION_KEYS:
        value = payload.get(key)
        if isinstance(value, (list, tuple, set, frozenset)):
            names = frozenset(item for item in value if isinstance(item, str) and item)
            if names:
                return names
            continue
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


def expressed_levers(action: PolicyAction) -> frozenset[str]:
    """The levers ``action`` sets, by :data:`ALL_LEVERS` name; a neutral lever is not expressed.

    A reorder map whose quantities are all zero IS expressed: it says "order nothing", which is
    a recommendation, not the absence of one.
    """
    named: set[str] = set()
    if action.reorder_quantities:
        named.add("reorder")
    if action.price is not None:
        named.add("price")
    if action.routing_assignment is not None:
        named.add("routing")
    if action.disruption_actions:
        named.add("disruption")
    return frozenset(named)


def binding_agent_of(decision: ConsensusDecision) -> str | None:
    """The agent whose proposal bound, or ``None`` when the decision cannot name one.

    The full path stamps ``binding_selected=<agent>``; the fast path binds the highest-utility
    proposal, whose payload IS the selected action, so the first proposal carrying it is named.
    """
    for line in decision.audit_trace:
        if line.startswith(_BINDING_SELECTED_PREFIX):
            return line[len(_BINDING_SELECTED_PREFIX) :]
    for proposal in decision.proposals:
        if proposal.payload == decision.selected_action:
            return str(proposal.agent_name)
    return None


# ---------------------------------------------------------------------------
# Dispatch classification (R7.20, task 29.6)
# ---------------------------------------------------------------------------
@dataclasses.dataclass(frozen=True)
class DispatchClassification:
    """The one bucket a decision lands in, and why. :attr:`applies` is its consequence."""

    bucket: DispatchBucket
    reason: str

    def __post_init__(self) -> None:
        if self.bucket not in DISPATCH_BUCKETS:
            raise ValueError(f"bucket {self.bucket!r} is not one of {list(DISPATCH_BUCKETS)}")
        if not self.reason.strip():
            raise ValueError("a dispatch classification must state why it holds")

    @property
    def applies(self) -> bool:
        """Whether the binding recommendation reaches the twin (dispatched, or withheld for
        confidence alone); a blocked or untranslatable decision applies nothing."""
        return self.bucket in _APPLIED_BUCKETS


def _withheld_by(decision: ConsensusDecision) -> tuple[str, ...]:
    return tuple(
        line[len(_WITHHELD_BY_PREFIX) :]
        for line in decision.audit_trace
        if line.startswith(_WITHHELD_BY_PREFIX)
    )


def _is_withheld(decision: ConsensusDecision) -> bool:
    return _WITHHELD_MARKER in decision.audit_trace or bool(_withheld_by(decision))


def _ratification_record(decision: ConsensusDecision) -> Mapping[str, Any] | None:
    """The last ``dispatch_ratification`` record in the decision's append-only context."""
    for message in reversed(decision.context_messages):
        content = message.content
        if message.source == "orchestrator" and content.get("type") == _RATIFICATION_RECORD:
            return content
    return None


def _masked_guardrail_refusal(decision: ConsensusDecision) -> str | None:
    """Re-run every hard guardrail except the confidence floor; the refusal found, or ``None``.

    ``GuardrailEngine.validate_decision`` returns at the first failing blocking rule, and it
    checks the confidence floor BEFORE the service-level minimum (rules.py:376-379). So a
    decision recorded as failing confidence alone was never judged against the service level,
    and applying it on that record would be a guess. The real engine is re-run, over a deep copy
    (the price-cap rule clips the action it is handed in place), at a zero floor that no
    confidence in ``[0, 1]`` fails. A rule that cannot be evaluated is a refusal, never a pass
    (I-7).
    """
    from orchestrator.guardrails.rules import GuardrailEngine

    probe = decision.model_copy(update={"selected_action": copy.deepcopy(decision.selected_action)})
    try:
        passed, violations = GuardrailEngine(confidence_threshold=0.0).validate_decision(probe)
    except (TypeError, ValueError) as exc:
        return (
            "the hard guardrails could not be evaluated on the selected action "
            f"({type(exc).__name__}: {exc})"
        )
    if passed:
        return None
    return "a hard guardrail the confidence floor masked refuses it: " + "; ".join(violations)


def _withhold_refusal(decision: ConsensusDecision) -> str | None:
    """Why a withheld decision may not be applied, or ``None`` when confidence alone withheld it.

    Settled by reading (task 29.6). ``withheld_by=guardrail_violation`` is stamped for a privacy
    BLOCK, a rider-shift REJECT, the service-level ESCALATE and the confidence floor alike
    (protocol.py:898), so the marker cannot tell them apart. What can is the
    ``dispatch_ratification`` record's violation strings (protocol.py:869-887) plus a re-run of
    the rules the engine's early return skipped. Every shape that is not exactly "the
    confidence floor, plus clips at most" is refused -- never guessed toward applying.
    """
    markers = _withheld_by(decision)
    marker_count = decision.audit_trace.count(_WITHHELD_MARKER)
    if marker_count != 1 or len(markers) != 1:
        return (
            f"the audit trace carries {marker_count} withheld marker(s) and {len(markers)} "
            "withheld_by marker(s); the protocol's one withhold path stamps exactly one of each"
        )
    if decision.execution_confirmations:
        return "a withheld dispatch carries execution confirmations, so its record is incoherent"
    (gate,) = markers
    if gate == _TWIN_WITHHOLD:
        return (
            "the Tier-4 twin vetoed dispatch (ADR-054 D3); R7.20 licenses applying a "
            "recommendation withheld for confidence, and a veto is not that"
        )
    if gate != _GUARDRAIL_WITHHOLD:
        return f"dispatch was withheld by {gate!r}, which is not the confidence floor"
    record = _ratification_record(decision)
    if record is None:
        return "no dispatch_ratification record names the violations that withheld dispatch"
    if record.get("passed") is not False or record.get("twin_veto") is not False:
        return "the ratification record does not describe a guardrail withhold and nothing else"
    violations = record.get("violations")
    if not isinstance(violations, list) or not all(isinstance(v, str) for v in violations):
        return "the ratification record's violations are not a list of stated reasons"
    if not any(v.startswith(_CONFIDENCE_VIOLATION_PREFIX) for v in violations):
        return "no recorded violation names the confidence floor: " + "; ".join(violations)
    unexplained = [
        v
        for v in violations
        if not v.startswith(_CONFIDENCE_VIOLATION_PREFIX) and _CLIP_MARKER not in v.lower()
    ]
    if unexplained:
        return "a recorded violation is not the confidence floor: " + "; ".join(unexplained)
    return _masked_guardrail_refusal(decision)


def classify_dispatch(
    decision: ConsensusDecision,
    translated: PolicyAction,
    *,
    levers: frozenset[str],
    stocked: frozenset[str],
) -> DispatchClassification:
    """Put one decision in exactly one bucket: blocked > untranslatable > withheld > dispatched.

    ``translated`` is the binding action in :class:`PolicyAction` vocabulary, before anything is
    withheld from it. Pure: reads the decision and the translation, applies nothing.

    * ``guardrail_blocked`` -- withheld by anything but the confidence floor alone (a hard
      guardrail, the Tier-4 twin, an unreadable record), or neither withheld nor confirmed as
      executed. With no evidence the protocol ratified it, the I-6-safe reading applies.
    * ``untranslatable`` -- expresses no lever, a lever outside ``levers``, or a reorder for a SKU
      outside ``stocked``, the SKUs the observed twin holds. An order for a SKU the world does not
      stock is not one the twin can place: with structure 3 on, ``place_order`` refuses it, and with
      it off it would add stock to a SKU no demand ever reaches.
    * ``withheld_for_confidence`` -- withheld for confidence alone (I-5); applied (Q2=a).
    * ``dispatched`` -- ratified and handed to execution; applied.
    """
    withheld = _is_withheld(decision)
    if withheld:
        refusal = _withhold_refusal(decision)
        if refusal is not None:
            return DispatchClassification(
                bucket="guardrail_blocked", reason=f"{refusal}; nothing is applied (I-6)"
            )
    elif not decision.execution_confirmations:
        return DispatchClassification(
            bucket="guardrail_blocked",
            reason=(
                "the protocol recorded neither a withheld dispatch nor an execution "
                "confirmation, so nothing shows it ratified the action; nothing is applied (I-6)"
            ),
        )
    expressed = expressed_levers(translated)
    if not expressed:
        return DispatchClassification(
            bucket="untranslatable",
            reason=(
                f"the binding action expresses none of the levers {sorted(ALL_LEVERS)}; "
                "nothing is applied"
            ),
        )
    excluded = expressed - levers
    if excluded:
        return DispatchClassification(
            bucket="untranslatable",
            reason=(
                f"the binding action expresses {sorted(excluded)}, outside this suite's lever "
                f"set {sorted(levers)}; executing part of a recommendation is not executing it, "
                "so nothing is applied"
            ),
        )
    unstocked = sorted(set(translated.reorder_quantities) - stocked)
    if unstocked:
        return DispatchClassification(
            bucket="untranslatable",
            reason=(
                f"the binding action reorders {unstocked}, which the observed world does not "
                f"stock ({len(stocked)} SKUs stocked); an order the twin cannot place is not a "
                "recommendation it can execute, and executing part of one is not executing it, "
                "so nothing is applied"
            ),
        )
    if withheld:
        return DispatchClassification(
            bucket="withheld_for_confidence",
            reason=(
                "dispatch was withheld for confidence alone (I-5); the binding recommendation "
                "is applied, as a recommendation if executed (R7.20, decision Q2=a)"
            ),
        )
    return DispatchClassification(
        bucket="dispatched", reason="the protocol ratified the binding action and dispatched it"
    )


@dataclasses.dataclass(frozen=True)
class ConsensusOutcome:
    """One consultation of the consensus pathway: request, decision, translation and bucket.

    Returned by :meth:`ConsensusArm.consult`, which counts nothing, so the pathway probe can
    consult the arm without moving a run's tally. :meth:`ConsensusArm.decide` is ``consult``
    plus the tally plus :attr:`action`.
    """

    request: Mapping[str, Any]
    decision: ConsensusDecision
    translated: PolicyAction
    dispatch: DispatchClassification

    @property
    def action(self) -> PolicyAction:
        """What reaches the twin: the translation when it applies, the neutral action if not."""
        return self.translated if self.dispatch.applies else PolicyAction()

    @property
    def binding_agent(self) -> str | None:
        """The agent whose proposal bound (:func:`binding_agent_of`)."""
        return binding_agent_of(self.decision)


def _checked_levers(levers: frozenset[str]) -> frozenset[str]:
    """Refuse a lever set that names no lever, or a lever no :class:`PolicyAction` carries."""
    if not isinstance(levers, frozenset):
        raise TypeError(f"levers must be a frozenset of lever names, not {type(levers).__name__}")
    unknown = sorted(str(name) for name in levers - ALL_LEVERS)
    if unknown:
        raise ValueError(
            f"levers {unknown} are not PolicyAction levers; the admissible names are "
            f"{sorted(ALL_LEVERS)}"
        )
    if not levers:
        raise ValueError(
            "an empty lever set makes every decision untranslatable: an arm that applies "
            "nothing while it is named consensus"
        )
    return levers


def _empty_tally() -> dict[DispatchBucket, int]:
    return {bucket: 0 for bucket in DISPATCH_BUCKETS}


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

    **Run-scoped (task 29.6, R7.20).** The arm satisfies :class:`~uplift.interfaces.RunScoped`:
    ``begin_run`` opens a fresh tally, every ``decide`` that returns lands in exactly one
    :data:`DispatchBucket`, and ``end_run`` returns the run's
    :class:`~uplift.interfaces.DecisionCounts`. A ``decide`` that raises counts nothing, because
    the run it belongs to fails honestly (R2.7). ``levers`` names the levers this arm's suite
    applies (:data:`ALL_LEVERS` by default, which is the behaviour before the set existed).
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
        levers: frozenset[str] = ALL_LEVERS,
    ) -> None:
        checked = _checked_levers(levers)
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
        self._levers = checked
        self._tally: dict[DispatchBucket, int] = _empty_tally()
        self._run_seed: int | None = None

    @property
    def levers(self) -> frozenset[str]:
        """The levers this arm's suite applies; a binding action outside them applies nothing."""
        return self._levers

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
            raise ConsensusArmUnavailable(f"consensus protocol construction failed: {exc}") from exc
        if built is None:
            raise ConsensusArmUnavailable("protocol_factory returned None")
        return built

    def consult(self, obs: Observation) -> ConsensusOutcome:
        """Run real consensus for ``obs`` and classify it, counting nothing.

        On any failure to reach a decision -- ``run_consensus`` raising, or consensus
        completing without reaching a single agent -- the failure is surfaced (raised), so
        the harness records the run as failed (R2.7) and never applies a fabricated
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
        translated = self._translate(decision, obs)
        return ConsensusOutcome(
            request=decision_request,
            decision=decision,
            translated=translated,
            dispatch=classify_dispatch(
                decision, translated, levers=self._levers, stocked=frozenset(obs.inventory)
            ),
        )

    def decide(self, obs: Observation) -> PolicyAction:
        """Run real consensus for ``obs``, count its bucket, and return what reaches the twin.

        That is the binding recommendation when it was dispatched or withheld for confidence
        alone (R7.20), and the neutral action when it was blocked or is untranslatable.
        """
        outcome = self.consult(obs)
        self._tally[outcome.dispatch.bucket] += 1
        return outcome.action

    def begin_run(self, seed: int) -> None:
        """Open run ``seed``'s tally: every count starts again at zero."""
        if isinstance(seed, bool) or not isinstance(seed, int):
            raise TypeError(f"a run seed is an int, not {type(seed).__name__}")
        self._tally = _empty_tally()
        self._run_seed = seed

    def end_run(self) -> DecisionCounts:
        """Close the open run and return its tally (R7.20).

        Raises:
            RuntimeError: if no run is open -- a tally attributed to no run is not a run's.
        """
        if self._run_seed is None:
            raise RuntimeError("end_run() with no run open; begin_run(seed) opens one")
        tally = self._tally
        self._run_seed = None
        return DecisionCounts(
            dispatched=tally["dispatched"],
            withheld_for_confidence=tally["withheld_for_confidence"],
            guardrail_blocked=tally["guardrail_blocked"],
            untranslatable=tally["untranslatable"],
        )

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
            return loop.run_until_complete(self._protocol.run_consensus(decision_request))
        finally:
            protocol_mod.send_a2a_request = original_transport
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


def _offline_reasoner() -> DeepSeekReasoner:
    """The Disruption Shield's own reasoner with its one HTTP call refused (finding 116, I-1).

    ``DeepSeekReasoner.reason`` (``agents/disruption_shield/models/reasoning.py:44-71``) calls
    ``_call_ollama`` (line 89), the class's only HTTP method, and on ``httpx.HTTPError``,
    ``httpx.TimeoutException`` or ``json.JSONDecodeError`` (line 65) logs ``ollama_unavailable``
    and returns ``_fallback_reasoning``, its rule-based chain. A refused port or a host name that
    does not resolve fails that method's ``client.post`` (line 102) with ``httpx.ConnectError``,
    an ``httpx.HTTPError``. The subclass overrides ``_call_ollama`` alone, raising that class
    before any client is built, so the rest of ``reason`` runs unchanged: it returns what the E5
    job's refused-port workaround returned, and only the warning's ``error`` text differs.

    The class is defined in here because its base lives in ``agents``, which this module imports
    only inside functions (``uplift/controls_run.py``'s thin-closure note). So it cannot be
    pickled, which changes nothing: the assembled arm already holds the local factory
    :func:`_in_process_session_factory` returns, and the harness runs an arm it cannot pickle
    serially.
    """
    import httpx

    from agents.disruption_shield.models import reasoning

    class _OfflineReasoner(reasoning.DeepSeekReasoner):
        """``DeepSeekReasoner`` with ``_call_ollama`` refused; every other line is the base's."""

        #: Not called ``reason``: that name is the base's method, which must not be shadowed.
        unavailable_reason = "no Ollama in the network-free in-process consensus arm ($0)"

        def _call_ollama(self, prompt: str) -> dict[str, Any]:  # noqa: ARG002 - always refused
            raise httpx.ConnectError(self.unavailable_reason)

    return _OfflineReasoner()


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
    :class:`_OfflineActuator`. The returned mapping's keys are exactly the
    :data:`AGENT_ENDPOINTS` names.

    **Neither Ollama path opens a socket (finding 116).** The debate's LLM client is
    :class:`_OfflineLLMClient` (:func:`build_consensus_protocol`). The Disruption Shield is the
    one agent whose default pipeline dials on every consult: its ``DeepSeekReasoner`` POSTs to
    ``http://ollama:11434``. So that handler alone is given a pipeline built with
    :func:`_offline_reasoner`, which takes the reasoner's own rule-based fallback with no socket;
    every other part of that pipeline is its default. The claim that assembling these handlers
    and consulting each for a proposal opens no socket is checked by
    ``tests/uplift/test_consensus_network_free_property.py``, under a guard that fails every
    non-loopback dial and every ``httpx`` send.

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
            if name == "disruption_shield":
                # Read through importlib, as each handler class is, so mypy does not follow the
                # agent's model imports into this module's type check.
                pipeline_module = importlib.import_module(
                    "agents.disruption_shield.inference.pipeline"
                )
                kwargs["pipeline"] = pipeline_module.DisruptionShieldPipeline(
                    reasoner=_offline_reasoner()
                )
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
    levers: frozenset[str] = ALL_LEVERS,
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
        levers: the levers the arm's suite applies (task 29.6). :data:`ALL_LEVERS` is the
            behaviour before the set existed; the E5 suite passes ``frozenset({"reorder"})``,
            and a binding action expressing any other lever is then untranslatable.

    Returns:
        A :class:`ConsensusArm` wired to the in-process network.

    Raises:
        ConsensusArmUnavailable: if the agent/twin network or the protocol cannot be
            assembled in this environment (R1.5). The caller records the affected runs
            as failed runs; no stub arm is fabricated and no decision is invented.
        ValueError: if ``levers`` names no lever or one no ``PolicyAction`` carries --
            refused before anything is assembled.
    """
    checked = _checked_levers(levers)
    handlers = dict(agent_handlers) if agent_handlers is not None else build_agent_handlers()
    if not handlers:
        raise ConsensusArmUnavailable(
            "no in-process agent handlers were assembled; the consensus network is "
            "unavailable in this environment"
        )
    twin = twin_handler if twin_handler is not None else build_twin_handler()
    transport = InProcessA2ATransport.from_agents(handlers, twin_handler=twin)
    resolved_protocol = protocol if protocol is not None else build_consensus_protocol()
    return ConsensusArm(protocol=resolved_protocol, transport=transport, name=name, levers=checked)


__all__ = [
    "ALL_LEVERS",
    "A2AHandler",
    "ActionTranslator",
    "ConsensusArm",
    "ConsensusArmUnavailable",
    "ConsensusOutcome",
    "DEFAULT_CONSENSUS_ARM",
    "DISPATCH_BUCKETS",
    "DispatchBucket",
    "DispatchClassification",
    "InProcessA2ATransport",
    "RequestBuilder",
    "Transport",
    "binding_agent_of",
    "build_agent_handlers",
    "build_consensus_arm",
    "build_consensus_protocol",
    "build_twin_handler",
    "classify_dispatch",
    "consensus_decision_to_policy_action",
    "expressed_levers",
    "observation_to_decision_request",
]
