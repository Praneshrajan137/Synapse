"""
SYNAPSE Orchestrator — Five-phase consensus protocol (~400 lines).

Phase 1 (COLLECTING):   Broadcast A2A proposal() to relevant agents.
Phase 2 (DEBATING):     LLM-mediated debate (Tier 3-4 only, max 3 rounds).
Phase 3 (ARBITRATING):  NSGA-II Pareto optimisation via pymoo.
Phase 4 (EXECUTING):    Dispatch per-agent actions, log audit, guardrails.
Phase 5 (LEARNING):     Meta-RL weight update, semantic cache update.

Tier 1-2 fast path (80 % of decisions): Phase 1 -> Phase 4 -> Phase 5.

Every tier reaches Phase 4 through one ratification choke point,
``_ratify_and_dispatch`` (ADR-054 D1): guardrails (I-6), the confidence floor
(I-5) and the audit append (I-4) apply on Tier 1 and Tier 2 exactly as they do on
Tier 3 and Tier 4. The Fast_Path used to call ``_phase_execute`` directly and was
therefore evaluated by neither the guardrail engine nor the HITL gate.

Three verdicts are consequential rather than decorative (ADR-054 D3, R13.4/R13.5/R13.8):
the Tier-4 twin's ``TwinVerdict`` withholds dispatch or escalates when its measured
disagreement exceeds the bound committed in
``infrastructure/quality/twin-verdict-bounds.yaml`` (never a literal here) while an
unavailable twin still degrades honestly and vetoes nothing (I-7); the recorded
``pareto_front`` is the set selection ran over, with the ratified action asserted a
member; and a debate round that changed no proposal value and no selection is stamped
advisory instead of being counted as though it moved the decision.
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final
from uuid import UUID, uuid4

import deal
import structlog
import yaml
from pydantic import BaseModel, ConfigDict, Field
from synapse_common.a2a_sdk import send_a2a_request
from synapse_common.metrics import (
    CONSENSUS_DEBATE_ROUNDS,
    CONSENSUS_DECISIONS_TOTAL,
    CONSENSUS_DURATION,
    CONSENSUS_PROPOSALS_RECEIVED,
    HITL_ESCALATIONS_TOTAL,
)
from synapse_common.models import (
    AgentProposal,
    ConsensusDecision,
    ContextMessage,
    DecisionTier,
    MessageStatus,
)
from synapse_common.schemas import SchemaValidationError, validate_agent_payload

from orchestrator.consensus.firehose_signals import emit_agent_metrics, emit_agent_signals
from orchestrator.consensus.models import ConflictReport, TierClassification
from orchestrator.consensus.pareto import (
    FRONT_INDEX_KEY,
    BindingSelection,
    SelectionFront,
    build_selection_front,
    run_pareto_arbitration,
    select_binding_action,
)
from orchestrator.guardrails.rules import execute_consensus, satisfies_confidence_floor
from orchestrator.state_machine import OrchestratorStateMachine

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from orchestrator.audit.logger import AuditLogger
    from orchestrator.config import OrchestratorConfig
    from orchestrator.consensus.tier_router import TierRouter
    from orchestrator.guardrails.rules import GuardrailEngine
    from orchestrator.hitl.escalation import HITLEscalation
    from orchestrator.llm.context_builder import ContextBuilder
    from orchestrator.llm.ollama_client import OllamaClient
    from orchestrator.llm.semantic_cache import SemanticDecisionCache
    from orchestrator.meta_rl.meta_agent import MetaRLAgent

logger = structlog.get_logger(__name__)

_JSON_KWARGS: dict[str, Any] = {"sort_keys": True, "separators": (",", ":")}

# Precision for rounding floats embedded in the append-only `audit_trace`. Fixing
# the precision keeps the binding-arbitration trace byte-stable across repeated
# executions and separate process invocations (R2.1/R2.3).
_AUDIT_FLOAT_PRECISION = 9


def _canonical_json(value: Any) -> str:
    """Serialize ``value`` to a canonical, byte-stable JSON string (I-14, R2.3)."""
    return json.dumps(value, **_JSON_KWARGS)


def _round_floats(mapping: dict[str, float]) -> dict[str, float]:
    """Round a ``str -> float`` mapping to a fixed precision for stable audit output."""
    return {key: round(float(val), _AUDIT_FLOAT_PRECISION) for key, val in mapping.items()}


# R4.1/R4.4: the LLM-mediated debate analysis is best-effort. Each attempt is
# bounded to 30s (R4.1) and retried at most once for a total of 2 calls per round
# (R4.4); after the attempts are exhausted the round degrades honestly (I-7) while
# rule-based concession continues (R4.2).
_DEBATE_LLM_TIMEOUT_S = 30.0
_DEBATE_LLM_MAX_ATTEMPTS = 2

AGENT_ENDPOINTS: dict[str, str] = {
    "demand_prophet": "http://demand-prophet:8001",
    "routing_navigator": "http://routing-navigator:8002",
    "inventory_sentinel": "http://inventory-sentinel:8003",
    "freshness_guardian": "http://freshness-guardian:8004",
    "pricing_oracle": "http://pricing-oracle:8005",
    "disruption_shield": "http://disruption-shield:8006",
    "supplier_trust": "http://supplier-trust:8007",
    "sustainability_agent": "http://sustainability-agent:8008",
}

# Each agent's own meta-RL objective (matches pareto._AGENT_TO_OBJECTIVE). The old
# `_phase_learn` matched these with a substring test that silently NEVER fired
# ("inventorysentinel" is not a substring of "inventoryfillrate"), so the learning
# signal was effectively empty. ADR-052 uses this explicit map.
_AGENT_OBJECTIVE: dict[str, str] = {
    "demand_prophet": "demand_accuracy",
    "routing_navigator": "route_efficiency",
    "inventory_sentinel": "inventory_fill_rate",
    "freshness_guardian": "freshness_score",
    "pricing_oracle": "pricing_revenue",
    "disruption_shield": "disruption_readiness",
    "supplier_trust": "supplier_reliability",
    "sustainability_agent": "carbon_efficiency",
}

# C7 (ADR-043): Tier-4 decisions are verified against the digital twin's
# Monte-Carlo what-if before execution (orchestrator→twin is no longer dead
# code). The twin exposes A2A `monte_carlo` (digital_twin/inference/serve.py);
# its response conforms to MonteCarloOutput
# (orchestrator/contracts/twin_simulation_contract.py). Bounded + degrades
# honestly (I-7) so a slow/absent twin never stalls or 504s the decision.
TWIN_ENDPOINT = "http://digital-twin:8009"
# PR-5: tunable so the synchronous twin-verify cap (~8s on a small CPU VM) can be
# matched to the deployment's compute instead of a hardcoded 1000-scenario run.
TWIN_SCENARIOS = int(os.environ.get("SYNAPSE_TWIN_SCENARIOS", "1000"))

REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[2]
#: The committed Tier-4 disagreement bound (ADR-054 D3, AD-13). The bound is read
#: from here and is never a literal in this module.
TWIN_BOUNDS_PATH: Final[Path] = (
    REPO_ROOT / "infrastructure" / "quality" / "twin-verdict-bounds.yaml"
)


class TwinVerdictConfigurationError(RuntimeError):
    """The committed Tier-4 twin bound is missing, malformed, or lies about I-7.

    Raised by :func:`load_twin_verdict_bounds`. Deliberately fail-closed: a
    deployment that declares a Tier-4 veto and cannot read its own bound must
    refuse to dispatch rather than skip the veto silently. A declared enforcement
    that does not enforce is the defect class ADR-054 exists to remove, so the
    honest failure mode is loud (I-7), and it mirrors task 8.3's
    ``GuardrailConfigurationError``.
    """


class SelectionIntegrityError(RuntimeError):
    """The ratified action is not a member of the recorded Pareto front (R13.5).

    A programming error, not a runtime condition: selection and the recorded front
    are both derived from one proposal list by pure functions, so a mismatch means
    the two have drifted. Raised rather than logged, because a decision whose
    recorded front does not contain the action it ratified is an audit record that
    misdescribes what happened - and it propagates out of ``run_consensus``, so
    nothing dispatches.
    """


class TwinAvailability(StrEnum):
    """Whether the Tier-4 twin produced a verdict at all (I-7).

    The values are the exact strings the pre-ADR-054 implementation stamped into
    ``audit_trace``, so the audit vocabulary is unchanged by this ADR - what
    changes is that the verdict now has a consequence.
    """

    VERIFIED = "twin_verified"
    UNAVAILABLE = "twin_unavailable"


class TwinExceedAction(StrEnum):
    """The recorded operator choice from ADR-054 D3's disjunction.

    D3 says a disagreement beyond the bound "withholds dispatch **or**
    escalates". Both are fail-closed - ``execution_confirmations`` stays empty
    either way - and which one applies is committed configuration, not a literal.
    """

    ESCALATE = "escalate"
    WITHHOLD = "withhold"


class TwinDisagreementBounds(BaseModel):
    """The committed Tier-4 disagreement bound (``twin-verdict-bounds.yaml``)."""

    model_config = ConfigDict(frozen=True)

    max_relative_disagreement: float
    relative_floor: float
    action_on_exceed: TwinExceedAction
    measured: bool


def load_twin_verdict_bounds(path: Path | None = None) -> TwinDisagreementBounds:
    """Load the committed Tier-4 bound (``encoding='utf-8'`` per E-S13-07).

    Reads ``infrastructure/quality/twin-verdict-bounds.yaml`` (AD-13). The file is
    read per Tier-4 verification rather than cached at import, so a reviewed bound
    edit takes effect without a process restart and a test can point the loader at
    its own file; one small YAML read sits comfortably inside the Tier-4 120s SLA.

    ``unavailable_action`` and ``not_comparable_action`` are both validated to read
    ``no_veto``: I-7 is pinned by the loader, not merely described in a comment, so
    the file cannot be edited into a configuration where a dead twin - or a twin
    that shares no KPI key with the consensus prediction - becomes a global Tier-4
    kill switch.

    Raises:
        TwinVerdictConfigurationError: the file is absent, unparseable, missing a
            key, or declares a veto on unavailability or on no comparison.
    """
    source = path if path is not None else TWIN_BOUNDS_PATH
    try:
        payload: Any = yaml.safe_load(source.read_text(encoding="utf-8"))
        section: Any = payload["tier4_disagreement"]
        for key in ("unavailable_action", "not_comparable_action"):
            declared = str(section[key])
            if declared != "no_veto":
                raise TwinVerdictConfigurationError(
                    f"{source}: {key}={declared!r} is not permitted; absence of a "
                    "verdict is not a negative verdict (I-7, ADR-054 D3)"
                )
        return TwinDisagreementBounds(
            max_relative_disagreement=float(section["max_relative_disagreement"]),
            relative_floor=float(section["relative_floor"]),
            action_on_exceed=TwinExceedAction(str(section["action_on_exceed"])),
            measured=bool(section["measured"]),
        )
    except TwinVerdictConfigurationError:
        raise
    except Exception as exc:
        raise TwinVerdictConfigurationError(f"{source}: unreadable Tier-4 bound: {exc}") from exc


def _numeric(value: Any) -> float | None:
    """Coerce a KPI value to a float, or ``None`` when it is not a number.

    ``bool`` is rejected explicitly: it is an ``int`` subclass, and comparing a
    flag against a Monte-Carlo mean would manufacture a disagreement.
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    numeric = float(value)
    if numeric != numeric or numeric in (float("inf"), float("-inf")):  # NaN / inf
        return None
    return numeric


