"""Tests for the honest outcome contract (Sprint 17, ADR-046).

Pins the substance core: outcomes are derived from realized signals, default
to ``unknown`` without evidence, and the calibration math discloses (never
fabricates) statistical power.
"""

from __future__ import annotations

import math

import pytest

from synapse_common.outcomes import (
    brier_score,
    classify_execution_confirmations,
    outcome_correct,
    reliability_bins,
    score_decision,
)

# --------------------------------------------------------------------------- #
# classify_execution_confirmations
# --------------------------------------------------------------------------- #


def test_empty_or_missing_confirmations_have_no_verdict() -> None:
    assert classify_execution_confirmations([]) is None
    assert classify_execution_confirmations(None) is None
    assert classify_execution_confirmations("confirmed") is None  # not a list


def test_divergence_dominates_confirmation() -> None:
    confs = [{"status": "executed"}, {"status": "failed"}]
    assert classify_execution_confirmations(confs) == "diverged"


def test_all_success_is_confirmed() -> None:
    assert classify_execution_confirmations([{"status": "ok"}, "completed"]) == "confirmed"


def test_uninterpretable_confirmations_have_no_verdict() -> None:
    assert classify_execution_confirmations([{"note": "hello"}, {"foo": 1}]) is None


# --------------------------------------------------------------------------- #
# score_decision — the honesty rule
# --------------------------------------------------------------------------- #


def test_no_signal_scores_unknown_not_confirmed() -> None:
    out = score_decision(
        confidence=0.95,
        execution_confirmations=[],
        twin_divergence=None,
        horizon_s=600,
        scored_at="2026-06-15T00:00:00Z",
    )
    assert out["status"] == "unknown"
    assert out["source"] == "none"
    assert out["error"] is None


def test_execution_confirmation_takes_precedence() -> None:
    out = score_decision(
        confidence=0.8,
        execution_confirmations=[{"status": "success"}],
        twin_divergence=0.5,  # would say diverged, but exec-confirm wins
        horizon_s=600,
        scored_at="t",
    )
    assert out["status"] == "confirmed"
    assert out["source"] == "execution_confirmations"


def test_twin_divergence_is_fallback_signal() -> None:
    hi = score_decision(
        confidence=0.8,
        execution_confirmations=[],
        twin_divergence=0.5,
        twin_threshold=0.1,
        horizon_s=600,
        scored_at="t",
    )
    assert hi["status"] == "diverged"
    assert hi["source"] == "twin_divergence"
    assert hi["error"] == pytest.approx(0.5)

    lo = score_decision(
        confidence=0.8,
        execution_confirmations=[],
        twin_divergence=0.02,
        twin_threshold=0.1,
        horizon_s=600,
        scored_at="t",
    )
    assert lo["status"] == "confirmed"


def test_confidence_does_not_influence_status() -> None:
    """A high confidence must NOT manufacture a confirmed outcome (circularity
    would defeat the entire calibration premise)."""
    out = score_decision(
        confidence=0.999,
        execution_confirmations=[],
        twin_divergence=None,
        horizon_s=1,
        scored_at="t",
    )
    assert out["status"] == "unknown"


# --------------------------------------------------------------------------- #
# outcome_correct / calibration math
# --------------------------------------------------------------------------- #


def test_outcome_correct_tri_state() -> None:
    assert outcome_correct("confirmed") is True
    assert outcome_correct("diverged") is False
    assert outcome_correct("unknown") is None


def test_reliability_bins_excludes_unknown_and_never_invents() -> None:
    samples = [(0.95, True), (0.92, False), (0.15, None), (0.15, False)]
    bins = reliability_bins(samples, n_bins=10)
    assert len(bins) == 10
    # bin [0.9, 1.0): two scored (one correct) → observed 0.5
    top = bins[9]
    assert top["n"] == 2
    assert top["observed_rate"] == pytest.approx(0.5)
    # bin [0.1, 0.2): the None sample is excluded → only one scored, incorrect
    low = bins[1]
    assert low["n"] == 1
    assert low["observed_rate"] == pytest.approx(0.0)
    # an empty bin reports n=0 and null means (no fabrication)
    assert bins[5]["n"] == 0
    assert bins[5]["mean_confidence"] is None


def test_brier_is_null_without_scored_samples() -> None:
    assert brier_score([(0.9, None), (0.1, None)]) is None


def test_brier_perfect_and_worst() -> None:
    # perfectly confident + correct → 0; perfectly confident + wrong → 1
    assert brier_score([(1.0, True)]) == pytest.approx(0.0)
    assert brier_score([(1.0, False)]) == pytest.approx(1.0)
    mixed = brier_score([(0.8, True), (0.8, False)])
    assert mixed == pytest.approx(((0.8 - 1) ** 2 + (0.8 - 0) ** 2) / 2)
    assert not math.isnan(mixed)
