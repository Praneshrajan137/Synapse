"""
SYNAPSE Decision-Integrity Uplift Proof — pre-registered metric contract, version 2.

Loads the version-controlled ``uplift/metric_contract.yaml`` artifact into an
immutable :class:`MetricContract` (R3.1, R3.3, R3.4, R3.6, R3.9) and exposes the
deterministic decision rule ``MetricContract.classify``.

The contract is *pre-registered*: it declares the primary KPI and its direction, the
effect-size measure, the interval estimator, the significance level ``alpha``, the
Minimum_Detectable_Effect, and the decision rule BEFORE any result is produced, so an
uplift result cannot be manufactured by metric-shopping after the fact. The harness reads
the contract from this file rather than embedding thresholds ad hoc in analysis code.

**Version 2 (decision-quality-proof task 29.4, decision 2=a, finding 64).** Version 1 judged
``fill_rate`` alone with a two-sample Mann-Whitney test and a Cohen's-d MDE. ``fill_rate``
rises with stock, so an arm that simply holds more inventory beat the lean tuned control on
it while LOSING on the committed objective (inferred from the metric, not measured). Version 2
makes the ADR-055 D2 scalar objective the sole primary KPI, lower is better; every other
``KpiVector`` field is secondary (R7.19). The decision rule is four-valued and is read off the
``1 - alpha`` paired interval on the mean objective difference (comparator minus subject) --
see :func:`interval_verdict`. This reader accepts version 2 ONLY: a version-1 contract is
refused, not translated, because a v1 MDE is a Cohen's d and the v2 rule reads a margin in
objective units -- silently reusing one as the other is exactly the defect this repairs.

**The MDE is not a number in this file.** It is the committed materiality margin, resolved at
load time from :func:`digital_twin.simulation.policy.materiality_margin`, which re-derives it
from its pre-registered rule (ADR-055 D2.5) and refuses a value the rule does not produce.
One canonical home for that number; this contract names it rather than restating it.

A missing or malformed contract is a first-class, honest failure: :func:`load_contract`
raises a typed :class:`MetricContractError`, and the harness/CLI exits with a failure
status reporting the contract as invalid and producing *no* uplift outcome (R3.10).
"""
from __future__ import annotations

import dataclasses
import math
import numbers
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final

import numpy as np
import yaml

from digital_twin.simulation.policy import PolicyUnavailableError, materiality_margin
from uplift.interfaces import Direction, HeadlineVerdict, KpiVector, Outcome
from uplift.interval import (
    INTERVAL_SEED,
    METHOD,
    Interval,
    IntervalUnavailableError,
    paired_difference_interval,
    resamples_for,
)

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

# Canonical location of the version-controlled metric-contract artifact.
DEFAULT_CONTRACT_PATH: Path = Path(__file__).with_name("metric_contract.yaml")

#: The one contract version this reader accepts. Any other is refused (task 29.4).
CONTRACT_VERSION: Final[int] = 2

#: The sole primary KPI of version 2: the ADR-055 D2 committed scalar objective.
OBJECTIVE_KPI: Final[str] = "objective"

# The set of KPI names the contract may reference: exactly the KpiVector fields.
_VALID_KPIS: frozenset[str] = frozenset(f.name for f in dataclasses.fields(KpiVector))

#: The effect-size measure version 2 declares: the mean paired difference of the objective,
#: comparator minus subject, on matched replicate seeds -- the estimator ADR-055 D2.4 commits.
_SUPPORTED_EFFECT_SIZE: Final[str] = "mean_paired_difference"

#: The interval estimator version 2 declares. Read from ``uplift.interval`` so the contract
#: and the estimator cannot name two different methods.
_SUPPORTED_SIGNIFICANCE_TEST: Final[str] = METHOD

#: The decision rule version 2 declares (R7.19); see :func:`interval_verdict`.
_SUPPORTED_DECISION_RULE: Final[str] = "interval_position_against_materiality_margin"

#: The only value an ``mde`` entry may carry: a reference to the committed materiality margin,
#: resolved at load time. A number written here would be a second opinion about that margin.
MDE_FROM_POLICY: Final[str] = "materiality_margin"

