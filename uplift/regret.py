"""The scalar regret objective, and the rule that a null needs a sensitive instrument.

Feature: decision-quality-proof, tasks 10.1 and 10.5 (R5.1, R5.3, R5.14, R5.33, R5.34, R5.35).

**Why this module exists at all.** ``uplift/metric_contract.yaml`` declares per-KPI hypothesis
tests, and ``MetricContract.classify`` returns a three-valued ``Outcome`` -- **not a cost**.
There is no scalar objective anywhere else in the tree, so before this module regret had no
units, no sign convention and no aggregation rule. ``MetricContract.classify`` is deliberately
**left untouched**: conflating a hypothesis outcome with a cost is how a regret number acquires
units nobody declared.

**Everything numeric here is read, not chosen.** Weights, normalisers and the aggregation rule
come from ``digital_twin/simulation/policy.yaml`` (AD-13), which ADR-055 D2 declared *before*
any run this judges. Two of the weights are themselves read from
``agents/inventory_sentinel/models/newsvendor.py`` -- an 8:1 shortage-to-holding ratio this
repository already commits -- so the objective and the inventory agent's own reward agree about
what matters. Nothing is defaulted: a missing key raises rather than substituting a plausible
number, because a default reintroduces at the reader exactly the defect the policy file removes.

**Task 10.5 is the criterion that makes R5.1 a measurement rather than an artefact.** A regret
below the materiality margin, measured while any objective KPI is recorded under R5.34 as not
observably sensitive, is reported ``inconclusive`` and **must not** be reported as confirming
Finding 4. A null produced by an insensitive instrument is not evidence of absence (I-7).

**The state of that rule as of task 10, stated before the run it decides.** Two of five
objective KPIs -- ``spoilage_rate`` and ``delivery_latency`` -- are still recorded
``sensitive: false``, because ``_spoilage`` reads neither inventory nor order size and
``_delivery`` draws travel time from an independent uniform. Structures 4 and 2 (tasks 13.3 and
12.3) earn those flips. Until then **any sub-margin regret is inconclusive**: task 11 can
*falsify* Finding 4 by measuring material regret, but it cannot *confirm* it. That is this
plan's own guard working, not a defect in it.
"""

from __future__ import annotations

import dataclasses
import statistics
from typing import Final, Literal

from digital_twin.simulation.policy import POLICY_PATH, PolicyUnavailableError, load_policy, require

__all__ = [
    "OBJECTIVE_TERMS",
    "InsensitiveKpi",
    "RegretObjective",
    "RegretVerdict",
    "TermContribution",
    "classify_regret",
    "load_objective",
]

#: The five cost terms ADR-055 D2.1 declares, in the order the ADR tables them. Each is a
#: COST -- lower is better -- so the objective is minimised and regret is non-negative by
#: construction. ``margin`` and ``co2_estimate`` are deliberately excluded; the policy file's
#: ``excluded_terms`` block records why, so the exclusion is a decision and not an oversight.
OBJECTIVE_TERMS: Final[tuple[str, ...]] = (
    "stockout_rate",
    "spoilage_rate",
    "on_hand",
    "delivery_latency",
    "unmet_service",
)

Verdict = Literal["material", "sub-margin", "inconclusive", "unavailable"]


@dataclasses.dataclass(frozen=True)
class InsensitiveKpi:
    """One objective KPI recorded as not observably sensitive, and why."""

    term: str
    blocked_on: str


@dataclasses.dataclass(frozen=True)
class TermContribution:
    """One term's raw value, normalised value, weight and weighted cost.

    Recorded per term rather than summed silently, because a regret number whose composition
    cannot be inspected is a number nobody can argue with -- and the whole point of committing
    the weights was to make the composition arguable.
    """

    term: str
    raw: float
    normalised: float
    weight: float
    weighted: float


