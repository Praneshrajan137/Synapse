"""Property-based test that a SYNAPSE win must clear significance, MDE, and direction.

Feature: core-purpose-uplift, Property 19: SYNAPSE_WINS requires significance and MDE.

    *For any* consensus and baseline samples, if ``MetricContract.classify`` returns
    ``SYNAPSE_WINS`` then the significance test is significant at the contract ``alpha``
    AND ``|d| >= mde[kpi]`` AND the effect favors consensus in the KPI's improvement
    direction.

    Requirement 6.4: a SYNAPSE win is gated on all three conditions together — a
    significant result alone, a large effect alone, or a favorable direction alone must
    never be reported as a win.

The three gate conditions are recomputed here *independently* of ``uplift.contract``:
Cohen's d is re-derived from ``statistics.mean``/``statistics.variance`` and the p-value
is taken straight from ``scipy.stats.mannwhitneyu``. So the assertion cannot be satisfied
by reusing the same helper the rule under test uses.

The drawn contract is the real pre-registered one *or* a mutated variant (near-zero
``alpha``, unreachable ``mde``, zero ``mde``, flipped improvement direction). Because the
implication is checked against whichever contract was handed to ``classify``, each
variant pins the *necessity* of one gate condition: with ``alpha = 1e-9`` a win requires
an implausibly small p-value, with ``mde = 50.0`` no reachable effect qualifies, and with
the direction flipped the favorable sign inverts.

A sufficiency check guards the property against vacuity: when all three conditions hold
and the effect is non-zero, the outcome must actually *be* ``SYNAPSE_WINS`` — so the test
cannot pass merely because no win was ever produced.

Pure and fast: ``classify`` is exercised directly on synthetic sample arrays — no twin
runs, no consensus assembly, no sockets, $0.

**Validates: Requirements 6.4**
"""
from __future__ import annotations

import dataclasses
import math
import statistics

from hypothesis import event, given, settings
from hypothesis import strategies as st
from scipy import stats

from uplift.contract import MetricContract, load_contract
from uplift.interfaces import Direction, Outcome

# The real, version-controlled contract: primary KPI ``fill_rate`` (higher is better),
# ``alpha = 0.05``, ``mde = 0.2``, Mann-Whitney U.
_CONTRACT = load_contract()
_PRIMARY_KPI = next(iter(_CONTRACT.primary_kpis))

# KPI names that are *not* primary in the contract: these have no declared MDE or
# direction, so they can never be a SYNAPSE win.
_NON_PRIMARY_KPIS = ("spoilage_rate", "margin", "co2_estimate", "unknown_kpi")


def _contract_variants() -> tuple[MetricContract, ...]:
    """The real contract plus one mutation per gate input (alpha, MDE, direction)."""
    flipped = (
        Direction.LOWER_IS_BETTER
        if _CONTRACT.primary_kpis[_PRIMARY_KPI] is Direction.HIGHER_IS_BETTER
        else Direction.HIGHER_IS_BETTER
    )
    return (
        _CONTRACT,
        dataclasses.replace(_CONTRACT, alpha=1e-9),  # significance nearly unreachable
        dataclasses.replace(
            _CONTRACT, mde={**_CONTRACT.mde, _PRIMARY_KPI: 50.0}
        ),  # MDE unreachable
        dataclasses.replace(
            _CONTRACT, mde={**_CONTRACT.mde, _PRIMARY_KPI: 0.0}
        ),  # MDE admits any effect
        dataclasses.replace(
            _CONTRACT, primary_kpis={**_CONTRACT.primary_kpis, _PRIMARY_KPI: flipped}
        ),  # favorable sign inverted
    )


_CONTRACTS = _contract_variants()


# ---------------------------------------------------------------------------
# Independent recomputation of the three gate conditions
# ---------------------------------------------------------------------------
def _independent_cohens_d(consensus: list[float], baseline: list[float]) -> float:
    """Pooled-SD Cohen's d re-derived from ``statistics``, not from ``uplift.contract``."""
    n1, n2 = len(consensus), len(baseline)
    if n1 == 0 or n2 == 0 or n1 + n2 - 2 <= 0:
        return 0.0
    if not all(math.isfinite(v) for v in (*consensus, *baseline)):
        return 0.0
    var_c = statistics.variance(consensus) if n1 > 1 else 0.0
    var_b = statistics.variance(baseline) if n2 > 1 else 0.0
    pooled_var = ((n1 - 1) * var_c + (n2 - 1) * var_b) / (n1 + n2 - 2)
    if not math.isfinite(pooled_var) or pooled_var <= 0.0:
        return 0.0
    d = (statistics.fmean(consensus) - statistics.fmean(baseline)) / math.sqrt(pooled_var)
    return d if math.isfinite(d) else 0.0


