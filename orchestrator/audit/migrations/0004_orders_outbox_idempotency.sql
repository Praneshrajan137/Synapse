-- ============================================================================
-- SYNAPSE WS-2 — Orders ingress through the outbox + override idempotency.
-- CANONICAL source. Mirrored at infrastructure/postgres/05_ws2_orders_outbox.sql.
--
-- 1. ``audit_outbox.audit_id`` is created NULLABLE by the (rewritten) outbox DDL
--    so the API gateway can enqueue ingress events (orders) that do not yet
--    correspond to a consensus decision. The guarded DROP NOT NULL below is a
--    no-op on a fresh DB and only matters when reconciling a legacy volume.
--
-- 2. Add ``idempotency_key`` to ``audit_escalations`` + a partial UNIQUE index.
--    Operator overrides may be retried by the FE on network flake (FE-INV-021):
--    the retry MUST land on the same row.
--
-- 3. Ingress lookup index on the real ORM columns ``(status, next_attempt_at)``.
--
-- NOTE: this migration was historically broken — it ALTERed audit_outbox.audit_id
-- before any audit_id column existed (the old outbox DDL never created one), so it
-- errored and was quietly dropped from the GCP mounts + the CD migrator, taking
-- orders-ingress + override-idempotency with it. With the ORM-true outbox DDL it
-- is now valid and fully idempotent; re-included in both. (Sprint 20)
-- ============================================================================

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
