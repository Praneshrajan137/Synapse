"""Property-based test that a SYNAPSE win must clear significance, MDE, and direction.

Feature: core-purpose-uplift, Property 19: SYNAPSE_WINS requires significance and MDE.

    *For any* consensus and baseline samples, if ``MetricContract.classify`` returns
    ``SYNAPSE_WINS`` then the significance test is significant at the contract ``alpha``
    AND ``|d| >= mde[kpi]`` AND the effect favors consensus in the KPI's improvement
    direction.

    Requirement 6.4: a SYNAPSE win is gated on all three conditions together — a
    significant result alone, a large effect alone, or a favorable direction alone must
    never be reported as a win.

**The quoted conditions are FALSE by decision as worded; the three-gate claim is kept.**
Metric_Contract v2 (decision-quality-proof task 29.4, decision 2=a) has no rank test, no Cohen's
d and no per-KPI direction: a win is read off the contract's ``1 - alpha`` paired interval on
``mean(comparator - consensus)`` of the committed objective, against the committed materiality
margin ``m``. The tag line is kept so the property stays traceable; what is asserted is each
gate's v2 analogue, all three together:

* *significant at the contract alpha* -> the ``1 - alpha`` interval excludes zero, on either
  side;
* *``|d| >= mde[kpi]``* -> the WHOLE interval lies more than the margin away from zero:
  ``low > m`` or ``high < -m``, which is stricter than the point estimate doing so;
* *favours consensus in the improvement direction* -> the mean paired difference, comparator
  minus consensus, is positive: the objective is a cost, so positive means consensus is cheaper.

All three together are exactly ``low > m``, which is the v2 rule's ``win``; any one alone -- a
significant loss, a large loss, a favourable but unresolved gain -- is not.

The gates are recomputed here *independently* of ``uplift.contract``: the interval comes straight
from the estimator, ``uplift.interval.paired_difference_interval``, called with the orientation,
confidence level, resample count and seed the contract commits; the gain is re-derived with
``statistics.fmean``; and the comparisons against ``0`` and ``m`` are written out here. Nothing of
``MetricContract.interval``, ``.verdict``, ``interval_verdict`` or ``outcome_for_verdict`` is
reused, so the assertion cannot be satisfied by the helper the rule under test uses. (The
estimator itself is shared: it is Property 60's subject, decision-quality-proof.)

The drawn contract is the real pre-registered one *or* a variant of a rule input v2 still lets
vary: a looser and a stricter confidence level (``alpha`` 0.5 and 0.01), a margin no drawn gain
reaches, and a margin almost any gain clears. Because the implication is checked against
whichever contract was handed to ``classify``, each variant pins the *necessity* of one gate.
v1's ``mde = 0.0`` and flipped-direction variants cannot be built under v2 -- construction
refuses both (``test_contract_schema.py``) -- so the direction gate is pinned by drawn gains of
BOTH signs instead. A near-zero ``alpha`` is not drawn: the resample count is derived from
``alpha`` (``resamples_for``), and ``1e-9`` would derive one no test budget could pay for.

A sufficiency check guards the property against vacuity: when all three gates hold, the outcome
must actually *be* ``SYNAPSE_WINS`` — so the test cannot pass merely because no win was ever
produced.

Pure and fast: ``classify`` is exercised directly on synthetic sample arrays — no twin
runs, no consensus assembly, no sockets, $0. Budget inherited from the root ``conftest.py``
profile; no ``max_examples`` literal.

**Validates: Requirements 6.4**
"""
from __future__ import annotations

import dataclasses
import statistics
from typing import TYPE_CHECKING

from hypothesis import event, given, settings
from hypothesis import strategies as st

from uplift.contract import MetricContract, load_contract
from uplift.interfaces import Outcome
from uplift.interval import (
    INTERVAL_SEED,
    IntervalUnavailableError,
    paired_difference_interval,
    resamples_for,
)

if TYPE_CHECKING:
    from uplift.interval import Interval

# The real, version-controlled contract: primary KPI ``objective`` (lower is better),
# ``alpha = 0.05``, the paired percentile bootstrap, MDE = the committed materiality margin.
_CONTRACT = load_contract()
_PRIMARY_KPI = _CONTRACT.objective_kpi
_MARGIN = _CONTRACT.materiality_margin

# KPI names that are *not* primary in the contract -- ``fill_rate``, v1's primary KPI, among
# them: these have no declared margin, so they can never be a SYNAPSE win.
_NON_PRIMARY_KPIS = ("fill_rate", "spoilage_rate", "margin", "co2_estimate", "unknown_kpi")


def _contract_variants() -> tuple[MetricContract, ...]:
    """The real contract plus one mutation per gate input v2 lets vary (alpha, the margin)."""
    return (
        _CONTRACT,
        dataclasses.replace(_CONTRACT, alpha=0.5),  # a 50% interval: significance is easier
        dataclasses.replace(_CONTRACT, alpha=0.01),  # a 99% interval: significance is harder
        dataclasses.replace(
            _CONTRACT, mde={_PRIMARY_KPI: 100.0 * _MARGIN}
        ),  # the margin is unreachable: drawn gains stay within five margins
        dataclasses.replace(
            _CONTRACT, mde={_PRIMARY_KPI: 1e-9 * _MARGIN}
        ),  # the margin admits almost any gain
    )


_CONTRACTS = _contract_variants()


