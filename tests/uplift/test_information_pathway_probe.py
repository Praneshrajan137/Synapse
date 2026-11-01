# Feature: decision-quality-proof, Property 95: The consensus request carries what the world
# rewards, and a pathway that never responds is reported, never relabelled
"""What the consensus arm is told, what it counts, and whether what it is told moves it.

Task 29.6 (R7.20, R7.21; finding 68; decisions 3=a and Q2=a). Subjects:
``uplift/consensus_arm.py`` (``observation_to_decision_request``, the translator,
``classify_dispatch``, ``ConsensusArm`` as a ``RunScoped`` policy) and ``uplift/dispatch.py``
(``summarise_dispatch`` and the pathway probe).

**Clauses, each asserted unconditionally.**

1. The request carries each of the five task-13.1 fields and ``inventory_position`` (on hand plus
   on order, per stocked SKU), every mapping in sorted key order, so equal observations give
   byte-identical requests however their mappings were assembled (I-13).
2. Every decision lands in exactly one bucket, by blocked > untranslatable > withheld >
   dispatched, over constructed protocol outputs covering each bucket and every ambiguous
   withhold. Each ambiguity resolves to ``guardrail_blocked`` and applies nothing (I-6). That
   includes the case the protocol's record cannot show: a confidence failure masking the
   service-level minimum, because the guardrail engine returns at its first failing rule.
3. A binding action expressing a lever outside the suite's set is untranslatable and its reason
   names the set; the Inventory Sentinel's reorder list translates to reorders and nothing else.
4. A run's ``DecisionCounts`` sum to the decides that returned; ``begin_run`` resets them; a
   decide that raised and a ``consult`` count nothing.
5. ``DispatchReport``: the rate is ``dispatched / total``, or ``None`` with a reason over zero
   decisions (never 0); a foreign arm's run, and a completed run with no tally, are refused; a
   failed run carrying a tally cannot even be constructed.
6. The probe: a rate over zero pairs fails, by construction; a pair is counted only where an
   input was carried and the full request replayed to the same binding decision. The real
   ``ConsensusArm`` is a ``PathwayConsultant`` and the ``UnavailableConsensusArm`` stand-in is
   not: the structural check the E5 CLI's probe step makes before it consults anything.
7. (``slow``, CI only) Over real twin states -- ``uplift.e5_suite.e5_probe_observations``, the
   one sampler the E5 CLI's probe step also calls (finding 109) -- and the real protocol and
   agents, the probe reports a non-empty pair count for every input, to a canonical-JSON
   artifact whose schema is asserted. It asserts NOTHING about whether any input changes the
   decision: by R7.21 an unresponsive pathway is a finding reported beside E5, never a
   relabelling of it.
8. (``slow``, CI only) One real reorders-only closed-loop run through the harness counts every
   decide it made in exactly one bucket, and its dispatch record round-trips canonically -- the
   per-run dispatched/withheld/blocked/untranslatable count of task 29.6's Demo.

**Pure except clauses 7 and 8.** Clauses 1-6 build protocol outputs by hand: no agent, no twin,
no protocol run. Budget inherited from ``HYPOTHESIS_PROFILE``; no ``max_examples`` literal. Locus:
``ci.yml::uplift-verify``, the fast step for clauses 1-6 and the slow step for clauses 7 and 8.
"""

from __future__ import annotations

import copy
import dataclasses
import functools
import json
from typing import TYPE_CHECKING, Any, Final
from uuid import uuid4

import pytest
from hypothesis import given
from hypothesis import strategies as st
from synapse_common.a2a_sdk import A2AResponse
from synapse_common.models import (
    AgentName,
    AgentProposal,
    ConsensusDecision,
    ContextMessage,
    DecisionTier,
)

from digital_twin.simulation.monte_carlo import ShockParams
from digital_twin.simulation.world import load_world
from uplift.consensus_arm import (
    ALL_LEVERS,
    ConsensusArm,
    ConsensusOutcome,
    DispatchClassification,
    build_consensus_arm,
    consensus_decision_to_policy_action,
    expressed_levers,
    observation_to_decision_request,
)
from uplift.dispatch import (
    DISPATCH_WORDING,
    PROBE_INPUTS,
    DecisionCountsRecord,
    DispatchReport,
    DispatchReportError,
    PathwayConsultant,
    PathwayProbeError,
    PathwayProbeReport,
    ProbeInputResult,
    RunDispatchRecord,
    carries_input,
    read_dispatch_report,
    read_probe_report,
    response_rate,
    run_pathway_probe,
    summarise_dispatch,
    withhold_input,
    write_dispatch_report,
    write_probe_report,
)
from uplift.e5_suite import (
    E5_CONSENSUS_LEVERS,
    E5_PROBE_OBSERVE_AT_HOURS,
    E5_PROBE_TWIN_SEED,
    e5_probe_observations,
)
from uplift.harness import LoopConfig, run_closed_loop
from uplift.interfaces import (
    DecisionCounts,
    KpiVector,
    Observation,
    PolicyAction,
    RunScoped,
    Scenario,
    ScenarioRun,
)
from uplift.policies import UnavailableConsensusArm

if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import Path

    from uplift.dispatch import ProbeInput


# ---------------------------------------------------------------------------
# Doubles and builders (pure)
# ---------------------------------------------------------------------------
_SKUS: Final[tuple[str, ...]] = tuple(f"sku_{index}" for index in range(12))
_SUPPLIERS: Final[tuple[str, ...]] = ("sup_a", "sup_b", "sup_c")

