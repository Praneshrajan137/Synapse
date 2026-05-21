# ADR-030: Dual Deployment Target (docker-compose + Helm)

## Status
Accepted (Sprint 7, 2026-05-17)

## Context

Sprint 5–6 ran on docker-compose. World-class production targets
Kubernetes via Helm + Linkerd + KEDA + Flagger (Sprint 9, WS-10). We
must avoid the migration trap where docker-compose is dropped before
Helm is mature, leaving the local dev loop broken.

## Decision

- **docker-compose remains the dev-loop primary** through Sprint 9 and
  beyond. `make dev` and `make demo-*` continue to target compose.
- **Helm is the production path** introduced in Sprint 9
  (`infrastructure/helm/synapse/`) with `values-bengaluru.yaml` and
  `values-mumbai.yaml`. CI matrix runs both targets.
- **No managed-K8s dependency** — Helm targets vanilla K8s + Linkerd
  (CNCF graduated, FOSS). $0 cost (I-1) preserved.

## Consequences

**Easier:**
- New contributors keep the fast `docker compose up` loop.
- Mumbai overlay (E-S6-10) keeps its compose-based behavior.
- Helm rollout can proceed without blocking dev.

**Harder:**
- Two deployment artifacts to maintain; CI matrix expands.
- Some features (KEDA autoscaling, Flagger canary) are Helm-only.

## Alternatives Rejected

1. **Helm-only from Sprint 9** — leaves no fast local loop without K8s.
2. **kustomize instead of Helm** — Linkerd ServiceProfile / Flagger
   Canary CRDs are easier expressed in Helm values.
