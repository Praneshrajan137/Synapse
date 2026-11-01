"""What the consensus arm's decisions amount to, reported beside E5's number (R7.20, R7.21).

decision-quality-proof task 29.6. Two records in one module, because both are published beside
the headline and neither may be read as part of it:

* :class:`DispatchReport` (R7.20, decision Q2=a). Per run, how many binding decisions were
  dispatched, withheld for confidence, blocked by a guardrail, or untranslatable -- the tally
  :class:`~uplift.consensus_arm.ConsensusArm` keeps as a :class:`~uplift.interfaces.RunScoped`
  policy -- summed, with the dispatch rate ``dispatched / total`` and the wording
  ``"recommendations, if executed"``. With no decision the rate is ``None`` and says why; it is
  never 0, because 0 would read as "nothing was dispatched" when nothing was measured.
* :class:`PathwayProbeReport` (R7.21, decision 3=a, finding 68). For each input the request now
  carries -- on-order stock, supplier lead-time history, demand to date -- how many observations
  were decided both with it and without it, and how often the binding decision changed. A probe
  showing no response is a finding reported beside E5's number, never a relabelling of it; a
  rate over zero pairs is refused, because it measures nothing. When the probe states no rate
  -- the arm has no pathway to consult, an input has zero pairs, or the probe could not run --
  a :class:`PathwayProbeRefusal` is written in its place, naming the arm and why (finding 109):
  the probe's absence is a finding too, and it refuses nothing else.

Each is a frozen pydantic record with ``extra="forbid"``, written in the repository's one
canonical JSON form, and every derived field is re-derived on construction and refused if it
disagrees.
"""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path
from typing import TYPE_CHECKING, Final, Literal, Protocol, runtime_checkable

import structlog
from pydantic import BaseModel, ConfigDict, Field, model_validator

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

    from uplift.consensus_arm import ConsensusOutcome
    from uplift.interfaces import DecisionCounts, Observation, ScenarioRun

logger = structlog.get_logger(__name__)

#: R7.20 (decision Q2=a): the published claim is worded as recommendations if executed.
DISPATCH_WORDING: Final = "recommendations, if executed"


class DispatchReportError(ValueError):
    """A dispatch report that would misstate what the consensus arm's runs recorded."""


class PathwayProbeError(ValueError):
    """A pathway probe record that would state what nobody measured.

    A rate over zero pairs, or a refusal that names no arm or no reason.
    """


def _canonical(payload: object) -> str:
    """``json.dumps(..., sort_keys=True, separators=(',', ':'))`` -- the repo convention."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


# ---------------------------------------------------------------------------
# R7.20 -- the dispatch report
# ---------------------------------------------------------------------------
class DecisionCountsRecord(BaseModel):
    """The recorded form of :class:`~uplift.interfaces.DecisionCounts`, with its total."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    dispatched: int = Field(strict=True, ge=0)
    withheld_for_confidence: int = Field(strict=True, ge=0)
    guardrail_blocked: int = Field(strict=True, ge=0)
    untranslatable: int = Field(strict=True, ge=0)
    total: int = Field(strict=True, ge=0)

    @model_validator(mode="after")
    def _total_is_the_sum_of_the_four(self) -> DecisionCountsRecord:
        parts = (
            self.dispatched
            + self.withheld_for_confidence
            + self.guardrail_blocked
            + self.untranslatable
        )
        if self.total != parts:
            raise DispatchReportError(
                f"total={self.total} but the four buckets sum to {parts}; a total is a sum"
            )
        return self

    @classmethod
    def of(cls, counts: DecisionCounts) -> DecisionCountsRecord:
        """Record one run's tally field for field; the total is refused if it is not the sum."""
        return cls(
            dispatched=counts.dispatched,
            withheld_for_confidence=counts.withheld_for_confidence,
            guardrail_blocked=counts.guardrail_blocked,
            untranslatable=counts.untranslatable,
            total=counts.total,
        )

    @classmethod
    def summed(cls, records: Iterable[DecisionCountsRecord]) -> DecisionCountsRecord:
        """Bucket-wise sums over ``records``; an empty iterable sums to zeros."""
        dispatched = withheld = blocked = untranslatable = 0
        for record in records:
            dispatched += record.dispatched
            withheld += record.withheld_for_confidence
            blocked += record.guardrail_blocked
            untranslatable += record.untranslatable
        return cls(
            dispatched=dispatched,
            withheld_for_confidence=withheld,
            guardrail_blocked=blocked,
            untranslatable=untranslatable,
            total=dispatched + withheld + blocked + untranslatable,
        )


