-- ============================================================================
-- SYNAPSE P1 — HITL Override audit columns (append-only)
--
-- The original I-4 contract grants synapse_app only SELECT + INSERT on
-- audit_decisions. Operator overrides MUST NOT mutate the original decision
-- row. Instead, we extend the existing audit_escalations table (also
-- INSERT-only) with operator-identity and override-reason columns, then
-- INSERT one row per override action.
--
-- Read path (Decision Theater / Audit Vault) joins audit_decisions to
-- audit_escalations by decision_id and renders both atomically.
-- ============================================================================

ALTER TABLE audit_escalations
    ADD COLUMN IF NOT EXISTS operator_token_ref VARCHAR(64),
    ADD COLUMN IF NOT EXISTS override_action    VARCHAR(20),
    ADD COLUMN IF NOT EXISTS override_reason    TEXT,
    ADD COLUMN IF NOT EXISTS override_at        TIMESTAMPTZ;

-- Enforce the override action enum at the DB layer.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints
        WHERE constraint_name = 'audit_escalations_override_action_chk'
    ) THEN
        ALTER TABLE audit_escalations
            ADD CONSTRAINT audit_escalations_override_action_chk
            CHECK (override_action IS NULL OR override_action IN ('approved','rejected','modified'));
    END IF;
END
$$;

-- Index for Audit Vault filter by operator (FE-INV-019).
CREATE INDEX IF NOT EXISTS idx_escalations_operator
    ON audit_escalations(operator_token_ref)
    WHERE operator_token_ref IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_escalations_override_at
    ON audit_escalations(override_at DESC)
    WHERE override_at IS NOT NULL;

-- Re-verify I-4: synapse_app must still have NO UPDATE/DELETE on
-- audit_decisions and audit_escalations. ALTER TABLE does not grant new
-- privileges, but we self-test anyway so configuration drift is caught.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.role_table_grants
        WHERE grantee = 'synapse_app'
          AND table_name IN ('audit_decisions','audit_escalations')
          AND privilege_type IN ('DELETE','UPDATE')
    ) THEN
        RAISE EXCEPTION 'I-4 VIOLATION: synapse_app has DELETE/UPDATE on an audit table';
    END IF;
    RAISE NOTICE 'I-4 still verified: audit_escalations is INSERT-only for synapse_app';
END
$$;
