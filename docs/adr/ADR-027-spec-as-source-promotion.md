# ADR-027: Spec-as-Source-of-Truth Promotion (Phase 1)

## Status
Accepted (Sprint 7, 2026-05-17)

## Context

Each agent ships an `agents/<name>/spec.yaml` with INV-* assertions,
metamorphic relations, and reward weights. Today the only artifact
derived from spec.yaml is `test_spec.py` (Sprint 1). The remaining
artifacts — JSON schemas, OpenAPI fragments, Prometheus alert rules,
reward configs — are hand-written and silently drift from the spec.

WS-3 in the Sprint-7–9 plan promotes spec.yaml to drive all of them.
Doing the full promotion in Sprint 7 is too risky (reward weights
migration is a behavior change). This ADR records the **phased**
plan.

## Decision

**Sprint 7 (this PR):**
- Ship `packages/synapse_common/schemas.py` as the canonical
  handler-boundary validator. Every A2A handler imports its schema
  name once and calls `validate_handler_input(...)`.

**Sprint 8 (deferred):**
- `scripts/spec_cli.py` with subcommands
  `validate | generate-tests | generate-schema | generate-openapi |
   generate-alerts`. Extension of
  `scripts/generate_tests_from_spec.py`, never a rewrite.
- Spec → Prometheus alerts wire-up; spec → OpenAPI extension; spec
  coverage gate (INV-*, MR-*, state-machine transitions).

**Sprint 8 shadow mode (deferred):**
- Spec → reward weights runs in shadow mode: read from both the
  spec block and the existing `reward_config.py`; alert on
  divergence; promote to source-of-truth only after one sprint of
  green shadow comparisons.

## Consequences

**Easier:**
- Handler outputs cannot diverge from `proto/domain/*.schema.json`
  without a test failure (Sprint 7 deliverable).
- Future spec-driven artifacts plug into the same validator surface.

**Harder:**
- The full promotion requires editor discipline: each agent's
  `spec.yaml` becomes the source of truth and PRs that change
  alert thresholds, reward weights, or schemas must touch the spec
  first.

## Alternatives Rejected

1. **Big-bang Sprint-7 promotion** — too much surface to land in one
   sprint without risk of regressions.
2. **Pydantic v2 schemas only, drop `proto/domain/*.json`** — but
   Pydantic schemas are Python-side; the JSON Schema files are the
   cross-language contract used by Schemathesis (Layer-2 fuzz) and
   the future external client SDKs.