#: The decision rule in words, reported beside every verdict so a reader never has to infer it.
DECISION_RULE_TEXT: Final[str] = (
    "win iff the 1 - alpha interval's LOW bound is strictly above the materiality margin; "
    "sub_margin_gain iff it is strictly above 0 but not above the margin; inconclusive iff the "
    "interval contains 0; baseline_wins iff its HIGH bound is strictly below 0"
)

# The required top-level keys of the contract schema. ``version`` is required: an absent
# version cannot be assumed to be 2, because assuming it would be a default.
_REQUIRED_KEYS: frozenset[str] = frozenset(
    {
        "version",
        "primary_kpis",
        "effect_size",
        "significance_test",
        "alpha",
        "mde",
        "decision_rule",
    }
)

#: How each headline verdict maps onto the legacy per-(scenario, KPI) ``Outcome`` grid.
#: ``sub_margin_gain`` maps to ``TIE_INCONCLUSIVE``, which is how version 1 treated a
#: significant gain below its MDE (significant but ``|d| < mde`` was a tie): a gain that does
#: not clear the margin is not a material win. ``baseline_wins`` needs no margin -- a loss the
#: interval excludes from zero is a loss at any size, which is stricter AGAINST the subject
#: than version 1 (a significant sub-MDE loss was a tie there).
_VERDICT_OUTCOMES: Final[Mapping[HeadlineVerdict, Outcome]] = {
    "win": Outcome.SYNAPSE_WINS,
    "sub_margin_gain": Outcome.TIE_INCONCLUSIVE,
    "inconclusive": Outcome.TIE_INCONCLUSIVE,
    "baseline_wins": Outcome.BASELINE_WINS,
}


class MetricContractError(Exception):
    """Raised when the metric contract is missing or malformed (R3.10).

    The harness/CLI treats this as a terminal, honest failure: it exits with a
    failure status reporting the contract as invalid and never produces an uplift
    outcome. It is intentionally a single typed error so every malformed-contract
    path — missing file, unparseable YAML, schema violation, out-of-range ``alpha``,
    a version other than 2, a primary KPI other than the objective, a numeric or
    unresolvable MDE — is caught uniformly.
    """


# ---------------------------------------------------------------------------
# Effect-size helpers (R3.2). No longer the decision rule under version 2; retained because
# they are importable, independently tested measures (Property 13) that reports may quote.
# ---------------------------------------------------------------------------
def _as_finite_float_array(samples: Any) -> np.ndarray:
    """Coerce ``samples`` to a 1-D float ``ndarray``; empty on any coercion failure.

    Totality helper: never raises. A value that cannot be interpreted as a numeric
    array yields an empty array, which the callers treat as a degenerate (no-effect)
    input rather than an error (Property 12).
    """
    try:
        arr = np.asarray(samples, dtype=float).ravel()
    except (TypeError, ValueError):
        return np.empty(0, dtype=float)
    return arr


def cohens_d(consensus: Any, baseline: Any) -> float:
    """Pooled-standard-deviation Cohen's d of ``consensus`` vs ``baseline`` (R3.2).

    Reference formula::

        d = (mean(consensus) - mean(baseline)) / s_pooled

        s_pooled = sqrt( ((n1 - 1) * var(consensus) + (n2 - 1) * var(baseline))
                         / (n1 + n2 - 2) )

    where ``var`` is the sample variance (``ddof=1``). A positive ``d`` means the
    consensus arm's mean is higher than the baseline arm's mean; a negative ``d``
    means it is lower.

    Total and deterministic: returns ``0.0`` (no measurable effect) for any degenerate
    input — an empty array, a combined sample too small to pool (``n1 + n2 - 2 <= 0``),
    a non-finite value (NaN/inf), or a zero pooled standard deviation — instead of
    raising or returning NaN (Property 12).
    """
    c = _as_finite_float_array(consensus)
    b = _as_finite_float_array(baseline)
    n1, n2 = c.size, b.size
    if n1 == 0 or n2 == 0:
        return 0.0
    if not (np.all(np.isfinite(c)) and np.all(np.isfinite(b))):
        return 0.0
    if n1 + n2 - 2 <= 0:
        return 0.0
    var_c = float(np.var(c, ddof=1)) if n1 > 1 else 0.0
    var_b = float(np.var(b, ddof=1)) if n2 > 1 else 0.0
    pooled_var = ((n1 - 1) * var_c + (n2 - 1) * var_b) / (n1 + n2 - 2)
    if not math.isfinite(pooled_var) or pooled_var <= 0.0:
        return 0.0
    pooled_std = math.sqrt(pooled_var)
    d = (float(np.mean(c)) - float(np.mean(b))) / pooled_std
    return d if math.isfinite(d) else 0.0


