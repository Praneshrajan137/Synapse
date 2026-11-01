"""Control classification by interval position: the negative, positive and agreement verdicts.

Feature: decision-quality-proof, task 16.4 as re-scoped 2026-09-29 (R6.1-R6.4, R6.14, R6.15;
design E3.2; ADR-055 D2.8, D2.9 and D6). Pure classification of intervals estimated elsewhere.
This module imports no twin, no harness and no numpy itself; the ``uplift`` package's
``__init__`` still loads all three on any ``uplift.*`` import. The one read is the
Metric_Contract's committed ``alpha``, so a caller cannot hand a classifier a different
confidence level.

**ORIENTATION, stated once and used everywhere below.** Every interval is on
``comparator cost - subject cost``, so a POSITIVE value means the SUBJECT arm is cheaper -- the
orientation of the uplift headline, where positive means the subject is better. The
comparator's split terms already read this way: ``achievable_information_value`` is ``E - O``
and ``information_ceiling`` is ``E - D`` (``uplift/regret.py::_measure``).

* **Negative control** (R6.1, R6.15). Arm E against itself on DISJOINT seed ranges paired by
  index: on shared seeds two copies of a deterministic arm give a ``[0, 0]`` interval, a control
  that cannot fail (finding 69). A repetition reports a proven gain iff its interval lies
  strictly above zero, and the control passes iff the proportion of the declared repetitions
  reporting one is within the declared tolerance (ADR-055 D6).
* **Positive control** (R6.2). Arm O (subject) against arm E (comparator): ``detected`` iff the
  interval lies ENTIRELY ABOVE zero -- not "excludes zero", which an interval wholly below zero
  also satisfies.
* **Agreement** (R6.3 and R6.4 as re-cut). The harness's ``E - O`` must agree with the
  comparator's independently measured ``E - O`` and must not exceed the information ceiling
  ``E - D``; failing either reports the HARNESS mis-measuring. :data:`AgreementVerdict` has no
  member for an under-performing oracle, so no input can produce that reading.

**Refused, never classified** (``ValueError``: a malformed input is a defect, not a verdict): a
non-finite or inverted interval, one not bracketing its point, one at any ``alpha`` but the
committed one, a duplicate or undeclared repetition index, and seed ranges overlapping within
or across repetitions -- independence is the premise of a rate. Absent data is
``unavailable``, never a pass (I-7). Each reading re-derives its verdict from the numbers it
records, by the same definition its classifier applies, so a reading read back from an
artifact cannot carry a verdict those numbers do not license. R6.14's single named comparator
is the invoking job's obligation (task 15.5's ``ControlSpec``): nothing here can see how an
interval was produced.
"""

from __future__ import annotations

import itertools
import math
from typing import TYPE_CHECKING, Final, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator

from uplift.interval import contract_alpha

if TYPE_CHECKING:
    from collections.abc import Sequence

__all__ = [
    "AGREEMENT_ASSUMPTION",
    "AGREEMENT_METHOD",
    "AGREEMENT_RULE",
    "AgreementReading",
    "AgreementVerdict",
    "IntervalBounds",
    "JudgedInterval",
    "MisMeasurement",
    "NegativeControlReading",
    "NegativeControlVerdict",
    "NegativeRepetition",
    "Position",
    "PositiveControlReading",
    "PositiveControlVerdict",
    "SeedRange",
    "agreement_difference",
    "classify_agreement",
    "classify_negative_control",
    "classify_positive_control",
]

#: Where a closed interval lies relative to zero. An endpoint exactly ON zero contains it.
Position = Literal["above_zero", "contains_zero", "below_zero"]

#: R6.1 and R6.15. ``unavailable`` while fewer repetitions than declared were supplied.
NegativeControlVerdict = Literal["pass", "fail", "unavailable"]

#: R6.2. ``detected`` only for an interval lying entirely above zero.
PositiveControlVerdict = Literal["detected", "not_detected", "unavailable"]

