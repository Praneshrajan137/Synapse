-- ============================================================================
-- SYNAPSE Sprint 4 — Consensus audit table (extends init_audit.sql)
-- I-4: Append-only.  Only INSERT + SELECT granted to synapse_app.
-- ============================================================================

CREATE TABLE IF NOT EXISTS audit_consensus (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    decision_id             UUID NOT NULL UNIQUE,
    timestamp               TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    tier                    VARCHAR(10) NOT NULL CHECK (tier IN ('tier_1','tier_2','tier_3','tier_4')),
    phase_reached           INTEGER NOT NULL DEFAULT 1 CHECK (phase_reached BETWEEN 1 AND 5),
    proposals               JSONB NOT NULL,
    selected_action         JSONB NOT NULL,
    pareto_weights          JSONB NOT NULL,
    confidence              DOUBLE PRECISION NOT NULL CHECK (confidence >= 0.0 AND confidence <= 1.0),
    debate_rounds           INTEGER NOT NULL DEFAULT 0,
    escalated               BOOLEAN NOT NULL DEFAULT FALSE,
    human_override          JSONB,
    execution_confirmations JSONB NOT NULL DEFAULT '[]',
    context_messages        JSONB NOT NULL,
    audit_trace             JSONB NOT NULL,
    pareto_front            JSONB,
    outcome                 JSONB,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes for operational and regulatory queries
CREATE INDEX IF NOT EXISTS idx_consensus_timestamp ON audit_consensus (timestamp);
CREATE INDEX IF NOT EXISTS idx_consensus_decision_id ON audit_consensus (decision_id);
CREATE INDEX IF NOT EXISTS idx_consensus_tier ON audit_consensus (tier);
CREATE INDEX IF NOT EXISTS idx_consensus_escalated ON audit_consensus (escalated) WHERE escalated = TRUE;

-- ════════════════════════════════════════════════════════════════════════════
-- I-4 ENFORCEMENT: synapse_app may only INSERT + SELECT.
-- ════════════════════════════════════════════════════════════════════════════
GRANT SELECT, INSERT ON audit_consensus TO synapse_app;

-- Self-test: verify privileges
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.role_table_grants
        WHERE grantee = 'synapse_app'
        AND table_name = 'audit_consensus'
        AND privilege_type = 'DELETE'
    ) THEN
        RAISE EXCEPTION 'I-4 VIOLATION: synapse_app has DELETE on audit_consensus';
    END IF;

    IF EXISTS (
        SELECT 1 FROM information_schema.role_table_grants
        WHERE grantee = 'synapse_app'
        AND table_name = 'audit_consensus'
        AND privilege_type = 'UPDATE'
    ) THEN
        RAISE EXCEPTION 'I-4 VIOLATION: synapse_app has UPDATE on audit_consensus';
    END IF;

    RAISE NOTICE 'I-4 VERIFIED: synapse_app has only SELECT + INSERT on audit_consensus';
END
$$;
