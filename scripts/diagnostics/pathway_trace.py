"""Which agent bound each decision R7.21's pathway probe compares, and why each pair moved or not.

ADR-058 (``docs/adr/ADR-058-inventory-sentinel-reads-the-request.md``), Falsification item 1: an
input that stays unresponsive while the Inventory Sentinel binds falsifies the Sentinel's wiring.
E5 run 41352100304, at 4b659e6, recorded the probe's counts: withholding
``supplier_lead_time_history`` changed the binding decision in 3 of 3 pairs, and withholding
``on_order`` or ``demand_to_date`` changed it in 0 of 3. A count names no agent and no
order-up-to level, so it cannot tell a wiring defect from probe states at which every SKU's stock
already exceeds the level the Sentinel orders up to. This module records both, through the code
the probe runs, and judges nothing.

**Called, never re-implemented.** The states are :func:`uplift.e5_suite.e5_probe_observations`
and the arm is :func:`uplift.e5_suite.e5_consensus_policy`. Each decision is the arm's
``consult``, compared by :func:`uplift.dispatch.binding_fingerprint` with inputs withheld by
:func:`uplift.dispatch.withhold_input`, in the order :func:`uplift.dispatch.run_pathway_probe`
consults: per observation the full request, its replay, then each input
:func:`uplift.dispatch.carries_input` names. The Sentinel's reading of a request is
:func:`agents.inventory_sentinel.inference.request_state.forecast_from_request` over
:func:`synapse_common.a2a_envelope.decision_context` of the envelope the protocol sends, and q* is
:func:`agents.inventory_sentinel.models.newsvendor.newsvendor_quantity` at the pipeline's own
:class:`~agents.inventory_sentinel.models.newsvendor.NewsvendorParams`.

**Restated, and checked.** ``InventorySentinelPipeline.decide`` returns a quantity, not q*, so
its reading of a forecast entry and its order ``round(max(0, q* - on_hand), 2)`` are restated in
:func:`sentinel_q_star` and :func:`ordered_quantity`. Every restated quantity is compared with the
quantity the Sentinel proposed in the same consult, and a difference is refused.

**Each self-check is a named refusal** (:data:`RefusalCheck`), never a guess: an arm with no
pathway (the ``UnavailableConsensusArm`` stand-in is never traced, and its reason is named); no
observation; a replay whose ``binding_fingerprint`` differs from the first consult's (the
observation is kept and contributes no pair, as in the probe); a pair whose fingerprint verdict
disagrees with its agent, bucket, price, routing, disruption actions and per-SKU quantities; a
request other than ``observation_to_decision_request`` builds; a Sentinel proposal that is not
one action per stocked SKU; a restated quantity the Sentinel did not propose; and per-input
counts that a fresh ``run_pathway_probe`` over the same states, on a fresh arm in the same
process after the trace, does not reproduce or cannot state.

**Output.** One canonical-JSON :class:`TraceDocument` at the required ``--output`` path, which
must not exist. A refused trace is written too, with every record taken and each refusal named.
Exit 0 traced; 2 nothing traced (no pathway, no state, or the output exists); 3 traced and
refused. An uncaught exception exits 1 with its traceback.

CI only (``.github/workflows/uplift-cost-probe.yml``): the arm stands up the eight agents and the
twin's A2A handler, and the states take 15 simulated hours of the twin (I-0).
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import logging
import math
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import TYPE_CHECKING, Final, Literal, TypeAlias

import structlog
from pydantic import BaseModel, ConfigDict, Field, StrictBool, ValidationError, model_validator
from synapse_common.a2a_envelope import PROPOSAL_ENVELOPE_KEY, decision_context
from synapse_common.models import AgentName, AgentProposal, InventoryAction

from agents.inventory_sentinel.inference.request_state import forecast_from_request
from agents.inventory_sentinel.models.newsvendor import NewsvendorParams, newsvendor_quantity
from uplift.consensus_arm import ConsensusOutcome, DispatchBucket, observation_to_decision_request
from uplift.dispatch import (
    PROBE_INPUTS,
    PathwayConsultant,
    PathwayProbeError,
    PathwayProbeReport,
    ProbeInput,
    binding_fingerprint,
    carries_input,
    run_pathway_probe,
    withhold_input,
)
from uplift.policies import UnavailableConsensusArm

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from uplift.interfaces import DecisionPolicy, Observation

__all__ = [
    "EXIT_REFUSED",
    "EXIT_TRACED",
    "EXIT_UNTRACEABLE",
    "FULL_REQUEST",
    "PREDICTIONS",
    "SENTINEL",
    "TRACE_KIND",
    "TRACE_SCHEMA_VERSION",
    "DecisionRecord",
    "InputCount",
    "ObservationTrace",
    "PairRecord",
    "PredictionReading",
    "ProductionComparison",
    "ProposalRecord",
    "QStarBasis",
    "Refusal",
    "RefusalCheck",
    "SentinelAction",
    "SkuRecord",
    "TraceDocument",
    "Variant",
    "build_document",
    "decision_record",
    "evaluate_predictions",
    "exit_code",
    "input_counts",
    "main",
    "ordered_quantity",
    "pair_record",
    "production_refusals",
    "q_star_basis",
    "refused_document",
    "run_trace",
    "sentinel_q_star",
    "summary_lines",
    "trace_probe",
    "trace_refusals",
    "write_trace",
]

logger = structlog.get_logger(__name__)

#: This record's declared kind and schema version.
TRACE_KIND: Final[Literal["consensus-pathway-trace"]] = "consensus-pathway-trace"
TRACE_SCHEMA_VERSION: Final[Literal[1]] = 1

#: Traced, and every self-check held.
EXIT_TRACED: Final[int] = 0
#: Nothing traced: the arm has no pathway, the sampler gave no state, or the output exists.
EXIT_UNTRACEABLE: Final[int] = 2
#: Traced, and at least one self-check refused; the file names each refusal. Exit 1 is left to
#: the interpreter: an uncaught exception, with its traceback.
EXIT_REFUSED: Final[int] = 3

#: The variant a consult decided: the full request, or the request with one probe input withheld.
FULL_REQUEST: Final[Literal["full"]] = "full"
Variant: TypeAlias = Literal["full"] | ProbeInput

#: The agent whose order-up-to arithmetic this trace restates (ADR-058).
SENTINEL: Final[str] = AgentName.INVENTORY_SENTINEL.value

#: ``InventorySentinelPipeline.decide`` (``agents/inventory_sentinel/inference/pipeline.py``),
#: restated because it returns the quantity and not q*: ``mean = float(f.get("mean", 10.0))``,
#: ``std = max(1e-3, float(f.get("std", 3.0)))``, ``on_hand = float(f.get("on_hand", 0.0))``
#: and, for a SKU the request never marks essential, ``round(max(0.0, q* - on_hand), 2)``. Every
#: quantity restated from these is compared with the quantity the Sentinel proposed.
DECIDE_MISSING_MEAN: Final[float] = 10.0
DECIDE_MISSING_STD: Final[float] = 3.0
DECIDE_MISSING_ON_HAND: Final[float] = 0.0
DECIDE_STD_FLOOR: Final[float] = 1e-3
DECIDE_QUANTITY_DECIMALS: Final[int] = 2

#: Where the q* parameters come from, recorded beside them in every trace.
_PARAMS_SOURCE: Final[str] = (
    "NewsvendorParams(), as InventorySentinelPipeline.__init__ holds it when none is injected "
    "('newsvendor_params or NewsvendorParams()'). build_agent_handlers gives the Sentinel's "
    "handler no pipeline, and the handler builds InventorySentinelPipeline() with no params"
)

#: Every named refusal. The first two leave nothing traced (:data:`EXIT_UNTRACEABLE`).
RefusalCheck: TypeAlias = Literal[
    "arm_not_consultable",
    "no_observation",
    "replay_unstable",
    "pair_verdict_unexplained",
    "request_not_rebuilt",
    "sentinel_proposal_ambiguous",
    "q_star_does_not_reproduce_the_sentinel",
    "production_disagrees",
    "production_not_compared",
]
UNTRACEABLE_CHECKS: Final[frozenset[RefusalCheck]] = frozenset(
    {"arm_not_consultable", "no_observation"}
)

PredictionId: TypeAlias = Literal["P1", "P2", "P3", "P4"]
Reading: TypeAlias = Literal["held", "missed", "unread"]

#: The four predictions, each beside what would make it wrong, written before the run. P1 is read
#: over every recorded decision; P2-P4 per traced observation, ``unread`` where the pair was not
#: traced (the input not carried, or the replay unstable) or a SKU has no Sentinel action. One
#: ``missed`` misses the prediction; otherwise one ``unread`` leaves it unread (I-7).
PREDICTIONS: Final[tuple[tuple[PredictionId, str, str], ...]] = (
    (
        "P1",
        "The Inventory Sentinel binds every traced decision: each full request, its replay and "
        "each input withheld.",
        "A recorded decision bound by another agent, or by none.",
    ),
    (
        "P2",
        "With demand_to_date withheld, every SKU's Sentinel quantity is 0 in both the full and "
        "the withheld variant.",
        "A SKU whose Sentinel quantity is above 0 in either variant, at any observation.",
    ),
    (
        "P3",
        "With on_order withheld, every SKU's Sentinel quantity is 0 in both variants, because "
        "on-hand exceeds q*.",
        "A SKU whose Sentinel quantity is above 0 in either variant, or whose on-hand (the stock "
        "the Sentinel reads with on_order withheld) does not exceed its q*. A translated quantity "
        "that differs while the fingerprint does not is refused as pair_verdict_unexplained.",
    ),
    (
        "P4",
        "With supplier_lead_time_history withheld, at least one SKU's Sentinel quantity is above "
        "0 at each observation.",
        "An observation at which every SKU's Sentinel quantity is 0 with the history withheld.",
    ),
)


# ---------------------------------------------------------------------------
# The records
# ---------------------------------------------------------------------------
class QStarBasis(BaseModel):
    """What every q* in a trace was computed with: the pipeline's costs and decide's defaults."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    cost_under: float
    cost_over: float
    critical_fractile: float
    missing_mean: float
    missing_std: float
    std_floor: float
    source: str


