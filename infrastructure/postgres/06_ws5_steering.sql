-- Mirror of orchestrator/audit/migrations/0005_steering.sql for docker-init.

CREATE TABLE IF NOT EXISTS audit_steering (
    id                UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    operator_token_ref VARCHAR(128)   NOT NULL,
    action            VARCHAR(64)     NOT NULL CHECK (action IN (
                          'set_pareto_weight',
                          'set_tier_threshold',
                          'reset'
                      )),
    target            VARCHAR(64),
    value             DOUBLE PRECISION,
    idempotency_key   VARCHAR(64),
    prev_hash         CHAR(64),
    current_hash      CHAR(64),
    created_at        TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_audit_steering_idempotency
    ON audit_steering (operator_token_ref, idempotency_key)
    WHERE idempotency_key IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_audit_steering_recent
    ON audit_steering (created_at DESC);