@dataclasses.dataclass(frozen=True)
class RegretObjective:
    """The committed scalar cost objective (ADR-055 D2).

    Constructed only via :func:`load_objective`, which reads every number from the policy file.
    """

    weights: dict[str, float]
    on_hand_normaliser: float
    delivery_normaliser: float
    aggregation: str
    sensitivity: dict[str, bool]
    insensitive: tuple[InsensitiveKpi, ...]

    def contributions(
        self,
        *,
        stockout_rate: float,
        spoilage_rate: float,
        fill_rate: float,
        avg_on_hand_units: float,
        avg_delivery_time_min: float,
    ) -> tuple[TermContribution, ...]:
        """Decompose one KPI observation into its five weighted cost terms.

        ``fill_rate`` enters as ``1 - fill_rate`` (unmet service), which is what makes every
        term a cost. ``fill_rate`` and ``stockout_rate`` are related but not redundant after
        E2a: the first is delivered over demand events, the second is unmet over demand events,
        and they diverge whenever an order is created and never delivered for a reason other
        than stock.
        """
        raw: dict[str, float] = {
            "stockout_rate": stockout_rate,
            "spoilage_rate": spoilage_rate,
            "on_hand": avg_on_hand_units,
            "delivery_latency": avg_delivery_time_min,
            "unmet_service": 1.0 - fill_rate,
        }
        normalised: dict[str, float] = dict(raw)
        # Only two terms carry units; the other three are already fractions in [0, 1].
        normalised["on_hand"] = raw["on_hand"] / self.on_hand_normaliser
        normalised["delivery_latency"] = raw["delivery_latency"] / self.delivery_normaliser
        return tuple(
            TermContribution(
                term=term,
                raw=raw[term],
                normalised=normalised[term],
                weight=self.weights[term],
                weighted=normalised[term] * self.weights[term],
            )
            for term in OBJECTIVE_TERMS
        )

    def cost(self, **kpis: float) -> float:
        """The scalar objective for one observation. Total over any finite input."""
        return sum(item.weighted for item in self.contributions(**kpis))

    def aggregate(self, costs: list[float]) -> float:
        """Aggregate per-replicate costs by the committed rule.

        ``mean_paired_on_seed`` is the arithmetic mean, and the choice is decision-theoretic
        rather than statistical taste: this is a cost, expected cost is the quantity an
        inventory decision is made against, and a median would discard exactly the tail where
        policy differences live -- a policy that stocks out badly once in twenty replicates is
        meaningfully worse than one that never does, and the median cannot see it.
        """
        if not costs:
            raise ValueError("cannot aggregate an empty set of replicate costs")
        if self.aggregation != "mean_paired_on_seed":
            raise PolicyUnavailableError(
                f"unrecognised aggregation rule {self.aggregation!r}; this reader implements "
                "only 'mean_paired_on_seed' and will not guess at another"
            )
        return statistics.fmean(costs)

    def regret(self, policy_costs: list[float], reference_costs: list[float]) -> float:
        """Difference of aggregated costs, paired on replicate seeds.

        Paired because ``Scenario`` guarantees an identical seed yields an identical demand
        realisation across arms (R2.1/R2.5), and pairing removes demand variance from the
        contrast. Requires equal lengths: an unpaired difference is a different estimator with
        a different variance, and silently computing it would misreport precision.
        """
        if len(policy_costs) != len(reference_costs):
            raise ValueError(
                f"paired regret needs equal replicate counts, got {len(policy_costs)} and "
                f"{len(reference_costs)}; an unpaired difference is a different estimator"
            )
        return self.aggregate(policy_costs) - self.aggregate(reference_costs)