class SentinelAction(BaseModel):
    """One ``InventoryAction`` of the Sentinel's proposal, as the consult returned it."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    action_type: str
    quantity: float
    reorder_point: float
    confidence: float
    safety_stock_multiplier: float

    @classmethod
    def of(cls, action: InventoryAction) -> SentinelAction:
        """``action``'s decision fields, field for field."""
        return cls(
            action_type=action.action_type,
            quantity=action.quantity,
            reorder_point=action.reorder_point,
            confidence=action.confidence,
            safety_stock_multiplier=action.safety_stock_multiplier,
        )


class SkuRecord(BaseModel):
    """One stocked SKU in one consult: what the request carried, what the Sentinel read, and q*.

    ``inventory`` (on hand), ``on_order``, ``inventory_position``, ``demand_to_date``,
    ``supplier`` and the landed lead times are read from the request the arm sent; ``None`` is a
    key the request did not carry for this SKU. ``forecast`` is ``forecast_from_request``'s entry.
    ``sentinel_stock`` is the stock ``decide`` subtracts from ``q_star``, ``predicted_quantity``
    what it then orders, and ``sentinel_action`` what the Sentinel proposed, or ``None``.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    sku: str
    inventory: int | None
    on_order: float | None
    inventory_position: float | None
    demand_to_date: int | None
    supplier: str | None
    landed_lead_times: int = Field(strict=True, ge=0)
    mean_landed_lead_time_min: float | None
    forecast: dict[str, float] | None
    q_star: float
    sentinel_stock: float
    predicted_quantity: float
    sentinel_action: SentinelAction | None

    @model_validator(mode="after")
    def _derived_fields_are_re_derived(self) -> SkuRecord:
        expected = ordered_quantity(self.q_star, self.sentinel_stock)
        if self.predicted_quantity != expected:
            raise ValueError(
                f"{self.sku}: predicted_quantity={self.predicted_quantity!r} is not "
                f"round(max(0, q* - stock), 2) = {expected!r}"
            )
        if (self.landed_lead_times == 0) != (self.mean_landed_lead_time_min is None):
            raise ValueError(f"{self.sku}: a mean landed lead time exists exactly when one landed")
        return self


class ProposalRecord(BaseModel):
    """One agent's proposal in a decision: who proposed, at what utility and confidence."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    agent: str
    utility_score: float
    confidence: float


