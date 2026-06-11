"""Chained-hash tamper-evidence primitives for the audit trail (ADR-033, ADR-044).

Every row in ``audit_consensus`` carries a ``current_hash =
SHA-256(prev_hash || canonical_json(row))``. The genesis row uses an
empty prev_hash. ``synapse audit verify`` walks the chain from the
genesis row forward and asserts each ``current_hash`` matches.

These pure functions originally lived in ``orchestrator/audit/hash_chain.py``
(Sprint 9). ADR-044 moved them here so the API gateway — whose image ships
only ``packages/`` + ``api/`` — can recompute single-row integrity for the
``chain_verified`` field without importing the orchestrator package. The
orchestrator module re-exports them, so ``orchestrator.audit.hash_chain``
remains the canonical import path for orchestrator code and the E-S9-02
rule (changing the canonical field set requires a chain-rewrite migration)
is unchanged.

Design notes:
- Canonical JSON uses ``sort_keys=True, separators=(',',':')`` (I-13)
  so the chain hashes deterministically across services and Python
  versions.
- ``hash_payload_for_row`` accepts the same fields ``AuditLogger`` writes;
  the writer passes them in directly (no second SELECT).
- Chain population is **per-row at insert time**; the migration leaves
  pre-existing rows with NULL chain values (legacy). ``verify`` skips
  legacy rows but flags the gap.
"""

from __future__ import annotations

import hashlib
import json
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from uuid import UUID

GENESIS_HASH: str = "0" * 64


def _canonical(payload: Any) -> str:  # noqa: ANN401
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def hash_payload_for_row(prev_hash: str | None, row_canonical: dict[str, Any]) -> str:
    """Compute the SHA-256 chain hash for one row.

    Args:
        prev_hash: 64-char hex digest of the previous row's ``current_hash``,
            or ``None`` for the genesis row.
        row_canonical: dict of the row's content fields (sans
            ``prev_hash``/``current_hash`` themselves).
    """
    prev = prev_hash or GENESIS_HASH
    body = _canonical(row_canonical)
    digest = hashlib.sha256()
    digest.update(prev.encode("ascii"))
    digest.update(b"\x1f")
    digest.update(body.encode("utf-8"))
    return digest.hexdigest()


def make_canonical_row(
    decision_id: UUID,
    tier: str,
    selected_action: dict[str, Any],
    pareto_weights: dict[str, float],
    confidence: float,
    proposals: list[dict[str, Any]],
    audit_trace: list[str],
) -> dict[str, Any]:
    """Return the canonical dict to be hashed (stable across replays)."""
    return {
        "decision_id": str(decision_id),
        "tier": tier,
        "selected_action": selected_action,
        "pareto_weights": pareto_weights,
        "confidence": round(confidence, 6),
        "proposals": proposals,
        "audit_trace": audit_trace,
    }


def verify_row_hash(
    *,
    prev_hash: str | None,
    current_hash: str,
    decision_id: UUID,
    tier: str,
    selected_action: dict[str, Any],
    pareto_weights: dict[str, float],
    confidence: float,
    proposals: list[dict[str, Any]],
    audit_trace: list[str],
) -> bool:
    """Single-row integrity check: recompute the chain hash from stored
    content and compare against the stored ``current_hash``.

    This does NOT walk the chain (that is ``synapse audit verify``'s job);
    it answers "has THIS row's content been altered since insert?" — the
    question the API's ``chain_verified`` field exposes per decision.
    """
    canonical = make_canonical_row(
        decision_id=decision_id,
        tier=tier,
        selected_action=selected_action,
        pareto_weights=pareto_weights,
        confidence=confidence,
        proposals=proposals,
        audit_trace=audit_trace,
    )
    return hash_payload_for_row(prev_hash, canonical) == current_hash


__all__ = [
    "GENESIS_HASH",
    "hash_payload_for_row",
    "make_canonical_row",
    "verify_row_hash",
]
