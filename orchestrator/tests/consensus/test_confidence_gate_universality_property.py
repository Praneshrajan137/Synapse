"""Property-based test for the tier-universal confidence gate (task 8.6, design E3).

Feature: purpose-achievement-audit, Property 22: The confidence gate applies on every tier

    *For any* generated decision request and *any* tier the router assigns, if the
    resulting decision's confidence is below the configured threshold then the decision
    is escalated, its audit row records ``escalated = true``, the guardrail engine was
    consulted before any dispatch attempt, and the dispatched-action count for that
    decision identifier is zero; and *for any* action violating a guardrail declared
    ``BLOCK``, no dispatch occurs on any tier and ``execution_confirmations`` is absent
    or empty.

Subject
-------

``ConsensusProtocol._ratify_and_dispatch`` (ADR-054 D1, task 8.5) - the single path from
a built decision to a dispatched action. Real collaborators wherever the assertion
depends on them: the real :class:`~orchestrator.guardrails.rules.GuardrailEngine`
supplies the verdict, its boundary comes from a real
:class:`~orchestrator.config.OrchestratorConfig` through
:class:`~orchestrator.guardrails.thresholds.ConfigConfidenceThresholdProvider`, and the
real :class:`~orchestrator.hitl.escalation.HITLEscalation` awaits a human future.
Postgres and the A2A network are the only doubles, and both are *recording sinks* rather
than mocks with canned verdicts, so the property observes what happened instead of what a
mock was told to say.

Why the tier is quantified over rather than sampled
--------------------------------------------------

R5.1's claim is unqualified - I-5 is "confidence-gated execution", not "confidence-gated
execution on the routes that happen to check". The finding behind Requirement 5 is
precisely that the tier router got to decide whether the invariant applied, because
``_fast_path`` reached ``_phase_execute`` directly. A property that *sampled* a tier
would reproduce that defect class in its own oracle: a re-introduced Tier-1 bypass would
show up in a fraction of examples and shrink to a confusing counterexample. So every
example iterates the whole of ``DecisionTier``, and the verdict is asserted to be
identical across all four. The tier is a loop, never a strategy.

What the sibling tests already cover, and what this adds
--------------------------------------------------------

``test_dispatch_choke_point.py`` is example-class: four Tier-1 cases (sub-threshold
confidence withholds; a BLOCK violation withholds; a passing decision dispatches once and
appends one row) plus four Tier-4 twin-verdict cases (beyond-bound escalates, ``withhold``
queues no human, an unavailable twin vetoes nothing, agreement dispatches). It pins the
route that previously had no gate at all, at one threshold and a handful of confidences.

``test_binding_fastpath.py`` is about *selection*, not ratification: the fast path still
picks the raw ``utility_score`` argmax (R1.6) and the full path picks the Pareto knee
(R1.2). It stubs the guardrail engine to ``(True, [])`` on purpose and says so.

``test_threshold_reload_property.py`` (Property 24) owns the *engine* seam: that the
boundary is the currently configured value, that it is exactly the configured value, and
that raising it is monotone in the escalation count. It never constructs the protocol and
never attempts a dispatch.

Uncovered until here, and asserted below:

1. **The gate verdict is universal over the tier and total over confidence.** Dispatch
   happens iff the confidence is at or above the *currently configured* threshold and no
   BLOCK violation applies - asserted for all four tiers in every example, at generated
   thresholds rather than one, and with the just-below-boundary case pinned by
   ``math.nextafter`` rather than an epsilon.
2. **A withheld dispatch is empty-handed on every tier.** No ``execute`` call reaches any
   agent, ``execution_confirmations`` is empty, and
   :func:`~orchestrator.hitl.escalation.has_dispatch_confirmation` agrees - so the HITL
   timeout record cannot later claim an action nobody took.
3. **The guardrail engine is consulted before any dispatch attempt** (R5.7) - asserted as
   an *ordering* over recorded events, not inferred from the source.
4. **Neither route has a bypass.** Behaviourally, ``_fast_path`` and ``_full_path`` are
   both driven and both enter the choke point exactly once; structurally, every
   privileged dispatch operation (the guardrail verdict, the escalation, the
   ``execute_consensus`` contract, ``_phase_execute``) has exactly one call site in the
   whole module, and it is the choke point. The structural clause is what makes "neither
   has a bypass" a claim about the module rather than about the two paths this test
   happened to drive.
5. **An escalation awaits a human future and dispatches nothing** - including when the
   human *approves*. No branch executes the action after escalating, in either direction.

Scope, and the sub-``0.7`` band this property now reaches
--------------------------------------------------------

``guardrails.rules.execute_consensus`` is on the production path (R13.7). Its
``@deal.pre`` used to hardcode ``0.7`` while task 8.1 had made the boundary reloadable,
so an operator reloading *below* ``0.7`` let a decision in ``[threshold, 0.7)`` pass
``validate_decision`` and then trip ``PreContractError`` inside the choke point -
fail-closed, but raised **after** the I-4 audit append, which is a crash plus an
irretractable row describing a dispatch that never happened. This file used to bound the
generated boundary below by that literal, which made the whole defective band
unreachable and is why the defect went unowned by every property that surrounds it.

Task 12.1a repaired it: one shared predicate
(:func:`~orchestrator.guardrails.rules.satisfies_confidence_floor`) is both the
``@deal.pre`` validator and a pre-flight the choke point evaluates *before* the append,
against a single snapshot of the boundary in force. So the boundary is now generated over
the **whole** closed unit interval, and the ``[threshold, 0.7)`` band is asserted rather
than avoided: a decision there dispatches, is recorded ``passed=True``, and raises
nothing. That makes this property the regression test the defect never had - the
pre-repair code fails it as an error escaping ``_ratify_and_dispatch``, and a
reintroduced literal floor fails it as ``dispatched is not expected``.

One clause cannot take the widened range and says so at its own strategy:
``test_an_escalation_awaits_a_human_and_dispatches_nothing`` pins ``confidence=0.0`` to
force the sub-threshold branch, which a boundary of exactly ``0.0`` does not do (at
``threshold=0.0`` a clean decision legitimately dispatches). It draws from
:func:`positive_thresholds` instead. The other clauses derive their oracle from the
generated values rather than from which branch the composite chose, so ``0.0`` is an
ordinary case for them.

The Tier-4 twin is consulted on the full-path drive with a transport that returns no
``kpi_means``, so the verdict degrades honestly to "no comparable KPI" and vetoes nothing
(I-7). The twin's *consequence* is Property 26 (task 8.8), not this property.

R5.6 asks for a replay corpus of at least 200 decisions with at least 50 sub-threshold and
at least 10 per tier. That size is an integration-scale obligation; what a property can
carry is the invariant the corpus exists to check, asserted over generated corpora with
all four tiers covered in every example. At the ``heavy`` profile the accumulated corpus
across a run is far larger than 200, and every sub-threshold decision in it is checked.

I-0: this module drives the real ``ConsensusProtocol``, so it is ``@pytest.mark.slow``,
runs in ``ci.yml::uplift-verify`` under ``HYPOTHESIS_PROFILE=heavy``, and is excluded
locally by ``-m "not slow"``. ``max_examples`` is never set here - the budget comes from
the root ``conftest.py`` profiles (``dev``=10, ``heavy``=100, ``ci``/``default``=500,
``nightly``=5000).

**Validates: Requirements 5.1, 5.2, 5.6, 5.7**
"""

