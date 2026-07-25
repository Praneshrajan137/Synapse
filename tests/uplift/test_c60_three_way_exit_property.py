"""Property-based test that the C60 gate exit is a total three-way mapping.

Feature: core-purpose-uplift, Property 15: The C60 gate exit is a total three-way mapping.

    *For any* result artifact, the C60 gate exits pass (``0``) iff the measured headline
    is available and ``>= UPLIFT_FLOOR``, regression (``1``) iff available and
    ``< UPLIFT_FLOOR``, and the distinct unavailable code (``2``) iff the measurement is
    unavailable (missing, unreadable, invalid, or non-finite) — the unavailable case never
    maps to pass.

    Requirement 4.4: a measured headline at or above the floor exits pass.
    Requirement 4.5: a measured headline below the floor exits the regression code,
    emitting the measured value, the floor, and a regression indication.
    Requirement 4.6: an unavailable measurement exits a *distinct* non-zero code —
    absence of proof is never a pass.

The generator walks the whole artifact surface the gate can meet in the wild: the file
absent, present-but-unreadable (a directory at the path, undecodable bytes), malformed
JSON, valid JSON that is not an object, an object with no ``headline_uplift``, a
non-numeric or boolean headline, a non-finite headline (``NaN`` / ``±Infinity``), and
valid numbers on both sides of :data:`~uplift.uplift_floor.UPLIFT_FLOOR` including the
exact boundary. The expected exit code is recomputed from the raw artifact description
rather than from the gate's own reader, so this is an independent statement of the rule.

Every artifact is written under ``tmp_path`` and the gate's reader is bound to that path,
so the repo's ``artifacts/uplift/result.json`` is never read or written. The property is
pure and fast: no twin, no arm, no socket, $0.

**Validates: Requirements 4.4, 4.5, 4.6**
"""
from __future__ import annotations

import json
import math
import uuid
from dataclasses import dataclass
from pathlib import Path

from hypothesis import given, settings
from hypothesis import strategies as st

from scripts.audit import uplift_truth as gate
from scripts.audit.uplift_truth import (
    EXIT_PASS,
    EXIT_REGRESSION,
    EXIT_UNAVAILABLE,
    RESULT_ARTIFACT,
    read_measured_uplift,
)

_FLOOR: float = gate.UPLIFT_FLOOR
_EXIT_CODES = (EXIT_PASS, EXIT_REGRESSION, EXIT_UNAVAILABLE)


# ---------------------------------------------------------------------------
# Artifact surface
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class _Artifact:
    """A description of one on-disk artifact state plus the headline it really carries.

    ``headline`` is the finite float a correct reader must extract, or ``None`` when the
    measurement is unavailable for any reason. It is carried alongside the bytes so the
    expected exit code is derived from the *description*, never from the gate's reader.
    """

    kind: str
    headline: float | None
    payload: bytes | None = None  # ``None`` means "do not create the file"
    as_directory: bool = False

    def materialise(self, root: Path) -> Path:
        path = root / uuid.uuid4().hex / "result.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        if self.as_directory:
            path.mkdir()
        elif self.payload is not None:
            path.write_bytes(self.payload)
        return path


def _json_bytes(obj: object) -> bytes:
    return json.dumps(obj).encode("utf-8")


def _raw(text: str) -> bytes:
    return text.encode("utf-8")


# -- available: a finite numeric headline, densely straddling the floor -----------
_deltas = st.one_of(
    st.floats(min_value=1e-9, max_value=1e6, allow_nan=False, allow_infinity=False),
    st.sampled_from([1e-9, 1e-6, 0.5, 1.0, 7.5, 1e6]),
)


@st.composite
def _available(draw) -> _Artifact:
    """A readable artifact whose headline lands above, below, or exactly on the floor."""
    side = draw(st.sampled_from(["boundary", "above", "below", "arbitrary", "integer"]))
    if side == "boundary":
        headline = _FLOOR
    elif side == "above":
        headline = _FLOOR + draw(_deltas)
    elif side == "below":
        headline = _FLOOR - draw(_deltas)
    elif side == "integer":
        headline = float(draw(st.integers(min_value=-1_000, max_value=1_000)))
    else:
        headline = draw(
            st.floats(min_value=-1e6, max_value=1e6, allow_nan=False, allow_infinity=False)
        )
    # Extra keys are ignored by the reader; include them sometimes for realism.
    body: dict[str, object] = {"headline_uplift": headline}
    if draw(st.booleans()):
        body["incomplete"] = draw(st.booleans())
    return _Artifact(kind=f"available:{side}", headline=headline, payload=_json_bytes(body))


