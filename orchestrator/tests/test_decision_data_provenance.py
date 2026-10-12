"""Unit tests for the append-only ``decision_data_provenance`` table (task 7.8).

Feature: purpose-achievement-audit, design AD-10 / conflict CF-1, R4.4.

Two halves, both cheap and both example-class (the universal round-trip and
append-only claims are Property 21, task 7.9):

1. The record: :class:`DecisionDataProvenance` canonical round trip, UTC
   normalisation, frozen-ness, and the frozen key set.
2. The migration: the canonical file and its Docker-init mirror agree byte for
   byte, grant ``synapse_app`` SELECT + INSERT only with UPDATE/DELETE revoked,
   and are wired into the runner and both compose init mounts. An unmirrored or
   unlisted migration is silently skipped -- the exact rot E-S9-14 and
   ``scripts/db/migrate.sh`` exist to prevent -- so the wiring is asserted, not
   assumed.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from orchestrator.audit.models import (
    PROVENANCE_FIELDS,
    SOURCE_CLASSES,
    DecisionDataProvenance,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
CANONICAL_DDL = (
    REPO_ROOT / "orchestrator" / "audit" / "migrations" / "0007_decision_data_provenance.sql"
)
MIRROR_DDL = REPO_ROOT / "infrastructure" / "postgres" / "09_decision_data_provenance.sql"
MIGRATE_RUNNER = REPO_ROOT / "scripts" / "db" / "migrate.sh"
COMPOSE_FILES = (
    REPO_ROOT / "docker" / "docker-compose.yml",
    REPO_ROOT / "docker" / "docker-compose.gcp.yml",
)
TABLE = "decision_data_provenance"


_DECISION_ID = uuid.UUID("11111111-2222-3333-4444-555555555555")
_OBSERVED_AT = datetime(2026, 5, 24, 11, 32, 51, 123456, tzinfo=UTC)


def _record(
    *,
    source_class: Any = "EXTERNAL",
    is_synthetic: bool = False,
    feed_revision: str | None = "synapse.orders.demand@0:4213",
    observed_at: datetime = _OBSERVED_AT,
) -> DecisionDataProvenance:
    """One provenance record. ``source_class`` is loosely typed so the
    rejection cases can hand it a value the Literal forbids."""
    return DecisionDataProvenance(
        decision_id=_DECISION_ID,
        source_class=source_class,
        is_synthetic=is_synthetic,
        feed_revision=feed_revision,
        observed_at=observed_at,
    )


# ---------------------------------------------------------------------------
# The record
# ---------------------------------------------------------------------------


def test_canonical_json_round_trips_and_is_byte_stable() -> None:
    record = _record()
    payload = record.to_canonical_json()

    assert DecisionDataProvenance.from_canonical_json(payload) == record
    # Byte-stable: the same record serialises identically every time (compact,
    # sorted keys), which is what makes a stored payload comparable across runs.
    assert payload == record.to_canonical_json()
    assert ", " not in payload


def test_canonical_key_set_is_exactly_the_frozen_field_set() -> None:
    keys = tuple(sorted(_record().to_canonical_dict()))
    assert keys == PROVENANCE_FIELDS
    # Storage bookkeeping is not part of the recorded fact.
    assert "id" not in keys
    assert "created_at" not in keys


def test_absent_feed_revision_survives_the_round_trip_as_none() -> None:
    record = _record(source_class="SEEDED", is_synthetic=True, feed_revision=None)
    assert DecisionDataProvenance.from_canonical_json(record.to_canonical_json()) == record


def test_non_utc_offset_is_normalised_without_moving_the_instant() -> None:
    ist = timezone(timedelta(hours=5, minutes=30))
    record = _record(observed_at=datetime(2026, 5, 24, 17, 2, 51, tzinfo=ist))

    assert record.observed_at.tzinfo == UTC
    assert record.observed_at == datetime(2026, 5, 24, 11, 32, 51, tzinfo=UTC)


def test_naive_timestamp_is_rejected() -> None:
    naive = datetime(2026, 5, 24, 11, 32, 51, tzinfo=None)
    with pytest.raises(ValidationError, match="timezone-aware"):
        _record(observed_at=naive)


def test_unknown_key_is_rejected_rather_than_dropped() -> None:
    payload = _record().to_canonical_dict()
    payload["outcome"] = "confirmed"
    with pytest.raises(ValidationError):
        DecisionDataProvenance.from_canonical_dict(payload)


def test_unknown_source_class_is_rejected() -> None:
    with pytest.raises(ValidationError):
        _record(source_class="REAL")


def test_record_is_frozen() -> None:
    record = _record()
    with pytest.raises(ValidationError):
        record.source_class = "SEEDED"


# ---------------------------------------------------------------------------
# The migration and its Docker-init mirror
# ---------------------------------------------------------------------------


def test_canonical_migration_and_mirror_are_identical() -> None:
    canonical = CANONICAL_DDL.read_text(encoding="utf-8")
    mirror = MIRROR_DDL.read_text(encoding="utf-8")
    assert canonical == mirror, "canonical DDL and its infrastructure/postgres mirror drifted"


def test_ddl_grants_insert_select_only_and_revokes_update_delete() -> None:
    ddl = CANONICAL_DDL.read_text(encoding="utf-8")

    assert f"GRANT SELECT, INSERT ON {TABLE} TO synapse_app;" in ddl
    assert f"REVOKE UPDATE, DELETE ON {TABLE} FROM synapse_app;" in ddl
    # No UPDATE or DELETE is ever granted (I-4), and the migration self-tests it.
    assert f"GRANT SELECT, INSERT, UPDATE ON {TABLE}" not in ddl
    assert f"GRANT DELETE ON {TABLE}" not in ddl
    assert "I-4 VIOLATION" in ddl


def test_ddl_declares_every_recorded_field_and_the_source_class_check() -> None:
    ddl = CANONICAL_DDL.read_text(encoding="utf-8")

    for field in PROVENANCE_FIELDS:
        assert field in ddl, f"{field} is recorded by the model but absent from the DDL"
    for source_class in SOURCE_CLASSES:
        assert f"'{source_class}'" in ddl
    assert "TIMESTAMPTZ NOT NULL" in ddl


def test_ddl_is_idempotent() -> None:
    ddl = CANONICAL_DDL.read_text(encoding="utf-8")
    assert f"CREATE TABLE IF NOT EXISTS {TABLE}" in ddl
    assert "CREATE INDEX IF NOT EXISTS" in ddl
    assert "IF NOT EXISTS (" in ddl  # the guarded CHECK constraint


def test_mirror_is_wired_into_the_runner_and_both_compose_mounts() -> None:
    runner = MIGRATE_RUNNER.read_text(encoding="utf-8")
    assert '"11_decision_data_provenance.sql"' in runner
    assert '["11_decision_data_provenance.sql"]="09_decision_data_provenance.sql"' in runner

    for compose in COMPOSE_FILES:
        text = compose.read_text(encoding="utf-8")
        assert MIRROR_DDL.name in text, f"{compose.name} does not mount the provenance migration"
