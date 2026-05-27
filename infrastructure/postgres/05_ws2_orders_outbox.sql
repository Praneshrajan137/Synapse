-- Mirror of orchestrator/audit/migrations/0004_orders_outbox_idempotency.sql
-- Loaded by docker-init (E-S9-14). Keep these two files byte-identical
-- (apart from this header comment) so the docker stack and the migrations
-- runner agree on the schema.

ALTER TABLE audit_outbox
    ALTER COLUMN audit_id DROP NOT NULL;

ALTER TABLE audit_escalations
    ADD COLUMN IF NOT EXISTS idempotency_key VARCHAR(64);

CREATE UNIQUE INDEX IF NOT EXISTS uq_audit_escalations_idempotency
    ON audit_escalations (decision_id, idempotency_key)
    WHERE idempotency_key IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_audit_outbox_ingress
    ON audit_outbox (status, next_attempt_at)
    WHERE audit_id IS NULL;
