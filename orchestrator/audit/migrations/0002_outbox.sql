-- ============================================================================
-- SYNAPSE Sprint 7 — Transactional outbox (WS-2 §3, ADR-026).
-- CANONICAL source. Mirrored at infrastructure/postgres/03_sprint7_outbox.sql
-- for docker-entrypoint init (E-S9-14). The two bodies MUST stay identical
-- apart from the header comment; scripts/audit/outbox_schema_truth.py (C55)
-- fails CI on any drift between them OR against the ORM.
--
-- SINGLE SOURCE OF TRUTH for the `audit_outbox` table — it MUST match
-- orchestrator/audit/models.py::AuditOutboxRow column-for-column. The previous
-- DDL created message_key/attempts/trace_id/sent_at + a TEXT status, while the
-- ORM (and synapse_common/outbox.py::enqueue, which flushes the row INSIDE the
-- decision's own transaction) writes audit_id/partition_key/headers/retries/
-- next_attempt_at/published_at/updated_at + an `outbox_status` ENUM. On a fresh
-- database that mismatch made the enqueue INSERT fail → the whole decision-
-- logging transaction rolled back → the orchestrator could not log ANY decision
-- (the live VM only ran because its volume was hand-patched; a new VM / DR
-- reverted to a backend that logged nothing, silently). This rewrite closes that.
--
-- The orchestrator's dispatcher drains status='PENDING' rows and publishes them
-- to Kafka with enable.idempotence=true. Unlike the append-only audit tables, the
-- dispatcher MUST UPDATE rows (PENDING → IN_FLIGHT → PUBLISHED|FAILED), so
-- synapse_app receives INSERT + SELECT + UPDATE on this table ONLY. DELETE is
-- still revoked (I-4); erasure goes through synapse_erasure_operator.
-- ============================================================================

-- Status ENUM. CREATE TYPE has no IF NOT EXISTS, so guard it for re-runnability.
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'outbox_status') THEN
        CREATE TYPE outbox_status AS ENUM ('PENDING', 'IN_FLIGHT', 'PUBLISHED', 'FAILED');
    END IF;
END
$$;

CREATE TABLE IF NOT EXISTS audit_outbox (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    -- Nullable: the API gateway enqueues ingress events (orders) that do not yet
    -- correspond to a consensus decision (WS-2). Consensus-tier rows set audit_id.
    audit_id        UUID REFERENCES audit_consensus(id) ON DELETE RESTRICT,
    decision_id     UUID NOT NULL,
    topic           VARCHAR(128) NOT NULL,
    partition_key   VARCHAR(256),
    payload         JSONB NOT NULL,
    headers         JSONB NOT NULL DEFAULT '{}',
    status          outbox_status NOT NULL DEFAULT 'PENDING',
    retries         INTEGER NOT NULL DEFAULT 0,
    last_error      TEXT,
    next_attempt_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    published_at    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Matches the dispatcher's claim query:
--   WHERE status='PENDING' AND next_attempt_at <= NOW()
--   ORDER BY next_attempt_at ... FOR UPDATE SKIP LOCKED.
CREATE INDEX IF NOT EXISTS idx_outbox_pending
    ON audit_outbox (next_attempt_at)
    WHERE status = 'PENDING';

CREATE INDEX IF NOT EXISTS idx_outbox_decision
    ON audit_outbox (decision_id);

-- INSERT + SELECT + UPDATE only. DELETE intentionally NOT granted (I-4).
GRANT SELECT, INSERT, UPDATE ON audit_outbox TO synapse_app;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.role_table_grants
        WHERE grantee = 'synapse_app'
          AND table_name = 'audit_outbox'
          AND privilege_type = 'DELETE'
    ) THEN
        RAISE EXCEPTION 'I-4 VIOLATION: synapse_app has DELETE on audit_outbox';
    END IF;
    RAISE NOTICE 'audit_outbox ready (ORM-true) with INSERT + SELECT + UPDATE grants only';
END
$$;