class DecisionRecord(BaseModel):
    """One consult: what bound, how it translated, its fingerprint, and the Sentinel's view.

    ``binding_agent``, ``bucket`` and ``fingerprint`` are ``ConsensusOutcome.binding_agent``, its
    dispatch bucket and ``binding_fingerprint``; the ``translated_*`` fields are the four
    components that fingerprint serialises beside them. ``request_rebuilt`` is whether the request
    the arm sent equals what ``observation_to_decision_request`` builds from the observation.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    variant: Variant
    tier: str
    binding_agent: str | None
    bucket: DispatchBucket
    fingerprint: str
    translated_reorder_quantities: dict[str, float]
    translated_price: float | None
    translated_routing: str | None
    translated_disruption_actions: tuple[str, ...]
    proposals: tuple[ProposalRecord, ...]
    sentinel_proposals: int = Field(strict=True, ge=0)
    sentinel_problems: tuple[str, ...]
    request_rebuilt: StrictBool
    skus: tuple[SkuRecord, ...]

    @model_validator(mode="after")
    def _one_record_per_sku_in_order(self) -> DecisionRecord:
        names = [sku.sku for sku in self.skus]
        if names != sorted(set(names)):
            raise ValueError(f"{self.variant}: the SKU records are not one per SKU, sorted")
        actions = list(self.translated_disruption_actions)
        if actions != sorted(set(actions)):
            raise ValueError(f"{self.variant}: the disruption actions are not a sorted set")
        recorded = any(sku.sentinel_action is not None for sku in self.skus)
        if recorded and self.sentinel_proposals != 1:
            raise ValueError(
                f"{self.variant}: a Sentinel action is recorded without exactly one Sentinel "
                "proposal to read it from"
            )
        return self


class PairRecord(BaseModel):
    """One (observation, input) pair: the probe's verdict, and the components that explain it.

    ``fingerprint_changed`` is the probe's own verdict, ``binding_fingerprint`` compared. Every
    other flag compares one component that fingerprint serialises, and ``quantity_changed_skus``
    names each SKU whose translated reorder differs, a SKU absent on one side included. The pair
    is explained when the verdict says changed exactly when some component did.

    Two lists the fingerprint does not compare say how far the input reached:
    ``forecast_changed_skus`` names the SKUs whose Sentinel forecast entry differs (the input
    reached its reading), and ``sentinel_quantity_changed_skus`` those whose proposed quantity
    differs (the input moved its order).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    input_name: ProbeInput
    fingerprint_changed: StrictBool
    binding_agent_changed: StrictBool
    bucket_changed: StrictBool
    price_changed: StrictBool
    routing_changed: StrictBool
    disruption_changed: StrictBool
    quantity_changed_skus: tuple[str, ...]
    verdict_explained: StrictBool
    forecast_changed_skus: tuple[str, ...]
    sentinel_quantity_changed_skus: tuple[str, ...]

    @property
    def moved(self) -> bool:
        """Whether any component ``binding_fingerprint`` serialises differs across the pair."""
        return (
            self.binding_agent_changed
            or self.bucket_changed
            or self.price_changed
            or self.routing_changed
            or self.disruption_changed
            or bool(self.quantity_changed_skus)
        )

    @model_validator(mode="after")
    def _explained_exactly_when_verdict_and_components_agree(self) -> PairRecord:
        if self.verdict_explained != (self.fingerprint_changed == self.moved):
            raise ValueError(
                f"{self.input_name}: verdict_explained={self.verdict_explained} contradicts "
                f"fingerprint_changed={self.fingerprint_changed} beside moved={self.moved}"
            )
        for skus in (
            self.quantity_changed_skus,
            self.forecast_changed_skus,
            self.sentinel_quantity_changed_skus,
        ):
            if list(skus) != sorted(set(skus)):
                raise ValueError(f"{self.input_name}: a list of changed SKUs is not a sorted set")
        return self


class ObservationTrace(BaseModel):
    """One probed state: its consults in the probe's order, and the pairs they make.

    ``variants`` is the full request first, then, only when the replay reproduced the full
    request's fingerprint, one record per carried input withheld, in :data:`PROBE_INPUTS` order.
    ``pairs`` is re-derived from them on construction. A replay-unstable state keeps its full
    request and its replay's fingerprint and binding agent, and makes no pair.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    index: int = Field(strict=True, ge=0)
    sim_time: float
    carried_inputs: tuple[ProbeInput, ...]
    replay_fingerprint: str
    replay_binding_agent: str | None
    replay_stable: StrictBool
    variants: tuple[DecisionRecord, ...]
    pairs: tuple[PairRecord, ...]

    @model_validator(mode="after")
    def _the_records_are_the_probes_consults(self) -> ObservationTrace:
        where = f"observation {self.index}"
        names = tuple(record.variant for record in self.variants)
        if not names or names[0] != FULL_REQUEST:
            raise ValueError(f"{where}: the first recorded consult is not the full request")
        if self.replay_stable != (self.replay_fingerprint == self.variants[0].fingerprint):
            raise ValueError(
                f"{where}: replay_stable is not whether the replay reproduced the fingerprint"
            )
        in_order = tuple(name for name in PROBE_INPUTS if name in self.carried_inputs)
        if self.carried_inputs != in_order:
            raise ValueError(f"{where}: carried_inputs are not distinct and in PROBE_INPUTS order")
        consulted: tuple[ProbeInput, ...] = self.carried_inputs if self.replay_stable else ()
        if names[1:] != consulted:
            raise ValueError(
                f"{where}: withheld consults {list(names[1:])} are not the {list(consulted)} the "
                "probe consults after a stable replay"
            )
        derived = tuple(
            pair_record(name, self.variants[0], record)
            for name, record in zip(consulted, self.variants[1:], strict=True)
        )
        if self.pairs != derived:
            raise ValueError(f"{where}: the pairs are not the pairs its consults make")
        return self


class InputCount(BaseModel):
    """One input's counts over a trace, in the probe's own terms (R7.21)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    input_name: ProbeInput
    carried: int = Field(strict=True, ge=0)
    pairs: int = Field(strict=True, ge=0)
    changed: int = Field(strict=True, ge=0)

    @model_validator(mode="after")
    def _changed_within_pairs_within_carried(self) -> InputCount:
        if not self.changed <= self.pairs <= self.carried:
            raise ValueError(
                f"{self.input_name}: changed={self.changed}, pairs={self.pairs} and "
                f"carried={self.carried} are not ordered changed <= pairs <= carried"
            )
        return self


class Refusal(BaseModel):
    """One self-check that failed, by name, with what it found."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    check: RefusalCheck
    detail: str

    @model_validator(mode="after")
    def _states_what_it_found(self) -> Refusal:
        if not self.detail.strip():
            raise ValueError(f"refusal {self.check} states nothing, and so explains nothing")
        return self


class ProductionComparison(BaseModel):
    """A fresh ``run_pathway_probe`` over the same states and a fresh arm, or why there is none."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    report: PathwayProbeReport | None
    unavailable_reason: str | None

    @model_validator(mode="after")
    def _a_report_or_a_reason(self) -> ProductionComparison:
        reason = self.unavailable_reason
        if (self.report is None) == (reason is None) or (reason is not None and not reason.strip()):
            raise ValueError("a production comparison holds a report or a stated reason, not both")
        return self