def load_objective(path: object = POLICY_PATH) -> RegretObjective:
    """Read the committed objective. Raises rather than defaulting any term.

    Also enforces ADR-055 D3's citation rule: a KPI recorded ``sensitive: true`` **must** carry
    a ``demonstrated_by`` reference naming the property test that shows it. A bare ``true`` is
    an assertion, and this phase exists to stop assertions standing in for evidence.
    """
    document = load_policy(path)  # type: ignore[arg-type]
    weights_raw = require(document, "regret_objective.weights", path=path)  # type: ignore[arg-type]
    weights = {str(name): float(value) for name, value in dict(weights_raw).items()}

    missing = [term for term in OBJECTIVE_TERMS if term not in weights]
    if missing:
        raise PolicyUnavailableError(
            f"{POLICY_PATH.as_posix()} declares no weight for {', '.join(missing)}; every "
            "objective term must be weighted explicitly, because an unweighted term silently "
            "contributes nothing and the objective would then not be the one ADR-055 declared"
        )

    on_hand = float(
        require(document, "regret_objective.normalisers.on_hand_units", path=path)  # type: ignore[arg-type]
    )
    delivery = float(
        require(document, "regret_objective.normalisers.delivery_time_min", path=path)  # type: ignore[arg-type]
    )
    if on_hand <= 0.0 or delivery <= 0.0:
        raise PolicyUnavailableError(
            "both normalisers must be strictly positive; a zero normaliser makes its term "
            "undefined rather than large"
        )

    aggregation = str(require(document, "regret_objective.aggregation", path=path))  # type: ignore[arg-type]

    sensitivity_raw = dict(require(document, "kpi_sensitivity", path=path))  # type: ignore[arg-type]
    sensitivity: dict[str, bool] = {}
    insensitive: list[InsensitiveKpi] = []
    for term in OBJECTIVE_TERMS:
        if term not in sensitivity_raw:
            raise PolicyUnavailableError(
                f"kpi_sensitivity declares nothing for objective term {term!r}. R5.34 requires a "
                "record PER objective KPI, and an unrecorded KPI cannot be treated as sensitive "
                "-- that is the direction I-7 forbids"
            )
        entry = dict(sensitivity_raw[term])
        is_sensitive = bool(entry.get("sensitive", False))
        if is_sensitive and not str(entry.get("demonstrated_by", "")).strip():
            raise PolicyUnavailableError(
                f"kpi_sensitivity.{term} claims sensitive: true with no `demonstrated_by` "
                "citation. ADR-055 D3 requires each flip to name the property test that shows "
                "it; a bare true is an assertion, not evidence"
            )
        sensitivity[term] = is_sensitive
        if not is_sensitive:
            insensitive.append(
                InsensitiveKpi(
                    term=term,
                    blocked_on=str(entry.get("blocked_on", "no reason recorded")).strip(),
                )
            )

    return RegretObjective(
        weights=weights,
        on_hand_normaliser=on_hand,
        delivery_normaliser=delivery,
        aggregation=aggregation,
        sensitivity=sensitivity,
        insensitive=tuple(insensitive),
    )


@dataclasses.dataclass(frozen=True)
class RegretVerdict:
    """What a measured regret licenses anyone to say (R5.3, R5.14, R5.35).

    Four values, and the third is the one task 10.5 exists for:

    * ``material``      -- regret at or above the margin with its interval excluding it.
      **Finding 4 is FALSIFIED.** R5's scope shrinks and the spec is re-cut (R5.3, R5.4).
    * ``sub-margin``    -- regret below the margin AND every objective KPI recorded sensitive.
      Only this value licenses reading the result as consistent with Finding 4.
    * ``inconclusive``  -- regret below the margin while ANY objective KPI is recorded not
      observably sensitive. **Not confirmation.** The repair is the instrument, not the twin's
      physics.
    * ``unavailable``   -- no margin is committed yet, so nothing can be judged. R5.2 forbids
      pinning the margin before measurement, so this is the honest state of the FIRST run and
      is not a defect.
    """

    verdict: Verdict
    regret: float
    margin: float | None
    interval_low: float | None
    interval_high: float | None
    insensitive: tuple[InsensitiveKpi, ...]
    reason: str

    @property
    def falsifies_finding_4(self) -> bool:
        return self.verdict == "material"

    @property
    def confirms_finding_4(self) -> bool:
        """True ONLY for ``sub-margin``. An ``inconclusive`` result confirms nothing."""
        return self.verdict == "sub-margin"