def relative_pct_change(consensus: Any, baseline: Any) -> float:
    """Relative percentage change of the consensus mean over the baseline mean (R3.2).

    Reference formula::

        rel_pct = (mean(consensus) - mean(baseline)) / mean(baseline) * 100.0

    Total and deterministic: returns ``0.0`` for any degenerate input — an empty
    array, a non-finite value, or a zero baseline mean (undefined denominator) —
    instead of raising or returning NaN/inf (Property 12).
    """
    c = _as_finite_float_array(consensus)
    b = _as_finite_float_array(baseline)
    if c.size == 0 or b.size == 0:
        return 0.0
    if not (np.all(np.isfinite(c)) and np.all(np.isfinite(b))):
        return 0.0
    mean_b = float(np.mean(b))
    if mean_b == 0.0 or not math.isfinite(mean_b):
        return 0.0
    rel = (float(np.mean(c)) - mean_b) / mean_b * 100.0
    return rel if math.isfinite(rel) else 0.0


# ---------------------------------------------------------------------------
# The version-2 decision rule (R7.19)
# ---------------------------------------------------------------------------
def interval_verdict(low: float, high: float, *, margin: float) -> HeadlineVerdict:
    """The four-valued verdict an interval licenses against the materiality margin (R7.19).

    STRICT bounds, and the strictness is the point: a closed interval whose low bound sits
    exactly ON the margin contains it, so it is a ``sub_margin_gain`` and not a ``win``; one
    whose low or high bound is exactly ``0`` contains zero, so it is ``inconclusive``.

    * ``win`` iff ``low > margin``;
    * ``sub_margin_gain`` iff ``0 < low <= margin``;
    * ``inconclusive`` iff ``low <= 0 <= high``;
    * ``baseline_wins`` iff ``high < 0``.

    Exhaustive and mutually exclusive whenever ``low <= high`` and ``margin > 0``, which is
    why both are REFUSED rather than assumed: an inverted or non-finite interval, or a margin
    that is not strictly positive, has no verdict, and returning one would be a fabrication.

    Raises:
        ValueError: On a non-finite bound or margin, ``low > high``, or ``margin <= 0``.
    """
    for name, value in (("low", low), ("high", high), ("margin", margin)):
        if not math.isfinite(value):
            raise ValueError(f"no verdict for a non-finite {name}={value!r}")
    if low > high:
        raise ValueError(f"no verdict for an inverted interval: low={low!r} > high={high!r}")
    if margin <= 0.0:
        raise ValueError(
            f"no verdict against margin={margin!r}: the materiality margin must be strictly "
            "positive, or every gain would be material by construction"
        )
    if low > margin:
        return "win"
    if low > 0.0:
        return "sub_margin_gain"
    if high >= 0.0:
        return "inconclusive"
    return "baseline_wins"


def outcome_for_verdict(verdict: HeadlineVerdict) -> Outcome:
    """The legacy ``Outcome`` a headline verdict maps to (see :data:`_VERDICT_OUTCOMES`)."""
    return _VERDICT_OUTCOMES[verdict]


