"""Property-based test for the C43 published-checkpoint gate decision.

Feature: core-purpose-uplift, Property 16: The C43 published-checkpoint gate decision is
correct over sidecar/registry inputs

    *For any* combination of published sidecar ``smoke`` flag, ``last_coverage_p90``,
    recorded registry sha, and published version string (with the registry populated and
    the remote reachable), ``published_checkpoint_truth.evaluate()`` returns ``ok`` if and
    only if the sidecar is non-smoke AND coverage ``>= 0.85`` AND the recorded sha appears
    in the published version; otherwise it returns a failure (smoke artifact,
    uncalibrated coverage, or sha drift).

    Requirement 5.3: a pass requires non-smoke + ``last_coverage_p90 >= 0.85`` + recorded
    sha matching the published version.
    Requirement 5.4: a smoke artifact is a failure.
    Requirement 5.5: coverage below the 0.85 floor is a failure.
    Requirement 5.6: a recorded sha absent from the published version is a drift failure.

The expected verdict is recomputed here from the raw sidecar/registry fields, so the test
states the rule independently rather than echoing ``evaluate()``'s branch order. Because
the registry is populated and the remote answers, ``skip`` is never an acceptable verdict:
every example must be a decided ``ok`` or ``fail``.

The property is network-free and repo-safe: the registry loader is replaced with the
generated record (the committed ``published_checkpoints.json`` is never read or written)
and the HF Hub download is replaced with a local sidecar file, so no socket is opened
and $0 is spent.

**Validates: Requirements 5.3, 5.4, 5.5, 5.6**
"""

from __future__ import annotations

import json
import sys
import types
from typing import TYPE_CHECKING, Any

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from scripts.audit import published_checkpoint_truth as c43
from scripts.audit.published_checkpoint_truth import COVERAGE_FLOOR, SERVING_NAME

if TYPE_CHECKING:
    from pathlib import Path

_REPO = "example-owner/synapse-demand-prophet"

# ---------------------------------------------------------------------------
# Strategies
#
# The generators stay inside the input space a published sidecar/registry pair can
# actually occupy — a boolean-or-absent ``smoke`` flag, a probability-or-absent
# coverage, a hex sha, and a ``<kind>_<sha>`` version string — while weighting the
# exact decision boundaries (the 0.85 floor, an empty sha, a sha that is//isn't a
# substring of the version) so they are hit densely instead of by luck.
# ---------------------------------------------------------------------------
_MISSING = object()  # the key is absent from the sidecar entirely

_smoke = st.sampled_from([True, False, _MISSING])

_coverage = st.one_of(
    st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
    st.sampled_from(
        [
            None,
            _MISSING,
            0.0,
            COVERAGE_FLOOR - 1e-9,
            COVERAGE_FLOOR,
            COVERAGE_FLOOR + 1e-9,
            0.91,
            1.0,
        ]
    ),
)

_hex7 = st.text(alphabet="0123456789abcdef", min_size=7, max_size=7)
_sha = st.one_of(
    _hex7,
    st.sampled_from(["", "   ", "  a1b2c3d  ", "a1b2c3d", "deadbee", "0000000"]),
)


@st.composite
def _gate_inputs(draw: st.DrawFn) -> tuple[Any, Any, str, str]:
    """Draw ``(smoke, coverage, recorded_sha, published_version)`` quadruples.

    The version is often derived from the drawn sha (matching record) and often from an
    unrelated sha (drift), so both sides of the sha cross-check are exercised.
    """
    smoke = draw(_smoke)
    coverage = draw(_coverage)
    sha = draw(_sha)
    stripped = sha.strip()
    other = draw(_hex7)
    version = draw(
        st.one_of(
            st.just(f"full_{stripped}"),
            st.just(f"smoke_{stripped}"),
            st.just(f"full_{other}"),
            st.just(stripped),
            st.sampled_from(["", "full_", "version-1"]),
        )
    )
    return smoke, coverage, sha, version


def _expected_status(smoke: Any, coverage: Any, sha: str, version: str) -> str:
    """Restate the R5.3-R5.6 rule directly from the raw fields."""
    non_smoke = smoke is not True
    calibrated = isinstance(coverage, (int, float)) and float(coverage) >= COVERAGE_FLOOR
    sha_matches = sha.strip() in version  # an unrecorded (empty) sha imposes no pin
    return "ok" if (non_smoke and calibrated and sha_matches) else "fail"


def _build_sidecar(smoke: Any, coverage: Any, version: str) -> dict[str, Any]:
    sidecar: dict[str, Any] = {"version": version, "arch": {}}
    if smoke is not _MISSING:
        sidecar["smoke"] = smoke
    if coverage is not _MISSING:
        sidecar["calibrator"] = {"last_coverage_p90": coverage}
    return sidecar


@pytest.fixture(scope="module")
def sidecar_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A module-scoped scratch dir standing in for the HF Hub cache (no network)."""
    return tmp_path_factory.mktemp("c43_published_sidecar")


# ---------------------------------------------------------------------------
# Property 16
# ---------------------------------------------------------------------------
@settings(max_examples=250, deadline=None)
@given(gate_inputs=_gate_inputs())
def test_c43_gate_decision_is_correct_over_sidecar_and_registry_inputs(
    gate_inputs: tuple[Any, Any, str, str], sidecar_dir: Path
) -> None:
    """Property 16: ``ok`` iff non-smoke AND calibrated AND the recorded sha is pinned.

    **Validates: Requirements 5.3, 5.4, 5.5, 5.6**
    """
    smoke, coverage, sha, version = gate_inputs
    sidecar = _build_sidecar(smoke, coverage, version)
    sidecar_path = sidecar_dir / f"{SERVING_NAME}.serving.json"
    sidecar_path.write_text(json.dumps(sidecar, sort_keys=True), encoding="utf-8")

    entry = {
        "repo": _REPO,
        "sha": sha,
        "coverage_p90": 0.91,
        "final_crps": 0.42,
        "trained_at": "2026-06-01T12:00:00Z",
        "rows": 1_125_000,
    }

    def _fake_download(*, repo_id: str, filename: str) -> str:
        # The gate must ask the recorded repo for the serving-name sidecar, nothing else.
        assert repo_id == _REPO
        assert filename == f"{SERVING_NAME}.serving.json"
        return str(sidecar_path)

    fake_hub = types.ModuleType("huggingface_hub")
    fake_hub.hf_hub_download = _fake_download  # type: ignore[attr-defined]

    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("DP_HF_REPO", _REPO)
        mp.setitem(sys.modules, "huggingface_hub", fake_hub)
        # The committed registry file is never touched: the record is the generated one.
        mp.setattr(c43, "_load_registry", lambda: {SERVING_NAME: entry})
        probe = c43.evaluate()

    expected = _expected_status(smoke, coverage, sha, version)
    assert probe.status == expected, (smoke, coverage, sha, version, probe.detail)
    # A populated registry + reachable remote is always a decided verdict, never a SKIP.
    assert probe.status in {"ok", "fail"}

    if expected == "ok":
        assert version in probe.detail
        assert SERVING_NAME in probe.detail and _REPO in probe.detail
    elif smoke is True:
        assert "SMOKE" in probe.detail  # R5.4
    elif not (isinstance(coverage, (int, float)) and float(coverage) >= COVERAGE_FLOOR):
        assert "uncalibrated" in probe.detail  # R5.5
    else:
        assert "drift" in probe.detail and sha.strip() in probe.detail  # R5.6


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