def numeric_map(mapping: dict[str, Any]) -> dict[str, float]:
    """The numeric entries of ``mapping``, key-sorted, non-numerics dropped.

    Used to record the consensus prediction and the twin's KPI means as evidence
    without coercing a non-numeric field into a number it never was.
    """
    numeric: dict[str, float] = {}
    for key in sorted(mapping):
        value = _numeric(mapping[key])
        if value is not None:
            numeric[key] = value
    return numeric


def measure_twin_disagreement(
    consensus_prediction: dict[str, Any],
    twin_kpis: dict[str, Any],
    *,
    relative_floor: float,
) -> tuple[float | None, tuple[str, ...]]:
    """Measure the twin's disagreement with the consensus prediction (R13.4).

    Compares only the keys the consensus **itself** predicted: the numeric keys
    present in both the selected action and the twin's ``kpi_means``. Nothing is
    invented for a key the consensus never claimed, so the metric never fabricates
    a prediction in order to have something to disagree with (I-7).

    The metric is the maximum relative deviation over those keys::

        max_k |twin_k - consensus_k| / max(|consensus_k|, relative_floor)

    A maximum, so one contradicted KPI cannot be averaged away by agreeing ones;
    relative, so one committed bound spans KPI scales from ``spoilage_rate`` to
    ``orders_created``; floored, so a near-zero consensus value cannot report an
    infinite disagreement.

    Returns:
        ``(disagreement, compared_keys)``. ``disagreement`` is ``None`` when no key
        is comparable - which is *not* a disagreement and never a veto (ADR-054 D3,
        ``not_comparable_action``).

    Pure: no I/O and no state, so the bound comparison is unit- and
    property-testable without the protocol or the twin.
    """
    compared: list[str] = []
    deviations: list[float] = []

    for key in sorted(consensus_prediction):
        predicted = _numeric(consensus_prediction[key])
        simulated = _numeric(twin_kpis.get(key))
        if predicted is None or simulated is None:
            continue
        compared.append(key)
        deviations.append(abs(simulated - predicted) / max(abs(predicted), relative_floor))

    if not deviations:
        return None, ()
    return max(deviations), tuple(compared)


class TwinVerdict(BaseModel):
    """The Tier-4 twin's verdict on a selected action (ADR-054 D3, R13.4).

    Frozen: this is **evidence**. The ratification choke point reads it to decide
    whether to dispatch, and the audit row records it; neither may edit the
    verdict it is judging.

    Before ADR-054 the twin's answer reached ``audit_trace`` and nothing else -
    the twin was consulted at the most consequential tier and could not object.
    A verdict whose ``exceeds_bound`` is true now withholds dispatch or escalates.
    """

    model_config = ConfigDict(frozen=True)

    availability: TwinAvailability
    #: The committed bound in force when this verdict was measured.
    bound: float
    action_on_exceed: TwinExceedAction
    #: ``None`` when the twin was unavailable, or available with no comparable KPI.
    #: Absence of a measurement is never treated as a negative verdict (I-7).
    disagreement: float | None = None
    compared_kpis: tuple[str, ...] = ()
    consensus_kpis: dict[str, float] = Field(default_factory=dict)
    twin_kpis: dict[str, float] = Field(default_factory=dict)
    n_scenarios: int | None = None
    error: str | None = None
    #: True when the committed bound was set from an observed disagreement
    #: distribution. False means the bound is honestly wide (ADR-054 ratchet).
    bound_measured: bool = False

    @property
    def available(self) -> bool:
        """Whether the twin answered at all."""
        return self.availability is TwinAvailability.VERIFIED

    @property
    def comparable(self) -> bool:
        """Whether a disagreement could be measured against a consensus prediction."""
        return self.disagreement is not None

    @property
    def exceeds_bound(self) -> bool:
        """Whether this verdict vetoes dispatch (R13.4).

        False whenever no disagreement was measured. An unreachable or slow twin,
        and a twin that shares no KPI key with the consensus prediction, both
        degrade honestly and veto nothing: absence of a verdict is not a negative
        verdict, and a dead twin must not become a global Tier-4 kill switch
        (I-7, ADR-054 D3).
        """
        return self.disagreement is not None and self.disagreement > self.bound

    def as_context(self) -> dict[str, Any]:
        """The append-only record of this verdict (I-14).

        Floats are rounded to the fixed audit precision so a replayed decision
        produces byte-identical context and trace entries (R2.1/R2.3).
        """
        return {
            "verdict": self.availability.value,
            "available": self.available,
            "comparable": self.comparable,
            "disagreement": (
                None
                if self.disagreement is None
                else round(self.disagreement, _AUDIT_FLOAT_PRECISION)
            ),
            "bound": round(self.bound, _AUDIT_FLOAT_PRECISION),
            "bound_measured": self.bound_measured,
            "exceeds_bound": self.exceeds_bound,
            "action_on_exceed": self.action_on_exceed.value,
            "compared_kpis": list(self.compared_kpis),
            "consensus_kpis": _round_floats(self.consensus_kpis),
            "twin_kpis": _round_floats(self.twin_kpis),
            "n_scenarios": self.n_scenarios,
            "error": self.error,
        }

    def veto_reason(self) -> str:
        """The reason string recorded when this verdict withholds dispatch (R13.4).

        ASCII only, and it names both measured numbers so the audit row and the
        escalation payload say *why* the twin objected rather than that it did.
        Returns ``""`` when this verdict vetoes nothing.
        """
        if self.disagreement is None or not self.exceeds_bound:
            return ""
        return (
            f"twin_disagreement:{round(self.disagreement, _AUDIT_FLOAT_PRECISION)}"
            f">bound:{round(self.bound, _AUDIT_FLOAT_PRECISION)}"
            f" on {','.join(self.compared_kpis)}"
        )

    def trace_lines(self) -> list[str]:
        """The ``audit_trace`` entries for this verdict.

        ``twin=<availability>`` is unchanged from the pre-ADR-054 stamp - the
        audit vocabulary does not move - and the disagreement, the bound, and the
        consequence are recorded beside it. R13.4 forbids recording the
        disagreement in ``audit_trace`` *alone*, not recording it there at all.
        """
        lines = [f"twin={self.availability.value}"]
        if self.disagreement is None:
            lines.append("twin_disagreement=not_comparable")
            return lines
        lines.append(f"twin_disagreement={round(self.disagreement, _AUDIT_FLOAT_PRECISION)}")
        lines.append(f"twin_bound={round(self.bound, _AUDIT_FLOAT_PRECISION)}")
        if self.exceeds_bound:
            lines.append(f"twin_veto={self.action_on_exceed.value}")
        return lines


