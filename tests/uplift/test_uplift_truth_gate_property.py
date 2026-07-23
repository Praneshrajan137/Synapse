"""Property-based tests for the ``uplift_truth`` honesty gate exit codes.

Feature: decision-integrity-uplift-proof
Property 21: Uplift_truth gate exit codes follow the floor mapping.

    *For any* measured uplift and committed floor, the gate exits ``0`` when the
    measured uplift is greater than or equal to the floor; exits with the
    regression code (``1``), emitting the measured value, the floor, and a
    regression indication, when the measured uplift is strictly below the floor;
    and exits with a distinct non-zero code (never a pass) when the measured
    uplift is unavailable.

Validates: Requirements 6.3, 6.4, 6.5
"""
from __future__ import annotations

import json
import math

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from scripts.audit import uplift_truth as gate
from scripts.audit.uplift_truth import (
    EXIT_PASS,
    EXIT_REGRESSION,
    EXIT_UNAVAILABLE,
    read_measured_uplift,
    run,
)


# ---------------------------------------------------------------------------
# Strategies — finite floats for the measured uplift and the committed floor,
# plus ``None`` for the "measured uplift unavailable" case (R6.5). Bounded to a
# sensible finite range so the ``measured >= floor`` comparison stays meaningful.
# ---------------------------------------------------------------------------
_finite = st.floats(
    min_value=-1e9,
    max_value=1e9,
    allow_nan=False,
    allow_infinity=False,
)
# measured uplift including ``None`` (the unavailable case, R6.5)
_measured_or_none = st.one_of(st.none(), _finite)


def _set_gate_state(monkeypatch, measured: float | None, floor: float) -> None:
    """Pin the gate's measured-uplift source and committed floor.

    ``run()`` reads the measurement through the module-level
    ``read_measured_uplift`` and compares against the module-level
    ``UPLIFT_FLOOR``; monkeypatching both lets Hypothesis drive the full input
    space (measured value, unavailable, and floor) without a live twin run.
    """
    monkeypatch.setattr(gate, "read_measured_uplift", lambda: measured)
    monkeypatch.setattr(gate, "UPLIFT_FLOOR", floor)


# ---------------------------------------------------------------------------
# Property 21: the three-way exit-code mapping against the floor
# ---------------------------------------------------------------------------
@settings(max_examples=200)
@given(measured=_measured_or_none, floor=_finite)
def test_exit_codes_follow_floor_mapping(
    measured: float | None, floor: float, monkeypatch, capsys
) -> None:
    """exit 0 when measured >= floor, 1 (regression) when below, 2 when unavailable."""
    _set_gate_state(monkeypatch, measured, floor)

    exit_code = run(check=True)
    out = capsys.readouterr().out

    if measured is None:
        # R6.5: unavailable -> a DISTINCT non-zero code, never a pass.
        assert exit_code == EXIT_UNAVAILABLE
        assert exit_code != EXIT_PASS
        assert exit_code != EXIT_REGRESSION
        assert exit_code != 0
    elif measured >= floor:
        # R6.3: measured >= floor -> pass.
        assert exit_code == EXIT_PASS
        assert exit_code == 0
    else:
        # R6.4: measured < floor -> regression code, emitting measured + floor +
        # a regression indication.
        assert exit_code == EXIT_REGRESSION
        assert exit_code != 0
        assert str(measured) in out
        assert str(floor) in out
        assert "REGRESSION" in out.upper()


# ---------------------------------------------------------------------------
# Property 21 (boundary): measured == floor is a pass, not a regression (R6.3 '>=')
# ---------------------------------------------------------------------------
@given(floor=_finite)
def test_boundary_measured_equals_floor_is_pass(floor: float, monkeypatch) -> None:
    """When measured == floor exactly, the gate passes (R6.3 uses '>=')."""
    _set_gate_state(monkeypatch, floor, floor)
    assert run(check=True) == EXIT_PASS


# ---------------------------------------------------------------------------
# Property 21 (--json mode): the boolean regression field tracks the mapping (R6.7)
# ---------------------------------------------------------------------------
@settings(max_examples=200)
@given(measured=_measured_or_none, floor=_finite)
def test_json_regression_field_tracks_mapping(
    measured: float | None, floor: float, monkeypatch, capsys
) -> None:
    """--json emits measured, floor, and regression==True iff measured < floor."""
    _set_gate_state(monkeypatch, measured, floor)

    run(as_json=True, check=True)
    payload = json.loads(capsys.readouterr().out)

    assert payload["measured_uplift"] == measured
    assert payload["uplift_floor"] == floor
    # regression is True iff a measurement exists AND it is below the floor.
    expected_regression = measured is not None and measured < floor
    assert payload["regression"] is expected_regression


# ---------------------------------------------------------------------------
# Property 21 (artifact source): the measured value is read from the JSON
# artifact, and an unavailable measurement (missing / malformed / non-numeric)
# maps to ``None`` — which drives the distinct "unavailable" exit path (R6.5).
# ---------------------------------------------------------------------------
@given(headline=_finite)
def test_read_measured_uplift_round_trips_numeric_headline(
    headline: float, tmp_path
) -> None:
    """A numeric ``headline_uplift`` in the artifact is read back as that value."""
    artifact = tmp_path / "result.json"
    artifact.write_text(json.dumps({"headline_uplift": headline}), encoding="utf-8")

    measured = read_measured_uplift(artifact)
    assert measured is not None
    assert math.isclose(measured, headline, rel_tol=0.0, abs_tol=0.0)


def test_read_measured_uplift_missing_artifact_is_unavailable(tmp_path) -> None:
    """A missing artifact yields ``None`` (unavailable), never a spurious value."""
    assert read_measured_uplift(tmp_path / "does_not_exist.json") is None


@pytest.mark.parametrize(
    "contents",
    [
        "not valid json {",              # malformed JSON
        json.dumps([1, 2, 3]),           # valid JSON but not a dict
        json.dumps({"other": 1.0}),      # dict without headline_uplift
        json.dumps({"headline_uplift": "0.5"}),  # non-numeric headline_uplift
        json.dumps({"headline_uplift": True}),   # bool must not count as 1.0
        json.dumps({"headline_uplift": None}),   # explicit null
    ],
)
def test_read_measured_uplift_unavailable_variants(contents: str, tmp_path) -> None:
    """Malformed / non-numeric artifacts all map to ``None`` (unavailable, R6.5)."""
    artifact = tmp_path / "result.json"
    artifact.write_text(contents, encoding="utf-8")
    assert read_measured_uplift(artifact) is None


def test_read_measured_uplift_rejects_non_finite(tmp_path) -> None:
    """A non-finite headline (Infinity/NaN) is treated as unavailable (R6.5)."""
    for token in ("Infinity", "-Infinity", "NaN"):
        artifact = tmp_path / f"{token}.json"
        artifact.write_text(f'{{"headline_uplift": {token}}}', encoding="utf-8")
        assert read_measured_uplift(artifact) is None
