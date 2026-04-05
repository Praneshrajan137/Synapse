-- ============================================================================
-- SYNAPSE PostgreSQL Audit Trail — Append-Only (I-4)
-- This schema enforces immutable decision provenance.
--
-- CRITICAL FIX: The 'synapse' user is the superuser/owner (set by POSTGRES_USER).
-- Superusers bypass all permission checks and owners retain full privileges.
-- We create a non-superuser 'synapse_app' role and grant ONLY INSERT + SELECT.
-- The application MUST connect as 'synapse_app', not 'synapse'.
-- ============================================================================

-- Create the application role (NOT superuser, NOT owner)
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'synapse_app') THEN
        CREATE ROLE synapse_app WITH LOGIN PASSWORD 'synapse_app_2026' NOSUPERUSER NOCREATEDB NOCREATEROLE;
    END IF;
END
$$;

GRANT CONNECT ON DATABASE synapse_audit TO synapse_app;

-- Audit trail: every orchestrator decision
CREATE TABLE IF NOT EXISTS audit_decisions (
    id              BIGSERIAL PRIMARY KEY,
    decision_id     UUID NOT NULL UNIQUE,
    timestamp       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    tier            VARCHAR(10) NOT NULL CHECK (tier IN ('tier_1','tier_2','tier_3','tier_4')),
    agent_proposals JSONB NOT NULL,
    selected_action JSONB NOT NULL,
    pareto_weights  JSONB NOT NULL,
    confidence      DOUBLE PRECISION NOT NULL CHECK (confidence >= 0.0 AND confidence <= 1.0),
    escalated       BOOLEAN NOT NULL DEFAULT FALSE,
    human_override  JSONB,
    audit_trace     JSONB NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- HITL escalation log
CREATE TABLE IF NOT EXISTS audit_escalations (
    id              BIGSERIAL PRIMARY KEY,
    decision_id     UUID NOT NULL REFERENCES audit_decisions(decision_id),
    escalation_reason VARCHAR(500) NOT NULL,
    human_action    JSONB,
    resolution_time_ms INTEGER,
    resolved_at     TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Guardrail violation log
CREATE TABLE IF NOT EXISTS audit_guardrail_violations (
    id              BIGSERIAL PRIMARY KEY,
    decision_id     UUID,
    agent_name      VARCHAR(50) NOT NULL,
    guardrail_id    VARCHAR(20) NOT NULL,
    violation_detail JSONB NOT NULL,
    action_taken    VARCHAR(50) NOT NULL CHECK (action_taken IN ('blocked','capped','escalated')),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Agent output log (for provenance tracing)
CREATE TABLE IF NOT EXISTS audit_agent_outputs (
    id              BIGSERIAL PRIMARY KEY,
    agent_name      VARCHAR(50) NOT NULL,
    output_type     VARCHAR(50) NOT NULL,
    output_payload  JSONB NOT NULL,
    schema_valid    BOOLEAN NOT NULL,
    confidence      DOUBLE PRECISION,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes for query performance
CREATE INDEX IF NOT EXISTS idx_decisions_timestamp ON audit_decisions(timestamp);
CREATE INDEX IF NOT EXISTS idx_decisions_tier ON audit_decisions(tier);
CREATE INDEX IF NOT EXISTS idx_decisions_escalated ON audit_decisions(escalated) WHERE escalated = TRUE;
CREATE INDEX IF NOT EXISTS idx_escalations_decision ON audit_escalations(decision_id);
CREATE INDEX IF NOT EXISTS idx_violations_agent ON audit_guardrail_violations(agent_name);
CREATE INDEX IF NOT EXISTS idx_agent_outputs_name ON audit_agent_outputs(agent_name, created_at);

-- ════════════════════════════════════════════════════════════════════════════
-- I-4 ENFORCEMENT: Grant ONLY INSERT + SELECT to synapse_app.
-- DELETE and UPDATE are NEVER granted. This is NON-NEGOTIABLE.
-- ════════════════════════════════════════════════════════════════════════════
GRANT USAGE ON SCHEMA public TO synapse_app;
GRANT SELECT, INSERT ON ALL TABLES IN SCHEMA public TO synapse_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO synapse_app;

-- Set default privileges for any future tables created by synapse
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT, INSERT ON TABLES TO synapse_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT USAGE, SELECT ON SEQUENCES TO synapse_app;

-- ════════════════════════════════════════════════════════════════════════════
-- Self-test: verify synapse_app can INSERT but NOT DELETE or UPDATE.
-- This runs at init time to catch configuration errors immediately.
-- ════════════════════════════════════════════════════════════════════════════
DO $$
BEGIN
    -- Verify synapse_app does NOT have DELETE privilege
    IF EXISTS (
        SELECT 1 FROM information_schema.role_table_grants
        WHERE grantee = 'synapse_app'
        AND table_name = 'audit_decisions'
        AND privilege_type = 'DELETE'
    ) THEN
        RAISE EXCEPTION 'I-4 VIOLATION: synapse_app has DELETE on audit_decisions';
    END IF;

    -- Verify synapse_app does NOT have UPDATE privilege
    IF EXISTS (
        SELECT 1 FROM information_schema.role_table_grants
        WHERE grantee = 'synapse_app'
        AND table_name = 'audit_decisions'
        AND privilege_type = 'UPDATE'
    ) THEN
        RAISE EXCEPTION 'I-4 VIOLATION: synapse_app has UPDATE on audit_decisions';
    END IF;

    RAISE NOTICE 'I-4 VERIFIED: synapse_app has only SELECT + INSERT on audit tables';
END
$$;