class RunDispatchRecord(BaseModel):
    """One run's tally, in run order. A failed run carries none; a completed run must."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    seed: int = Field(strict=True, ge=0)
    failed: bool = Field(strict=True)
    counts: DecisionCountsRecord | None

    @model_validator(mode="after")
    def _a_completed_run_counted_what_it_decided(self) -> RunDispatchRecord:
        if self.failed and self.counts is not None:
            raise DispatchReportError(
                f"run seed={self.seed} failed but carries a tally; a failed run records none"
            )
        if not self.failed and self.counts is None:
            raise DispatchReportError(
                f"completed run seed={self.seed} carries no tally: a counting arm that reports "
                "nothing is a defect, not a zero"
            )
        if not self.failed and self.counts is not None and self.counts.total == 0:
            raise DispatchReportError(
                f"completed run seed={self.seed} counted 0 decisions, but a completed closed "
                "loop decides at least once: the tally missed what the arm decided"
            )
        return self


class DispatchReport(BaseModel):
    """How the consensus arm's binding decisions reached the twin, over one arm's runs (R7.20).

    ``counts`` sums the completed runs' tallies; ``per_run`` lists every run in the order given,
    a failed run with no tally. ``dispatch_rate`` is ``counts.dispatched / counts.total`` exactly,
    or ``None`` with ``rate_unavailable_reason`` stated when no decision was counted -- never 0.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    kind: Literal["consensus-dispatch-report"]
    schema_version: Literal[1]
    arm: str
    wording: Literal["recommendations, if executed"]
    runs: int = Field(strict=True, ge=1)
    completed_runs: int = Field(strict=True, ge=0)
    failed_runs: int = Field(strict=True, ge=0)
    counts: DecisionCountsRecord
    per_run: tuple[RunDispatchRecord, ...]
    dispatch_rate: float | None
    rate_unavailable_reason: str | None

    @model_validator(mode="after")
    def _derived_fields_are_what_the_runs_say(self) -> DispatchReport:
        refusals: list[str] = []
        if not self.arm.strip() or self.arm != self.arm.strip():
            refusals.append(f"arm {self.arm!r} does not name an arm")
        if len(self.per_run) != self.runs:
            refusals.append(f"runs={self.runs} but per_run lists {len(self.per_run)}")
        failed = sum(1 for run in self.per_run if run.failed)
        if self.failed_runs != failed or self.completed_runs != len(self.per_run) - failed:
            refusals.append(
                f"completed={self.completed_runs}, failed={self.failed_runs}, but per_run "
                f"holds {len(self.per_run) - failed} completed and {failed} failed"
            )
        summed = DecisionCountsRecord.summed(
            run.counts for run in self.per_run if run.counts is not None
        )
        if summed != self.counts:
            refusals.append("counts is not the sum of the per-run tallies")
        if self.counts.total == 0:
            reason = self.rate_unavailable_reason
            if self.dispatch_rate is not None or reason is None or not reason.strip():
                refusals.append("no decision was counted, so the rate is None and says why")
        elif (
            self.rate_unavailable_reason is not None
            or self.dispatch_rate != self.counts.dispatched / self.counts.total
        ):
            refusals.append(
                f"dispatch_rate={self.dispatch_rate!r} is not dispatched/total = "
                f"{self.counts.dispatched}/{self.counts.total}"
            )
        if refusals:
            raise DispatchReportError(
                "the dispatch report is refused rather than recorded: " + "; ".join(refusals)
            )
        return self

    def to_canonical_json(self) -> str:
        """The report in this repository's one canonical JSON form."""
        return _canonical(self.model_dump(mode="json"))


def _run_record(run: ScenarioRun) -> RunDispatchRecord:
    tally = run.decision_counts
    if run.failed:
        if tally is not None:
            raise DispatchReportError(
                f"failed run seed={run.seed} of {run.arm!r} carries a tally; a failed run "
                "records decision_counts=None"
            )
        return RunDispatchRecord(seed=run.seed, failed=True, counts=None)
    if tally is None:
        raise DispatchReportError(
            f"completed run seed={run.seed} of {run.arm!r} carries no decision tally: a counting "
            "arm that reports nothing is a defect, not a zero"
        )
    if tally.total == 0:
        raise DispatchReportError(
            f"completed run seed={run.seed} of {run.arm!r} counted 0 decisions, but a completed "
            "closed loop decides at least once: the tally missed what the arm decided"
        )
    return RunDispatchRecord(seed=run.seed, failed=False, counts=DecisionCountsRecord.of(tally))