#: R6.3 and R6.4. CLOSED BY CONSTRUCTION: no member says the oracle under-performs, because an
#: oracle effect outside the agreement rule is the instrument's defect, not the arm's.
AgreementVerdict = Literal["agrees", "harness_mis_measuring", "unavailable"]

#: The agreement rule's two clauses, in the order they are evaluated and reported.
MisMeasurement = Literal["disagrees_with_comparator", "exceeds_information_ceiling"]

#: How :func:`agreement_difference` puts an interval on the difference of two estimates.
AGREEMENT_METHOD: Final[str] = "normal_approximation_from_half_widths"

#: What that method assumes, recorded beside every reading so the assumption can be attacked.
AGREEMENT_ASSUMPTION: Final[str] = (
    "each interval is approximately a symmetric normal interval at the shared committed alpha, "
    "so its standard error is its half-width over z = inv_cdf(1 - alpha / 2); the estimates are "
    "independent (disjoint seeds), so their variances add, and z cancels: the difference's "
    "half-width is sqrt(w_harness^2 + w_comparator^2). Estimates that share seeds are "
    "positively correlated, the true half-width is narrower, and the reading leans toward agrees"
)

#: R6.3's tolerance as re-cut 2026-09-29 (ADR-055 D2.8): a rule, not a number.
AGREEMENT_RULE: Final[str] = (
    "agrees iff the interval on (harness E - O) - (comparator E - O) contains 0 AND the "
    "harness's E - O low bound is at or below the information ceiling's (E - D) high bound; "
    "harness_mis_measuring otherwise, naming every failed clause; unavailable while any of the "
    "three intervals is absent. Arm O is never reported as under-performing (R6.4)"
)


class IntervalBounds(Protocol):
    """The four numbers a classifier reads off an interval.

    Structural, so ``uplift.interval.Interval`` (the estimator's form) and task 15.1's
    serialisation form, which declares the same field names, are both accepted without this
    module importing the harness. A structural type promises names, not admissible values, so
    whatever supplies one is re-validated through :class:`JudgedInterval`.
    """

    @property
    def low(self) -> float: ...

    @property
    def high(self) -> float: ...

    @property
    def point(self) -> float: ...

    @property
    def alpha(self) -> float: ...


class JudgedInterval(BaseModel):
    """An interval as a control verdict reads it, recorded beside the verdict it supports.

    Refuses rather than records a non-finite number, ``low > high``, a point outside its own
    bounds, or an ``alpha`` outside ``(0, 1)``. ``uplift.interval.Interval`` refuses the first
    three at construction already; this record re-checks because :class:`IntervalBounds` is
    structural, and an interval read back from an artifact has passed through no estimator.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    low: float
    high: float
    point: float
    alpha: float

    @model_validator(mode="after")
    def _admissible(self) -> JudgedInterval:
        for name, value in (
            ("low", self.low),
            ("high", self.high),
            ("point", self.point),
            ("alpha", self.alpha),
        ):
            if not math.isfinite(value):
                raise ValueError(f"{name}={value!r} is not finite, so nothing was estimated")
        if self.low > self.high:
            raise ValueError(f"the bounds are inverted: low={self.low!r} > high={self.high!r}")
        if not self.low <= self.point <= self.high:
            raise ValueError(
                f"[{self.low!r}, {self.high!r}] does not bracket its own point {self.point!r}"
            )
        if not 0.0 < self.alpha < 1.0:
            raise ValueError(f"alpha={self.alpha!r} lies outside (0, 1), so it names no level")
        return self

    @classmethod
    def of(cls, source: IntervalBounds) -> JudgedInterval:
        """Read the four numbers off any interval-shaped object, re-validating them."""
        return cls(low=source.low, high=source.high, point=source.point, alpha=source.alpha)

    @property
    def position(self) -> Position:
        """Where the closed interval lies relative to zero; an endpoint ON zero contains it."""
        if self.low > 0.0:
            return "above_zero"
        if self.high < 0.0:
            return "below_zero"
        return "contains_zero"

    def describe(self) -> str:
        """ASCII one-liner, so a reason never states a bare pair of numbers."""
        return f"[{self.low:.6g}, {self.high:.6g}] (point {self.point:.6g})"


class SeedRange(BaseModel):
    """A half-open range ``[start, start + count)`` of replicate seeds.

    The shape ``uplift/tuning.py::seed_overlap_refusal`` already reasons in, where tuning and
    measurement seeds are integer ranges handed to the twin. Strict integers, so neither a
    ``True`` nor a ``2.0`` can stand in for a seed.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    start: int = Field(strict=True, ge=0)
    count: int = Field(strict=True, ge=1)

    @property
    def stop(self) -> int:
        """One past the last seed."""
        return self.start + self.count

    def overlaps(self, other: SeedRange) -> bool:
        """Whether any seed lies in both ranges."""
        return self.start < other.stop and other.start < self.stop

    def describe(self) -> str:
        """ASCII one-liner naming the inclusive seed span."""
        return f"seeds {self.start}..{self.stop - 1}"


