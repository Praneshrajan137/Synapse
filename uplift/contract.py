"""
SYNAPSE Decision-Integrity Uplift Proof — pre-registered metric contract.

Loads the version-controlled ``uplift/metric_contract.yaml`` artifact into an
immutable :class:`MetricContract` (R3.1, R3.3, R3.4, R3.6, R3.9) and exposes the
deterministic decision rule ``MetricContract.classify`` (implemented in task 5.3).

The contract is *pre-registered*: it declares the primary KPI(s) + directions, the
effect-size measure, the significance test, the significance level ``alpha``, the
per-KPI Minimum_Detectable_Effect, and the decision rule BEFORE any result is
produced, so an uplift result cannot be manufactured by metric-shopping after the
fact. The harness reads the contract from this file rather than embedding thresholds
ad hoc in analysis code.

A missing or malformed contract is a first-class, honest failure: :func:`load_contract`
raises a typed :class:`MetricContractError`, and the harness/CLI exits with a failure
status reporting the contract as invalid and producing *no* uplift outcome (R3.10).
"""
from __future__ import annotations

import dataclasses
import math
import numbers
from pathlib import Path
from typing import Any

import numpy as np
import yaml
from scipy import stats

from uplift.interfaces import Direction, KpiVector, Outcome

# Canonical location of the version-controlled metric-contract artifact.
DEFAULT_CONTRACT_PATH: Path = Path(__file__).with_name("metric_contract.yaml")

# The set of KPI names the contract may reference: exactly the KpiVector fields.
_VALID_KPIS: frozenset[str] = frozenset(f.name for f in dataclasses.fields(KpiVector))

# The only effect-size measure and decision rule this contract version supports
# (R3.2, R3.5). The declared values must match these exactly.
_SUPPORTED_EFFECT_SIZE: str = "cohens_d+rel_pct"
_SUPPORTED_DECISION_RULE: str = "significant_and_favorable_and_meets_mde"

# The significance test the decision rule knows how to run. Any other declared test
# is treated deterministically as "no significant result" (never raises) so that
# ``classify`` remains a total function (Property 12).
_MANN_WHITNEY_U: str = "mann_whitney_u"

# The required top-level keys of the contract schema.
_REQUIRED_KEYS: frozenset[str] = frozenset(
    {"primary_kpis", "effect_size", "significance_test", "alpha", "mde", "decision_rule"}
)


class MetricContractError(Exception):
    """Raised when the metric contract is missing or malformed (R3.10).

    The harness/CLI treats this as a terminal, honest failure: it exits with a
    failure status reporting the contract as invalid and never produces an uplift
    outcome. It is intentionally a single typed error so every malformed-contract
    path — missing file, unparseable YAML, schema violation, out-of-range ``alpha``,
    empty primary KPIs, non-numeric MDE — is caught uniformly.
    """


# ---------------------------------------------------------------------------
# Effect-size computation (R3.2) — importable, referenced by property task 5.4
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
    means it is lower. The sign is interpreted against the KPI's improvement
    direction by :meth:`MetricContract.classify`.

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


def _significance_pvalue(test_name: str, consensus: Any, baseline: Any) -> float | None:
    """Return the declared significance test's p-value, or ``None`` when undefined.

    Runs the declared ``test_name`` on the two sample arrays and returns its
    two-sided p-value. Returns ``None`` — meaning "no significant result can be
    established" — for any degenerate input (empty array, non-finite value, both
    samples identical so the test is undefined) or an unrecognized test name, so
    the decision rule never raises and remains deterministic (Property 12).
    """
    c = _as_finite_float_array(consensus)
    b = _as_finite_float_array(baseline)
    if c.size == 0 or b.size == 0:
        return None
    if not (np.all(np.isfinite(c)) and np.all(np.isfinite(b))):
        return None
    if test_name != _MANN_WHITNEY_U:
        # Deterministic totality: an unknown test cannot establish significance.
        return None
    try:
        _, p_value = stats.mannwhitneyu(c, b, alternative="two-sided")
    except ValueError:
        # scipy raises when all values across both samples are identical.
        return None
    if p_value is None or not math.isfinite(float(p_value)):
        return None
    return float(p_value)


