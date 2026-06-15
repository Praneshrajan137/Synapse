-- Mirror of orchestrator/audit/migrations/0004_orders_outbox_idempotency.sql
-- Loaded by docker-init (E-S9-14). Keep the body identical apart from this
-- header so the docker stack and the migration runner agree on the schema.
--
-- Re-included in the GCP mounts + the CD migrator in Sprint 20: with the ORM-true
-- outbox DDL (05_sprint7_outbox.sql / 0002_outbox.sql) this migration is valid and
-- idempotent. It was previously dropped because it ALTERed a non-existent
-- audit_id column and errored, taking orders-ingress + override-idempotency with it.

-- (1) Relax audit_outbox.audit_id (no-op on a fresh DB; guarded for re-runs).
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'audit_outbox' AND column_name = 'audit_id'
    ) THEN
        ALTER TABLE audit_outbox ALTER COLUMN audit_id DROP NOT NULL;
    END IF;
END
$$;

-- (2) Override idempotency.
ALTER TABLE audit_escalations
    ADD COLUMN IF NOT EXISTS idempotency_key VARCHAR(64);

CREATE UNIQUE INDEX IF NOT EXISTS uq_audit_escalations_idempotency
    ON audit_escalations (decision_id, idempotency_key)
    WHERE idempotency_key IS NOT NULL;

-- (3) Ingress-event lookup index (audit_id IS NULL), on real ORM columns.
CREATE INDEX IF NOT EXISTS idx_audit_outbox_ingress
    ON audit_outbox (status, next_attempt_at)
    WHERE audit_id IS NULL;

DO $$
BEGIN
    RAISE NOTICE 'orders-outbox + override-idempotency ready (WS-2)';
END
$$;