def summarise_dispatch(runs: Sequence[ScenarioRun], *, arm: str) -> DispatchReport:
    """Sum one arm's per-run tallies into the report published beside the headline (R7.20).

    Raises:
        DispatchReportError: when ``runs`` is empty, holds a run of another arm, or holds a
            completed run with no tally (or a failed run with one). A report over runs it was
            not given, or over a tally that was never kept, would state a rate nobody measured.
    """
    if not runs:
        raise DispatchReportError(
            f"no run of {arm!r} was given; a dispatch report over nothing reports nothing"
        )
    foreign = sorted({run.arm for run in runs if run.arm != arm})
    if foreign:
        raise DispatchReportError(
            f"runs of {foreign} are not runs of {arm!r}; one report summarises one arm"
        )
    per_run = tuple(_run_record(run) for run in runs)
    counts = DecisionCountsRecord.summed(
        record.counts for record in per_run if record.counts is not None
    )
    failed = sum(1 for record in per_run if record.failed)
    rate: float | None = None
    reason: str | None = None
    if counts.total > 0:
        rate = counts.dispatched / counts.total
    else:
        reason = (
            f"no completed run of {arm!r} counted a binding decision ({failed} of {len(runs)} "
            "run(s) failed), so there is no dispatch rate to state"
        )
    return DispatchReport(
        kind="consensus-dispatch-report",
        schema_version=1,
        arm=arm,
        wording=DISPATCH_WORDING,
        runs=len(runs),
        completed_runs=len(runs) - failed,
        failed_runs=failed,
        counts=counts,
        per_run=per_run,
        dispatch_rate=rate,
        rate_unavailable_reason=reason,
    )


