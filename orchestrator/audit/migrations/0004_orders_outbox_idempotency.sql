-- ============================================================================
-- SYNAPSE WS-2 — Orders ingress through the outbox + override idempotency.
--
-- 1. Make ``audit_outbox.audit_id`` NULLABLE so the API gateway can enqueue
--    ingress events (orders) that do not yet correspond to a consensus
--    decision row. The FK remains; consensus-tier rows still set audit_id.
--
-- 2. Add ``idempotency_key`` column to ``audit_escalations`` + a partial
--    UNIQUE index. Operator overrides may be retried by the FE on network
--    flake (FE-INV-021): the second retry MUST land on the same row.
--    The UNIQUE is partial (WHERE idempotency_key IS NOT NULL) so legacy
--    rows without a key continue to be valid.
--
-- Mirror at infrastructure/postgres/05_ws2_orders_outbox.sql for Docker
-- init. Reversible: ALTER COLUMN ... SET NOT NULL re-tightens; DROP INDEX
-- + DROP COLUMN removes the idempotency lane.
-- ============================================================================

-- (1) Relax audit_outbox.audit_id so it can carry ingress events.
ALTER TABLE audit_outbox
    ALTER COLUMN audit_id DROP NOT NULL;

-- (2) Override idempotency.
ALTER TABLE audit_escalations
    ADD COLUMN IF NOT EXISTS idempotency_key VARCHAR(64);

-- Partial unique: only enforce when the caller supplied a key. Replay-safe.
CREATE UNIQUE INDEX IF NOT EXISTS uq_audit_escalations_idempotency
    ON audit_escalations (decision_id, idempotency_key)
    WHERE idempotency_key IS NOT NULL;

-- Speed up ingress-event lookups (no audit_id) so the dispatcher's
-- ``WHERE status = 'PENDING'`` query stays bounded.
CREATE INDEX IF NOT EXISTS idx_audit_outbox_ingress
    ON audit_outbox (status, next_attempt_at)
    WHERE audit_id IS NULL;

DO $$
BEGIN
    RAISE NOTICE 'orders-outbox + override-idempotency ready (WS-2)';
END
$$;
