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
import math
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
    "negative_regret_refusal",
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


def negative_regret_refusal(
    *, regret: float, mean_reference: float, mean_foresight: float
) -> str | None:
    """Why a measured regret is inadmissible, or ``None`` when it may be classified.

    **The oracle must bound the subject, and until session 7 nothing in this tree said so**
    (ADR-055 D2.5.2). ``regret`` is "how much better a policy could have done given perfect
    information", which is bounded below by zero. A **negative** regret means the ``(s, S)``
    reference arm outperforms the arm labelled ``perfect_foresight``, so that arm is not an
    oracle and ``B - C`` is a difference between two ordinary policies rather than a regret.
    Run ``34570166681`` measured exactly that: ``regret = -0.8123524459522771`` with a 95%
    interval of ``[-0.8273, -0.7978]`` over 200 of 200 usable replicates, so the sign is not
    noise.

    **Why the sibling guard cannot see it**, which is why this is a separate clause rather than
    a strengthening of that one. ``_measure`` already refuses a run in which
    ``headroom >= regret`` fails, and substituting the definitions makes that
    ``(A - C) >= (B - C)``, which reduces to **``A >= B``** -- "doing nothing costs at least as
    much as the incumbent". True, and entirely silent about ``C``, because ``C`` cancels.
    **A guard built from two expressions that share a term cannot constrain that term.** The
    three-arm repair (conflict M) made ``regret`` and ``comparator_headroom`` different
    subtractions and left the oracle's own validity unasserted.

    **Why it refuses rather than classifying, which is the load-bearing half.** Handed to
    :func:`classify_regret` today, a negative regret returns ``inconclusive`` -- which reads as
    "regret below the margin" and would be recorded as task 11's verdict. Worse: once tasks
    12.3 and 13.3 land the two E2c sensitivity flips, the same negative number maps to
    ``sub-margin``, the **one** verdict that licenses reading the result as consistent with
    Finding 4. Conflict M's defect forced ``material``, which stops the spec loudly; this one
    would **confirm** the premise quietly, on a comparator that loses to its own subject. A
    false stop is recoverable; a false confirmation is the outcome this spec exists to prevent
    (I-7).

    **Zero is admissible.** A regret of exactly ``0.0`` means the incumbent matched the oracle,
    which is a legitimate measurement and the strongest possible support for Finding 4. The
    boundary is therefore strict on the negative side only, and
    ``tests/uplift/test_regret_comparator_admissibility_property.py`` asserts that rather than
    leaving it to the reader.

    Args:
        regret: The measured judged contrast, ``mean_reference - mean_foresight``.
        mean_reference: Arm B's mean objective cost, named in the reason so the refusal is
            attributable without re-running anything.
        mean_foresight: Arm C's mean objective cost.

    Returns:
        ``None`` when the comparator bounds the subject, so the regret may be classified.
        Otherwise a non-empty reason naming both arm costs and what the refusal does not claim.
    """
    if regret >= 0.0:
        return None
    return (
        f"measured regret {regret!r} is NEGATIVE: the (s, S) reference arm (mean objective "
        f"cost {mean_reference!r}) outperforms the perfect-foresight arm it is subtracted from "
        f"(mean objective cost {mean_foresight!r}), so that arm does not bound the subject and "
        "their difference is not a regret. No verdict is read from it (ADR-055 D2.5.2). This is "
        "refused rather than classified because the same number returns `inconclusive` today "
        "and `sub-margin` once the E2c sensitivity flips land, and `sub-margin` is the one "
        "verdict that licenses reading the result as consistent with Finding 4. The materiality "
        "margin was still read and accepted by its own guard before this refusal, so a run "
        "reaching here discharges task 10.4; it does not discharge task 11, and the repair is "
        "to the comparator rather than to the margin"
    )


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

    ``interval=None`` means the caller has no dispersion to offer, and ``material`` then rests
    on the point estimate alone. **That path is deliberately unreachable from the measurement
    CLI:** ``_measure`` estimates the interval (design E3.1) and reports ``unavailable`` when it
    cannot, precisely because ``material`` is the verdict that falsifies Finding 4 and stops
    this spec. The argument stays optional because this function is also exercised over
    generated inputs where no sample exists to resample, and because R5.3 -- unlike R5.13 --
    does not itself require an interval. **A new production caller that omits it reopens the
    hole**; supply the interval or report unavailable, never fall back.
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
        comparator_reference_policy,
        comparator_restock_threshold,
        materiality_margin,
        materiality_margin_rule,
    )
    from uplift.baselines.par_level_reorder import Par_Level_Reorder
    from uplift.foresight import run_three_pass
    from uplift.interval import (
        INTERVAL_SEED,
        IntervalUnavailableError,
        contract_alpha,
        paired_difference_interval,
        resamples_for,
    )

    objective = load_objective()
    threshold = comparator_restock_threshold()
    # THE REFERENCE ARM IS RESOLVED HERE, ONCE, FROM THE COMMITTED FILE (conflict M).
    # `comparator_reference_policy` refuses a missing key, an unimplemented policy name, a
    # non-integral level and a pair violating `0 <= s < S`, so an arm this run could not
    # justify never reaches the twin. The seed is the replicate seed, set per replicate
    # below: `Par_Level_Reorder` is deterministic and uses no randomness, but it holds a
    # seeded instance-local RNG under its R1.9 construction contract, so it is constructed
    # inside the loop rather than shared across replicates.
    reference_spec = comparator_reference_policy()

    noop_costs: list[float] = []
    reference_costs: list[float] = []
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
        result = run_three_pass(
            seed,
            hours=hours,
            restock_threshold=threshold,
            reference_policy=Par_Level_Reorder(
                s=reference_spec.reorder_point, S=reference_spec.order_up_to, seed=seed
            ),
        )
        if not result.usable:
            # A replicate whose arms saw different demand is not evidence. Recorded and
            # excluded rather than silently averaged in (I-7).
            unusable.append(seed)
            continue
        noop_costs.append(_cost(result.noop))
        reference_costs.append(_cost(result.reference))
        foresight_costs.append(_cost(result.foresight))

    if not reference_costs:
        return {
            "status": "unavailable",
            "reason": (
                "no replicate produced usable evidence: every arm triple disagreed on the "
                "demand path, so nothing was measured"
            ),
            "unusable_seeds": unusable,
        }

    # THE JUDGED CONTRAST IS THE REFERENCE ARM AGAINST THE ORACLE. That is the `(s, S)`
    # regret R5.1, Finding 4 and task 11 are about, and until session 5 it was not what this
    # function computed (conflict M).
    measured = objective.regret(reference_costs, foresight_costs)
    mean_noop = objective.aggregate(noop_costs)
    mean_reference = objective.aggregate(reference_costs)
    mean_foresight = objective.aggregate(foresight_costs)
    # THE BOUND IS THE NO-OP ARM AGAINST THE ORACLE, AND ITS INDEPENDENCE IS THE WHOLE
    # POINT. `must_be_below_measured_headroom` exists to refuse a margin so large that
    # `material` is unreachable. While the comparator had two arms this was
    # `mean_baseline - mean_foresight` over the SAME pair `regret` was computed from -- the
    # identical subtraction -- so the guard admitted exactly the margins below the regret
    # they would be judged against, and every margin in D2.5's bracket forced `material`.
    # With three arms the bound is a different subtraction over a different pair, and
    # `headroom >= regret` holds because doing nothing cannot cost less than running the
    # incumbent. That inequality is asserted below rather than assumed.
    headroom = mean_noop - mean_foresight

    # THE INTERVAL, AND WHY IT IS NOT OPTIONAL HERE (design E3.1, R6.13, R7.14).
    #
    # `classify_regret` reaches `material` on `regret >= margin` alone when `interval is None`,
    # and `material` is the verdict that FALSIFIES Finding 4 and stops this spec (R5.3, task
    # 11). Its own docstring, and `SESSION_PROTOCOL.md`'s checkpoint-A table, both define
    # `material` as the margin being at or below the regret WITH THE INTERVAL EXCLUDING IT.
    # Supplying the interval is what makes those two statements true of the run that decides.
    # R5.3 does not itself demand an interval -- R5.13 does, for the non-stationary twin -- so
    # this is a stricter standard than the criterion requires, adopted deliberately and
    # recorded rather than assumed.
    #
    # THE HEADROOM MUST BOUND THE REGRET, AND THAT IS NOW A CHECK RATHER THAN A DEFINITION.
    #
    # While the comparator had two arms this inequality was a tautology: `headroom` and
    # `regret` were the same subtraction, so `headroom >= regret` held trivially and proved
    # nothing. With three arms it is a real claim about the world -- doing nothing cannot cost
    # less than running the incumbent `(s, S)` policy -- and if it fails, the premise this
    # whole phase rests on has failed with it: either the reference arm is harming the twin,
    # or the arms were not run on the same world, or the objective's signs are wrong. Any of
    # those makes the margin guard meaningless again, so the run reports `unavailable` and
    # exits 2 rather than handing a verdict to a guard it has just invalidated (I-7).
    if headroom < measured:
        return {
            "status": "unavailable",
            "reason": (
                f"the no-op arm's headroom {headroom!r} is BELOW the measured (s, S) regret "
                f"{measured!r}, which cannot be true of a world where doing nothing is never "
                "better than running the incumbent. The margin guard bounds the margin "
                "against this headroom, so a headroom that does not bound the regret makes "
                "the guard meaningless and no verdict is admissible. Check the objective's "
                "signs, the reference arm, and whether the arms shared a demand path"
            ),
            "replicates_usable": len(reference_costs),
            "replicates_unusable": len(unusable),
            "unusable_seeds": unusable,
            "regret": measured,
            "comparator_headroom": headroom,
            "mean_noop_cost": mean_noop,
            "mean_reference_cost": mean_reference,
            "mean_foresight_cost": mean_foresight,
        }

    # `alpha` is READ from the committed Metric_Contract; "95%" is `1 - alpha` and appears
    # nowhere as a literal (AD-13). The resample count is derived from that alpha.
    alpha = contract_alpha()
    resamples = resamples_for(alpha)
    try:
        # OVER THE JUDGED CONTRAST, not the bound. `material` requires the interval to
        # exclude the margin, so the interval must be about the same quantity the margin is
        # compared against -- the reference arm's regret. An interval over the no-op contrast
        # would be dispersion for a number nothing is judged on.
        interval = paired_difference_interval(
            reference_costs,
            foresight_costs,
            alpha=alpha,
            resamples=resamples,
            seed=INTERVAL_SEED,
        )
    except IntervalUnavailableError as error:
        # A measurement whose dispersion could not be estimated is reported unavailable, and
        # `main` exits 2 on it, which fails the job. It is NOT downgraded to a point-estimate
        # verdict: falling back would restore exactly the hole this block closes, and would do
        # it silently on the one run whose verdict can end the spec (I-7).
        return {
            "status": "unavailable",
            "reason": (
                f"measured regret {measured:.6g} over {len(reference_costs)} usable replicate(s) "
                f"but no admissible interval could be estimated: {error}. The regret is "
                "reported and JUDGED BY NOTHING: `material` requires an interval excluding the "
                "margin, and a point estimate with no dispersion must not be read as one"
            ),
            "replicates_usable": len(reference_costs),
            "replicates_unusable": len(unusable),
            "unusable_seeds": unusable,
            "regret": measured,
            "comparator_headroom": headroom,
        }

    # The interval's own point estimate is PINNED against the objective's, not trusted to
    # agree with it (task 15.1's "`point` equals `headline_uplift` and is pinned against it,
    # not computed twice"). `fmean(a) - fmean(b)` and `fmean(a_i - b_i)` are the same quantity
    # by algebra and not necessarily the same float, so the comparison is a closeness test; a
    # real disagreement means the two sides are not measuring the same contrast, and that is
    # reported rather than averaged over.
    if not math.isclose(interval.point, measured, rel_tol=1e-9, abs_tol=1e-12):
        return {
            "status": "unavailable",
            "reason": (
                f"the interval's point estimate {interval.point!r} disagrees with the "
                f"objective's regret {measured!r}. These are the same contrast computed two "
                "ways, so a disagreement means the paired difference and the difference of "
                "means are not over the same replicate set. Nothing is judged on it"
            ),
            "replicates_usable": len(reference_costs),
            "replicates_unusable": len(unusable),
            "unusable_seeds": unusable,
            "regret": measured,
            "comparator_headroom": headroom,
            "interval_point": interval.point,
        }

    # `margin` is READ, not hardcoded. It is `None` until task 10.4 instantiates it, which
    # yields `unavailable` -- the honest verdict for the first run (R5.2). The RULE, however,
    # is required and is reported here, so checkpoint A's operator can see the value the rule
    # produces beside the measurement rather than choosing a number to suit it (ADR-055 D2.5).
    rule = materiality_margin_rule()
    margin = materiality_margin(measured_headroom=headroom)

    # THE ORACLE MUST BOUND THE SUBJECT, AND UNTIL SESSION 7 NOTHING SAID SO (ADR-055 D2.5.2).
    # The decision is `negative_regret_refusal`, a module-level pure function, so that the
    # refusal path is provable by construction rather than only by never firing: `_measure`
    # itself drives the SimPy twin and cannot be exercised in the fast suite (I-0).
    #
    # The margin is resolved ABOVE this guard on purpose. It is valid, it is re-derived from the
    # committed rule, and reporting it here is what lets checkpoint A discharge task 10.4 on
    # this run even though no verdict may be read from it. Two defects, two owners.
    inadmissible = negative_regret_refusal(
        regret=measured, mean_reference=mean_reference, mean_foresight=mean_foresight
    )
    if inadmissible is not None:
        return {
            "status": "unavailable",
            "reason": inadmissible,
            "replicates_usable": len(reference_costs),
            "replicates_unusable": len(unusable),
            "unusable_seeds": unusable,
            "hours_per_replicate": hours,
            "mean_noop_cost": mean_noop,
            "mean_reference_cost": mean_reference,
            "mean_foresight_cost": mean_foresight,
            "comparator_headroom": headroom,
            "regret": measured,
            "headroom_minus_regret": headroom - measured,
            "interval": interval.describe(),
            "interval_low": interval.low,
            "interval_high": interval.high,
            "interval_point": interval.point,
            "margin_committed": margin,
            "margin_rule": rule.describe(),
            "margin_rule_derives": rule.derived,
            "margin_rule_below_headroom": rule.derived < headroom,
            "insensitive_kpis": [item.term for item in objective.insensitive],
        }

    verdict = classify_regret(
        measured, objective=objective, margin=margin, interval=interval.bounds
    )
    return {
        "status": "measured",
        "replicates_usable": len(reference_costs),
        "replicates_unusable": len(unusable),
        "unusable_seeds": unusable,
        "hours_per_replicate": hours,
        "restock_threshold": threshold,
        "reference_policy": reference_spec.describe(),
        "reference_policy_name": reference_spec.name,
        "reference_reorder_point_s": reference_spec.reorder_point,
        "reference_order_up_to_S": reference_spec.order_up_to,
        # THREE ARMS, THREE MEANS. `mean_baseline_cost` was renamed to `mean_noop_cost`
        # rather than kept and repurposed: it named the arm the regret was computed FROM, and
        # that arm is no longer the subject. A reader comparing this report with run
        # 34366766968's would otherwise read two different quantities under one key.
        "mean_noop_cost": mean_noop,
        "mean_reference_cost": mean_reference,
        "mean_foresight_cost": mean_foresight,
        # The BOUND: no-op against the oracle. Independent of `regret` by construction now.
        "comparator_headroom": headroom,
        # The JUDGED quantity: the committed (s, S) reference arm against the oracle.
        "regret": measured,
        # Reported so a reader can see the two are no longer the same subtraction without
        # recomputing them. Under the two-arm comparator this was 0.0 by identity, which is
        # what conflict M was.
        "headroom_minus_regret": headroom - measured,
        "interval": interval.describe(),
        "interval_low": interval.low,
        "interval_high": interval.high,
        "interval_point": interval.point,
        "interval_alpha": interval.alpha,
        "interval_method": interval.method,
        "interval_resamples": interval.resamples,
        "interval_seed": interval.seed,
        "margin_committed": margin,
        "margin_rule": rule.describe(),
        "margin_rule_derives": rule.derived,
        "margin_rule_below_headroom": rule.derived < headroom,
        # Reported beside the verdict because it is the clause a reader most needs and the
        # verdict alone does not show: whether THIS interval would have licensed `material` at
        # the value the rule derives, independently of whether that value is committed yet.
        "interval_excludes_rule_margin": interval.excludes(rule.derived),
        "verdict": verdict.verdict,
        "reason": verdict.reason,
        "insensitive_kpis": [item.term for item in objective.insensitive],
        "comparator": (
            "THREE ARMS. regret = (s, S) reference - perfect foresight, which is the "
            "quantity R5.1, Finding 4 and task 11 are about. comparator_headroom = no-op - "
            "perfect foresight, retained as an INDEPENDENT bound so the margin guard "
            "`must_be_below_measured_headroom` is not checking the margin against the very "
            "quantity it judges. The reference arm is Par_Level_Reorder from "
            "uplift/baselines/, owned by decision-integrity-uplift-proof (its task 2.1) and "
            "LANDED -- four documents had recorded it as unlanded, which was conflict N. Its "
            "s and S are read from the twin's own restock threshold and opening stock; the "
            "claim that it REPRODUCES the twin's endogenous restock is not proven, because "
            "the mechanisms differ, and policy.yaml records that limit"
        ),
    }


