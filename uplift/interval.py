"""The two-sided interval at ``1 - alpha`` -- a paired percentile bootstrap.

Feature: decision-quality-proof, design section **E3.1** (R6.13, R7.14). This is the
estimator half of task 15.2, brought forward out of session 3 because checkpoint A needs it:
without an interval, ``uplift.regret.classify_regret`` reaches its ``material`` branch on a
bare point estimate, and ``material`` is the verdict that STOPS this spec by falsifying
Finding 4. Stopping a 132-task plan on a number with no dispersion is not a decision anybody
should be asked to make. See ``HANDOFF.md``'s conflict record.

**What is estimated.** A paired bootstrap over replicate-aligned samples. The statistic is
the mean paired difference, which is exactly ``RegretObjective.regret``'s estimator
(``fmean(policy) - fmean(reference)``) and exactly the headline uplift's, so one estimator
serves both call sites rather than two disagreeing about what "95%" means.

**Why ``random.Random`` and not numpy.** I-1 and a dependency fact, in that order. Stdlib
only means the estimator replays byte-identically anywhere, and it means this module imports
into ``uplift.yml::twin-regret``'s deliberately thin closure (``packages/requirements.txt``
plus ``simpy numpy pyyaml``) without dragging anything else in.

**Why ``alpha`` is read here with ``yaml`` rather than through**
``uplift.contract.load_contract`` **, which is what task 15.2 asked for.** ``contract.py``
imports ``scipy`` at module scope, for the Mann-Whitney test it also owns. ``scipy`` is in
neither ``packages/requirements.txt`` nor ``packages/requirements-dev.txt``; it reaches
``ci.yml::uplift-verify`` transitively through ``agents/*/requirements.txt``, which
``twin-regret`` does not install. So routing this one float through the validating reader
would make the regret measurement fail at import with ``ModuleNotFoundError`` inside the job
that exists to run it. The narrow read below is the resolution, and the drift it could
introduce is closed mechanically rather than promised away:
``tests/uplift/test_interval_estimation_property.py`` asserts the two readers return the same
number, and it runs in the fast suite where ``scipy`` is present. Two readers of one artifact
with nothing comparing them is the ``None == None`` shape C75 exists to close.

**The figure "95%" appears nowhere as a literal.** It is ``1 - alpha`` from
``uplift/metric_contract.yaml``'s committed ``0.05`` (AD-13).
"""

from __future__ import annotations

import dataclasses
import math
import random
import statistics
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final

import yaml

if TYPE_CHECKING:
    from collections.abc import Sequence

__all__ = [
    "CONTRACT_PATH",
    "INTERVAL_SEED",
    "METHOD",
    "TAIL_ORDER_STATISTICS",
    "Interval",
    "IntervalUnavailableError",
    "contract_alpha",
    "headline_interval",
    "paired_difference_interval",
    "resamples_for",
]

#: The pre-registered Metric_Contract artifact. Same path ``uplift.contract`` reads.
CONTRACT_PATH: Final[Path] = Path(__file__).with_name("metric_contract.yaml")

#: Recorded in every :class:`Interval` so a reader knows which estimator produced the bounds.
#: An interval whose method is not stated is not reproducible, and R7.14 asks for the interval
#: to accompany the headline "in the same output" -- a bound with no method is not that.
METHOD: Final[str] = "paired_percentile_bootstrap"

#: The one chosen input to the resample count, flagged exactly as ``service_points`` and the
#: ``delivery_latency`` weight are flagged. It is the number of resample statistics that must
#: lie beyond EACH tail bound of a ``1 - alpha`` interval, so the bound is an order statistic
#: with company rather than the single most extreme draw. At the committed ``alpha = 0.05``
#: this derives ``50 / 0.025 = 2000`` resamples.
#:
#: Deliberately NOT a bare ``2000``: a resample count restated as a literal is a number with
#: no antecedent, and this one follows from ``alpha`` plus one judgement. Unlike the
#: materiality margin it has no self-serving sign -- a wider or narrower interval helps
#: nobody in particular -- so it carries no ``ratchets.json`` direction, on the same reasoning
#: that file's header gives for the objective weights.
TAIL_ORDER_STATISTICS: Final[int] = 50