@dataclasses.dataclass(frozen=True)
class MetricContract:
    """Immutable, validated view of the pre-registered metric contract, version 2 (R3).

    Built by :func:`load_contract` from the version-controlled ``metric_contract.yaml``.
    **Construction itself validates** (``__post_init__``), so no in-memory contract can be a
    version-1 contract, judge a KPI other than the objective, or carry a margin that is not a
    strictly positive finite number -- including one made by ``dataclasses.replace``:

    - ``primary_kpis`` — exactly ``{"objective": Direction.LOWER_IS_BETTER}`` (R3.1, R7.19).
    - ``effect_size`` — ``"mean_paired_difference"`` (R3.2, ADR-055 D2.4).
    - ``significance_test`` — the interval estimator, ``uplift.interval.METHOD`` (R3.3).
    - ``alpha`` — significance level in the open interval ``(0, 1)`` (R3.3); the interval is
      estimated at ``1 - alpha``.
    - ``mde`` — ``{"objective": m}``, where ``m`` is the committed materiality margin resolved
      at load time, in objective units (R3.4).
    - ``decision_rule`` — ``"interval_position_against_materiality_margin"`` (R3.5).
    - ``version`` — exactly :data:`CONTRACT_VERSION`.
    """

    primary_kpis: dict[str, Direction]
    effect_size: str
    significance_test: str
    alpha: float
    mde: dict[str, float]
    decision_rule: str
    version: int

    def __post_init__(self) -> None:
        """Refuse any contract this reader cannot apply exactly as declared (R3.7)."""
        if isinstance(self.version, bool) or self.version != CONTRACT_VERSION:
            raise MetricContractError(
                f"metric contract version {self.version!r} is not supported: this reader "
                f"accepts version {CONTRACT_VERSION} only. Version 1 judged fill_rate with a "
                "Cohen's-d MDE; version 2 judges the committed objective against the "
                "materiality margin, and one is never silently read as the other"
            )
        if self.primary_kpis != {OBJECTIVE_KPI: Direction.LOWER_IS_BETTER}:
            raise MetricContractError(
                f"primary_kpis must be exactly {{{OBJECTIVE_KPI!r}: 'lower'}} under version "
                f"{CONTRACT_VERSION}; got {self.primary_kpis!r}. The objective is a cost and the "
                "sole primary KPI; every other KpiVector field is secondary (R7.19)"
            )
        if self.effect_size != _SUPPORTED_EFFECT_SIZE:
            raise MetricContractError(
                f"effect_size must be '{_SUPPORTED_EFFECT_SIZE}'; got {self.effect_size!r}"
            )
        if self.significance_test != _SUPPORTED_SIGNIFICANCE_TEST:
            raise MetricContractError(
                f"significance_test must be '{_SUPPORTED_SIGNIFICANCE_TEST}', the interval "
                f"estimator uplift.interval implements; got {self.significance_test!r}"
            )
        if (
            isinstance(self.alpha, bool)
            or not isinstance(self.alpha, numbers.Real)
            or not math.isfinite(float(self.alpha))
            or not 0.0 < float(self.alpha) < 1.0
        ):
            raise MetricContractError(
                f"alpha must be in the open interval (0, 1); got {self.alpha!r}"
            )
        if set(self.mde) != {OBJECTIVE_KPI}:
            raise MetricContractError(
                f"mde must declare exactly the primary KPI {OBJECTIVE_KPI!r}; got keys "
                f"{sorted(self.mde)}"
            )
        margin = self.mde[OBJECTIVE_KPI]
        if (
            isinstance(margin, bool)
            or not isinstance(margin, numbers.Real)
            or not math.isfinite(float(margin))
            or float(margin) <= 0.0
        ):
            raise MetricContractError(
                f"the objective's MDE (the materiality margin) must be a strictly positive "
                f"finite number; got {margin!r}"
            )
        if self.decision_rule != _SUPPORTED_DECISION_RULE:
            raise MetricContractError(
                f"decision_rule must be '{_SUPPORTED_DECISION_RULE}'; got {self.decision_rule!r}"
            )

    @property
    def objective_kpi(self) -> str:
        """The sole primary KPI's name, ``"objective"``."""
        return OBJECTIVE_KPI

    @property
    def materiality_margin(self) -> float:
        """The MDE, in objective units: the committed materiality margin resolved at load."""
        return float(self.mde[OBJECTIVE_KPI])

    @property
    def resamples(self) -> int:
        """The bootstrap resample count ``alpha`` derives (``uplift.interval.resamples_for``)."""
        return resamples_for(self.alpha)

    def interval(self, subject: Sequence[float], comparator: Sequence[float]) -> Interval:
        """The ``1 - alpha`` paired interval on ``mean(comparator - subject)``, objective units.

        Signed so a POSITIVE value means the subject is cheaper -- the subject wins on a cost.
        ``alpha`` is this contract's, the resample count is the one ``alpha`` derives, and the
        seed is the committed ``uplift.interval.INTERVAL_SEED``, so the interval replays from
        the recorded fields. The two sequences must already be paired element by element on
        matched replicate seeds; pairing is the caller's job and is never done by position here.

        Raises:
            IntervalUnavailableError: On unequal or empty inputs, a non-finite difference, or
                an estimated interval that does not bracket its point estimate.
        """
        return paired_difference_interval(
            comparator, subject, alpha=self.alpha, resamples=self.resamples, seed=INTERVAL_SEED
        )

    def verdict(self, interval: Interval) -> HeadlineVerdict:
        """The four-valued verdict ``interval`` licenses against this contract's margin."""
        return interval_verdict(interval.low, interval.high, margin=self.materiality_margin)

    def classify(
        self, consensus: Sequence[float], baseline: Sequence[float], kpi: str
    ) -> Outcome:
        """Return the one-of-three :class:`Outcome` for one primary-KPI comparison (R3.5).

        ``consensus`` and ``baseline`` are per-replicate objective samples ALREADY PAIRED on
        matched replicate seeds (element ``i`` of each comes from one seed). The rule is the
        version-2 interval rule, applied exactly as declared: estimate :meth:`interval`, read
        :meth:`verdict`, map it through :func:`outcome_for_verdict`.

        Totality (Property 12): the function returns exactly one ``Outcome`` for any float
        input and never raises. A KPI that is not the primary KPI, and any input for which no
        interval can be estimated -- unequal or empty samples, a non-finite difference, an
        arithmetic overflow -- resolve deterministically to ``TIE_INCONCLUSIVE``: no interval
        is never a verdict. Identical inputs always yield the identical outcome, because the
        estimator is seeded.
        """
        if kpi not in self.primary_kpis:
            return Outcome.TIE_INCONCLUSIVE
        try:
            estimated = self.interval(consensus, baseline)
        except (IntervalUnavailableError, OverflowError):
            return Outcome.TIE_INCONCLUSIVE
        return outcome_for_verdict(self.verdict(estimated))