#: The engine's own confidence-floor wording (orchestrator/guardrails/rules.py:462).
_CONFIDENCE_VIOLATION: Final[str] = "Confidence 0.600 below threshold 0.7"

#: What `ConsensusProtocol._record_withheld_dispatch` stamps (protocol.py:962-964).
_WITHHELD_TRACE: Final[tuple[str, ...]] = (
    "dispatch=withheld",
    "withheld_by=guardrail_violation",
    "violations=1",
    "audit_id=constructed",
)

_KPIS: Final[KpiVector] = KpiVector(
    fill_rate=0.9,
    spoilage_rate=0.01,
    stockout_rate=0.05,
    avg_delivery_time_min=20.0,
    margin=100.0,
    co2_estimate=1.0,
    avg_on_hand_units=50.0,
    objective=10.0,
)


async def _no_transport(**_: Any) -> A2AResponse:
    """The transport a scripted protocol never dials; ``ConsensusArm`` refuses to exist without."""
    return A2AResponse(id="unused", result={})


class _ScriptedProtocol:
    """A ``run_consensus``-shaped double: its script in order, cycling; an exception is raised."""

    def __init__(self, script: list[ConsensusDecision | Exception]) -> None:
        self._script = list(script)
        self.requests: list[dict[str, Any]] = []

    async def run_consensus(self, decision_request: dict[str, Any]) -> ConsensusDecision:
        self.requests.append(decision_request)
        step = self._script[(len(self.requests) - 1) % len(self._script)]
        if isinstance(step, Exception):
            raise step
        return step


def _arm(script: list[ConsensusDecision | Exception], *, levers: frozenset[str]) -> ConsensusArm:
    return ConsensusArm(protocol=_ScriptedProtocol(script), transport=_no_transport, levers=levers)


def _observation(**overrides: Any) -> Observation:
    """An observation carrying all five task-13.1 fields, every input non-empty."""
    fields: dict[str, Any] = {
        "inventory": {"sku_1": 9, "sku_0": 4},
        "sim_time": 60.0,
        "delivery_count": 3,
        "spoilage_count": 0,
        "stockout_count": 1,
        "unit_costs": {"sku_1": 1.5, "sku_0": 1.0},
        "on_order": {"sku_0": 20.0},
        "supplier_lead_time_history": {"sup_b": (), "sup_a": (250.0,)},
        "demand_to_date": {"sku_1": 2, "sku_0": 5},
        "sku_supplier": {"sku_1": "sup_b", "sku_0": "sup_a"},
        "start_weekday": 4,
    }
    fields.update(overrides)
    return Observation(**fields)


def _decision(
    action: dict[str, Any],
    *,
    trace: tuple[str, ...],
    confirmations: tuple[str, ...],
    ratification: dict[str, Any] | None,
    confidence: float,
) -> ConsensusDecision:
    """A protocol output built by hand: one binding proposal whose payload is ``action``."""
    proposal = AgentProposal(
        agent_name=AgentName.INVENTORY_SENTINEL,
        decision_id=uuid4(),
        utility_score=0.85,
        confidence=confidence,
        justification_trace=["constructed"],
        payload=action,
        tier=DecisionTier.TIER_2,
    )
    context = (
        []
        if ratification is None
        else [
            ContextMessage(
                source="orchestrator",
                content={"type": "dispatch_ratification", **ratification},
            )
        ]
    )
    return ConsensusDecision(
        tier=DecisionTier.TIER_2,
        proposals=[proposal],
        selected_action=action,
        pareto_weights={},
        confidence=confidence,
        audit_trace=["tier=tier_2", "phase=4", *trace],
        phase_reached=4,
        context_messages=context,
        execution_confirmations=list(confirmations),
    )


def _dispatched(action: dict[str, Any]) -> ConsensusDecision:
    """A decision as ``_phase_execute`` returns it: ratified, one confirmation per proposal."""
    return _decision(
        action,
        trace=("audit_id=constructed", "confirmations=1"),
        confirmations=("acknowledged",),
        ratification={"passed": True, "violations": [], "twin_veto": False},
        confidence=0.9,
    )


def _withheld_for_confidence(action: dict[str, Any]) -> ConsensusDecision:
    return _decision(
        action,
        trace=_WITHHELD_TRACE,
        confirmations=(),
        ratification={"passed": False, "violations": [_CONFIDENCE_VIOLATION], "twin_veto": False},
        confidence=0.6,
    )


# ---------------------------------------------------------------------------
# Clause 1 -- the request carries what the world rewards, canonically
# ---------------------------------------------------------------------------
_MINUTES = st.floats(min_value=30.0, max_value=1440.0, allow_nan=False, allow_infinity=False)


@st.composite
def _planner_observations(draw: st.DrawFn) -> Observation:
    skus = draw(st.lists(st.sampled_from(_SKUS), min_size=1, max_size=6, unique=True))
    in_transit = draw(st.lists(st.sampled_from(skus), unique=True))
    demanded = draw(st.lists(st.sampled_from(skus), unique=True))
    suppliers = draw(st.lists(st.sampled_from(_SUPPLIERS), min_size=1, unique=True))
    return Observation(
        inventory={sku: draw(st.integers(min_value=0, max_value=400)) for sku in skus},
        sim_time=draw(st.floats(min_value=0.0, max_value=1440.0, allow_nan=False)),
        delivery_count=draw(st.integers(min_value=0, max_value=500)),
        spoilage_count=draw(st.integers(min_value=0, max_value=50)),
        stockout_count=draw(st.integers(min_value=0, max_value=50)),
        unit_costs={sku: draw(st.floats(min_value=0.5, max_value=10.0)) for sku in skus},
        on_order={
            sku: draw(st.floats(min_value=0.25, max_value=500.0, allow_nan=False))
            for sku in in_transit
        },
        supplier_lead_time_history={
            supplier: tuple(draw(st.lists(_MINUTES, max_size=4))) for supplier in suppliers
        },
        demand_to_date={sku: draw(st.integers(min_value=0, max_value=900)) for sku in demanded},
        sku_supplier={sku: draw(st.sampled_from(suppliers)) for sku in skus},
        start_weekday=draw(st.none() | st.integers(min_value=0, max_value=6)),
    )