class PredictionReading(BaseModel):
    """One prediction of :data:`PREDICTIONS`, read off the records by its stated rule."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    prediction: PredictionId
    statement: str
    falsifier: str
    reading: Reading
    basis: str


class TraceDocument(BaseModel):
    """The trace: every consult's record, the pair verdicts, the comparison and the refusals.

    ``verdict`` is ``refused`` exactly when ``refusals`` is non-empty, and a document with no
    observation names why. ``input_counts`` and ``predictions`` are re-derived from
    ``observations`` on construction and refused if they disagree, so neither can be edited apart
    from the records it summarises.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    kind: Literal["consensus-pathway-trace"]
    schema_version: Literal[1]
    verdict: Literal["traced", "refused"]
    refusals: tuple[Refusal, ...]
    arm: str
    levers: tuple[str, ...]
    q_star_basis: QStarBasis | None
    observations: tuple[ObservationTrace, ...]
    input_counts: tuple[InputCount, ...]
    production: ProductionComparison | None
    predictions: tuple[PredictionReading, ...]

    @model_validator(mode="after")
    def _derived_fields_are_what_the_records_say(self) -> TraceDocument:
        problems: list[str] = []
        if not self.arm.strip() or self.arm != self.arm.strip():
            problems.append(f"arm {self.arm!r} does not name an arm")
        if list(self.levers) != sorted(set(self.levers)):
            problems.append(f"levers {list(self.levers)} are not a sorted set")
        if self.verdict != ("refused" if self.refusals else "traced"):
            problems.append(f"verdict {self.verdict!r} contradicts {len(self.refusals)} refusal(s)")
        if not self.observations and not any(
            refusal.check in UNTRACEABLE_CHECKS for refusal in self.refusals
        ):
            problems.append("no observation was traced, and no refusal says why")
        if [trace.index for trace in self.observations] != list(range(len(self.observations))):
            problems.append("observations are not indexed 0..n-1 in the order they were sampled")
        if self.input_counts != input_counts(self.observations):
            problems.append("input_counts are not the counts of the recorded pairs")
        if self.predictions != evaluate_predictions(self.observations):
            problems.append("predictions are not the readings of the recorded consults")
        if problems:
            raise ValueError(
                "the pathway trace is refused rather than recorded: " + "; ".join(problems)
            )
        return self

    def to_canonical_json(self) -> str:
        """The trace in the repository's one canonical JSON form."""
        return _canonical(self.model_dump(mode="json"))


# ---------------------------------------------------------------------------
# Pure helpers: q*, the pair verdict, the counts, the refusals and the readings
# ---------------------------------------------------------------------------
def _canonical(payload: object) -> str:
    """``json.dumps(..., sort_keys=True, separators=(',', ':'))``: the repository's one form."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def ordered_quantity(q_star: float, stock: float) -> float:
    """What ``decide`` orders for a SKU the request never marks essential, given q* and stock."""
    return round(max(0.0, q_star - stock), DECIDE_QUANTITY_DECIMALS)


def sentinel_q_star(
    entry: Mapping[str, float] | None, params: NewsvendorParams
) -> tuple[float, float]:
    """``(q*, the stock decide subtracts)`` for one SKU's forecast entry, read as decide reads it.

    ``None`` is a SKU the forecast does not name, which ``decide`` plans on its defaults alone.
    """
    reading: Mapping[str, float] = {} if entry is None else entry
    mean = float(reading.get("mean", DECIDE_MISSING_MEAN))
    std = max(DECIDE_STD_FLOOR, float(reading.get("std", DECIDE_MISSING_STD)))
    stock = float(reading.get("on_hand", DECIDE_MISSING_ON_HAND))
    return newsvendor_quantity(mean, std, params), stock


def q_star_basis(params: NewsvendorParams) -> QStarBasis:
    """``params`` and ``decide``'s entry defaults, as every q* in a trace is computed."""
    return QStarBasis(
        cost_under=params.cost_under,
        cost_over=params.cost_over,
        critical_fractile=params.critical_fractile,
        missing_mean=DECIDE_MISSING_MEAN,
        missing_std=DECIDE_MISSING_STD,
        std_floor=DECIDE_STD_FLOOR,
        source=_PARAMS_SOURCE,
    )


def _differing(before: Mapping[str, object], after: Mapping[str, object]) -> tuple[str, ...]:
    """The keys, sorted, whose values differ across the two mappings; absent on one side counts."""
    return tuple(
        key for key in sorted(set(before) | set(after)) if before.get(key) != after.get(key)
    )


def _proposed(record: DecisionRecord) -> dict[str, float | None]:
    """Each SKU's Sentinel quantity in ``record``, ``None`` where the Sentinel proposed none."""
    return {
        sku.sku: None if sku.sentinel_action is None else sku.sentinel_action.quantity
        for sku in record.skus
    }


def pair_record(
    input_name: ProbeInput, full: DecisionRecord, withheld: DecisionRecord
) -> PairRecord:
    """The probe's verdict on one pair, beside each component ``binding_fingerprint`` compares.

    Raises:
        ValueError: ``full`` is not the full request or ``withheld`` is not ``input_name``
            withheld, so the two records are not a pair.
    """
    if full.variant != FULL_REQUEST or withheld.variant != input_name:
        raise ValueError(
            f"a pair compares the full request with {input_name!r} withheld, not "
            f"{full.variant!r} with {withheld.variant!r}"
        )
    differing = _differing(
        full.translated_reorder_quantities, withheld.translated_reorder_quantities
    )
    agent = full.binding_agent != withheld.binding_agent
    bucket = full.bucket != withheld.bucket
    price = full.translated_price != withheld.translated_price
    routing = full.translated_routing != withheld.translated_routing
    disruption = full.translated_disruption_actions != withheld.translated_disruption_actions
    changed = full.fingerprint != withheld.fingerprint
    moved = agent or bucket or price or routing or disruption or bool(differing)
    return PairRecord(
        input_name=input_name,
        fingerprint_changed=changed,
        binding_agent_changed=agent,
        bucket_changed=bucket,
        price_changed=price,
        routing_changed=routing,
        disruption_changed=disruption,
        quantity_changed_skus=differing,
        verdict_explained=changed == moved,
        forecast_changed_skus=_differing(
            {sku.sku: sku.forecast for sku in full.skus},
            {sku.sku: sku.forecast for sku in withheld.skus},
        ),
        sentinel_quantity_changed_skus=_differing(_proposed(full), _proposed(withheld)),
    )


def input_counts(observations: Sequence[ObservationTrace]) -> tuple[InputCount, ...]:
    """Per input, in :data:`PROBE_INPUTS` order: states carrying it, its pairs, pairs changed."""
    counts: list[InputCount] = []
    for name in PROBE_INPUTS:
        pairs = [pair for trace in observations for pair in trace.pairs if pair.input_name == name]
        counts.append(
            InputCount(
                input_name=name,
                carried=sum(1 for trace in observations if name in trace.carried_inputs),
                pairs=len(pairs),
                changed=sum(1 for pair in pairs if pair.fingerprint_changed),
            )
        )
    return tuple(counts)