def _coerce_direction(kpi: str, raw: Any) -> Direction:
    """Coerce a raw ``primary_kpis`` value into a :class:`Direction` (R3.1)."""
    if isinstance(raw, Direction):
        return raw
    if isinstance(raw, str):
        try:
            return Direction(raw)
        except ValueError:
            pass
    raise MetricContractError(
        f"primary_kpis['{kpi}'] direction must be one of "
        f"{[d.value for d in Direction]}; got {raw!r}"
    )


def _resolve_mde(raw_mde: Any, source: Path) -> dict[str, float]:
    """Resolve the ``mde`` block: each entry must NAME the committed margin, never state it.

    Raises:
        MetricContractError: On a non-mapping or empty block, an entry that is not the
            :data:`MDE_FROM_POLICY` reference (a number included), or a margin the policy
            reader cannot supply -- unreadable, refused by its own rule, or not yet instantiated.
    """
    if not isinstance(raw_mde, dict) or not raw_mde:
        raise MetricContractError(
            f"mde must be a non-empty mapping of primary KPI -> {MDE_FROM_POLICY!r}"
        )
    for kpi, raw_value in raw_mde.items():
        if raw_value != MDE_FROM_POLICY:
            raise MetricContractError(
                f"mde['{kpi}'] must be the reference {MDE_FROM_POLICY!r}; got {raw_value!r}. "
                "The MDE is the committed materiality margin, resolved from "
                "digital_twin/simulation/policy.py::materiality_margin() -- a number written "
                "here would be a second home for it"
            )
    try:
        margin = materiality_margin()
    except PolicyUnavailableError as exc:
        raise MetricContractError(
            f"metric contract at {source} resolves its MDE from the committed materiality "
            f"margin, which could not be read: {exc}"
        ) from exc
    if margin is None:
        raise MetricContractError(
            f"metric contract at {source} resolves its MDE from the committed materiality "
            "margin, which is not instantiated (regret_objective.materiality_margin.value is "
            "null). A version-2 contract cannot judge anything without it"
        )
    return {str(kpi): float(margin) for kpi in raw_mde}