from __future__ import annotations

import ast
import asyncio
import math
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final, NamedTuple
from unittest import mock
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from hypothesis import given
from hypothesis import strategies as st
from synapse_common.models import (
    AgentName,
    AgentProposal,
    ConsensusDecision,
    DecisionTier,
)

from orchestrator.config import OrchestratorConfig
from orchestrator.consensus import protocol as protocol_mod
from orchestrator.consensus.models import TierClassification
from orchestrator.consensus.pareto import OBJECTIVES
from orchestrator.consensus.protocol import ConsensusProtocol, TwinVerdict
from orchestrator.guardrails.rules import GuardrailEngine
from orchestrator.guardrails.thresholds import ConfigConfidenceThresholdProvider
from orchestrator.hitl.escalation import (
    HITLEscalation,
    WebSocketManager,
    has_dispatch_confirmation,
)

if TYPE_CHECKING:
    from collections.abc import Iterable
    from uuid import UUID

# --------------------------------------------------------------------------- constants

#: I-5 is stated without qualification, so every tier is checked in every example.
TIERS: Final[tuple[DecisionTier, ...]] = tuple(DecisionTier)

#: The tiers routed through ``_fast_path`` - the route that had no gate at all.
FAST_PATH_TIERS: Final[tuple[DecisionTier, ...]] = (
    DecisionTier.TIER_1,
    DecisionTier.TIER_2,
)

#: The operations only the ratification choke point may perform. Each is the *reason*
#: a route cannot be trusted to gate itself: the guardrail verdict (I-6), the human
#: escalation (I-5), the ``@deal.pre``/``@deal.post`` contract (I-5/I-4), and the
#: dispatch itself.
PRIVILEGED_OPERATIONS: Final[tuple[str, ...]] = (
    "self._guardrails.validate_decision",
    "self._hitl.escalate",
    "execute_consensus",
    "self._phase_execute",
)

