"""Property-based test for consequential selection and twin verdicts (task 8.8, design E3).

Feature: purpose-achievement-audit, Property 26: Selection and twin verdicts are
consequential

    *For any* proposal set and weight vector, the recorded Pareto front is exactly the
    set selection ran over and contains the ratified action; *for any* Tier-4 twin
    verdict whose disagreement exceeds the declared bound, dispatch is withheld or the
    decision is escalated rather than the disagreement being recorded in ``audit_trace``
    alone; and *for any* debate round that changed no payload value and no selection,
    the recorded analysis is marked advisory.

What the sibling example tests already cover
--------------------------------------------

Three files carry the example classes for ADR-054 D3, and none of them makes a universal
statement - which is why this file exists rather than adding a fourth example:

* ``orchestrator/tests/test_twin_verification.py`` - ``_phase_twin_verify`` returns a
  ``TwinVerdict``: a verified twin that agrees, one that contradicts the consensus
  prediction beyond an explicitly supplied bound, an unreachable twin that must veto
  nothing (I-7), and one read of the committed bound file. It stops at the verdict; it
  never dispatches, so it cannot observe a *consequence*.
* ``orchestrator/tests/consensus/test_dispatch_choke_point.py`` - the choke point honours
  a **fabricated** ``TwinVerdict``: escalate, withhold, unavailable, agree, plus the
  Tier-1 confidence and BLOCK routes. Every verdict there is hand-built, so nothing
  connects a *measured* disagreement to the outcome.
* ``orchestrator/tests/consensus/test_selection_front_and_advisory.py`` - three fixed
  proposals: the front has one member per candidate, the ratified action is a member, the
  fast path records no front, a drifted front raises, and four advisory examples.

So the uncovered part, and the subject here, is the **composition over arbitrary inputs**:
a disagreement *measured* by the real metric from a real twin reply, judged against the
*committed* bound, travelling through the real choke point to a real (non-)dispatch; the
front-membership assertion holding for any proposal set and any knee weight vector rather
than for one triple; and the advisory rule holding in both directions - a round that
changed something is *not* stamped advisory - over generated mutations.

Why the property is shaped this way
-----------------------------------

**1. A stamp is not a consequence (R13.4).** The audit finding was that
``_phase_twin_verify`` returned a decision whose ``audit_trace`` had gained
``twin=twin_verified`` and nothing else: the twin was consulted at the tier where a wrong
action costs the most and could not object. Asserting the trace line is therefore not
evidence of a fix - the trace line was already there *before* the fix. What is asserted
instead is dispatch reality: zero ``execute`` calls over the A2A seam, an empty
``execution_confirmations`` on both the returned decision and the appended audit row, and
``withheld_by=twin_disagreement`` on the trace. The trace line is asserted too, because
R13.4 forbids recording the disagreement in ``audit_trace`` *alone*, not recording it.

**2. Attribution, by a metamorphic pair.** A withheld dispatch proves nothing on its own -
a guardrail could have withheld it. The vetoing example is therefore re-ratified
byte-identically with ``twin_verdict=None`` (the shape of a tier that consults no twin) and
must dispatch exactly once. The decision, the action, the confidence and the guardrail
engine are the same across the pair, so the verdict is the only thing that can account for
the difference in outcome.

**3. The bound is data, not a literal.** ``TestBoundComesFromCommittedConfiguration``
writes two configuration files that differ only in ``max_relative_disagreement`` - one
below the measured disagreement, one above - points ``protocol_mod.TWIN_BOUNDS_PATH`` at
each in turn, and asserts opposite outcomes for the same decision and the same twin reply.
A bound compiled into the protocol could not produce that difference. Every other key in
both files is copied from the committed
``infrastructure/quality/twin-verdict-bounds.yaml``, so no threshold is invented here; the
committed file is read with ``encoding='utf-8'`` (E-S13-07). The second property pins the
loader's I-7 refusal: no committed value other than ``no_veto`` is accepted for
``unavailable_action`` / ``not_comparable_action``, so the file cannot be edited into a
configuration where a dead twin becomes a global Tier-4 kill switch. That refusal is
reachable from no sibling test.

**4. Independent oracles, not agreement with the subject.** The recorded front's
``weighted_score`` is checked against the knee weights dotted with the *recorded* utility
vector - R1.1's rule ("aggregate that proposal's per-objective utilities under the
Pareto-knee weights") restated over the recorded row, so the two recorded fields cannot
drift apart, and neither is taken on trust from ``select_binding_action``. The ratified
member is additionally required to carry the maximal recorded score. For the advisory rule
the value-change oracle is a restatement of R13.8's own wording ("changed no payload
value") - payload equality plus utility equality, written out here rather than imported -
and the selection-change oracle is the ``binding_selected=`` line of two independently
built decisions, which is the protocol's own recorded audit evidence rather than a second
call of the predicate under test.

What "drives the twin" means here, and what is deliberately not driven
---------------------------------------------------------------------

The real ``ConsensusProtocol`` is constructed and the real Tier-4 twin path runs:
``_phase_twin_verify`` -> ``load_twin_verdict_bounds`` (a real read of committed YAML) ->
``measure_twin_disagreement`` -> ``_ratify_and_dispatch`` -> the real ``GuardrailEngine``,
the real ``HITLEscalation`` (which awaits a human future and dispatches nothing) and
``_phase_execute``. Two seams are doubled, and only two: Postgres, by an append-only
recording sink, and the A2A network hop, by a recorder that answers ``monte_carlo`` with a
KPI mean set and ``execute`` with a status - the same doubling the sibling choke-point test
uses, and for the same reason.

The twin's own Monte-Carlo is **not** driven, and that is a constraint rather than a
preference: ``MonteCarloRunner.run_scenarios`` raises ``ValueError`` below
``MIN_SCENARIOS`` (INV-TW-002 - 1000 scenarios in a ``ProcessPoolExecutor``), so there is
no legitimate small-n way to drive it, and a 1000-scenario Monte-Carlo inside a property
loop is precisely the workload ``.kiro/steering/local-compute-budget.md`` (I-0) forbids.
What the subject of R13.4 needs is a *measured* disagreement of a controlled magnitude
straddling the committed bound, which a real Monte-Carlo cannot supply anyway.

I-0 routing
-----------

Every statement here drives the real protocol, so the whole module is
``@pytest.mark.slow`` via ``pytestmark`` and ``-m "not slow"`` genuinely excludes it. It
was **never executed on the development laptop**. ``max_examples`` is not set anywhere -
the budget comes from the root ``conftest.py`` profiles (``dev``=10, ``heavy``=100,
``ci``/``default``=500, ``nightly``=5000). No example calls ``run_pareto_arbitration``, so
no NSGA-II generation runs and an example stays cheap enough for the 500-example
``default`` budget.

Note for task 12.2, which owns the routing: ``ci.yml::uplift-verify``'s slow step selects
``tests/uplift tests/verify`` only, so it does **not** collect this file;
``ci.yml::quality-gates`` runs ``pytest packages/tests agents orchestrator digital_twin
api`` with no ``-m`` filter and no ``HYPOTHESIS_PROFILE``, so as things stand this module
executes there at the ``default`` budget. Either job is a correct owner; what is not
correct is assuming the ``slow`` marker keeps it out of ``quality-gates``.

**Validates: Requirements 13.4, 13.5, 13.8**
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Final
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
import yaml
from hypothesis import given
from hypothesis import strategies as st
from synapse_common.models import AgentName, AgentProposal, DecisionTier

from orchestrator.config import OrchestratorConfig
from orchestrator.consensus import protocol as protocol_mod
from orchestrator.consensus.pareto import (
    FRONT_INDEX_KEY,
    FRONT_SCORE_KEY,
    OBJECTIVES,
    select_binding_action,
)
from orchestrator.consensus.protocol import (
    ConsensusProtocol,
    DebateRoundChange,
    TwinDisagreementBounds,
    TwinExceedAction,
    TwinVerdictConfigurationError,
    changed_proposal_values,
    load_twin_verdict_bounds,
)
from orchestrator.guardrails.rules import HARD_GUARDRAILS, GuardrailEngine
from orchestrator.hitl.escalation import HITLEscalation, WebSocketManager

if TYPE_CHECKING:
    from pathlib import Path
    from uuid import UUID

    from synapse_common.models import ConsensusDecision

    from orchestrator.consensus.protocol import TwinVerdict

# Every example drives the real four-tier protocol, so the whole module is slow and
# `-m "not slow"` excludes all of it (I-0).
pytestmark = pytest.mark.slow

# --- Committed values, never literals ---------------------------------------

#: The committed Tier-4 bound file, captured at import so a monkeypatched
#: `TWIN_BOUNDS_PATH` cannot make the "committed" section mean the patched one.
_COMMITTED_BOUNDS_PATH: Final[Path] = protocol_mod.TWIN_BOUNDS_PATH

#: The I-5 boundary as declared in the committed guardrail table, and the **only** floor
#: a ratifiable example here has to clear. The engine below is constructed with this
#: value, and since task 12.1a `_ratify_and_dispatch` hands `execute_consensus` the
#: boundary in force rather than judging it against a literal - so the pre-flight, the
#: `@deal.pre` and `validate_decision` all read this one number. This file used to carry a
#: second `_EXECUTE_CONSENSUS_PRE_FLOOR = 0.7` and take the `max()` of the two; that was
#: a copy of the same literal 12.1a deleted from production, and taking a maximum of a
#: value against itself is scaffolding for a conflict that no longer exists.
_CONFIDENCE_FLOOR: Final[float] = float(HARD_GUARDRAILS["confidence_floor"]["default_threshold"])

#: The neutral cross-objective utility `_build_utility_matrix` and
#: `build_selection_front` both document; a modelling constant, not a threshold.
_NEUTRAL_BASELINE: Final[float] = 0.5

#: KPI keys the twin's `monte_carlo` reply carries (`MonteCarloOutput.kpi_means`). None of
#: them appears in `RAW_DEMAND_FIELDS` or `STORE_IDENTITY_FIELDS`, so putting one in the
#: selected action cannot trip a guardrail and confound the twin verdict.
_TWIN_KPI_KEYS: Final[tuple[str, ...]] = (
    "orders_created",
    "orders_delivered",
    "avg_delivery_time_min",
    "spoilage_rate",
    "restocks_triggered",
)

#: A guardrail-clean action skeleton: one store identity, no raw demand payload, no
#: pricing or routing actions, no `predicted_fill_rate`.
_CLEAN_ACTION: Final[dict[str, Any]] = {"action_type": "reorder", "store_id": "blr_001"}

_CANONICAL_JSON_KWARGS: Final[dict[str, Any]] = {"sort_keys": True, "separators": (",", ":")}

# --- Strategies (no `max_examples` anywhere - profiles own the budget) -------

#: Every agent is mapped to an objective by `pareto._AGENT_TO_OBJECTIVE` today, so every
#: agent is an eligible candidate. The front property asserts that totality rather than
#: assuming it, so a future unmapped agent is named instead of silently excluded.
_AGENTS: Final[tuple[AgentName, ...]] = tuple(AgentName)

_utilities = st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)
#: Strictly above the one floor in force, so a withheld dispatch below is always
#: attributable to the twin verdict and never to the confidence gate. Clamped at 1.0 so a
#: committed default of 1.0 would yield an empty-free range rather than an invalid one.
_confidences = st.floats(
    min_value=min(1.0, _CONFIDENCE_FLOOR + 0.01),
    max_value=1.0,
    allow_nan=False,
    allow_infinity=False,
)
_weight_values = st.floats(min_value=0.01, max_value=2.0, allow_nan=False, allow_infinity=False)
_kpi_magnitudes = st.floats(min_value=1.0, max_value=1000.0, allow_nan=False, allow_infinity=False)
#: Multiples of the committed bound, so generated disagreements straddle it.
_bound_multiples = st.floats(min_value=0.0, max_value=3.0, allow_nan=False, allow_infinity=False)


def _weight_vectors() -> st.SearchStrategy[dict[str, float]]:
    """A knee weight vector over the 8 objectives."""
    return st.fixed_dictionaries({objective: _weight_values for objective in OBJECTIVES})


def _proposal(
    agent: AgentName,
    *,
    utility: float,
    confidence: float,
    payload: dict[str, Any] | None = None,
) -> AgentProposal:
    return AgentProposal(
        agent_name=agent,
        decision_id=uuid4(),
        utility_score=utility,
        confidence=confidence,
        justification_trace=[f"{agent.value} proposal"],
        payload=payload if payload is not None else {"action": f"{agent.value}_action"},
        tier=DecisionTier.TIER_4,
    )


@st.composite
def _proposal_sets(
    draw: st.DrawFn,
    *,
    min_size: int = 1,
    max_size: int = 4,
) -> list[AgentProposal]:
    """One proposal per distinct agent, each with its own utility and confidence."""
    agents = draw(
        st.lists(
            st.sampled_from(_AGENTS),
            min_size=min_size,
            max_size=max_size,
            unique=True,
        ),
    )
    return [
        _proposal(agent, utility=draw(_utilities), confidence=draw(_confidences))
        for agent in agents
    ]


# --- Doubles: Postgres and the A2A hop, and nothing else ---------------------


@dataclass(frozen=True)
class _A2AReply:
    """The `.result` / `.error` shape `send_a2a_request` returns."""

    result: dict[str, Any] | None = None
    error: str | None = None


class _A2ARecorder:
    """Answers the twin's `monte_carlo` and each agent's `execute`, recording both.

    A recording sink rather than a mock with a canned verdict: the assertions read what
    the protocol actually attempted over the seam, so "nothing dispatched" is observed
    instead of asserted.
    """

    def __init__(self, twin_kpis: dict[str, float], *, n_scenarios: int = 1000) -> None:
        self.calls: list[dict[str, Any]] = []
        self._twin_kpis = dict(twin_kpis)
        self._n_scenarios = n_scenarios

    async def __call__(self, **kwargs: Any) -> _A2AReply:
        self.calls.append(kwargs)
        if kwargs.get("method") == "monte_carlo":
            return _A2AReply(
                result={"n_scenarios": self._n_scenarios, "kpi_means": dict(self._twin_kpis)},
            )
        return _A2AReply(result={"status": "ok"})

    @property
    def executes(self) -> list[dict[str, Any]]:
        """Every dispatch attempt - the observable this property turns on."""
        return [call for call in self.calls if call.get("method") == "execute"]


class _RecordingAuditSink:
    """An `AuditLogger`-shaped append-only sink (I-4: append, never update)."""

    def __init__(self) -> None:
        self.rows: list[ConsensusDecision] = []

    async def log_decision(self, decision: ConsensusDecision) -> UUID:
        self.rows.append(decision)
        return uuid4()


class _TimingOutWaiter:
    """Timer-free waiter that times the human out immediately."""

    async def __call__(
        self,
        future: asyncio.Future[dict[str, Any]],
        *,
        timeout: float,
        decision_id: UUID,
    ) -> dict[str, Any]:
        del future, timeout, decision_id
        raise TimeoutError


def _protocol(audit: _RecordingAuditSink | None = None) -> ConsensusProtocol:
    """The real protocol with the real guardrail engine and the real HITL gate."""
    config = OrchestratorConfig(postgresql_url="sqlite+aiosqlite:///", pinecone_api_key=None)
    return ConsensusProtocol(
        config=config,
        tier_router=MagicMock(),
        guardrails=GuardrailEngine(confidence_threshold=_CONFIDENCE_FLOOR),
        audit_logger=audit or _RecordingAuditSink(),  # type: ignore[arg-type]
        hitl_escalation=HITLEscalation(
            kafka_producer=None,
            ws_manager=WebSocketManager(),
            timeout_seconds=0.01,
            timeout_action="defer",
            waiter=_TimingOutWaiter(),
        ),
        context_builder=MagicMock(),
        ollama_client=MagicMock(),
        meta_rl=MagicMock(**{"get_weights.return_value": {"demand_accuracy": 1.0}}),
        semantic_cache=MagicMock(**{"available": False}),
    )


# --- Readers over recorded evidence ------------------------------------------


def _trace_value(decision: ConsensusDecision, prefix: str) -> str | None:
    """The single `audit_trace` entry beginning with *prefix*, without it."""
    for line in decision.audit_trace:
        if line.startswith(prefix):
            return line[len(prefix) :]
    return None


def _ratification(decision: ConsensusDecision) -> dict[str, Any]:
    """The choke point's ratification record for *decision*."""
    records = [
        message.content
        for message in decision.context_messages
        if message.content.get("type") == "dispatch_ratification"
    ]
    assert records, "the choke point records every ratification"
    return records[-1]