@dataclasses.dataclass(frozen=True)
class MetricContract:
    """Immutable, validated view of the pre-registered metric contract (R3).

    Built exclusively by :func:`load_contract` from the version-controlled
    ``metric_contract.yaml`` artifact. All fields are validated at load time so an
    in-memory ``MetricContract`` is always well-formed:

    - ``primary_kpis`` — non-empty mapping of primary KPI name -> improvement
      :class:`Direction` (R3.1).
    - ``effect_size`` — the declared effect-size measure, ``"cohens_d+rel_pct"`` (R3.2).
    - ``significance_test`` — the declared significance test, e.g. ``"mann_whitney_u"`` (R3.3).
    - ``alpha`` — significance level in the open interval ``(0, 1)`` (R3.3).
    - ``mde`` — per-primary-KPI numeric Minimum_Detectable_Effect (Cohen's d floor) (R3.4).
    - ``decision_rule`` — the declared decision-rule identifier (R3.5).
    - ``version`` — the artifact schema version.
    """

    primary_kpis: dict[str, Direction]
    effect_size: str
    significance_test: str
    alpha: float
    mde: dict[str, float]
    decision_rule: str
    version: int = 1

    def effect_sizes(self, consensus: Any, baseline: Any) -> tuple[float, float]:
        """Return ``(cohens_d, relative_pct_change)`` for consensus vs baseline (R3.2).

        Convenience accessor exposing both declared effect-size measures for
        reporting alongside the classification. Both values are total and
        deterministic (see :func:`cohens_d` and :func:`relative_pct_change`).
        """
        return cohens_d(consensus, baseline), relative_pct_change(consensus, baseline)

    def classify(self, consensus: Any, baseline: Any, kpi: str) -> Outcome:
        """Return the one-of-three :class:`Outcome` for a primary KPI comparison (R3.5).

        Total, deterministic mapping of ``(consensus samples, baseline samples, kpi)``
        to exactly one of ``{SYNAPSE_WINS, BASELINE_WINS, TIE_INCONCLUSIVE}`` applying
        the ``significant_and_favorable_and_meets_mde`` rule:

        - SYNAPSE_WINS iff the significance test is significant at ``alpha`` **and**
          ``|d| >= mde[kpi]`` **and** the effect favors the consensus arm in the KPI's
          improvement direction.
        - BASELINE_WINS iff significant **and** ``|d| >= mde[kpi]`` **and** the effect
          favors the baseline arm.
        - TIE_INCONCLUSIVE otherwise.

        Totality (Property 12): the function returns exactly one ``Outcome`` for any
        input and never raises. Non-primary KPIs, degenerate/empty/NaN/zero-variance
        arrays, and undefined significance tests all resolve deterministically to
        ``TIE_INCONCLUSIVE``. Identical inputs always yield the identical outcome.
        """
        # A KPI the contract does not declare as primary has no MDE / direction; it
        # cannot be adjudicated, so it is deterministically inconclusive (R3.8 labels
        # such KPIs secondary; here they never win or lose).
        direction = self.primary_kpis.get(kpi)
        if direction is None or kpi not in self.mde:
            return Outcome.TIE_INCONCLUSIVE

        d = cohens_d(consensus, baseline)
        p_value = _significance_pvalue(self.significance_test, consensus, baseline)

        significant = p_value is not None and p_value < self.alpha
        meets_mde = abs(d) >= self.mde[kpi]

        # The rule requires significance, a large-enough effect, and a directional
        # winner. Any missing precondition (incl. a zero-effect tie) is inconclusive.
        if not (significant and meets_mde) or d == 0.0:
            return Outcome.TIE_INCONCLUSIVE

        # Interpret the sign of d against the KPI's improvement direction. For a
        # higher-is-better KPI a positive d (consensus mean higher) favors consensus;
        # for a lower-is-better KPI a negative d (consensus mean lower) favors consensus.
        if direction is Direction.HIGHER_IS_BETTER:
            consensus_favored = d > 0.0
        else:  # Direction.LOWER_IS_BETTER
            consensus_favored = d < 0.0

        return Outcome.SYNAPSE_WINS if consensus_favored else Outcome.BASELINE_WINS


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


