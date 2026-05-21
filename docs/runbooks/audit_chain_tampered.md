# Runbook: Audit Chain Tampered (ADR-033)

**Alert source:** `synapse_audit_chain_tamper_detected_total{source="verify_cli"} > 0`
(WS-6 §M-sec-4).

## Symptoms
- `synapse audit verify` exits 1 and prints `TAMPER: row=<uuid> ...`.
- The daily anchor artifact (`infrastructure/audit_anchors/<date>.json`)
  may already be uploaded → cross-check against a prior anchor.

## Likely Causes
1. **DB admin tampered** with a row via the `synapse` superuser
   (bypasses `synapse_app` grants).
2. **Backup-restore drift** — replica re-promoted with stale data.
3. **Replication lag bug** — `prev_hash` references a row not yet
   visible on the replica during failover.
4. **Bug in the writer** — `make_canonical_row` field set changed
   without a chain-rewrite migration. Treat as a P1 regression.

## Verification
```bash
# 1. Walk the chain since the last known-good anchor.
synapse audit verify --since=$(date -d '7 days ago' +%Y-%m-%d)

# 2. Cross-check against the GitHub Release anchor of that day.
gh release download audit-anchors --pattern '*.json' --dir /tmp
diff infrastructure/audit_anchors/<date>.json /tmp/<date>.json
```

## Mitigation
1. Open a P1 incident.
2. Quarantine the suspect rows: do NOT delete (audit immutability).
   Open a separate `audit_consensus_quarantine` view that lists the
   broken rows for forensics.
3. If the break is a known writer regression (verify against the
   commit log), fix the writer, then run a **chain rebuild migration**
   that recomputes `current_hash` from the genesis row. The new
   anchor diverges from the published artifact — publish a
   `corrected-<date>.json` and link the postmortem.
4. If the break is genuine tampering, treat as a security incident
   per the org's IR playbook.

## Postmortem Anchor
Always capture the offending `row_id`, both hashes (stored + computed),
and the immediately preceding `current_hash` so any reader can
reproduce the calculation.
