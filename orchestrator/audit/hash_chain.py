"""Chained-hash tamper-evidence for the audit trail (Sprint 9 §M-sec-4, ADR-033).

Every row in ``audit_consensus`` carries a ``current_hash =
SHA-256(prev_hash || canonical_json(row))``. The genesis row uses an
empty prev_hash. ``synapse audit verify`` walks the chain from the
genesis row forward and asserts each ``current_hash`` matches.

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