class NegativeRepetition(BaseModel):
    """One negative-control repetition: arm E against itself on two disjoint seed ranges.

    Paired by index -- replicate ``i`` of ``subject_seeds`` against replicate ``i`` of
    ``comparator_seeds`` -- so the two ranges have one length. ``interval`` is on the comparator
    copy's cost minus the subject copy's, so a proven gain says the subject copy was cheaper.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    index: int = Field(strict=True, ge=0)
    subject_seeds: SeedRange
    comparator_seeds: SeedRange
    interval: JudgedInterval

    @model_validator(mode="after")
    def _paired_on_disjoint_seeds(self) -> NegativeRepetition:
        subject, comparator = self.subject_seeds, self.comparator_seeds
        if subject.count != comparator.count:
            raise ValueError(
                f"repetition {self.index} pairs {subject.count} subject replicates with "
                f"{comparator.count} comparator replicates; pairing by index needs one length"
            )
        if subject.overlaps(comparator):
            raise ValueError(
                f"repetition {self.index} runs both copies of arm E on overlapping seeds "
                f"({subject.describe()} and {comparator.describe()}): a shared seed is one "
                "realisation counted on both sides, and on identical ranges every paired "
                "difference is 0 -- a [0, 0] interval that cannot fail (finding 69)"
            )
        return self

    @property
    def proven_gain(self) -> bool:
        """The subject copy proven cheaper: the interval lies strictly above zero."""
        return self.interval.position == "above_zero"


def _refuse_unjudgeable_bound(bound: float) -> None:
    """Refuse a rate bound outside ``[0, 1)``: at ``1`` every count passes."""
    if not (math.isfinite(bound) and 0.0 <= bound < 1.0):
        raise ValueError(
            f"max_proven_gain_rate={bound!r} is not a proportion in [0, 1): "
            "outside [0, 1] no count can be judged against it, and at 1 every count passes, "
            "so the control could never fail (finding 69's shape, one level up)"
        )


def _negative_verdict(
    *, supplied: int, required: int, gains: int, bound: float
) -> tuple[NegativeControlVerdict, float | None]:
    """R6.15's verdict and rate for these counts: the ONE definition classifier and record share.

    ``unavailable`` with no rate while fewer than ``required`` were supplied; otherwise ``pass``
    iff ``gains / supplied <= bound``, compared by division so the decimal the policy states is
    the bound applied.
    """
    if supplied < required:
        return "unavailable", None
    rate = gains / supplied
    verdict: NegativeControlVerdict = "pass" if rate <= bound else "fail"
    return verdict, rate


class NegativeControlReading(BaseModel):
    """What the repeated negative control licenses (R6.1, R6.15; ADR-055 D6).

    ``proven_loss_count`` is recorded and does not drive the verdict, which counts proven GAINS
    as R6.15 states. It is recorded because a gain-only count sees half of a symmetric
    miscalibration: an E-against-E interval excludes zero on either side equally often, so an
    instrument excluding zero on two in five null repetitions reports gains on about one in
    five, which the committed bound admits.

    The verdict and the rate are re-derived from the counts and the bound on construction, by
    :func:`_negative_verdict`, so a ``pass`` over fewer repetitions than declared, or over more
    gains than the bound admits, is refused rather than recorded.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    verdict: NegativeControlVerdict
    supplied: int = Field(strict=True, ge=0)
    required: int = Field(strict=True, ge=1)
    proven_gain_count: int = Field(strict=True, ge=0)
    proven_loss_count: int = Field(strict=True, ge=0)
    #: ``proven_gain_count / supplied``; ``None`` while ``unavailable``, because a rate over
    #: fewer repetitions than declared estimates nothing R6.15 judges.
    rate: float | None
    max_proven_gain_rate: float
    alpha: float
    explanation: str

    @model_validator(mode="after")
    def _licensed_by_its_counts(self) -> NegativeControlReading:
        if self.supplied > self.required:
            raise ValueError(
                f"{self.supplied} repetitions supplied against {self.required} declared: a "
                "reading over undeclared repetitions licenses no verdict"
            )
        if self.proven_gain_count + self.proven_loss_count > self.supplied:
            raise ValueError(
                f"{self.proven_gain_count} proven gains and {self.proven_loss_count} proven "
                f"losses among {self.supplied} repetitions: a repetition proves one or neither"
            )
        _refuse_unjudgeable_bound(self.max_proven_gain_rate)
        if not (math.isfinite(self.alpha) and 0.0 < self.alpha < 1.0):
            raise ValueError(f"alpha={self.alpha!r} lies outside (0, 1), so it names no level")
        verdict, rate = _negative_verdict(
            supplied=self.supplied,
            required=self.required,
            gains=self.proven_gain_count,
            bound=self.max_proven_gain_rate,
        )
        if (self.verdict, self.rate) != (verdict, rate):
            raise ValueError(
                f"the reading records verdict={self.verdict!r} at rate={self.rate!r}, but its "
                f"own counts license verdict={verdict!r} at rate={rate!r}: a verdict its "
                "numbers do not license is refused rather than recorded"
            )
        return self