def _flipped(mapping: Mapping[str, Any]) -> dict[str, Any]:
    return dict(reversed(list(mapping.items())))


def _reassembled(obs: Observation) -> Observation:
    """The same observation with every mapping built in the reverse insertion order."""
    return dataclasses.replace(
        obs,
        inventory=_flipped(obs.inventory),
        unit_costs=_flipped(obs.unit_costs),
        on_order=_flipped(obs.on_order),
        supplier_lead_time_history=_flipped(obs.supplier_lead_time_history),
        demand_to_date=_flipped(obs.demand_to_date),
        sku_supplier=_flipped(obs.sku_supplier),
    )


_MAPPING_KEYS: Final[tuple[str, ...]] = (
    "inventory",
    "unit_costs",
    "on_order",
    "inventory_position",
    "demand_to_date",
    "supplier_lead_time_history",
    "sku_supplier",
)


@given(obs=_planner_observations())
def test_the_request_carries_what_the_world_rewards_in_one_canonical_order(
    obs: Observation,
) -> None:
    request = observation_to_decision_request(obs)

    # Restated here independently of the subject: position is on hand plus on order.
    assert request["inventory_position"] == {
        sku: level + obs.on_order.get(sku, 0.0) for sku, level in obs.inventory.items()
    }
    assert request["on_order"] == dict(obs.on_order)
    assert request["demand_to_date"] == dict(obs.demand_to_date)
    assert request["supplier_lead_time_history"] == {
        supplier: list(times) for supplier, times in obs.supplier_lead_time_history.items()
    }
    assert request["sku_supplier"] == dict(obs.sku_supplier)
    assert request["start_weekday"] == obs.start_weekday
    assert request["sku_ids"] == sorted(obs.inventory)
    for key in _MAPPING_KEYS:
        assert list(request[key]) == sorted(request[key]), key

    canonical = json.dumps(request, sort_keys=True, separators=(",", ":"))
    assert json.loads(canonical) == request
    # Order-SENSITIVE equality: the same bytes, not merely the same parsed value.
    assert json.dumps(observation_to_decision_request(_reassembled(obs))) == json.dumps(request)


def test_each_of_the_five_fields_and_the_position_reaches_the_request() -> None:
    request = observation_to_decision_request(_observation())

    assert request["on_order"] == {"sku_0": 20.0}
    assert request["inventory_position"] == {"sku_0": 24.0, "sku_1": 9.0}
    assert request["demand_to_date"] == {"sku_0": 5, "sku_1": 2}
    assert request["supplier_lead_time_history"] == {"sup_a": [250.0], "sup_b": []}
    assert request["sku_supplier"] == {"sku_0": "sup_a", "sku_1": "sup_b"}
    assert request["start_weekday"] == 4

    # With no world the twin reports all five empty, and the position is the on-hand level.
    bare = observation_to_decision_request(
        Observation(
            inventory={"sku_1": 3, "sku_0": 7},
            sim_time=0.0,
            delivery_count=0,
            spoilage_count=0,
            stockout_count=0,
            unit_costs={"sku_1": 1.5, "sku_0": 1.0},
        )
    )
    assert bare["on_order"] == {}
    assert bare["demand_to_date"] == {}
    assert bare["supplier_lead_time_history"] == {}
    assert bare["sku_supplier"] == {}
    assert bare["start_weekday"] is None
    assert bare["inventory_position"] == {"sku_0": 7.0, "sku_1": 3.0}


# ---------------------------------------------------------------------------
# Clause 2 -- one bucket per decision, by the stated precedence
# ---------------------------------------------------------------------------
@dataclasses.dataclass(frozen=True)
class _Withhold:
    """One shape of protocol output, and what the I-6-safe reading must conclude about it."""

    name: str
    trace: tuple[str, ...]
    confirmations: tuple[str, ...]
    ratification: dict[str, Any] | None
    action_extras: dict[str, Any]
    confidence: float
    blocked: bool
    withheld: bool


def _confidence_record() -> dict[str, Any]:
    return {"passed": False, "violations": [_CONFIDENCE_VIOLATION], "twin_veto": False}