def write_dispatch_report(path: Path, report: DispatchReport) -> Path:
    """Write ``report``'s canonical JSON to ``path`` (no trailing newline) and return the path."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(report.to_canonical_json(), encoding="utf-8")
    logger.info(
        "dispatch_report_written",
        path=str(target),
        arm=report.arm,
        runs=report.runs,
        failed_runs=report.failed_runs,
        dispatch_rate=report.dispatch_rate,
    )
    return target


def read_dispatch_report(path: Path) -> DispatchReport:
    """Read a report written by :func:`write_dispatch_report`, re-deriving every field."""
    return DispatchReport.model_validate_json(Path(path).read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# R7.21 -- the information-pathway probe
# ---------------------------------------------------------------------------
#: An input R7.21 names, by the :class:`~uplift.interfaces.Observation` field that carries it.
ProbeInput = Literal["on_order", "supplier_lead_time_history", "demand_to_date"]

#: R7.21's three inputs, in the order the probe reports them.
PROBE_INPUTS: Final[tuple[ProbeInput, ...]] = (
    "on_order",
    "supplier_lead_time_history",
    "demand_to_date",
)


def carries_input(obs: Observation, name: ProbeInput) -> bool:
    """Whether ``obs`` holds anything to withhold for ``name``; a pair needs a contrast."""
    if name == "on_order":
        return any(quantity > 0.0 for quantity in obs.on_order.values())
    if name == "supplier_lead_time_history":
        return any(len(times) > 0 for times in obs.supplier_lead_time_history.values())
    if name == "demand_to_date":
        return any(count > 0 for count in obs.demand_to_date.values())
    raise PathwayProbeError(f"{name!r} is not one of the probe's inputs {list(PROBE_INPUTS)}")


def withhold_input(obs: Observation, name: ProbeInput) -> Observation:
    """``obs`` with ``name`` withheld: the planner is told nothing about it, nothing else moves.

    Withholding ``on_order`` also moves the request's ``inventory_position``, by construction:
    a planner that does not know its open orders cannot add them to its stock.
    """
    if name == "on_order":
        return dataclasses.replace(obs, on_order={})
    if name == "supplier_lead_time_history":
        return dataclasses.replace(obs, supplier_lead_time_history={})
    if name == "demand_to_date":
        return dataclasses.replace(obs, demand_to_date={})
    raise PathwayProbeError(f"{name!r} is not one of the probe's inputs {list(PROBE_INPUTS)}")


def binding_fingerprint(outcome: ConsensusOutcome) -> str:
    """The binding decision as compared: the agent that bound, its bucket, and its translation.

    Canonical JSON, so equal decisions compare equal byte for byte. Untranslated payload
    content is NOT compared: it reaches no lever, and per-call fields such as the pricing
    oracle's ``pricing_id`` and ``timestamp`` would make every pair read as changed.
    """
    action = outcome.translated
    routing = action.routing_assignment
    return _canonical(
        {
            "binding_agent": outcome.binding_agent,
            "bucket": outcome.dispatch.bucket,
            "disruption_actions": sorted(action.disruption_actions),
            "price": action.price,
            "reorder_quantities": {
                str(sku): float(qty) for sku, qty in action.reorder_quantities.items()
            },
            "routing": None if routing is None else dataclasses.asdict(routing),
        }
    )


def response_rate(*, pairs: int, changed: int) -> float:
    """``changed / pairs``, refused over zero pairs: a rate over nothing measures nothing."""
    if pairs < 1:
        raise PathwayProbeError(
            f"a response rate over {pairs} pair(s) measures nothing; no input is reported as "
            "unresponsive, or as responsive, on zero contrasts"
        )
    if not 0 <= changed <= pairs:
        raise PathwayProbeError(f"changed={changed} lies outside [0, pairs={pairs}]")
    return changed / pairs


class ProbeInputResult(BaseModel):
    """One input's contrasts: observations carrying it, stable pairs, and decisions changed."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    input_name: ProbeInput
    carried: int = Field(strict=True, ge=1)
    pairs: int = Field(strict=True, ge=1)
    changed: int = Field(strict=True, ge=0)
    rate: float

    @model_validator(mode="after")
    def _the_rate_is_measured_over_the_pairs(self) -> ProbeInputResult:
        if self.pairs > self.carried:
            raise PathwayProbeError(
                f"{self.input_name}: pairs={self.pairs} exceeds the {self.carried} "
                "observation(s) that carried it"
            )
        expected = response_rate(pairs=self.pairs, changed=self.changed)
        if self.rate != expected:
            raise PathwayProbeError(
                f"{self.input_name}: rate={self.rate!r} is not changed/pairs = {expected!r}"
            )
        return self


class PathwayProbeReport(BaseModel):
    """Whether the consensus pathway responds to what the request carries (R7.21).

    ``unresponsive_inputs`` names every input no pair changed. It is reported beside E5's
    number as a finding; nothing here relabels E5.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    kind: Literal["consensus-pathway-probe"]
    schema_version: Literal[1]
    arm: str
    levers: tuple[str, ...]
    observations: int = Field(strict=True, ge=1)
    replay_unstable: int = Field(strict=True, ge=0)
    full_request_buckets: DecisionCountsRecord
    inputs: tuple[ProbeInputResult, ...]
    unresponsive_inputs: tuple[ProbeInput, ...]

    @model_validator(mode="after")
    def _derived_fields_are_what_the_pairs_say(self) -> PathwayProbeReport:
        refusals: list[str] = []
        if not self.arm.strip() or self.arm != self.arm.strip():
            refusals.append(f"arm {self.arm!r} does not name an arm")
        if not self.levers or list(self.levers) != sorted(set(self.levers)):
            refusals.append(f"levers {list(self.levers)} is not a sorted, non-empty set")
        if self.replay_unstable > self.observations:
            refusals.append(
                f"replay_unstable={self.replay_unstable} exceeds {self.observations} observations"
            )
        if self.full_request_buckets.total != self.observations:
            refusals.append(
                f"the full-request tally counts {self.full_request_buckets.total} decisions over "
                f"{self.observations} observations; each is decided once with the full request"
            )
        names = tuple(result.input_name for result in self.inputs)
        if names != PROBE_INPUTS:
            refusals.append(f"inputs {list(names)} are not exactly {list(PROBE_INPUTS)}, in order")
        stable = self.observations - self.replay_unstable
        for result in self.inputs:
            if result.carried > self.observations or result.pairs > stable:
                refusals.append(
                    f"{result.input_name}: carried={result.carried}, pairs={result.pairs} exceed "
                    f"{self.observations} observations, {stable} of them replay-stable"
                )
        unresponsive = tuple(result.input_name for result in self.inputs if result.changed == 0)
        if self.unresponsive_inputs != unresponsive:
            refusals.append(
                f"unresponsive_inputs {list(self.unresponsive_inputs)} is not the inputs no pair "
                f"changed, {list(unresponsive)}"
            )
        if refusals:
            raise PathwayProbeError(
                "the pathway probe report is refused rather than recorded: " + "; ".join(refusals)
            )
        return self

    def to_canonical_json(self) -> str:
        """The report in this repository's one canonical JSON form."""
        return _canonical(self.model_dump(mode="json"))


