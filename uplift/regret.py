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

from digital_twin.simulation.policy import (
    POLICY_PATH,
    ZEROED_PROVENANCE_PREFIX,
    PolicyUnavailableError,
    load_policy,
    refuse_inadmissible_weights,
    require,
)

if TYPE_CHECKING:  # annotation-only, so the fast property suite pays nothing for them
    from collections.abc import Callable, Mapping, Sequence

    from digital_twin.simulation.world import ResolvedWorld
    from uplift.tuned_static import GroupLevels

__all__ = [
    "ARM_LABELS",
    "JUDGED_CONTRAST",
    "OBJECTIVE_TERMS",
    "ORACLE_ARM",
    "ROOM_TO_WIN_RULE",
    "ZEROED_PROVENANCE_PREFIX",
    "InSampleRecheck",
    "InsensitiveKpi",
    "RegretObjective",
    "RegretVerdict",
    "RoomToWin",
    "TermContribution",
    "classify_regret",
    "decomposition_refusal",
    "hindsight_min",
    "in_sample_recheck",
    "negative_regret_refusal",
    "load_objective",
    "room_to_win",
    "room_to_win_out_of_sample",
    "split_refusal",
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

#: The comparator's arm labels, in the order this module tables them (ADR-055 D2.5.1, D2.5.4,
#: and D2.6 for arm E). Declared once so the per-arm counter totals, the cost decomposition and
#: the hindsight-minimum family cannot drift apart -- three places naming the arms by hand is
#: how an arm gets silently dropped from one of them. ``tuned_static`` is arm E, the tuned
#: static par-level control; ``structure_aware`` is arm O (task 13.7b), the structure-aware
#: base-stock arm -- the two values ``uplift/tuned_static.py::TUNED_STATIC_ARM`` and
#: ``uplift/oracle_arm.py::STRUCTURE_AWARE_ARM`` name, pinned equal by Property 96 rather than
#: imported, so this module's fast import closure stays light. APPEND-ONLY: never reordered.
#: ``ORACLE_ARM`` and ``JUDGED_CONTRAST`` below are UNCHANGED by either arrival, because both
#: are decomposition arms and never candidates for the judged contrast.
ARM_LABELS: Final[tuple[str, ...]] = (
    "noop",
    "reference",
    "foresight",
    "hindsight",
    "tuned_static",
    "structure_aware",
)

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

# `ZEROED_PROVENANCE_PREFIX` and the zero-weight admission rule it serves (finding 65) are DEFINED
# in `digital_twin/simulation/policy.py` and re-exported here through `__all__`, so every existing
# import keeps working while both readers of `regret_objective.weights` apply one rule.

Verdict = Literal["material", "sub-margin", "inconclusive", "unavailable"]

#: What one world cell's information ceiling licenses (task 13.7b; checkpoint B-prime, task 14).
RoomToWin = Literal["room_to_win", "no_room_to_win", "straddles", "unavailable"]

#: The rule :func:`room_to_win` implements, in words, reported beside every reading of it. W2b R1
#: made it two-sided in the bias: the out-of-sample ceiling is biased UP and the in-sample
#: recheck's DOWN, so ``room_to_win`` needs both and ``no_room_to_win`` reads the first alone.
ROOM_TO_WIN_RULE: Final[str] = (
    "room_to_win iff BOTH information-ceiling (E - D) intervals have their LOW bound strictly "
    "above the committed margin: the out-of-sample one (arm E tuned on seeds disjoint from the "
    "measurement's; biased UP) and the in-sample one (arm E re-chosen as the least mean, on the "
    "measurement seeds, of its ranked levels and the selection's unit neighbours; biased DOWN); "
    "no_room_to_win iff the out-of-sample interval's HIGH bound is strictly below the margin; "
    "straddles otherwise, so a closed interval containing the margin never licenses room; "
    "unavailable when the split is refused, the in-sample recheck is impossible, no margin was "
    "read, or a ceiling has no interval. room_to_win_out_of_sample applies the same strict "
    "bounds to the out-of-sample interval alone and binds nothing. Read per world cell from the "
    "two ceiling intervals alone; only world.primary_cell binds (task 14), and this artifact "
    "does not decide that"
)


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
        term a cost. On every measured path the engine makes ``1 - fill_rate`` and
        ``stockout_rate`` the same quantity (Property 64), which is why the committed objective
        weights ``stockout_rate`` at 0.0 (finding 65). Both terms stay in the decomposition, so
        every per-term report keeps all five entries.
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
    an assertion, and this phase exists to stop assertions standing in for evidence. And it
    refuses a zero weight that does not state why
    (:func:`digital_twin.simulation.policy.refuse_inadmissible_weights`, the rule's one home).
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
    refuse_inadmissible_weights(document, weights, source=str(path), terms=OBJECTIVE_TERMS)

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


def decomposition_refusal(
    *,
    search_refusal: str | None,
    tuning_gap: float,
    information_ceiling: float,
    usable_judged: int,
    usable_tuned: int,
) -> str | None:
    """Why the two-term split of the judged regret is inadmissible, or ``None`` when it holds.

    **What this does NOT do, stated first because it is the part most easily got wrong.** It does
    not touch ``status`` and it does not touch ``verdict``. ``status: measured`` certifies the
    JUDGED contrast -- arm B against arm D -- which is computed from arms that exist whether or
    not arm E behaved. Refusing a valid verdict because a subsidiary arm misbehaved would discard
    a real measurement, and I-7 cuts both ways: a fabricated pass and a discarded measurement are
    both misreports. So ``_measure`` reports ``decomposition_admissible`` and
    ``decomposition_refusal`` BESIDE the verdict and leaves the verdict alone.

    **Why a NEGATIVE tuning gap must be loud, and the direction is the whole reason.**
    ``regret = tuning_gap + information_ceiling`` by construction, so a tuning gap below zero
    makes ``information_ceiling`` LARGER than the regret it decomposes. The information ceiling
    is the denominator E3's hard gate reads, so an inflated ceiling makes that gate MORE
    PERMISSIVE -- the dangerous direction, in which a comparator that should have refused instead
    passes. It is also a real statement about the world when it fires: arm E's search starts at
    the incumbent's own levels and only accepts strict improvements, so its result over the
    tuning seeds cannot be worse than the incumbent THERE (``uplift/tuning.py`` asserts it), and
    a negative gap on the measurement seeds is unambiguously an out-of-sample effect rather than
    an artefact of a search that excluded its own comparison.

    **A refused search is the first clause, and before W2b it lived in only one of two places.**
    ``tune_group_levels`` reports a boundary or non-convergence refusal with the levels it
    reached, so arm E is then not certified the best static policy for this world: its tuning gap
    may be understated and its ceiling overstated -- the permissive direction above, reached with
    no sign flipping. :func:`split_refusal` refused on it and this did not, so a run could report
    ``decomposition_admissible: True`` over a search that had itself refused (R2).

    **A negative information ceiling means arm D is not an oracle**, which is
    :func:`negative_regret_refusal`'s subject reached by a different route: the best static policy
    beat the hindsight arm, so that arm does not bound the family and the second term is not EVPI.
    The repair is the comparator, not the split.

    **The count clause is the subtle one.** Both terms are differences of means, and the identity
    only telescopes when all three means are taken over the SAME replicates.
    ``usable_tuned != usable_judged`` means the split is over a different denominator from the
    number it decomposes, so the two terms sum to something that is not the regret and the
    residual would be non-zero for a reason that has nothing to do with floating point. Refused
    rather than averaged, exactly as :meth:`RegretObjective.regret` refuses an unpaired difference.

    Args:
        search_refusal: ``GroupTunedSelection.refusal`` -- boundary or non-convergence -- or
            ``None`` when the search certified the levels it returned.
        tuning_gap: ``mean_reference - mean_tuned_static`` over the measurement seeds. May be
            ``nan`` when arm E has no admissible mean over that set; ``nan`` fails both sign
            clauses, so the count clause is what refuses that case -- which is correct, because an
            undefined term is a denominator problem and not a sign problem.
        information_ceiling: ``mean_tuned_static - mean_hindsight`` over the same seeds.
        usable_judged: Replicates that contributed to ``regret``.
        usable_tuned: Replicates that contributed to arm E.

    Returns:
        ``None`` when the split may be read. Otherwise a non-empty reason naming the offending
        quantity, its direction, and what it does and does not imply.
    """
    if search_refusal is not None:
        return (
            f"arm E's search refused ({search_refusal}), so arm E is not certified as the best "
            "static policy for this world: its tuning gap may be UNDERSTATED and its information "
            "ceiling OVERSTATED -- the permissive direction for E3's denominator. The split is "
            "reported, not read, and the JUDGED contrast is unaffected"
        )
    if tuning_gap < 0.0:
        return (
            f"tuning gap {tuning_gap!r} is NEGATIVE: the tuned static control (arm E) cost MORE "
            "than the incumbent (s, S) reference arm on the measurement seeds, so the split "
            "reports an information ceiling LARGER than the regret it decomposes. That is the "
            "PERMISSIVE direction for E3's denominator -- an inflated ceiling makes the gate "
            "that reads it easier to pass -- which is why this refuses rather than reports. The "
            "search starts at the incumbent's own levels and never ends worse than them on the "
            "tuning seeds, so this is an out-of-sample effect and not a search that excluded its "
            "comparison; the repair is the search, and the JUDGED contrast is unaffected"
        )
    if information_ceiling < 0.0:
        return (
            f"information ceiling {information_ceiling!r} is NEGATIVE: the tuned static control "
            "beat the hindsight arm, so that arm does not bound the best STATIC policy and the "
            "second term is not EVPI. This is `negative_regret_refusal`'s subject reached by "
            "another route, and the repair is the comparator rather than the decomposition"
        )
    if usable_tuned != usable_judged:
        return (
            f"the split is over {usable_tuned} replicate(s) while the judged regret is over "
            f"{usable_judged}: the two terms are differences of means over DIFFERENT replicate "
            "sets, so they do not telescope to the regret and their residual would be non-zero "
            "for a reason unrelated to floating point. Refused rather than silently averaged "
            "(I-7). A `nan` term reaches this clause too, because an arm with no admissible "
            "mean over the judged set is a denominator defect and not a sign defect"
        )
    return None


def split_refusal(
    *,
    search_refusal: str | None,
    usable: Mapping[str, int],
    decomposition: str | None,
    residual_information_value: float,
) -> str | None:
    """Why ``B - D = (B - E) + (E - O) + (O - D)`` may not be read, or ``None`` when it may.

    Task 13.7b. Like :func:`decomposition_refusal` it touches neither ``status`` nor ``verdict``:
    ``_measure`` reports ``split_admissible`` and ``split_refusal`` BESIDE the judged A-D verdict
    and never instead of it. Every clause refuses in the SAFE direction -- an understated ceiling
    is a recoverable false stop, an overstated one a false confirmation -- so each names how the
    ceiling ``E - D`` could otherwise be overstated or meaningless.

    Clauses, first match wins: arm E's search refused, so E is not certified the best static
    policy for this world; the arms' usable replicate counts differ, so the terms do not
    telescope; the two-term decomposition this split refines is inadmissible (a negative tuning
    gap or ceiling, or no interval on the tuning gap); ``O - D`` is not finite, or is negative --
    hindsight does not bound the structure-aware arm, so D is not an oracle in this world.

    Args:
        search_refusal: ``GroupTunedSelection.refusal`` -- boundary or non-convergence.
        usable: Usable replicates per split arm; all must be equal, and at least one is named.
        decomposition: :func:`decomposition_refusal`'s reason, or ``None``.
        residual_information_value: ``mean_O - mean_D`` over the judged replicates.
    """
    if search_refusal is not None:
        return (
            f"arm E's search refused ({search_refusal}), so arm E is not certified as the best "
            "static policy for this world and the information ceiling E - D it bounds may be "
            "OVERSTATED -- the false-confirmation direction. The split is reported, not read"
        )
    if len(set(usable.values())) != 1:
        return (
            f"the split's arms were measured over different replicate counts "
            f"({dict(sorted(usable.items()))!r}), so its terms are differences of means over "
            "different replicate sets and do not telescope to the regret (I-7)"
        )
    if decomposition is not None:
        return f"the two-term decomposition this split refines is inadmissible: {decomposition}"
    if not math.isfinite(residual_information_value):
        return (
            f"residual information value {residual_information_value!r} is not finite, so the "
            "split has no defined third term and nothing is read from it"
        )
    if residual_information_value < 0.0:
        return (
            f"residual information value {residual_information_value!r} is NEGATIVE: hindsight "
            "does not bound the structure-aware arm: D is not an oracle in this world, so "
            "E - D is not EVPI and the room-to-win reading it would license is refused. The "
            "repair is the comparator, not the split"
        )
    return None


def _ceiling_reading(interval: tuple[float, float], margin: float, *, which: str) -> RoomToWin:
    """One ceiling interval against the margin, strict on both sides as ``Interval.excludes`` is.

    An interval whose endpoint sits exactly on the margin CONTAINS it, so it straddles and
    licenses nothing.

    Raises:
        ValueError: On a non-finite bound or margin, or ``low > high`` -- an interval no
            estimator produced, refused rather than read.
    """
    low, high = interval
    if not (math.isfinite(low) and math.isfinite(high) and math.isfinite(margin)) or low > high:
        raise ValueError(
            f"room_to_win needs finite low <= high and a finite margin, got {which} interval "
            f"[{low!r}, {high!r}] and margin {margin!r}"
        )
    if low > margin:
        return "room_to_win"
    if high < margin:
        return "no_room_to_win"
    return "straddles"


def room_to_win_out_of_sample(
    ceiling_interval: tuple[float, float] | None,
    *,
    margin: float | None,
    split_admissible: bool,
) -> RoomToWin:
    """The OUT-OF-SAMPLE ceiling interval's reading alone -- reported, and binding nothing.

    It was the binding reading until W2b R1. Arm E is the least of noisy TUNING means, so on the
    measurement seeds its expected cost exceeds the best static policy's and this interval is
    biased UP: alone, it can license a false room to win. :func:`room_to_win` binds instead.

    Raises:
        ValueError: On a non-finite bound or margin, or ``low > high``.
    """
    if not split_admissible or margin is None or ceiling_interval is None:
        return "unavailable"
    return _ceiling_reading(ceiling_interval, margin, which="out-of-sample ceiling")


def room_to_win(
    *,
    out_of_sample_ceiling: tuple[float, float] | None,
    in_sample_ceiling: tuple[float, float] | None,
    margin: float | None,
    split_admissible: bool,
) -> RoomToWin:
    """Checkpoint B-prime's BINDING reading of one cell, from its two ceiling intervals alone.

    :data:`ROOM_TO_WIN_RULE` states the rule. ``room_to_win`` needs BOTH intervals strictly above
    the margin -- the out-of-sample one is biased UP and the in-sample recheck's DOWN
    (:func:`in_sample_recheck`), so a reading that survives both survives the bias either way.
    ``no_room_to_win`` reads the out-of-sample interval alone, because an upward-biased interval
    wholly below the margin is the firmest stop there is; anything else straddles. Given both
    intervals, the recheck can only turn room into a straddle: it never grants room and never
    stops. Keyword-only, so the two intervals cannot be swapped by position, and no other term
    of the split can reach the reading.

    Raises:
        ValueError: On a non-finite bound or margin, or ``low > high``, in either interval.
    """
    if (
        not split_admissible
        or margin is None
        or out_of_sample_ceiling is None
        or in_sample_ceiling is None
    ):
        return "unavailable"
    out_of_sample = _ceiling_reading(out_of_sample_ceiling, margin, which="out-of-sample ceiling")
    in_sample = _ceiling_reading(in_sample_ceiling, margin, which="in-sample ceiling")
    if out_of_sample == "no_room_to_win":
        return "no_room_to_win"
    if out_of_sample == "room_to_win" and in_sample == "room_to_win":
        return "room_to_win"
    return "straddles"


@dataclasses.dataclass(frozen=True)
class InSampleRecheck:
    """Arm E re-chosen IN SAMPLE, on the measurement seeds (W2b R1): :func:`in_sample_recheck`."""

    #: K, deduplicated, in pricing order -- which is also the tie-break order.
    members: tuple[GroupLevels, ...]
    #: Each member's mean cost over the seeds, in ``members`` order.
    mean_costs: tuple[float, ...]
    #: E_in: the FIRST member holding the least mean cost.
    levels: GroupLevels
    #: E_in's per-seed costs, in the order the seeds were given, so they pair with every arm's.
    costs: tuple[float, ...]
    mean_cost: float
    #: The selection's per-seed costs, for the reproduction check; ``None`` exactly when the
    #: selection is not a member of K, which only a refused search can cause.
    selection_costs: tuple[float, ...] | None


def in_sample_recheck(
    *,
    selection: GroupLevels,
    ranked: Sequence[tuple[GroupLevels, float]],
    neighbours_of_selection: Sequence[GroupLevels],
    seeds: Sequence[int],
    cost_of: Callable[[int, GroupLevels], float],
    aggregate: Callable[[list[float]], float],
) -> InSampleRecheck:
    """The least mean of K on the measurement seeds: checkpoint B-prime's conservative arm E.

    W2b R1. K is every level vector of ``ranked`` (the search's cheapest, in its order), then
    ``neighbours_of_selection``, deduplicated keeping the first occurrence. Every member is priced
    at EVERY seed, in the order given, by the injected ``cost_of``; E_in is the member with the
    least ``aggregate``, and a tie keeps the EARLIER member. A converged search heads ``ranked``
    with its selection, so the selection is then K's first member and wins every tie it is party
    to -- the search's own rule that a tie keeps the incumbent-side point -- and
    ``mean_cost <= aggregate(selection_costs)`` holds by construction whenever the selection is
    in K.

    **Biased DOWN, and over what.** E_in is a least of noisy means over the very seeds it is
    reported on, and ``E[min] <= min E``, so its mean is biased DOWN relative to K's best member
    and so is any ceiling taken from it -- the opposite of arm E's own bias. It bounds nothing
    outside K.

    Raises:
        ValueError: On no seed, no candidate, or a non-finite cost: a least mean over any of
            them is not a least mean over the measurement seeds.
    """
    ordered = tuple(seeds)
    if not ordered:
        raise ValueError("the in-sample recheck was given no seed, so it would measure nothing")
    members = tuple(dict.fromkeys((*(levels for levels, _ in ranked), *neighbours_of_selection)))
    if not members:
        raise ValueError("the in-sample recheck was given no candidate, so it chooses nothing")
    priced: list[tuple[float, ...]] = []
    for member in members:
        costs = tuple(cost_of(seed, member) for seed in ordered)
        for seed, cost in zip(ordered, costs, strict=True):
            if not math.isfinite(cost):
                raise ValueError(
                    f"levels {member.as_dict()} cost {cost!r} at seed {seed}, and a least mean "
                    "over a non-finite cost is not a least mean"
                )
        priced.append(costs)
    means = tuple(aggregate(list(costs)) for costs in priced)
    best = 0
    for index, mean in enumerate(means):
        # Strict: a tie keeps the earlier member, so the selection wins every tie it is party to.
        if mean < means[best]:
            best = index
    return InSampleRecheck(
        members=members,
        mean_costs=means,
        levels=members[best],
        costs=priced[best],
        mean_cost=means[best],
        selection_costs=priced[members.index(selection)] if selection in members else None,
    )


def _world_summary(world: ResolvedWorld | None) -> dict[str, object] | None:
    """The structures this artifact's arms ran, READ from the resolved cell (task 13.7b).

    A cell NAME alone would make the artifact's meaning depend on the policy file at read time;
    the resolved values make it self-describing. ``None`` for the world before structures 1, 3.
    """
    if world is None:
        return None
    demand = world.demand
    supply = world.supply
    demand_summary: dict[str, object] | None = None
    if demand is not None:
        demand_summary = {
            "hourly": list(demand.hourly),
            "weekday": list(demand.weekday),
            "promotions": [
                {
                    "weekday": promotion.weekday,
                    "start_hour": promotion.start_hour,
                    "hours": promotion.hours,
                    "multiplier": promotion.multiplier,
                }
                for promotion in demand.promotions
            ],
        }
    supply_summary: dict[str, object] | None = None
    if supply is not None:
        supply_summary = {
            "suppliers": {
                name: {"mean_lead_time_min": spec.mean_lead_time_min, "log_sd": spec.log_sd}
                for name, spec in sorted(supply.suppliers.items())
            },
            "sku_supplier": dict(sorted(supply.sku_supplier.items())),
            "daily_autocorrelation": supply.daily_autocorrelation,
            "demand_coupling": supply.demand_coupling,
            "coupling_floor": supply.coupling_floor,
            "min_lead_time_min": supply.min_lead_time_min,
        }
    return {
        "cell": world.cell,
        "structure_1_on": world.structure_1_on,
        "structure_3_on": world.structure_3_on,
        "demand": demand_summary,
        "supply": supply_summary,
    }


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
# CI ONLY. The protocol runs SIX arms per replicate, so it costs six twin replicates per seed --
# +33% on the three-arm form for arm D, paid so one run reports both the retired and the current
# oracle (ADR-055 D2.5.4), +25% for arm E (D2.6) and +20% for arm O (task 13.7b), paid so the
# artifact reports the three terms the judged regret splits into rather than only their sum. Arm
# E also adds a SEARCH ahead of the measurement loop, re-derived per world cell: its evaluation
# count times the tuning seeds, in single-arm replicates, which `comparator-tuning.yaml`'s
# `budget` block projects -- and an IN-SAMPLE RECHECK after the loop (W2b R1): one single-arm
# replicate per recheck candidate per judged seed. That projection is READ there, not restated
# here; every artifact reports `measure_seconds` (the recheck's share apart, as
# `in_sample_recheck_seconds`), so the next sizing reads a measurement instead. A run at
# `MIN_SCENARIOS` scale is a category-4 workload under I-0 that must never execute on a
# development machine. `--replicates` defaults small so an accidental local invocation is cheap
# and obvious rather than thermally expensive.


def _measure(
    replicates: int,
    hours: float,
    cell: str | None,
    *,
    candidates: Mapping[str, Sequence[int]] | None = None,
    tuning_seeds: Sequence[int] | None = None,
) -> dict[str, object]:
    """Run the six-arm comparator in one world cell over ``replicates`` seeds, without judging.

    ``cell`` names a ``world.cells`` entry of the committed policy file and is resolved here,
    through ``load_world().resolve(cell)``; ``None`` runs the world before structures 1 and 3.
    Every artifact shape returned names ``cell``, ``primary_cell`` and the resolved ``world``, and
    reports ``measure_seconds`` (wall clock of this call), so a refusal is attributable to its
    cell and the next sizing reads a measurement.

    After the measurement loop arm E is re-chosen IN SAMPLE (:func:`in_sample_recheck`, W2b R1),
    and ``room_to_win`` binds on that ceiling as well as on the out-of-sample one.

    ``candidates`` and ``tuning_seeds`` are TEST SEAMS that shrink arm E's search so a slow
    property can drive this whole path in seconds. The CLI never passes them; ``None`` means the
    committed candidate rule and the committed tuning seeds, and an artifact built with either
    says so (``tuned_static_candidates_injected``, ``tuning_seeds_injected``).
    """
    import time

    started = time.perf_counter()
    provenance: dict[str, object] = {"cell": cell, "primary_cell": False, "world": None}

    def _finish(report: dict[str, object]) -> dict[str, object]:
        """Every artifact names its world cell and its own cost, whichever path produced it."""
        return {**report, **provenance, "measure_seconds": time.perf_counter() - started}

    # Imported here, not at module scope: `regret.py` is imported by the fast property suite,
    # and pulling the engine in at import time would drag SimPy into every one of those runs.
    from digital_twin.config import TwinConfig
    from digital_twin.simulation.policy import (
        comparator_reference_policy,
        comparator_restock_threshold,
        materiality_margin,
        materiality_margin_rule,
    )
    from digital_twin.simulation.world import load_world
    from uplift.baselines.par_level_reorder import Par_Level_Reorder
    from uplift.foresight import run_single_arm, run_three_pass, stocked_skus
    from uplift.interval import (
        INTERVAL_SEED,
        IntervalUnavailableError,
        contract_alpha,
        paired_difference_interval,
        resamples_for,
    )
    from uplift.tuned_static import GroupParLevelReorder, sku_groups
    from uplift.tuning import (
        GridPoint,
        TuningUnavailableError,
        decomposition_identity_residual,
        derive_candidates,
        load_tuning_spec,
        neighbours,
        seed_overlap_refusal,
        three_term_split,
        tune_group_levels,
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

    # THE WORLD CELL, RESOLVED ONCE, AND ITS CATALOGUE READ ONCE (task 13.7b). Every arm and the
    # tuner run `resolved`, and the artifact records the RESOLVED structures rather than only the
    # cell's name. A cell that cannot be resolved, or a world whose engine refuses to stock its
    # catalogue, is reported unavailable -- never measured in a different world instead.
    resolved: ResolvedWorld | None = None
    try:
        if cell is not None:
            world_spec = load_world()
            resolved = world_spec.resolve(cell)
            provenance["primary_cell"] = cell == world_spec.primary_cell
            provenance["world"] = _world_summary(resolved)
        # The catalogue is the engine's `start()` literal and depends on no seed; 0 is simply
        # the first measurement seed, so the probe is as reproducible as every arm's engine.
        skus = stocked_skus(0, world=resolved)
    except (PolicyUnavailableError, ValueError) as error:
        return _finish(
            {
                "status": "unavailable",
                "reason": (
                    f"world cell {cell!r} could not be resolved or stocked: {error}. Nothing is "
                    "measured in a world other than the one the artifact names"
                ),
                "unusable_seeds": [],
            }
        )
    #: Arm E's groups: one per supplier when structure 3 is on, otherwise one for every SKU.
    groups_by_sku = sku_groups(resolved, skus)
    groups = sorted(set(groups_by_sku.values()))

    noop_costs: list[float] = []
    reference_costs: list[float] = []
    foresight_costs: list[float] = []
    #: Arm D, the hindsight oracle -- the JUDGED comparator from session 9 (ADR-055 D2.5.4).
    hindsight_costs: list[float] = []
    #: Arm E, the tuned static par-level control (ADR-055 D2.6). Gated on its OWN predicate, so
    #: this list can be shorter than the four above -- and if it is, the decomposition is
    #: inadmissible rather than reported over a different denominator (see below).
    tuned_static_costs: list[float] = []
    #: Arm O, the structure-aware base-stock arm (task 13.7b). Built in every replicate.
    structure_aware_costs: list[float] = []
    #: Arm D's delayed-world falsifier: no arm leaves less demand unmet at any replicate.
    hindsight_unmet_least = True
    unusable: list[int] = []
    #: The seeds `reference_costs` and `hindsight_costs` are over, in order: what the in-sample
    #: recheck prices its candidates at, so its costs pair with arm D's seed for seed.
    judged_seeds: list[int] = []

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
    tuned_static_terms: dict[str, list[float]] = {term: [] for term in OBJECTIVE_TERMS}
    structure_aware_terms: dict[str, list[float]] = {term: [] for term in OBJECTIVE_TERMS}
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

    # THE TUNING PASS, AND IT RUNS BEFORE THE MEASUREMENT LOOP BECAUSE ARM E NEEDS ITS LEVELS
    # BEFORE ANY REPLICATE IS BUILT (ADR-055 D2.6, finding 61). From task 13.7b it is RE-DERIVED
    # PER WORLD CELL: one (s, S) per supplier group, candidates derived by the committed rule from
    # lead-time-plus-review demand in THIS world, searched from the incumbent's own levels.
    #
    # IT CANNOT PERTURB ARMS A-D, and that is a construction fact rather than a hope. Every
    # candidate is evaluated by `run_single_arm`, which builds its OWN `SupplyChainSimulation`
    # from `SeedSequence(seed)` at a seed in the committed tuning range, disjoint from
    # `range(replicates)` by `seed_overlap_refusal`. An arm's realisation is a function of its
    # own seed and its own actions only, so the numbers three sessions have confirmed to sixteen
    # significant figures do not move; `comparator_headroom_vs_foresight` must still read
    # 8.937888952967558 at the committed configuration and that is the check, not this comment.
    #
    # `cost_of` IS INJECTED SO THERE IS EXACTLY ONE PLACE THAT DECIDES AN ARM'S PHYSICS.
    # `run_single_arm` and `run_three_pass` both build through `_new_arm_engine` and drive
    # through `_drive_arm`, so the levels are SELECTED under the same world, cadence, unit costs
    # and restock threshold they are then MEASURED under. The in-sample recheck below prices its
    # candidates through this same function, on the measurement seeds.
    def _static_arm_cost(seed: int, levels: GroupLevels) -> float:
        return _cost(
            run_single_arm(
                seed,
                hours=hours,
                restock_threshold=threshold,
                policy=GroupParLevelReorder(levels, groups_by_sku, seed=seed),
                world=resolved,
            )
        )

    def _no_search(reason: str) -> dict[str, object]:
        # REFUSED, NOT DEFAULTED, AND THE MEASUREMENT IS NOT ATTEMPTED. The search is a
        # PRECONDITION of the decomposition: arm E's entire claim is that its levels were
        # DERIVED by a pre-registered rule rather than chosen, so falling back to any other
        # levels -- the incumbent's, a midpoint, a hardcoded pair -- would put an arm nobody
        # registered into the split and report an information ceiling with no search behind it.
        return _finish(
            {
                "status": "unavailable",
                "reason": (
                    f"arm E's levels could not be derived for this world: {reason}. The search "
                    "is a precondition of the decomposition, and levels nobody pre-registered "
                    "would make the information ceiling unfalsifiable, so no measurement is "
                    "attempted rather than one being reported on defaulted levels"
                ),
                "unusable_seeds": unusable,
            }
        )

    try:
        spec = load_tuning_spec()
    except TuningUnavailableError as error:
        return _no_search(str(error))
    seeds = tuple(spec.seeds) if tuning_seeds is None else tuple(tuning_seeds)
    # `seed_overlap_refusal` stays ENFORCED against the actual replicate count, on the committed
    # range; injected seeds are held to the same disjointness rather than exempted from it.
    overlap = seed_overlap_refusal(spec, measurement_replicates=replicates)
    if overlap is None and not seeds:
        overlap = "no tuning seeds were given, so the search has nothing to average over"
    if overlap is None and not set(seeds).isdisjoint(range(replicates)):
        overlap = (
            f"tuning seeds {sorted(set(seeds) & set(range(replicates)))} overlap the "
            f"measurement seeds 0..{replicates - 1}; in-sample tuning would bias the "
            "decomposition toward the tuning gap and away from the information ceiling"
        )
    if overlap is not None:
        return _no_search(overlap)
    try:
        searched: Mapping[str, Sequence[int]]
        if candidates is None:
            searched = derive_candidates(
                resolved,
                groups,
                spec.rule,
                rate_per_sku_per_min=TwinConfig().order_arrival_rate / len(skus),
            )
        elif sorted(candidates) != groups:
            raise TuningUnavailableError(
                f"injected candidates name groups {sorted(candidates)} but this world's are "
                f"{groups}; a search over groups the world does not have measures nothing"
            )
        else:
            searched = candidates
        selection = tune_group_levels(
            groups=groups,
            candidates=searched,
            incumbent=GridPoint(s=reference_spec.reorder_point, S=reference_spec.order_up_to),
            seeds=seeds,
            cost_of=_static_arm_cost,
            rule=spec.rule,
        )
    except TuningUnavailableError as error:
        return _no_search(str(error))

    for seed in range(replicates):
        result = run_three_pass(
            seed,
            hours=hours,
            restock_threshold=threshold,
            reference_policy=Par_Level_Reorder(
                s=reference_spec.reorder_point, S=reference_spec.order_up_to, seed=seed
            ),
            # ARM E is `uplift/tuned_static.py`'s per-supplier-group par-level rule, with levels
            # the search above DERIVED in this world cell; arm B's are READ from the engine's own
            # defaults. Constructed inside the loop for arm B's reason: each takes the replicate
            # seed under the R1.9 construction contract.
            tuned_static_policy=GroupParLevelReorder(selection.levels, groups_by_sku, seed=seed),
            world=resolved,
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
        judged_seeds.append(seed)
        noop_costs.append(_cost(result.noop))
        reference_costs.append(_cost(result.reference))
        foresight_costs.append(_cost(result.foresight))
        hindsight_costs.append(_cost(hindsight_arm))
        structure_aware_costs.append(_cost(result.structure_aware))
        _accumulate(result.noop, noop_terms)
        _accumulate(result.reference, reference_terms)
        _accumulate(result.foresight, foresight_terms)
        _accumulate(hindsight_arm, hindsight_terms)
        _accumulate(result.structure_aware, structure_aware_terms)
        arm_counters = {
            "noop": _counters(result.noop),
            "reference": _counters(result.reference),
            "foresight": _counters(result.foresight),
            "hindsight": _counters(hindsight_arm),
            "structure_aware": _counters(result.structure_aware),
        }
        # ARM E IS GATED ON ITS OWN PREDICATE, AND ONLY ITS OWN LISTS ARE GATED ON IT.
        # `usable_for_tuning_gap` is `usable_for_judged_contrast` AND arm E present; gating the
        # judged lists on it would drop a replicate from `regret` because a SUBSIDIARY arm was
        # missing, which is the one thing arm E must not be able to do. The `continue` above
        # therefore still tests `usable_for_judged_contrast`, unchanged. If the two usable sets
        # differ at all, `decomposition_refusal` marks the split inadmissible below rather than
        # averaging two denominators together.
        if result.usable_for_tuning_gap and result.tuned_static is not None:
            # `usable_for_tuning_gap` already required arm E; the second clause restates it so
            # the type checker can narrow the Optional, and it cannot fire on its own.
            tuned_static_costs.append(_cost(result.tuned_static))
            _accumulate(result.tuned_static, tuned_static_terms)
            arm_counters["tuned_static"] = _counters(result.tuned_static)
        # ARM D'S UNMET DEMAND IS THE FLOOR AT EVERY REPLICATE, OR ITS CLAIM HAS FAILED. Under a
        # delay zero is not guaranteed -- demand fulfilled before a SKU's first arrival is served
        # from opening stock alone, by every arm alike -- so the claim is pointwise least, taken
        # over every arm this replicate carries, and one counterexample at one seed falsifies it.
        floor = arm_counters["hindsight"]["unmet_demand_events"]
        if any(counts["unmet_demand_events"] < floor for counts in arm_counters.values()):
            hindsight_unmet_least = False
        for arm, counts in arm_counters.items():
            for counter, value in counts.items():
                counter_totals[arm][counter] += value

    if not reference_costs:
        return _finish(
            {
                "status": "unavailable",
                "reason": (
                    "no replicate produced usable evidence: every arm family disagreed on the "
                    "demand path, so nothing was measured"
                ),
                "unusable_seeds": unusable,
            }
        )

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
    # ARM E'S MEAN, AND THE TWO TERMS THE JUDGED REGRET SPLITS INTO (ADR-055 D2.6, finding 61).
    #
    #     regret = (mean_reference - mean_tuned_static) + (mean_tuned_static - mean_hindsight)
    #            =  tuning_gap                          +  information_ceiling
    #
    # The first term is closable by a GRID SEARCH -- no forecast, no agent, no consensus. The
    # second is EVPI in its textbook sense, perfect information minus the best here-and-now
    # decision, so it is a CEILING on what any forecaster or consensus system could ever win and
    # not an estimate of what one would. Before arm E this artifact reported their SUM, and every
    # document that quoted it read that sum as the second term alone.
    #
    # `nan` when the two usable sets disagree, because arm E then has no mean over the judged
    # replicate set and an unpaired one is a different estimator -- which
    # `RegretObjective.regret` refuses outright. `nan` is IEEE's value for "undefined" rather
    # than a substituted number: it fails both sign clauses of `decomposition_refusal`, so the
    # count clause is what refuses, and the artifact reports `None` because `NaN` is not valid
    # JSON and reads as a measured value in any consumer that coerces it.
    usable_judged = len(reference_costs)
    usable_tuned = len(tuned_static_costs)
    paired_arm_e = usable_tuned == usable_judged
    mean_tuned_static = objective.aggregate(tuned_static_costs) if paired_arm_e else math.nan
    tuning_gap = mean_reference - mean_tuned_static
    information_ceiling = mean_tuned_static - mean_hindsight
    # ARM O'S MEAN, on the same rule as arm E's: `nan`, never a substituted number, when its
    # usable set is not the judged one -- which `split_refusal`'s count clause then refuses.
    usable_structure_aware = len(structure_aware_costs)
    paired_arm_o = usable_structure_aware == usable_judged
    mean_structure_aware = objective.aggregate(structure_aware_costs) if paired_arm_o else math.nan
    split_paired = paired_arm_e and paired_arm_o
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
    # ARM E IS IN THE FAMILY, DELIBERATELY, AND EXCLUDING IT WOULD BE A FORBIDDEN REPAIR.
    # Leaving a new arm out to keep `hindsight_arm_is_pointwise_best` from flipping is narrowing
    # a checker's scope. Including it makes the claim STRICTLY STRONGER: arm D must now be the
    # pointwise minimum even against a par-level control tuned by grid search over a committed
    # grid. PRE-REGISTERED PREDICTION, recorded before the run that tests it: the flag stays
    # `True`, because arm D raises cumulative supply to cover every unit generated before its next
    # decision and no STATIC pair of levels can match that per-replicate. A `False` therefore says
    # arm D is not the objective's minimiser and ADR-055 D2.5.4 needs repair -- it does NOT say
    # arm E is wrong, and it changes neither `status` nor `verdict`, which read this flag nowhere.
    #
    # Admitted only when arm E is PAIRED with the others, and that is the ragged-family refusal
    # being respected rather than bypassed: `hindsight_min` raises on unequal lengths because an
    # unpaired minimum is a different estimator. When the sets disagree the decomposition is
    # already inadmissible below, and `hindsight_min_arms` names the arms the floor was actually
    # taken over, so a reader sees which family produced the flag instead of inferring it.
    if paired_arm_e:
        arm_cost_family["tuned_static"] = tuned_static_costs
    # Arm O joins on the same terms and for the same reason: excluding it would narrow the claim.
    if paired_arm_o:
        arm_cost_family["structure_aware"] = structure_aware_costs
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
    tuned_static_by_term = _term_means(tuned_static_terms)
    structure_aware_by_term = _term_means(structure_aware_terms)
    regret_by_term = {
        term: reference_by_term[term] - hindsight_by_term[term] for term in OBJECTIVE_TERMS
    }
    # THE SPLIT, PER TERM. `regret_by_term[t] == tuning_gap_by_term[t] +
    # information_ceiling_by_term[t]` for every term by the same telescoping as the scalars, so
    # these say WHICH term the information ceiling lives in -- the question "is the remaining
    # headroom holding cost or service?" cannot be answered from the two scalars alone. `None`
    # rather than a zero-filled mapping when arm E is unpaired: `_term_means` returns 0.0 over an
    # empty list, and a zero over no observations is indistinguishable from a measured zero.
    tuning_gap_by_term = (
        {term: reference_by_term[term] - tuned_static_by_term[term] for term in OBJECTIVE_TERMS}
        if paired_arm_e
        else None
    )
    information_ceiling_by_term = (
        {term: tuned_static_by_term[term] - hindsight_by_term[term] for term in OBJECTIVE_TERMS}
        if paired_arm_e
        else None
    )
    # THE THREE-TERM SPLIT, PER TERM (task 13.7b): which objective term the achievable and the
    # residual information values live in. `None` when the split's arms are unpaired, as above.
    achievable_information_value_by_term = (
        {
            term: tuned_static_by_term[term] - structure_aware_by_term[term]
            for term in OBJECTIVE_TERMS
        }
        if split_paired
        else None
    )
    residual_information_value_by_term = (
        {term: structure_aware_by_term[term] - hindsight_by_term[term] for term in OBJECTIVE_TERMS}
        if split_paired
        else None
    )
    regret_by_term_vs_foresight = {
        term: reference_by_term[term] - foresight_by_term[term] for term in OBJECTIVE_TERMS
    }
    headroom_by_term = {
        term: noop_by_term[term] - hindsight_by_term[term] for term in OBJECTIVE_TERMS
    }
    # Reported so a reader can see WHICH term dominates without sorting five numbers, and
    # named by magnitude rather than by sign so it is meaningful whichever way the regret goes.
    dominant_term = max(OBJECTIVE_TERMS, key=lambda term: abs(regret_by_term[term]))

    # EVERY ARM'S PER-TERM MEANS, IN ONE PLACE, so the artifact and the complement check cannot
    # disagree about which arms were examined. Arm E joins both when it is paired, for the same
    # reason it joins the hindsight-minimum family: a new arm excluded from a family-level claim
    # narrows that claim's scope, and the exclusion would be for no stated reason.
    by_term_arms: dict[str, dict[str, float]] = {
        "noop": noop_by_term,
        "reference": reference_by_term,
        "foresight": foresight_by_term,
        "hindsight": hindsight_by_term,
    }
    if paired_arm_e:
        by_term_arms["tuned_static"] = tuned_static_by_term
    if paired_arm_o:
        by_term_arms["structure_aware"] = structure_aware_by_term

    decomposition: dict[str, object] = {
        "mean_weighted_cost_by_term": by_term_arms,
        "regret_by_term": regret_by_term,
        "tuning_gap_by_term": tuning_gap_by_term,
        "information_ceiling_by_term": information_ceiling_by_term,
        "achievable_information_value_by_term": achievable_information_value_by_term,
        "residual_information_value_by_term": residual_information_value_by_term,
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
        # THAT HOLDS WITH INSTANTANEOUS REPLENISHMENT ONLY. Under structure 3 demand fulfilled
        # before a SKU's first arrival is served from opening stock alone, by every arm alike,
        # so zero is no longer owed and the delayed claim's falsifier is the top-level
        # `hindsight_unmet_pointwise_least` instead (task 13.7b).
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
            for by_term in by_term_arms.values()
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

    # THE SPLIT AND ARM E'S KEYS, BUILT ONCE, BEFORE ANY JUDGED-PATH REFUSAL, AND REPORTED ON EVERY
    # PATH THAT FOLLOWS (ADR-055 D2.6; task 13.7b). A refusal that withheld them would withhold
    # the evidence for its own most likely cause -- and at a horizon the opening stock covers, the
    # headroom guard below refuses legitimately, so that is the payload such a run lands on.
    #
    #     regret(B - D) = (B - E)      + (E - O)                       + (O - D)
    #                   =  tuning gap  + achievable information value  + residual information
    #
    # E - D is the information ceiling checkpoint B-prime judges. EACH TERM CARRIES ITS OWN
    # PAIRED INTERVAL, an independent bootstrap over the same seeds at the judged interval's
    # alpha, resample count and `INTERVAL_SEED` -- never the judged interval reused, which would
    # report one contrast's width as another's. An unpaired arm raises `IntervalUnavailableError`
    # in its term's call, which is how this block learns of it; the failure marks the SPLIT
    # inadmissible and never the measurement, because the judged verdict reads neither E nor O.
    split = (
        three_term_split(
            reference=mean_reference,
            tuned=mean_tuned_static,
            structure_aware=mean_structure_aware,
            hindsight=mean_hindsight,
        )
        if split_paired
        else None
    )
    term_samples: dict[str, tuple[list[float], list[float]]] = {
        "tuning_gap": (reference_costs, tuned_static_costs),
        "achievable_information_value": (tuned_static_costs, structure_aware_costs),
        "residual_information_value": (structure_aware_costs, hindsight_costs),
        "information_ceiling": (tuned_static_costs, hindsight_costs),
    }
    term_intervals: dict[str, dict[str, float] | None] = {term: None for term in term_samples}
    term_interval_refusals: dict[str, str] = {}
    try:
        term_alpha = contract_alpha()
        term_resamples = resamples_for(term_alpha)
    except IntervalUnavailableError as error:
        term_interval_refusals = dict.fromkeys(term_samples, str(error))
    else:
        for term, (first, second) in term_samples.items():
            try:
                found = paired_difference_interval(
                    first, second, alpha=term_alpha, resamples=term_resamples, seed=INTERVAL_SEED
                )
            except IntervalUnavailableError as error:
                term_interval_refusals[term] = str(error)
            else:
                term_intervals[term] = {"low": found.low, "high": found.high, "point": found.point}

    # ADMISSIBILITY OF THE TWO-TERM SPLIT, AND IT IS NOT THE VERDICT'S BUSINESS (ADR-055 D2.6).
    # `status: measured` certifies the JUDGED contrast -- arm B against arm D -- and NOT this
    # split, so the fields below are what stops a reader taking one for the other. A negative
    # tuning gap is the loud case and the reason is directional: it makes `information_ceiling`
    # exceed the regret, and an inflated ceiling makes the hard gate on E3's denominator MORE
    # permissive. `decomposition_refusal` carries that argument in full.
    # R2 (W2b): a refused search refuses the two-term split, as it already refused the three-term.
    decomposition_reason = decomposition_refusal(
        search_refusal=selection.refusal,
        tuning_gap=tuning_gap,
        information_ceiling=information_ceiling,
        usable_judged=usable_judged,
        usable_tuned=usable_tuned,
    )
    if decomposition_reason is None and "tuning_gap" in term_interval_refusals:
        decomposition_reason = (
            "no admissible interval could be estimated on the tuning gap: "
            f"{term_interval_refusals['tuning_gap']}. The split is reported without dispersion "
            "and marked INADMISSIBLE; the judged contrast and its own interval are untouched, "
            "because nothing in them reads arm E"
        )
    decomposition_admissible = decomposition_reason is None
    # The identity is a theorem over the reals and NOT over IEEE 754 (finding 56), so the residual
    # is REPORTED and the reader picks a tolerance they can defend. `None` when arm E has no
    # admissible mean: a NaN residual is not valid JSON and reads as a measured value downstream.
    decomposition_residual = (
        decomposition_identity_residual(
            regret=measured, tuning_gap=tuning_gap, information_ceiling=information_ceiling
        )
        if paired_arm_e
        else None
    )
    # THE THREE-TERM SPLIT'S ADMISSIBILITY REFINES THE TWO-TERM ONE: every clause that refuses
    # the two-term split refuses this one, and `split_refusal` adds E's search, the arm counts
    # and the sign of O - D. Any term without an interval refuses it too, because B-prime reads
    # an interval, and a term reported without its dispersion must not be read as having one.
    split_reason = split_refusal(
        search_refusal=selection.refusal,
        usable={
            "reference": usable_judged,
            "hindsight": usable_judged,
            "tuned_static": usable_tuned,
            "structure_aware": usable_structure_aware,
        },
        decomposition=decomposition_reason,
        residual_information_value=(
            split.residual_information_value if split is not None else math.nan
        ),
    )
    if split_reason is None and term_interval_refusals:
        missing = min(term_interval_refusals)
        split_reason = (
            f"no admissible interval could be estimated on {missing}: "
            f"{term_interval_refusals[missing]}. Every term of the split carries its own "
            "interval, so the split is reported without that dispersion and marked INADMISSIBLE"
        )
    split_admissible = split_reason is None

    # THE IN-SAMPLE RECHECK, AND WHY CHECKPOINT B-PRIME BINDS ON IT (W2b R1, the winner's curse).
    # Arm E's levels are the least of NOISY means over the tuning seeds, so on fresh seeds they
    # cost MORE in expectation than the best static policy: the out-of-sample ceiling E - D is
    # biased UP. That is the safe direction for finding 63's question (is the ceiling SMALL?) and
    # the UNSAFE one for B-prime's (is it ABOVE the margin?), where it can manufacture a false
    # room to win. So K -- the search's `ranked` cheapest vectors and the selection's unit
    # neighbours -- is re-priced on every judged measurement seed through `_static_arm_cost`, and
    # E_in is K's least mean THERE.
    #
    # WHY THAT IS CONSERVATIVE. A least of in-sample means is biased DOWN (E[min] <= min E), so
    # E_in - D is biased DOWN relative to K's best member; and because a converged search heads K
    # with its selection, E_in - D never exceeds E - D on these seeds -- PROVIDED re-pricing the
    # selection reproduces arm E's measured costs exactly, which is checked
    # (`in_sample_reproduces_arm_e`) and refused rather than assumed. `room_to_win` needs BOTH
    # ceilings above the margin, so a room reading survives the bias in either direction.
    # Neither covers a better static policy outside K's neighbourhood: the search's boundary and
    # non-convergence refusals cover its box and its budget, and nothing here claims more. The
    # judged contrast reads none of this.
    recheck_started = time.perf_counter()
    recheck: InSampleRecheck | None = None
    recheck_reason: str | None = None
    try:
        recheck = in_sample_recheck(
            selection=selection.levels,
            ranked=selection.ranked,
            neighbours_of_selection=neighbours(selection.levels),
            seeds=judged_seeds,
            cost_of=_static_arm_cost,
            aggregate=objective.aggregate,
        )
    except ValueError as error:
        recheck_reason = f"the in-sample recheck could not be priced: {error}"
    recheck_seconds = time.perf_counter() - recheck_started
    # `None` when it cannot be checked: the recheck refused, arm E is unpaired, or a refused
    # search left its selection out of K.
    reproduces = (
        list(recheck.selection_costs) == tuned_static_costs
        if recheck is not None and recheck.selection_costs is not None and paired_arm_e
        else None
    )
    if recheck is not None and reproduces is None:
        recheck_reason = (
            "whether the recheck reproduces arm E's measured costs cannot be checked -- arm E is "
            "not paired with the judged replicates, or a refused search left its selection out "
            "of the recheck's candidates -- so the in-sample ceiling is not comparable"
        )
    elif reproduces is False:
        recheck_reason = (
            "re-pricing arm E's own levels did not reproduce arm E's measured costs seed for "
            "seed, so the recheck ran different physics from the measurement and its ceiling is "
            "not comparable with the out-of-sample one"
        )
    #: The in-sample ceiling's paired interval; `None` exactly when the recheck is impossible.
    in_sample_interval: dict[str, float] | None = None
    if recheck is not None and recheck_reason is None:
        try:
            recheck_alpha = contract_alpha()
            estimated = paired_difference_interval(
                list(recheck.costs),
                hindsight_costs,
                alpha=recheck_alpha,
                resamples=resamples_for(recheck_alpha),
                seed=INTERVAL_SEED,
            )
        except IntervalUnavailableError as error:
            recheck_reason = (
                f"no admissible interval could be estimated on the in-sample ceiling: {error}"
            )
        else:
            in_sample_interval = {
                "low": estimated.low,
                "high": estimated.high,
                "point": estimated.point,
            }

    def _room(margin_read: float | None) -> dict[str, object]:
        """Checkpoint B-prime's readings for this cell, from the two ceiling intervals alone."""
        ceiling = term_intervals["information_ceiling"]
        out_of_sample = (ceiling["low"], ceiling["high"]) if ceiling is not None else None
        in_sample = (
            (in_sample_interval["low"], in_sample_interval["high"])
            if in_sample_interval is not None
            else None
        )
        return {
            # BINDING: both ceilings above the margin for room, the out-of-sample one below it
            # for no room -- ROOM_TO_WIN_RULE, reported beside it as `room_to_win_rule`.
            "room_to_win": room_to_win(
                out_of_sample_ceiling=out_of_sample,
                in_sample_ceiling=in_sample,
                margin=margin_read,
                split_admissible=split_admissible,
            ),
            # The out-of-sample reading alone -- the binding one before W2b -- so the recheck's
            # effect on this cell is one comparison away. It binds nothing.
            "room_to_win_out_of_sample": room_to_win_out_of_sample(
                out_of_sample, margin=margin_read, split_admissible=split_admissible
            ),
            # The margin both readings compared against; `None` on a path that refused before
            # the margin was read, which both report as `unavailable`.
            "room_to_win_margin": margin_read,
        }

    # ARM E'S KEYS AND THE SPLIT'S KEYS, AND WHAT EACH IS. `status` CERTIFIES THE JUDGED CONTRAST
    # AND NOT THE SPLIT: `decomposition_admissible` certifies the two-term split and
    # `split_admissible` the three-term one, each as its own boolean, so a `measured` run whose
    # split refused cannot be read as certifying both and no consumer parses a reason string.
    shared: dict[str, object] = {
        # Arm E's mean over the MEASUREMENT seeds. This is the number the split uses.
        "mean_tuned_static_cost": mean_tuned_static if paired_arm_e else None,
        "tuned_static_levels": selection.levels.as_dict(),
        "tuned_static_refusal": selection.refusal,
        "tuned_static_converged": selection.converged,
        "tuned_static_evaluations": selection.evaluations,
        "tuned_static_passes": selection.passes,
        # TWO MEAN COSTS ONE WORD APART, so state which is which rather than let a reader match
        # them up: `tuned_static_mean_cost` is the SELECTED levels' mean over the TUNING seeds,
        # the number the search minimised, whereas `mean_tuned_static_cost` above is over the
        # measurement seeds. `tuning_vs_measurement_seed_gap` is the second minus the first, and
        # it is NOT a generalisation gap: the two means are over DIFFERENT seed sets, so it mixes
        # the winner's curse with plain sampling difference and separates neither (W2b).
        # `tuned_static_incumbent_cost` is the incumbent's mean over the same tuning seeds, so
        # the search's asserted invariant (never worse than the incumbent) is readable here.
        "tuned_static_mean_cost": selection.mean_cost,
        "tuning_vs_measurement_seed_gap": (
            mean_tuned_static - selection.mean_cost if paired_arm_e else None
        ),
        "tuned_static_incumbent_cost": selection.incumbent_cost,
        "tuned_static_tie_broken": selection.tie_broken,
        # Every candidate the search was ever offered, per group, after its extensions.
        "tuned_static_candidates": {
            group: list(values) for group, values in sorted(selection.candidates.items())
        },
        "tuned_static_candidates_injected": candidates is not None,
        "tuning_seeds": list(seeds),
        "tuning_seeds_injected": tuning_seeds is not None,
        "tuning_spec_source": spec.source,
        "tuning_gap": tuning_gap if paired_arm_e else None,
        "information_ceiling": information_ceiling if paired_arm_e else None,
        "tuning_gap_interval": term_intervals["tuning_gap"],
        "decomposition_residual": decomposition_residual,
        "decomposition_admissible": decomposition_admissible,
        "decomposition_refusal": decomposition_reason,
        # The split's denominators, as values rather than as prose inside the reason.
        "replicates_usable_tuned_static": usable_tuned,
        "replicates_usable_structure_aware": usable_structure_aware,
        "mean_structure_aware_cost": mean_structure_aware if paired_arm_o else None,
        "achievable_information_value": (
            split.achievable_information_value if split is not None else None
        ),
        "residual_information_value": (
            split.residual_information_value if split is not None else None
        ),
        "achievable_information_value_interval": term_intervals["achievable_information_value"],
        "residual_information_value_interval": term_intervals["residual_information_value"],
        "information_ceiling_interval": term_intervals["information_ceiling"],
        # What IEEE 754 leaves of `regret - (sum of the three terms)`, reported for the reader to
        # judge rather than toleranced here (finding 56). The identity over `Fraction` is a
        # theorem for every finite input, so it was a constant and is no longer reported (W2b R5).
        "split_residual_float": split.residual_float if split is not None else None,
        "split_admissible": split_admissible,
        "split_refusal": split_reason,
        "room_to_win_rule": ROOM_TO_WIN_RULE,
        # THE IN-SAMPLE RECHECK (W2b R1), computed above `_room`: arm E re-chosen on the
        # measurement seeds, and the downward-biased ceiling `room_to_win` also requires.
        "in_sample_tuned_static_levels": recheck.levels.as_dict() if recheck is not None else None,
        "mean_in_sample_tuned_static_cost": recheck.mean_cost if recheck is not None else None,
        "in_sample_candidates_evaluated": len(recheck.members) if recheck is not None else None,
        # Every candidate's mean over the measurement seeds, in pricing (= tie-break) order and
        # headed by the selection, so E_in's choice is checkable from the artifact alone.
        "in_sample_surface": (
            [
                {"levels": member.as_dict(), "mean_cost": mean}
                for member, mean in zip(recheck.members, recheck.mean_costs, strict=True)
            ]
            if recheck is not None
            else None
        ),
        "in_sample_reproduces_arm_e": reproduces,
        "information_ceiling_in_sample": (
            recheck.mean_cost - mean_hindsight if recheck is not None else None
        ),
        "information_ceiling_in_sample_interval": in_sample_interval,
        "in_sample_recheck_refusal": recheck_reason,
        "in_sample_recheck_seconds": recheck_seconds,
        # Arm D's delayed-world falsifier, over every arm at every usable replicate.
        "hindsight_unmet_pointwise_least": hindsight_unmet_least,
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
        return _finish(
            {
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
                "hours_per_replicate": hours,
                "regret": measured,
                "comparator_headroom": headroom,
                "mean_noop_cost": mean_noop,
                "mean_reference_cost": mean_reference,
                "mean_foresight_cost": mean_foresight,
                "mean_hindsight_cost": mean_hindsight,
                "oracle_arm": ORACLE_ARM,
                **shared,
                **_room(None),
            }
        )

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
        return _finish(
            {
                "status": "unavailable",
                "reason": (
                    f"measured regret {measured:.6g} over {len(reference_costs)} usable "
                    f"replicate(s) but no admissible interval could be estimated: {error}. The "
                    "regret is reported and JUDGED BY NOTHING: `material` requires an interval "
                    "excluding the margin, and a point estimate with no dispersion must not be "
                    "read as one"
                ),
                "replicates_usable": len(reference_costs),
                "replicates_unusable": len(unusable),
                "unusable_seeds": unusable,
                "regret": measured,
                "comparator_headroom": headroom,
                "mean_reference_cost": mean_reference,
                "mean_hindsight_cost": mean_hindsight,
                "oracle_arm": ORACLE_ARM,
                **shared,
                **_room(None),
            }
        )

    # The interval's own point estimate is PINNED against the objective's, not trusted to
    # agree with it (task 15.1's "`point` equals `headline_uplift` and is pinned against it,
    # not computed twice"). `fmean(a) - fmean(b)` and `fmean(a_i - b_i)` are the same quantity
    # by algebra and not necessarily the same float, so the comparison is a closeness test; a
    # real disagreement means the two sides are not measuring the same contrast, and that is
    # reported rather than averaged over.
    if not math.isclose(interval.point, measured, rel_tol=1e-9, abs_tol=1e-12):
        return _finish(
            {
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
                "mean_reference_cost": mean_reference,
                "mean_hindsight_cost": mean_hindsight,
                "oracle_arm": ORACLE_ARM,
                **shared,
                **_room(None),
            }
        )

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
        refusal_report: dict[str, object] = {
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
            # The split is reported here too; with B - D negative one of its two-term clauses
            # must refuse it, so `room_to_win` reads `unavailable` on this path by construction.
            **shared,
            **_room(margin),
        }
        return _finish(refusal_report)

    verdict = classify_regret(
        measured, objective=objective, margin=margin, interval=interval.bounds
    )
    report: dict[str, object] = {
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
        # ARM E'S AND ARM O'S KEYS, AND WHAT THEY ARE AND ARE NOT (ADR-055 D2.6; task 13.7b).
        # `regret`, `comparator_headroom`, `regret_vs_foresight`,
        # `comparator_headroom_vs_foresight`, the judged interval and `verdict` below are
        # computed from EXACTLY the same inputs as before either arm existed: both are built
        # AFTER arms A-D inside `run_three_pass`, and nothing on the judged path reads them.
        # `status: measured` therefore certifies the judged contrast and NOT the split --
        # `decomposition_admissible` and `split_admissible` certify the splits, and
        # `room_to_win` is read from the two ceiling intervals alone.
        **shared,
        **_room(margin),
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
            "SIX ARMS, in the world cell `cell` names (`None` = the world before structures 1 "
            "and 3). Arms E (tuned static, re-derived per cell) and O (structure-aware "
            "base-stock) are DECOMPOSITION arms, never candidates for the judged contrast: they "
            "split it as B - D = (B - E) + (E - O) + (O - D) -- tuning gap, achievable "
            "information value, residual information value -- and E - D, the information "
            "ceiling, is what `room_to_win` reads: out of sample AND re-chosen in sample on the "
            "measurement seeds, both required above the margin (W2b R1). `status` certifies the "
            "judged contrast and "
            "NOT that split; `split_admissible` certifies the split. ADR-055 D2.6 carries the "
            "argument. THE FOUR ARMS BELOW ARE UNCHANGED BY IT. "
            "regret = (s, S) reference - hindsight oracle, "
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
    return _finish(report)


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
    # NO CELL IS THE WORLD BEFORE STRUCTURES 1 AND 3 -- a declared meaning, not a default value:
    # it is what every run before task 13.7b measured, and the artifact reports `cell: null`.
    parser.add_argument(
        "--cell",
        default=None,
        help=(
            "a world.cells name from digital_twin/simulation/policy.yaml; omitted, the arms run "
            "the world before structures 1 and 3"
        ),
    )
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args(argv)

    report = _measure(int(args.replicates), float(args.hours), args.cell)
    if args.as_json:
        print(json.dumps(report, sort_keys=True, separators=(",", ":"), default=str))
    else:
        for key, value in sorted(report.items()):
            print(f"{key}: {value}")
    return 0 if report.get("status") == "measured" else 2


if __name__ == "__main__":
    import sys

    sys.exit(main())
