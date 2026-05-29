# ADR-041: Shared Feature & Model Anti-Corruption Layer

## Status
Accepted (Plan v2 — Substance Mandate, 2026-05-30)

## Context

Each agent's inference pipeline reached for Feast and a model directly, and each
hand-rolled its own `if self._dep is None:` fallback. The result was eight
inconsistent, duplicated fallback paths — and, worse, fallbacks that fired even
when the real dependency was present (the substance gap; see ADR-040). There was
no shared path that loaded a registered checkpoint by name+stage, and the
Mumbai (`mumbai_`) / cold-start (`coldstart_`) naming conventions (E-S6-07,
E-S6-14) lived in prose, not code.

In DDD terms: the 8 agents are bounded contexts, but the integration with the
Feast/MLflow data fabric had no **anti-corruption layer** — every context spoke
its own dialect to the external stores, and the translation logic (including the
critical degradation semantics) was copy-pasted and divergent.

## Decision

**Two shared domain services are the single published-language path to the data
fabric. Agents never touch Feast or MLflow directly.**

### `FeatureProvider` (`packages/synapse_common/features.py`)

Wraps the Feast online store. `get(entity_keys, feature_refs, store_id=...)`
returns a `FeatureResult(values, source, degraded, entity_keys)`. Reachable store
→ real features (`source=FEAST`, `degraded=False`); unreachable → a
**deterministic** synthetic fallback (`source=FALLBACK`, `degraded=True`). The
fallback is seeded per `(entity, store, feature, city)` so a key's features do
not depend on its position in the batch — the metamorphic `MR-*-004`
order-invariance invariants hold. Per-city Redis DB index and the Mumbai
`monsoon_intensity` column (E-S6-03, E-S6-09) are honored. Store failures retry
with Full-Jitter (ADR-016) before degrading; the provider never raises (I-7).

### `ModelRegistry` (`packages/synapse_common/model_registry.py`)

Wraps the MLflow model registry. `load(base_name, city=..., stage=..., coldstart=...)`
applies the naming conventions via `resolve_name(...)` and returns a
`LoadedModel(model, name, version, sha, stage, degraded)`. The `version`/`sha`
feed output provenance (ADR-040) and the I-4 audit. Missing model or unreachable
registry → it first retries the cold-start baseline, then returns a degraded
handle (`model=None`, `degraded=True`) — it never raises (I-7).

### The contract for pipelines

A pipeline MUST:
1. fetch features via `FeatureProvider` and read `result.degraded`;
2. load its model via `ModelRegistry` and read `loaded.degraded`;
3. when both are real, run the genuine model and derive confidence from
   uncertainty; otherwise take the documented I-7 fallback;
4. stamp `Provenance` (ADR-040) reflecting the actual sources used;
5. re-validate the output with `RuntimeValidator` before publish.

## Consequences

- **Positive:** one tested degradation path instead of eight divergent ones; the
  naming conventions are executable, not prose; provenance is trivially correct
  because the provider/registry report `degraded` directly; the substance gap
  cannot reopen agent-by-agent without `substance_truth.py` (C33) noticing.
- **Negative:** an indirection layer between agents and the stores. Acceptable —
  the layer is thin, fully unit-tested without live backends, and is exactly the
  seam where degradation honesty belongs.

## Alternatives considered

- *Keep per-agent fallbacks, just fix the guard-then-ignore bug.* Rejected:
  leaves eight divergent code paths and re-invites drift; the conventions stay in
  prose.
- *A Feast/MLflow facade that raises on failure.* Rejected: violates I-7
  graceful degradation — a store outage must degrade, not take an agent down.