def _record_refusals(at: str, record: DecisionRecord) -> list[Refusal]:
    """The refusals one consult's record raises on its own, each naming where it was taken."""
    refusals: list[Refusal] = []
    if not record.request_rebuilt:
        refusals.append(
            Refusal(
                check="request_not_rebuilt",
                detail=(
                    f"{at}: the arm sent a request other than observation_to_decision_request "
                    "builds from the observation, so the records do not describe what was sent"
                ),
            )
        )
    if record.sentinel_problems:
        refusals.append(
            Refusal(
                check="sentinel_proposal_ambiguous",
                detail=f"{at}: " + "; ".join(record.sentinel_problems),
            )
        )
    mismatched: list[tuple[str, float, float]] = []
    for sku in record.skus:
        action = sku.sentinel_action
        if action is not None and action.quantity != sku.predicted_quantity:
            mismatched.append((sku.sku, sku.predicted_quantity, action.quantity))
    if mismatched:
        name, restated, proposed = mismatched[0]
        refusals.append(
            Refusal(
                check="q_star_does_not_reproduce_the_sentinel",
                detail=(
                    f"{at}: the restated order differs from the Sentinel's at {len(mismatched)} "
                    f"SKU(s); first {name}: restated {restated!r}, proposed {proposed!r}, so the "
                    "recorded q* is not the Sentinel's"
                ),
            )
        )
    return refusals


def trace_refusals(observations: Sequence[ObservationTrace]) -> tuple[Refusal, ...]:
    """Every refusal the records themselves raise, in observation and consult order."""
    refusals: list[Refusal] = []
    for trace in observations:
        where = f"observation {trace.index} (t={trace.sim_time:g} min)"
        if not trace.replay_stable:
            refusals.append(
                Refusal(
                    check="replay_unstable",
                    detail=(
                        f"{where}: the replayed full request bound {trace.replay_binding_agent} "
                        "under a fingerprint other than the first consult's (bound by "
                        f"{trace.variants[0].binding_agent}); like run_pathway_probe, the trace "
                        "makes no pair there and attributes nothing to any input"
                    ),
                )
            )
        for record in trace.variants:
            refusals.extend(_record_refusals(f"{where}, {record.variant}", record))
        for pair in trace.pairs:
            if pair.verdict_explained:
                continue
            said = "changed" if pair.fingerprint_changed else "unchanged"
            read = "unchanged" if pair.fingerprint_changed else "changed"
            refusals.append(
                Refusal(
                    check="pair_verdict_unexplained",
                    detail=(
                        f"{where}, {pair.input_name} withheld: binding_fingerprint reads {said}, "
                        "but the binding agent, bucket, price, routing, disruption actions and "
                        f"per-SKU translated quantities read {read}"
                    ),
                )
            )
    return tuple(refusals)


def production_refusals(
    observations: Sequence[ObservationTrace], report: PathwayProbeReport
) -> tuple[Refusal, ...]:
    """A refusal when a fresh ``run_pathway_probe``'s report and the trace disagree, else none.

    Compared: the observation count, the replay-unstable count, the full requests' four dispatch
    buckets, and every input's carried, pairs and changed counts.
    """
    mismatches: list[str] = []
    unstable = sum(1 for trace in observations if not trace.replay_stable)
    if report.observations != len(observations):
        mismatches.append(f"observations {len(observations)} vs {report.observations}")
    if report.replay_unstable != unstable:
        mismatches.append(f"replay-unstable {unstable} vs {report.replay_unstable}")
    tally = report.full_request_buckets
    probed_buckets = {
        "dispatched": tally.dispatched,
        "withheld_for_confidence": tally.withheld_for_confidence,
        "guardrail_blocked": tally.guardrail_blocked,
        "untranslatable": tally.untranslatable,
    }
    traced_buckets = {
        bucket: sum(1 for trace in observations if trace.variants[0].bucket == bucket)
        for bucket in probed_buckets
    }
    if traced_buckets != probed_buckets:
        mismatches.append(f"full-request buckets {traced_buckets} vs {probed_buckets}")
    probed = {result.input_name: result for result in report.inputs}
    for count in input_counts(observations):
        result = probed.get(count.input_name)
        if result is None:
            mismatches.append(f"{count.input_name}: absent from the production report")
            continue
        traced = (count.carried, count.pairs, count.changed)
        reported = (result.carried, result.pairs, result.changed)
        if traced != reported:
            mismatches.append(f"{count.input_name} carried/pairs/changed {traced} vs {reported}")
    if not mismatches:
        return ()
    return (
        Refusal(
            check="production_disagrees",
            detail=(
                "a fresh run_pathway_probe over the same states and a fresh arm does not "
                "reproduce the trace (trace vs production): " + "; ".join(mismatches)
            ),
        ),
    )


def _aggregate(readings: Sequence[Reading]) -> Reading:
    """``missed`` if any unit missed; else ``unread`` if none or any was unread; else ``held``."""
    if "missed" in readings:
        return "missed"
    if not readings or "unread" in readings:
        return "unread"
    return "held"


def _withheld_variant(trace: ObservationTrace, name: ProbeInput) -> DecisionRecord | None:
    """The consult of ``trace`` with ``name`` withheld, when the probe made it."""
    return next((record for record in trace.variants[1:] if record.variant == name), None)


def _sentinel_quantities(record: DecisionRecord) -> list[float] | None:
    """Every stocked SKU's Sentinel quantity in ``record``, or ``None`` when one has none."""
    quantities: list[float] = []
    for sku in record.skus:
        if sku.sentinel_action is None:
            return None
        quantities.append(sku.sentinel_action.quantity)
    return quantities or None


def _p1(observations: Sequence[ObservationTrace]) -> tuple[Reading, str]:
    """P1 over every recorded decision: each full request, its replay and each input withheld."""
    decisions: list[tuple[int, str, str | None]] = [
        (trace.index, record.variant, record.binding_agent)
        for trace in observations
        for record in trace.variants
    ]
    decisions.extend((trace.index, "replay", trace.replay_binding_agent) for trace in observations)
    if not decisions:
        return "unread", "no decision was traced"
    others = [decision for decision in decisions if decision[2] != SENTINEL]
    if others:
        index, variant, agent = others[0]
        return "missed", (
            f"{len(others)} of {len(decisions)} recorded decisions were bound by another agent "
            f"or by none; the first is observation {index}, {variant}: {agent}"
        )
    return "held", f"all {len(decisions)} recorded decisions were bound by {SENTINEL}"


