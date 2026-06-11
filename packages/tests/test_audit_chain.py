"""Tests for synapse_common.audit_chain — the shared chain-hash primitives
(ADR-033 algorithm, relocated per ADR-044 D6 so the API gateway can compute
``chain_verified`` without importing the orchestrator).

The byte-level pins here are the tamper-evidence contract: if ANY of these
digests change, every existing audit chain in production becomes
unverifiable. There is no acceptable reason for these tests to be updated
short of a chain-rewrite migration (E-S9-02).
"""

from __future__ import annotations

import hashlib
import json
from uuid import UUID

from synapse_common.audit_chain import (
    GENESIS_HASH,
    hash_payload_for_row,
    make_canonical_row,
    verify_row_hash,
)

_DECISION_ID = UUID("22222222-2222-2222-2222-222222222222")
_ROW_KW = {
    "tier": "tier_2",
    "selected_action": {"action": "restock", "sku_id": "SKU001"},
    "pareto_weights": {"cost": 0.5, "time": 0.5},
    "confidence": 0.87,
    "proposals": [{"agent_name": "demand_prophet", "confidence": 0.87}],
    "audit_trace": ["tier=tier_2", "phase=4"],
}


class TestAlgorithmPins:
    def test_genesis_hash_is_64_zeros(self) -> None:
        assert GENESIS_HASH == "0" * 64

    def test_canonical_row_field_set_is_frozen(self) -> None:
        """E-S9-02: the canonical field set changes only via a chain-rewrite
        migration. A new key here = every production chain breaks."""
        row = make_canonical_row(decision_id=_DECISION_ID, **_ROW_KW)
        assert sorted(row.keys()) == [
            "audit_trace",
            "confidence",
            "decision_id",
            "pareto_weights",
            "proposals",
            "selected_action",
            "tier",
        ]

    def test_confidence_rounded_to_six_decimals(self) -> None:
        row = make_canonical_row(
            decision_id=_DECISION_ID, **{**_ROW_KW, "confidence": 0.123456789}
        )
        assert row["confidence"] == 0.123457

    def test_hash_matches_independent_recompute(self) -> None:
        """Oracle: recompute the digest with raw stdlib calls (sort_keys +
        compact separators + the 0x1F unit separator) and pin equality."""
        row = make_canonical_row(decision_id=_DECISION_ID, **_ROW_KW)
        body = json.dumps(row, sort_keys=True, separators=(",", ":"), default=str)
        expected = hashlib.sha256(
            GENESIS_HASH.encode("ascii") + b"\x1f" + body.encode("utf-8")
        ).hexdigest()
        assert hash_payload_for_row(None, row) == expected

    def test_none_prev_hash_means_genesis(self) -> None:
        row = make_canonical_row(decision_id=_DECISION_ID, **_ROW_KW)
        assert hash_payload_for_row(None, row) == hash_payload_for_row(GENESIS_HASH, row)

    def test_provenance_free_proposals_hash_pin(self) -> None:
        """Regression pin for ADR-044: relocating the implementation (and
        adding the optional provenance field upstream) must NOT change the
        digest of a pre-044-shaped row. This exact value was computed with
        the Sprint-9 algorithm; it is load-bearing for every legacy chain."""
        row = make_canonical_row(
            decision_id=UUID("11111111-1111-1111-1111-111111111111"),
            tier="tier_1",
            selected_action={"action": "noop"},
            pareto_weights={"latency": 1.0},
            confidence=0.95,
            proposals=[],
            audit_trace=["t"],
        )
        body = json.dumps(row, sort_keys=True, separators=(",", ":"), default=str)
        assert body == (
            '{"audit_trace":["t"],"confidence":0.95,'
            '"decision_id":"11111111-1111-1111-1111-111111111111",'
            '"pareto_weights":{"latency":1.0},"proposals":[],'
            '"selected_action":{"action":"noop"},"tier":"tier_1"}'
        )


class TestVerifyRowHash:
    def test_untampered_row_verifies(self) -> None:
        canonical = make_canonical_row(decision_id=_DECISION_ID, **_ROW_KW)
        current = hash_payload_for_row("a" * 64, canonical)
        assert (
            verify_row_hash(
                prev_hash="a" * 64,
                current_hash=current,
                decision_id=_DECISION_ID,
                **_ROW_KW,
            )
            is True
        )

    def test_tampered_content_fails(self) -> None:
        canonical = make_canonical_row(decision_id=_DECISION_ID, **_ROW_KW)
        current = hash_payload_for_row("a" * 64, canonical)
        tampered = {**_ROW_KW, "selected_action": {"action": "restock", "sku_id": "SKU666"}}
        assert (
            verify_row_hash(
                prev_hash="a" * 64,
                current_hash=current,
                decision_id=_DECISION_ID,
                **tampered,
            )
            is False
        )

    def test_tampered_confidence_fails(self) -> None:
        canonical = make_canonical_row(decision_id=_DECISION_ID, **_ROW_KW)
        current = hash_payload_for_row(None, canonical)
        assert (
            verify_row_hash(
                prev_hash=None,
                current_hash=current,
                decision_id=_DECISION_ID,
                **{**_ROW_KW, "confidence": 0.99},
            )
            is False
        )

    def test_provenance_bearing_proposals_verify(self) -> None:
        """ADR-044 D2: a row whose proposals carry the structured provenance
        key hashes over what it stores — stored == hashed == verifiable."""
        kw = {
            **_ROW_KW,
            "proposals": [
                {
                    "agent_name": "demand_prophet",
                    "confidence": 0.87,
                    "provenance": {
                        "model_version": "registry-v2",
                        "feature_source": "feast",
                        "degraded": False,
                        "confidence_basis": "conformal_interval",
                    },
                }
            ],
        }
        canonical = make_canonical_row(decision_id=_DECISION_ID, **kw)
        current = hash_payload_for_row(None, canonical)
        assert (
            verify_row_hash(
                prev_hash=None,
                current_hash=current,
                decision_id=_DECISION_ID,
                **kw,
            )
            is True
        )


class TestPublicSurface:
    def test_all_exports_exist(self) -> None:
        """Pin __all__ so a mutated export name (or a silently dropped one)
        fails here instead of breaking downstream star-importers."""
        from synapse_common import audit_chain

        assert audit_chain.__all__ == [
            "GENESIS_HASH",
            "hash_payload_for_row",
            "make_canonical_row",
            "verify_row_hash",
        ]
        for name in audit_chain.__all__:
            assert hasattr(audit_chain, name)
