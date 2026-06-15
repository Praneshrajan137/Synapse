-- ============================================================================
-- SYNAPSE Sprint 19 (ADR-047) — decision_outcomes (append-only fact stream)
--
-- The `outcome` JSONB column on audit_consensus (02_sprint4_consensus.sql:23)
-- has existed since Sprint 4 but the audit logger never wrote it — the system
-- recorded what it DECIDED but never what HAPPENED. We cannot fix that by
-- writing the column: audit_consensus grants synapse_app only INSERT + SELECT
-- (I-4, init_audit.sql:81 — UPDATE is NEVER granted, with a self-test).
--
-- So outcomes live here, as their own append-only fact stream keyed by
-- decision_id: the scorer (data_fabric/jobs/outcome_score.py) INSERTs one row
-- after the settle horizon; re-scoring INSERTs a newer row (readers take the
-- latest scored_at). The hashed canonical audit row is never touched
-- (E-S9-02). The legacy audit_consensus.outcome column is SUPERSEDED by this
-- table and stays NULL.
-- ============================================================================

CREATE TABLE IF NOT EXISTS decision_outcomes (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    decision_id  UUID NOT NULL,
    -- Tri-state honesty (ADR-047 D3): an outcome is `unknown` until a realized
    -- signal exists. `confirmed`/`diverged` are NEVER written without evidence.
    status       VARCHAR(16) NOT NULL CHECK (status IN ('confirmed','diverged','unknown')),
    -- Which realized signal produced the verdict: execution_confirmations,
    -- twin_divergence, or none (→ status MUST be 'unknown').
    source       VARCHAR(32) NOT NULL,
    realized     JSONB,
    error        DOUBLE PRECISION,
    horizon_s    INTEGER NOT NULL DEFAULT 0,
    scored_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_outcomes_decision_id ON decision_outcomes (decision_id);
CREATE INDEX IF NOT EXISTS idx_outcomes_scored_at ON decision_outcomes (scored_at DESC);
-- A constant 'none'/'unknown' source can never masquerade as a positive verdict.
CREATE INDEX IF NOT EXISTS idx_outcomes_status ON decision_outcomes (status);

-- ════════════════════════════════════════════════════════════════════════════
-- I-4 ENFORCEMENT: decision_outcomes is INSERT + SELECT only (append-only).
-- A scored outcome is a fact; it is never edited or deleted. Re-scoring appends.
-- ════════════════════════════════════════════════════════════════════════════
GRANT SELECT, INSERT ON decision_outcomes TO synapse_app;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.role_table_grants
        WHERE grantee = 'synapse_app'
          AND table_name = 'decision_outcomes'
          AND privilege_type IN ('DELETE','UPDATE')
    ) THEN
        RAISE EXCEPTION 'I-4 VIOLATION: synapse_app has DELETE/UPDATE on decision_outcomes';
    END IF;
    RAISE NOTICE 'I-4 VERIFIED: synapse_app has only SELECT + INSERT on decision_outcomes';
END
$$;
