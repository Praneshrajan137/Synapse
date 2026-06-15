"""Tests for the outbox ORM<->DDL drift gate (Sprint 20, C55).

Two things must hold: (1) the gate is GREEN on the real repo files (the contract
holds now), and (2) the gate has TEETH — its parsers actually extract columns and
its comparison flags a real drift. A gate that always returns [] is theatre, so we
prove the failure paths on synthetic inputs.
"""

from __future__ import annotations

from scripts.audit.outbox_schema_truth import (
    _ddl_columns,
    _ddl_enum_values,
    _orm_columns_and_enum,
    collect,
)

_FAKE_ORM = '''
OUTBOX_STATUSES = ("PENDING", "IN_FLIGHT", "PUBLISHED", "FAILED")

class AuditOutboxRow(Base):
    __tablename__ = "audit_outbox"
    id: Any = Column(UUID, primary_key=True)
    audit_id: Any = Column(UUID, ForeignKey("audit_consensus.id"))
    next_attempt_at: Any = Column(DateTime)
    status: Any = Column(ENUM(*OUTBOX_STATUSES, name="outbox_status", create_type=False))
    note = "not a column"
'''

_GOOD_DDL = """
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'outbox_status') THEN
    CREATE TYPE outbox_status AS ENUM ('PENDING', 'IN_FLIGHT', 'PUBLISHED', 'FAILED');
  END IF;
END $$;
CREATE TABLE IF NOT EXISTS audit_outbox (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    audit_id        UUID REFERENCES audit_consensus(id) ON DELETE RESTRICT,
    next_attempt_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    status          outbox_status NOT NULL DEFAULT 'PENDING'
);
"""


def test_real_repo_is_clean() -> None:
    """The shipped ORM, canonical DDL and docker mirror must agree (baseline 0)."""
    assert collect() == []


def test_orm_parser_extracts_columns_and_enum() -> None:
    cols, enum = _orm_columns_and_enum(_FAKE_ORM)
    assert cols == {"id", "audit_id", "next_attempt_at", "status"}
    assert "note" not in cols  # only Column(...) assignments count
    assert set(enum) == {"PENDING", "IN_FLIGHT", "PUBLISHED", "FAILED"}


def test_ddl_parser_extracts_columns_and_enum() -> None:
    assert _ddl_columns(_GOOD_DDL) == {"id", "audit_id", "next_attempt_at", "status"}
    assert set(_ddl_enum_values(_GOOD_DDL)) == {"PENDING", "IN_FLIGHT", "PUBLISHED", "FAILED"}


def test_ddl_parser_skips_constraint_lines() -> None:
    ddl = """
    CREATE TABLE IF NOT EXISTS audit_outbox (
        id        UUID PRIMARY KEY,
        decision_id UUID NOT NULL,
        CONSTRAINT some_chk CHECK (decision_id IS NOT NULL),
        PRIMARY KEY (id)
    );
    """
    assert _ddl_columns(ddl) == {"id", "decision_id"}


def test_gate_detects_missing_column() -> None:
    """A DDL missing an ORM column is the exact bug this gate exists to catch."""
    orm_cols, orm_enum = _orm_columns_and_enum(_FAKE_ORM)
    drifted_ddl = _GOOD_DDL.replace(
        "audit_id        UUID REFERENCES audit_consensus(id) ON DELETE RESTRICT,\n", ""
    )
    ddl_cols = _ddl_columns(drifted_ddl)
    assert "audit_id" in (orm_cols - ddl_cols)  # the runtime-INSERT-failure column


def test_gate_detects_enum_drift() -> None:
    text_status_ddl = _GOOD_DDL.replace(
        "CREATE TYPE outbox_status AS ENUM ('PENDING', 'IN_FLIGHT', 'PUBLISHED', 'FAILED');",
        "CREATE TYPE outbox_status AS ENUM ('PENDING', 'SENT', 'FAILED');",
    )
    _, orm_enum = _orm_columns_and_enum(_FAKE_ORM)
    assert set(_ddl_enum_values(text_status_ddl)) != set(orm_enum)
