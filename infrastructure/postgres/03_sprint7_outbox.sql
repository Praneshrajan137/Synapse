-- ============================================================================
-- SYNAPSE Sprint 7 — Transactional outbox (mirrored from
-- orchestrator/audit/migrations/0002_outbox.sql for docker-entrypoint init).
-- ============================================================================

CREATE TABLE IF NOT EXISTS audit_outbox (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    decision_id     UUID NOT NULL,
    topic           TEXT NOT NULL,
    message_key     TEXT,
    payload         JSONB NOT NULL,
    status          TEXT NOT NULL DEFAULT 'PENDING'
                    CHECK (status IN ('PENDING', 'SENT', 'FAILED')),
    attempts        INTEGER NOT NULL DEFAULT 0,
    last_error      TEXT,
    trace_id        TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    sent_at         TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_outbox_pending
    ON audit_outbox (created_at)
    WHERE status = 'PENDING';

CREATE INDEX IF NOT EXISTS idx_outbox_decision
    ON audit_outbox (decision_id);

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

    RAISE NOTICE 'audit_outbox created with INSERT + SELECT + UPDATE grants only';
END
$$;
