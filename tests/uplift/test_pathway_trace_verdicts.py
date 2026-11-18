# Feature: decision-quality-proof, session 13: the pathway probe's decisions, traced (ADR-058)
"""The pathway trace's helpers: the pair verdict, each refusal, and the shape of the record.

Subject: ``scripts/diagnostics/pathway_trace.py``, the CI measurement that records which agent
bound each decision R7.21's probe compares and why each pair moved or not (ADR-058, Falsification
item 1). No twin runs here, and no agent handler or consensus protocol is assembled.

Two tests reach past hand-built records, each for a reason. The q* property drives the Inventory
Sentinel's own ``InventorySentinelPipeline.decide`` (pure NumPy, no handler), because that is the
oracle the restated arithmetic must reproduce. The order test drives ``run_trace`` over a pure
double pathway, because a trace that consulted in another order than ``run_pathway_probe`` would
be refused in CI, and here that costs milliseconds.

Budget inherited from ``HYPOTHESIS_PROFILE``; no ``max_examples`` literal.
"""

from __future__ import annotations

import copy
import json
import math
from typing import TYPE_CHECKING, Any, Final
from uuid import uuid4

import pytest
from hypothesis import given
from hypothesis import strategies as st
from synapse_common.a2a_envelope import PROPOSAL_ENVELOPE_KEY, decision_context
from synapse_common.models import AgentName, AgentProposal, ConsensusDecision, DecisionTier

from agents.inventory_sentinel.inference.pipeline import InventorySentinelPipeline
from agents.inventory_sentinel.inference.request_state import forecast_from_request
from agents.inventory_sentinel.models.newsvendor import NewsvendorParams
from scripts.diagnostics.pathway_trace import (
    EXIT_REFUSED,
    EXIT_TRACED,
    EXIT_UNTRACEABLE,
    FULL_REQUEST,
    SENTINEL,
    TRACE_KIND,
    DecisionRecord,
    ObservationTrace,
    PairRecord,
    ProposalRecord,
    SentinelAction,
    SkuRecord,
    TraceDocument,
    Variant,
    build_document,
    evaluate_predictions,
    exit_code,
    input_counts,
    main,
    ordered_quantity,
    pair_record,
    production_refusals,
    q_star_basis,
    refused_document,
    run_trace,
    sentinel_q_star,
    summary_lines,
    trace_refusals,
    write_trace,
)
from uplift.consensus_arm import (
    ConsensusOutcome,
    DispatchClassification,
    consensus_decision_to_policy_action,
    observation_to_decision_request,
)
from uplift.dispatch import (
    PROBE_INPUTS,
    DecisionCountsRecord,
    PathwayProbeReport,
    ProbeInputResult,
    response_rate,
)
from uplift.interfaces import Observation, PolicyAction
from uplift.policies import UnavailableConsensusArm

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path


# ---------------------------------------------------------------------------
# Builders (pure)
# ---------------------------------------------------------------------------
_SKUS: Final[tuple[str, str]] = ("sku_a", "sku_b")
_STOCK: Final[float] = 40.0
#: A q* below the stock, so the SKU orders nothing.
_IDLE_Q_STAR: Final[float] = 12.5
_IDLE: Final[tuple[float, float]] = (0.0, 0.0)


def _sku(sku: str, quantity: float) -> SkuRecord:
    """A SKU whose restated order is ``quantity``, which the Sentinel also proposed."""
    q_star = _STOCK + quantity if quantity > 0.0 else _IDLE_Q_STAR
    ordered = ordered_quantity(q_star, _STOCK)
    return SkuRecord(
        sku=sku,
        inventory=int(_STOCK),
        on_order=None,
        inventory_position=_STOCK,
        demand_to_date=6,
        supplier="sup_a",
        landed_lead_times=1,
        mean_landed_lead_time_min=240.0,
        forecast={
            "on_hand": _STOCK,
            "lead_time_days": 240.0 / 1440.0,
            "mean": 3.0,
            "std": math.sqrt(3.0),
        },
        q_star=q_star,
        sentinel_stock=_STOCK,
        predicted_quantity=ordered,
        sentinel_action=SentinelAction(
            action_type="reorder",
            quantity=ordered,
            reorder_point=1.0,
            confidence=0.75,
            safety_stock_multiplier=1.0,
        ),
    )