# ---------------------------------------------------------------------------
# Independent recomputation of the three gates
# ---------------------------------------------------------------------------
def _independent_interval(
    consensus: list[float], baseline: list[float], contract: MetricContract
) -> Interval | None:
    """The interval on ``mean(baseline - consensus)``, straight from the estimator.

    The orientation (comparator first), the confidence level (the contract's ``alpha``), the
    resample count (``resamples_for(alpha)``) and the seed (``INTERVAL_SEED``) are the ones the
    contract commits, supplied here rather than read through ``MetricContract.interval``.
    ``None`` when no interval exists -- unpaired or empty samples, a non-finite difference, an
    overflow -- and no interval is never a win.
    """
    try:
        return paired_difference_interval(
            baseline,
            consensus,
            alpha=contract.alpha,
            resamples=resamples_for(contract.alpha),
            seed=INTERVAL_SEED,
        )
    except (IntervalUnavailableError, OverflowError):
        return None


def _independent_gain(consensus: list[float], baseline: list[float]) -> float | None:
    """``fmean(baseline - consensus)`` re-derived, or ``None`` when the arrays do not pair."""
    if not consensus or len(consensus) != len(baseline):
        return None
    return statistics.fmean(b - c for b, c in zip(baseline, consensus, strict=True))


# ---------------------------------------------------------------------------
# Strategies — shaped so wins, sub-margin gains, ties, and losses are all reachable
# ---------------------------------------------------------------------------
# Offsets scaled by a per-case spread give each arm a real distribution (non-zero
# variance), so the paired differences vary and the interval has width.
_offsets = st.floats(min_value=-1.0, max_value=1.0, allow_nan=False, allow_infinity=False)

# Gains (comparator minus consensus) in units of the margin: "no separation" (inconclusive),
# "small" (positive but under the margin, a sub-margin gain at these spreads), and "large",
# in both directions (consensus cheaper / consensus dearer).
_gains_in_margins = st.sampled_from((0.0, 0.05, -0.05, 0.5, -0.5, 1.5, -1.5, 4.0, -4.0))


@st.composite
def _cases(draw: st.DrawFn) -> tuple[list[float], list[float], str, MetricContract]:
    """Consensus/baseline objectives, a KPI name, and the contract to classify under.

    One replicate count is drawn for both arms, because ``classify`` pairs element by
    element; an occasional extra baseline replicate leaves the arrays unpaired, where no
    interval exists and no win may be reported.
    """
    centre = draw(st.floats(min_value=5.0, max_value=50.0))
    spread = draw(st.floats(min_value=0.0125, max_value=0.125)) * _MARGIN
    gain = draw(_gains_in_margins) * _MARGIN

    n = draw(st.integers(min_value=1, max_value=12))
    extra = draw(st.sampled_from((0, 0, 0, 1)))
    baseline = [centre + spread * draw(_offsets) for _ in range(n + extra)]
    consensus = [centre - gain + spread * draw(_offsets) for _ in range(n)]

    kpi = draw(
        st.one_of(
            st.just(_PRIMARY_KPI),
            st.just(_PRIMARY_KPI),
            st.sampled_from(_NON_PRIMARY_KPIS),
        )
    )
    return consensus, baseline, kpi, draw(st.sampled_from(_CONTRACTS))


@settings(deadline=None)
@given(case=_cases())
def test_synapse_wins_requires_significance_and_mde(
    case: tuple[list[float], list[float], str, MetricContract],
) -> None:
    """A SYNAPSE win implies an interval that excludes 0, clears the margin, and favours us."""
    consensus, baseline, kpi, contract = case

    outcome = contract.classify(consensus, baseline, kpi)

    adjudicable = kpi in contract.primary_kpis and kpi in contract.mde
    interval = _independent_interval(consensus, baseline, contract) if adjudicable else None
    gain = _independent_gain(consensus, baseline)
    margin = contract.materiality_margin

    significant = interval is not None and (interval.low > 0.0 or interval.high < 0.0)
    clears_margin = interval is not None and (interval.low > margin or interval.high < -margin)
    favors_consensus = gain is not None and gain > 0.0

    event(f"outcome: {outcome.value}")

    if outcome is Outcome.SYNAPSE_WINS:
        # (a) The KPI must be adjudicable at all: declared primary, with a margin.
        assert adjudicable, (
            f"SYNAPSE_WINS reported for KPI '{kpi}', which the contract does not "
            "declare as primary with an MDE"
        )
        # (b) Significant at the contract's alpha: the 1 - alpha interval excludes zero.
        assert significant, (
            f"SYNAPSE_WINS reported on the interval {interval}, which does not exclude zero "
            f"at alpha={contract.alpha}"
        )
        # (c) The effect is at least the declared MDE: the whole interval clears the margin.
        assert clears_margin, (
            f"SYNAPSE_WINS reported on the interval {interval}, which does not lie more than "
            f"the materiality margin {margin} away from zero"
        )
        # (d) The effect favors consensus: on a cost, consensus is the cheaper arm.
        assert favors_consensus, (
            f"SYNAPSE_WINS reported with a mean paired gain of {gain}, which does not favor "
            "consensus on a lower-is-better objective"
        )
    elif adjudicable and significant and clears_margin and favors_consensus:
        # Non-vacuity: when every gate holds the rule must actually award the win, so the
        # implication above cannot pass by never producing SYNAPSE_WINS.
        raise AssertionError(
            f"every gate held (interval {interval} excludes 0 and lies more than the margin "
            f"{margin} from it; mean paired gain {gain} > 0) but classify returned {outcome}"
        )
