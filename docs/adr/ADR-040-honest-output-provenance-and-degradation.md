# ADR-040: Honest Output Provenance & Runtime Invariant Validation

## Status
Accepted (Plan v2 — Substance Mandate, 2026-05-30)

## Context

Sprints 11–13 built a fully honest *enforcement* boundary: per-package coverage
floors, mutation PR-gates, assertion-matched spec coverage, and the
`verify_claims.py` truth ledger. That machinery proves an agent output satisfies
its schema (I-3), its DbC postconditions, its latency SLA (I-10), and its price
caps. It does **not** prove the output is real.

Direct inspection (`docs/state/substance-baseline-2026-05-30.md`) found every
`agents/*/inference/pipeline.py` returning synthetic features and fallback
predictions **unconditionally** — the `if self._dep is None:` guard logs a
warning, then the *next line* returns the fallback regardless of whether a real
model / Feast / Neo4j was injected. Confidence was a hardcoded constant (`0.85`).

This is dangerous, not cosmetic:

- **It kills I-5.** A constant confidence above the HITL threshold means
  confidence-gated escalation can never fire. The safety mechanism is dead by
  construction. Only genuine model uncertainty makes I-5 mean anything.
- **It makes I-3 a test-time fiction.** Postconditions are checked in tests
  against hand-built inputs, never re-checked on the live serving output.
- **It corrupts consensus.** A silent I-7 fallback enters Pareto arbitration with
  the same weight as a genuine prediction. The orchestrator cannot down-weight
  what it cannot see.

## Decision

**Every served agent output carries machine-readable provenance, and pipelines
re-validate their own spec postconditions on the live output before publishing.**

### Rule 1 — The `Provenance` value object

`packages/synapse_common/provenance.py` defines a frozen `Provenance` recording
`model_version`, `feature_source` (`feast`|`fallback`), `degraded` (bool), and
`confidence_basis`. `confidence_basis` is an enum whose `CONSTANT` member is a
documented smell — a real path MUST use an uncertainty-derived basis
(conformal interval, ensemble variance, posterior spread, …). `Provenance.real(...)`
refuses to construct a non-degraded provenance with a `CONSTANT`/`FALLBACK_FLOOR`
basis or a `degraded` model_version.

### Rule 2 — Provenance rides the A2A envelope, not the domain payload

The domain output schemas (`proto/domain/*.schema.json`) are frozen inter-agent
data contracts with `additionalProperties: false`; polluting them with serving
metadata would risk I-3 across the whole system and the KV-cached body (I-13).
Instead, provenance is attached to the **`AgentProposal`** — the orchestration
envelope that crosses A2A and feeds the I-4 audit — via `payload["provenance"]`
(a `Provenance.model_dump()`) plus a human-readable `provenance.trace_line()`
appended to `justification_trace`. The domain output (e.g. `DemandForecast`) is
the inner *value*; the proposal is the *served unit*. Zero schema churn.

### Rule 3 — Confidence is derived, never constant

Each pipeline derives `confidence` from its model's uncertainty
(`agents/*/spec.yaml` records the basis per agent) and stamps the matching
`ConfidenceBasis`. On the I-7 fallback path, `confidence` is the documented
fallback floor and `degraded=True` — honest, not silently confident.

### Rule 4 — Runtime invariant validation

`packages/synapse_common/invariants.py` provides `RuntimeValidator`, which
re-checks the JSON-Schema contract (reusing `schema_registry`) plus the agent's
`spec.yaml` postconditions — the same logical assertions already expressed as
`@deal.post` — on the **live output** immediately before publish. A breach raises
`InvariantViolation`, so a malformed prediction is never published. This
generalizes I-3 from a test-time contract to a runtime guard.

### Rule 5 — The gap is a mechanical, ratcheting gate

`scripts/audit/substance_truth.py` AST-flags the synthetic-shortcut anti-patterns
(ignored dependency, hardcoded confidence, random model input). `verify_claims.py`
**C33** ratchets the violation count toward zero; Phase 4 wires
`substance_truth.py --check` as a hard blocking gate at zero.

## Consequences

- **Positive:** I-5 becomes live; I-3 is enforced at runtime; consensus can
  down-weight degraded proposals; the audit trail records which model version
  produced each decision; no domain schema changes (I-3 risk avoided).
- **Negative:** pipelines carry slightly more wiring (provider + registry +
  validator). Mitigated by the shared anti-corruption layer (ADR-041) so the
  per-agent surface stays thin.
- **Neutral:** provenance in `payload` is opt-in for downstream readers; existing
  consumers that ignore it are unaffected.

## Alternatives considered

- *Add `provenance` to every domain output schema.* Rejected: 8 frozen schemas
  with `additionalProperties: false`, real I-3 regression surface, KV-cache risk,
  for metadata that belongs on the envelope.
- *Keep confidence constant, add only `degraded`.* Rejected: leaves I-5 dead.
