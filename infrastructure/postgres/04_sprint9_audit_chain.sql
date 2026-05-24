-- ============================================================================
-- SYNAPSE Sprint 9 — Audit chained-hash tamper-evidence (mirrored from
-- orchestrator/audit/migrations/0003_audit_chain.sql for docker-entrypoint init).
-- ============================================================================

ALTER TABLE audit_consensus
    ADD COLUMN IF NOT EXISTS prev_hash    CHAR(64),
    ADD COLUMN IF NOT EXISTS current_hash CHAR(64);

CREATE INDEX IF NOT EXISTS idx_consensus_chain_order
    ON audit_consensus (created_at, id);

DO $$
BEGIN
    RAISE NOTICE 'audit_consensus chained-hash columns ready (Sprint 9 §M-sec-4)';
END
$$;