def classify_regret(
    regret: float,
    *,
    objective: RegretObjective,
    margin: float | None,
    interval: tuple[float, float] | None = None,
) -> RegretVerdict:
    """Classify a measured regret. Total: never raises, always names its reason.

    ``margin=None`` means R5.2's deferral is still in force -- the margin may only be committed
    after task 10.3 measures the distribution. That yields ``unavailable`` rather than a
    comparison against an invented threshold.
    """
    low, high = interval if interval is not None else (None, None)

    if margin is None:
        return RegretVerdict(
            verdict="unavailable",
            regret=regret,
            margin=None,
            interval_low=low,
            interval_high=high,
            insensitive=objective.insensitive,
            reason=(
                f"measured regret {regret:.6g}, but no materiality margin is committed: R5.2 "
                "forbids pinning it before measurement, so this run reports the value and "
                "judges nothing. Commit the margin from this distribution (task 10.4), then "
                "judge SUBSEQUENT runs against it"
            ),
        )

    # Material requires the interval to EXCLUDE the margin, not merely the point to exceed it.
    excludes_margin = low is not None and low > margin
    if regret >= margin and (interval is None or excludes_margin):
        interval_note = (
            f" with its interval [{low:.6g}, {high:.6g}] excluding it" if excludes_margin else ""
        )
        return RegretVerdict(
            verdict="material",
            regret=regret,
            margin=margin,
            interval_low=low,
            interval_high=high,
            insensitive=objective.insensitive,
            reason=(
                f"measured regret {regret:.6g} is at or above the committed margin "
                f"{margin:.6g}{interval_note}. FINDING 4 IS FALSIFIED: a base-stock (s, S) "
                "policy is already measurably sub-optimal on this twin, so R5's remaining scope "
                "shrinks and the spec must be re-cut rather than executed as written (R5.3, "
                "R5.4). This is a good outcome"
            ),
        )

    if objective.insensitive:
        named = ", ".join(item.term for item in objective.insensitive)
        return RegretVerdict(
            verdict="inconclusive",
            regret=regret,
            margin=margin,
            interval_low=low,
            interval_high=high,
            insensitive=objective.insensitive,
            reason=(
                f"measured regret {regret:.6g} is below the margin {margin:.6g}, but "
                f"{len(objective.insensitive)} objective KPI(s) are recorded as NOT observably "
                f"sensitive ({named}). A null produced by an instrument that cannot see its "
                "subject is not evidence of absence (I-7, R5.35), so this is INCONCLUSIVE and "
                "must NOT be reported as confirming Finding 4. The repair is the instrument, "
                "not the twin's physics"
            ),
        )

    return RegretVerdict(
        verdict="sub-margin",
        regret=regret,
        margin=margin,
        interval_low=low,
        interval_high=high,
        insensitive=(),
        reason=(
            f"measured regret {regret:.6g} is below the committed margin {margin:.6g} while "
            "every objective KPI is recorded observably sensitive, so the instrument could "
            "have seen an effect and did not. This is the only verdict that licenses reading "
            "the result as consistent with Finding 4"
        ),
    )


# ---------------------------------------------------------------------------
# Measurement CLI -- the entry point `uplift.yml::twin-regret` invokes (task 10.3)
# ---------------------------------------------------------------------------
#
# CI ONLY. The two-pass protocol doubles the twin cost of every replicate, and a run at
# `MIN_SCENARIOS` scale is a category-4 workload under I-0 that must never execute on a
# development machine. `--replicates` defaults small so an accidental local invocation is
# cheap and obvious rather than thermally expensive.


