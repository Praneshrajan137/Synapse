"""Property-based test that every headline number carries its fidelity context.

Feature: core-purpose-uplift
Property 13: Every headline number is co-located with its fidelity context

    *For any* :class:`~uplift.interfaces.UpliftResult`, the rendered uplift report
    contains the headline number together with the twin KL value, its comparison to the
    threshold, the confidence annotation, and the fidelity-bound statement in one place.

    Requirement 3.5: "WHERE the operator requests a fully-powered proof, THE
    Uplift_Harness SHALL emit the Headline_Uplift number co-located in the same output
    with its Fidelity_Bound report."

    The test builds ``HarnessResult`` / ``ScenarioRun`` data directly and calls
    :func:`uplift.harness.build_uplift_report` — no twin runs, no consensus assembly —
    so it is pure, fast, and network-free ($0, I-1). The ``FidelityReport`` is varied
    across available/unavailable KL values and within/outside the committed threshold so
    every branch of the co-located fidelity block is exercised.

**Validates: Requirements 3.5**
"""
from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from uplift.contract import load_contract
from uplift.fidelity import (
    CONFIDENCE_LOW_DIVERGENT,
    CONFIDENCE_UNKNOWN,
    CONFIDENCE_WITHIN_BOUND,
    FIDELITY_BOUND_STATEMENT,
    FidelityReport,
)
from uplift.harness import (
    DEFAULT_CONSENSUS_ARM,
    HarnessResult,
    aggregate_arm,
    assemble_uplift_result,
    build_uplift_report,
)
from uplift.interfaces import KpiVector, Scenario, ScenarioRun

from digital_twin.simulation.monte_carlo import ShockParams

# The real, version-controlled metric contract (single primary KPI ``fill_rate``).
_CONTRACT = load_contract()

# Strictly positive fill rates keep the pooled baseline mean non-zero so the headline's
# relative-change denominator is defined for every generated grid.
_FILL_RATES = st.floats(
    min_value=0.05, max_value=1.0, allow_nan=False, allow_infinity=False
)
_KL_VALUES = st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)
_THRESHOLDS = st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)


def _kpi(fill_rate: float) -> KpiVector:
    return KpiVector(
        fill_rate=fill_rate,
        spoilage_rate=0.0,
        stockout_rate=0.0,
        avg_delivery_time_min=1.0,
        margin=1.0,
        co2_estimate=1.0,
    )


def _runs(arm: str, fill_rates: list[float], *, failed: bool) -> list[ScenarioRun]:
    """Runs for one ``(scenario, arm)`` pair, either all completed or all failed."""
    if failed:
        return [
            ScenarioRun(arm=arm, seed=index, kpis=None, failed=True, error="synthetic")
            for index, _ in enumerate(fill_rates)
        ]
    return [
        ScenarioRun(arm=arm, seed=index, kpis=_kpi(value), failed=False, error=None)
        for index, value in enumerate(fill_rates)
    ]


@st.composite
def _results(draw: st.DrawFn) -> tuple[HarnessResult, FidelityReport]:
    """A synthetic harness grid plus a varied fidelity report.

    The grid is deliberately small (1-2 scenarios x 1-2 baseline arms, 2-3 replicates)
    because co-location is a rendering property, not a sample-size property. Pairs are
    allowed to fail so incomplete results (headline ``0.0``) are covered too — the
    fidelity context must accompany *every* headline number, including that one.

    The fidelity report is drawn so all three branches occur: KL unavailable
    (``None``), KL at or below the threshold, and KL strictly above it.
    """
    n_scenarios = draw(st.integers(min_value=1, max_value=2))
    n_baselines = draw(st.integers(min_value=1, max_value=2))
    n_replicates = draw(st.integers(min_value=2, max_value=3))
    arm_names = (DEFAULT_CONSENSUS_ARM, *(f"baseline-{i}" for i in range(n_baselines)))

    scenarios = [
        Scenario(
            name=f"scenario-{index}",
            seed=6001 + index,
            shock=ShockParams(demand_multiplier=1.0),
        )
        for index in range(n_scenarios)
    ]

    runs_by_pair: dict[tuple[str, str], list[ScenarioRun]] = {}
    for scenario in scenarios:
        for arm in arm_names:
            fill_rates = draw(
                st.lists(_FILL_RATES, min_size=n_replicates, max_size=n_replicates)
            )
            failed = draw(st.booleans())
            runs_by_pair[(scenario.name, arm)] = _runs(arm, fill_rates, failed=failed)

    harness_result = HarnessResult(
        arm_results={
            pair: aggregate_arm(pair[1], runs) for pair, runs in runs_by_pair.items()
        },
        runs_by_pair=runs_by_pair,
        all_runs=[run for runs in runs_by_pair.values() for run in runs],
        results_path=None,
        scenarios=tuple(scenarios),
        arm_names=arm_names,
    )

    fidelity = FidelityReport(
        kl_divergence=draw(st.none() | _KL_VALUES),
        threshold=draw(_THRESHOLDS),
    )
    return harness_result, fidelity


@settings(max_examples=200, deadline=None)
@given(case=_results())
def test_headline_is_co_located_with_its_fidelity_context(
    case: tuple[HarnessResult, FidelityReport],
) -> None:
    """The rendered report holds the headline and its full fidelity context together."""
    harness_result, fidelity = case

    result = assemble_uplift_result(harness_result, _CONTRACT, fidelity=fidelity)
    report = build_uplift_report(result)

    # The report carries the assembled headline unchanged, plus the fidelity fields.
    assert report.headline_uplift == float(result.headline_uplift)
    assert report.kl_divergence == fidelity.kl_divergence
    assert report.threshold == fidelity.threshold
    assert report.confidence == fidelity.confidence
    assert report.fidelity_bound_statement == FIDELITY_BOUND_STATEMENT

    rendered = report.render()

    # (1) the headline number itself
    assert f"{report.headline_uplift:+.4f}" in rendered
    # (2) the twin KL value (or its explicit unavailability)
    if fidelity.kl_divergence is None:
        assert report.within_fidelity_bound is None
        assert report.confidence == CONFIDENCE_UNKNOWN
        assert "twin KL divergence: unavailable" in rendered
    else:
        assert f"{fidelity.kl_divergence:.6f}" in rendered
        # (3) its comparison to the committed threshold
        if fidelity.kl_divergence <= fidelity.threshold:
            assert report.within_fidelity_bound is True
            assert report.confidence == CONFIDENCE_WITHIN_BOUND
            assert "<= threshold" in rendered
        else:
            assert report.within_fidelity_bound is False
            assert report.confidence == CONFIDENCE_LOW_DIVERGENT
            assert "> threshold" in rendered
    assert f"{fidelity.threshold:.6f}" in rendered
    # (4) the confidence annotation
    assert f"fidelity confidence: {report.confidence}" in rendered
    # (5) the fidelity-bound statement
    assert FIDELITY_BOUND_STATEMENT in rendered

    # ... and all five live in ONE place: a single contiguous block with no blank line
    # separating the headline from its fidelity context.
    lines = rendered.splitlines()
    assert all(line.strip() for line in lines), rendered
    assert lines[0].startswith("headline uplift:")
    assert lines[-1] == FIDELITY_BOUND_STATEMENT
