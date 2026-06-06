-- ============================================================================
-- SYNAPSE Phase A (WS-A) — Add city column to audit_consensus.
--
-- ROOT CAUSE THIS FIXES: the orchestrator writes every decision to
-- `audit_consensus` (orchestrator/audit/models.py::AuditConsensusRow), but the
-- API read path (api/routers/decisions.py) selected `phase_reached` + `city`
-- FROM the *legacy* `audit_decisions` table — which has neither `phase_reached`
-- (that column lives on audit_consensus) nor, on the consensus table, `city`.
-- The live `GET /api/v1/decisions/recent` therefore 503'd with
-- `column "phase_reached" does not exist`. Repointing the API to
-- audit_consensus needs a `city` column there for the Decision Theater filter
-- (FE-INV-016), mirroring 04_p3_city.sql which added it to audit_decisions.
--
-- Backfill existing rows with 'bengaluru' (the single city the write path
-- currently records; per-decision city threading is a tracked follow-up).
-- Idempotent: ADD COLUMN IF NOT EXISTS + guarded constraint + IF NOT EXISTS
-- index, so it is safe to re-run on every deploy. I-4 still holds: the
-- migration runs as the schema owner; synapse_app gets no UPDATE/DELETE.
-- ============================================================================

ALTER TABLE audit_consensus
    ADD COLUMN IF NOT EXISTS city VARCHAR(20) NOT NULL DEFAULT 'bengaluru';

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints
        WHERE constraint_name = 'audit_consensus_city_chk'
    ) THEN
        ALTER TABLE audit_consensus
            ADD CONSTRAINT audit_consensus_city_chk
            CHECK (city IN ('bengaluru','mumbai'));
    END IF;
END
$$;

CREATE INDEX IF NOT EXISTS idx_consensus_city_created
    ON audit_consensus(city, created_at DESC);

-- Re-verify I-4: synapse_app must still have NO UPDATE/DELETE on
-- audit_consensus. ALTER doesn't grant new privileges, but we self-test so
-- configuration drift is caught at migration time.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.role_table_grants
        WHERE grantee = 'synapse_app'
          AND table_name = 'audit_consensus'
          AND privilege_type IN ('DELETE','UPDATE')
    ) THEN
        RAISE EXCEPTION 'I-4 VIOLATION: synapse_app has DELETE/UPDATE on audit_consensus';
    END IF;
    RAISE NOTICE 'I-4 still verified: audit_consensus remains INSERT-only';
END
$$;