CHOKE_POINT: Final[str] = "_ratify_and_dispatch"

#: The A2A method by which an action reaches the world.
DISPATCH_METHOD: Final[str] = "execute"

_VALIDATE_EVENT: Final[str] = "validate"
_DISPATCH_EVENT: Final[str] = "dispatch"
_HUMAN_EVENT: Final[str] = "human"


def equal_weights() -> dict[str, float]:
    """A weight vector over every meta-RL objective."""
    return {objective: 1.0 for objective in OBJECTIVES}


# ----------------------------------------------------------------------------- oracles


def gate_passes(confidence: float, threshold: float, *, blocked: bool) -> bool:
    """The ratification verdict, restated independently of the subject.

    Two clauses, matching R5.1 and R5.2: a BLOCK violation withholds dispatch
    irrespective of confidence, and otherwise the confidence must be at or above the
    boundary. ``_check_confidence_floor`` compares ``confidence < threshold``; restating
    that comparison rather than importing it means the property compares two
    implementations instead of asserting the subject agrees with itself.
    """
    return not blocked and confidence >= threshold


# --------------------------------------------------------------------- recording doubles


class _Trace:
    """An ordered log of the events the ordering assertions are made over.

    Ordering is asserted from observed events rather than read off the source, so a
    reordering of the choke point that dispatched before validating would be caught even
    though the source still contains both calls.
    """

    __slots__ = ("events",)

    def __init__(self) -> None:
        self.events: list[str] = []

    def record(self, event: str) -> None:
        self.events.append(event)

    def index_of(self, event: str) -> int:
        return self.events.index(event)


class _RecordingAudit:
    """An ``AuditLogger``-shaped append-only sink (I-4: append, never update).

    The real logger needs Postgres. What this property asserts is how many rows were
    appended and what each said about dispatch, which this records faithfully.
    """

    __slots__ = ("rows",)

    def __init__(self) -> None:
        self.rows: list[ConsensusDecision] = []

    async def log_decision(self, decision: ConsensusDecision) -> UUID:
        self.rows.append(decision)
        return uuid4()


class _A2AResponse(NamedTuple):
    """The shape ``send_a2a_request`` returns, as the protocol reads it."""

    error: str | None
    result: dict[str, Any] | None


class _RecordingTransport:
    """Replaces ``send_a2a_request`` and records every call in order.

    Deliberately answers ``monte_carlo`` with no ``kpi_means``: the Tier-4 twin then has
    no comparable KPI, degrades honestly, and vetoes nothing (I-7), so a withheld
    dispatch in this property is always attributable to the confidence gate or the BLOCK
    guardrail and never to the twin.
    """

    __slots__ = ("calls", "_trace")

    def __init__(self, trace: _Trace) -> None:
        self.calls: list[dict[str, Any]] = []
        self._trace = trace

    async def __call__(self, **kwargs: Any) -> _A2AResponse:
        self.calls.append(kwargs)
        if kwargs.get("method") == DISPATCH_METHOD:
            self._trace.record(_DISPATCH_EVENT)
        return _A2AResponse(error=None, result={"status": "ok"})

    @property
    def dispatches(self) -> list[dict[str, Any]]:
        """Every A2A call that would enact an action on the world."""
        return [call for call in self.calls if call.get("method") == DISPATCH_METHOD]


class _OrderedGuardrails:
    """Wraps the **real** engine and records when its verdict was taken.

    A wrapper rather than a stand-in: the verdict is the real engine's, so the property
    is evidence about ``GuardrailEngine`` and about the order the choke point consults
    it in, not about a canned return value.
    """

    __slots__ = ("_engine", "_trace", "validations")

    def __init__(self, engine: GuardrailEngine, trace: _Trace) -> None:
        self._engine = engine
        self._trace = trace
        self.validations: int = 0

    @property
    def confidence_threshold(self) -> float:
        return self._engine.confidence_threshold

    def validate_decision(self, decision: ConsensusDecision) -> tuple[bool, list[str]]:
        self.validations += 1
        self._trace.record(_VALIDATE_EVENT)
        return self._engine.validate_decision(decision)


