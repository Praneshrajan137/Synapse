# ADR-026: ETL quality gates + lineage via the audit ledger

## Status
Accepted (Sprint 7)

## Context
The ETL layer (`data_fabric/etl/kafka_to_parquet.py`) silently dropped
malformed rows: a row that failed deserialization or schema validation
disappeared with a WARN log and no replay path. There was no data-lineage
record, no quarantine, and no schema-evolution check. Compliance asks
"where did this column come from?" had no answer.

I-6 freezes the 16 Kafka topics post-Sprint 1, so a 17th `etl.lineage.v1`
topic — the OpenLineage-canonical place to put events — is not allowed.

## Decision
Three additive ETL modules, all pyarrow + stdlib (zero-cost, I-1):

1. **`data_fabric/etl/quality_gates.py`** — composable `GateRegistry` with
   built-ins for null-presence, range, freshness, and JSON Schema. Failed
   rows are appended to `data_fabric/quarantine/<YYYYMMDD>/<topic>.jsonl`,
   never dropped.
2. **`data_fabric/etl/lineage.py`** — emits OpenLineage-1.0 events into
   PostgreSQL's `lineage_events` table (migration `002_lineage_events.sql`)
   and stamps the active OTel span with `synapse.lineage.run_id`. *No new
   Kafka topic* — preserves I-6.
3. **`data_fabric/etl/schema_evolution.py`** — pre-commit gate verifying
   that a proposed schema is backward-compatible (no removed required
   fields, no narrowed types, no shrunk enums).

`backfill.py` provides a deterministic date-range replay that emits
START/COMPLETE lineage envelopes and feeds the same quality gates.

## Consequences
- Every quality failure is recoverable from the quarantine directory.
- A regulator can ask "show me every dataset that fed into this decision"
  and the answer is a SQL JOIN on `lineage_events` → `audit_consensus`.
- Postgres becomes a soft-state lineage sink — degrades open if down.
- Schema evolution is now CI-enforced, no more bus-factor in code review.

## Alternatives Rejected
- **Great Expectations** — heavy dependency, paid hosted offering tempts
  scope creep. Our gate set is small; pyarrow suffices.
- **Marquez (OpenLineage server)** — additional service we don't run; would
  duplicate the audit ledger's append-only properties.
- **Adding a 17th Kafka topic** — would break I-6 and the v4-compliance gate.