@runtime_checkable
class PathwayConsultant(Protocol):
    """What the probe needs of an arm: its name, its lever set, and a consult that counts nothing.

    :class:`~uplift.consensus_arm.ConsensusArm` satisfies it. Runtime-checkable, so a caller can
    tell an arm with a pathway from the :class:`~uplift.policies.UnavailableConsensusArm`
    stand-in, which has neither ``levers`` nor ``consult``, before consulting anything; the check
    is structural, by member presence, as every runtime protocol check is.
    """

    @property
    def name(self) -> str:
        """The arm identifier the report names."""
        ...

    @property
    def levers(self) -> frozenset[str]:
        """The levers the arm's suite applies."""
        ...

    def consult(self, obs: Observation) -> ConsensusOutcome:
        """Decide ``obs`` once, without moving any run's tally."""
        ...


def run_pathway_probe(
    arm: PathwayConsultant, observations: Sequence[Observation]
) -> PathwayProbeReport:
    """Decide each observation with the full request, replay it, then withhold each input once.

    Per observation: consult the full request twice -- the replay control, because a pathway
    that does not reproduce its own decision cannot attribute a change to an input, so that
    observation contributes no pair -- then, for each input it carries, consult once with that
    input withheld and compare :func:`binding_fingerprint`. An observation's consults are
    adjacent, so state an agent keeps between calls has the least room to pose as a response.
    Nothing is asserted about whether any input changes the decision: an input no pair changed
    is named in ``unresponsive_inputs`` (R7.21), never relabelled.

    Raises:
        PathwayProbeError: before consulting anything when no observation carries some input,
            and after consulting when every observation carrying it failed its replay -- either
            way that input has zero pairs, and a rate over zero pairs measures nothing.
    """
    if not observations:
        raise PathwayProbeError("the probe was given no observation, so it has no pair at all")
    carried = [
        tuple(name for name in PROBE_INPUTS if carries_input(obs, name)) for obs in observations
    ]
    for name in PROBE_INPUTS:
        if not any(name in names for names in carried):
            raise PathwayProbeError(
                f"no observation carries {name!r}: withholding it changes no request, so it has "
                "zero pairs and no rate can be stated"
            )
    pairs = dict.fromkeys(PROBE_INPUTS, 0)
    changed = dict.fromkeys(PROBE_INPUTS, 0)
    # The four bucket names are DecisionCounts's (and DecisionCountsRecord's) fields.
    buckets = dict.fromkeys(
        ("dispatched", "withheld_for_confidence", "guardrail_blocked", "untranslatable"), 0
    )
    unstable = 0
    for obs, names in zip(observations, carried, strict=True):
        full = arm.consult(obs)
        buckets[full.dispatch.bucket] += 1
        reference = binding_fingerprint(full)
        if binding_fingerprint(arm.consult(obs)) != reference:
            unstable += 1
            continue
        for name in names:
            pairs[name] += 1
            if binding_fingerprint(arm.consult(withhold_input(obs, name))) != reference:
                changed[name] += 1
    results: list[ProbeInputResult] = []
    for name in PROBE_INPUTS:
        carrying = sum(1 for names in carried if name in names)
        if pairs[name] == 0:
            raise PathwayProbeError(
                f"all {carrying} observation(s) carrying {name!r} failed the replay control, so "
                "it has zero stable pairs; a pathway that does not reproduce its own decision "
                "cannot attribute a change to an input"
            )
        results.append(
            ProbeInputResult(
                input_name=name,
                carried=carrying,
                pairs=pairs[name],
                changed=changed[name],
                rate=response_rate(pairs=pairs[name], changed=changed[name]),
            )
        )
    return PathwayProbeReport(
        kind="consensus-pathway-probe",
        schema_version=1,
        arm=arm.name,
        levers=tuple(sorted(arm.levers)),
        observations=len(observations),
        replay_unstable=unstable,
        full_request_buckets=DecisionCountsRecord(
            dispatched=buckets["dispatched"],
            withheld_for_confidence=buckets["withheld_for_confidence"],
            guardrail_blocked=buckets["guardrail_blocked"],
            untranslatable=buckets["untranslatable"],
            total=len(observations),
        ),
        inputs=tuple(results),
        unresponsive_inputs=tuple(result.input_name for result in results if result.changed == 0),
    )


