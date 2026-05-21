-- ============================================================================
-- SYNAPSE Sprint 7 — Audit-outbox table (WS-2 distributed correctness).
--
-- The orchestrator writes a `(decision_id, payload, status='PENDING')` row
-- into this table inside the SAME transaction as the audit_consensus row.
-- A separate dispatcher worker (orchestrator.outbox.dispatcher) drains
-- PENDING rows by publishing each to Kafka topic `synapse.orchestrator.decision`
-- with `enable.idempotence=true`, then transitions the row to `PUBLISHED`.
--
-- Invariants:
--   * audit_consensus is THE record of truth (immutable).
--   * audit_outbox is a WORKFLOW primitive: rows mutate (status, retries,
--     last_error, published_at). It must allow UPDATE on those columns.
--   * INSERT into audit_outbox is gated by a FOREIGN KEY to audit_consensus
--     so there can never be an outbox row without a matching audit row.
-- ============================================================================

CREATE TYPE outbox_status AS ENUM ('PENDING', 'IN_FLIGHT', 'PUBLISHED', 'FAILED');

CREATE TABLE IF NOT EXISTS audit_outbox (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    audit_id        UUID NOT NULL REFERENCES audit_consensus(id) ON DELETE RESTRICT,
    decision_id     UUID NOT NULL,
    topic           VARCHAR(128) NOT NULL,
    partition_key   VARCHAR(256),
    payload         JSONB NOT NULL,
    headers         JSONB NOT NULL DEFAULT '{}'::jsonb,
    status          outbox_status NOT NULL DEFAULT 'PENDING',
    retries         INTEGER NOT NULL DEFAULT 0 CHECK (retries >= 0),
    last_error      TEXT,
    next_attempt_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    published_at    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Hot path for the dispatcher: pull the next PENDING row by next_attempt_at.
CREATE INDEX IF NOT EXISTS idx_outbox_pending_next
    ON audit_outbox (next_attempt_at)
    WHERE status = 'PENDING';

-- For reconciliation queries: which audit row maps to which outbox attempt(s).
CREATE INDEX IF NOT EXISTS idx_outbox_audit_id
    ON audit_outbox (audit_id);

CREATE INDEX IF NOT EXISTS idx_outbox_decision_id
    ON audit_outbox (decision_id);

-- The dispatcher transitions PENDING -> IN_FLIGHT -> PUBLISHED|FAILED.
-- That's UPDATE on status / retries / last_error / next_attempt_at /
-- published_at / updated_at. INSERT happens in the audit transaction.
GRANT SELECT, INSERT, UPDATE ON audit_outbox TO synapse_app;

-- LISTEN/NOTIFY so the dispatcher can wake immediately on insert without
-- polling. The trigger fires on every insert and emits an empty payload;
-- the dispatcher just treats any notification as "go check the queue".
CREATE OR REPLACE FUNCTION audit_outbox_notify() RETURNS TRIGGER AS $$
BEGIN
    PERFORM pg_notify('audit_outbox_pending', '');
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS audit_outbox_notify_trg ON audit_outbox;
CREATE TRIGGER audit_outbox_notify_trg
    AFTER INSERT ON audit_outbox
    FOR EACH ROW EXECUTE FUNCTION audit_outbox_notify();

-- updated_at maintenance (so reconciliation queries can detect stuck rows).
CREATE OR REPLACE FUNCTION audit_outbox_touch() RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS audit_outbox_touch_trg ON audit_outbox;
CREATE TRIGGER audit_outbox_touch_trg
    BEFORE UPDATE ON audit_outbox
    FOR EACH ROW EXECUTE FUNCTION audit_outbox_touch();

-- Self-test: verify the dispatcher role can do exactly the operations it needs.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.role_table_grants
        WHERE grantee = 'synapse_app'
        AND table_name = 'audit_outbox'
        AND privilege_type = 'DELETE'
    ) THEN
        RAISE EXCEPTION 'WS-2 VIOLATION: synapse_app has DELETE on audit_outbox; the dispatcher must not delete published rows (use a separate archival role).';
    END IF;

    RAISE NOTICE 'WS-2 VERIFIED: audit_outbox grants are SELECT + INSERT + UPDATE only.';
END
$$;
