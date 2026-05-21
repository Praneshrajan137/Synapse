-- ============================================================================
-- SYNAPSE Sprint 7 migration 001 — causal envelope + explainable consensus
-- ADR-027 (causation_id + correlation_id)
-- ADR-028 (rationale + counterfactuals)
-- ============================================================================
-- Idempotent: every column add is IF NOT EXISTS.
-- I-4 still holds — synapse_app retains only INSERT + SELECT on this table.
-- ============================================================================

ALTER TABLE audit_consensus
    ADD COLUMN IF NOT EXISTS correlation_id    VARCHAR(64),
    ADD COLUMN IF NOT EXISTS causation_chain   JSONB,
    ADD COLUMN IF NOT EXISTS rationale         JSONB,
    ADD COLUMN IF NOT EXISTS counterfactuals   JSONB;

CREATE INDEX IF NOT EXISTS idx_consensus_correlation_id
    ON audit_consensus (correlation_id);

-- Sanity: synapse_app must NOT have UPDATE/DELETE on the new columns either.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.role_table_grants
        WHERE grantee = 'synapse_app'
          AND table_name = 'audit_consensus'
          AND privilege_type IN ('UPDATE', 'DELETE')
    ) THEN
        RAISE EXCEPTION 'I-4 VIOLATION: synapse_app has UPDATE or DELETE on audit_consensus';
    END IF;
END
$$;
