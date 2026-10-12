-- ============================================================================
-- SYNAPSE purpose-achievement-audit (design AD-10, conflict CF-1)
--   decision_data_provenance -- append-only data-provenance fact stream
--
-- Canonical: orchestrator/audit/migrations/0007_decision_data_provenance.sql
-- Mirror:    infrastructure/postgres/09_decision_data_provenance.sql (E-S9-14 --
--            Docker init reads from infrastructure/postgres/, so every canonical
--            migration is mirrored there and listed in scripts/db/migrate.sh;
--            an unmirrored, unlisted migration is silently skipped, which is
--            exactly how the WS-2 outbox migration rotted).
--
-- WHY A NEW TABLE AND NOT A COLUMN. R4.4 requires the audit record for a
-- decision convened from non-synthetic state to carry a data-provenance value
-- distinct from a simulation-sourced decision's. The audit row's hashed
-- canonical field set is byte-pinned (I-4 / E-S9-02: adding or removing a field
-- in orchestrator/audit/hash_chain.py::make_canonical_row requires a
-- chain-rewrite migration, not a silent field bump), and synapse_app holds no
-- UPDATE on audit_consensus anyway (init_audit.sql:81). So provenance lives
-- here, as its own append-only stream keyed by decision_id -- the same shape
-- ADR-047 D2 chose for decision_outcomes. make_canonical_row is untouched and
-- its literal-digest test still passes; a reader joins audit_consensus to this
-- table on decision_id.
--
-- The writer (purpose-achievement-audit task 10.11) INSERTs one row per
-- convened decision from the active WorldSource's declared provenance
-- (SourceProvenance: SEEDED | EXTERNAL | STUB, design AD-11). A correction
-- appends a newer row; readers take the latest observed_at. The row shape is
-- orchestrator/audit/models.py::DecisionDataProvenance.
--
-- Idempotent (CREATE TABLE / CREATE INDEX IF NOT EXISTS, guarded constraint,
-- no-op REVOKE), so applying the full ordered chain on every deploy is safe.
-- ============================================================================

CREATE TABLE IF NOT EXISTS decision_data_provenance (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    decision_id   UUID NOT NULL,
    -- Which class of world source produced the perceived state this decision was
    -- convened from. This is the value R4.4 requires to be distinguishable; a
    -- STUB source (an unconditionally empty poll_arrivals, R4.8) can therefore
    -- never be recorded as external.
    source_class  VARCHAR(16) NOT NULL,
    -- Derived from source_class by the caller (AD-11), never pinned to a literal.
    -- Stored as handed over so a disagreement stays visible in the audit trail.
    is_synthetic  BOOLEAN NOT NULL,
    -- Feed offset/revision where the source exposes one; NULL for sources that
    -- have no revision concept (a seeded generator).
    feed_revision VARCHAR(128),
    -- When the input state was observed (TIMESTAMPTZ: a naive instant would read
    -- differently per locale).
    observed_at   TIMESTAMPTZ NOT NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Guarded rather than inline so re-running against an existing table converges.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints
        WHERE constraint_name = 'decision_data_provenance_source_class_chk'
    ) THEN
        ALTER TABLE decision_data_provenance
            ADD CONSTRAINT decision_data_provenance_source_class_chk
            CHECK (source_class IN ('SEEDED','EXTERNAL','STUB'));
    END IF;
END
$$;

CREATE INDEX IF NOT EXISTS idx_provenance_decision_id
    ON decision_data_provenance (decision_id);
CREATE INDEX IF NOT EXISTS idx_provenance_observed_at
    ON decision_data_provenance (observed_at DESC);
-- Lets the feed-provenance gate count externally-driven decisions without a scan,
-- so "the loop ran on real data" can never be asserted without rows behind it.
CREATE INDEX IF NOT EXISTS idx_provenance_source_class
    ON decision_data_provenance (source_class);

-- ============================================================================
-- I-4 ENFORCEMENT: decision_data_provenance is INSERT + SELECT only.
-- A recorded provenance is a fact; it is never edited or deleted. A correction
-- appends. init_audit.sql's ALTER DEFAULT PRIVILEGES already limits new tables
-- to SELECT + INSERT; the explicit GRANT + REVOKE below make this table's
-- contract local and readable, and the self-test fails the migration loudly if
-- configuration ever drifts.
-- ============================================================================
GRANT SELECT, INSERT ON decision_data_provenance TO synapse_app;
REVOKE UPDATE, DELETE ON decision_data_provenance FROM synapse_app;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.role_table_grants
        WHERE grantee = 'synapse_app'
          AND table_name = 'decision_data_provenance'
          AND privilege_type IN ('DELETE','UPDATE')
    ) THEN
        RAISE EXCEPTION 'I-4 VIOLATION: synapse_app has DELETE/UPDATE on decision_data_provenance';
    END IF;
    RAISE NOTICE 'I-4 VERIFIED: synapse_app has only SELECT + INSERT on decision_data_provenance';
END
$$;