# -- unavailable: every way the measurement can fail to exist --------------------
_unavailable = st.one_of(
    # missing file
    st.just(_Artifact(kind="missing", headline=None, payload=None)),
    # unreadable: a directory sitting at the artifact path
    st.just(_Artifact(kind="directory", headline=None, as_directory=True)),
    # unreadable: bytes that are not valid UTF-8
    st.just(_Artifact(kind="undecodable", headline=None, payload=b"\xff\xfe\x00not utf-8")),
    # malformed JSON
    st.sampled_from(["not valid json {", "", "   ", "{'headline_uplift': 1.0}", "{,}"]).map(
        lambda text: _Artifact(kind="malformed", headline=None, payload=_raw(text))
    ),
    # valid JSON that is not an object
    st.sampled_from([[1, 2, 3], "0.5", 12.5, None, True]).map(
        lambda obj: _Artifact(kind="not-object", headline=None, payload=_json_bytes(obj))
    ),
    # object without the headline key
    st.sampled_from([{}, {"other": 1.0}, {"uplift": 2.0}, {"incomplete": False}]).map(
        lambda obj: _Artifact(kind="missing-key", headline=None, payload=_json_bytes(obj))
    ),
    # non-numeric headline (including bool, which must not read as 1.0 / 0.0)
    st.sampled_from(["0.5", "", None, [1.0], {"value": 1.0}, True, False]).map(
        lambda value: _Artifact(
            kind="non-numeric", headline=None, payload=_json_bytes({"headline_uplift": value})
        )
    ),
    # non-finite headline (JSON's non-standard NaN / Infinity tokens)
    st.sampled_from(["NaN", "Infinity", "-Infinity"]).map(
        lambda token: _Artifact(
            kind="non-finite",
            headline=None,
            payload=_raw('{"headline_uplift": %s}' % token),
        )
    ),
)

_artifacts = st.one_of(_available(), _unavailable)


def _expected_exit(artifact: _Artifact) -> int:
    """Restate the three-way rule directly from the artifact description."""
    headline = artifact.headline
    if headline is None or not math.isfinite(headline):
        return EXIT_UNAVAILABLE  # R4.6
    return EXIT_PASS if headline >= _FLOOR else EXIT_REGRESSION  # R4.4 / R4.5


# ---------------------------------------------------------------------------
# Property 15
# ---------------------------------------------------------------------------
@settings(max_examples=200, deadline=None)
@given(artifact=_artifacts)
def test_c60_gate_exit_is_a_total_three_way_mapping(
    artifact: _Artifact, tmp_path: Path, monkeypatch, capsys
) -> None:
    """Property 15: pass / regression / distinct-unavailable, and never a false pass.

    **Validates: Requirements 4.4, 4.5, 4.6**
    """
    path = artifact.materialise(tmp_path)
    assert path != RESULT_ARTIFACT  # the repo's own artifact is never touched

    # The gate reads through the module-level reader; bind the REAL reader to the
    # generated artifact so the read logic under test is the shipped one.
    monkeypatch.setattr(gate, "read_measured_uplift", lambda: read_measured_uplift(path))

    exit_code = gate.run(check=True)
    out = capsys.readouterr().out

    expected = _expected_exit(artifact)

    # Totality: the gate always lands on exactly one of the three declared codes,
    # and the three codes are mutually distinct.
    assert exit_code in _EXIT_CODES
    assert len(set(_EXIT_CODES)) == 3
    assert exit_code == expected

    if expected == EXIT_UNAVAILABLE:
        # R4.6: unavailable -> a distinct NON-ZERO code that is neither pass nor regression.
        assert exit_code != EXIT_PASS
        assert exit_code != EXIT_REGRESSION
        assert exit_code != 0
        assert "UNAVAILABLE" in out.upper()
    elif expected == EXIT_PASS:
        # R4.4: available and at/above the floor -> pass.
        assert exit_code == 0
        assert artifact.headline is not None and artifact.headline >= _FLOOR
    else:
        # R4.5: available and below the floor -> regression, naming measured + floor.
        assert exit_code != 0
        assert "REGRESSION" in out.upper()
        assert str(artifact.headline) in out
        assert str(_FLOOR) in out