def _validate_and_build(data: Any, source: Path) -> MetricContract:
    """Validate the parsed contract mapping and build an immutable ``MetricContract``.

    Enforces the schema, known KPI names and directions, a numeric ``alpha``, and the MDE
    reference here; :meth:`MetricContract.__post_init__` then refuses anything version 2 does
    not declare (R3.1, R3.3, R3.4). Any violation raises :class:`MetricContractError` (R3.10).
    """
    if not isinstance(data, dict):
        raise MetricContractError(
            f"metric contract at {source} must be a mapping; got {type(data).__name__}"
        )

    missing = _REQUIRED_KEYS - data.keys()
    if missing:
        raise MetricContractError(
            f"metric contract at {source} is missing required keys: {sorted(missing)}"
        )

    version = data["version"]
    if isinstance(version, bool) or not isinstance(version, int):
        raise MetricContractError(f"version must be an integer; got {version!r}")

    # --- primary_kpis: non-empty mapping of known KPI -> direction (R3.1) ---
    raw_primary = data["primary_kpis"]
    if not isinstance(raw_primary, dict) or not raw_primary:
        raise MetricContractError(
            "primary_kpis must be a non-empty mapping of KPI name -> direction"
        )
    primary_kpis: dict[str, Direction] = {}
    for kpi, raw_dir in raw_primary.items():
        if kpi not in _VALID_KPIS:
            raise MetricContractError(
                f"primary_kpis references unknown KPI '{kpi}'; "
                f"valid KPIs are {sorted(_VALID_KPIS)}"
            )
        primary_kpis[kpi] = _coerce_direction(kpi, raw_dir)

    # --- significance_test: non-empty string (R3.3); its value is checked on construction ---
    significance_test = data["significance_test"]
    if not isinstance(significance_test, str) or not significance_test.strip():
        raise MetricContractError("significance_test must be a non-empty string")

    # --- alpha: a real number (R3.3); its range is checked on construction ---
    alpha = data["alpha"]
    if isinstance(alpha, bool) or not isinstance(alpha, numbers.Real):
        raise MetricContractError(f"alpha must be a real number; got {alpha!r}")

    return MetricContract(
        primary_kpis=primary_kpis,
        effect_size=data["effect_size"],
        significance_test=significance_test,
        alpha=float(alpha),
        mde=_resolve_mde(data["mde"], source),
        decision_rule=data["decision_rule"],
        version=version,
    )


def load_contract(path: str | Path = DEFAULT_CONTRACT_PATH) -> MetricContract:
    """Load and validate the metric contract into an immutable :class:`MetricContract`.

    Reads the version-controlled YAML artifact at ``path`` (defaults to the
    co-located ``metric_contract.yaml``), validates it, resolves its MDE from the committed
    materiality margin, and returns the immutable contract.

    Raises :class:`MetricContractError` on any missing or malformed contract — a
    non-existent file, unreadable/unparseable YAML, a version other than 2, or any
    schema/range violation — so the caller exits with a failure status and produces no
    uplift outcome (R3.10).
    """
    contract_path = Path(path)
    try:
        raw_text = contract_path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise MetricContractError(
            f"metric contract not found at {contract_path}"
        ) from exc
    except OSError as exc:
        raise MetricContractError(
            f"metric contract at {contract_path} could not be read: {exc}"
        ) from exc

    try:
        data = yaml.safe_load(raw_text)
    except yaml.YAMLError as exc:
        raise MetricContractError(
            f"metric contract at {contract_path} is not valid YAML: {exc}"
        ) from exc

    if data is None:
        raise MetricContractError(f"metric contract at {contract_path} is empty")

    return _validate_and_build(data, contract_path)


__all__ = [
    "CONTRACT_VERSION",
    "DECISION_RULE_TEXT",
    "DEFAULT_CONTRACT_PATH",
    "MDE_FROM_POLICY",
    "OBJECTIVE_KPI",
    "MetricContract",
    "MetricContractError",
    "cohens_d",
    "interval_verdict",
    "load_contract",
    "outcome_for_verdict",
    "relative_pct_change",
]