def _positive_verdict(position: Position | None) -> PositiveControlVerdict:
    """R6.2's verdict for an interval at ``position``; ``None`` is an absent interval."""
    if position is None:
        return "unavailable"
    if position == "above_zero":
        return "detected"
    return "not_detected"


class PositiveControlReading(BaseModel):
    """What the positive control licenses (R6.2), with the interval it was judged on.

    The position and the verdict are re-derived from the recorded interval on construction, by
    :func:`_positive_verdict`, so a ``detected`` the interval does not show is refused rather
    than recorded.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    verdict: PositiveControlVerdict
    position: Position | None
    interval: JudgedInterval | None
    explanation: str

    @model_validator(mode="after")
    def _licensed_by_its_interval(self) -> PositiveControlReading:
        position: Position | None = None if self.interval is None else self.interval.position
        verdict = _positive_verdict(position)
        if (self.verdict, self.position) != (verdict, position):
            raise ValueError(
                f"the reading records verdict={self.verdict!r} at position={self.position!r}, "
                f"but its own interval licenses verdict={verdict!r} at position={position!r}: "
                "a verdict its numbers do not license is refused rather than recorded"
            )
        return self


class AgreementReading(BaseModel):
    """The agreement verdict (R6.3 and R6.4 as re-cut), with all three estimates it read.

    The difference interval, the failed clauses and the verdict are re-derived from the three
    recorded estimates on construction, by :func:`agreement_difference` and
    :func:`_failed_clauses` -- what :func:`classify_agreement` applies -- so an ``agrees`` its
    estimates do not license is refused rather than recorded.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    verdict: AgreementVerdict
    #: Every failed clause, in :data:`MisMeasurement` order; empty unless mis-measuring.
    reasons: tuple[MisMeasurement, ...]
    harness: JudgedInterval | None
    comparator: JudgedInterval | None
    ceiling: JudgedInterval | None
    #: The interval on ``harness.point - comparator.point``; ``None`` while ``unavailable``.
    difference: JudgedInterval | None
    method: str
    assumption: str
    explanation: str

    @model_validator(mode="after")
    def _licensed_by_its_estimates(self) -> AgreementReading:
        if self.method != AGREEMENT_METHOD:
            raise ValueError(
                f"method={self.method!r} is not {AGREEMENT_METHOD!r}, the one method whose "
                "difference interval this record can re-derive, so its verdict is not read"
            )
        harness, comparator, ceiling = self.harness, self.comparator, self.ceiling
        verdict: AgreementVerdict = "unavailable"
        reasons: tuple[MisMeasurement, ...] = ()
        difference: JudgedInterval | None = None
        if harness is not None and comparator is not None and ceiling is not None:
            if ceiling.alpha != harness.alpha:
                raise ValueError(
                    f"the ceiling was estimated at alpha={ceiling.alpha!r} and the harness at "
                    f"alpha={harness.alpha!r}; one verdict is read at one alpha"
                )
            difference = agreement_difference(harness, comparator)
            reasons = _failed_clauses(harness, difference, ceiling)
            verdict = "harness_mis_measuring" if reasons else "agrees"
        if (self.verdict, self.reasons, self.difference) != (verdict, reasons, difference):
            raise ValueError(
                f"the reading records verdict={self.verdict!r} with reasons={self.reasons!r}, "
                f"but its own estimates license verdict={verdict!r} with reasons={reasons!r} "
                "and their recomputed difference interval: a verdict its numbers do not "
                "license is refused rather than recorded"
            )
        return self