def _record(variant: Variant, orders: tuple[float, float], agent: str | None) -> DecisionRecord:
    """A dispatched consult whose fingerprint is exactly its binding agent and its reorders."""
    reorders = dict(zip(_SKUS, orders, strict=True))
    return DecisionRecord(
        variant=variant,
        tier="tier_2",
        binding_agent=agent,
        bucket="dispatched",
        fingerprint=json.dumps({"agent": agent, "reorders": reorders}, sort_keys=True),
        translated_reorder_quantities=reorders,
        translated_price=None,
        translated_routing=None,
        translated_disruption_actions=(),
        proposals=(ProposalRecord(agent=SENTINEL, utility_score=0.9, confidence=0.9),),
        sentinel_proposals=1,
        sentinel_problems=(),
        request_rebuilt=True,
        skus=tuple(_sku(sku, quantity) for sku, quantity in reorders.items()),
    )


def _trace(
    index: int, full: DecisionRecord, withheld: Sequence[DecisionRecord], replay: str
) -> ObservationTrace:
    """A state carrying all three inputs; ``withheld`` is in PROBE_INPUTS order when stable."""
    stable = replay == full.fingerprint
    pairs: tuple[PairRecord, ...] = ()
    if stable:
        pairs = tuple(
            pair_record(name, full, record)
            for name, record in zip(PROBE_INPUTS, withheld, strict=True)
        )
    return ObservationTrace(
        index=index,
        sim_time=600.0 + 120.0 * index,
        carried_inputs=PROBE_INPUTS,
        replay_fingerprint=replay,
        replay_binding_agent=full.binding_agent,
        replay_stable=stable,
        variants=(full, *withheld),
        pairs=pairs,
    )


def _stable(
    index: int, full: tuple[float, float], withheld: Sequence[tuple[float, float]]
) -> ObservationTrace:
    """A replay-stable state; ``withheld`` holds the orders with each input withheld, in order."""
    head = _record(FULL_REQUEST, full, SENTINEL)
    rest = [
        _record(name, held, SENTINEL) for name, held in zip(PROBE_INPUTS, withheld, strict=True)
    ]
    return _trace(index, head, rest, head.fingerprint)


def _two_stable_states() -> tuple[ObservationTrace, ...]:
    """Withholding the lead-time history moves one order at state 0; nothing moves at state 1."""
    return (
        _stable(0, _IDLE, [_IDLE, (7.5, 0.0), _IDLE]),
        _stable(1, _IDLE, [_IDLE, _IDLE, _IDLE]),
    )


def _single(record: DecisionRecord) -> ObservationTrace:
    """A state that carries no input, so its one recorded consult is its full request."""
    return ObservationTrace(
        index=0,
        sim_time=600.0,
        carried_inputs=(),
        replay_fingerprint=record.fingerprint,
        replay_binding_agent=record.binding_agent,
        replay_stable=True,
        variants=(record,),
        pairs=(),
    )


def _report(
    changed: Sequence[int], *, observations: int, pairs: int, unstable: int
) -> PathwayProbeReport:
    """A production probe report stating ``changed`` per input, each input carried throughout."""
    inputs = tuple(
        ProbeInputResult(
            input_name=name,
            carried=observations,
            pairs=pairs,
            changed=moved,
            rate=response_rate(pairs=pairs, changed=moved),
        )
        for name, moved in zip(PROBE_INPUTS, changed, strict=True)
    )
    return PathwayProbeReport(
        kind="consensus-pathway-probe",
        schema_version=1,
        arm="consensus",
        levers=("reorder",),
        observations=observations,
        replay_unstable=unstable,
        full_request_buckets=DecisionCountsRecord(
            dispatched=observations,
            withheld_for_confidence=0,
            guardrail_blocked=0,
            untranslatable=0,
            total=observations,
        ),
        inputs=inputs,
        unresponsive_inputs=tuple(result.input_name for result in inputs if result.changed == 0),
    )