#: The committed resampling seed. **Its value is immaterial; its fixity is the point.** The
#: interval must be a pure function of ``(samples, alpha, resamples, seed)`` so it replays
#: byte-identically from the recorded fields (task 15.1's ``ArtifactInterval.seed``).
#:
#: THE HONESTY CLAUSE, because this is the one knob here that could be abused: the seed must
#: never be re-chosen after an interval has been seen. Re-seeding until a lower bound clears
#: a floor, or until an interval excludes a margin, is metric-shopping with extra steps -- the
#: pattern task 25's pre-commitment forbids and the reason the margin's rule was pre-registered
#: separately from its value.
INTERVAL_SEED: Final[int] = 0


class IntervalUnavailableError(Exception):
    """No admissible interval could be estimated. Never substituted with a bound.

    Raised rather than returning a widened or clamped interval, on the same reasoning
    ``PolicyUnavailableError`` is raised rather than defaulting a policy key: a bound nobody
    estimated is indistinguishable, to every downstream reader, from one that was. I-7 makes
    ``unavailable`` a first-class state, so the caller reports it and fails rather than
    judging against a number the data did not support.
    """


def contract_alpha(path: Path = CONTRACT_PATH) -> float:
    """The Metric_Contract's committed significance level, or raise naming the file.

    A deliberately narrow read of one key -- see the module docstring for why this does not go
    through :func:`uplift.contract.load_contract`, and for the test that stops the two readers
    drifting. Validated in the open interval ``(0, 1)`` exactly as ``MetricContract`` validates
    it, because an ``alpha`` outside that range yields percentile probabilities outside
    ``[0, 1]`` and the interval would be nonsense rather than merely wrong.
    """
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as error:
        raise IntervalUnavailableError(
            f"the metric contract at {path.as_posix()} could not be read: {error}"
        ) from error
    if not isinstance(raw, dict) or "alpha" not in raw:
        raise IntervalUnavailableError(
            f"the metric contract at {path.as_posix()} declares no 'alpha'. This is NOT "
            "defaulted: the interval's confidence level is a pre-registered quantity and a "
            "substituted one would make '1 - alpha' a number nobody committed"
        )
    value = raw["alpha"]
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise IntervalUnavailableError(
            f"the metric contract at {path.as_posix()} declares a non-numeric alpha "
            f"{value!r}"
        )
    alpha = float(value)
    if not math.isfinite(alpha) or not 0.0 < alpha < 1.0:
        raise IntervalUnavailableError(
            f"the metric contract at {path.as_posix()} declares alpha={alpha!r}, which is "
            "not in the open interval (0, 1)"
        )
    return alpha


def resamples_for(alpha: float, *, tail_order_statistics: int = TAIL_ORDER_STATISTICS) -> int:
    """The resample count ``alpha`` derives, given the one flagged choice.

    ``ceil(tail_order_statistics / (alpha / 2))``: enough resamples that each tail bound of a
    two-sided ``1 - alpha`` interval is the ``tail_order_statistics``-th order statistic rather
    than the single most extreme draw. At the committed ``alpha = 0.05`` this is ``2000``.
    """
    if not math.isfinite(alpha) or not 0.0 < alpha < 1.0:
        raise IntervalUnavailableError(
            f"cannot derive a resample count from alpha={alpha!r}: alpha must lie in the open "
            "interval (0, 1)"
        )
    if tail_order_statistics < 1:
        raise IntervalUnavailableError(
            f"tail_order_statistics must be at least 1, got {tail_order_statistics!r}; a tail "
            "bound read off zero order statistics is not an estimate"
        )
    return int(math.ceil(tail_order_statistics / (alpha / 2.0)))