class _RecordingWaiter:
    """A timer-free ``HumanResponseWaiter`` that records what it was handed.

    ``approve=True`` returns a human approval; ``approve=False`` times the human out.
    Both are asserted to dispatch nothing, which is the load-bearing half of I-5: there
    is no branch that executes the action after escalating.
    """

    __slots__ = ("_approve", "_trace", "awaited", "pending_when_awaited")

    def __init__(self, trace: _Trace, *, approve: bool) -> None:
        self._approve = approve
        self._trace = trace
        self.awaited: list[UUID] = []
        self.pending_when_awaited: list[bool] = []

    async def __call__(
        self,
        future: asyncio.Future[dict[str, Any]],
        *,
        timeout: float,
        decision_id: UUID,
    ) -> dict[str, Any]:
        del timeout
        self.awaited.append(decision_id)
        self.pending_when_awaited.append(isinstance(future, asyncio.Future) and not future.done())
        self._trace.record(_HUMAN_EVENT)
        if self._approve:
            return {"action": "approve", "approved_by": "operator"}
        raise TimeoutError


# ---------------------------------------------------------------------------- fixtures


class _Harness(NamedTuple):
    """One protocol under test plus every sink the assertions read."""

    protocol: ConsensusProtocol
    guardrails: _OrderedGuardrails
    audit: _RecordingAudit
    transport: _RecordingTransport
    trace: _Trace
    waiter: _RecordingWaiter
    threshold: float


def build_harness(*, threshold: float, approve: bool = False) -> _Harness:
    """Build a real protocol whose escalation boundary comes from configuration.

    The boundary reaches the engine as an ``OrchestratorConfig`` field through
    ``ConfigConfidenceThresholdProvider``, and is read back through the provider - no
    threshold literal appears in any assertion, so relaxing the shipped default cannot
    leave this property passing for the wrong reason.
    """
    config = OrchestratorConfig(
        postgresql_url="sqlite+aiosqlite:///",
        pinecone_api_key=None,
        confidence_threshold=threshold,
    )
    provider = ConfigConfidenceThresholdProvider(config)
    trace = _Trace()
    guardrails = _OrderedGuardrails(GuardrailEngine(confidence_threshold=provider), trace)
    audit = _RecordingAudit()
    transport = _RecordingTransport(trace)
    waiter = _RecordingWaiter(trace, approve=approve)

    protocol = ConsensusProtocol(
        config=config,
        tier_router=MagicMock(),
        guardrails=guardrails,  # type: ignore[arg-type]
        audit_logger=audit,  # type: ignore[arg-type]
        hitl_escalation=HITLEscalation(
            kafka_producer=None,
            ws_manager=WebSocketManager(),
            timeout_seconds=0.01,
            timeout_action="defer",
            waiter=waiter,
        ),
        context_builder=MagicMock(),
        ollama_client=MagicMock(),
        meta_rl=MagicMock(**{"get_weights.return_value": equal_weights()}),
        semantic_cache=MagicMock(available=False, store_decision=AsyncMock()),
    )
    return _Harness(
        protocol=protocol,
        guardrails=guardrails,
        audit=audit,
        transport=transport,
        trace=trace,
        waiter=waiter,
        threshold=provider.current(),
    )


def blocking_action() -> dict[str, Any]:
    """An action that violates ``privacy_boundary``, whose enforcement is ``BLOCK``.

    Raw demand (``order_ids``) alongside two store identities and an explicit recipient:
    I-11's cross-store raw-demand payload. Nothing else in it trips a guardrail, so a
    withheld dispatch is attributable to the BLOCK rule.
    """
    return {
        "action_type": "reorder",
        "store_id": "blr_001",
        "target_store_id": "blr_002",
        "share_with": ["blr_002"],
        "order_ids": ["o-1", "o-2"],
    }


def clean_action() -> dict[str, Any]:
    """An action no guardrail objects to.

    No ``pricing_actions`` to clip, no ``routing_actions`` to reject, no
    ``predicted_fill_rate`` to report and one store identity, so the confidence floor is
    the only reachable gate.
    """
    return {"action_type": "reorder", "store_id": "blr_001"}


def action_for(*, blocked: bool) -> dict[str, Any]:
    return blocking_action() if blocked else clean_action()


def proposal_for(
    confidence: float,
    action: dict[str, Any],
    tier: DecisionTier,
) -> AgentProposal:
    """One proposal whose confidence is the confidence the decision will carry.

    Both routes derive the decision's confidence from a selected proposal
    (``fast_best.confidence`` on the fast path, the knee-selected proposal's on the
    full path), so a single proposal makes the generated confidence the decision's on
    either route without the property having to model selection.
    """
    return AgentProposal(
        agent_name=AgentName.INVENTORY_SENTINEL,
        decision_id=uuid4(),
        utility_score=confidence,
        confidence=confidence,
        justification_trace=["reorder below par"],
        payload=dict(action),
        tier=tier,
    )