def _traced(observations: tuple[ObservationTrace, ...]) -> TraceDocument:
    """``observations`` built into a document beside a production report that agrees with them."""
    return build_document(
        arm="consensus",
        levers=("reorder",),
        basis=q_star_basis(NewsvendorParams()),
        observations=observations,
        production=_report((0, 1, 0), observations=2, pairs=2, unstable=0),
    )


# ---------------------------------------------------------------------------
# The pair verdict
# ---------------------------------------------------------------------------
def test_a_pair_moved_by_one_skus_order_names_that_sku_and_is_explained() -> None:
    full = _record(FULL_REQUEST, _IDLE, SENTINEL)
    withheld = _record("supplier_lead_time_history", (7.5, 0.0), SENTINEL)

    pair = pair_record("supplier_lead_time_history", full, withheld)

    assert pair.fingerprint_changed
    assert pair.quantity_changed_skus == ("sku_a",)
    assert pair.sentinel_quantity_changed_skus == ("sku_a",)
    assert not (pair.binding_agent_changed or pair.bucket_changed or pair.price_changed)
    assert pair.verdict_explained
    assert trace_refusals(_two_stable_states()) == ()
    with pytest.raises(ValueError, match="pair compares"):
        pair_record("on_order", full, withheld)


def test_a_fingerprint_that_moved_with_no_component_is_refused_as_unexplained() -> None:
    full = _record(FULL_REQUEST, _IDLE, SENTINEL)
    same = _record("on_order", _IDLE, SENTINEL)
    # The same agent, bucket and orders under other bytes: what a fingerprint carrying a
    # per-call field would do to every pair.
    drifted = same.model_copy(update={"fingerprint": same.fingerprint + " "})
    rest = [_record(name, _IDLE, SENTINEL) for name in PROBE_INPUTS[1:]]

    pair = pair_record("on_order", full, drifted)
    refusals = trace_refusals([_trace(0, full, [drifted, *rest], full.fingerprint)])

    assert pair.fingerprint_changed
    assert not pair.moved
    assert not pair.verdict_explained
    assert [refusal.check for refusal in refusals] == ["pair_verdict_unexplained"]
    assert "on_order withheld: binding_fingerprint reads changed" in refusals[0].detail


def test_an_order_that_moved_under_an_unchanged_fingerprint_is_refused_as_unexplained() -> None:
    full = _record(FULL_REQUEST, _IDLE, SENTINEL)
    moved = _record("demand_to_date", (3.0, 0.0), SENTINEL).model_copy(
        update={"fingerprint": full.fingerprint}
    )

    pair = pair_record("demand_to_date", full, moved)

    assert not pair.fingerprint_changed
    assert pair.quantity_changed_skus == ("sku_a",)
    assert not pair.verdict_explained


def test_a_change_of_binding_agent_alone_explains_a_changed_fingerprint() -> None:
    full = _record(FULL_REQUEST, _IDLE, SENTINEL)
    elsewhere = _record("demand_to_date", _IDLE, "supplier_trust")

    pair = pair_record("demand_to_date", full, elsewhere)

    assert pair.fingerprint_changed
    assert pair.binding_agent_changed
    assert pair.quantity_changed_skus == ()
    assert pair.verdict_explained


# ---------------------------------------------------------------------------
# Each refusal
# ---------------------------------------------------------------------------
def test_a_replay_that_binds_differently_contributes_no_pair_and_is_refused() -> None:
    full = _record(FULL_REQUEST, _IDLE, SENTINEL)
    unstable = _trace(0, full, [], _record(FULL_REQUEST, (2.0, 0.0), SENTINEL).fingerprint)
    stable = _stable(1, _IDLE, [_IDLE, (7.5, 0.0), _IDLE])

    refusals = trace_refusals([unstable, stable])
    counts = {
        count.input_name: (count.carried, count.pairs, count.changed)
        for count in input_counts([unstable, stable])
    }

    assert (unstable.replay_stable, unstable.pairs, len(unstable.variants)) == (False, (), 1)
    assert [refusal.check for refusal in refusals] == ["replay_unstable"]
    assert refusals[0].detail.startswith("observation 0 ")
    assert counts == {
        "on_order": (2, 1, 0),
        "supplier_lead_time_history": (2, 1, 1),
        "demand_to_date": (2, 1, 0),
    }
    # A withheld consult recorded after an unstable replay cannot even be constructed.
    with pytest.raises(ValueError, match="stable replay"):
        ObservationTrace(
            index=0,
            sim_time=600.0,
            carried_inputs=PROBE_INPUTS,
            replay_fingerprint=unstable.replay_fingerprint,
            replay_binding_agent=SENTINEL,
            replay_stable=False,
            variants=(full, *(_record(name, _IDLE, SENTINEL) for name in PROBE_INPUTS)),
            pairs=(),
        )