def _refuse_other_alpha(interval: JudgedInterval, *, which: str, committed: float) -> None:
    """Refuse an interval at any confidence level but the Metric_Contract's committed one."""
    if interval.alpha != committed:
        raise ValueError(
            f"the {which} interval was estimated at alpha={interval.alpha!r}, not the "
            f"Metric_Contract's committed alpha={committed!r}; a verdict at another level is a "
            "different test, so it is refused rather than read"
        )


def _judged(source: IntervalBounds, *, which: str, committed: float) -> JudgedInterval:
    """Re-validate ``source`` and refuse any ``alpha`` but the committed one."""
    try:
        judged = JudgedInterval.of(source)
    except ValueError as error:
        raise ValueError(f"the {which} interval is malformed and is refused: {error}") from error
    _refuse_other_alpha(judged, which=which, committed=committed)
    return judged


def _judged_or_none(
    source: IntervalBounds | None, *, which: str, committed: float
) -> JudgedInterval | None:
    """:func:`_judged`, with an absent interval left absent rather than refused."""
    return None if source is None else _judged(source, which=which, committed=committed)


def _refuse_dependent_repetitions(
    ordered: Sequence[NegativeRepetition], *, required: int, alpha: float
) -> None:
    """Refuse whatever would stop the repetitions being independent draws of one test."""
    for earlier, later in itertools.pairwise(ordered):
        if earlier.index == later.index:
            raise ValueError(
                f"repetition index {later.index} appears twice; a rate counts each declared "
                "repetition once, so a duplicate is refused rather than double-counted"
            )
    for repetition in ordered:
        if repetition.index >= required:
            raise ValueError(
                f"repetition index {repetition.index} lies outside the {required} declared "
                f"(0..{required - 1}); judging undeclared repetitions would license running "
                "until the rate looks good"
            )
        _refuse_other_alpha(
            repetition.interval, which=f"repetition {repetition.index}", committed=alpha
        )
    sizes = sorted({repetition.subject_seeds.count for repetition in ordered})
    if len(sizes) > 1:
        raise ValueError(
            f"repetitions ran at {sizes} replicates per side; a rate is a proportion of ONE "
            "experiment repeated, and different replicate counts are different experiments"
        )
    spans: list[tuple[SeedRange, str]] = []
    for repetition in ordered:
        spans.append((repetition.subject_seeds, f"repetition {repetition.index} subject"))
        spans.append((repetition.comparator_seeds, f"repetition {repetition.index} comparator"))
    spans.sort(key=lambda span: (span[0].start, span[0].stop))
    for (first, first_label), (second, second_label) in itertools.pairwise(spans):
        if first.overlaps(second):
            raise ValueError(
                f"{first_label} ({first.describe()}) and {second_label} "
                f"({second.describe()}) overlap: independence is the premise of a rate, and a "
                "seed shared by two repetitions is one realisation counted twice"
            )