def _ordered_nothing(trace: ObservationTrace, name: ProbeInput, *, on_hand_rule: bool) -> Reading:
    """P2 and P3 at one state: no Sentinel order either way, and for P3 on-hand above q*."""
    withheld = _withheld_variant(trace, name)
    if withheld is None:
        return "unread"
    before = _sentinel_quantities(trace.variants[0])
    after = _sentinel_quantities(withheld)
    if before is None or after is None:
        return "unread"
    if any(quantity > 0.0 for quantity in (*before, *after)):
        return "missed"
    if on_hand_rule and any(sku.sentinel_stock <= sku.q_star for sku in withheld.skus):
        return "missed"
    return "held"


def _p2(trace: ObservationTrace) -> Reading:
    return _ordered_nothing(trace, "demand_to_date", on_hand_rule=False)


def _p3(trace: ObservationTrace) -> Reading:
    return _ordered_nothing(trace, "on_order", on_hand_rule=True)


def _p4(trace: ObservationTrace) -> Reading:
    """P4 at one state: some SKU's Sentinel quantity is above 0 with the history withheld."""
    withheld = _withheld_variant(trace, "supplier_lead_time_history")
    if withheld is None:
        return "unread"
    after = _sentinel_quantities(withheld)
    if after is None:
        return "unread"
    return "held" if any(quantity > 0.0 for quantity in after) else "missed"


def _per_observation(
    observations: Sequence[ObservationTrace], rule: Callable[[ObservationTrace], Reading]
) -> tuple[Reading, str]:
    """``rule`` at every traced state, aggregated, with each state's reading as the basis."""
    units = [(trace.index, rule(trace)) for trace in observations]
    basis = ", ".join(f"observation {index} {reading}" for index, reading in units)
    return _aggregate([reading for _, reading in units]), basis or "no observation was traced"


def evaluate_predictions(observations: Sequence[ObservationTrace]) -> tuple[PredictionReading, ...]:
    """Each of :data:`PREDICTIONS`, read off ``observations`` by its stated rule."""
    readings: dict[PredictionId, tuple[Reading, str]] = {
        "P1": _p1(observations),
        "P2": _per_observation(observations, _p2),
        "P3": _per_observation(observations, _p3),
        "P4": _per_observation(observations, _p4),
    }
    return tuple(
        PredictionReading(
            prediction=prediction,
            statement=statement,
            falsifier=falsifier,
            reading=readings[prediction][0],
            basis=readings[prediction][1],
        )
        for prediction, statement, falsifier in PREDICTIONS
    )


def build_document(
    *,
    arm: str,
    levers: tuple[str, ...],
    basis: QStarBasis,
    observations: tuple[ObservationTrace, ...],
    production: PathwayProbeReport | str,
) -> TraceDocument:
    """The traced document: the records, every self-check's refusals, and the readings.

    ``production`` is the fresh ``run_pathway_probe``'s report, or why there is none. A missing
    comparison is itself a refusal, because the trace's counts are then confirmed by nothing.
    """
    refusals = list(trace_refusals(observations))
    if not observations:
        refusals.insert(0, Refusal(check="no_observation", detail="no observation was traced"))
    if isinstance(production, str):
        comparison = ProductionComparison(report=None, unavailable_reason=production)
        refusals.append(Refusal(check="production_not_compared", detail=production))
    else:
        comparison = ProductionComparison(report=production, unavailable_reason=None)
        refusals.extend(production_refusals(observations, production))
    return TraceDocument(
        kind=TRACE_KIND,
        schema_version=TRACE_SCHEMA_VERSION,
        verdict="refused" if refusals else "traced",
        refusals=tuple(refusals),
        arm=arm,
        levers=levers,
        q_star_basis=basis,
        observations=observations,
        input_counts=input_counts(observations),
        production=comparison,
        predictions=evaluate_predictions(observations),
    )


def refused_document(
    *,
    arm: str,
    levers: tuple[str, ...],
    check: Literal["arm_not_consultable", "no_observation"],
    detail: str,
) -> TraceDocument:
    """The document for a run that traced nothing: one refusal, no record, every reading unread."""
    return TraceDocument(
        kind=TRACE_KIND,
        schema_version=TRACE_SCHEMA_VERSION,
        verdict="refused",
        refusals=(Refusal(check=check, detail=detail),),
        arm=arm,
        levers=levers,
        q_star_basis=None,
        observations=(),
        input_counts=input_counts(()),
        production=None,
        predictions=evaluate_predictions(()),
    )


def exit_code(document: TraceDocument) -> int:
    """:data:`EXIT_TRACED`, :data:`EXIT_UNTRACEABLE` with no record, or :data:`EXIT_REFUSED`."""
    if document.verdict == "traced":
        return EXIT_TRACED
    if not document.observations:
        return EXIT_UNTRACEABLE
    return EXIT_REFUSED


def write_trace(path: Path, document: TraceDocument) -> Path:
    """Write ``document``'s canonical JSON (no trailing newline) to a NEW file at ``path``.

    Opened with mode ``"x"``, so a file that already exists raises ``FileExistsError`` and is
    left as it was, even one created after the caller last looked.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as handle:
        handle.write(document.to_canonical_json())
    logger.info(
        "pathway_trace_written",
        path=str(path),
        verdict=document.verdict,
        refusals=[refusal.check for refusal in document.refusals],
    )
    return path


def _ascii(text: str) -> str:
    """``text`` with every non-ASCII character replaced by ``?``: the Windows console contract."""
    return text.encode("ascii", "replace").decode("ascii")


def _variant_line(record: DecisionRecord, pair: PairRecord | None) -> str:
    """One consult in a line: the pair's verdict, what bound, and the smallest stock - q*."""
    label = "full request" if record.variant == FULL_REQUEST else f"{record.variant} withheld"
    verdict = ""
    if pair is not None:
        moved = "CHANGED" if pair.fingerprint_changed else "unchanged"
        agent = ", binding agent differs" if pair.binding_agent_changed else ""
        verdict = (
            f" {moved} ({len(pair.quantity_changed_skus)} SKU quantities differ{agent}; the "
            f"Sentinel's forecast moved at {len(pair.forecast_changed_skus)} SKU(s) and its "
            f"order at {len(pair.sentinel_quantity_changed_skus)});"
        )
    utility = next(
        (p.utility_score for p in record.proposals if p.agent == record.binding_agent), None
    )
    bound = "" if utility is None else f" at utility {utility:.3f}"
    ordering = sum(1 for quantity in record.translated_reorder_quantities.values() if quantity > 0)
    margins = [sku.sentinel_stock - sku.q_star for sku in record.skus]
    margin = "n/a" if not margins else f"{min(margins):.4g}"
    return (
        f"  {label}:{verdict} bound by {record.binding_agent}{bound}, {record.bucket}, "
        f"{ordering} of {len(record.translated_reorder_quantities)} SKUs ordered, "
        f"min(stock - q*) {margin}"
    )