def test_counts_a_fresh_probe_does_not_reproduce_are_refused_and_equal_counts_are_not() -> None:
    states = _two_stable_states()
    agreeing = _report((0, 1, 0), observations=2, pairs=2, unstable=0)
    moved_on_order = _report((1, 1, 0), observations=2, pairs=2, unstable=0)
    one_unstable = _report((0, 1, 0), observations=2, pairs=1, unstable=1)

    assert production_refusals(states, agreeing) == ()
    (moved,) = production_refusals(states, moved_on_order)
    (unstable,) = production_refusals(states, one_unstable)

    assert moved.check == unstable.check == "production_disagrees"
    assert "on_order carried/pairs/changed (2, 2, 0) vs (2, 2, 1)" in moved.detail
    assert "supplier_lead_time_history" not in moved.detail
    assert "replay-unstable 0 vs 1" in unstable.detail


def test_a_production_probe_that_stated_no_rate_is_a_refusal_never_an_agreement() -> None:
    document = build_document(
        arm="consensus",
        levers=("reorder",),
        basis=q_star_basis(NewsvendorParams()),
        observations=_two_stable_states(),
        production="run_pathway_probe stated no rate over the same states: constructed",
    )

    assert [refusal.check for refusal in document.refusals] == ["production_not_compared"]
    assert document.production is not None
    assert document.production.report is None
    assert (document.verdict, exit_code(document)) == ("refused", EXIT_REFUSED)


def test_a_restated_order_the_sentinel_did_not_propose_is_refused() -> None:
    honest = _record(FULL_REQUEST, (7.5, 0.0), SENTINEL)
    first = honest.skus[0]
    assert first.sentinel_action is not None
    proposed = first.sentinel_action.model_copy(update={"quantity": 9.0})
    drifted = honest.model_copy(
        update={"skus": (first.model_copy(update={"sentinel_action": proposed}), honest.skus[1])}
    )

    assert trace_refusals([_single(honest)]) == ()
    (refusal,) = trace_refusals([_single(drifted)])
    assert refusal.check == "q_star_does_not_reproduce_the_sentinel"
    assert "first sku_a: restated 7.5, proposed 9.0" in refusal.detail


def test_an_unrebuilt_request_or_an_unreadable_sentinel_proposal_is_refused() -> None:
    honest = _record(FULL_REQUEST, _IDLE, SENTINEL)
    unrebuilt = honest.model_copy(update={"request_rebuilt": False})
    ambiguous = honest.model_copy(update={"sentinel_problems": ("2 Sentinel proposals",)})

    unrebuilt_checks = [refusal.check for refusal in trace_refusals([_single(unrebuilt)])]
    ambiguous_checks = [refusal.check for refusal in trace_refusals([_single(ambiguous)])]

    assert unrebuilt_checks == ["request_not_rebuilt"]
    assert ambiguous_checks == ["sentinel_proposal_ambiguous"]


# ---------------------------------------------------------------------------
# q* is the Sentinel's: the restated arithmetic against the agent's own decide
# ---------------------------------------------------------------------------
_UNITS = st.floats(min_value=0.0, max_value=1.0e4, allow_nan=False, allow_infinity=False)
_SPREAD = st.floats(min_value=0.0, max_value=1.0e3, allow_nan=False, allow_infinity=False)
_DAYS = st.floats(min_value=1.0e-3, max_value=10.0, allow_nan=False, allow_infinity=False)

#: The three shapes ``forecast_from_request`` gives a SKU: absent, unrated, and rated.
_ENTRIES = st.one_of(
    st.none(),
    st.fixed_dictionaries({"on_hand": _UNITS, "lead_time_days": _DAYS}),
    st.fixed_dictionaries(
        {"on_hand": _UNITS, "lead_time_days": _DAYS, "mean": _UNITS, "std": _SPREAD}
    ),
)