def _validate_and_build(data: Any, source: Path) -> MetricContract:
    """Validate the parsed contract mapping and build an immutable ``MetricContract``.

    Enforces the schema, ``alpha ∈ (0, 1)``, non-empty primary KPIs, and numeric MDEs
    (R3.1, R3.3, R3.4). Any violation raises :class:`MetricContractError` (R3.10).
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

    # --- effect_size: must be the supported measure (R3.2) ---
    effect_size = data["effect_size"]
    if effect_size != _SUPPORTED_EFFECT_SIZE:
        raise MetricContractError(
            f"effect_size must be '{_SUPPORTED_EFFECT_SIZE}'; got {effect_size!r}"
        )

    # --- significance_test: non-empty string (R3.3) ---
    significance_test = data["significance_test"]
    if not isinstance(significance_test, str) or not significance_test.strip():
        raise MetricContractError("significance_test must be a non-empty string")

    # --- alpha: numeric in the open interval (0, 1) (R3.3) ---
    alpha = data["alpha"]
    if isinstance(alpha, bool) or not isinstance(alpha, numbers.Real):
        raise MetricContractError(f"alpha must be a real number; got {alpha!r}")
    alpha = float(alpha)
    if not (0.0 < alpha < 1.0):
        raise MetricContractError(
            f"alpha must be in the open interval (0, 1); got {alpha}"
        )

    # --- mde: numeric MDE per primary KPI (R3.4) ---
    raw_mde = data["mde"]
    if not isinstance(raw_mde, dict) or not raw_mde:
        raise MetricContractError(
            "mde must be a non-empty mapping of primary KPI -> numeric effect-size floor"
        )
    mde: dict[str, float] = {}
    for kpi, raw_value in raw_mde.items():
        if isinstance(raw_value, bool) or not isinstance(raw_value, numbers.Real):
            raise MetricContractError(
                f"mde['{kpi}'] must be a real number; got {raw_value!r}"
            )
        mde[kpi] = float(raw_value)
    missing_mde = set(primary_kpis) - set(mde)
    if missing_mde:
        raise MetricContractError(
            f"mde must declare a value for every primary KPI; missing: {sorted(missing_mde)}"
        )

    # --- decision_rule: must be the supported rule (R3.5) ---
    decision_rule = data["decision_rule"]
    if decision_rule != _SUPPORTED_DECISION_RULE:
        raise MetricContractError(
            f"decision_rule must be '{_SUPPORTED_DECISION_RULE}'; got {decision_rule!r}"
        )

    # --- version: optional positive integer, defaults to 1 ---
    version = data.get("version", 1)
    if isinstance(version, bool) or not isinstance(version, int) or version < 1:
        raise MetricContractError(f"version must be a positive integer; got {version!r}")

    return MetricContract(
        primary_kpis=primary_kpis,
        effect_size=effect_size,
        significance_test=significance_test,
        alpha=alpha,
        mde=mde,
        decision_rule=decision_rule,
        version=version,
    )


def load_contract(path: str | Path = DEFAULT_CONTRACT_PATH) -> MetricContract:
    """Load and validate the metric contract into an immutable :class:`MetricContract`.

    Reads the version-controlled YAML artifact at ``path`` (defaults to the
    co-located ``metric_contract.yaml``), validates it (schema, ``alpha ∈ (0, 1)``,
    non-empty primary KPIs, numeric MDEs), and returns the immutable contract.

    Raises :class:`MetricContractError` on any missing or malformed contract — a
    non-existent file, unreadable/unparseable YAML, or any schema/range violation —
    so the caller exits with a failure status and produces no uplift outcome (R3.10).
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
