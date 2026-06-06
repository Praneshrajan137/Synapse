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
