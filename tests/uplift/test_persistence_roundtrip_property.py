"""Property-based tests for recorded-run persistence round-trips.

Feature: decision-integrity-uplift-proof
Property 8: KPI_Vector persistence round-trips.

    *For any* set of recorded ``ScenarioRun``s (including failed runs with
    ``kpis=None`` and runs carrying finite float ``KpiVector`` values), persisting
    them and reloading them yields the identical list with each vector's arm
    identifier and scenario seed preserved.

Validates: Requirements 2.6
"""
from __future__ import annotations

import math

from hypothesis import given, settings
from hypothesis import strategies as st

from uplift.interfaces import KpiVector, ScenarioRun
from uplift.persistence import load_runs, save_runs

# ---------------------------------------------------------------------------
# Strategies
#
# A recorded run carries an arm id (text), a scenario seed (int), a failed flag,
# an optional error string, and an optional KpiVector. For the equality
# round-trip we use *finite* floats for the six KpiVector fields: json emits the
# shortest round-tripping repr for every float, so a finite value decodes back to
# the same IEEE-754 value and ``==`` on the frozen dataclasses holds. Non-finite
# values (nan/inf) are round-trippable by the impl too, but ``nan != nan`` makes a
# whole-list equality assertion unusable, so they are exercised in a dedicated
# test below using ``math.isnan``/``math.isinf`` checks.
# ---------------------------------------------------------------------------

_arms = st.text(min_size=0, max_size=32)
_seeds = st.integers(min_value=-(10**18), max_value=10**18)
_finite_floats = st.floats(allow_nan=False, allow_infinity=False)
_errors = st.none() | st.text(max_size=64)


def _kpi_vectors() -> st.SearchStrategy[KpiVector]:
    """A KpiVector with finite floats in every one of its six fields."""
    return st.builds(
        KpiVector,
        fill_rate=_finite_floats,
        spoilage_rate=_finite_floats,
        stockout_rate=_finite_floats,
        avg_delivery_time_min=_finite_floats,
        margin=_finite_floats,
        co2_estimate=_finite_floats,
    )


@st.composite
def _scenario_runs(draw: st.DrawFn) -> ScenarioRun:
    """A ScenarioRun that is either completed (has a KpiVector) or failed (kpis=None)."""
    failed = draw(st.booleans())
    kpis = None if failed else draw(st.none() | _kpi_vectors())
    error = draw(_errors) if failed else None
    return ScenarioRun(
        arm=draw(_arms),
        seed=draw(_seeds),
        kpis=kpis,
        failed=failed,
        error=error,
    )


_run_lists = st.lists(_scenario_runs(), max_size=25)


# ---------------------------------------------------------------------------
# Property 8: persist then reload yields the identical list (R2.6)
# ---------------------------------------------------------------------------
@settings(max_examples=200)
@given(runs=_run_lists)
def test_persistence_round_trips_identically(runs: list[ScenarioRun], tmp_path_factory) -> None:
    """load_runs(save_runs(runs, path)) equals the original runs (Property 8)."""
    path = tmp_path_factory.mktemp("uplift-runs") / "runs.json"

    written = save_runs(runs, path)
    reloaded = load_runs(written)

    # ScenarioRun and KpiVector are frozen dataclasses, so == compares by value,
    # including arm id, seed, and every KpiVector field.
    assert reloaded == runs

    # Explicitly assert arm id + seed preservation, element-wise (R2.6).
    for original, restored in zip(runs, reloaded, strict=True):
        assert restored.arm == original.arm
        assert restored.seed == original.seed


# ---------------------------------------------------------------------------
# Property 8 (non-finite variant): nan/inf KPI values survive the round-trip
#
# ``nan != nan`` so a whole-list == assertion cannot be used; instead we assert
# structural preservation (arm/seed/failed/error) and compare KPI fields with
# nan-aware equality.
# ---------------------------------------------------------------------------
_any_floats = st.floats(allow_nan=True, allow_infinity=True)


def _any_kpi_vectors() -> st.SearchStrategy[KpiVector]:
    return st.builds(
        KpiVector,
        fill_rate=_any_floats,
        spoilage_rate=_any_floats,
        stockout_rate=_any_floats,
        avg_delivery_time_min=_any_floats,
        margin=_any_floats,
        co2_estimate=_any_floats,
    )


def _floats_equal(a: float, b: float) -> bool:
    """Nan-aware float equality: two nans compare equal here."""
    if math.isnan(a) and math.isnan(b):
        return True
    return a == b


@st.composite
def _any_scenario_runs(draw: st.DrawFn) -> ScenarioRun:
    failed = draw(st.booleans())
    kpis = None if failed else draw(st.none() | _any_kpi_vectors())
    error = draw(_errors) if failed else None
    return ScenarioRun(
        arm=draw(_arms),
        seed=draw(_seeds),
        kpis=kpis,
        failed=failed,
        error=error,
    )


@settings(max_examples=100)
@given(runs=st.lists(_any_scenario_runs(), max_size=25))
def test_persistence_round_trips_nonfinite_kpis(
    runs: list[ScenarioRun], tmp_path_factory
) -> None:
    """Non-finite (nan/inf) KPI values survive persist/reload (Property 8)."""
    path = tmp_path_factory.mktemp("uplift-runs-nonfinite") / "runs.json"

    reloaded = load_runs(save_runs(runs, path))

    assert len(reloaded) == len(runs)
    for original, restored in zip(runs, reloaded, strict=True):
        assert restored.arm == original.arm
        assert restored.seed == original.seed
        assert restored.failed == original.failed
        assert restored.error == original.error
        if original.kpis is None:
            assert restored.kpis is None
        else:
            assert restored.kpis is not None
            for name in ("fill_rate", "spoilage_rate", "stockout_rate",
                         "avg_delivery_time_min", "margin", "co2_estimate"):
                assert _floats_equal(getattr(restored.kpis, name), getattr(original.kpis, name))