@given(entry=_ENTRIES)
def test_the_restated_q_star_orders_exactly_what_the_sentinels_own_decide_orders(
    entry: dict[str, float] | None,
) -> None:
    forecast = {} if entry is None else {"sku_x": entry}
    pipeline = InventorySentinelPipeline()
    (action,) = pipeline.decide(["sku_x"], "STORE_TEST", demand_forecast=forecast)

    q_star, stock = sentinel_q_star(entry, NewsvendorParams())

    assert ordered_quantity(q_star, stock) == action.quantity
    assert stock == (0.0 if entry is None else entry["on_hand"])


# ---------------------------------------------------------------------------
# The predictions
# ---------------------------------------------------------------------------
def _readings(states: Sequence[ObservationTrace]) -> dict[str, str]:
    return {reading.prediction: reading.reading for reading in evaluate_predictions(states)}


def test_each_prediction_reads_held_missed_or_unread_by_its_stated_rule() -> None:
    # With the history withheld, no SKU orders at state 1, so P4 misses there.
    expected = {"P1": "held", "P2": "held", "P3": "held", "P4": "missed"}
    assert _readings(_two_stable_states()) == expected
    assert set(_readings(()).values()) == {"unread"}

    head = _record(FULL_REQUEST, _IDLE, SENTINEL)
    unstable = _trace(0, head, [], _record(FULL_REQUEST, (2.0, 0.0), SENTINEL).fingerprint)
    assert _readings([unstable]) == {"P1": "held", "P2": "unread", "P3": "unread", "P4": "unread"}

    other = _record(FULL_REQUEST, _IDLE, "supplier_trust")
    bound_elsewhere = _trace(
        0,
        other,
        [_record(name, _IDLE, "supplier_trust") for name in PROBE_INPUTS],
        other.fingerprint,
    )
    assert _readings([bound_elsewhere])["P1"] == "missed"

    # P3's because-clause: no order either way, yet on-hand does not exceed q*.
    flat = _record("on_order", _IDLE, SENTINEL)
    level = tuple(sku.model_copy(update={"q_star": _STOCK}) for sku in flat.skus)
    on_hand_at_q_star = flat.model_copy(update={"skus": level})
    rest = [_record(name, _IDLE, SENTINEL) for name in PROBE_INPUTS[1:]]
    state = _trace(0, head, [on_hand_at_q_star, *rest], head.fingerprint)
    assert _readings([state])["P3"] == "missed"
    assert _readings([state])["P2"] == "held"


# ---------------------------------------------------------------------------
# The record's shape, and the file
# ---------------------------------------------------------------------------
def test_the_trace_is_one_canonical_json_document_whose_derived_fields_refuse_an_edit(
    tmp_path: Path,
) -> None:
    document = _traced(_two_stable_states())
    assert (document.verdict, exit_code(document)) == ("traced", EXIT_TRACED)
    assert document.refusals == ()

    text = write_trace(tmp_path / "probe-trace.json", document).read_text(encoding="utf-8")
    payload = json.loads(text)

    assert text == json.dumps(payload, sort_keys=True, separators=(",", ":"))
    assert (payload["kind"], payload["schema_version"]) == (TRACE_KIND, 1)
    assert set(payload) == {
        "arm",
        "input_counts",
        "kind",
        "levers",
        "observations",
        "predictions",
        "production",
        "q_star_basis",
        "refusals",
        "schema_version",
        "verdict",
    }
    variant = payload["observations"][0]["variants"][0]
    assert set(variant) == {
        "binding_agent",
        "bucket",
        "fingerprint",
        "proposals",
        "request_rebuilt",
        "sentinel_problems",
        "sentinel_proposals",
        "skus",
        "tier",
        "translated_disruption_actions",
        "translated_price",
        "translated_reorder_quantities",
        "translated_routing",
        "variant",
    }
    assert set(variant["skus"][0]) == {
        "demand_to_date",
        "forecast",
        "inventory",
        "inventory_position",
        "landed_lead_times",
        "mean_landed_lead_time_min",
        "on_order",
        "predicted_quantity",
        "q_star",
        "sentinel_action",
        "sentinel_stock",
        "sku",
        "supplier",
    }
    assert set(payload["observations"][0]["pairs"][1]) == {
        "binding_agent_changed",
        "bucket_changed",
        "disruption_changed",
        "fingerprint_changed",
        "forecast_changed_skus",
        "input_name",
        "price_changed",
        "quantity_changed_skus",
        "routing_changed",
        "sentinel_quantity_changed_skus",
        "verdict_explained",
    }
    assert TraceDocument.model_validate_json(text) == document

    edited_pair = copy.deepcopy(payload)
    edited_pair["observations"][0]["pairs"][1]["fingerprint_changed"] = False
    for edited in (
        {**payload, "verdict": "refused"},
        {**payload, "input_counts": []},
        {**payload, "predictions": []},
        edited_pair,
    ):
        with pytest.raises(ValueError):
            TraceDocument.model_validate(edited)


