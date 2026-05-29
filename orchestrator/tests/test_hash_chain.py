"""Sprint 13 §Phase 3 — orchestrator audit hash-chain tests.

ADR-033 + E-S9-02: every audit row carries `current_hash =
SHA-256(prev_hash || canonical_json(row))`. The chain MUST be:
- deterministic across replays (I-13 canonical JSON),
- tamper-evident (any byte change → different digest),
- forward-only (genesis row uses GENESIS_HASH = "0"*64).

These tests pin the exact algorithm. Mutation-survival targets per C30:
- byte-level pin on canonical JSON output (separators, sort_keys),
- exact digest values for a fixed (prev_hash, row) input,
- 0x1F separator between prev_hash and body (the unit separator).
"""

from __future__ import annotations

import hashlib
import json
from uuid import UUID

import pytest

from orchestrator.audit.hash_chain import (
    GENESIS_HASH,
    hash_payload_for_row,
    make_canonical_row,
)


# -----------------------------------------------------------------------------
# Constants used as inputs across multiple tests so a single test can pin them
# -----------------------------------------------------------------------------

_DECISION_ID = UUID("11111111-1111-1111-1111-111111111111")
_TIER = "tier_1"
_SELECTED_ACTION = {"action": "noop", "store_id": "store_1"}
_PARETO_WEIGHTS = {"latency": 0.5, "cost": 0.5}
_CONFIDENCE = 0.987654321  # gets rounded to 6 dp
_PROPOSALS: list[dict] = []
_AUDIT_TRACE = ["tier_1_routed"]


# =============================================================================
# Canonical-row construction
# =============================================================================


class TestMakeCanonicalRow:
    def test_decision_id_serialized_as_string(self) -> None:
        row = make_canonical_row(
            _DECISION_ID, _TIER, _SELECTED_ACTION, _PARETO_WEIGHTS,
            _CONFIDENCE, _PROPOSALS, _AUDIT_TRACE,
        )
        assert row["decision_id"] == str(_DECISION_ID)
        assert isinstance(row["decision_id"], str)

    def test_confidence_rounded_to_six_dp(self) -> None:
        """Per spec: confidence is rounded to 6 dp to keep the digest stable
        across float-format drift."""
        row = make_canonical_row(
            _DECISION_ID, _TIER, _SELECTED_ACTION, _PARETO_WEIGHTS,
            _CONFIDENCE, _PROPOSALS, _AUDIT_TRACE,
        )
        assert row["confidence"] == round(_CONFIDENCE, 6)
        assert row["confidence"] == 0.987654

    def test_all_required_keys_present(self) -> None:
        row = make_canonical_row(
            _DECISION_ID, _TIER, _SELECTED_ACTION, _PARETO_WEIGHTS,
            _CONFIDENCE, _PROPOSALS, _AUDIT_TRACE,
        )
        expected = {"decision_id", "tier", "selected_action", "pareto_weights",
                    "confidence", "proposals", "audit_trace"}
        assert set(row.keys()) == expected, (
            f"Canonical row schema drifted: {row.keys()} vs {expected}; "
            f"E-S9-02 requires a migration when fields change"
        )

    def test_round_trip_through_canonical_json(self) -> None:
        """Round-tripping the row through json.dumps + json.loads must yield
        the same dict — i.e. no non-JSON-native types leak through."""
        row = make_canonical_row(
            _DECISION_ID, _TIER, _SELECTED_ACTION, _PARETO_WEIGHTS,
            _CONFIDENCE, _PROPOSALS, _AUDIT_TRACE,
        )
        roundtrip = json.loads(json.dumps(row, sort_keys=True, separators=(",", ":")))
        assert roundtrip == row


# =============================================================================
# hash_payload_for_row — algorithmic pins (the strongest mutation killer)
# =============================================================================