@dataclasses.dataclass(frozen=True)
class Interval:
    """A two-sided interval at ``1 - alpha`` on a mean paired difference.

    The seven fields are exactly the ones task 15.1's ``ArtifactInterval`` declares
    (``method``, ``alpha``, ``resamples``, ``seed``, ``low``, ``high``, ``point``), so that
    model is constructed from :meth:`as_dict` rather than recomputing anything. **The split is
    deliberate and is a stated deviation from design E3.1's declared return type:** E3.1 has
    :func:`headline_interval` return ``ArtifactInterval`` directly, but that model lives in
    ``uplift/harness.py``, and importing the harness here would pull the twin, the arm
    machinery and numpy into ``uplift.regret``'s fast import path -- which that module goes out
    of its way to keep light. So this frozen record is the *computation* form and
    ``ArtifactInterval`` is the *serialisation* form, with the field names pinned to each other
    by name. Recorded in ``HANDOFF.md`` rather than absorbed silently.
    """

    method: str
    alpha: float
    resamples: int
    seed: int
    low: float
    high: float
    point: float

    def __post_init__(self) -> None:
        """Refuse an inadmissible interval rather than record one.

        Two conditions, both checked because both have been reasoned about rather than
        assumed. ``low <= high`` is arithmetic hygiene. ``low <= point <= high`` is the
        substantive one: design E3.1 claims the interval brackets the point estimate, and the
        percentile bootstrap of a mean does not *guarantee* that -- the bootstrap distribution
        is centred on the sample mean but its tails are draws, so a sufficiently degenerate
        resample set can miss it. When that happens the honest report is that no interval was
        estimated, NOT a bound silently widened to contain the point (which would make the
        bracketing claim unfalsifiable) and not a bound left not containing it (which would
        make ``excludes`` meaningless).
        """
        for name, value in (("low", self.low), ("high", self.high), ("point", self.point)):
            if not math.isfinite(value):
                raise IntervalUnavailableError(
                    f"interval {name}={value!r} is not finite, so no bound was estimated"
                )
        if self.low > self.high:
            raise IntervalUnavailableError(
                f"interval bounds are inverted: low={self.low!r} > high={self.high!r}"
            )
        if not self.low <= self.point <= self.high:
            raise IntervalUnavailableError(
                f"the estimated interval [{self.low!r}, {self.high!r}] does not bracket the "
                f"point estimate {self.point!r}. Reported unavailable rather than widened: a "
                "bound adjusted to satisfy the claim made about it proves nothing"
            )
        if self.resamples < 1:
            raise IntervalUnavailableError(
                f"an interval cannot be estimated from resamples={self.resamples!r}"
            )

    @property
    def bounds(self) -> tuple[float, float]:
        """``(low, high)``, the shape ``classify_regret``'s ``interval=`` argument takes."""
        return (self.low, self.high)

    @property
    def width(self) -> float:
        """``high - low``. Non-negative by construction."""
        return self.high - self.low

    def excludes(self, value: float) -> bool:
        """Whether ``value`` lies strictly outside the closed interval.

        Strict on both sides, and that is load-bearing for R5.13: a closed interval whose
        endpoint sits exactly ON the materiality margin *contains* it, so it excludes nothing
        and must not license ``material``. Session 1r found this the hard way -- a property
        built its "excluding" interval from an absolute width and asserted ``material`` for an
        interval that touched the margin. ``classify_regret`` was right to refuse it.
        """
        return value < self.low or value > self.high

    def as_dict(self) -> dict[str, Any]:
        """The seven declared fields, for task 15.1's ``ArtifactInterval`` and for reports."""
        return dataclasses.asdict(self)

    def describe(self) -> str:
        """ASCII one-liner naming the confidence level and the estimator, never a bare pair."""
        return (
            f"[{self.low:.6g}, {self.high:.6g}] at {(1.0 - self.alpha) * 100.0:.6g}% "
            f"(point {self.point:.6g}, {self.method}, resamples={self.resamples}, "
            f"seed={self.seed})"
        )


def _nearest_rank(sorted_statistics: list[float], probability: float) -> float:
    """The nearest-rank percentile of an ascending list. No interpolation, stated once.

    ``ceil(p * n) - 1``, clamped into range. Interpolation is deliberately avoided: it invents
    a value no resample produced, and at the tails -- which is exactly where a ``1 - alpha``
    bound is read -- that invention is between the two draws that matter most.
    """
    count = len(sorted_statistics)
    index = int(math.ceil(probability * count)) - 1
    return sorted_statistics[min(count - 1, max(0, index))]


