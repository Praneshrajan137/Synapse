"""Unit tests for the data-gated uplift-floor raise guard.

Feature: core-purpose-uplift (design C9, AD-4)

A floor raise asserts a measured gain, so it is only accepted against a
co-located, fully-powered, complete, within-fidelity-bound proof artifact whose
headline uplift is at least the proposed floor (0 < v <= measured).

Validates: Requirements 4.1, 4.2, 4.3, 4.7
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from digital_twin.simulation.monte_carlo import MIN_SCENARIOS

from uplift.uplift_floor import (
    MIN_POWERED_REPLICATES,
    UPLIFT_FLOOR,
    FloorRatchetError,
    PoweredProof,
    UnprovenFloorRaiseError,
    ratchet,
    ratchet_to_measured,
)


def _proof(**overrides) -> PoweredProof:
    fields = {
        "headline_uplift": 3.0,
        "replicates": MIN_POWERED_REPLICATES,
        "incomplete": False,
        "within_fidelity_bound": True,
    }
    fields.update(overrides)
    return PoweredProof(**fields)  # type: ignore[arg-type]


def _payload(**overrides) -> dict:
    payload = {
        "headline_uplift": 3.0,
        "replicates_per_arm": MIN_POWERED_REPLICATES,
        "incomplete": False,
        "fidelity": {"within_fidelity_bound": True},
    }
    payload.update(overrides)
    return payload


# --- R4.1: single declared numeric constant, still at the honest 0.0 ----------
def test_declared_floor_is_zero_until_a_powered_proof_lands() -> None:
    assert isinstance(UPLIFT_FLOOR, float)
    assert UPLIFT_FLOOR == 0.0


def test_powered_replicate_floor_matches_inv_tw_002() -> None:
    """The power bar mirrors the INV-TW-002 Monte-Carlo scenario floor."""
    assert MIN_POWERED_REPLICATES == MIN_SCENARIOS


# --- R4.3: monotonicity ------------------------------------------------------
def test_lowering_is_rejected_by_both_helpers() -> None:
    with pytest.raises(FloorRatchetError):
        ratchet(2.0, 1.9)
    with pytest.raises(FloorRatchetError):
        ratchet_to_measured(2.0, 1.9, _proof())


def test_holding_the_committed_floor_needs_no_proof() -> None:
    assert ratchet_to_measured(1.5, 1.5, None) == 1.5


# --- R4.2 / R4.7: data-gated raises -----------------------------------------
def test_supported_raise_is_accepted_up_to_the_measured_headline() -> None:
    proof = _proof(headline_uplift=3.0)
    assert ratchet_to_measured(0.0, 3.0, proof) == 3.0
    assert ratchet_to_measured(0.0, 1.25, proof) == 1.25


@pytest.mark.parametrize(
    ("proposed", "proof"),
    [
        (3.5, _proof(headline_uplift=3.0)),  # above the measured headline
        (1.0, _proof(replicates=MIN_POWERED_REPLICATES - 1)),  # under-powered
        (1.0, _proof(incomplete=True)),  # incomplete run
        (1.0, _proof(within_fidelity_bound=False)),  # outside the fidelity bound
        (1.0, _proof(within_fidelity_bound=None)),  # fidelity unavailable
        (1.0, _proof(headline_uplift=-2.0)),  # negative measurement
        (1.0, None),  # no measurement at all
    ],
)
def test_unsupported_raise_is_rejected(proposed: float, proof: PoweredProof | None) -> None:
    with pytest.raises(UnprovenFloorRaiseError):
        ratchet_to_measured(0.0, proposed, proof)


def test_proof_never_supports_a_non_positive_floor() -> None:
    """Only ``0 < v <= measured`` is a supported raise (R4.2)."""
    proof = _proof(headline_uplift=3.0)
    assert not proof.supports(0.0)
    assert not proof.supports(-1.0)
    with pytest.raises(UnprovenFloorRaiseError):
        ratchet_to_measured(-1.0, 0.0, proof)


# --- artifact parsing: unusable artifacts are not proofs ---------------------
@pytest.mark.parametrize(
    "payload",
    [
        _payload(headline_uplift="3.0"),  # non-numeric
        _payload(headline_uplift=True),  # bool is not a measurement
        _payload(headline_uplift=float("nan")),  # non-finite
        {"headline_uplift": 3.0},  # no replicate evidence
        ["not", "a", "mapping"],
    ],
)
def test_unusable_payload_yields_no_proof(payload) -> None:
    assert PoweredProof.from_payload(payload) is None


def test_payload_round_trip_and_incomplete_default() -> None:
    proof = PoweredProof.from_payload(_payload())
    assert proof == _proof()
    # A payload that omits `incomplete` is treated as incomplete (fail closed).
    assert PoweredProof.from_payload(
        {"headline_uplift": 3.0, "replicates": MIN_POWERED_REPLICATES}
    ) == _proof(incomplete=True, within_fidelity_bound=None)


def test_from_artifact_reads_json_and_handles_missing_or_malformed(tmp_path: Path) -> None:
    good = tmp_path / "result.json"
    good.write_text(json.dumps(_payload()), encoding="utf-8")
    assert PoweredProof.from_artifact(good) == _proof()

    assert PoweredProof.from_artifact(tmp_path / "absent.json") is None

    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    assert PoweredProof.from_artifact(bad) is None