class DebateRoundChange(BaseModel):
    """Whether one debate round changed any proposal value (R13.8).

    Frozen: it is a record of what a completed round did, written once by
    ``_phase_debate`` and read by ``_record_debate_consequence``.
    """

    model_config = ConfigDict(frozen=True)

    round_number: int
    values_changed: bool
    revised_agents: tuple[str, ...] = ()


def changed_proposal_values(
    before: list[AgentProposal],
    after: list[AgentProposal],
) -> tuple[str, ...]:
    """The agents whose payload or utility a concession round actually changed (R13.8).

    Compares **values**, not the ``status`` an agent reported: a ``"revised"``
    response that returns a byte-identical payload and the same utility changed
    nothing, and R13.8 asks whether the round changed a proposal *value*. Pure, so
    the advisory rule is decidable without the protocol.

    A length mismatch cannot arise from ``_run_concession_round`` (it emits one
    proposal per input) but is reported as "everything changed" rather than
    silently zipped short, because a shortened round is not an unchanged round.
    """
    if len(before) != len(after):
        return tuple(str(p.agent_name) for p in after)
    changed: list[str] = []
    for prior, revised in zip(before, after, strict=True):
        if prior.payload != revised.payload or float(prior.utility_score) != float(
            revised.utility_score
        ):
            changed.append(str(revised.agent_name))
    return tuple(changed)


