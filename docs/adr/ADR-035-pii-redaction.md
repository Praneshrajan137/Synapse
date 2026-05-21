# ADR-035: PII Redaction Policy

## Status
Accepted (Sprint 9, 2026-05-17)

## Context

DPDPA Article 8 (and broadly defensive engineering) requires that PII
never silently flows into:

- shipped log records (structlog → stdout → fluentbit → S3),
- the KV-cached prefix of any LLM prompt (where it would be retained
  in `synapse.audit.log` Kafka topic with -1 retention).

Sprint 7 audit + Sprint 8 spec coverage already prevent code-level
mistakes (no `print()`, no bare `except`); Sprint 9 adds the
*content-level* guard.

## Decision

Three layers:

1. **structlog `redact_pii` processor** at module level
   (`packages/synapse_common/logging_config.py`). Runs early in the
   processor chain so downstream renderers see scrubbed strings.
   Matches:
   - email (`[A-Za-z0-9._%+-]+@…`),
   - Indian mobile (`+91-9XXXXXXXXX` or 10-digit starting 6-9),
   - Aadhaar (12 digits, optionally grouped),
   - 6-digit PIN code.
   Each scrub increments `synapse_pii_redaction_total{field}` so the
   *attempted* leak is observable even after the redaction.

2. **Pre-commit / CI guard** (`scripts/check_llm_prompt_pii.py`)
   scans `orchestrator/llm/context_builder.py:SYSTEM_PROMPT`, every
   `agents/<name>/inference/*.py` prompt string, and
   `tests/eval/judge_prompt.md`. Any raw PII pattern fails the hook.

3. **DPDPA cascade helper** (`packages/synapse_common/dpdpa.py`)
   gives the runtime erasure operator one call site for purging a
   subject across Postgres + Neo4j (city-filtered per E-S6-05) +
   Feast online + Kafka tombstone on `synapse.audit.log`.

Sprint 9 ships the patterns + the redactor + the guard + the cascade
helper. Sprint 10 wires the runtime erasure operator into the HITL
console.

## Consequences

**Easier:**
- PII can't enter logs without surfacing as a redaction-counter
  spike — a far better signal than a quiet leak.
- KV-cache PII drift is caught at commit time, not in production.
- DPDPA erasure has one canonical call site (= one auditable code
  path).

**Harder:**
- The `redact_pii` processor scrubs string values *recursively* in
  log payloads — large nested dicts pay a small CPU cost. Profiling
  on Sprint 8's golden-trace suite shows < 1 µs per log call;
  acceptable.

## Alternatives Rejected

1. **Regex everywhere at log-call sites** — error-prone; one missed
   site silently leaks. Centralised processor is one-and-done.
2. **Tokenisation service** — overkill for the volume; introduces a
   third-party service.
3. **Schema-driven redaction (mark PII fields in Pydantic models)** —
   nice-to-have eventually, but requires every model to opt in.
   Sprint 9 stays defensive with regex; Sprint 11 can add the
   schema layer.

## References

- I-13: Deterministic JSON
- ADR-026: W3C trace propagation
- `packages/synapse_common/logging_config.py:redact_pii`
- `packages/synapse_common/dpdpa.py:cascade_erasure`
- `scripts/check_llm_prompt_pii.py`
- `docs/runbooks/dpdpa_erasure.md`