def test_the_trace_never_overwrites_a_file(tmp_path: Path) -> None:
    target = tmp_path / "probe-trace.json"
    target.write_text("an earlier run", encoding="utf-8")
    document = refused_document(
        arm="consensus", levers=(), check="arm_not_consultable", detail="constructed"
    )

    with pytest.raises(FileExistsError):
        write_trace(target, document)
    # The command refuses before it builds an arm, samples the twin or consults anything.
    assert main(["--output", str(target)]) == EXIT_UNTRACEABLE
    assert target.read_text(encoding="utf-8") == "an earlier run"


def test_the_summary_is_ascii_even_when_a_recorded_reason_is_not(tmp_path: Path) -> None:
    refused = refused_document(
        arm="consensus",
        levers=(),
        check="arm_not_consultable",
        detail="no agent network \u2014 the stand-in stood in",
    )
    output = tmp_path / "probe-trace.json"

    for document in (refused, _traced(_two_stable_states())):
        lines = summary_lines(document, output)
        assert lines
        assert all(line.isascii() for line in lines)
    refused_lines = summary_lines(refused, output)
    assert "REFUSED arm_not_consultable: no agent network ? the stand-in stood in" in refused_lines


# ---------------------------------------------------------------------------
# run_trace over doubles: the stand-in, no state, and the probe's consult order
# ---------------------------------------------------------------------------
def _proposal(agent: AgentName, payload: dict[str, Any], utility: float) -> AgentProposal:
    return AgentProposal(
        agent_name=agent,
        decision_id=uuid4(),
        utility_score=utility,
        confidence=utility,
        justification_trace=["constructed"],
        payload=payload,
        tier=DecisionTier.TIER_2,
    )


class _SentinelPathway:
    """A pure double whose binding proposal is the Inventory Sentinel's own ``decide``.

    At ``flips_at`` every even call binds a Demand Prophet proposal instead, so that state's
    replay never reproduces its first consult. No protocol, agent handler or twin runs.
    """

    name = "consensus"
    levers = frozenset({"reorder"})

    def __init__(self, flips_at: float) -> None:
        self._flips_at = flips_at
        self._pipeline = InventorySentinelPipeline()
        self.calls = 0

    def consult(self, obs: Observation) -> ConsensusOutcome:
        self.calls += 1
        request = observation_to_decision_request(obs)
        state = forecast_from_request(decision_context({PROPOSAL_ENVELOPE_KEY: request}))
        skus = list(request["sku_ids"])
        actions = self._pipeline.decide(skus, "STORE_TEST", demand_forecast=state)
        dumped = [action.model_dump(mode="json") for action in actions]
        sentinel: dict[str, Any] = {"actions": dumped}
        prophet: dict[str, Any] = {"forecast": "constructed"}
        flipped = obs.sim_time == self._flips_at and self.calls % 2 == 0
        decision = ConsensusDecision(
            tier=DecisionTier.TIER_2,
            proposals=[
                _proposal(AgentName.INVENTORY_SENTINEL, sentinel, 0.9),
                _proposal(AgentName.DEMAND_PROPHET, prophet, 0.95 if flipped else 0.5),
            ],
            selected_action=prophet if flipped else sentinel,
            pareto_weights={},
            confidence=0.9,
            audit_trace=["constructed"],
            execution_confirmations=["acknowledged"],
        )
        return ConsensusOutcome(
            request=request,
            decision=decision,
            translated=consensus_decision_to_policy_action(decision, obs),
            dispatch=DispatchClassification(bucket="dispatched", reason="constructed"),
        )

    def decide(self, obs: Observation) -> PolicyAction:
        """What the consult applies, so the double is the DecisionPolicy the factory returns."""
        return self.consult(obs).action