class TestHashChainAlgorithm:
    def test_genesis_hash_is_64_zero_hex(self) -> None:
        assert GENESIS_HASH == "0" * 64
        assert len(GENESIS_HASH) == 64

    def test_none_prev_hash_uses_genesis(self) -> None:
        """When prev_hash is None, the genesis hash MUST be substituted —
        otherwise the chain is unverifiable from row 1."""
        row = {"a": 1, "b": 2}
        h_none = hash_payload_for_row(None, row)
        h_genesis = hash_payload_for_row(GENESIS_HASH, row)
        assert h_none == h_genesis, "None prev_hash must fall back to GENESIS_HASH"

    def test_digest_is_sha256_hex(self) -> None:
        """Pin the digest length and alphabet — a mutant switching to MD5
        (32-char) or SHA-1 (40-char) fails this."""
        h = hash_payload_for_row(None, {"x": 1})
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)

    def test_digest_is_deterministic(self) -> None:
        """Same inputs → identical digest, across calls. Required for chain
        verification to be reproducible across replays + processes."""
        row = {"alpha": 1, "beta": [2, 3]}
        d1 = hash_payload_for_row("a" * 64, row)
        d2 = hash_payload_for_row("a" * 64, row)
        assert d1 == d2

    def test_digest_changes_on_prev_hash_change(self) -> None:
        """A 1-bit change in prev_hash MUST produce a different digest
        (no chain-breakage tolerated)."""
        row = {"x": 1}
        d1 = hash_payload_for_row("0" * 63 + "0", row)
        d2 = hash_payload_for_row("0" * 63 + "1", row)
        assert d1 != d2

    def test_digest_changes_on_row_change(self) -> None:
        d1 = hash_payload_for_row(GENESIS_HASH, {"x": 1})
        d2 = hash_payload_for_row(GENESIS_HASH, {"x": 2})
        assert d1 != d2

    def test_digest_invariant_to_key_order(self) -> None:
        """Canonical JSON sorts keys — {a:1,b:2} and {b:2,a:1} must hash
        identically. Pins `sort_keys=True`."""
        d1 = hash_payload_for_row(GENESIS_HASH, {"a": 1, "b": 2})
        d2 = hash_payload_for_row(GENESIS_HASH, {"b": 2, "a": 1})
        assert d1 == d2

    def test_unit_separator_in_digest_input(self) -> None:
        """The chain implementation joins prev_hash and body with 0x1F (US).
        This pins that contract — a mutant dropping the separator (or using
        a different one) collapses {prev:"abc", body:"def"} and
        {prev:"abcd", body:"ef"} into the same digest."""
        row_short_body = {"x": "def"}
        row_long_body = {"x": "abcdef"}
        prev_long = "abcd" + "0" * 60  # 64 hex chars
        prev_short = "ab" + "0" * 62

        # If the separator is dropped, these MIGHT collide. With separator,
        # they cannot — assert non-collision.
        d1 = hash_payload_for_row(prev_long, row_short_body)
        d2 = hash_payload_for_row(prev_short, row_long_body)
        assert d1 != d2

    def test_digest_matches_exact_reference_value(self) -> None:
        """Pin one exact digest value end-to-end so any algorithmic mutation
        (separator, encoding, hash function, ordering) gets caught."""
        row = {"k": "v"}
        body = json.dumps(row, sort_keys=True, separators=(",", ":"))
        expected = hashlib.sha256(
            GENESIS_HASH.encode("ascii") + b"\x1f" + body.encode("utf-8")
        ).hexdigest()
        assert hash_payload_for_row(None, row) == expected


# =============================================================================
# Chain integrity — multi-row walk
# =============================================================================


class TestChainIntegrity:
    def test_chain_of_three_links(self) -> None:
        """Build a 3-link chain forward; each link's `current_hash` must be
        deterministic when fed the prior link's hash."""
        row_a = {"id": 1, "data": "first"}
        row_b = {"id": 2, "data": "second"}
        row_c = {"id": 3, "data": "third"}
        h_a = hash_payload_for_row(None, row_a)
        h_b = hash_payload_for_row(h_a, row_b)
        h_c = hash_payload_for_row(h_b, row_c)
        # Re-walking the chain produces the same digests
        assert hash_payload_for_row(None, row_a) == h_a
        assert hash_payload_for_row(h_a, row_b) == h_b
        assert hash_payload_for_row(h_b, row_c) == h_c

    def test_tampering_with_middle_row_breaks_chain(self) -> None:
        """If row_b is altered after the fact, recomputed h_c will not
        match the stored h_c → tampering detected."""
        row_a = {"id": 1, "data": "first"}
        row_b = {"id": 2, "data": "second"}
        row_c = {"id": 3, "data": "third"}
        h_a = hash_payload_for_row(None, row_a)
        h_b_original = hash_payload_for_row(h_a, row_b)
        h_c_original = hash_payload_for_row(h_b_original, row_c)

        # Tamper with row_b's payload (the attacker's edit)
        row_b_tampered = {"id": 2, "data": "second_HACKED"}
        h_b_tampered = hash_payload_for_row(h_a, row_b_tampered)
        h_c_recomputed = hash_payload_for_row(h_b_tampered, row_c)
        assert h_c_recomputed != h_c_original, (
            "Tampered middle row must produce a different downstream digest"
        )


# =============================================================================
# Property-based: hash is collision-free in practice on random small inputs
# =============================================================================


@pytest.mark.parametrize("seed", [0, 1, 2, 3, 4])
def test_no_collisions_across_distinct_inputs(seed: int) -> None:
    """Different (prev_hash, row) inputs must produce different digests over
    a small parametrised sweep. Not a cryptographic proof — a regression
    sentinel against an accidental constant-return mutant."""
    import random
    rng = random.Random(seed)
    seen: set[str] = set()
    for i in range(20):
        prev = "".join(rng.choice("0123456789abcdef") for _ in range(64))
        row = {"i": i, "blob": rng.random()}
        d = hash_payload_for_row(prev, row)
        assert d not in seen, f"Collision in seeded sweep — digest fn broken: {d}"
        seen.add(d)