def decision_for(
    *,
    confidence: float,
    tier: DecisionTier,
    blocked: bool,
) -> ConsensusDecision:
    action = action_for(blocked=blocked)
    return ConsensusDecision(
        tier=tier,
        proposals=[proposal_for(confidence, action, tier)],
        selected_action=action,
        pareto_weights=equal_weights(),
        confidence=confidence,
        audit_trace=[f"tier={tier.value}", "phase=4"],
    )


def ratification_record(decision: ConsensusDecision) -> dict[str, Any]:
    """The choke point's own append-only record of this ratification."""
    records = [
        message.content
        for message in decision.context_messages
        if message.content.get("type") == "dispatch_ratification"
    ]
    assert records, "the choke point records every ratification it performs"
    return records[-1]


# -------------------------------------------------------------------------- strategies


class _GateCase(NamedTuple):
    """A configured boundary, a confidence, and whether the action is BLOCK-violating."""

    threshold: float
    confidence: float
    blocked: bool


def thresholds() -> st.SearchStrategy[float]:
    """Any configurable boundary in the closed unit interval.

    The whole interval, deliberately: the band below the guardrail table's declared
    default is where ``execute_consensus``'s precondition and the reloadable boundary
    used to disagree, and after task 12.1a it is the band this property is the regression
    test for. No literal bounds it, so relaxing the shipped default cannot narrow what
    is generated here.
    """
    return st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)


def positive_thresholds() -> st.SearchStrategy[float]:
    """Any configurable boundary strictly above zero.

    For the one clause that pins ``confidence=0.0`` to *force* the sub-threshold branch.
    Zero is below every boundary in this range and below no boundary of ``0.0``, so the
    exclusion is what makes that clause's premise true rather than usually true. A clause
    whose oracle is computed from the generated values needs no such exclusion and uses
    :func:`thresholds` instead.
    """
    return st.floats(
        min_value=0.0,
        max_value=1.0,
        exclude_min=True,
        allow_nan=False,
        allow_infinity=False,
    )


def confidences() -> st.SearchStrategy[float]:
    """Any confidence a ``ConsensusDecision`` admits (the model pins ``0 <= c <= 1``)."""
    return st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)


@st.composite
def gate_cases(draw: st.DrawFn) -> _GateCase:
    """A case that lands deliberately on one side of the boundary.

    Drawing the confidence independently of the boundary would spend most examples far
    from the interesting region. Instead each example picks a side, and the withholding
    side includes ``math.nextafter(threshold, 0.0)`` so the boundary is pinned exactly
    rather than approximately: the threshold itself must dispatch and the largest
    representable value below it must not.

    The side is a search heuristic, never part of the oracle. At a boundary of ``0.0``
    the withholding side is empty - ``ConsensusDecision`` pins ``confidence >= 0``, so no
    admissible confidence lies below zero and ``nextafter(0.0, 0.0)`` is ``0.0`` - and
    the drawn case is simply a passing one. ``gate_passes`` recomputes the verdict from
    the drawn values, so that example asserts the dispatching branch rather than
    silently asserting nothing.
    """
    threshold = draw(thresholds())
    blocked = draw(st.booleans())
    just_below = math.nextafter(threshold, 0.0)
    if draw(st.booleans()):
        confidence = draw(
            st.floats(
                min_value=threshold,
                max_value=1.0,
                allow_nan=False,
                allow_infinity=False,
            ),
        )
    else:
        confidence = draw(
            st.one_of(
                st.just(just_below),
                st.floats(
                    min_value=0.0,
                    max_value=just_below,
                    allow_nan=False,
                    allow_infinity=False,
                ),
            ),
        )
    return _GateCase(threshold=threshold, confidence=confidence, blocked=blocked)


# ------------------------------------------------------------------------- async drivers


async def ratify(
    case: _GateCase,
    tier: DecisionTier,
    *,
    approve: bool = False,
) -> tuple[_Harness, ConsensusDecision]:
    """Drive one decision through the real choke point on *tier*."""
    harness = build_harness(threshold=case.threshold, approve=approve)
    with mock.patch.object(protocol_mod, "send_a2a_request", harness.transport):
        decision = await harness.protocol._ratify_and_dispatch(
            decision_for(confidence=case.confidence, tier=tier, blocked=case.blocked),
            tier=tier,
        )
    return harness, decision


