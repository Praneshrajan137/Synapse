"""Regression guard for the decisions read-path table (Phase A, WS-A).

The live ``GET /api/v1/decisions/recent`` returned HTTP 503
``column "phase_reached" does not exist`` because the router queried the legacy,
write-dead ``audit_decisions`` table while the orchestrator writes every decision
to ``audit_consensus`` (``orchestrator/audit/models.py::AuditConsensusRow``). The
consensus table also names the JSONB column ``proposals`` (not
``agent_proposals``).

These tests are DB-free: they inspect the SQL the router embeds. They pin the
read path to the real write-target table so the 503 class cannot silently come
back. The mechanical CI gate ``verify_claims.py::C42`` enforces the same
invariant against ``AuditConsensusRow.__tablename__``.
"""

from __future__ import annotations

import inspect

from api.routers import decisions
from orchestrator.audit.models import AuditConsensusRow


def _source() -> str:
    return inspect.getsource(decisions)


def test_reads_audit_consensus_not_dead_table() -> None:
    src = _source()
    assert "FROM audit_consensus" in src, "decisions router must read audit_consensus"
    assert "FROM audit_decisions" not in src, (
        "decisions router must NOT read the write-dead audit_decisions table "
        "(that caused the live 503)"
    )


def test_read_table_matches_orchestrator_write_table() -> None:
    # The single source of truth for the write target.
    assert AuditConsensusRow.__tablename__ == "audit_consensus"
    assert f"FROM {AuditConsensusRow.__tablename__}" in _source()


def test_detail_query_uses_consensus_column_names() -> None:
    src = _source()
    # audit_consensus calls the JSONB column `proposals`, not `agent_proposals`.
    assert "agent_proposals" not in src
    assert "proposals" in src


# --------------------------------------------------------------------------- #
# ADR-044 — additive anatomy + honesty fields
# --------------------------------------------------------------------------- #


def test_detail_selects_every_anatomy_column() -> None:
    """The decision-detail SELECT must carry the previously-imprisoned
    audit_consensus columns. Dropping any of these silently re-hides
    intelligence the FE renders (Living Interface Phases 3-4)."""
    src = _source()
    for column in (
        "debate_rounds",
        "pareto_front",
        "execution_confirmations",
        "context_messages",
        "outcome",
        "prev_hash",
        "current_hash",
    ):
        assert column in src, f"detail SELECT lost ADR-044 column: {column}"


def test_detail_response_carries_computed_honesty_fields() -> None:
    src = _source()
    for key in ('"chain_verified"', '"degraded"', '"is_synthetic"', '"initiator"'):
        assert key in src, f"detail response lost ADR-044/053 computed field: {key}"


def test_recent_computes_initiator_via_both_prefixes() -> None:
    """ADR-053: /recent derives initiator from BOTH the synthetic and autonomous
    prefixes (single-owned in synapse_common), and autonomous wins so a
    self-initiated decision is never reported synthetic."""
    src = _source()
    assert "AUTONOMOUS_ORDER_PREFIX" in src
    assert '"initiator"' in src
    assert '"autonomous"' in src
    assert "'auto-" not in src.replace("AUTONOMOUS_ORDER_PREFIX", "")


def test_recent_computes_honesty_flags_in_sql() -> None:
    """/recent derives degraded + is_synthetic via jsonb_path_exists so the
    row-heavy JSONB columns never leave the database."""
    src = _source()
    assert "jsonb_path_exists(proposals" in src
    assert "jsonb_path_exists(context_messages" in src


def test_synthetic_prefix_has_single_owner() -> None:
    """The 'synthetic-' rule is owned by synapse_common.synthetic and passed
    into the jsonpath as a variable — a second hardcoded copy in this router
    would let the two definitions drift."""
    src = _source()
    assert "SYNTHETIC_ORDER_PREFIX" in src
    assert "'synthetic-" not in src.replace("SYNTHETIC_ORDER_PREFIX", "")


def test_chain_verification_uses_shared_implementation() -> None:
    """chain_verified must recompute via synapse_common.audit_chain — the
    SAME functions the writer hashes with (ADR-044 D6), never a local copy."""
    src = _source()
    assert "from synapse_common.audit_chain import verify_row_hash" in src
    assert "hashlib" not in src, "no local hash reimplementation in the router"