def write_probe_report(path: Path, report: PathwayProbeReport) -> Path:
    """Write ``report``'s canonical JSON to ``path`` (no trailing newline) and return the path."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(report.to_canonical_json(), encoding="utf-8")
    logger.info(
        "pathway_probe_written",
        path=str(target),
        observations=report.observations,
        replay_unstable=report.replay_unstable,
        unresponsive_inputs=list(report.unresponsive_inputs),
    )
    return target


def read_probe_report(path: Path) -> PathwayProbeReport:
    """Read a report written by :func:`write_probe_report`, re-deriving every field."""
    return PathwayProbeReport.model_validate_json(Path(path).read_text(encoding="utf-8"))


class PathwayProbeRefusal(BaseModel):
    """Why R7.21's probe states no rate for a run, written in place of its report (finding 109).

    Two causes, each named in ``reason``: the arm has no pathway to consult (the
    :class:`~uplift.policies.UnavailableConsensusArm` stand-in is not a
    :class:`PathwayConsultant`), or the probe states no rate (:class:`PathwayProbeError`: an
    input with zero pairs) or cannot run. This record never refuses the run it sits beside. The
    probe's absence is a finding reported beside E5's number, exactly as an unresponsive input
    is, and it relabels nothing. ``arm`` names an arm, and ``reason`` is not blank, because a
    refusal that states no reason explains nothing.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal["consensus-pathway-probe-refusal"]
    schema_version: Literal[1]
    arm: str
    reason: str

    @model_validator(mode="after")
    def _names_an_arm_and_a_reason(self) -> PathwayProbeRefusal:
        refusals: list[str] = []
        if not self.arm.strip() or self.arm != self.arm.strip():
            refusals.append(f"arm {self.arm!r} does not name an arm")
        if not self.reason.strip():
            refusals.append("a refusal that states no reason explains nothing")
        if refusals:
            raise PathwayProbeError(
                "the pathway probe refusal is refused rather than recorded: " + "; ".join(refusals)
            )
        return self

    @classmethod
    def of(cls, *, arm: str, reason: str) -> PathwayProbeRefusal:
        """The refusal for ``arm`` stating ``reason``, at this record's kind and version."""
        return cls(
            kind="consensus-pathway-probe-refusal",
            schema_version=1,
            arm=arm,
            reason=reason,
        )

    def to_canonical_json(self) -> str:
        """The refusal in this repository's one canonical JSON form."""
        return _canonical(self.model_dump(mode="json"))


def write_probe_refusal(path: Path, refusal: PathwayProbeRefusal) -> Path:
    """Write ``refusal``'s canonical JSON to ``path`` (no trailing newline) and return the path."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(refusal.to_canonical_json(), encoding="utf-8")
    logger.info(
        "pathway_probe_refusal_written",
        path=str(target),
        arm=refusal.arm,
        reason=refusal.reason,
    )
    return target


def read_probe_refusal(path: Path) -> PathwayProbeRefusal:
    """Read a refusal written by :func:`write_probe_refusal`, re-checking every field."""
    return PathwayProbeRefusal.model_validate_json(Path(path).read_text(encoding="utf-8"))


__all__ = [
    "DISPATCH_WORDING",
    "PROBE_INPUTS",
    "DecisionCountsRecord",
    "DispatchReport",
    "DispatchReportError",
    "PathwayConsultant",
    "PathwayProbeError",
    "PathwayProbeRefusal",
    "PathwayProbeReport",
    "ProbeInput",
    "ProbeInputResult",
    "RunDispatchRecord",
    "binding_fingerprint",
    "carries_input",
    "read_dispatch_report",
    "read_probe_refusal",
    "read_probe_report",
    "response_rate",
    "run_pathway_probe",
    "summarise_dispatch",
    "withhold_input",
    "write_dispatch_report",
    "write_probe_refusal",
    "write_probe_report",
]