def _last_context(proto: ConsensusProtocol, content_type: str) -> dict[str, Any]:
    """The most recent context message of *content_type*.

    Selected by type rather than by position: `_append_context` injects an objective
    recitation on every `recitation_interval`-th append (ADR-024), so the last message is
    not reliably the one just written.
    """
    records = [
        message.content
        for message in proto._context_messages
        if message.content.get("type") == content_type
    ]
    assert records, f"no {content_type} record was appended"
    return records[-1]


def _committed_section() -> dict[str, Any]:
    """The committed `tier4_disagreement` section (E-S13-07: utf-8 on every read)."""
    payload: Any = yaml.safe_load(_COMMITTED_BOUNDS_PATH.read_text(encoding="utf-8"))
    section: dict[str, Any] = dict(payload["tier4_disagreement"])
    return section


def _write_bounds(path: Path, *, max_relative_disagreement: float, **overrides: Any) -> None:
    """Write a bounds file that differs from the committed one only where asked."""
    section = {
        **_committed_section(),
        "max_relative_disagreement": max_relative_disagreement,
        **overrides,
    }
    path.write_text(
        yaml.safe_dump({"version": 1, "tier4_disagreement": section}, sort_keys=True),
        encoding="utf-8",
    )


def _relative_deviation(predicted: float, simulated: float, *, floor: float) -> float:
    """The metric R13.4 declares, restated here rather than imported."""
    return abs(simulated - predicted) / max(abs(predicted), floor)


