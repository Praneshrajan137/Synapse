-- ============================================================================
-- SYNAPSE Sprint 9 — Audit chained-hash tamper-evidence (WS-6 §M-sec-4, ADR-033).
--
-- Adds prev_hash + current_hash columns to audit_consensus. Existing rows have
-- NULL chain values (legacy); new rows always populate. ``synapse audit verify``
-- walks from the genesis row and asserts each ``current_hash`` equals
-- SHA-256(prev_hash || canonical_json(row)).
--
-- Mirror file at infrastructure/postgres/04_sprint9_audit_chain.sql for the
-- docker-init path. Migration is additive + reversible (DROP COLUMN works).
-- ============================================================================

ALTER TABLE audit_consensus
    ADD COLUMN IF NOT EXISTS prev_hash    CHAR(64),
    ADD COLUMN IF NOT EXISTS current_hash CHAR(64);

CREATE INDEX IF NOT EXISTS idx_consensus_chain_order
    ON audit_consensus (created_at, id);

-- synapse_app already has INSERT + SELECT on this table; chain population happens
-- via the same INSERT path so no additional grants are required.

DO $$
BEGIN
    RAISE NOTICE 'audit_consensus chained-hash columns ready (Sprint 9 §M-sec-4)';
END
$$;
