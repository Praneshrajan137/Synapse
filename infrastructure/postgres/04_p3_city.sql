-- ============================================================================
-- SYNAPSE P3 — Add city column to audit_decisions (E-S6-05 / FE-INV-016).
--
-- Backfill existing rows with 'bengaluru' (the city for pre-P3 history).
-- Index on (city, created_at DESC) speeds the Decision Theater filter.
-- I-4 still holds: synapse_app gets no UPDATE/DELETE; the migration runs
-- as the schema owner.
-- ============================================================================

ALTER TABLE audit_decisions
    ADD COLUMN IF NOT EXISTS city VARCHAR(20) NOT NULL DEFAULT 'bengaluru';

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints
        WHERE constraint_name = 'audit_decisions_city_chk'
    ) THEN
        ALTER TABLE audit_decisions
            ADD CONSTRAINT audit_decisions_city_chk
            CHECK (city IN ('bengaluru','mumbai'));
    END IF;
END
$$;

CREATE INDEX IF NOT EXISTS idx_decisions_city_created
    ON audit_decisions(city, created_at DESC);

-- Re-verify I-4: synapse_app must still have NO UPDATE/DELETE on
-- audit_decisions. ALTER doesn't grant new privileges, but we self-test.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.role_table_grants
        WHERE grantee = 'synapse_app'
          AND table_name = 'audit_decisions'
          AND privilege_type IN ('DELETE','UPDATE')
    ) THEN
        RAISE EXCEPTION 'I-4 VIOLATION: synapse_app has DELETE/UPDATE on audit_decisions';
    END IF;
    RAISE NOTICE 'I-4 still verified: audit_decisions remains INSERT-only';
END
$$;