def classify_negative_control(
    repetitions: Sequence[NegativeRepetition],
    *,
    required_repetitions: int,
    max_proven_gain_rate: float,
) -> NegativeControlReading:
    """Judge the repeated negative control by its proportion of proven gains (R6.15).

    ``required_repetitions`` and ``max_proven_gain_rate`` are ADR-055 D6's two numbers, read by
    the caller through ``digital_twin.simulation.policy.negative_control_settings``. ``pass``
    iff ``proven_gain_count / supplied <= max_proven_gain_rate`` over exactly the declared
    count -- compared by division, so the decimal the policy states is the bound applied --
    ``fail`` otherwise, and ``unavailable`` while fewer were supplied, never a pass. Judged in
    index order, so the order supplied cannot move the verdict.

    Raises:
        ValueError: On a repetition count below 1; a rate bound outside ``[0, 1)`` (at ``1``
            every count passes, so the control could never fail); a duplicate index, or one
            outside ``0 .. required_repetitions - 1`` (a repetition nobody declared: judging
            extras would license running until the rate looks good); repetitions at different
            replicate counts, which are different experiments rather than one repeated; seed
            ranges overlapping across repetitions; or an interval at any ``alpha`` but the
            committed one.
        IntervalUnavailableError: When the committed ``alpha`` cannot be read.
    """
    if required_repetitions < 1:
        raise ValueError(
            f"required_repetitions={required_repetitions!r}: a rate needs at least one declared "
            "repetition to be a proportion of anything"
        )
    _refuse_unjudgeable_bound(max_proven_gain_rate)
    alpha = contract_alpha()
    ordered = sorted(repetitions, key=lambda repetition: repetition.index)
    _refuse_dependent_repetitions(ordered, required=required_repetitions, alpha=alpha)
    gains = sum(1 for repetition in ordered if repetition.proven_gain)
    losses = sum(1 for repetition in ordered if repetition.interval.position == "below_zero")
    supplied = len(ordered)
    verdict, rate = _negative_verdict(
        supplied=supplied, required=required_repetitions, gains=gains, bound=max_proven_gain_rate
    )
    if rate is None:
        explanation = (
            f"{supplied} of the {required_repetitions} declared repetitions were supplied; "
            "a rate over fewer than the declared count estimates nothing R6.15 judges, so "
            "this is unavailable and never a pass (I-7)"
        )
    else:
        comparison = "within" if verdict == "pass" else "above"
        explanation = (
            f"{gains} of {supplied} repetitions report a proven gain (rate {rate:.6g}), "
            f"{comparison} the declared {max_proven_gain_rate:g} at alpha={alpha:g}; "
            f"{losses} report a proven loss, recorded and not judged (R6.15 counts gains)"
        )
    return NegativeControlReading(
        verdict=verdict,
        supplied=supplied,
        required=required_repetitions,
        proven_gain_count=gains,
        proven_loss_count=losses,
        rate=rate,
        max_proven_gain_rate=max_proven_gain_rate,
        alpha=alpha,
        explanation=explanation,
    )