_WITHHOLDS: Final[tuple[_Withhold, ...]] = (
    _Withhold(
        name="ratified_and_dispatched",
        trace=("audit_id=constructed", "confirmations=1"),
        confirmations=("acknowledged",),
        ratification={"passed": True, "violations": [], "twin_veto": False},
        action_extras={},
        confidence=0.9,
        blocked=False,
        withheld=False,
    ),
    _Withhold(
        name="withheld_for_confidence_alone",
        trace=_WITHHELD_TRACE,
        confirmations=(),
        ratification=_confidence_record(),
        action_extras={},
        confidence=0.6,
        blocked=False,
        withheld=True,
    ),
    _Withhold(
        name="withheld_for_confidence_after_a_clip",
        trace=_WITHHELD_TRACE,
        confirmations=(),
        ratification={
            "passed": False,
            "violations": [
                "Essential price cap CLIPPED: rice from 1.50 to 1.3",
                _CONFIDENCE_VIOLATION,
            ],
            "twin_veto": False,
        },
        action_extras={"pricing_actions": [{"category": "rice", "multiplier": 1.3}]},
        confidence=0.6,
        blocked=False,
        withheld=True,
    ),
    _Withhold(
        # The engine returned at the confidence floor (rules.py:376-377) and never reached the
        # service-level minimum (rules.py:379), so the record names confidence alone.
        name="confidence_failure_masking_the_service_level_minimum",
        trace=_WITHHELD_TRACE,
        confirmations=(),
        ratification=_confidence_record(),
        action_extras={"predicted_fill_rate": 0.5},
        confidence=0.6,
        blocked=True,
        withheld=True,
    ),
    _Withhold(
        name="privacy_boundary_block",
        trace=_WITHHELD_TRACE,
        confirmations=(),
        ratification={
            "passed": False,
            "violations": [
                "Privacy boundary BLOCKED: raw demand payload at raw_demand crosses a store "
                "boundary (stores=store_a, store_b; recipients=none)"
            ],
            "twin_veto": False,
        },
        action_extras={"store_id": "store_a", "target_store_id": "store_b", "raw_demand": [3]},
        confidence=0.9,
        blocked=True,
        withheld=True,
    ),
    _Withhold(
        name="rider_shift_reject",
        trace=_WITHHELD_TRACE,
        confirmations=(),
        ratification={
            "passed": False,
            "violations": ["Rider shift limit exceeded: 12h > 10h max"],
            "twin_veto": False,
        },
        action_extras={"routing_actions": [{"rider_shift_hours": 12}]},
        confidence=0.9,
        blocked=True,
        withheld=True,
    ),
    _Withhold(
        name="tier_four_twin_veto",
        trace=("dispatch=withheld", "withheld_by=twin_disagreement", "violations=1"),
        confirmations=(),
        ratification={"passed": True, "violations": [], "twin_veto": True},
        action_extras={},
        confidence=0.9,
        blocked=True,
        withheld=True,
    ),
    _Withhold(
        name="withheld_by_an_unknown_gate",
        trace=("dispatch=withheld", "withheld_by=a_later_gate", "violations=1"),
        confirmations=(),
        ratification=_confidence_record(),
        action_extras={},
        confidence=0.6,
        blocked=True,
        withheld=True,
    ),
    _Withhold(
        name="withheld_with_no_ratification_record",
        trace=_WITHHELD_TRACE,
        confirmations=(),
        ratification=None,
        action_extras={},
        confidence=0.6,
        blocked=True,
        withheld=True,
    ),
    _Withhold(
        name="withheld_with_two_withheld_by_markers",
        trace=(*_WITHHELD_TRACE, "withheld_by=guardrail_violation"),
        confirmations=(),
        ratification=_confidence_record(),
        action_extras={},
        confidence=0.6,
        blocked=True,
        withheld=True,
    ),
    _Withhold(
        name="withheld_yet_confirmed_as_executed",
        trace=_WITHHELD_TRACE,
        confirmations=("acknowledged",),
        ratification=_confidence_record(),
        action_extras={},
        confidence=0.6,
        blocked=True,
        withheld=True,
    ),
    _Withhold(
        name="neither_withheld_nor_confirmed",
        trace=("audit_id=constructed",),
        confirmations=(),
        ratification=None,
        action_extras={},
        confidence=0.9,
        blocked=True,
        withheld=False,
    ),
)

_WITHHOLD_BY_NAME: Final[dict[str, _Withhold]] = {shape.name: shape for shape in _WITHHOLDS}


@dataclasses.dataclass(frozen=True)
class _Binding:
    """A binding payload, with the levers and the reorders it expresses stated independently."""

    name: str
    payload: dict[str, Any]
    levers: frozenset[str]
    reorders: dict[str, float]
    price: float | None


def _sentinel_entry(sku: str, action_type: str, quantity: float) -> dict[str, Any]:
    """One ``InventoryAction`` as the Inventory Sentinel serialises it into ``actions``."""
    return {
        "store_id": "",
        "sku_id": sku,
        "action_type": action_type,
        "quantity": quantity,
        "safety_stock_multiplier": 1.5,
        "reorder_point": 3.0,
        "confidence": 0.85,
    }


_BINDINGS: Final[tuple[_Binding, ...]] = (
    _Binding(
        name="a_reorder_map",
        payload={"reorder_quantities": {"sku_0": 10.0}},
        levers=frozenset({"reorder"}),
        reorders={"sku_0": 10.0},
        price=None,
    ),
    _Binding(
        name="the_inventory_sentinels_actions",
        payload={
            "actions": [
                _sentinel_entry("sku_1", "reorder", 7.5),
                _sentinel_entry("sku_0", "markdown", 2.0),
            ]
        },
        levers=frozenset({"reorder"}),
        reorders={"sku_1": 7.5},
        price=None,
    ),
    _Binding(
        name="a_price",
        payload={"price": 4.0},
        levers=frozenset({"price"}),
        reorders={},
        price=4.0,
    ),
    _Binding(
        name="a_reorder_and_a_price",
        payload={"reorder_quantities": {"sku_0": 10.0}, "price": 4.0},
        levers=frozenset({"reorder", "price"}),
        reorders={"sku_0": 10.0},
        price=4.0,
    ),
    _Binding(
        name="the_pricing_oracles_updates",
        payload={"updates": [{"sku_id": "sku_0", "final_price": 3.0, "pricing_id": "p-1"}]},
        levers=frozenset(),
        reorders={},
        price=None,
    ),
)