def _measure(replicates: int, hours: float) -> dict[str, object]:
    """Run the two-pass comparator over ``replicates`` seeds and report, without judging."""
    # Imported here, not at module scope: `regret.py` is imported by the fast property suite,
    # and pulling the engine in at import time would drag SimPy into every one of those runs.
    from digital_twin.simulation.policy import (
        comparator_restock_threshold,
        materiality_margin,
        materiality_margin_rule,
    )
    from uplift.foresight import run_two_pass

    objective = load_objective()
    threshold = comparator_restock_threshold()

    baseline_costs: list[float] = []
    foresight_costs: list[float] = []
    unusable: list[int] = []

    def _cost(sim: object) -> float:
        metrics = sim.metrics  # type: ignore[attr-defined]
        return objective.cost(
            stockout_rate=metrics.stockout_rate,
            spoilage_rate=metrics.spoilage_rate,
            fill_rate=metrics.fill_rate,
            avg_on_hand_units=metrics.avg_on_hand_units(sim.sim_time_min),  # type: ignore[attr-defined]
            avg_delivery_time_min=metrics.avg_delivery_time_min,
        )

    for seed in range(replicates):
        result = run_two_pass(seed, hours=hours, restock_threshold=threshold)
        if not result.usable:
            # A replicate whose two passes saw different demand is not evidence. Recorded and
            # excluded rather than silently averaged in (I-7).
            unusable.append(seed)
            continue
        baseline_costs.append(_cost(result.baseline))
        foresight_costs.append(_cost(result.foresight))

    if not baseline_costs:
        return {
            "status": "unavailable",
            "reason": (
                "no replicate produced usable evidence: every pass pair disagreed on the "
                "demand path, so nothing was measured"
            ),
            "unusable_seeds": unusable,
        }

    measured = objective.regret(baseline_costs, foresight_costs)
    mean_baseline = objective.aggregate(baseline_costs)
    mean_foresight = objective.aggregate(foresight_costs)
    # The comparator's headroom bounds any (s, S) regret from above, and it is what the
    # committed margin is checked against: a margin at or above it is unfalsifiable.
    headroom = mean_baseline - mean_foresight

    # `margin` is READ, not hardcoded. It is `None` until task 10.4 instantiates it, which
    # yields `unavailable` -- the honest verdict for the first run (R5.2). The RULE, however,
    # is required and is reported here, so checkpoint A's operator can see the value the rule
    # produces beside the measurement rather than choosing a number to suit it (ADR-055 D2.5).
    rule = materiality_margin_rule()
    margin = materiality_margin(measured_headroom=headroom)
    verdict = classify_regret(measured, objective=objective, margin=margin)
    return {
        "status": "measured",
        "replicates_usable": len(baseline_costs),
        "replicates_unusable": len(unusable),
        "unusable_seeds": unusable,
        "hours_per_replicate": hours,
        "restock_threshold": threshold,
        "mean_baseline_cost": mean_baseline,
        "mean_foresight_cost": mean_foresight,
        "comparator_headroom": headroom,
        "regret": measured,
        "margin_committed": margin,
        "margin_rule": rule.describe(),
        "margin_rule_derives": rule.derived,
        "margin_rule_below_headroom": rule.derived < headroom,
        "verdict": verdict.verdict,
        "reason": verdict.reason,
        "insensitive_kpis": [item.term for item in objective.insensitive],
        "comparator": (
            "no-op vs perfect-foresight. NOTE: this is NOT yet the (s, S) regret R5.1 asks "
            "for -- Par_Level_Reorder is owned by decision-integrity-uplift-proof and is a "
            "PRECONDITION. This job measures the comparator's own headroom, which bounds it"
        ),
    }


def main(argv: list[str] | None = None) -> int:
    """Measure and report. Exit 0 on a completed measurement, 2 when nothing was measurable."""
    import argparse
    import json

    parser = argparse.ArgumentParser(
        prog="uplift.regret",
        description=(
            "Measure (s, S)-class regret against the perfect-foresight comparator using the "
            "objective committed in digital_twin/simulation/policy.yaml. CI only."
        ),
    )
    parser.add_argument("--replicates", type=int, default=4)
    parser.add_argument("--hours", type=float, default=24.0)
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args(argv)

    report = _measure(int(args.replicates), float(args.hours))
    if args.as_json:
        print(json.dumps(report, sort_keys=True, separators=(",", ":"), default=str))
    else:
        for key, value in sorted(report.items()):
            print(f"{key}: {value}")
    return 0 if report.get("status") == "measured" else 2


if __name__ == "__main__":
    import sys

    sys.exit(main())