class ConsensusProtocol:
    """Five-phase multi-agent consensus engine."""

    def __init__(
        self,
        config: OrchestratorConfig,
        tier_router: TierRouter,
        guardrails: GuardrailEngine,
        audit_logger: AuditLogger,
        hitl_escalation: HITLEscalation,
        context_builder: ContextBuilder,
        ollama_client: OllamaClient,
        meta_rl: MetaRLAgent,
        semantic_cache: SemanticDecisionCache,
        kafka_producer: Any = None,
        world_observer: Callable[[str], Awaitable[dict[str, Any] | None]] | None = None,
    ) -> None:
        self._config = config
        self._tier_router = tier_router
        self._guardrails = guardrails
        self._audit = audit_logger
        self._hitl = hitl_escalation
        self._ctx_builder = context_builder
        self._ollama = ollama_client
        self._meta_rl = meta_rl
        self._semantic_cache = semantic_cache
        self._kafka = kafka_producer
        # ADR-052: perceive the realized world to learn from reality (not predicted
        # utility). Async (city -> WorldState dict | None); None ⇒ degrade honestly.
        self._world_observer = world_observer
        self._fsm = OrchestratorStateMachine()
        # ADR-051: correlation id for the live cognition stream. Generated at run
        # start so the phase events and the final ConsensusDecision share one id —
        # the live stream and the recorded Council Theater reconstruction line up.
        self._decision_id: UUID | None = None
        self._city: str | None = None

        self._context_messages: list[ContextMessage] = []
        self._tool_call_count: int = 0
        # R13.8: one record per completed debate round, saying whether that round
        # changed any proposal value. Read once selection is known, so a round that
        # moved nothing is stamped advisory rather than recorded as consequential.
        self._debate_rounds_log: list[DebateRoundChange] = []

    # ── Context management (I-14: append-only) ─────────────────────────

    @deal.pre(lambda self, msg: isinstance(msg, ContextMessage))
    def _append_context(self, msg: ContextMessage) -> int:
        """Append-only context modification.  Returns new length."""
        self._context_messages.append(msg)
        self._tool_call_count += 1
        if self._tool_call_count % self._config.recitation_interval == 0:
            self._append_recitation()
        return len(self._context_messages)

    def _append_recitation(self) -> None:
        """Push objective recitation into context (ADR-024)."""
        recitation = ContextMessage(
            source="orchestrator",
            content={
                "type": "objective_recitation",
                "current_phase": self._fsm.state.value,
                "proposals_received": sum(
                    1 for m in self._context_messages if m.source != "orchestrator"
                ),
                "tool_calls_completed": self._tool_call_count,
                "active_objective": self._fsm.ACTIVE_OBJECTIVE,
                "active_constraints": self._fsm.ACTIVE_CONSTRAINTS,
            },
        )
        self._context_messages.append(recitation)

    # ── Live cognition telemetry (ADR-051) ──────────────────────────────

    def _emit_phase(
        self,
        phase: str,
        *,
        agent_name: str | None = None,
        round_: int | None = None,
        event: str | None = None,
    ) -> None:
        """Publish one FSM phase-transition event to ``synapse.orchestrator.phase``.

        This is the live Cognition Channel: the firehose streams the council's
        *reasoning* (collecting → debating → arbitrating → executing → learning),
        not only the final verdict, so the AUX grammar can show thinking/debating
        honestly from REAL events. Fire-and-forget and fully guarded — a missing
        or slow producer NEVER blocks or fails the decision (I-7). Correlated to
        the eventual ConsensusDecision by ``decision_id``.
        """
        if self._kafka is None or self._decision_id is None:
            return
        payload: dict[str, Any] = {
            "type": "cognition_phase",
            "decision_id": str(self._decision_id),
            "phase": phase,
            "ts": datetime.now(UTC).isoformat(),
        }
        if self._city is not None:
            payload["city"] = self._city
        if agent_name is not None:
            payload["agent_name"] = agent_name
        if round_ is not None:
            payload["round"] = round_
        if event is not None:
            payload["event"] = event
        try:
            self._kafka.produce(
                "synapse.orchestrator.phase",
                value=payload,
                key=str(self._decision_id),
            )
        except Exception as exc:  # noqa: BLE001 — telemetry is best-effort (I-7)
            logger.warning("cognition_phase_emit_failed", phase=phase, error=str(exc))

    # ── Main entry point ────────────────────────────────────────────────

    async def run_consensus(
        self,
        decision_request: dict[str, Any],
    ) -> ConsensusDecision:
        """Execute the full consensus lifecycle for a single decision."""
        self._reset()
        # ADR-051: stamp the correlation id + city up front so every phase event
        # carries them and the final decision reuses the same id.
        self._decision_id = uuid4()
        self._city = decision_request.get("city") if isinstance(decision_request, dict) else None
        start = time.monotonic()

        classification = self._tier_router.classify(decision_request)
        tier = classification.tier

        self._append_context(
            ContextMessage(
                source="orchestrator",
                content={
                    "type": "decision_request",
                    "tier": tier.value,
                    "request": decision_request,
                },
            )
        )

        try:
            if tier in (DecisionTier.TIER_1, DecisionTier.TIER_2):
                decision = await self._fast_path(decision_request, tier)
            else:
                decision = await self._full_path(decision_request, tier, classification)

            elapsed = time.monotonic() - start
            CONSENSUS_DURATION.labels(tier=tier.value).observe(elapsed)
            CONSENSUS_DECISIONS_TOTAL.labels(tier=tier.value, outcome="success").inc()
            return decision

        except Exception:
            CONSENSUS_DECISIONS_TOTAL.labels(tier=tier.value, outcome="error").inc()
            self._fsm.transition("exception_raised")
            raise

    # ── Tier 1-2 fast path ──────────────────────────────────────────────

    async def _fast_path(
        self,
        request: dict[str, Any],
        tier: DecisionTier,
    ) -> ConsensusDecision:
        proposals = await self._phase_collect(request, tier)

        fast_best = max(proposals, key=lambda p: p.utility_score) if proposals else None
        decision = self._build_decision(
            proposals=proposals,
            tier=tier,
            phase_reached=4,
            pareto_weights=self._meta_rl.get_weights(self._system_state()),
            fast_best=fast_best,
        )
        # ADR-054 D1/D2: the fast path ratifies through the same choke point as the
        # full path, so I-5 and I-6 are not decided by the tier router (R5.1, R5.7).
        decision = await self._ratify_and_dispatch(decision, tier=tier)
        await self._phase_learn(decision)
        return decision

    # ── Tier 3-4 full path ──────────────────────────────────────────────

    async def _full_path(
        self,
        request: dict[str, Any],
        tier: DecisionTier,
        classification: TierClassification,
    ) -> ConsensusDecision:
        proposals = await self._phase_collect(request, tier)
        # R13.8: kept so the debate's consequence is decidable - the same knee
        # weights applied to the pre-debate and post-debate proposals answer
        # "did the debate change the selection?" without guessing.
        pre_debate = list(proposals)

        debate_rounds = 0
        conflict = self._detect_conflicts(proposals)
        if conflict.has_conflict:
            proposals, debate_rounds = await self._phase_debate(
                proposals,
                tier,
                classification,
            )

        pareto_result = await self._phase_arbitrate(proposals)
        weights = pareto_result["selected_weights"]

        # Binding Pareto arbitration (R1.1): apply the knee weights to the
        # per-objective proposal utilities and let that selection — not a raw
        # `utility_score` argmax — drive the ratified action on the full path.
        selection = select_binding_action(proposals, weights)
        self._append_context(
            ContextMessage(
                source="orchestrator",
                content={
                    "type": "binding_selection",
                    "selected_agent": selection.selected_agent,
                    "selected_index": selection.selected_index,
                    "weighted_scores": _round_floats(selection.weighted_scores),
                    "excluded_agents": list(selection.excluded_agents),
                    "tie_break_applied": selection.tie_break_applied,
                    "tie_break_reason": selection.tie_break_reason,
                },
            )
        )

        # R13.8: stamp every round that changed no proposal value and no selection
        # advisory. Done before the decision is built so the mark is inside the
        # decision's own append-only context.
        advisory_rounds = self._record_debate_consequence(
            pre_debate=pre_debate,
            post_debate=proposals,
            weights=weights,
            selection=selection,
        )

        decision = self._build_decision(
            proposals=proposals,
            tier=tier,
            phase_reached=4,
            pareto_weights=weights,
            debate_rounds=debate_rounds,
            selection=selection,
            advisory_rounds=advisory_rounds,
        )

        # ADR-043/C7: record whether the decision rested on any degraded agent input
        # (a real model vs. an honest fallback), so the audit trail reflects substance.
        self._record_input_provenance(proposals)

        # C7: at the top tier the selected action is verified against the digital
        # twin's Monte-Carlo what-if before execution — the twin is no longer dead
        # code at Tier 4. Degrades honestly if the twin is unreachable (I-7).
        # ADR-054 D3: the verdict travels to the choke point, where a disagreement
        # beyond the committed bound withholds dispatch or escalates (R13.4). It is
        # no longer stamped into `audit_trace` and then dropped.
        twin_verdict: TwinVerdict | None = None
        if tier == DecisionTier.TIER_4:
            decision, twin_verdict = await self._phase_twin_verify(decision)

        decision = await self._ratify_and_dispatch(
            decision,
            tier=tier,
            twin_verdict=twin_verdict,
        )

        await self._phase_learn(decision)
        return decision

    # ── Dispatch ratification choke point (ADR-054 D1) ──────────────────

    async def _ratify_and_dispatch(
        self,
        decision: ConsensusDecision,
        *,
        tier: DecisionTier,
        twin_verdict: TwinVerdict | None = None,
    ) -> ConsensusDecision:
        """The single path from a built decision to a dispatched action.

        Every tier traverses this method, so I-5 (confidence-gated execution) and
        I-6 (hard guardrails cannot be overridden) are properties of the running
        system rather than properties of one route. Recorded in ADR-054 (D1/D2):
        ``_fast_path`` used to reach ``_phase_execute`` directly and was therefore
        evaluated by neither the guardrail engine nor the HITL gate, which made the
        tier router the thing that decided whether I-5 applied (R5.1, R5.2, R5.7).

        This is the only caller of
        :meth:`~orchestrator.guardrails.rules.GuardrailEngine.validate_decision`,
        :meth:`~orchestrator.hitl.escalation.HITLEscalation.escalate`,
        :func:`~orchestrator.guardrails.rules.execute_consensus` - which puts that
        function's ``@deal.pre`` (I-5) / ``@deal.post`` (I-4) contract on the
        production path instead of leaving it reachable only from tests (R13.7) -
        and :meth:`_phase_execute`.

        Order of operations (ADR-054 D1, amended by task 12.1a):

        1. ``validate_decision``, on Tier 1 and Tier 2 as well as Tier 3/4.
        2. Snapshot the boundary in force and re-check the I-5 dispatch precondition
           through :func:`~orchestrator.guardrails.rules.satisfies_confidence_floor` -
           the same predicate ``execute_consensus``'s ``@deal.pre`` uses - so that
           precondition is decided *before* anything is appended.
        3. Apply the twin verdict (see ``twin_verdict``).
        4. Not passed -> ``escalate``, which awaits a human future and dispatches
           nothing, then record the withheld dispatch. A twin veto configured as
           ``withhold`` records the withheld dispatch without queueing a human.
        5. Passed -> append the audit row, ``execute_consensus``, ``_phase_execute``.

        A BLOCK violation or a sub-threshold confidence therefore withholds dispatch
        on every tier and leaves ``execution_confirmations`` empty (R5.1, R5.2). The
        audit append precedes ``execute_consensus`` because that function's
        ``@deal.post`` asserts ``audit_id is not None``: under I-4 the decision is on
        the audit trail *before* the world is mutated. ``_phase_execute`` reuses the
        id, so exactly one row is appended per decision, and the canonical row is
        byte-for-byte what it was before this change (``make_canonical_row`` is not
        touched - I-4 is byte-pinned).

        Step 2 is why the contract's floor is a *parameter* rather than a literal. The
        precondition used to hardcode ``0.7`` while ADR-054 D4 / R5.4 made the boundary
        reloadable, so a reload below ``0.7`` let a decision in ``[threshold, 0.7)``
        pass ``validate_decision`` and then trip ``PreContractError`` at step 5 - after
        the append. Failing closed was right; failing *after* an irretractable row was
        not, and a crash is not one of I-7's honest outcomes. The boundary is now read
        once for both checks, so the two cannot disagree and no contract fires after an
        append.

        Args:
            decision: the built decision awaiting ratification.
            tier: the routed tier, recorded with the ratification outcome.
            twin_verdict: the Tier-4 twin's verdict, or ``None`` on a tier that
                consults no twin. A verdict whose measured disagreement exceeds the
                **committed** bound (``infrastructure/quality/twin-verdict-bounds.yaml``,
                AD-13 - never a literal here) withholds dispatch: it escalates when
                the file declares ``action_on_exceed: escalate`` and records the
                withheld dispatch with no human queued when it declares
                ``withhold``. Both leave ``execution_confirmations`` empty.
                An unavailable twin, and a twin with no comparable KPI, veto
                **nothing** - ``TwinVerdict.exceeds_bound`` is false whenever no
                disagreement was measured, so a twin outage cannot become a global
                Tier-4 kill switch (I-7, ADR-054 D3).
        """
        passed, violations = self._guardrails.validate_decision(decision)

        # Task 12.1a. The boundary in force is read **once**, before anything is
        # appended, and this one snapshot judges both the pre-flight here and
        # `execute_consensus`'s @deal.pre below. Reading it twice would leave the window
        # this repair closes: a reload landing between the two reads made the contract
        # raise `PreContractError` *after* the audit row was appended, and an
        # append-only row cannot be retracted (I-4) - the operator saw a crash plus a
        # permanent row describing a dispatch that never happened. A decision below the
        # floor is a recorded withhold with a stated reason (I-7), never an exception
        # out of this method.
        confidence_floor = self._guardrails.confidence_threshold
        if passed and not satisfies_confidence_floor(
            decision,
            confidence_floor=confidence_floor,
        ):
            passed = False
            # A new list, not an append: `violations` belongs to the engine's verdict.
            violations = [
                *violations,
                f"Confidence {decision.confidence:.3f} below the dispatch floor "
                f"{confidence_floor} in force, and no human was escalated (I-5)",
            ]

        # ADR-054 D3. The bound lives in the verdict because `_phase_twin_verify`
        # read it from committed configuration; nothing here supplies a number.
        reasons = list(violations)
        twin_veto = False
        if twin_verdict is not None and twin_verdict.exceeds_bound:
            twin_veto = True
            reasons.append(twin_verdict.veto_reason())
            logger.warning(
                "twin_veto_applied",
                decision_id=str(decision.decision_id),
                tier=tier.value,
                disagreement=twin_verdict.disagreement,
                bound=twin_verdict.bound,
                bound_measured=twin_verdict.bound_measured,
                action=twin_verdict.action_on_exceed.value,
            )

        self._append_context(
            ContextMessage(
                source="orchestrator",
                content={
                    "type": "dispatch_ratification",
                    "tier": tier.value,
                    "confidence": decision.confidence,
                    "passed": passed,
                    "violations": list(violations),
                    # True unconditionally from task 8.7 on: the veto is in force at
                    # this choke point. `twin_verdict` is null on a tier that
                    # consults no twin, which is an absent verdict and not a veto.
                    "twin_verdict_enforced": True,
                    "twin_verdict": None if twin_verdict is None else twin_verdict.as_context(),
                    "twin_veto": twin_veto,
                    "reasons": reasons,
                },
            )
        )

        if not passed or twin_veto:
            # A guardrail failure always queues a human (unchanged). A twin veto
            # queues one only when the committed `action_on_exceed` says so; the
            # `withhold` setting records the withheld dispatch with no human.
            escalates = (
                not passed
                or twin_verdict is None
                or twin_verdict.action_on_exceed is TwinExceedAction.ESCALATE
            )
            reason = "guardrail_violation" if not passed else "twin_disagreement"
            logger.warning(
                "dispatch_withheld",
                decision_id=str(decision.decision_id),
                tier=tier.value,
                confidence=decision.confidence,
                reason=reason,
                reasons=reasons,
                twin_veto=twin_veto,
                escalated=escalates,
            )
            if escalates:
                HITL_ESCALATIONS_TOTAL.labels(reason=reason).inc()
                withheld = await self._hitl.escalate(decision, reasons)
            else:
                withheld = decision
            return await self._record_withheld_dispatch(withheld, reasons, reason=reason)

        # I-4 first: the row exists before the action does. The id it returns is what
        # satisfies `execute_consensus`'s @deal.post, and `_phase_execute` reuses it.
        # The @deal.pre is handed the same floor the pre-flight above already applied, so
        # it cannot fail here by construction - it is a backstop against a future route
        # that reaches this line without ratifying, not a live crash risk.
        audit_id = await self._audit.log_decision(decision)
        ratified = execute_consensus(
            decision.model_copy(update={"audit_id": audit_id}),
            confidence_floor=confidence_floor,
        )
        return await self._phase_execute(ratified)

    async def _record_withheld_dispatch(
        self,
        decision: ConsensusDecision,
        violations: list[str],
        *,
        reason: str = "guardrail_violation",
    ) -> ConsensusDecision:
        """Append the audit row for a decision whose dispatch was withheld.

        ``escalate`` awaits a human future and dispatches nothing - unchanged, and it
        is what makes ADR-054 D2 fail-closed rather than fail-open - so the row says
        exactly that: ``escalated`` is true (set by the escalator, never asserted
        here) and ``execution_confirmations`` is empty (R5.1, R5.2). Nothing is
        executed after a human approves either.

        The empty list is load-bearing beyond this method: the HITL timeout record
        derives ``dispatched`` from ``execution_confirmations``, so a fabricated
        confirmation here would make that record claim an action nobody took.

        Args:
            decision: the decision whose dispatch was withheld, already escalated
                when a human was queued.
            violations: every reason dispatch was withheld - guardrail violations
                and, on Tier 4, the twin's veto reason (R13.4).
            reason: which gate withheld it, recorded as ``withheld_by=`` so a reader
                can tell a guardrail BLOCK from a twin disagreement without parsing
                the reason strings.
        """
        withheld = decision.model_copy(
            update={
                "execution_confirmations": [],
                "context_messages": list(self._context_messages),
                "audit_trace": [
                    *decision.audit_trace,
                    "dispatch=withheld",
                    f"withheld_by={reason}",
                    f"violations={len(violations)}",
                ],
            },
        )
        audit_id = await self._audit.log_decision(withheld)
        return withheld.model_copy(
            update={
                "audit_id": audit_id,
                "audit_trace": [*withheld.audit_trace, f"audit_id={audit_id}"],
            },
        )

    # ── Phase 1: Proposal collection ────────────────────────────────────

    async def _phase_collect(
        self,
        request: dict[str, Any],
        tier: DecisionTier,
    ) -> list[AgentProposal]:
        self._fsm.transition("decision_request_received")
        self._emit_phase("collecting")

        tasks = {
            name: self._request_proposal(name, url, request, tier)
            for name, url in AGENT_ENDPOINTS.items()
        }
        results = await asyncio.gather(
            *tasks.values(),
            return_exceptions=True,
        )

        proposals: list[AgentProposal] = []
        for name, result in zip(tasks.keys(), results, strict=False):
            if isinstance(result, AgentProposal):
                proposals.append(result)
                CONSENSUS_PROPOSALS_RECEIVED.labels(agent_name=name).inc()
                self._append_context(
                    ContextMessage(
                        source=name,
                        content=json.loads(result.to_deterministic_json()),
                    )
                )
                self._emit_phase("collecting", agent_name=name, event="proposed")
            else:
                self._append_context(
                    ContextMessage(
                        source=name,
                        content={"error": str(result)},
                        status=MessageStatus.ERROR,
                    )
                )
                self._emit_phase("collecting", agent_name=name, event="failed")
        # Phase 1.5 (#64): event-source each agent's domain output onto its
        # firehose topic (ADR-038) so the FE pricing/demand/freshness surfaces
        # show live data. Pre-debate proposals = "what each agent proposed".
        # Best-effort (I-7) — never blocks consensus. (Coexists with the ADR-051
        # cognition phase events above.)
        emit_agent_signals(self._kafka, proposals)
        # ADR-053: live per-agent telemetry onto synapse.metrics.agent (the
        # `metric` firehose channel's producer). Best-effort (I-7).
        emit_agent_metrics(self._kafka, proposals)
        return proposals

    async def _request_proposal(
        self,
        agent_name: str,
        agent_url: str,
        request: dict[str, Any],
        tier: DecisionTier,
    ) -> AgentProposal:
        # PR-4 (P1.6): tier-aware timeout (I-10 SLAs: T1=2s … T4=120s) instead of a
        # single fixed proposal_timeout for every tier — so a fast tier fails fast on
        # a dead agent rather than waiting the worst-case budget.
        response = await send_a2a_request(
            target_url=agent_url,
            method="proposal",
            params={"decision_context": request},
            tier=tier,
        )
        if response.error:
            raise RuntimeError(f"{agent_name}: {response.error}")
        return AgentProposal.model_validate(response.result)

    # ── Phase 2: LLM-mediated debate ────────────────────────────────────

    async def _phase_debate(
        self,
        proposals: list[AgentProposal],
        tier: DecisionTier,
        classification: TierClassification,
    ) -> tuple[list[AgentProposal], int]:
        self._fsm.transition("all_proposals_received")

        model = classification.model
        rounds = 0

        for round_num in range(1, self._config.debate_max_rounds + 1):
            rounds = round_num
            self._emit_phase("debating", round_=round_num)

            if model:
                content, degraded_reason = await self._run_debate_llm_analysis(model, tier)
                if degraded_reason is not None:
                    # R4.1/R4.3: the LLM is unavailable after the bounded attempts.
                    # DEGRADE the round honestly — record the failure reason — but
                    # do NOT break: concession is LLM-independent (R4.2), so the
                    # round still runs concession and the convergence check below,
                    # and arbitration proceeds with the most-recent proposals.
                    logger.warning(
                        "debate_llm_unavailable", round=round_num, reason=degraded_reason
                    )
                    self._append_context(
                        ContextMessage(
                            source="orchestrator",
                            content={
                                "type": "debate_round",
                                "round": round_num,
                                "llm_analysis": "",
                                "degraded": True,
                                "degraded_reason": degraded_reason,
                            },
                            status=MessageStatus.ERROR,
                        )
                    )
                else:
                    self._append_context(
                        ContextMessage(
                            source="orchestrator",
                            content={
                                "type": "debate_round",
                                "round": round_num,
                                "llm_analysis": content,
                                "degraded": False,
                            },
                        )
                    )

            # R3.1/R3.8: rule-based concession round. Invoke each agent's
            # `debate_respond` over A2A and replace a proposal ONLY with a
            # `"revised"` response whose payload re-validates schema-side;
            # otherwise retain the prior proposal. Concession is LLM-independent
            # (R4.2) so it runs whether or not an LLM model mediates this round.
            before_round = proposals
            proposals = await self._run_concession_round(before_round, tier, round_num)

            # R13.8: record what this round actually changed. A round whose agents
            # all maintained their position - or "revised" to the identical payload
            # and utility - changed no proposal value, and once selection is known
            # `_record_debate_consequence` stamps it advisory.
            revised_agents = changed_proposal_values(before_round, proposals)
            self._debate_rounds_log.append(
                DebateRoundChange(
                    round_number=round_num,
                    values_changed=bool(revised_agents),
                    revised_agents=revised_agents,
                )
            )

            # R3.4: stop once the (possibly revised) proposals converge.
            if self._check_convergence(proposals):
                break

        CONSENSUS_DEBATE_ROUNDS.labels(tier=tier.value).observe(rounds)
        return proposals, rounds

    async def _run_debate_llm_analysis(
        self,
        model: str,
        tier: DecisionTier,
    ) -> tuple[str | None, str | None]:
        """Run the best-effort, LLM-mediated analysis for one debate round.

        Each attempt is bounded to ``_DEBATE_LLM_TIMEOUT_S`` via ``asyncio.wait_for``
        (R4.1) and the call is retried at most once for a total of
        ``_DEBATE_LLM_MAX_ATTEMPTS`` attempts (R4.4). Returns ``(content, None)`` on
        success or ``(None, reason)`` when the LLM is unavailable after the attempts
        are exhausted, capturing the failure reason honestly (I-7) — ``"timeout"``
        on a timed-out attempt, otherwise the exception string.
        """
        messages = self._ctx_builder.build_ollama_messages(self._context_messages)
        mask = self._tier_router.get_tool_mask(tier)
        last_reason = "llm_unavailable"
        for attempt in range(1, _DEBATE_LLM_MAX_ATTEMPTS + 1):
            try:
                llm_response = await asyncio.wait_for(
                    self._ollama.chat(
                        model=model,
                        messages=messages,
                        prefill=mask.get("prefill"),
                    ),
                    timeout=_DEBATE_LLM_TIMEOUT_S,
                )
            except TimeoutError:
                last_reason = "timeout"
                logger.warning(
                    "debate_llm_timeout",
                    attempt=attempt,
                    timeout_s=_DEBATE_LLM_TIMEOUT_S,
                )
                continue
            except Exception as exc:  # noqa: BLE001 — LLM is best-effort (I-7)
                last_reason = str(exc) or exc.__class__.__name__
                logger.warning("debate_llm_error", attempt=attempt, error=last_reason)
                continue
            content = llm_response.get("message", {}).get("content", "")
            return str(content), None
        return None, last_reason

    async def _run_concession_round(
        self,
        proposals: list[AgentProposal],
        tier: DecisionTier,
        round_num: int,
    ) -> list[AgentProposal]:
        """Run one rule-based concession round and return the next round's proposals.

        Each conflicting agent's ``debate_respond`` is invoked over A2A (mirroring
        ``_request_proposal``); the orchestrator replaces an agent's prior proposal
        only with a ``"revised"`` response whose payload passes ``proto/domain/``
        schema validation (defense-in-depth re-validation, R3.1/R3.10/I-3), and
        otherwise retains the prior proposal. The round's revisions are appended to
        the append-only context (R3.8/I-14).
        """
        if len(proposals) < 2:
            return proposals

        round_utilities = [p.utility_score for p in proposals]
        tasks = [
            self._request_debate_response(
                str(p.agent_name),
                AGENT_ENDPOINTS.get(str(p.agent_name), ""),
                p,
                tier,
                round_num,
                round_utilities,
            )
            for p in proposals
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        revised: list[AgentProposal] = []
        revisions: list[dict[str, Any]] = []
        for prior, result in zip(proposals, results, strict=False):
            new_proposal, record = self._apply_debate_result(prior, result)
            revised.append(new_proposal)
            revisions.append(record)

        self._append_context(
            ContextMessage(
                source="orchestrator",
                content={
                    "type": "debate_revisions",
                    "round": round_num,
                    "revisions": revisions,
                },
            )
        )
        return revised

    async def _request_debate_response(
        self,
        agent_name: str,
        agent_url: str,
        proposal: AgentProposal,
        tier: DecisionTier,
        round_num: int,
        round_utilities: list[float],
    ) -> dict[str, Any]:
        """Invoke one agent's ``debate_respond`` over A2A (mirrors ``_request_proposal``).

        Passes the params the shared ``build_debate_response`` handler expects: the
        round number, the current round's utility scores, this agent's current
        ``utility_score``, and its current payload so the agent can honestly revise it.
        """
        response = await send_a2a_request(
            target_url=agent_url,
            method="debate_respond",
            params={
                "round_number": round_num,
                "round_utilities": round_utilities,
                "current_utility_score": proposal.utility_score,
                "current_payload": proposal.payload,
            },
            tier=tier,
        )
        if response.error:
            raise RuntimeError(f"{agent_name}: {response.error}")
        return response.result or {}

    def _apply_debate_result(
        self,
        prior: AgentProposal,
        result: dict[str, Any] | BaseException,
    ) -> tuple[AgentProposal, dict[str, Any]]:
        """Reconstruct the next-round proposal from one ``debate_respond`` result.

        Returns ``(proposal, record)`` where ``proposal`` is the honestly revised
        ``AgentProposal`` when the response is a schema-valid ``"revised"`` reply,
        otherwise the unchanged prior proposal (R3.1/R3.10). ``record`` is the
        append-only audit entry describing the outcome for this agent (R3.8).
        """
        agent_name = str(prior.agent_name)

        # An A2A failure honestly retains the prior proposal rather than fabricating
        # a revision (I-7).
        if isinstance(result, BaseException):
            return prior, {
                "agent": agent_name,
                "status": "error",
                "prior_utility": prior.utility_score,
                "error": str(result),
            }

        if result.get("status") != "revised":
            return prior, {
                "agent": agent_name,
                "status": "maintained",
                "prior_utility": prior.utility_score,
                "rationale": str(result.get("rationale", "")),
            }

        payload = result.get("payload")
        raw_score = result.get("utility_score")
        if not isinstance(payload, dict) or not isinstance(raw_score, (int, float)):
            return prior, {
                "agent": agent_name,
                "status": "maintained",
                "prior_utility": prior.utility_score,
                "rationale": "revision_missing_fields",
            }

        # R3.10/I-3: replace ONLY when the revised payload re-validates against the
        # agent's proto/domain schema; an invalid revision retains the prior position.
        try:
            validate_agent_payload(agent_name, payload)
        except SchemaValidationError:
            return prior, {
                "agent": agent_name,
                "status": "maintained",
                "prior_utility": prior.utility_score,
                "rationale": "revision_failed_schema",
                "schema_valid": False,
            }

        revised_score = float(raw_score)
        # Honest reconstruction: preserve agent identity/decision/tier/provenance and
        # update only the revised payload and utility_score (R3.7).
        new_proposal = prior.model_copy(
            update={"payload": payload, "utility_score": revised_score},
        )
        return new_proposal, {
            "agent": agent_name,
            "status": "revised",
            "prior_utility": prior.utility_score,
            "revised_utility": revised_score,
            "schema_valid": True,
        }

    def _record_debate_consequence(
        self,
        *,
        pre_debate: list[AgentProposal],
        post_debate: list[AgentProposal],
        weights: dict[str, float],
        selection: BindingSelection,
    ) -> tuple[int, ...]:
        """Mark every debate round that changed no value and no selection advisory (R13.8).

        The audit finding this closes is that the debate analysis was "recorded,
        ignored": rounds were counted on the decision whether or not they moved
        anything, so ``debate_rounds=3`` read as three consequential rounds. R13.8
        requires the *recorded analysis* to say which rounds were advisory.

        Two decidable questions, no proxies:

        * **Did the round change a proposal value?** ``changed_proposal_values``
          compares payloads and utilities before and after the concession round.
        * **Did the debate change the selection?** ``select_binding_action`` is pure,
          so applying the **same** knee weights to the pre-debate proposals answers
          it exactly. It is not re-derived from a utility argmax, which would be a
          different selection rule than the one that ratified the action.

        The mark is a **new** append-only context message, never an edit of the
        already-recorded ``debate_round`` analysis (I-14). Returns the advisory round
        numbers so ``_build_decision`` can stamp them into ``audit_trace`` too.
        """
        if not self._debate_rounds_log:
            return ()

        prior_selection = select_binding_action(pre_debate, weights)
        selection_changed = (
            prior_selection.selected_agent != selection.selected_agent
            or prior_selection.selected_index != selection.selected_index
        )

        rounds: list[dict[str, Any]] = []
        advisory: list[int] = []
        for record in self._debate_rounds_log:
            is_advisory = not record.values_changed and not selection_changed
            if is_advisory:
                advisory.append(record.round_number)
            rounds.append(
                {
                    "round": record.round_number,
                    "values_changed": record.values_changed,
                    "revised_agents": list(record.revised_agents),
                    "selection_changed": selection_changed,
                    "advisory": is_advisory,
                }
            )

        self._append_context(
            ContextMessage(
                source="orchestrator",
                content={
                    "type": "debate_consequence",
                    "selection_changed": selection_changed,
                    "selected_before": prior_selection.selected_agent,
                    "selected_after": selection.selected_agent,
                    "rounds": rounds,
                    "advisory_rounds": advisory,
                },
            )
        )
        return tuple(advisory)

    # ── Phase 3: Pareto arbitration ─────────────────────────────────────

    async def _phase_arbitrate(
        self,
        proposals: list[AgentProposal],
    ) -> dict[str, Any]:
        self._fsm.transition("convergence_or_max_rounds")
        self._emit_phase("arbitrating")
        weights = self._meta_rl.get_weights(self._system_state())
        result: dict[str, Any] = run_pareto_arbitration(proposals, weights)
        self._append_context(
            ContextMessage(
                source="orchestrator",
                content={
                    "type": "pareto_result",
                    "knee_index": result["knee_index"],
                    # R13.5: NSGA-II optimises over **weight vectors**, so this front
                    # is a front of candidate weightings - selection never ran over
                    # it, and recording it as the decision's `pareto_front` claimed a
                    # set the ratified action was not chosen from. It is kept here as
                    # arbitration evidence; the decision records the set selection
                    # actually ran over (`build_selection_front`).
                    "front_over": "weight_vectors",
                    "n_solutions": result["n_solutions"],
                },
            )
        )
        return result

    # ── C7: Tier-4 digital-twin verification ────────────────────────────

    async def _phase_twin_verify(
        self,
        decision: ConsensusDecision,
        *,
        bounds: TwinDisagreementBounds | None = None,
    ) -> tuple[ConsensusDecision, TwinVerdict]:
        """Verify the selected action against the digital twin's Monte-Carlo what-if.

        Returns the decision with the verdict recorded **and the**
        :class:`TwinVerdict` **itself**, which ``_ratify_and_dispatch`` reads
        (ADR-054 D3). Before this change the method returned only a decision whose
        ``audit_trace`` had gained ``twin=twin_verified``: the twin was consulted at
        the tier where a wrong action costs the most and had no way to object
        (purpose-achievement-audit R13.4). The predicted KPI distribution is still
        recorded into the append-only context and trace (I-14) so an operator sees
        the simulated outcome before the action executes.

        An unreachable or slow twin still degrades to an honest ``twin_unavailable``
        verdict, and that verdict vetoes nothing (I-7): ``exceeds_bound`` is false
        whenever no disagreement was measured, so a twin outage does not become a
        Tier-4 outage. What *does* veto is a measured disagreement beyond the
        committed bound.

        Args:
            decision: the built decision whose selected action is being verified.
            bounds: the committed bound to judge against. ``None`` reads
                ``infrastructure/quality/twin-verdict-bounds.yaml`` (AD-13); the
                parameter exists so a caller can supply a bound explicitly rather
                than as a literal here.

        Raises:
            TwinVerdictConfigurationError: the committed bound cannot be read. This
                is fail-closed on purpose - a deployment that declares a veto and
                cannot read its own bound must not dispatch as though the veto had
                been evaluated.
        """
        limits = bounds if bounds is not None else load_twin_verdict_bounds()
        verdict: TwinVerdict
        try:
            resp = await send_a2a_request(
                target_url=TWIN_ENDPOINT,
                method="monte_carlo",
                params={
                    "consensus_action": decision.selected_action,
                    "n_scenarios": TWIN_SCENARIOS,
                },
                # Bounded at 8s: 1000-scenario Monte-Carlo exceeds the twin's 10s
                # SLA on the small CPU VM; cap the wait so a slow twin degrades to
                # an honest note instead of stalling Tier-4 past the gateway timeout.
                timeout=8.0,
            )
            if resp.error:
                raise RuntimeError(resp.error)
            mc = resp.result or {}
            raw_kpis = mc.get("kpi_means") or {}
            twin_kpis = numeric_map(raw_kpis if isinstance(raw_kpis, dict) else {})
            consensus_kpis = numeric_map(decision.selected_action)
            disagreement, compared = measure_twin_disagreement(
                consensus_kpis,
                twin_kpis,
                relative_floor=limits.relative_floor,
            )
            n_scenarios = _numeric(mc.get("n_scenarios"))
            verdict = TwinVerdict(
                availability=TwinAvailability.VERIFIED,
                bound=limits.max_relative_disagreement,
                action_on_exceed=limits.action_on_exceed,
                bound_measured=limits.measured,
                disagreement=disagreement,
                compared_kpis=compared,
                consensus_kpis=consensus_kpis,
                twin_kpis=twin_kpis,
                n_scenarios=None if n_scenarios is None else int(n_scenarios),
            )
        except Exception as exc:  # noqa: BLE001 — an unreachable twin degrades (I-7)
            logger.warning("twin_verification_unavailable", error=str(exc))
            verdict = TwinVerdict(
                availability=TwinAvailability.UNAVAILABLE,
                bound=limits.max_relative_disagreement,
                action_on_exceed=limits.action_on_exceed,
                bound_measured=limits.measured,
                error=str(exc),
            )

        if verdict.exceeds_bound:
            logger.warning(
                "twin_disagreement_exceeds_bound",
                decision_id=str(decision.decision_id),
                disagreement=verdict.disagreement,
                bound=verdict.bound,
                compared_kpis=list(verdict.compared_kpis),
                action=verdict.action_on_exceed.value,
            )

        note: dict[str, Any] = {"type": "twin_verification", **verdict.as_context()}
        # The pre-ADR-054 note carried `kpi_means`; keep the key so existing audit
        # readers and the console keep resolving it.
        note["kpi_means"] = _round_floats(verdict.twin_kpis)
        self._append_context(ContextMessage(source="digital_twin", content=note))
        return (
            decision.model_copy(
                update={"audit_trace": [*decision.audit_trace, *verdict.trace_lines()]},
            ),
            verdict,
        )

    def _record_input_provenance(self, proposals: list[AgentProposal]) -> None:
        """Append an honest summary of which proposals rested on a degraded input.

        Reads each proposal's ``payload['provenance']`` (ADR-040) and records the
        degraded agents into the append-only context, so the audit chain captures
        whether the decision was built on real models or fallbacks (I-3/I-4 substance).
        """
        degraded: list[str] = []
        for p in proposals:
            # ADR-044: the typed AgentProposal.provenance field is authoritative;
            # the payload["provenance"] dict remains as the pre-044 fallback so
            # proposals from older agents are still read honestly.
            if p.provenance is not None:
                if p.provenance.degraded:
                    degraded.append(str(p.agent_name))
                continue
            payload = p.payload if isinstance(p.payload, dict) else {}
            prov = payload.get("provenance", {})
            if isinstance(prov, dict) and prov.get("degraded") is True:
                degraded.append(str(p.agent_name))
        self._append_context(
            ContextMessage(
                source="orchestrator",
                content={
                    "type": "input_provenance",
                    "degraded_agents": degraded,
                    "all_real": not degraded,
                },
            )
        )

    # ── Phase 4: Execution dispatch ─────────────────────────────────────

    async def _phase_execute(
        self,
        decision: ConsensusDecision,
    ) -> ConsensusDecision:
        self._fsm.transition("pareto_solution_selected")
        self._emit_phase("executing")

        confirmations: list[str] = []
        for proposal in decision.proposals:
            try:
                agent_name = str(proposal.agent_name)
                url = AGENT_ENDPOINTS.get(agent_name, "")
                resp = await send_a2a_request(
                    target_url=url,
                    method="execute",
                    params={
                        "decision_id": str(decision.decision_id),
                        "consensus_action": decision.selected_action,
                        # ADR-052: an agent enacts ITS OWN ratified proposal on the world
                        # (real actuation), and needs the city to route to the right
                        # WorldRuntime. `self._city` was stamped at run_consensus start.
                        "city": self._city,
                        "ratified_proposal": json.loads(proposal.to_deterministic_json()),
                    },
                    timeout=self._config.execution_timeout_seconds,
                )
                confirmations.append(
                    resp.result.get("status", "unknown") if resp.result else "no_result",
                )
            except Exception as exc:
                confirmations.append(f"error:{exc}")

        # ADR-054 D1: `_ratify_and_dispatch` appends the audit row before the I-4
        # postcondition on `execute_consensus` is checked, so a ratified decision
        # already carries its id. Re-logging would put a second row on the chain for
        # one decision; reuse it instead. A caller that supplies no id still gets the
        # append, so this phase remains usable on its own.
        audit_id = (
            decision.audit_id
            if decision.audit_id is not None
            else await self._audit.log_decision(decision)
        )
        self._fsm.transition("execution_complete")

        return decision.model_copy(
            update={
                "execution_confirmations": confirmations,
                "audit_id": audit_id,
                "context_messages": list(self._context_messages),
                "audit_trace": [
                    *decision.audit_trace,
                    f"audit_id={audit_id}",
                    f"confirmations={len(confirmations)}",
                ],
            },
        )

    # ── Phase 5: Learning ───────────────────────────────────────────────

    async def _phase_learn(self, decision: ConsensusDecision) -> None:
        self._fsm.transition("execution_complete")
        self._emit_phase("learning")

        # ADR-052: learn from the REALIZED world, not the predicted utility_score.
        # Perceive the post-execution world for this city; objectives the world can
        # observe (fill rate, spoilage, delivery) get the realized value, the rest fall
        # back to predicted utility. An unreachable world degrades to the old
        # predicted-utility path (I-7). This closes the loop Agent-audit flagged:
        # meta-RL previously learned only from its own predictions.
        world_state: dict[str, Any] | None = None
        if self._world_observer is not None and self._city is not None:
            try:
                world_state = await self._world_observer(self._city)
            except Exception as exc:  # noqa: BLE001 — a missing world degrades learning (I-7)
                logger.warning("learn_world_unavailable", error=str(exc))
                world_state = None

        self._meta_rl.update(self._build_learning_outcome(decision, world_state))

        if decision.tier in (DecisionTier.TIER_3, DecisionTier.TIER_4):
            await self._semantic_cache.store_decision(
                query_embedding=[0.0] * 384,
                decision=json.loads(decision.to_deterministic_json()),
                context_hash=str(decision.tier.value),
            )

        self._fsm.transition("updates_applied")

    def _build_learning_outcome(
        self,
        decision: ConsensusDecision,
        world_state: dict[str, Any] | None,
    ) -> dict[str, float]:
        """Map the realized world + proposals onto the 8 meta-RL objective scores.

        World-observable objectives use the REALIZED KPI; the rest fall back to the
        agent's predicted ``utility_score`` (no realized signal exists for them yet —
        honest, not fabricated). Pure given its inputs, so it is unit-tested directly.
        """
        outcome: dict[str, float] = {}
        if world_state is not None:
            if "fill_rate" in world_state:
                outcome["inventory_fill_rate"] = float(world_state["fill_rate"])
            if "spoilage_rate" in world_state:
                outcome["freshness_score"] = max(0.0, 1.0 - float(world_state["spoilage_rate"]))
            if "avg_delivery_min" in world_state:
                delivery = float(world_state["avg_delivery_min"])
                outcome["route_efficiency"] = max(0.0, min(1.0, 1.0 - delivery / 60.0))
        for proposal in decision.proposals:
            obj = _AGENT_OBJECTIVE.get(str(proposal.agent_name))
            if obj is not None and obj not in outcome:
                outcome[obj] = float(proposal.utility_score)
        return outcome

    # ── Helpers ─────────────────────────────────────────────────────────

    def _detect_conflicts(self, proposals: list[AgentProposal]) -> ConflictReport:
        if len(proposals) < 2:
            return ConflictReport(has_conflict=False)
        scores = [p.utility_score for p in proposals]
        divergence = max(scores) - min(scores)
        return ConflictReport(
            has_conflict=divergence > 0.3,
            max_utility_divergence=divergence,
        )

    @staticmethod
    def _check_convergence(proposals: list[AgentProposal]) -> bool:
        if len(proposals) < 2:
            return True
        scores = [p.utility_score for p in proposals]
        import numpy as np

        return float(np.var(scores)) < 0.1

    def _build_decision(
        self,
        proposals: list[AgentProposal],
        tier: DecisionTier,
        phase_reached: int,
        pareto_weights: dict[str, float],
        debate_rounds: int = 0,
        *,
        selection: BindingSelection | None = None,
        fast_best: AgentProposal | None = None,
        advisory_rounds: tuple[int, ...] = (),
    ) -> ConsensusDecision:
        """Build the decision, recording the set selection ran over (R13.5, R13.8).

        The recorded ``pareto_front`` is derived **only** from ``build_selection_front``
        and only when ``selection`` is not ``None``: it is one row per evaluated
        candidate, carrying that candidate's index and the knee-weighted score
        selection scored it with. There is no parameter by which a caller can record
        some other front, which is how R13.5's "the recorded front SHALL be the set
        the ratified action was selected from" is made unrepresentable rather than
        merely intended. The NSGA-II front over weight vectors - what this field used
        to hold - is recorded as arbitration evidence in the append-only context by
        ``_phase_arbitrate``.

        The fast path records no front (``None``): Tier 1/2 selects by a raw
        ``utility_score`` argmax over the proposals (R1.6) and runs no Pareto
        arbitration, so there is no front to claim.

        Args:
            advisory_rounds: debate rounds that changed no proposal value and no
                selection, from ``_record_debate_consequence``. Stamped into
                ``audit_trace`` beside the round count so the count cannot read as
                three consequential rounds when none of them moved anything (R13.8).

        Raises:
            SelectionIntegrityError: selection ratified a proposal that is not a
                member of the recorded front (R13.5).
        """
        audit_trace = [f"tier={tier.value}", f"phase={phase_reached}"]
        recorded_front: list[dict[str, float]] | None = None

        if selection is not None:
            # Binding Pareto-knee selection drives the full-path action (R1.1/R1.2).
            # The raw `utility_score` argmax no longer selects here; it survives only
            # on the fast path via `fast_best` (R1.6).
            chosen = (
                proposals[selection.selected_index]
                if selection.selected_index is not None
                else None
            )
            selected_action = chosen.payload if chosen is not None else {}
            confidence = chosen.confidence if chosen is not None else 0.0

            # R13.5: the recorded front is the set selection ran over, and the
            # ratified action is asserted to be a member of it.
            front = build_selection_front(proposals, selection)
            self._assert_ratified_front_member(front, selection, ratified=chosen is not None)
            recorded_front = [dict(row) for row in front.members]

            # Append-only binding-arbitration audit (I-14, R2.2/R2.5): the knee
            # weight vector, every evaluated candidate's weighted score, the
            # selected identity, any exclusions, and the deterministic tie-break.
            audit_trace.append(f"knee_weights={_canonical_json(_round_floats(pareto_weights))}")
            audit_trace.append(
                f"weighted_scores={_canonical_json(_round_floats(selection.weighted_scores))}"
            )
            audit_trace.append(f"binding_selected={selection.selected_agent}")
            if selection.excluded_agents:
                audit_trace.append(f"binding_excluded={_canonical_json(selection.excluded_agents)}")
            if selection.tie_break_applied:
                audit_trace.append(f"tie_break={selection.tie_break_reason}")
            # R13.5: membership is decidable from the row alone - the front size and
            # the ratified member's index into it are both on the trace.
            audit_trace.append(f"selection_front_size={len(front.members)}")
            if front.ratified_member_index is not None:
                audit_trace.append(f"selection_front_member={front.ratified_member_index}")
        else:
            # Fast path (Tier 1/2) retains raw `utility_score` argmax selection,
            # supplied by the caller as `fast_best` (R1.6).
            selected_action = fast_best.payload if fast_best is not None else {}
            confidence = fast_best.confidence if fast_best is not None else 0.0

        # R13.8: a round count is not a claim of consequence. Advisory rounds are
        # named, so `debate_rounds=3` with `debate_advisory=[1,2,3]` reads honestly.
        if debate_rounds:
            audit_trace.append(f"debate_advisory={_canonical_json(list(advisory_rounds))}")

        return ConsensusDecision(
            decision_id=self._decision_id or uuid4(),
            tier=tier,
            proposals=proposals,
            selected_action=selected_action,
            pareto_weights=pareto_weights,
            confidence=confidence,
            audit_trace=audit_trace,
            phase_reached=phase_reached,
            debate_rounds=debate_rounds,
            pareto_front=recorded_front,
            context_messages=list(self._context_messages),
        )

    @staticmethod
    def _assert_ratified_front_member(
        front: SelectionFront,
        selection: BindingSelection,
        *,
        ratified: bool,
    ) -> None:
        """Assert the ratified action is a member of the recorded front (R13.5).

        Raised, not logged: selection and the front are both pure projections of one
        proposal list, so a mismatch is drift between the two rather than a runtime
        condition. It propagates out of ``run_consensus``, so a decision whose
        recorded front misdescribes what it selected from never dispatches and never
        reaches the audit chain.

        ``ratified`` is false when selection found no eligible candidate; there is
        then no ratified action to be a member of anything, the front is empty, and
        the decision carries the honest empty action ``{}`` (R1.5, I-7).
        """
        if not ratified:
            if front.ratified_member_index is not None:
                raise SelectionIntegrityError(
                    "recorded front names a ratified member "
                    f"({front.ratified_member_index}) but selection ratified nothing"
                )
            return
        if front.ratified_member_index is None:
            raise SelectionIntegrityError(
                f"ratified action (proposal index {selection.selected_index}, agent "
                f"{selection.selected_agent}) is not a member of the recorded front of "
                f"{len(front.members)} candidate(s) (R13.5)"
            )
        member = front.members[front.ratified_member_index]
        recorded_index = int(member[FRONT_INDEX_KEY])
        if recorded_index != selection.selected_index:
            raise SelectionIntegrityError(
                f"recorded front member {front.ratified_member_index} carries candidate "
                f"index {recorded_index}, but selection ratified proposal index "
                f"{selection.selected_index} (R13.5)"
            )

    def _system_state(self) -> dict[str, Any]:
        return {
            "hour_of_day": datetime.now(UTC).hour,
            "active_disruptions": 0,
            "avg_fill_rate": 0.95,
        }

    def _reset(self) -> None:
        self._context_messages = []
        self._tool_call_count = 0
        self._debate_rounds_log = []
        self._decision_id = None
        self._city = None
        self._fsm.reset()