def main(argv: list[str] | None = None) -> int:
    """Measure and report. Exit 0 on a completed measurement, 2 when nothing was measurable."""
    import argparse
    import json
    import logging
    import sys as _sys

    import structlog

    # THE ARTIFACT'S SHAPE IS THESE TWO LINES' RESPONSIBILITY, AND IT WAS FALSE WITHOUT THEM.
    #
    # `uplift.yml::twin-regret` runs `python -m uplift.regret --replicates 200 --hours 24
    # --json | tee artifacts/uplift/twin-regret.json`, and
    # `infrastructure/quality/blocking-steps.yaml` declares that step `role: producer` with
    # `emits: "artifacts/uplift/twin-regret.json (canonical JSON, --json)"`. Run
    # 34366766968 uploaded 215,293,577 bytes: the twin's `structlog` writes to stdout, so
    # `tee` captured a debug flood with the report on the final line and `json.load` raised
    # `JSONDecodeError: Extra data: line 1 column 5`. The declaration was FALSE AS WRITTEN,
    # and tasks 17.x, 22.3 and 25 read this artifact with a JSON parser. 90-day retention
    # on 215 MB per run is its own cost.
    #
    # TWO CONFIGURATIONS, AND THE SECOND IS THE ONE THAT MAKES THE CLAIM UNCONDITIONAL.
    #
    #   1. `wrapper_class` at `logging.ERROR` removes the VOLUME. That is the idiom five
    #      twin-driving modules under `digital_twin/tests/` already use, and it is what the
    #      215 MB was made of: `engine.py`'s `logger.debug("unmet_demand", ...)` and
    #      `logger.debug("delivery_done", ...)` once per event.
    #   2. `logger_factory` at **stderr** removes the CHANNEL. Without it, canonicality
    #      would hold only while nothing logged at ERROR or above -- a clause true by
    #      accident, which is the tolerated-exception disjunct the authoring rules forbid.
    #      A single `logger.error` on a bad replicate would have re-broken the artifact,
    #      and the next reader would have found a `JSONDecodeError` with no cause in sight.
    #
    # Together they cost nothing that was worth keeping. `| tee` reads stdout only, so
    # every log line and every traceback still lands in the job log via stderr -- the
    # visibility `set -o pipefail` was made safe for is preserved in full, and the
    # measurement's JSON stays the only thing on the pipe. An `--out` flag was the other
    # candidate repair and was rejected: it would give the artifact two sources of truth
    # and lose the JSON-in-the-log check a reader uses to tie artifact to run.
    #
    # CLI-ONLY, DELIBERATELY. `structlog.configure` is process-global and `regret.py` is
    # imported by the fast property suite, so configuring at module scope would silence
    # logging for every test that imports this module. Here it runs only under
    # `python -m uplift.regret`.
    structlog.configure(
        wrapper_class=structlog.make_filtering_bound_logger(logging.ERROR),
        logger_factory=structlog.PrintLoggerFactory(file=_sys.stderr),
    )

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
