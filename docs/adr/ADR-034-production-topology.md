# ADR-034: Production Topology Skeleton — Helm + Linkerd + KEDA + Flagger

## Status
Accepted (Sprint 9, 2026-05-17). Extends ADR-030 (dual deployment target).

## Context

Sprint 7 ADR-030 committed to a dual-target deployment: docker-compose
for the dev loop, Kubernetes for production. Sprint 8 deferred Helm to
Sprint 9. Sprint 9 ships the **skeleton** that proves the four-layer
stack works end-to-end for the critical-path services; the remaining
agents are templated onto the same pattern in Sprint 10.

The four layers, in order:

1. **Helm** for packaging + per-city values overrides.
2. **Linkerd** (CNCF graduated, FOSS) for in-cluster mTLS + per-route
   timeouts + retry budgets.
3. **KEDA** for autoscaling on per-topic Kafka consumer-group lag.
4. **Flagger** for canary deploys gated on a golden-trace webhook.

## Decision

**Sprint 9 ships exactly 3 subcharts**:

- `infrastructure/helm/synapse/charts/api-gateway/`
- `infrastructure/helm/synapse/charts/orchestrator/`
- `infrastructure/helm/synapse/charts/demand-prophet/` (representative agent)

Per-city overlays live at the top level:

- `values.yaml` — defaults.
- `values-bengaluru.yaml` — Feast db=0, no MLflow prefix.
- `values-mumbai.yaml` — Feast db=1, OSRM port 5001, `mumbai_` MLflow
  prefix (E-S6-03/07/19).

**Linkerd** is per-deployment: each pod gets `linkerd.io/inject:
enabled`. A `ServiceProfile` for the orchestrator declares per-route
timeouts matching `packages/synapse_common/a2a_sdk.py` `TIER_TIMEOUTS`
(Sprint 7) — Linkerd is the *outer* ring of the resilience mesh; the
application-layer circuit breakers remain the inner ring.

**KEDA** scales the orchestrator on per-topic Kafka consumer-group lag
+ rate of Tier-1 decisions. Min 2 replicas (HA), max 20.

**Flagger** canary checks include a custom webhook
(`infrastructure/flagger/webhook_eval.py`) that runs the golden-trace
suite and asserts overall tier-routing accuracy ≥ 80% before promotion.

**CI gate** (`sprint9-helm` job): `helm lint` + `helm template -f
values-bengaluru.yaml | kubeval` (and same for Mumbai). No live K8s
required — `kubeval` validates against the schemas.

## Consequences

**Easier:**
- Multi-city Helm releases keep their values diff'd in two small
  files; the shared chart logic is one source of truth.
- Linkerd retry budgets + KEDA scaling + Flagger canaries compose
  with the Sprint 7 application-layer mesh (breakers + brownout +
  outbox) — no overlap, just layered redundancy.
- New agents inherit the pattern by copying the `demand-prophet`
  subchart (Sprint 10).

**Harder:**
- Two deployment artifacts to maintain (compose + Helm) — kept in
  sync via the CI matrix.
- CRDs for Linkerd / KEDA / Flagger must be vendored or fetched in CI
  for `kubeval` to validate. Sprint 9 ships a CI step that fetches
  the upstream CRD JSON-schemas at install time.

## Alternatives Rejected

1. **Full topology in Sprint 9 (all 11 services)** — too large; the
   diminishing returns past the orchestrator subchart are low for
   Sprint 9's window. Sprint 10 templates the rest.
2. **Istio instead of Linkerd** — heavier (Envoy footprint), more
   config surface. Linkerd's Rust dataplane keeps the cluster
   footprint small.
3. **HPA-only autoscaling, no KEDA** — HPA can't scale on Kafka lag
   without a custom metrics adapter; KEDA is purpose-built and FOSS.
4. **Argo Rollouts instead of Flagger** — equivalent CRDs but Argo's
   webhook surface for the golden-trace check is less ergonomic.

## References

- ADR-030: Dual deployment target (Sprint 7)
- ADR-028: Brownout policy (Sprint 7)
- ADR-032: Tier-1 hard budget (Sprint 8)
- `infrastructure/helm/synapse/`
- `infrastructure/linkerd/orchestrator.serviceprofile.yaml`
- `infrastructure/keda/orchestrator.scaledobject.yaml`
- `infrastructure/flagger/orchestrator.canary.yaml`
- `docs/runbooks/dr/`