class TestRecordedFrontIsTheSetSelectionRanOver:
    """R13.5: the recorded front is what selection ran over, and holds the winner."""

    # Feature: purpose-achievement-audit, Property 26: Selection and twin verdicts are consequential
    @given(proposals=_proposal_sets(), weights=_weight_vectors())
    def test_front_is_the_evaluated_set_and_names_the_maximal_ratified_member(
        self,
        proposals: list[AgentProposal],
        weights: dict[str, float],
    ) -> None:
        """R13.5, for any proposal set and any knee weight vector.

        Before ADR-054 the recorded `pareto_front` was the NSGA-II front over *weight
        vectors*: selection never ran over it, so the ratified action could not be a
        member and the audit row described a set it had not chosen from. Four things are
        asserted over the recorded row alone, because membership has to be decidable by a
        reader who has only the audit row: one row per evaluated candidate in input
        order; each row's score equal to the knee weights dotted with that row's own
        recorded utility vector; the ratified member carrying the maximal score; and the
        ratified action equal to the payload of the candidate that member names.
        """
        selection = select_binding_action(proposals, weights)
        # `_build_decision` is the recorder under test.
        decision = _protocol()._build_decision(
            proposals=proposals,
            tier=DecisionTier.TIER_4,
            phase_reached=4,
            pareto_weights=weights,
            selection=selection,
        )

        front = decision.pareto_front
        assert front is not None
        # The agent -> objective table is total today; if it stops being total this names
        # it rather than silently shrinking the front the assertions below range over.
        assert selection.excluded_agents == []
        assert len(front) == len(proposals)
        assert [int(row[FRONT_INDEX_KEY]) for row in front] == list(range(len(proposals)))

        for row, proposal in zip(front, proposals, strict=True):
            utility = float(proposal.utility_score)
            off_baseline = [
                objective for objective in OBJECTIVES if row[objective] != _NEUTRAL_BASELINE
            ]
            # The row is the utility vector arbitration evaluated: the agent's own
            # objective carries its utility, every other objective the neutral baseline.
            assert len(off_baseline) <= 1
            assert all(row[objective] == pytest.approx(utility) for objective in off_baseline)
            if utility != _NEUTRAL_BASELINE:
                assert len(off_baseline) == 1
            # R1.1 restated over the recorded row, so the two recorded fields cannot drift.
            expected = sum(weights[objective] * row[objective] for objective in OBJECTIVES)
            assert row[FRONT_SCORE_KEY] == pytest.approx(expected, rel=1e-9)

        member = _trace_value(decision, "selection_front_member=")
        assert member is not None, "a ratified decision names its member on the trace"
        assert f"selection_front_size={len(front)}" in decision.audit_trace

        ratified_row = front[int(member)]
        candidate_index = int(ratified_row[FRONT_INDEX_KEY])
        best = max(row[FRONT_SCORE_KEY] for row in front)
        assert ratified_row[FRONT_SCORE_KEY] >= best - 1e-9
        assert _trace_value(decision, "binding_selected=") == str(
            proposals[candidate_index].agent_name,
        )
        assert decision.selected_action == proposals[candidate_index].payload
        assert decision.confidence == pytest.approx(proposals[candidate_index].confidence)


