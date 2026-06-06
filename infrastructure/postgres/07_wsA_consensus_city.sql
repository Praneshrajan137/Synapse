-- Mirror of orchestrator/audit/migrations/0006_consensus_city.sql for
-- docker-init (E-S9-14). Keep these two files byte-identical apart from this
-- header comment so the docker stack and the migrations runner agree.
--
-- Phase A (WS-A): add `city` to audit_consensus so the API decisions feed,
-- repointed from the dead `audit_decisions` table onto the real write target
-- `audit_consensus`, can SELECT city for the Decision Theater filter.

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
