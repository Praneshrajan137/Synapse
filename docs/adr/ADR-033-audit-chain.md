# ADR-033: Audit Chained-Hash Tamper-Evidence

## Status
Accepted (Sprint 9, 2026-05-17)

## Context

I-4 makes `audit_consensus` append-only at the DB level (DELETE +
UPDATE revoked from `synapse_app`). That stops _direct_ tampering by
the app, but not:

- a database admin with `synapse` superuser rights silently mutating
  a row,
- a compromised pod with stolen `synapse_erasure_operator` credentials
  selectively deleting rows after-the-fact,
- backup-restore drift between primary and replica.

We need **detection** as well as prevention.

## Decision

Each row in `audit_consensus` carries:

- `prev_hash CHAR(64)` — SHA-256 of the previous row's `current_hash`
  (genesis row uses 64 zeros).
- `current_hash CHAR(64)` — SHA-256(`prev_hash || canonical_json(row)`).

Population happens at insert time inside `AuditLogger.log_decision`
(Sprint 7's writer extended in Sprint 9). The chain head is cached
in-process + recovered from the DB on first insert.

`synapse audit verify --since=YYYY-MM-DD` walks the chain and asserts
each row's stored `current_hash` matches the recomputation. Any
mismatch increments
`synapse_audit_chain_tamper_detected_total{source="verify_cli"}` and
exits non-zero.

A daily `audit-anchor` job (Sprint 9 §M5 scheduler) captures the
latest `(created_at, current_hash)` to
`infrastructure/audit_anchors/<date>.json`. The existing GitHub
Releases workflow uploads that file as a public artifact — a free
pseudo-blockchain root any auditor can cross-check.

## Consequences

**Easier:**
- Any tampering between two anchor dates is mathematically detectable.
- DPDPA erasure (Sprint 9 §M-life-3) is observable: the cascade
  intentionally leaves chain gaps that the verifier surfaces with a
  documented "expected" annotation.
- The Postgres replica gets the same chain — replication divergence
  is detectable.

**Harder:**
- Audit row insert is now ~1 ms slower (one extra SELECT for the head
  on cold cache).
- `current_hash` becomes part of the canonical row content for
  rolling-window replay (Sprint 7 ADR-026 sibling).

## Alternatives Rejected

1. **Notary timestamping service** — costs money + adds a third-party
   dependency. Violates I-1.
2. **Immutable storage (S3 Object Lock)** — solves backup integrity
   but not in-flight Postgres tampering.
3. **Per-row HMAC with a single shared key** — single key is the
   single point of failure. Chain composition with public anchors
   distributes trust.

## References

- I-4: Append-only audit
- ADR-026: W3C trace propagation + outbox (Sprint 7)
- `orchestrator/audit/hash_chain.py`
- `orchestrator/audit/anchorer.py`
- `scripts/synapse_cli/audit_verify.py`
- `docs/runbooks/audit_chain_tampered.md`
