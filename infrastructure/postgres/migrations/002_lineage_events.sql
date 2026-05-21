-- ============================================================================
-- SYNAPSE Sprint 7 migration 002 — ETL lineage events (ADR-026)
-- ============================================================================
-- Append-only. synapse_app gets only INSERT + SELECT. Lineage is observability,
-- not authoritative state — it's allowed to be lossy under Postgres pressure.
-- ============================================================================

CREATE TABLE IF NOT EXISTS lineage_events (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id      UUID NOT NULL,
    job_name    VARCHAR(128) NOT NULL,
    event_type  VARCHAR(16) NOT NULL CHECK (event_type IN ('START','COMPLETE','FAIL')),
    event_time  TIMESTAMPTZ NOT NULL,
    inputs      JSONB NOT NULL DEFAULT '[]',
    outputs     JSONB NOT NULL DEFAULT '[]',
    facets      JSONB NOT NULL DEFAULT '{}',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_lineage_run_id ON lineage_events (run_id);
CREATE INDEX IF NOT EXISTS idx_lineage_job ON lineage_events (job_name);
CREATE INDEX IF NOT EXISTS idx_lineage_time ON lineage_events (event_time DESC);

GRANT SELECT, INSERT ON lineage_events TO synapse_app;

-- I-4: lineage table inherits append-only semantics. Verify.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.role_table_grants
        WHERE grantee = 'synapse_app'
          AND table_name = 'lineage_events'
          AND privilege_type IN ('UPDATE', 'DELETE')
    ) THEN
        RAISE EXCEPTION 'I-4 VIOLATION: synapse_app has UPDATE or DELETE on lineage_events';
    END IF;
END
$$;