_LEVER_SETS: Final[tuple[frozenset[str], ...]] = (
    ALL_LEVERS,
    frozenset({"reorder"}),
    frozenset({"price"}),
)


def _expected_bucket(withhold: _Withhold, binding: _Binding, levers: frozenset[str]) -> str:
    """The precedence restated independently of the subject: blocked > untranslatable >
    withheld > dispatched."""
    if withhold.blocked:
        return "guardrail_blocked"
    if not binding.levers or not binding.levers <= levers:
        return "untranslatable"
    if withhold.withheld:
        return "withheld_for_confidence"
    return "dispatched"


def _decision_for(withhold: _Withhold, binding: _Binding) -> ConsensusDecision:
    action = {**copy.deepcopy(binding.payload), **copy.deepcopy(withhold.action_extras)}
    return _decision(
        action,
        trace=withhold.trace,
        confirmations=withhold.confirmations,
        ratification=copy.deepcopy(withhold.ratification),
        confidence=withhold.confidence,
    )


@pytest.mark.parametrize("levers", _LEVER_SETS, ids=lambda levers: "+".join(sorted(levers)))
@pytest.mark.parametrize("binding", _BINDINGS, ids=lambda binding: binding.name)
@pytest.mark.parametrize("withhold", _WITHHOLDS, ids=lambda withhold: withhold.name)
def test_every_decision_lands_in_exactly_one_bucket_by_the_stated_precedence(
    withhold: _Withhold, binding: _Binding, levers: frozenset[str]
) -> None:
    arm = _arm([_decision_for(withhold, binding)], levers=levers)
    expected = _expected_bucket(withhold, binding, levers)

    outcome = arm.consult(_observation())
    assert outcome.dispatch.bucket == expected, outcome.dispatch.reason
    assert outcome.dispatch.reason.strip()
    assert outcome.dispatch.applies is (expected in ("dispatched", "withheld_for_confidence"))

    applied = arm.decide(_observation())
    if outcome.dispatch.applies:
        assert applied.reorder_quantities == binding.reorders
        assert applied.price == binding.price
    else:
        assert applied == PolicyAction()


def test_an_excluded_lever_is_untranslatable_and_its_reason_names_the_suites_lever_set() -> None:
    reorders_only = frozenset({"reorder"})
    outcome = _arm(
        [_dispatched({"reorder_quantities": {"sku_0": 10.0}, "price": 4.0})], levers=reorders_only
    ).consult(_observation())

    assert outcome.dispatch.bucket == "untranslatable"
    assert "['price']" in outcome.dispatch.reason
    assert "['reorder']" in outcome.dispatch.reason
    assert outcome.action == PolicyAction()


@pytest.mark.parametrize(
    "payload",
    [
        {"reorder_quantities": {"SKU001": 10.0}},
        {"reorder_quantities": {"sku_0": 5.0, "SKU001": 10.0}},
        {"actions": [_sentinel_entry("SKU001", "reorder", 7.5)]},
    ],
    ids=["an_unstocked_sku", "a_stocked_and_an_unstocked_sku", "the_sentinels_default_sku"],
)
def test_a_reorder_for_a_sku_the_world_does_not_stock_is_untranslatable_and_applies_nothing(
    payload: dict[str, Any],
) -> None:
    """Finding 112: every agent reads its request one level too shallow, so the Inventory
    Sentinel orders its default ``SKU001``, which no twin stocks. Under structure 3 the twin
    refuses that order, failing the run (CI run 41265189389). The arm must not hand it over.
    A recommendation naming a stocked SKU beside an unstocked one applies nothing at all."""
    arm = _arm([_dispatched(payload)], levers=frozenset({"reorder"}))
    observation = _observation()
    assert "SKU001" not in observation.inventory

    outcome = arm.consult(observation)
    assert outcome.dispatch.bucket == "untranslatable", outcome.dispatch.reason
    assert "['SKU001']" in outcome.dispatch.reason
    assert outcome.action == PolicyAction()

    arm.begin_run(7)
    assert arm.decide(observation) == PolicyAction()
    assert arm.end_run() == DecisionCounts(
        dispatched=0, withheld_for_confidence=0, guardrail_blocked=0, untranslatable=1
    )


def test_a_blocked_reorder_for_an_unstocked_sku_stays_blocked_by_the_precedence() -> None:
    """blocked > untranslatable: an unstocked SKU never lifts a refusal into another bucket."""
    blocked = next(withhold for withhold in _WITHHOLDS if withhold.blocked)
    binding = _Binding(
        name="unstocked",
        payload={"reorder_quantities": {"SKU001": 10.0}},
        levers=frozenset({"reorder"}),
        reorders={"SKU001": 10.0},
        price=None,
    )
    outcome = _arm([_decision_for(blocked, binding)], levers=frozenset({"reorder"})).consult(
        _observation()
    )
    assert outcome.dispatch.bucket == "guardrail_blocked", outcome.dispatch.reason
    assert outcome.action == PolicyAction()


@pytest.mark.parametrize(
    "levers",
    [frozenset(), frozenset({"reorders"}), frozenset({"reorder", "markdown"})],
    ids=["empty", "misspelt", "unknown_lever"],
)
def test_a_lever_set_naming_no_lever_or_an_unknown_one_is_refused(levers: frozenset[str]) -> None:
    with pytest.raises(ValueError, match="lever"):
        _arm([_dispatched({"price": 1.0})], levers=levers)
    with pytest.raises(ValueError, match="lever"):
        build_consensus_arm(
            agent_handlers={"pricing_oracle": lambda request: {"jsonrpc": "2.0", "result": {}}},
            twin_handler=lambda request: {"jsonrpc": "2.0", "result": {}},
            protocol=_ScriptedProtocol([_dispatched({"price": 1.0})]),
            levers=levers,
        )


