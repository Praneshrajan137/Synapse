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
from typing import TYPE_CHECKING, Final, Literal

from digital_twin.simulation.policy import POLICY_PATH, PolicyUnavailableError, load_policy, require

if TYPE_CHECKING:  # annotation-only, so the fast property suite pays nothing for them
    from collections.abc import Mapping, Sequence

__all__ = [
    "ARM_LABELS",
    "JUDGED_CONTRAST",
    "OBJECTIVE_TERMS",
    "ORACLE_ARM",
    "InsensitiveKpi",
    "RegretObjective",
    "RegretVerdict",
    "TermContribution",
    "classify_regret",
    "hindsight_min",
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

#: The comparator's arm labels, in the order this module tables them (ADR-055 D2.5.1, D2.5.4).
#: Declared once so the per-arm counter totals, the cost decomposition and the
#: hindsight-minimum family cannot drift apart -- three places naming four arms by hand is how
#: an arm gets silently dropped from one of them.
ARM_LABELS: Final[tuple[str, ...]] = ("noop", "reference", "foresight", "hindsight")

#: Which of :data:`ARM_LABELS` supplies the oracle that `regret` and `comparator_headroom` are
#: computed against. It moved from ``foresight`` to ``hindsight`` in session 9, and it is named
#: here -- and reported in the artifact -- because a reader comparing this run with
#: ``34570166681`` or ``34590696403`` must be able to see WHICH arm those two keys are about
#: rather than infer it (ADR-055 D2.5.4).
ORACLE_ARM: Final[str] = "hindsight"

#: What ``regret`` is the difference OF, stated in the artifact's own key names. Reported rather
#: than left to be matched up, because the same key named a different subtraction in each of the
#: last two runs and a reader should not have to reconstruct which one from a prose field.
JUDGED_CONTRAST: Final[str] = "mean_reference_cost - mean_hindsight_cost"

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


def hindsight_min(arm_costs: Mapping[str, Sequence[float]]) -> list[float]:
    """The pointwise-minimum cost across a DECLARED family of arms, replicate by replicate.

    **What this buys, and it is the one guarantee arm C never had.** Regret is "how much better a
    policy could have done given perfect information", so it is bounded below by zero -- and run
    ``34570166681`` measured ``-0.8123524459522771`` because the arm it was subtracted from was
    not an optimum (ADR-055 D2.5.2, D2.5.3). A hindsight minimum over a family that **contains
    the subject** cannot have that defect: ``min_i <= subject_i`` at every replicate by
    construction, so the aggregated difference is non-negative for every finite input. The
    guarantee is a property of the **family**, not of the arithmetic -- over a family that
    excludes the subject the minimum can be strictly worse than the subject and the difference
    goes negative, which
    ``tests/uplift/test_hindsight_oracle_admissibility_property.py`` asserts rather than assumes
    so this docstring cannot be read as claiming more than it does.

    **Why it is not the comparator, and this matters.** A best-of-the-arms-we-ran floor is a
    *within-sample* bound: it can only ever be as good as the best arm present, so it would
    report zero regret against a family of bad policies and would rise if a worse arm were added.
    ``HindsightOraclePolicy`` is the comparator because it is optimal by construction over the
    world's own realised demand, independent of which arms happen to be in the run.
    ``_measure`` reports both, and the pair answers a question neither answers alone: whether the
    oracle arm was in fact the best arm at **every** replicate, which is the oracle claim's
    per-run falsifier.

    Args:
        arm_costs: One per-replicate cost sequence per arm name, all of equal length because the
            objective is paired on seeds (D2.4). Iterated in sorted name order so the result
            cannot depend on the caller's dict ordering.

    Returns:
        One cost per replicate: the least cost any declared arm achieved on that replicate.

    Raises:
        ValueError: On an empty family, on an arm with no replicates, or on ragged lengths.
            Refused rather than truncated to the shortest: an unpaired minimum is a different
            estimator over a different replicate set, exactly as
            :meth:`RegretObjective.regret` refuses an unpaired difference.
    """
    if not arm_costs:
        raise ValueError(
            "cannot take a hindsight minimum over an empty family of arms; the family is what "
            "supplies the guarantee, so an empty one guarantees nothing"
        )
    lengths = {name: len(costs) for name, costs in arm_costs.items()}
    if len(set(lengths.values())) != 1:
        raise ValueError(
            f"a hindsight minimum needs equal replicate counts, got {lengths!r}; an unpaired "
            "minimum is a different estimator over a different replicate set"
        )
    # Sorted by arm name so the result cannot depend on the caller's dict ordering. `min` is
    # order-invariant anyway; the sort makes that independence structural rather than incidental.
    ordered: list[Sequence[float]] = [arm_costs[name] for name in sorted(arm_costs)]
    paired = len(ordered[0])
    if paired == 0:
        raise ValueError(
            "every arm in the family reported zero replicates, so there is nothing to minimise; "
            "an empty result would be read as a measurement of nothing (I-7)"
        )
    return [min(costs[index] for costs in ordered) for index in range(paired)]


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

    **This refusal is RETAINED, not relaxed, now that the comparator has been repaired
    (D2.5.4).** Its red was the finding; with an oracle that attains the service terms' floor by
    construction it becomes a guard that can only fire on a bug -- a coverage hole in the
    hindsight arm, an arm pair that did not share a demand path, or an objective sign error.
    Removing it because the number is expected to be positive would delete the only thing that
    would say so if it were not.

    Args:
        regret: The measured judged contrast, ``mean_reference - mean_<oracle>``.
        mean_reference: Arm B's mean objective cost, named in the reason so the refusal is
            attributable without re-running anything.
        mean_foresight: The ORACLE arm's mean objective cost. **The parameter keeps this name
            although the oracle is arm D from session 9 on** (ADR-055 D2.5.4): it is passed by
            keyword from ``tests/uplift/test_regret_comparator_admissibility_property.py``, a
            landed property file, and renaming it would edit that file to no measurable end. The
            predicate below is unchanged -- only which arm's cost the caller supplies has moved.

    Returns:
        ``None`` when the comparator bounds the subject, so the regret may be classified.
        Otherwise a non-empty reason naming both arm costs and what the refusal does not claim.
    """
    if regret >= 0.0:
        return None
    return (
        f"measured regret {regret!r} is NEGATIVE: the (s, S) reference arm (mean objective "
        f"cost {mean_reference!r}) outperforms the ORACLE arm it is subtracted from "
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
# CI ONLY. The protocol runs FOUR arms per replicate, so it costs four twin replicates per
# seed -- +33% on the three-arm form, paid so one run reports both the retired and the current
# oracle (ADR-055 D2.5.4). A run at `MIN_SCENARIOS` scale is a category-4 workload under I-0
# that must never execute on a development machine. `--replicates` defaults small so an
# accidental local invocation is cheap and obvious rather than thermally expensive.


def _measure(replicates: int, hours: float) -> dict[str, object]:
    """Run the four-arm comparator over ``replicates`` seeds and report, without judging."""
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
    #: Arm D, the hindsight oracle -- the JUDGED comparator from session 9 (ADR-055 D2.5.4).
    hindsight_costs: list[float] = []
    unusable: list[int] = []

    # PER-TERM ACCUMULATORS, AND THE MACHINERY FOR THEM WAS ALWAYS THERE (finding 58).
    # `RegretObjective.contributions` has decomposed an observation into its five weighted
    # terms since task 9, and its own docstring says why: "a regret number whose composition
    # cannot be inspected is a number nobody can argue with -- and the whole point of
    # committing the weights was to make the composition arguable." `_measure` called
    # `cost()` and never `contributions()`, so every run this spec has ever taken reported a
    # scalar whose composition was unavailable. That is why finding 54's explanation had to
    # be left as a HYPOTHESIS: the number that would confirm or kill it was one call away.
    noop_terms: dict[str, list[float]] = {term: [] for term in OBJECTIVE_TERMS}
    reference_terms: dict[str, list[float]] = {term: [] for term in OBJECTIVE_TERMS}
    foresight_terms: dict[str, list[float]] = {term: [] for term in OBJECTIVE_TERMS}
    hindsight_terms: dict[str, list[float]] = {term: [] for term in OBJECTIVE_TERMS}
    #: Last replicate's counters per arm. Provenance for the complement identity, not an
    #: aggregate: the identity is structural, so one replicate exhibits it or none do.
    arm_counters: dict[str, dict[str, int]] = {}
    #: RUN-LEVEL counter totals per arm, and unlike `arm_counters` these MUST be aggregated.
    #: The hindsight arm's claim is that it leaves ZERO unmet demand by construction; one
    #: replicate exhibiting zero is not that claim, so the falsifier is summed over every
    #: usable replicate and reported as a boolean the reader does not have to derive.
    counter_totals: dict[str, dict[str, int]] = {
        arm: {
            "demand_events": 0,
            "unmet_demand_events": 0,
            "orders_created": 0,
            "orders_delivered": 0,
        }
        for arm in ARM_LABELS
    }

    def _observation(sim: object) -> dict[str, float]:
        """The five KPI arguments, read once so cost and contributions cannot diverge."""
        metrics = sim.metrics  # type: ignore[attr-defined]
        return {
            "stockout_rate": metrics.stockout_rate,
            "spoilage_rate": metrics.spoilage_rate,
            "fill_rate": metrics.fill_rate,
            "avg_on_hand_units": metrics.avg_on_hand_units(
                sim.sim_time_min  # type: ignore[attr-defined]
            ),
            "avg_delivery_time_min": metrics.avg_delivery_time_min,
        }

    def _counters(sim: object) -> dict[str, int]:
        """The two counters that decide whether the service terms are one quantity.

        Reported per arm so a reader can verify the complement identity from the artifact
        rather than trusting this module's word for it (finding 60).
        """
        metrics = sim.metrics  # type: ignore[attr-defined]
        return {
            "demand_events": int(metrics.demand_events),
            "unmet_demand_events": int(metrics.unmet_demand_events),
            "orders_created": int(metrics.orders_created),
            "orders_delivered": int(metrics.orders_delivered),
        }

    def _cost(sim: object) -> float:
        return objective.cost(**_observation(sim))

    def _accumulate(sim: object, into: dict[str, list[float]]) -> None:
        """Record each term's weighted contribution for this replicate."""
        for contribution in objective.contributions(**_observation(sim)):
            into[contribution.term].append(contribution.weighted)

    for seed in range(replicates):
        result = run_three_pass(
            seed,
            hours=hours,
            restock_threshold=threshold,
            reference_policy=Par_Level_Reorder(
                s=reference_spec.reorder_point, S=reference_spec.order_up_to, seed=seed
            ),
        )
        if not result.usable_for_judged_contrast:
            # A replicate whose arms saw different demand is not evidence, and neither is one
            # missing the oracle arm the judged contrast is computed against. Recorded and
            # excluded rather than silently averaged in (I-7).
            unusable.append(seed)
            continue
        hindsight_arm = result.hindsight
        # `usable_for_judged_contrast` already required arm D; this restates the clause so the
        # type checker can narrow the Optional, and it cannot fire on its own.
        if hindsight_arm is None:
            unusable.append(seed)
            continue
        noop_costs.append(_cost(result.noop))
        reference_costs.append(_cost(result.reference))
        foresight_costs.append(_cost(result.foresight))
        hindsight_costs.append(_cost(hindsight_arm))
        _accumulate(result.noop, noop_terms)
        _accumulate(result.reference, reference_terms)
        _accumulate(result.foresight, foresight_terms)
        _accumulate(hindsight_arm, hindsight_terms)
        arm_counters = {
            "noop": _counters(result.noop),
            "reference": _counters(result.reference),
            "foresight": _counters(result.foresight),
            "hindsight": _counters(hindsight_arm),
        }
        for arm, counts in arm_counters.items():
            for counter, value in counts.items():
                counter_totals[arm][counter] += value

    if not reference_costs:
        return {
            "status": "unavailable",
            "reason": (
                "no replicate produced usable evidence: every arm quadruple disagreed on the "
                "demand path, so nothing was measured"
            ),
            "unusable_seeds": unusable,
        }

    # THE JUDGED CONTRAST IS THE REFERENCE ARM AGAINST THE ORACLE, AND THE ORACLE IS ARM D
    # FROM SESSION 9 ON (ADR-055 D2.5.4). That is the `(s, S)` regret R5.1, Finding 4 and task
    # 11 are about; until session 5 it was not what this function computed (conflict M), and
    # until session 9 the arm it was computed against was not an oracle (findings 54, 59).
    #
    # `regret` AND `comparator_headroom` KEEP THEIR NAMES AND CHANGE WHICH ORACLE THEY NAME.
    # Both keep their FORM -- `mean_reference - mean_<oracle>` and `mean_noop - mean_<oracle>` --
    # and `oracle_arm` below states which arm that is, so no reader has to infer it. The two
    # quantities runs 34570166681 and 34590696403 reported under these names are retained under
    # `regret_vs_foresight` and `comparator_headroom_vs_foresight`, so nothing a reader wants to
    # compare across runs has to be recomputed and no key silently carries two meanings.
    measured = objective.regret(reference_costs, hindsight_costs)
    mean_noop = objective.aggregate(noop_costs)
    mean_reference = objective.aggregate(reference_costs)
    mean_foresight = objective.aggregate(foresight_costs)
    mean_hindsight = objective.aggregate(hindsight_costs)
    regret_vs_foresight = objective.regret(reference_costs, foresight_costs)
    # THE BOUND IS THE NO-OP ARM AGAINST THE ORACLE, AND ITS INDEPENDENCE IS THE WHOLE
    # POINT. `must_be_below_measured_headroom` exists to refuse a margin so large that
    # `material` is unreachable. While the comparator had two arms this was
    # `mean_baseline - mean_foresight` over the SAME pair `regret` was computed from -- the
    # identical subtraction -- so the guard admitted exactly the margins below the regret
    # they would be judged against, and every margin in D2.5's bracket forced `material`.
    # With three arms the bound became a different subtraction over a different pair, and
    # `headroom >= regret` holds because doing nothing cannot cost less than running the
    # incumbent. That inequality is asserted below rather than assumed.
    headroom = mean_noop - mean_hindsight
    headroom_vs_foresight = mean_noop - mean_foresight

    # THE WITHIN-SAMPLE FLOOR, AND WHY IT IS REPORTED BESIDE THE ORACLE RATHER THAN INSTEAD OF
    # IT. `hindsight_min` takes the least cost any declared arm achieved at each replicate, so
    # `mean_reference - mean(hindsight_min(family))` is non-negative for EVERY finite input
    # whenever the family contains the reference arm -- which this one does. That makes it a
    # sanity floor rather than a comparator: it can only ever be as good as the best arm
    # present, and it would report zero regret against a family of bad policies.
    #
    # What it buys is the oracle claim's PER-RUN FALSIFIER. If arm D is optimal by construction
    # it must be the pointwise minimum of the family at every replicate, so
    # `hindsight_arm_is_pointwise_best` is `True` -- and if it is `False`, some other arm beat
    # the arm this run's verdict is read against, on the run's own numbers, and D2.5.4's
    # construction argument has failed rather than merely looked wrong.
    arm_cost_family: dict[str, list[float]] = {
        "noop": noop_costs,
        "reference": reference_costs,
        "foresight": foresight_costs,
        "hindsight": hindsight_costs,
    }
    pointwise_best = hindsight_min(arm_cost_family)
    mean_pointwise_best = objective.aggregate(pointwise_best)
    regret_vs_pointwise_best = objective.regret(reference_costs, pointwise_best)
    # Exact equality, not a closeness test: `min` returns one of its arguments unchanged, so
    # the two lists are bit-identical when arm D is the minimum at every replicate.
    hindsight_is_pointwise_best = pointwise_best == hindsight_costs

    # THE PER-TERM ATTRIBUTION OF THE REGRET. This is finding 54's falsifier and it is the
    # reason this block exists (ADR-055 D2.5.2).
    #
    # `regret` is a scalar difference of two weighted sums over the same five terms, so it
    # decomposes EXACTLY into per-term differences: sum(regret_by_term) == regret, up to
    # floating-point association. That identity is what makes these numbers evidence rather
    # than commentary, and `tests/uplift/test_regret_decomposition_property.py` asserts it.
    #
    # What it decided: finding 54 recorded that the `(s, S)` arm outperforms the arm labelled
    # `perfect_foresight`, and offered ONE surviving hypothesis -- that `stockout_rate`, at
    # weight 8.0, counts SKUs at zero stock rather than unmet demand (ADR-055 D3), so a
    # just-in-time oracle is charged for being efficient while a par-level buffer is not. Run
    # 34590696403 measured it: direction right, mechanism wrong in one respect and doubled in
    # another (findings 59 and 60, ADR-055 D2.5.3). The decomposition is retained -- now over
    # the hindsight arm -- because it is the same falsifier for the repair: with arm D attaining
    # the service terms' floor, `regret_by_term["stockout_rate"]` and `["unmet_service"]` must
    # be non-negative, and `regret_by_term_vs_foresight` keeps the pre-repair attribution
    # visible in the same artifact so the effect of the repair is one subtraction away.
    def _term_means(accumulated: dict[str, list[float]]) -> dict[str, float]:
        return {
            term: objective.aggregate(values) if values else 0.0
            for term, values in accumulated.items()
        }

    noop_by_term = _term_means(noop_terms)
    reference_by_term = _term_means(reference_terms)
    foresight_by_term = _term_means(foresight_terms)
    hindsight_by_term = _term_means(hindsight_terms)
    regret_by_term = {
        term: reference_by_term[term] - hindsight_by_term[term] for term in OBJECTIVE_TERMS
    }
    regret_by_term_vs_foresight = {
        term: reference_by_term[term] - foresight_by_term[term] for term in OBJECTIVE_TERMS
    }
    headroom_by_term = {
        term: noop_by_term[term] - hindsight_by_term[term] for term in OBJECTIVE_TERMS
    }
    # Reported so a reader can see WHICH term dominates without sorting five numbers, and
    # named by magnitude rather than by sign so it is meaningful whichever way the regret goes.
    dominant_term = max(OBJECTIVE_TERMS, key=lambda term: abs(regret_by_term[term]))

    decomposition: dict[str, object] = {
        "mean_weighted_cost_by_term": {
            "noop": noop_by_term,
            "reference": reference_by_term,
            "foresight": foresight_by_term,
            "hindsight": hindsight_by_term,
        },
        "regret_by_term": regret_by_term,
        # The pre-repair attribution, under its own name. This is the column ADR-055 D2.5.3
        # tables, so a reader can confirm from ONE run that the repair moved the service terms
        # and left the others alone, instead of comparing two runs at two shas.
        "regret_by_term_vs_foresight": regret_by_term_vs_foresight,
        "headroom_by_term": headroom_by_term,
        "dominant_regret_term": dominant_term,
        "dominant_regret_share": (
            regret_by_term[dominant_term] / measured if measured != 0.0 else None
        ),
        # PROVENANCE FOR THE COMPLEMENT IDENTITY (finding 60). `stockout_rate` and
        # `unmet_service` are ONE quantity on this path, by construction rather than by
        # coincidence: `SimulationMetrics.fill_rate` is
        # `(demand_events - unmet_demand_events) / demand_events` and its own docstring calls
        # itself "the exact complement of stockout_rate", which is
        # `unmet_demand_events / demand_events`. So `1 - fill_rate == stockout_rate` over one
        # shared denominator, and both carry weight 8.0. These counters are reported so a
        # reader can re-derive that from the artifact instead of trusting this comment.
        "arm_counters": arm_counters,
        # RUN-LEVEL TOTALS, AND THE ORACLE'S FALSIFIER READ OFF THEM (ADR-055 D2.5.4).
        # `hindsight_attains_zero_unmet` is the whole construction argument reduced to one
        # boolean: arm D covers cumulative outstanding demand at every decision, so it can
        # only stock out if the coverage inequality was violated -- a coverage hole, an arm
        # pair that did not share a demand path, or a window shorter than the cadence. A
        # `False` here means D2.5.4's argument has FAILED, not that the number looks wrong.
        # `reference_attains_zero_unmet` is reported beside it because it is what makes the
        # service terms cancel: with both arms at zero unmet demand, `regret` is a pure
        # holding-plus-latency difference and the finding-60 double-count contributes exactly
        # nothing to the judged contrast.
        "arm_counters_total": counter_totals,
        "hindsight_attains_zero_unmet": counter_totals["hindsight"]["unmet_demand_events"] == 0,
        "reference_attains_zero_unmet": counter_totals["reference"]["unmet_demand_events"] == 0,
        "service_terms_are_one_quantity": all(
            math.isclose(
                by_term["stockout_rate"], by_term["unmet_service"], rel_tol=0.0, abs_tol=0.0
            )
            for by_term in (
                noop_by_term,
                reference_by_term,
                foresight_by_term,
                hindsight_by_term,
            )
        ),
        "note": (
            "regret_by_term sums to `regret` by construction (a difference of two weighted "
            "sums over the same terms), so these are the exact attribution of the judged "
            "contrast rather than a commentary on it. `regret_by_term` is now the reference "
            "arm against the HINDSIGHT arm (ADR-055 D2.5.4) and "
            "`regret_by_term_vs_foresight` is the pre-repair column D2.5.3 tables, so the "
            "effect of replacing the comparator is legible from one run: the two service "
            "terms should move from -0.6566 each to non-negative, and no other term should "
            "move for a reason this repair explains"
        ),
    }

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
            "mean_hindsight_cost": mean_hindsight,
            "oracle_arm": ORACLE_ARM,
        }

    # `alpha` is READ from the committed Metric_Contract; "95%" is `1 - alpha` and appears
    # nowhere as a literal (AD-13). The resample count is derived from that alpha.
    alpha = contract_alpha()
    resamples = resamples_for(alpha)
    try:
        # OVER THE JUDGED CONTRAST, not the bound. `material` requires the interval to
        # exclude the margin, so the interval must be about the same quantity the margin is
        # compared against -- the reference arm's regret against the ORACLE arm, which is arm D
        # from session 9 (ADR-055 D2.5.4). An interval over the no-op contrast would be
        # dispersion for a number nothing is judged on, and an interval over the retired
        # foresight contrast would be dispersion for a number nothing is judged on either.
        interval = paired_difference_interval(
            reference_costs,
            hindsight_costs,
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
            "mean_hindsight_cost": mean_hindsight,
            "oracle_arm": ORACLE_ARM,
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
            "mean_hindsight_cost": mean_hindsight,
            "oracle_arm": ORACLE_ARM,
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
        regret=measured, mean_reference=mean_reference, mean_foresight=mean_hindsight
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
            "mean_hindsight_cost": mean_hindsight,
            "oracle_arm": ORACLE_ARM,
            "judged_contrast": JUDGED_CONTRAST,
            "comparator_headroom": headroom,
            "comparator_headroom_vs_foresight": headroom_vs_foresight,
            "regret": measured,
            "regret_vs_foresight": regret_vs_foresight,
            "mean_hindsight_min_cost": mean_pointwise_best,
            "regret_vs_hindsight_min": regret_vs_pointwise_best,
            "hindsight_min_arms": sorted(arm_cost_family),
            "hindsight_arm_is_pointwise_best": hindsight_is_pointwise_best,
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
            # THE DECOMPOSITION IS REPORTED ON THE REFUSAL PATH TOO, and that is deliberate
            # rather than incidental: this is the payload a reader actually lands on today,
            # and it is the one where the question "which term inverted the sign?" is live.
            # A refusal that withholds the evidence for its own cause would be a worse
            # instrument than the one it replaced.
            "cost_decomposition": decomposition,
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
        # FOUR ARMS, FOUR MEANS. `mean_baseline_cost` was renamed to `mean_noop_cost` in
        # session 5 rather than kept and repurposed: it named the arm the regret was computed
        # FROM, and that arm was no longer the subject. A reader comparing this report with run
        # 34366766968's would otherwise read two different quantities under one key. Session 9
        # adds `mean_hindsight_cost` for arm D and CHANGES NEITHER of the other three.
        "mean_noop_cost": mean_noop,
        "mean_reference_cost": mean_reference,
        "mean_foresight_cost": mean_foresight,
        "mean_hindsight_cost": mean_hindsight,
        # WHICH ARM THE TWO SUBTRACTIONS BELOW ARE AGAINST. Reported rather than implied: the
        # oracle moved from arm C to arm D in session 9 (ADR-055 D2.5.4), so `regret` and
        # `comparator_headroom` keep their FORM and change which arm supplies the subtrahend.
        "oracle_arm": ORACLE_ARM,
        "judged_contrast": JUDGED_CONTRAST,
        # The BOUND: no-op against the oracle. Independent of `regret` by construction now.
        "comparator_headroom": headroom,
        # The JUDGED quantity: the committed (s, S) reference arm against the oracle.
        "regret": measured,
        # THE TWO PRE-REPAIR QUANTITIES, UNDER NAMES OF THEIR OWN. These are exactly what runs
        # 34570166681 and 34590696403 reported as `regret` and `comparator_headroom`, so both
        # remain comparable across runs without a reader recomputing anything -- and
        # `comparator_headroom_vs_foresight` is session 7's prediction-1 check: it must still
        # read 8.937888952967558, which is what proves adding arm D perturbed neither arm A nor
        # arm C, exactly as adding arm B perturbed neither.
        "regret_vs_foresight": regret_vs_foresight,
        "comparator_headroom_vs_foresight": headroom_vs_foresight,
        # THE WITHIN-SAMPLE FLOOR AND THE ORACLE CLAIM'S PER-RUN FALSIFIER. `hindsight_min`
        # takes the least cost any declared arm achieved at each replicate, so
        # `regret_vs_hindsight_min` is non-negative for every finite input (the family contains
        # the reference arm). `hindsight_arm_is_pointwise_best` is the load-bearing one: arm D
        # is optimal by construction, so it must BE that minimum at every replicate. `False`
        # means another arm beat the arm this verdict is read against, on this run's numbers.
        "mean_hindsight_min_cost": mean_pointwise_best,
        "regret_vs_hindsight_min": regret_vs_pointwise_best,
        "hindsight_min_arms": sorted(arm_cost_family),
        "hindsight_arm_is_pointwise_best": hindsight_is_pointwise_best,
        # Reported so a reader can see the two are no longer the same subtraction without
        # recomputing them. Under the two-arm comparator this was 0.0 by identity, which is
        # what conflict M was.
        "headroom_minus_regret": headroom - measured,
        # THE COMPOSITION OF THE JUDGED CONTRAST, per term. Reported beside the scalar
        # because `contributions()` has been able to produce it since task 9 and no run
        # ever asked (finding 58), which is why finding 54's cause had to be a hypothesis.
        "cost_decomposition": decomposition,
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
            "FOUR ARMS, and the ORACLE MOVED. regret = (s, S) reference - hindsight oracle, "
            "which is the quantity R5.1, Finding 4 and task 11 are about. comparator_headroom "
            "= no-op - hindsight oracle, retained as an INDEPENDENT bound so the margin guard "
            "`must_be_below_measured_headroom` is not checking the margin against the very "
            "quantity it judges. THE KEY MEANINGS THAT CHANGED, stated rather than left to be "
            "discovered: `regret` and `comparator_headroom` were computed against the "
            "perfect-foresight arm in runs 34570166681 and 34590696403, and are now computed "
            "against the hindsight arm; both prior quantities are reported under "
            "`regret_vs_foresight` and `comparator_headroom_vs_foresight`. The foresight arm "
            "is RETAINED and still measured, because two committed runs were judged against it "
            "and deleting it would make them unreadable. WHY the oracle moved: the foresight "
            "arm left 8.2% of demand unmet while the incumbent left none, so it did not bound "
            "its own subject (findings 54, 59); the hindsight arm covers cumulative outstanding "
            "demand and attains the service terms' floor by construction. Full argument, "
            "domain and falsifier in ADR-055 D2.5.4 -- not restated here. The reference arm is "
            "Par_Level_Reorder from uplift/baselines/, owned by decision-integrity-uplift-proof "
            "(its task 2.1) and LANDED -- four documents had recorded it as unlanded, which was "
            "conflict N. Its s and S are read from the twin's own restock threshold and opening "
            "stock; the claim that it REPRODUCES the twin's endogenous restock is not proven, "
            "because the mechanisms differ, and policy.yaml records that limit"
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
            "Measure (s, S)-class regret against the hindsight-oracle comparator using the "
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
