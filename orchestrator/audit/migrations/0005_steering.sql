-- ============================================================================
-- SYNAPSE WS-5 — Steering surface audit table.
--
-- The Atlas Console "Steering" surface lets an operator tune two governance
-- knobs: Pareto objective weights and per-tier confidence thresholds. Pre-
-- WS-5 these mutations lived only in localStorage (Zustand persist) and were
-- invisible to the audit trail — a compliance hole versus FE-INV-033.
--
-- This migration creates audit_steering, a forward-only log of every
-- operator change. The row is INSERTed by the gateway's POST
-- /api/v1/steering route inside the same hash-chain machinery as
-- audit_consensus (Sprint 9 ADR-033) so `synapse audit verify` walks both
-- in one pass.
--
-- Mirror at infrastructure/postgres/06_ws5_steering.sql for docker init.
-- ============================================================================

CREATE TABLE IF NOT EXISTS audit_steering (
    id                UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    -- Operator identity (token_ref, NOT raw operator_id — PII).
    operator_token_ref VARCHAR(128)   NOT NULL,
    -- The knob being mutated.
    action            VARCHAR(64)     NOT NULL CHECK (action IN (
                          'set_pareto_weight',
                          'set_tier_threshold',
                          'reset'
                      )),
    -- Which dimension (e.g. 'cost', 'time', 'tier_2'). NULL for reset.
    target            VARCHAR(64),
    -- New numeric value in [0,1]. NULL for reset.
    value             DOUBLE PRECISION,
    -- Replay-safe key from the gateway.
    idempotency_key   VARCHAR(64),
    -- Hash-chain (mirrors ADR-033 / audit_consensus).
    prev_hash         CHAR(64),
    current_hash      CHAR(64),
    created_at        TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

-- Partial UNIQUE keyed on (operator_token_ref, idempotency_key). Retries
-- with the same key by the same operator collapse to one row.
CREATE UNIQUE INDEX IF NOT EXISTS uq_audit_steering_idempotency
    ON audit_steering (operator_token_ref, idempotency_key)
    WHERE idempotency_key IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_audit_steering_recent
    ON audit_steering (created_at DESC);

DO $$
BEGIN
    RAISE NOTICE 'audit_steering ready (WS-5)';
END
$$;