def _independent_pvalue(consensus: list[float], baseline: list[float]) -> float | None:
    """Two-sided Mann-Whitney U p-value, or ``None`` when the test is undefined."""
    if not consensus or not baseline:
        return None
    if not all(math.isfinite(v) for v in (*consensus, *baseline)):
        return None
    try:
        p_value = float(stats.mannwhitneyu(consensus, baseline, alternative="two-sided")[1])
    except ValueError:
        return None
    return p_value if math.isfinite(p_value) else None


# ---------------------------------------------------------------------------
# Strategies — shaped so wins, losses, and ties are all reachable
# ---------------------------------------------------------------------------
# Offsets scaled by a per-case spread give each arm a real distribution (non-zero
# variance) so Cohen's d and the rank test are both defined.
_offsets = st.floats(min_value=-1.0, max_value=1.0, allow_nan=False, allow_infinity=False)

# Shifts span "no separation" (tie), "small" (significant but under the 0.2 MDE at these
# spreads), and "large" in both directions (consensus better / baseline better).
_shifts = st.sampled_from((0.0, 0.001, -0.001, 0.01, -0.01, 0.05, -0.05, 0.3, -0.3))


@st.composite
def _cases(draw: st.DrawFn) -> tuple[list[float], list[float], str, MetricContract]:
    """Consensus/baseline samples, a KPI name, and the contract to classify under."""
    centre = draw(st.floats(min_value=0.1, max_value=0.9))
    spread = draw(st.floats(min_value=0.005, max_value=0.05))
    shift = draw(_shifts)

    n_c = draw(st.integers(min_value=1, max_value=12))
    n_b = draw(st.integers(min_value=1, max_value=12))
    baseline = [centre + spread * draw(_offsets) for _ in range(n_b)]
    consensus = [centre + shift + spread * draw(_offsets) for _ in range(n_c)]

    kpi = draw(
        st.one_of(
            st.just(_PRIMARY_KPI),
            st.just(_PRIMARY_KPI),
            st.sampled_from(_NON_PRIMARY_KPIS),
        )
    )
    return consensus, baseline, kpi, draw(st.sampled_from(_CONTRACTS))


@settings(max_examples=200, deadline=None)
@given(case=_cases())
def test_synapse_wins_requires_significance_and_mde(
    case: tuple[list[float], list[float], str, MetricContract],
) -> None:
    """A SYNAPSE win implies significance at alpha, ``|d| >= mde``, and favorability."""
    consensus, baseline, kpi, contract = case

    outcome = contract.classify(consensus, baseline, kpi)
    d = _independent_cohens_d(consensus, baseline)
    p_value = _independent_pvalue(consensus, baseline)

    significant = p_value is not None and p_value < contract.alpha
    meets_mde = kpi in contract.mde and abs(d) >= contract.mde[kpi]
    direction = contract.primary_kpis.get(kpi)
    favors_consensus = direction is not None and (
        d > 0.0 if direction is Direction.HIGHER_IS_BETTER else d < 0.0
    )

    event(f"outcome: {outcome.value}")

    if outcome is Outcome.SYNAPSE_WINS:
        # (a) The KPI must be adjudicable at all: declared primary, with an MDE.
        assert kpi in contract.primary_kpis and kpi in contract.mde, (
            f"SYNAPSE_WINS reported for KPI '{kpi}', which the contract does not "
            "declare as primary with an MDE"
        )
        # (b) Significant at the contract's alpha.
        assert significant, (
            f"SYNAPSE_WINS reported at p={p_value} which is not significant at "
            f"alpha={contract.alpha}"
        )
        # (c) Effect at least the declared Minimum_Detectable_Effect.
        assert meets_mde, (
            f"SYNAPSE_WINS reported at |d|={abs(d)} below mde[{kpi}]="
            f"{contract.mde[kpi]}"
        )
        # (d) The effect favors consensus in the KPI's improvement direction.
        assert favors_consensus, (
            f"SYNAPSE_WINS reported with d={d} which does not favor consensus for a "
            f"{direction} KPI"
        )
    elif significant and meets_mde and favors_consensus and d != 0.0:
        # Non-vacuity: when every gate condition holds the rule must actually award the
        # win, so the implication above cannot pass by never producing SYNAPSE_WINS.
        raise AssertionError(
            f"all gate conditions held (p={p_value} < {contract.alpha}, |d|={abs(d)} >= "
            f"{contract.mde[kpi]}, favorable for {direction}) but classify returned "
            f"{outcome}"
        )