# ---------------------------------------------------------------------------
# Clause 3 -- the Inventory Sentinel's reorders translate as its own execute enacts them
# ---------------------------------------------------------------------------
def test_the_inventory_sentinels_reorder_entries_translate_to_reorders_and_nothing_else() -> None:
    payload = {
        "actions": [
            _sentinel_entry("sku_1", "reorder", 7.5),
            _sentinel_entry("sku_1", "reorder", 2.5),
            _sentinel_entry("sku_0", "markdown", 2.0),
            _sentinel_entry("sku_3", "transfer", 4.0),
            _sentinel_entry("sku_2", "reorder", 0.0),
        ]
    }
    action = consensus_decision_to_policy_action(_dispatched(payload), _observation())

    # Entries for one SKU add; a zero reorder keeps the lever expressed ("order nothing").
    assert action.reorder_quantities == {"sku_1": 10.0, "sku_2": 0.0}
    # A dict is not a disruption-action name: the list no longer stringifies into one.
    assert action.disruption_actions == frozenset()
    assert action.price is None
    assert expressed_levers(action) == frozenset({"reorder"})


# ---------------------------------------------------------------------------
# Clause 4 -- the per-run tally
# ---------------------------------------------------------------------------
def test_a_runs_counts_sum_to_what_it_decided_and_reset_at_begin_run() -> None:
    one_per_bucket: list[ConsensusDecision | Exception] = [
        _dispatched({"reorder_quantities": {"sku_0": 1.0}}),
        _withheld_for_confidence({"reorder_quantities": {"sku_0": 2.0}}),
        _decision_for(_WITHHOLD_BY_NAME["privacy_boundary_block"], _BINDINGS[0]),
        _dispatched({"updates": []}),  # expresses no lever
        RuntimeError("consensus exploded"),
    ]
    arm = _arm(one_per_bucket, levers=ALL_LEVERS)
    assert isinstance(arm, RunScoped)

    arm.begin_run(7)
    for _ in range(4):
        arm.decide(_observation())
    with pytest.raises(RuntimeError, match="consensus exploded"):
        arm.decide(_observation())
    counts = arm.end_run()
    assert counts == DecisionCounts(
        dispatched=1, withheld_for_confidence=1, guardrail_blocked=1, untranslatable=1
    )
    assert counts.total == 4

    arm.begin_run(8)
    arm.consult(_observation())  # the probe's entry point counts nothing
    assert arm.end_run() == DecisionCounts(
        dispatched=0, withheld_for_confidence=0, guardrail_blocked=0, untranslatable=0
    )
    with pytest.raises(RuntimeError, match="no run open"):
        arm.end_run()
    assert (
        DecisionCounts(
            dispatched=1, withheld_for_confidence=2, guardrail_blocked=3, untranslatable=4
        ).total
        == 10
    )


# ---------------------------------------------------------------------------
# Clause 5 -- the dispatch report
# ---------------------------------------------------------------------------
def _run(seed: int, counts: DecisionCounts | None, *, failed: bool, arm: str) -> ScenarioRun:
    return ScenarioRun(
        arm=arm,
        seed=seed,
        kpis=None if failed else _KPIS,
        failed=failed,
        error="RuntimeError: constructed" if failed else None,
        decision_counts=counts,
    )


def _counts(dispatched: int, withheld: int, blocked: int, untranslatable: int) -> DecisionCounts:
    return DecisionCounts(
        dispatched=dispatched,
        withheld_for_confidence=withheld,
        guardrail_blocked=blocked,
        untranslatable=untranslatable,
    )


def test_the_dispatch_rate_is_dispatched_over_total_beside_per_run_tallies_in_run_order(
    tmp_path: Path,
) -> None:
    runs = [
        _run(5, _counts(3, 1, 0, 0), failed=False, arm="consensus"),
        _run(2, _counts(1, 1, 1, 1), failed=False, arm="consensus"),
        _run(9, None, failed=True, arm="consensus"),
    ]
    report = summarise_dispatch(runs, arm="consensus")

    assert report.wording == DISPATCH_WORDING == "recommendations, if executed"
    assert (report.runs, report.completed_runs, report.failed_runs) == (3, 2, 1)
    assert report.counts == DecisionCountsRecord(
        dispatched=4, withheld_for_confidence=2, guardrail_blocked=1, untranslatable=1, total=8
    )
    assert report.dispatch_rate == 4 / 8
    assert report.rate_unavailable_reason is None
    seen = [(run.seed, run.failed) for run in report.per_run]
    assert seen == [(5, False), (2, False), (9, True)]
    assert report.per_run[2].counts is None

    path = write_dispatch_report(tmp_path / "dispatch.json", report)
    text = path.read_text(encoding="utf-8")
    assert text == json.dumps(json.loads(text), sort_keys=True, separators=(",", ":"))
    assert read_dispatch_report(path) == report

    for tamper in ({"unexpected": 1}, {"dispatch_rate": 0.25}):
        payload = {**json.loads(text), **tamper}
        with pytest.raises(ValueError):
            DispatchReport.model_validate(payload)


def test_over_zero_decisions_the_rate_is_none_and_says_why_never_zero() -> None:
    report = summarise_dispatch(
        [
            _run(1, None, failed=True, arm="consensus"),
            _run(2, None, failed=True, arm="consensus"),
        ],
        arm="consensus",
    )

    assert report.counts.total == 0
    assert report.dispatch_rate is None
    assert report.rate_unavailable_reason is not None
    assert "2 of 2" in report.rate_unavailable_reason

    payload = json.loads(report.to_canonical_json())
    payload.update({"dispatch_rate": 0.0, "rate_unavailable_reason": None})
    with pytest.raises(ValueError):
        DispatchReport.model_validate(payload)


