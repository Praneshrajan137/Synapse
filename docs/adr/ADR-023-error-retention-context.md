# ADR-023: Error Retention in Runtime Context

## Status
Accepted

## Context
Production research from Manus AI shows that removing errors, failed proposals, or guardrail rejections from the agent's runtime context during an active decision lifecycle causes **cyclical failure patterns** — the model repeats the same mistake because the prior failure is invisible. The instinct to "clean up" the context for the next attempt is wrong; the model needs the error trace to update its prior. This is independent of KV-cache concerns and applies even when summarization is otherwise tempting.

## Decision
The Orchestrator's runtime context is **append-only** during the active decision lifecycle (Phases 1-5):

- Error traces, failed proposals, guardrail rejections, and validation failures are **appended** with explicit failure annotations (`status: 'rejected'`, `rejection_reason: '...'`, `superseded_by: <id>`).
- They are **NEVER removed, replaced, or summarized** during the lifecycle.
- After the lifecycle commits to the audit log (I-4), the context is discarded — but errors are retained in the audit trail.
- Enforcement: `ContextMessage` Pydantic model is `frozen=True`; `append_to_context()` is the **only** method that modifies the message list; `deal` postcondition `len(new.messages) >= len(old.messages)` blocks all other mutations.
- Pre-commit hook detects `del`, `.pop()`, `.remove()`, list reassignment on `context.messages` in `protocol.py`.

This is Invariant I-14.

## Consequences
- Cyclical failure patterns are eliminated; each retry sees prior failures.
- Context grows during long debates (max 30s, max 3 rounds — bounded).
- Storage cost is trivial (per-decision, not persistent).
- Auditability improves — every rejected proposal is preserved.
- Runtime context size is bounded by max debate rounds × max agents × max payload size.

## Alternatives Rejected
- **Error removal**: rejected — root cause of cyclical failures.
- **Summarization**: rejected — loses the structured signal the model needs.
- **External error log only (not in context)**: rejected — model cannot see it during the next iteration.
