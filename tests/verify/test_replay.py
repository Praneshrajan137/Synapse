"""Replay-harness determinism gate (ADR-032, Layer 6).

Two replays of the same bundle must produce byte-identical outputs. This is
the universal oracle for the orchestrator: any non-determinism — whether
from an unpinned seed, a model load order, or an out-of-order set traversal
— surfaces here as a diff.

Skipped automatically when `pymoo` is absent (local dev), runs in CI.
"""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest

pytestmark = [pytest.mark.oracle]

pytest.importorskip("pymoo", reason="orchestrator replay needs pymoo (CI only)")


def _build_bundle(tmp_path: Path) -> Path:
    from orchestrator.replay.harness import capture_bundle, save_bundle
    from synapse_common.models import AgentName, AgentProposal, DecisionTier

    proposals = [
        AgentProposal(
            agent_name=a,
            decision_id=uuid4(),
            utility_score=0.7 + 0.02 * i,
            confidence=0.9,
            justification_trace=["replay-fixture"],
            payload={},
            tier=DecisionTier.TIER_3,
        )
        for i, a in enumerate(AgentName)
    ]
    bundle = capture_bundle(
        decision_id=str(uuid4()),
        inputs={"proposals": [p.model_dump(mode="json") for p in proposals]},
        weights={
            "demand_accuracy": 1.0,
            "route_efficiency": 1.0,
            "inventory_fill_rate": 1.2,
            "freshness_score": 1.0,
            "pricing_revenue": 0.8,
            "disruption_readiness": 1.0,
            "supplier_reliability": 0.8,
            "carbon_efficiency": 0.6,
        },
    )
    return save_bundle(bundle, tmp_path / "bundle.json")


def test_two_replays_produce_byte_identical_output(tmp_path: Path) -> None:
    from orchestrator.replay.harness import canonical, load_bundle, replay

    path = _build_bundle(tmp_path)
    bundle = load_bundle(path)

    a = canonical(replay(bundle))
    b = canonical(replay(bundle))
    assert a == b, "replay produced non-deterministic output — investigate seeds"


def test_bundle_roundtrip_preserves_hash(tmp_path: Path) -> None:
    from orchestrator.replay.harness import load_bundle

    path = _build_bundle(tmp_path)
    bundle = load_bundle(path)
    assert bundle.bundle_hash, "bundle hash must be populated"
    # Re-loading must succeed without raising on hash mismatch.
    again = load_bundle(path)
    assert again.bundle_hash == bundle.bundle_hash