class TestTwinDisagreementIsConsequential:
    """R13.4: a measured disagreement beyond the committed bound changes the outcome."""

    # Feature: purpose-achievement-audit, Property 26: Selection and twin verdicts are consequential
    @given(
        kpi_key=st.sampled_from(_TWIN_KPI_KEYS),
        predicted=_kpi_magnitudes,
        bound_multiple=_bound_multiples,
        on_exceed=st.sampled_from(tuple(TwinExceedAction)),
        confidence=_confidences,
    )
    def test_measured_disagreement_beyond_the_bound_withholds_or_escalates(
        self,
        monkeypatch: pytest.MonkeyPatch,
        kpi_key: str,
        predicted: float,
        bound_multiple: float,
        on_exceed: TwinExceedAction,
        confidence: float,
    ) -> None:
        """R13.4, driven end to end through the real Tier-4 path.

        The decision is guardrail-clean and above both confidence floors, so the twin is
        the only gate that can withhold it. `bound_multiple` scales the deviation about
        the committed bound, so generated examples fall on both sides of it.

        The consequence is read from dispatch reality - zero `execute` calls, empty
        `execution_confirmations` on the returned decision *and* on the appended audit
        row - never from the trace note, which existed before the fix. The trace note is
        asserted as well: R13.4 forbids recording the disagreement in `audit_trace`
        *alone*, not recording it there.
        """
        committed = load_twin_verdict_bounds()
        # Every number below is the committed one; only ADR-054 D3's documented
        # `withhold`-or-`escalate` disjunction is generated.
        limits = TwinDisagreementBounds(
            max_relative_disagreement=committed.max_relative_disagreement,
            relative_floor=committed.relative_floor,
            action_on_exceed=on_exceed,
            measured=committed.measured,
        )
        simulated = predicted * (1.0 + bound_multiple * committed.max_relative_disagreement)
        deviation = _relative_deviation(predicted, simulated, floor=committed.relative_floor)

        action = {**_CLEAN_ACTION, kpi_key: predicted}
        proposals = [
            _proposal(
                AgentName.INVENTORY_SENTINEL,
                utility=0.9,
                confidence=confidence,
                payload=action,
            ),
        ]
        weights = {objective: 1.0 for objective in OBJECTIVES}
        recorder = _A2ARecorder({kpi_key: simulated})
        monkeypatch.setattr(protocol_mod, "send_a2a_request", recorder)

        audit = _RecordingAuditSink()
        proto = _protocol(audit)
        control_audit = _RecordingAuditSink()
        control_proto = _protocol(control_audit)

        async def drive() -> tuple[ConsensusDecision, TwinVerdict, int, ConsensusDecision | None]:
            built = proto._build_decision(
                proposals=proposals,
                tier=DecisionTier.TIER_4,
                phase_reached=4,
                pareto_weights=weights,
                selection=select_binding_action(proposals, weights),
            )
            verified, verdict = await proto._phase_twin_verify(built, bounds=limits)
            out = await proto._ratify_and_dispatch(
                verified,
                tier=DecisionTier.TIER_4,
                twin_verdict=verdict,
            )
            # Counted here, before the control run adds to the same recorder.
            dispatched = len(recorder.executes)
            control: ConsensusDecision | None = None
            if verdict.exceeds_bound:
                # The metamorphic half: same decision, same action, same guardrails, no
                # verdict. If this dispatches, the verdict is what withheld the other.
                control = await control_proto._ratify_and_dispatch(
                    verified,
                    tier=DecisionTier.TIER_4,
                    twin_verdict=None,
                )
            return out, verdict, dispatched, control

        out, verdict, dispatched, control = asyncio.run(drive())

        # The measurement, against a restatement of the declared metric.
        assert verdict.disagreement == pytest.approx(deviation, rel=1e-9)
        assert verdict.compared_kpis == (kpi_key,)
        assert verdict.bound == pytest.approx(committed.max_relative_disagreement)
        assert verdict.exceeds_bound is (deviation > committed.max_relative_disagreement)
        # Recorded on the trace - and the recording is not the consequence.
        recorded = _trace_value(out, "twin_disagreement=")
        assert recorded is not None
        assert float(recorded) == pytest.approx(deviation, rel=1e-8)

        record = _ratification(out)
        if verdict.exceeds_bound:
            # Nothing was enacted on the world: the veto is a consequence, not a note.
            assert dispatched == 0
            assert out.execution_confirmations == []
            assert "dispatch=withheld" in out.audit_trace
            assert "withheld_by=twin_disagreement" in out.audit_trace
            assert record["twin_veto"] is True
            assert record["twin_verdict_enforced"] is True
            assert any("twin_disagreement:" in reason for reason in record["reasons"])
            # ADR-054 D3's disjunction: `escalate` queues a human, `withhold` does not,
            # and both leave `execution_confirmations` empty.
            assert out.escalated_to_human is (on_exceed is TwinExceedAction.ESCALATE)
            assert len(audit.rows) == 1
            assert audit.rows[0].execution_confirmations == []
            # Attribution: the identical decision with no verdict dispatches once, so the
            # verdict is the only thing that can account for the withheld dispatch.
            assert control is not None
            assert len(recorder.executes) == 1
            assert control.execution_confirmations == ["ok"]
            assert _ratification(control)["twin_veto"] is False
        else:
            assert control is None
            assert dispatched == 1
            assert out.execution_confirmations == ["ok"]
            assert record["twin_veto"] is False
            assert out.escalated_to_human is False
            assert len(audit.rows) == 1


