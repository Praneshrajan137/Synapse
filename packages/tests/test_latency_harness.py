"""Tests for the per-tier latency harness (Phase 2.3, scripts.perf.latency_harness).

Covers the pure logic (percentiles, verdict), the grounded static budget audit
(read from the real TIER_CRITERIA / TIER_TIMEOUTS constants), and a round-trip
that proves ``payload_for_tier`` actually classifies into the intended tier — so
the live --measure driver is verified correct without a running stack.
"""

from __future__ import annotations

import pytest

from scripts.perf.latency_harness import (
    payload_for_tier,
    percentiles,
    static_budget_audit,
    tier_verdict,
)


def test_percentiles_basic() -> None:
    p = percentiles([10.0, 20.0, 30.0, 40.0, 50.0])
    assert p["n"] == 5.0
    assert p["p50"] == 30.0
    assert p["max"] == 50.0
    assert p["mean"] == 30.0


def test_percentiles_empty_is_zeros() -> None:
    p = percentiles([])
    assert p["n"] == 0.0
    assert p["p95"] == 0.0


def test_tier_verdict_met() -> None:
    status, ratio = tier_verdict(80.0, 100.0)
    assert status == "met"
    assert abs(ratio - 0.8) < 1e-9


def test_tier_verdict_violated() -> None:
    assert tier_verdict(120.0, 100.0)[0] == "violated"


def test_tier_verdict_unknown_budget() -> None:
    assert tier_verdict(50.0, 0.0) == ("unknown", 0.0)


def test_static_audit_reads_real_constants() -> None:
    findings = static_budget_audit()
    assert len(findings) == 4
    by_tier = {f.tier: f for f in findings}
    # Grounded: Tier-1's 100ms decision budget sits under a 2000ms per-agent A2A
    # timeout, so it is structurally fragile (the finding the harness exists to surface).
    assert by_tier["tier_1"].budget_ms == 100
    assert by_tier["tier_1"].a2a_timeout_ms == 2000.0
    assert by_tier["tier_1"].fragile is True
    for f in findings:
        assert f.note  # every finding explains itself


@pytest.mark.parametrize("tier", ["tier_1", "tier_2", "tier_3", "tier_4"])
def test_payload_for_tier_classifies_correctly(tier: str) -> None:
    from orchestrator.consensus.tier_router import TierRouter
    from synapse_common.models import DecisionTier

    expected = {
        "tier_1": DecisionTier.TIER_1,
        "tier_2": DecisionTier.TIER_2,
        "tier_3": DecisionTier.TIER_3,
        "tier_4": DecisionTier.TIER_4,
    }[tier]
    assert TierRouter().classify(payload_for_tier(tier)).tier == expected