async def run_route(
    case: _GateCase,
    tier: DecisionTier,
) -> tuple[_Harness, ConsensusDecision, list[DecisionTier]]:
    """Drive the real route for *tier* and record every choke-point traversal.

    Proposal collection and Pareto arbitration are supplied so the generated confidence
    is the decision's confidence and the run needs no live agents or NSGA-II sweep;
    selection, the guardrail engine, the escalator, the contract, the audit append and
    the dispatch are all real. Arbitration's own consequence is Property 26's subject,
    not this one's.
    """
    harness = build_harness(threshold=case.threshold)
    protocol = harness.protocol
    proposals = [proposal_for(case.confidence, action_for(blocked=case.blocked), tier)]
    traversals: list[DecisionTier] = []
    original = protocol._ratify_and_dispatch

    async def _collect(request: dict[str, Any], routed: DecisionTier) -> list[AgentProposal]:
        del request, routed
        return list(proposals)

    async def _arbitrate(candidates: list[AgentProposal]) -> dict[str, Any]:
        del candidates
        return {"selected_weights": equal_weights(), "knee_index": 0, "n_solutions": 1}

    async def _counted(
        decision: ConsensusDecision,
        *,
        tier: DecisionTier,
        twin_verdict: TwinVerdict | None = None,
    ) -> ConsensusDecision:
        traversals.append(tier)
        return await original(decision, tier=tier, twin_verdict=twin_verdict)

    protocol._phase_collect = _collect  # type: ignore[method-assign,assignment]
    protocol._phase_arbitrate = _arbitrate  # type: ignore[method-assign,assignment]
    protocol._ratify_and_dispatch = _counted  # type: ignore[method-assign]

    request: dict[str, Any] = {"city": "bengaluru"}
    with mock.patch.object(protocol_mod, "send_a2a_request", harness.transport):
        if tier in FAST_PATH_TIERS:
            decision = await protocol._fast_path(request, tier)
        else:
            decision = await protocol._full_path(
                request,
                tier,
                TierClassification(
                    tier=tier,
                    confidence=case.confidence,
                    reasons=["property-22"],
                    model=None,
                    latency_budget_ms=120_000,
                ),
            )
    return harness, decision, traversals


# ------------------------------------------------------------- structural call-site walk


