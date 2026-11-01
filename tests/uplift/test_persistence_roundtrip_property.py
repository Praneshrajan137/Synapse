"""Property-based tests for recorded-run persistence round-trips.

Feature: decision-integrity-uplift-proof
Property 8: KPI_Vector persistence round-trips.

    *For any* set of recorded ``ScenarioRun``s (including failed runs with
    ``kpis=None`` and runs carrying finite float ``KpiVector`` values), persisting
    them and reloading them yields the identical list with each vector's arm
    identifier and scenario seed preserved.

Carried to Metric_Contract v2 (decision-quality-proof task 29.4): ``KpiVector`` gained the
required ``avg_on_hand_units`` and ``objective``, so the run-record file is schema version 2.
A version-1 file, and a file whose run omits either new field, is REFUSED rather than read
with a substituted value: a defaulted objective would be a fabricated cost.

Carried to schema version 3 (decision-quality-proof session 12, R7.20): every run carries its
``decision_counts`` -- the four counts, or ``null`` -- and the round trip preserves it. A
version-2 file is refused by its version, a run without the key is refused rather than read as
"kept no tally", and a tally that is not exactly four non-negative integer counts, or that rides
on a failed run, is refused.

Validates: Requirements 2.6
"""
from __future__ import annotations

import dataclasses
import json
import math
from typing import TYPE_CHECKING

import pytest
from hypothesis import given
from hypothesis import strategies as st

from uplift.interfaces import DecisionCounts, KpiVector, ScenarioRun
from uplift.persistence import SCHEMA_VERSION, PersistenceError, load_runs, save_runs

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

#: Every KpiVector field, for the field-by-field comparisons below.
_KPI_NAMES: tuple[str, ...] = tuple(field.name for field in dataclasses.fields(KpiVector))

#: The two fields schema version 2 exists to carry.
_V2_FIELDS: tuple[str, ...] = ("avg_on_hand_units", "objective")

#: Every DecisionCounts field -- the four counts schema version 3 exists to carry.
_COUNT_NAMES: tuple[str, ...] = tuple(
    field.name for field in dataclasses.fields(DecisionCounts)
)

# ---------------------------------------------------------------------------
# Strategies
#
# A recorded run carries an arm id (text), a scenario seed (int), a failed flag,
# an optional error string, and an optional KpiVector. For the equality
# round-trip we use *finite* floats for the eight KpiVector fields: json emits the
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
    """A KpiVector with finite floats in every one of its eight fields."""
    return st.builds(
        KpiVector,
        fill_rate=_finite_floats,
        spoilage_rate=_finite_floats,
        stockout_rate=_finite_floats,
        avg_delivery_time_min=_finite_floats,
        margin=_finite_floats,
        co2_estimate=_finite_floats,
        avg_on_hand_units=_finite_floats,
        objective=_finite_floats,
    )


_counts = st.integers(min_value=0, max_value=10**12)


def _decision_counts() -> st.SearchStrategy[DecisionCounts]:
    """A tally of four non-negative integer counts (R7.20)."""
    return st.builds(
        DecisionCounts,
        dispatched=_counts,
        withheld_for_confidence=_counts,
        guardrail_blocked=_counts,
        untranslatable=_counts,
    )


@st.composite
def _scenario_runs(draw: st.DrawFn) -> ScenarioRun:
    """A ScenarioRun that is either completed (has a KpiVector) or failed (kpis=None).

    Only a completed run may carry a decision tally; a failed one always carries ``None``.
    """
    failed = draw(st.booleans())
    kpis = None if failed else draw(st.none() | _kpi_vectors())
    error = draw(_errors) if failed else None
    counts = None if failed else draw(st.none() | _decision_counts())
    return ScenarioRun(
        arm=draw(_arms),
        seed=draw(_seeds),
        kpis=kpis,
        failed=failed,
        error=error,
        decision_counts=counts,
    )


@st.composite
def _completed_scenario_runs(draw: st.DrawFn) -> ScenarioRun:
    """A completed ScenarioRun that carries a KpiVector, so its ``kpis`` object exists."""
    return ScenarioRun(
        arm=draw(_arms),
        seed=draw(_seeds),
        kpis=draw(_kpi_vectors()),
        failed=False,
        error=None,
        decision_counts=draw(st.none() | _decision_counts()),
    )


_run_lists = st.lists(_scenario_runs(), max_size=25)


