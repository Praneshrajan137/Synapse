"""Chained-hash tamper-evidence for the audit trail (Sprint 9 §M-sec-4, ADR-033).

Every row in ``audit_consensus`` carries a ``current_hash =
SHA-256(prev_hash || canonical_json(row))``. The genesis row uses an
empty prev_hash. ``synapse audit verify`` walks the chain from the
genesis row forward and asserts each ``current_hash`` matches.

ADR-044: the pure functions now live in ``synapse_common.audit_chain`` so
the API gateway (whose image ships only ``packages/`` + ``api/``) can
recompute single-row integrity for the ``chain_verified`` response field.
This module remains the canonical import path for orchestrator code; the
E-S9-02 rule (the canonical field set changes only via a chain-rewrite
migration) applies to the shared implementation unchanged.
"""

from __future__ import annotations

from synapse_common.audit_chain import (
    GENESIS_HASH,
    hash_payload_for_row,
    make_canonical_row,
    verify_row_hash,
)

__all__ = [
    "GENESIS_HASH",
    "hash_payload_for_row",
    "make_canonical_row",
    "verify_row_hash",
]
