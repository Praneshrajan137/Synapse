from __future__ import annotations

"""Test that audit tables are truly immutable (I-4).

Verifies REVOKE DELETE, UPDATE on synapse_audit tables.
Uses the correct table names from the actual schema:
  - audit_decisions   (Sprint 1, init_audit.sql)
  - audit_consensus   (Sprint 4, 02_sprint4_consensus.sql)
"""

import pytest
import structlog

logger = structlog.get_logger()

try:
    import psycopg2
except ImportError:
    psycopg2 = None

AUDIT_DB_CONFIG = {
    "dbname": "synapse_audit",
    "user": "synapse_app",
    "password": "synapse_app_2026",
    "host": "localhost",
    "port": 5432,
}

AUDIT_TABLES = ["audit_decisions", "audit_consensus"]


@pytest.mark.skipif(psycopg2 is None, reason="psycopg2 not installed")
class TestAuditImmutability:
    """Verify PostgreSQL audit trail immutability (I-4)."""

    @pytest.fixture()
    def audit_conn(self):
        try:
            conn = psycopg2.connect(**AUDIT_DB_CONFIG)
            yield conn
            conn.close()
        except psycopg2.OperationalError:
            pytest.skip("PostgreSQL not available")

    @pytest.mark.parametrize("table", AUDIT_TABLES)
    def test_app_user_cannot_delete(self, audit_conn, table: str) -> None:
        """synapse_app has no DELETE privilege on audit tables."""
        cur = audit_conn.cursor()
        try:
            cur.execute(
                """
                SELECT has_table_privilege(%s, %s, 'DELETE')
                """,
                (AUDIT_DB_CONFIG["user"], table),
            )
            has_delete = cur.fetchone()[0]
            assert has_delete is False, (
                f"I-4 VIOLATION: {AUDIT_DB_CONFIG['user']} has DELETE on {table}"
            )
        finally:
            cur.close()

    @pytest.mark.parametrize("table", AUDIT_TABLES)
    def test_app_user_cannot_update(self, audit_conn, table: str) -> None:
        """synapse_app has no UPDATE privilege on audit tables."""
        cur = audit_conn.cursor()
        try:
            cur.execute(
                """
                SELECT has_table_privilege(%s, %s, 'UPDATE')
                """,
                (AUDIT_DB_CONFIG["user"], table),
            )
            has_update = cur.fetchone()[0]
            assert has_update is False, (
                f"I-4 VIOLATION: {AUDIT_DB_CONFIG['user']} has UPDATE on {table}"
            )
        finally:
            cur.close()

    @pytest.mark.parametrize("table", AUDIT_TABLES)
    def test_app_user_can_insert(self, audit_conn, table: str) -> None:
        """synapse_app retains INSERT privilege (required for logging)."""
        cur = audit_conn.cursor()
        try:
            cur.execute(
                """
                SELECT has_table_privilege(%s, %s, 'INSERT')
                """,
                (AUDIT_DB_CONFIG["user"], table),
            )
            has_insert = cur.fetchone()[0]
            assert has_insert is True, (
                f"synapse_app must have INSERT on {table} for audit logging"
            )
        finally:
            cur.close()

    @pytest.mark.parametrize("table", AUDIT_TABLES)
    def test_app_user_can_select(self, audit_conn, table: str) -> None:
        """synapse_app retains SELECT privilege (required for reads)."""
        cur = audit_conn.cursor()
        try:
            cur.execute(
                """
                SELECT has_table_privilege(%s, %s, 'SELECT')
                """,
                (AUDIT_DB_CONFIG["user"], table),
            )
            has_select = cur.fetchone()[0]
            assert has_select is True, (
                f"synapse_app must have SELECT on {table} for audit reads"
            )
        finally:
            cur.close()