def _dotted(node: ast.expr) -> str | None:
    """Render an attribute/name chain as ``a.b.c``, or ``None`` for anything else."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _dotted(node.value)
        return None if base is None else f"{base}.{node.attr}"
    return None


def _methods() -> Iterable[ast.FunctionDef | ast.AsyncFunctionDef]:
    """Every method defined on ``ConsensusProtocol``, from the module source.

    ``encoding='utf-8'`` per E-S13-07 - a default-codepage read of this module on Windows
    is exactly the failure that lesson records.
    """
    source = Path(protocol_mod.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == ConsensusProtocol.__name__:
            for member in node.body:
                if isinstance(member, ast.FunctionDef | ast.AsyncFunctionDef):
                    yield member


def call_sites(target: str) -> frozenset[str]:
    """The ``ConsensusProtocol`` methods that *call* ``target``.

    Calls only - a mention in a docstring, a comment, or a type annotation is not a call
    site, which is why this walks the AST instead of the file text.
    """
    sites: set[str] = set()
    for method in _methods():
        for node in ast.walk(method):
            if isinstance(node, ast.Call) and _dotted(node.func) == target:
                sites.add(method.name)
    return frozenset(sites)


# -------------------------------------------------------------------------- properties


# Feature: purpose-achievement-audit, Property 22: The confidence gate applies on every tier
@pytest.mark.slow
@given(case=gate_cases())
def test_dispatch_happens_iff_the_gate_passes_on_every_tier(case: _GateCase) -> None:
    """R5.1, R5.2, R5.7: one verdict, four tiers, and nothing dispatched when withheld.

    The tier is iterated rather than sampled: R5.1 is unqualified, so a verdict that
    differed by route would be the defect Requirement 5 reports, and it is asserted here
    to be impossible in every example rather than unlikely across a run.
    """
    expected = gate_passes(case.confidence, case.threshold, blocked=case.blocked)
    observed: set[bool] = set()

    for tier in TIERS:
        harness, decision = asyncio.run(ratify(case, tier))

        # The boundary is the configured one, not a construction-time capture.
        assert harness.threshold == case.threshold
        assert harness.guardrails.confidence_threshold == case.threshold

        # R5.7: the engine is consulted on every tier, before anything is dispatched.
        assert harness.guardrails.validations == 1
        assert harness.trace.events[0] == _VALIDATE_EVENT

        dispatched = bool(harness.transport.dispatches)
        observed.add(dispatched)
        assert dispatched is expected

        record = ratification_record(decision)
        assert record["tier"] == tier.value
        assert record["confidence"] == case.confidence
        assert record["passed"] is expected
        assert record["twin_veto"] is False

        if expected:
            # One dispatch per proposal, and the confirmation is the agent's own answer.
            assert len(harness.transport.dispatches) == len(decision.proposals)
            assert decision.execution_confirmations == ["ok"]
            assert has_dispatch_confirmation(decision.execution_confirmations) is True
            assert decision.escalated_to_human is False
            assert harness.waiter.awaited == []
            assert harness.trace.index_of(_VALIDATE_EVENT) < harness.trace.index_of(
                _DISPATCH_EVENT,
            )
        else:
            # R5.1/R5.2: zero dispatched actions and an empty confirmation list.
            assert harness.transport.dispatches == []
            assert decision.execution_confirmations == []
            assert has_dispatch_confirmation(decision.execution_confirmations) is False
            assert _DISPATCH_EVENT not in harness.trace.events
            assert "dispatch=withheld" in decision.audit_trace
            # The audit row says the same thing the returned decision says.
            assert harness.audit.rows[-1].execution_confirmations == []

        # I-4: exactly one row per decision either way. The choke point appends before
        # `execute_consensus`'s @deal.post is checked and `_phase_execute` reuses the id,
        # so a dispatched decision does not produce a second row. That row is a
        # pre-execution snapshot, which is why the dispatched case asserts confirmations
        # on the returned decision rather than on the row.
        assert len(harness.audit.rows) == 1
        assert decision.audit_id is not None

    # I-5 is not a property of a route: all four tiers agreed.
    assert observed == {expected}


# Feature: purpose-achievement-audit, Property 22: The confidence gate applies on every tier
@pytest.mark.slow
@given(
    threshold=thresholds(),
    corpus=st.lists(st.tuples(confidences(), st.booleans()), min_size=1, max_size=6),
)
def test_no_dispatched_decision_is_sub_threshold_or_unescalated(
    threshold: float,
    corpus: list[tuple[float, bool]],
) -> None:
    """R5.6: over a replayed corpus, no dispatched row is sub-threshold and unescalated.

    Every corpus entry is replayed on all four tiers, so the per-tier floor R5.6 states
    is met in every example. The corpus-size floor R5.6 also states is an
    integration-scale obligation; the invariant it exists to check is what a property can
    carry, and it is checked here on every generated decision.
    """
    tiers_seen: set[DecisionTier] = set()
    sub_threshold = 0

    for confidence, blocked in corpus:
        case = _GateCase(threshold=threshold, confidence=confidence, blocked=blocked)
        for tier in TIERS:
            harness, decision = asyncio.run(ratify(case, tier))
            tiers_seen.add(tier)
            row = harness.audit.rows[-1]

            if confidence < harness.threshold:
                sub_threshold += 1
                # Escalated, and nothing enacted - on every tier, including the two the
                # guardrail engine never used to see.
                assert row.escalated_to_human is True
                assert decision.escalated_to_human is True
                assert row.execution_confirmations == []
                assert harness.transport.dispatches == []
                assert harness.waiter.awaited == [decision.decision_id]
            elif blocked:
                assert row.execution_confirmations == []
                assert harness.transport.dispatches == []
            else:
                assert len(harness.transport.dispatches) == 1

            # The invariant R5.6 names, stated directly: no row is both dispatched and
            # sub-threshold-without-escalation.
            enacted = has_dispatch_confirmation(decision.execution_confirmations)
            below = decision.confidence < harness.threshold
            assert not (enacted and below and not decision.escalated_to_human)

    assert tiers_seen == set(TIERS)
    assert sub_threshold == sum(1 for confidence, _ in corpus if confidence < threshold) * len(
        TIERS,
    )


# Feature: purpose-achievement-audit, Property 22: The confidence gate applies on every tier
@pytest.mark.slow
@given(case=gate_cases())
def test_both_routes_ratify_through_the_same_choke_point(case: _GateCase) -> None:
    """R5.7: ``_fast_path`` and ``_full_path`` reach dispatch only through ratification.

    Driven end to end on all four tiers, so "the fast path is gated too" is observed on
    the route rather than inferred from the choke point being called directly. The
    verdict is asserted identical across routes: if it were not, the tier router would
    still be deciding whether I-5 applies.
    """
    expected = gate_passes(case.confidence, case.threshold, blocked=case.blocked)

    for tier in TIERS:
        harness, decision, traversals = asyncio.run(run_route(case, tier))

        # Exactly one ratification per decision, on the tier the route was given.
        assert traversals == [tier]
        assert harness.guardrails.validations == 1
        assert decision.tier is tier
        assert decision.confidence == case.confidence

        dispatched = bool(harness.transport.dispatches)
        assert dispatched is expected

        if expected:
            assert decision.execution_confirmations == ["ok"]
            assert harness.trace.index_of(_VALIDATE_EVENT) < harness.trace.index_of(
                _DISPATCH_EVENT,
            )
        else:
            assert decision.execution_confirmations == []
            assert _DISPATCH_EVENT not in harness.trace.events
            assert "dispatch=withheld" in decision.audit_trace

        assert len(harness.audit.rows) == 1
        assert ratification_record(decision)["passed"] is expected


# Feature: purpose-achievement-audit, Property 22: The confidence gate applies on every tier
@pytest.mark.slow
@given(operation=st.sampled_from(PRIVILEGED_OPERATIONS))
def test_the_choke_point_is_the_only_site_of_a_privileged_operation(operation: str) -> None:
    """R5.7: for any privileged operation, its only call site is the choke point.

    The behavioural clauses above prove the two routes *do* traverse ratification. This
    clause is what makes "neither has a bypass" a statement about the module: quantified
    over the operations that gate or perform a dispatch, each has exactly one call site,
    and neither route is it. Derived from the AST, so a mention in a docstring or a
    comment is not mistaken for a call - the substring-gate defect class RC-3 reports.
    """
    sites = call_sites(operation)

    assert sites == frozenset({CHOKE_POINT}), (
        f"{operation} is called from {sorted(sites)}; only {CHOKE_POINT} may call it"
    )
    assert call_sites(f"self.{CHOKE_POINT}") == frozenset({"_fast_path", "_full_path"})


# Feature: purpose-achievement-audit, Property 22: The confidence gate applies on every tier
@pytest.mark.slow
@given(
    threshold=positive_thresholds(),
    tier=st.sampled_from(TIERS),
    approve=st.booleans(),
    blocked=st.booleans(),
)
def test_an_escalation_awaits_a_human_and_dispatches_nothing(
    threshold: float,
    tier: DecisionTier,
    approve: bool,
    blocked: bool,
) -> None:
    """R5.1: escalation awaits a human future, and no branch dispatches afterwards.

    Both human outcomes are driven. An approval must not enact the action either: the
    fail-closed half of I-5 is that ``escalate`` returns a decision and the choke point
    returns a withheld record, with no post-approval execution path.

    The premise this clause rests on is that the escalating branch is *reached*, so the
    boundary is drawn from :func:`positive_thresholds` and the confidence is pinned to
    zero: a confidence of zero is below every strictly positive boundary, independently
    of ``blocked``, so both the escalation and the BLOCK route are exercised while the
    escalation stays guaranteed. It is **not** below a boundary of ``0.0`` - there a
    clean decision dispatches and there is nothing to escalate, which is why the
    inclusive strategy the other clauses use would make this premise false rather than
    merely rare.
    """
    case = _GateCase(threshold=threshold, confidence=0.0, blocked=blocked)
    harness, decision = asyncio.run(ratify(case, tier, approve=approve))

    # A human was queued, and was handed a pending future rather than a settled one.
    assert harness.waiter.awaited == [decision.decision_id]
    assert harness.waiter.pending_when_awaited == [True]
    assert harness.trace.events == [_VALIDATE_EVENT, _HUMAN_EVENT]

    # Nothing was enacted, whichever way the human went.
    assert harness.transport.dispatches == []
    assert decision.escalated_to_human is True
    assert decision.execution_confirmations == []
    assert has_dispatch_confirmation(decision.execution_confirmations) is False
    assert "dispatch=withheld" in decision.audit_trace
    assert "withheld_by=guardrail_violation" in decision.audit_trace

    # The record never names an action that was not dispatched.
    override = decision.human_override
    assert override is not None
    if approve:
        assert override["action"] == "approve"
    else:
        assert override["dispatched"] is False

    # One append-only row, and it agrees with the returned decision.
    assert len(harness.audit.rows) == 1
    assert harness.audit.rows[-1].escalated_to_human is True
    assert harness.audit.rows[-1].execution_confirmations == []


if __name__ == "__main__":  # pragma: no cover - I-0: never run this module locally
    raise SystemExit(
        "Property 22 drives the real ConsensusProtocol and is @pytest.mark.slow; "
        "it runs in ci.yml::uplift-verify at HYPOTHESIS_PROFILE=heavy, never locally.",
    )