def test_a_dispatch_report_refuses_another_arms_run_and_an_untallied_completed_run() -> None:
    tallied = _run(1, _counts(1, 0, 0, 0), failed=False, arm="consensus")
    refused: tuple[list[ScenarioRun], ...] = (
        [],
        [tallied, _run(2, _counts(1, 0, 0, 0), failed=False, arm="tuned_static")],
        [tallied, _run(3, None, failed=False, arm="consensus")],
        [tallied, _run(4, _counts(0, 0, 0, 0), failed=False, arm="consensus")],
    )
    for runs in refused:
        with pytest.raises(DispatchReportError):
            summarise_dispatch(runs, arm="consensus")
    # A failed run carrying a tally never reaches the report: ScenarioRun refuses to exist
    # (uplift/interfaces.py, ScenarioRun.__post_init__), which is the stricter refusal. The
    # report's own per-run record refuses the same shape, so it cannot be written by hand either.
    with pytest.raises(ValueError, match="failed"):
        _run(5, _counts(1, 0, 0, 0), failed=True, arm="consensus")
    with pytest.raises(ValueError):
        RunDispatchRecord(seed=5, failed=True, counts=DecisionCountsRecord.of(_counts(1, 0, 0, 0)))
    assert summarise_dispatch([tallied], arm="consensus").dispatch_rate == 1.0


# ---------------------------------------------------------------------------
# Clause 6 -- the probe, over a pure double
# ---------------------------------------------------------------------------
class _OnOrderOnlyPathway:
    """A pathway that responds to on-order stock alone, and replays unstably at chosen times."""

    name = "consensus"
    levers = frozenset({"reorder"})

    def __init__(self, unstable_at: frozenset[float]) -> None:
        self._unstable_at = unstable_at
        self.calls = 0

    def consult(self, obs: Observation) -> ConsensusOutcome:
        self.calls += 1
        quantity = 10.0 if any(units > 0.0 for units in obs.on_order.values()) else 25.0
        if obs.sim_time in self._unstable_at:
            quantity += float(self.calls)  # a different decision on every call
        decision = _dispatched({"reorder_quantities": {"sku_0": quantity}})
        return ConsensusOutcome(
            request=observation_to_decision_request(obs),
            decision=decision,
            translated=consensus_decision_to_policy_action(decision, obs),
            dispatch=DispatchClassification(bucket="dispatched", reason="constructed"),
        )


def test_a_response_rate_over_zero_pairs_fails() -> None:
    with pytest.raises(PathwayProbeError):
        response_rate(pairs=0, changed=0)
    with pytest.raises(ValueError):
        ProbeInputResult(input_name="on_order", carried=1, pairs=0, changed=0, rate=0.0)
    assert response_rate(pairs=4, changed=1) == 0.25


@pytest.mark.parametrize("name", PROBE_INPUTS)
def test_withholding_an_input_changes_that_input_of_the_request_and_nothing_else(
    name: ProbeInput,
) -> None:
    obs = _observation()
    withheld = withhold_input(obs, name)

    assert carries_input(obs, name)
    assert not carries_input(withheld, name)
    full_request = observation_to_decision_request(obs)
    withheld_request = observation_to_decision_request(withheld)
    moved = {key for key in full_request if full_request[key] != withheld_request[key]}
    # Withholding open orders also withholds them from the position, by construction.
    assert moved == ({name, "inventory_position"} if name == "on_order" else {name})


def test_the_probe_counts_a_pair_only_where_an_input_was_carried_and_replayed_stably() -> None:
    stable = _observation(sim_time=60.0)
    unstable = _observation(sim_time=120.0)
    demand_only = _observation(sim_time=180.0, on_order={}, supplier_lead_time_history={})
    pathway = _OnOrderOnlyPathway(unstable_at=frozenset({120.0}))

    report = run_pathway_probe(pathway, [stable, unstable, demand_only])

    by_name = {result.input_name: result for result in report.inputs}
    history = by_name["supplier_lead_time_history"]
    assert [result.input_name for result in report.inputs] == list(PROBE_INPUTS)
    assert (report.observations, report.replay_unstable) == (3, 1)
    assert (by_name["on_order"].carried, by_name["on_order"].pairs) == (2, 1)
    assert (by_name["on_order"].changed, by_name["on_order"].rate) == (1, 1.0)
    assert (history.carried, history.pairs, history.changed) == (2, 1, 0)
    assert (by_name["demand_to_date"].carried, by_name["demand_to_date"].pairs) == (3, 2)
    assert by_name["demand_to_date"].changed == 0
    assert report.unresponsive_inputs == ("supplier_lead_time_history", "demand_to_date")
    assert report.full_request_buckets.dispatched == report.full_request_buckets.total == 3

    payload = json.loads(report.to_canonical_json())
    payload["unresponsive_inputs"] = []
    with pytest.raises(ValueError):
        PathwayProbeReport.model_validate(payload)


def test_a_probe_with_no_contrast_for_an_input_fails_rather_than_reporting() -> None:
    demand_only = _observation(on_order={}, supplier_lead_time_history={})
    pathway = _OnOrderOnlyPathway(unstable_at=frozenset())
    with pytest.raises(PathwayProbeError, match="zero pairs"):
        run_pathway_probe(pathway, [demand_only])
    assert pathway.calls == 0  # refused before a single consult was spent

    replay_fails = _OnOrderOnlyPathway(unstable_at=frozenset({60.0}))
    with pytest.raises(PathwayProbeError, match="replay"):
        run_pathway_probe(replay_fails, [_observation(sim_time=60.0)])