def classify_positive_control(interval: IntervalBounds | None) -> PositiveControlReading:
    """Arm O against arm E: ``detected`` iff the interval lies strictly above zero (R6.2).

    An interval wholly BELOW zero excludes zero and is still ``not_detected`` -- R6.2 replaced
    "excludes zero" for exactly that reason. Whether such a reading means the harness is
    mis-measuring is :func:`classify_agreement`'s question (R6.4); nothing here reads it as arm
    O under-performing. A low bound exactly on zero contains zero, so it is not a detection.

    Raises:
        ValueError: On a malformed interval or one at any ``alpha`` but the committed one.
        IntervalUnavailableError: When the committed ``alpha`` cannot be read.
    """
    if interval is None:
        return PositiveControlReading(
            verdict="unavailable",
            position=None,
            interval=None,
            explanation=(
                "no positive-control interval was supplied, so the harness has been shown "
                "neither to detect arm O's effect nor to miss it; unavailable is never a pass"
            ),
        )
    judged = _judged(interval, which="positive-control", committed=contract_alpha())
    position = judged.position
    if position == "above_zero":
        return PositiveControlReading(
            verdict="detected",
            position=position,
            interval=judged,
            explanation=(
                f"the interval {judged.describe()} lies entirely above zero: at the replicate "
                "count it was run at, the harness detects arm O's advantage over arm E"
            ),
        )
    if position == "contains_zero":
        return PositiveControlReading(
            verdict="not_detected",
            position=position,
            interval=judged,
            explanation=(
                f"the interval {judged.describe()} contains zero: the instrument cannot "
                "distinguish arm O from arm E at the replicate count it was run at -- a fact "
                "about the instrument's power (the Power_Report's subject), not about either arm"
            ),
        )
    return PositiveControlReading(
        verdict="not_detected",
        position=position,
        interval=judged,
        explanation=(
            f"the interval {judged.describe()} lies entirely below zero: it excludes zero on "
            "the wrong side, which R6.2's wording correction exists to refuse. Whether the "
            "harness is mis-measuring is classify_agreement's verdict (R6.4); this reading "
            "does not report arm O as under-performing"
        ),
    )


def agreement_difference(harness: JudgedInterval, comparator: JudgedInterval) -> JudgedInterval:
    """The interval on ``harness.point - comparator.point``, by :data:`AGREEMENT_METHOD`.

    Under :data:`AGREEMENT_ASSUMPTION` each standard error is ``(high - low) / (2 z)`` and the
    difference's half-width is ``z * sqrt(se_h^2 + se_c^2)``. At one shared ``alpha`` that
    reduces to ``sqrt(w_h^2 + w_c^2)`` over the half-widths ``w = (high - low) / 2``: z cancels,
    so it is not computed. The cancellation is also why one ``alpha`` is required -- at two
    levels the half-widths are in different units. Addition and multiplication commute, so
    swapping the two arguments negates the interval exactly.

    Raises:
        ValueError: When the two intervals were estimated at different ``alpha``, or when an
            input is so wide that the difference interval is not finite.
    """
    if harness.alpha != comparator.alpha:
        raise ValueError(
            f"the two estimates were made at alpha={harness.alpha!r} and "
            f"alpha={comparator.alpha!r}; their half-widths are in different units, so no "
            "difference interval is formed"
        )
    harness_half = (harness.high - harness.low) / 2.0
    comparator_half = (comparator.high - comparator.low) / 2.0
    half = math.sqrt(harness_half * harness_half + comparator_half * comparator_half)
    point = harness.point - comparator.point
    return JudgedInterval(low=point - half, high=point + half, point=point, alpha=harness.alpha)