# ---------------------------------------------------------------------------
# Property 8: persist then reload yields the identical list (R2.6)
# ---------------------------------------------------------------------------
@given(runs=_run_lists)
def test_persistence_round_trips_identically(
    runs: list[ScenarioRun], tmp_path_factory: pytest.TempPathFactory
) -> None:
    """load_runs(save_runs(runs, path)) equals the original runs (Property 8)."""
    path = tmp_path_factory.mktemp("uplift-runs") / "runs.json"

    written = save_runs(runs, path)
    reloaded = load_runs(written)

    # The file declares the layout that carries all eight KPI fields and the tally.
    assert SCHEMA_VERSION == 3
    assert json.loads(written.read_text(encoding="utf-8"))["version"] == 3

    # ScenarioRun, KpiVector and DecisionCounts are frozen dataclasses, so == compares by
    # value, including arm id, seed, every KpiVector field and every count.
    assert reloaded == runs

    # Explicitly assert arm id + seed + tally preservation, element-wise (R2.6, R7.20).
    for original, restored in zip(runs, reloaded, strict=True):
        assert restored.arm == original.arm
        assert restored.seed == original.seed
        assert restored.decision_counts == original.decision_counts


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
        avg_on_hand_units=_any_floats,
        objective=_any_floats,
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
    counts = None if failed else draw(st.none() | _decision_counts())
    return ScenarioRun(
        arm=draw(_arms),
        seed=draw(_seeds),
        kpis=kpis,
        failed=failed,
        error=error,
        decision_counts=counts,
    )