def test_the_consensus_arm_is_a_pathway_the_probe_can_consult_and_its_stand_in_is_not() -> None:
    arm = _arm([_dispatched({"price": 1.0})], levers=E5_CONSENSUS_LEVERS)
    assert isinstance(arm, PathwayConsultant)
    assert arm.levers == E5_CONSENSUS_LEVERS

    stand_in = UnavailableConsensusArm("no network here")
    assert not isinstance(stand_in, PathwayConsultant)
    assert not hasattr(stand_in, "consult")
    assert not hasattr(stand_in, "levers")
    # Clause 6's double passes the same structural check, so the CLI would probe it too.
    assert isinstance(_OnOrderOnlyPathway(unstable_at=frozenset()), PathwayConsultant)


# ---------------------------------------------------------------------------
# Clause 7 -- the probe over real twin states and the real pathway (slow, CI only)
# ---------------------------------------------------------------------------
def _twin_unavailable(request: dict[str, Any]) -> dict[str, Any]:
    """An honest JSON-RPC error: unshocked requests route to Tier 2 and never dial the twin."""
    return {
        "jsonrpc": "2.0",
        "id": str(request.get("id", "")),
        "error": {"code": -32004, "message": "twin verification unavailable in the probe"},
    }


@functools.lru_cache(maxsize=1)
def _probe_arm() -> ConsensusArm:
    """The arm E5 runs -- the eight real agents and the real protocol -- assembled once."""
    return build_consensus_arm(twin_handler=_twin_unavailable, levers=E5_CONSENSUS_LEVERS)


@pytest.mark.slow
def test_the_probe_over_real_twin_states_reports_a_non_empty_pair_count_for_every_input(
    tmp_path: Path,
) -> None:
    observations = e5_probe_observations()
    assert len(observations) == len(E5_PROBE_OBSERVE_AT_HOURS)
    for name in PROBE_INPUTS:
        assert any(carries_input(obs, name) for obs in observations), name

    arm = _probe_arm()
    report = run_pathway_probe(arm, observations)

    assert [result.input_name for result in report.inputs] == list(PROBE_INPUTS)
    for result in report.inputs:
        assert result.pairs >= 1, result
        assert 0 <= result.changed <= result.pairs
        assert result.rate == result.changed / result.pairs
    assert report.unresponsive_inputs == tuple(
        result.input_name for result in report.inputs if result.changed == 0
    )
    assert report.observations == report.full_request_buckets.total == len(observations)
    assert report.levers == ("reorder",)

    path = write_probe_report(tmp_path / "pathway-probe.json", report)
    text = path.read_text(encoding="utf-8")
    payload = json.loads(text)
    assert set(payload) == {
        "kind",
        "schema_version",
        "arm",
        "levers",
        "observations",
        "replay_unstable",
        "full_request_buckets",
        "inputs",
        "unresponsive_inputs",
    }
    assert (payload["kind"], payload["schema_version"]) == ("consensus-pathway-probe", 1)
    for entry in payload["inputs"]:
        assert set(entry) == {"input_name", "carried", "pairs", "changed", "rate"}
    assert text == json.dumps(payload, sort_keys=True, separators=(",", ":"))
    assert read_probe_report(path) == report

    # By construction: with every input withheld from every observation there is no pair, and
    # the probe refuses to state a rate rather than reporting one over nothing.
    stripped = [
        withhold_input(
            withhold_input(withhold_input(obs, "on_order"), "supplier_lead_time_history"),
            "demand_to_date",
        )
        for obs in observations
    ]
    with pytest.raises(PathwayProbeError, match="zero pairs"):
        run_pathway_probe(arm, stripped)


#: Two decides, reorders-only as E5 runs them: enough for a real tally, cheap enough for CI.
_PROBE_LOOP: Final[LoopConfig] = LoopConfig(
    duration_hours=2.0, step_hours=1.0, levers="reorders_only"
)


@pytest.mark.slow
def test_a_real_closed_loop_run_counts_every_decision_it_made_in_exactly_one_bucket(
    tmp_path: Path,
) -> None:
    arm = _probe_arm()
    spec = load_world()
    scenario = Scenario(
        name="probe_primary_unshocked",
        seed=E5_PROBE_TWIN_SEED,
        shock=ShockParams(),
        world=spec.resolve(spec.primary_cell),
    )

    run = run_closed_loop(scenario, arm, E5_PROBE_TWIN_SEED, arm.name, _PROBE_LOOP)

    assert not run.failed, run.error
    assert run.decision_counts is not None
    # Every decide of the run is counted, once: the harness decides once per step.
    assert _PROBE_LOOP.n_steps >= 1
    assert run.decision_counts.total == _PROBE_LOOP.n_steps

    report = summarise_dispatch([run], arm=arm.name)
    assert report.counts == DecisionCountsRecord.of(run.decision_counts)
    seen = [(record.seed, record.failed) for record in report.per_run]
    assert seen == [(E5_PROBE_TWIN_SEED, False)]
    assert report.dispatch_rate == run.decision_counts.dispatched / _PROBE_LOOP.n_steps
    assert report.wording == DISPATCH_WORDING

    path = write_dispatch_report(tmp_path / "dispatch.json", report)
    text = path.read_text(encoding="utf-8")
    assert text == json.dumps(json.loads(text), sort_keys=True, separators=(",", ":"))
    assert read_dispatch_report(path) == report