def paired_difference_interval(
    first: Sequence[float],
    second: Sequence[float],
    *,
    alpha: float,
    resamples: int,
    seed: int,
) -> Interval:
    """Interval on ``mean(first) - mean(second)``, paired elementwise (R6.13, R7.14).

    Paired because a shared replicate seed yields an identical demand realisation across arms
    (R2.1/R2.5), so the per-seed difference removes demand variance from the contrast. Equal
    lengths are REQUIRED, mirroring ``RegretObjective.regret``: an unpaired difference is a
    different estimator with a different variance, and silently computing it would misreport
    precision -- which is the whole quantity this function exists to report.

    **Order-invariance, and a correction to design E3.1.** The design said sorting the resample
    *statistics* makes the result invariant to input order. It does not: the seeded index
    stream is fixed, so permuting the inputs changes which values each resample draws and
    therefore changes the statistics themselves, sorted or not. Sorting the statistics is what
    makes percentile extraction well defined. Input-order invariance needs the *paired
    differences* sorted before resampling -- which loses nothing, because the bootstrap
    distribution of a mean depends only on the multiset of differences. Both sorts are applied
    below. This is the same argument ``uplift/harness.py`` makes when it sorts by seed before
    aggregating so worker scheduling cannot move the low bits.

    Raises:
        IntervalUnavailableError: On unequal or empty inputs, non-finite values, an ``alpha``
            outside ``(0, 1)``, a non-positive ``resamples``, or an estimated interval that
            does not bracket the point estimate.
    """
    if len(first) != len(second):
        raise IntervalUnavailableError(
            f"a paired interval needs equal sample counts, got {len(first)} and {len(second)}; "
            "an unpaired difference is a different estimator with a different variance"
        )
    if not first:
        raise IntervalUnavailableError(
            "a paired interval needs at least one replicate; nothing was measured"
        )
    if not math.isfinite(alpha) or not 0.0 < alpha < 1.0:
        raise IntervalUnavailableError(
            f"alpha={alpha!r} is not in the open interval (0, 1), so '1 - alpha' names no "
            "confidence level"
        )
    if resamples < 1:
        raise IntervalUnavailableError(
            f"resamples={resamples!r} is not a resample count; use resamples_for(alpha)"
        )

    differences = [float(a) - float(b) for a, b in zip(first, second, strict=True)]
    for value in differences:
        if not math.isfinite(value):
            raise IntervalUnavailableError(
                "a paired difference is not finite, so no interval was estimated; the "
                "replicate that produced it is evidence of a failed run, not of a wide bound"
            )

    point = statistics.fmean(differences)

    # Sorted BEFORE resampling -- this is the order-invariance mechanism, see the docstring.
    ordered = sorted(differences)
    count = len(ordered)
    rng = random.Random(seed)
    statistics_drawn: list[float] = [
        statistics.fmean([ordered[rng.randrange(count)] for _ in range(count)])
        for _ in range(resamples)
    ]
    # Sorted AFTER resampling -- this is what makes the percentile well defined.
    statistics_drawn.sort()

    return Interval(
        method=METHOD,
        alpha=alpha,
        resamples=resamples,
        seed=seed,
        low=_nearest_rank(statistics_drawn, alpha / 2.0),
        high=_nearest_rank(statistics_drawn, 1.0 - alpha / 2.0),
        point=point,
    )


def headline_interval(
    consensus: Sequence[float],
    baseline: Sequence[float],
    *,
    alpha: float,
    resamples: int,
    seed: int,
) -> Interval:
    """Design E3.1's declared entry point: the interval on the headline uplift.

    A thin alias for :func:`paired_difference_interval` under E3.1's parameter names, so the
    uplift call site reads in its own vocabulary and the regret call site reads in its. There
    is exactly one estimator; this is not a second one. Keeping the declared name and signature
    means task 15.2's remaining half -- wiring ``assemble_uplift_result`` once task 15.1's
    ``ArtifactInterval`` exists -- calls what the design says it calls.
    """
    return paired_difference_interval(
        consensus, baseline, alpha=alpha, resamples=resamples, seed=seed
    )