def summary_lines(document: TraceDocument, output: Path) -> list[str]:
    """A short ASCII account of ``document`` for the job log; the file is the record."""
    lines = [
        f"pathway_trace: verdict={document.verdict} arm={document.arm} "
        f"observations={len(document.observations)} output={output.as_posix()}"
    ]
    for trace in document.observations:
        replay = "stable" if trace.replay_stable else "UNSTABLE, no pair"
        lines.append(f"observation {trace.index} at t={trace.sim_time:g} min, replay {replay}")
        pairs: dict[str, PairRecord] = {pair.input_name: pair for pair in trace.pairs}
        lines.extend(_variant_line(record, pairs.get(record.variant)) for record in trace.variants)
    if document.observations:
        probed: dict[str, str] = {}
        if document.production is not None and document.production.report is not None:
            probed = {
                result.input_name: f"{result.changed}/{result.pairs}"
                for result in document.production.report.inputs
            }
        lines.extend(
            f"{count.input_name}: changed {count.changed}/{count.pairs} pairs "
            f"({count.carried} carried); fresh run_pathway_probe "
            f"{probed.get(count.input_name, 'not compared')}"
            for count in document.input_counts
        )
    lines.extend(
        f"{reading.prediction} {reading.reading}: {reading.basis}"
        for reading in document.predictions
    )
    lines.extend(f"REFUSED {refusal.check}: {refusal.detail}" for refusal in document.refusals)
    if not document.refusals:
        lines.append("refusals: none")
    return [_ascii(line) for line in lines]


# ---------------------------------------------------------------------------
# Reading one consult (CI: the arm is the real eight-agent pathway)
# ---------------------------------------------------------------------------
def _entry(request: Mapping[str, object], key: str, name: str) -> object:
    """``request[key][name]``, or ``None`` when the request carries no such mapping or entry."""
    mapping = request.get(key)
    if not isinstance(mapping, Mapping):
        return None
    value: object = mapping.get(name)
    return value


def _number(value: object) -> float | None:
    """``value`` as a float when it is a real number and not a bool, else ``None``."""
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return float(value)


def _count_at(request: Mapping[str, object], key: str, sku: str) -> int | None:
    value = _entry(request, key, sku)
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def _text_at(request: Mapping[str, object], key: str, sku: str) -> str | None:
    value = _entry(request, key, sku)
    return value if isinstance(value, str) else None


def _landed_lead_times(request: Mapping[str, object], supplier: str | None) -> tuple[float, ...]:
    """The landed lead times, in minutes, the request carries for ``supplier``."""
    if supplier is None:
        return ()
    times = _entry(request, "supplier_lead_time_history", supplier)
    if not isinstance(times, list | tuple):
        return ()
    landed = (_number(minutes) for minutes in times)
    return tuple(minutes for minutes in landed if minutes is not None)


def _sentinel_reading(
    proposals: Sequence[AgentProposal], stocked: frozenset[str]
) -> tuple[int, dict[str, InventoryAction], tuple[str, ...]]:
    """How many Sentinel proposals a decision holds, its actions by SKU, and what is unreadable.

    ``decide`` returns one ``InventoryAction`` per requested SKU, and the request names the
    stocked SKUs, so anything else is a problem the record names. No Sentinel proposal is not a
    problem: it is a fact the record keeps (``sentinel_proposals == 0``).
    """
    payloads = [p.payload for p in proposals if p.agent_name == AgentName.INVENTORY_SENTINEL]
    if not payloads:
        return 0, {}, ()
    if len(payloads) > 1:
        problem = f"{len(payloads)} Sentinel proposals in one decision; the protocol collects one"
        return len(payloads), {}, (problem,)
    entries = payloads[0].get("actions")
    if not isinstance(entries, list):
        return 1, {}, ("the Sentinel's payload carries no actions list",)
    actions: dict[str, InventoryAction] = {}
    problems: list[str] = []
    for entry in entries:
        try:
            action = InventoryAction.model_validate(entry)
        except ValidationError as exc:
            problems.append(f"an action is not an InventoryAction ({exc.error_count()} error(s))")
            continue
        if action.sku_id in actions:
            problems.append(f"{action.sku_id!r} has two actions, where decide returns one per SKU")
        elif action.sku_id not in stocked:
            problems.append(f"{action.sku_id!r} is not a SKU the request named")
        else:
            actions[action.sku_id] = action
    missing = sorted(stocked - set(actions))
    if missing:
        problems.append(f"no action for {len(missing)} stocked SKU(s), the first {missing[0]!r}")
    return 1, actions, tuple(problems)


def _sku_record(
    sku: str,
    sent: Mapping[str, object],
    forecast: Mapping[str, Mapping[str, float]] | None,
    action: InventoryAction | None,
    params: NewsvendorParams,
) -> SkuRecord:
    entry = None if forecast is None else forecast.get(sku)
    q_star, stock = sentinel_q_star(entry, params)
    supplier = _text_at(sent, "sku_supplier", sku)
    landed = _landed_lead_times(sent, supplier)
    return SkuRecord(
        sku=sku,
        inventory=_count_at(sent, "inventory", sku),
        on_order=_number(_entry(sent, "on_order", sku)),
        inventory_position=_number(_entry(sent, "inventory_position", sku)),
        demand_to_date=_count_at(sent, "demand_to_date", sku),
        supplier=supplier,
        landed_lead_times=len(landed),
        mean_landed_lead_time_min=math.fsum(landed) / len(landed) if landed else None,
        forecast=None if entry is None else dict(entry),
        q_star=q_star,
        sentinel_stock=stock,
        predicted_quantity=ordered_quantity(q_star, stock),
        sentinel_action=None if action is None else SentinelAction.of(action),
    )


def decision_record(
    variant: Variant, obs: Observation, outcome: ConsensusOutcome, params: NewsvendorParams
) -> DecisionRecord:
    """Record one consult of ``obs``, reading the outcome and re-deciding nothing.

    The Sentinel's forecast is ``forecast_from_request`` over ``decision_context`` of the
    envelope the protocol sends (``params={"decision_context": request}``), so it is the
    forecast the Sentinel's ``proposal`` computed from the request this consult sent.
    """
    sent = dict(outcome.request)
    forecast = forecast_from_request(decision_context({PROPOSAL_ENVELOPE_KEY: sent}))
    stocked = sorted(obs.inventory)
    count, actions, problems = _sentinel_reading(outcome.decision.proposals, frozenset(stocked))
    translated = outcome.translated
    routing = translated.routing_assignment
    return DecisionRecord(
        variant=variant,
        tier=str(outcome.decision.tier),
        binding_agent=outcome.binding_agent,
        bucket=outcome.dispatch.bucket,
        fingerprint=binding_fingerprint(outcome),
        translated_reorder_quantities={
            str(sku): float(quantity) for sku, quantity in translated.reorder_quantities.items()
        },
        translated_price=translated.price,
        translated_routing=None if routing is None else _canonical(dataclasses.asdict(routing)),
        translated_disruption_actions=tuple(sorted(translated.disruption_actions)),
        proposals=tuple(
            ProposalRecord(
                agent=str(proposal.agent_name),
                utility_score=proposal.utility_score,
                confidence=proposal.confidence,
            )
            for proposal in outcome.decision.proposals
        ),
        sentinel_proposals=count,
        sentinel_problems=problems,
        request_rebuilt=sent == observation_to_decision_request(obs),
        skus=tuple(_sku_record(sku, sent, forecast, actions.get(sku), params) for sku in stocked),
    )