class TestBoundComesFromCommittedConfiguration:
    """AD-13 / I-7: the veto boundary is a committed value the loader validates."""

    # Feature: purpose-achievement-audit, Property 26: Selection and twin verdicts are consequential
    @given(
        kpi_key=st.sampled_from(_TWIN_KPI_KEYS),
        predicted=_kpi_magnitudes,
        deviation_multiple=st.floats(
            min_value=0.05,
            max_value=3.0,
            allow_nan=False,
            allow_infinity=False,
        ),
        confidence=_confidences,
    )
    def test_the_veto_boundary_follows_the_committed_file(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        kpi_key: str,
        predicted: float,
        deviation_multiple: float,
        confidence: float,
    ) -> None:
        """The same disagreement vetoes under a tight bound and does not under a loose one.

        `_phase_twin_verify` is called with no `bounds` argument, so it reads
        `TWIN_BOUNDS_PATH`. Two files are written per example, identical to the committed
        one except for `max_relative_disagreement` - one below the measured deviation, one
        above. The decision, the twin reply and the guardrail engine are held fixed, so a
        bound written into the protocol as a literal could not produce two outcomes.
        """
        # Read explicitly from the committed path: `TWIN_BOUNDS_PATH` is patched below,
        # and Hypothesis reuses this function body across examples.
        committed = load_twin_verdict_bounds(_COMMITTED_BOUNDS_PATH)
        simulated = predicted * (1.0 + deviation_multiple)
        deviation = _relative_deviation(predicted, simulated, floor=committed.relative_floor)

        action = {**_CLEAN_ACTION, kpi_key: predicted}
        proposals = [
            _proposal(
                AgentName.INVENTORY_SENTINEL,
                utility=0.9,
                confidence=confidence,
                payload=action,
            ),
        ]
        weights = {objective: 1.0 for objective in OBJECTIVES}
        recorder = _A2ARecorder({kpi_key: simulated})
        monkeypatch.setattr(protocol_mod, "send_a2a_request", recorder)

        bounds_file = tmp_path / "twin-verdict-bounds.yaml"
        monkeypatch.setattr(protocol_mod, "TWIN_BOUNDS_PATH", bounds_file)

        async def drive(bound: float) -> tuple[ConsensusDecision, TwinVerdict]:
            _write_bounds(bounds_file, max_relative_disagreement=bound)
            proto = _protocol()
            built = proto._build_decision(
                proposals=proposals,
                tier=DecisionTier.TIER_4,
                phase_reached=4,
                pareto_weights=weights,
                selection=select_binding_action(proposals, weights),
            )
            # No `bounds` argument: the loader reads the (patched) committed path.
            verified, verdict = await proto._phase_twin_verify(built)
            out = await proto._ratify_and_dispatch(
                verified,
                tier=DecisionTier.TIER_4,
                twin_verdict=verdict,
            )
            return out, verdict

        tight = deviation * 0.5
        loose = deviation * 2.0

        vetoed, tight_verdict = asyncio.run(drive(tight))
        dispatched, loose_verdict = asyncio.run(drive(loose))

        assert tight_verdict.bound == pytest.approx(tight)
        assert loose_verdict.bound == pytest.approx(loose)
        assert tight_verdict.disagreement == pytest.approx(deviation, rel=1e-9)
        assert loose_verdict.disagreement == pytest.approx(deviation, rel=1e-9)

        assert tight_verdict.exceeds_bound is True
        assert vetoed.execution_confirmations == []
        assert "withheld_by=twin_disagreement" in vetoed.audit_trace

        assert loose_verdict.exceeds_bound is False
        assert dispatched.execution_confirmations == ["ok"]
        assert _ratification(dispatched)["twin_veto"] is False
        # One dispatch across the pair, from the loose-bound run only.
        assert len(recorder.executes) == 1

    # Feature: purpose-achievement-audit, Property 26: Selection and twin verdicts are consequential
    @given(
        key=st.sampled_from(("unavailable_action", "not_comparable_action")),
        declared=st.sampled_from(("veto", "withhold", "escalate", "block", "", "NO_VETO")),
        bound=st.floats(min_value=0.01, max_value=5.0, allow_nan=False, allow_infinity=False),
    )
    def test_loader_refuses_a_configuration_that_vetoes_on_absence(
        self,
        tmp_path: Path,
        key: str,
        declared: str,
        bound: float,
    ) -> None:
        """I-7: absence of a verdict is never a negative verdict, and it is pinned.

        The committed file *documents* that an unavailable twin must not become a Tier-4
        kill switch; this asserts the loader *enforces* it, for any declared value other
        than the exact string `no_veto` - including `NO_VETO`, which nearly resolves. The
        refusal is reachable from no sibling test, so without this the strongest I-7
        guarantee in the twin path would be a comment.
        """
        bounds_file = tmp_path / "twin-verdict-bounds.yaml"
        _write_bounds(bounds_file, max_relative_disagreement=bound, **{key: declared})

        with pytest.raises(TwinVerdictConfigurationError, match=key):
            load_twin_verdict_bounds(bounds_file)