def classify_agreement(
    *,
    harness: IntervalBounds | None,
    comparator: IntervalBounds | None,
    ceiling: IntervalBounds | None,
) -> AgreementReading:
    """The re-cut R6.3 tolerance, read as R6.4 requires: :data:`AGREEMENT_RULE`.

    ``harness`` is the harness's interval on ``E - O`` -- the positive control's, comparator E's
    cost minus subject O's; ``comparator`` is the comparator's independently measured ``E - O``
    and ``ceiling`` its information ceiling ``E - D`` (``uplift/regret.py``'s
    ``achievable_information_value`` and ``information_ceiling``). Keyword-only, so the two
    estimates cannot be swapped by position.

    **Which clause reads what.** The disagreement clause is symmetric: swapping ``harness`` and
    ``comparator`` negates the difference interval exactly and leaves the clause unchanged. The
    ceiling clause reads the harness's low bound alone, because the harness is the instrument
    under judgement; whether the comparator's own split is admissible is ``uplift/regret.py``'s
    business. It is lenient on purpose -- it fires only when the two intervals are disjoint with
    the harness's above -- and its known blind side is the ceiling's: ``E - D`` is a lower bound
    on the value of perfect information (ADR-055 D2.8), so an arm D far from optimal can flag a
    correct harness. That error is a false stop, never a false agreement.

    Raises:
        ValueError: On a malformed interval or one at any ``alpha`` but the committed one --
            checked before absence, so a defect is never masked as ``unavailable``.
        IntervalUnavailableError: When the committed ``alpha`` cannot be read.
    """
    alpha = contract_alpha()
    judged_harness = _judged_or_none(harness, which="harness E - O", committed=alpha)
    judged_comparator = _judged_or_none(comparator, which="comparator E - O", committed=alpha)
    judged_ceiling = _judged_or_none(ceiling, which="information ceiling E - D", committed=alpha)
    if judged_harness is None or judged_comparator is None or judged_ceiling is None:
        labelled = (
            ("harness E - O", judged_harness),
            ("comparator E - O", judged_comparator),
            ("information ceiling E - D", judged_ceiling),
        )
        absent = ", ".join(label for label, judged in labelled if judged is None)
        return AgreementReading(
            verdict="unavailable",
            reasons=(),
            harness=judged_harness,
            comparator=judged_comparator,
            ceiling=judged_ceiling,
            difference=None,
            method=AGREEMENT_METHOD,
            assumption=AGREEMENT_ASSUMPTION,
            explanation=(
                f"no agreement verdict: {absent} absent. Without all three estimates the "
                "harness is shown neither to agree nor to mis-measure, and that is not a pass"
            ),
        )
    difference = agreement_difference(judged_harness, judged_comparator)
    reasons = _failed_clauses(judged_harness, difference, judged_ceiling)
    if not reasons:
        return AgreementReading(
            verdict="agrees",
            reasons=(),
            harness=judged_harness,
            comparator=judged_comparator,
            ceiling=judged_ceiling,
            difference=difference,
            method=AGREEMENT_METHOD,
            assumption=AGREEMENT_ASSUMPTION,
            explanation=(
                f"the harness's E - O {judged_harness.describe()} agrees with the comparator's "
                f"{judged_comparator.describe()} -- their difference interval "
                f"{difference.describe()} contains 0 -- and its low bound does not exceed the "
                f"information ceiling's high bound {judged_ceiling.high:.6g}"
            ),
        )
    clauses: list[str] = []
    if "disagrees_with_comparator" in reasons:
        clauses.append(
            f"its E - O {judged_harness.describe()} disagrees with the comparator's "
            f"{judged_comparator.describe()}: the difference interval {difference.describe()} "
            "excludes 0"
        )
    if "exceeds_information_ceiling" in reasons:
        clauses.append(
            f"its E - O low bound {judged_harness.low:.6g} exceeds the information ceiling's "
            f"(E - D) high bound {judged_ceiling.high:.6g}"
        )
    failed = "; ".join(clauses)
    return AgreementReading(
        verdict="harness_mis_measuring",
        reasons=reasons,
        harness=judged_harness,
        comparator=judged_comparator,
        ceiling=judged_ceiling,
        difference=difference,
        method=AGREEMENT_METHOD,
        assumption=AGREEMENT_ASSUMPTION,
        explanation=(
            f"the HARNESS is mis-measuring (R6.4): {failed}. Arm O is not reported as "
            "under-performing: an oracle effect outside the agreement rule is a defect of the "
            "instrument that measured it"
        ),
    )


def _failed_clauses(
    harness: JudgedInterval, difference: JudgedInterval, ceiling: JudgedInterval
) -> tuple[MisMeasurement, ...]:
    """:data:`AGREEMENT_RULE`'s failed clauses, in :data:`MisMeasurement` order.

    The ONE definition :func:`classify_agreement` and :class:`AgreementReading` share: the
    difference interval excludes 0, and the harness's ``E - O`` low bound lies above the
    ceiling's high bound -- strictly, so a low bound ON the ceiling's high bound is within it.
    """
    failed: list[MisMeasurement] = []
    if difference.position != "contains_zero":
        failed.append("disagrees_with_comparator")
    if harness.low > ceiling.high:
        failed.append("exceeds_information_ceiling")
    return tuple(failed)