def trace_probe(
    arm: PathwayConsultant, observations: Sequence[Observation], params: NewsvendorParams
) -> tuple[ObservationTrace, ...]:
    """Consult ``arm`` exactly as ``run_pathway_probe`` does, recording every consult.

    Per observation: the full request, its replay, and, only when the replay reproduced the full
    request's fingerprint, each carried input withheld in :data:`PROBE_INPUTS` order. Nothing is
    consulted that the probe does not consult, so state an agent keeps between calls evolves as
    it does under the probe.
    """
    traces: list[ObservationTrace] = []
    for index, obs in enumerate(observations):
        carried = tuple(name for name in PROBE_INPUTS if carries_input(obs, name))
        full = decision_record(FULL_REQUEST, obs, arm.consult(obs), params)
        replay = arm.consult(obs)
        replay_fingerprint = binding_fingerprint(replay)
        stable = replay_fingerprint == full.fingerprint
        withheld: list[DecisionRecord] = []
        consulted: tuple[ProbeInput, ...] = carried if stable else ()
        for name in consulted:
            withheld_obs = withhold_input(obs, name)
            withheld.append(decision_record(name, withheld_obs, arm.consult(withheld_obs), params))
        traces.append(
            ObservationTrace(
                index=index,
                sim_time=float(obs.sim_time),
                carried_inputs=carried,
                replay_fingerprint=replay_fingerprint,
                replay_binding_agent=replay.binding_agent,
                replay_stable=stable,
                variants=(full, *withheld),
                pairs=tuple(
                    pair_record(name, full, record)
                    for name, record in zip(consulted, withheld, strict=True)
                ),
            )
        )
    return tuple(traces)


def _unconsultable(arm: DecisionPolicy) -> str:
    """Why ``arm`` cannot be traced, with the stand-in's own reason when it is the stand-in."""
    if isinstance(arm, UnavailableConsensusArm):
        return (
            "the consensus arm is the UnavailableConsensusArm stand-in, which has no pathway to "
            f"consult and is never traced; its reason: {arm.reason}"
        )
    return (
        f"the consensus arm is a {type(arm).__name__}, not a PathwayConsultant with levers and "
        "consult, so there is no decision to trace"
    )


def run_trace(
    *,
    arm_factory: Callable[[], DecisionPolicy],
    sampler: Callable[[], Sequence[Observation]],
    params: NewsvendorParams,
) -> TraceDocument:
    """Trace the probe over the sampler's states, then compare a fresh probe over the same states.

    ``arm_factory`` is called twice: for the arm the trace consults, and, after the trace, for the
    fresh arm ``run_pathway_probe`` consults. A stand-in is never traced. Production passes
    :func:`uplift.e5_suite.e5_consensus_policy` and :func:`uplift.e5_suite.e5_probe_observations`;
    a fast test passes doubles, so that no twin and no agent handler runs.
    """
    arm = arm_factory()
    if not isinstance(arm, PathwayConsultant):
        return refused_document(
            arm=arm.name, levers=(), check="arm_not_consultable", detail=_unconsultable(arm)
        )
    levers = tuple(sorted(arm.levers))
    observations = tuple(sampler())
    if not observations:
        return refused_document(
            arm=arm.name,
            levers=levers,
            check="no_observation",
            detail="the probe's sampler returned no observation, so no decision can be traced",
        )
    traces = trace_probe(arm, observations, params)
    fresh = arm_factory()
    production: PathwayProbeReport | str
    if not isinstance(fresh, PathwayConsultant):
        production = f"the fresh arm for run_pathway_probe has no pathway: {_unconsultable(fresh)}"
    else:
        try:
            production = run_pathway_probe(fresh, observations)
        except PathwayProbeError as exc:
            production = f"run_pathway_probe stated no rate over the same states: {exc}"
        except Exception as exc:  # noqa: BLE001 - recorded beside the trace, never in its place
            production = f"run_pathway_probe could not run: {type(exc).__name__}: {exc}"
    return build_document(
        arm=arm.name,
        levers=levers,
        basis=q_star_basis(params),
        observations=traces,
        production=production,
    )


def _quiet_logging() -> None:
    """structlog at ERROR, to stderr, so stdout carries the summary alone.

    Mirrors ``uplift.cost_probe._quiet_logging``, which measured about 500 MB of engine debug lines
    in one simulated hour without it, and the sampler simulates fifteen. CLI-only: it is global.
    """
    structlog.configure(
        wrapper_class=structlog.make_filtering_bound_logger(logging.ERROR),
        logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
    )


def main(argv: Sequence[str]) -> int:
    """``python -m scripts.diagnostics.pathway_trace --output PATH``: trace, write, summarise."""
    parser = argparse.ArgumentParser(
        prog="python -m scripts.diagnostics.pathway_trace",
        description=(
            "Trace R7.21's pathway probe through its own production code: which agent bound "
            "each probed decision, and each SKU's q* against its stock (ADR-058 falsification "
            "item 1). CI only: it stands up the eight agents and runs the twin."
        ),
    )
    # A FILE, never stdout, for uplift.cost_probe's reason: the agents and the twin log to the
    # process's streams. Required, with no default, and never overwritten.
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(list(argv))
    output: Path = args.output
    if output.exists():
        sys.stdout.write(
            f"pathway_trace: refused: {_ascii(output.as_posix())} exists, and a trace never "
            "overwrites a file\n"
        )
        return EXIT_UNTRACEABLE
    _quiet_logging()
    # Imported once the logging floor is set, as uplift.cost_probe imports what it drives.
    from uplift.e5_suite import e5_consensus_policy, e5_probe_observations

    document = run_trace(
        arm_factory=e5_consensus_policy,
        sampler=e5_probe_observations,
        # The pipeline's own parameters, built as it builds them: build_agent_handlers gives the
        # Sentinel's handler no pipeline, `pipeline or InventorySentinelPipeline()` builds one,
        # and its __init__ holds `newsvendor_params or NewsvendorParams()`.
        params=NewsvendorParams(),
    )
    write_trace(output, document)
    for line in summary_lines(document, output):
        sys.stdout.write(f"{line}\n")
    return exit_code(document)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