class TestDebateAdvisoryStamp:
    """R13.8: an advisory round is one that moved nothing, and it is named."""

    # Feature: purpose-achievement-audit, Property 26: Selection and twin verdicts are consequential
    @given(
        proposals=_proposal_sets(min_size=2, max_size=4),
        weights=_weight_vectors(),
        target=st.integers(min_value=0, max_value=3),
        mutation=st.sampled_from(("none", "payload", "utility")),
        revised_utility=_utilities,
        rounds=st.integers(min_value=1, max_value=3),
    )
    def test_advisory_marks_exactly_the_rounds_that_moved_nothing(
        self,
        proposals: list[AgentProposal],
        weights: dict[str, float],
        target: int,
        mutation: str,
        revised_utility: float,
        rounds: int,
    ) -> None:
        """R13.8 in both directions, over generated concession outcomes.

        The modelled debate is the shape `_phase_debate` produces: round 1 carries
        whatever the concession changed, later rounds maintain. `values_changed` is
        computed by the same `changed_proposal_values` the protocol uses, because that is
        the input `_record_debate_consequence` receives; what is *not* taken from the
        subject is either oracle. Value change is checked against a restatement of
        R13.8's own wording - payload equality plus utility equality - and selection
        change against the `binding_selected=` line of two independently built decisions.
        """
        index = target % len(proposals)
        prior = proposals[index]
        after = list(proposals)
        if mutation == "payload":
            after[index] = prior.model_copy(
                update={"payload": {**prior.payload, "concession": index}},
            )
        elif mutation == "utility":
            after[index] = prior.model_copy(update={"utility_score": revised_utility})

        changed_agents = changed_proposal_values(proposals, after)
        log = [
            DebateRoundChange(
                round_number=number,
                values_changed=bool(changed_agents) and number == 1,
                revised_agents=changed_agents if number == 1 else (),
            )
            for number in range(1, rounds + 1)
        ]

        # Oracle 1: did any proposal value move? R13.8's wording restated here, not the
        # predicate under test called a second time.
        values_identical = all(
            prior_proposal.payload == revised.payload
            and float(prior_proposal.utility_score) == float(revised.utility_score)
            for prior_proposal, revised in zip(proposals, after, strict=True)
        )
        # Oracle 2: did the ratified identity move? Read from each decision's own trace.
        before_decision = _protocol()._build_decision(
            proposals=proposals,
            tier=DecisionTier.TIER_4,
            phase_reached=4,
            pareto_weights=weights,
            selection=select_binding_action(proposals, weights),
        )
        selected_before = _trace_value(before_decision, "binding_selected=")

        proto = _protocol()
        # Exactly what `_phase_debate` records, in the order `_full_path` records it.
        proto._debate_rounds_log = log
        selection = select_binding_action(after, weights)
        advisory = proto._record_debate_consequence(
            pre_debate=proposals,
            post_debate=after,
            weights=weights,
            selection=selection,
        )
        decision = proto._build_decision(
            proposals=after,
            tier=DecisionTier.TIER_4,
            phase_reached=4,
            pareto_weights=weights,
            debate_rounds=len(log),
            selection=selection,
            advisory_rounds=advisory,
        )
        selected_after = _trace_value(decision, "binding_selected=")

        record = _last_context(proto, "debate_consequence")
        assert record["selected_before"] == selected_before
        assert record["selected_after"] == selected_after
        assert record["selection_changed"] is (selected_before != selected_after)

        if selected_before != selected_after:
            # A round that moved the ratified action is consequential whatever it did to
            # any single payload.
            assert advisory == ()
        elif values_identical:
            # Changed no payload and no selection: every round is advisory (R13.8).
            assert advisory == tuple(range(1, rounds + 1))
        else:
            # Changed something: the round that changed it is not advisory.
            assert 1 not in advisory
            assert advisory == tuple(range(2, rounds + 1))

        per_round = {entry["round"]: entry for entry in record["rounds"]}
        assert set(per_round) == set(range(1, rounds + 1))
        for number, entry in per_round.items():
            assert entry["advisory"] is (number in advisory)
        assert record["advisory_rounds"] == list(advisory)

        # A round count is not a claim of consequence: the trace names the advisory ones.
        assert decision.debate_rounds == rounds
        expected = "debate_advisory=" + json.dumps(list(advisory), **_CANONICAL_JSON_KWARGS)
        assert expected in decision.audit_trace