def _state(sim_time: float, stock: int) -> Observation:
    """A state carrying all three inputs, its two SKUs at ``stock`` on hand or one over."""
    return Observation(
        inventory={"sku_0": stock + 1, "sku_1": stock},
        sim_time=sim_time,
        delivery_count=4,
        spoilage_count=0,
        stockout_count=1,
        unit_costs={"sku_0": 1.0, "sku_1": 1.5},
        on_order={"sku_0": 5.0},
        supplier_lead_time_history={"sup_a": (240.0,), "sup_b": (360.0,)},
        demand_to_date={"sku_0": 30, "sku_1": 12},
        sku_supplier={"sku_0": "sup_a", "sku_1": "sup_b"},
        start_weekday=2,
    )


def test_a_stand_in_arm_is_never_traced_and_the_refusal_names_its_reason() -> None:
    sampled: list[int] = []

    def sampler() -> list[Observation]:
        sampled.append(1)
        return [_state(600.0, 1)]

    document = run_trace(
        arm_factory=lambda: UnavailableConsensusArm("no agent network in this environment"),
        sampler=sampler,
        params=NewsvendorParams(),
    )

    assert [refusal.check for refusal in document.refusals] == ["arm_not_consultable"]
    assert "its reason: no agent network in this environment" in document.refusals[0].detail
    assert (document.observations, document.production, sampled) == ((), None, [])
    assert {reading.reading for reading in document.predictions} == {"unread"}
    assert exit_code(document) == EXIT_UNTRACEABLE


def test_a_sampler_that_returns_no_state_is_refused_before_any_consult() -> None:
    arms: list[_SentinelPathway] = []

    def factory() -> _SentinelPathway:
        arms.append(_SentinelPathway(flips_at=-1.0))
        return arms[-1]

    document = run_trace(arm_factory=factory, sampler=lambda: [], params=NewsvendorParams())

    assert [refusal.check for refusal in document.refusals] == ["no_observation"]
    assert [arm.calls for arm in arms] == [0]
    assert exit_code(document) == EXIT_UNTRACEABLE


def test_the_trace_consults_in_the_probes_order_so_a_fresh_probe_reproduces_its_counts() -> None:
    # State 0 orders under every variant, with each input moving the order; state 1 flips its
    # binding agent on every other call; state 2 holds far more stock than any q* reaches.
    states = [_state(600.0, 1), _state(720.0, 1), _state(840.0, 1000)]

    document = run_trace(
        arm_factory=lambda: _SentinelPathway(flips_at=720.0),
        sampler=lambda: states,
        params=NewsvendorParams(),
    )

    assert document.production is not None
    report = document.production.report
    assert report is not None
    traced = [(c.input_name, c.carried, c.pairs, c.changed) for c in document.input_counts]
    probed = [(r.input_name, r.carried, r.pairs, r.changed) for r in report.inputs]
    assert traced == probed
    assert traced == [
        ("on_order", 3, 2, 1),
        ("supplier_lead_time_history", 3, 2, 1),
        ("demand_to_date", 3, 2, 1),
    ]
    # The flipping state is recorded, makes no pair, and is the only refusal.
    assert [(r.check, r.detail.split(" ")[1]) for r in document.refusals] == [
        ("replay_unstable", "1")
    ]
    assert exit_code(document) == EXIT_REFUSED
    # The restated q* reproduces the real Sentinel at every SKU of every recorded consult.
    for trace in document.observations:
        for record in trace.variants:
            assert record.request_rebuilt
            assert record.sentinel_problems == ()
            for sku in record.skus:
                assert sku.sentinel_action is not None
                assert sku.sentinel_action.quantity == sku.predicted_quantity
    assert _readings(document.observations)["P1"] == "missed"