@given(runs=st.lists(_any_scenario_runs(), max_size=25))
def test_persistence_round_trips_nonfinite_kpis(
    runs: list[ScenarioRun], tmp_path_factory: pytest.TempPathFactory
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
        assert restored.decision_counts == original.decision_counts
        if original.kpis is None:
            assert restored.kpis is None
        else:
            assert restored.kpis is not None
            for name in _KPI_NAMES:
                assert _floats_equal(getattr(restored.kpis, name), getattr(original.kpis, name))


# ---------------------------------------------------------------------------
# Schema version 2: what version 1 cannot carry is refused, never defaulted
# ---------------------------------------------------------------------------
@given(runs=_run_lists)
def test_a_run_file_labelled_version_1_is_refused(
    runs: list[ScenarioRun], tmp_path_factory: pytest.TempPathFactory
) -> None:
    """A file declaring version 1 is refused even when every field is present."""
    path = tmp_path_factory.mktemp("uplift-runs-v1-label") / "runs.json"
    payload = json.loads(save_runs(runs, path).read_text(encoding="utf-8"))
    payload["version"] = 1
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(PersistenceError, match="schema version 1"):
        load_runs(path)


@given(
    runs=_run_lists,
    completed=_completed_scenario_runs(),
    position=st.integers(min_value=0, max_value=25),
    field=st.sampled_from(_V2_FIELDS),
)
def test_a_run_missing_a_version_2_kpi_field_is_refused(
    runs: list[ScenarioRun],
    completed: ScenarioRun,
    position: int,
    field: str,
    tmp_path_factory: pytest.TempPathFactory,
) -> None:
    """A completed run whose kpis omit ``avg_on_hand_units`` or ``objective`` is refused."""
    index = position % (len(runs) + 1)
    recorded = [*runs[:index], completed, *runs[index:]]
    path = tmp_path_factory.mktemp("uplift-runs-missing-field") / "runs.json"
    payload = json.loads(save_runs(recorded, path).read_text(encoding="utf-8"))
    del payload["runs"][index]["kpis"][field]
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(PersistenceError, match=field):
        load_runs(path)


def test_a_file_in_the_version_1_layout_is_refused(tmp_path: Path) -> None:
    """Version 1's own layout -- six KPI fields -- is refused, and so is its relabelling."""
    six_field_kpis = {
        "fill_rate": 0.9,
        "spoilage_rate": 0.01,
        "stockout_rate": 0.1,
        "avg_delivery_time_min": 27.5,
        "margin": 12.0,
        "co2_estimate": 3.4,
    }
    version_1 = {
        "version": 1,
        "runs": [
            {
                "arm": "consensus",
                "seed": 7,
                "failed": False,
                "error": None,
                "kpis": six_field_kpis,
            },
        ],
    }
    path = tmp_path / "runs.json"
    path.write_text(json.dumps(version_1), encoding="utf-8")
    with pytest.raises(PersistenceError, match="schema version 1"):
        load_runs(path)

    # Relabelled as version 2, it is refused by its version: the reader reads version 3 only.
    path.write_text(json.dumps({**version_1, "version": 2}), encoding="utf-8")
    with pytest.raises(PersistenceError, match="schema version 2"):
        load_runs(path)

    # Relabelled as the current version, the same content still lacks what version 2 added,
    # and the KPI object is read first, so that is the field named.
    path.write_text(json.dumps({**version_1, "version": SCHEMA_VERSION}), encoding="utf-8")
    with pytest.raises(PersistenceError, match="avg_on_hand_units"):
        load_runs(path)


# ---------------------------------------------------------------------------
# Schema version 3: the decision tally is carried, and what cannot carry it is refused
# ---------------------------------------------------------------------------
@given(runs=_run_lists)
def test_a_run_file_labelled_version_2_is_refused(
    runs: list[ScenarioRun], tmp_path_factory: pytest.TempPathFactory
) -> None:
    """A version-2 file cannot say whether its arm kept a tally, so it is refused, not read."""
    path = tmp_path_factory.mktemp("uplift-runs-v2-label") / "runs.json"
    payload = json.loads(save_runs(runs, path).read_text(encoding="utf-8"))
    payload["version"] = 2
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(PersistenceError, match="schema version 2"):
        load_runs(path)


@given(
    runs=_run_lists,
    completed=_completed_scenario_runs(),
    position=st.integers(min_value=0, max_value=25),
)
def test_a_run_without_its_decision_counts_key_is_refused(
    runs: list[ScenarioRun],
    completed: ScenarioRun,
    position: int,
    tmp_path_factory: pytest.TempPathFactory,
) -> None:
    """An absent ``decision_counts`` is refused: it is not the same fact as an explicit null."""
    index = position % (len(runs) + 1)
    recorded = [*runs[:index], completed, *runs[index:]]
    path = tmp_path_factory.mktemp("uplift-runs-missing-tally") / "runs.json"
    payload = json.loads(save_runs(recorded, path).read_text(encoding="utf-8"))
    assert "decision_counts" in payload["runs"][index]
    del payload["runs"][index]["decision_counts"]
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(PersistenceError, match="decision_counts"):
        load_runs(path)


#: Each way a recorded tally can fail to be four non-negative integer counts, as an edit of the
#: tally a valid run serialises to.
_TALLY_DEFECTS: dict[str, Callable[[dict[str, object]], object]] = {
    "a negative count": lambda tally: {**tally, "dispatched": -1},
    "a boolean count": lambda tally: {**tally, "guardrail_blocked": True},
    "a fractional count": lambda tally: {**tally, "untranslatable": 1.5},
    "a string count": lambda tally: {**tally, "withheld_for_confidence": "3"},
    "a missing count": lambda tally: {k: v for k, v in tally.items() if k != "dispatched"},
    "an unknown count": lambda tally: {**tally, "overridden": 1},
    "a list, not an object": lambda tally: list(tally.values()),
}


@pytest.mark.parametrize("defect", sorted(_TALLY_DEFECTS))
def test_an_inadmissible_decision_tally_is_refused(defect: str, tmp_path: Path) -> None:
    """A tally is exactly the four counts, each a non-negative int; anything else is refused."""
    run = ScenarioRun(
        arm="consensus",
        seed=11,
        kpis=None,
        failed=False,
        error=None,
        decision_counts=DecisionCounts(
            dispatched=3, withheld_for_confidence=2, guardrail_blocked=1, untranslatable=0
        ),
    )
    path = tmp_path / "runs.json"
    payload = json.loads(save_runs([run], path).read_text(encoding="utf-8"))
    tally = payload["runs"][0]["decision_counts"]
    assert sorted(tally) == sorted(_COUNT_NAMES)
    payload["runs"][0]["decision_counts"] = _TALLY_DEFECTS[defect](tally)
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(PersistenceError, match="decision_counts"):
        load_runs(path)


def test_a_failed_run_carrying_a_tally_is_refused(tmp_path: Path) -> None:
    """A failed run has no outcome, so its decisions are not R7.20's evidence."""
    run = ScenarioRun(arm="consensus", seed=5, kpis=None, failed=True, error="boom")
    path = tmp_path / "runs.json"
    payload = json.loads(save_runs([run], path).read_text(encoding="utf-8"))
    assert payload["runs"][0]["decision_counts"] is None
    payload["runs"][0]["decision_counts"] = dict.fromkeys(_COUNT_NAMES, 1)
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(PersistenceError, match="failed"):
        load_runs(path)
