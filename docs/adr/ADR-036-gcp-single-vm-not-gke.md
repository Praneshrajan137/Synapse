# ADR-036: GCP Primary Deployment — Single-VM GCE, not GKE

## Status
Accepted (Sprint 10, 2026-05-26)

## Context

User direction promoted Google Cloud from "future-considered" to the
*primary* deployment target (Oracle Always-Free demoted to fallback —
see ADR-037). The 11-service SYNAPSE stack (8 agents + orchestrator +
digital_twin + api-gateway) can land on GCP in two shapes:

- **Single VM (GCE)** — one `e2-standard-8` Debian VM running the full
  `docker-compose.gcp.yml` stack.
- **GKE Autopilot or Standard** — managed Kubernetes, the Sprint 9 Helm
  chart skeleton extended to full coverage.

ADR-030 already chose "compose for dev, Helm for prod K8s." The Sprint 9
Helm skeleton (`infrastructure/helm/synapse/`) currently covers only 3
of the 11 services (api-gateway, orchestrator, demand-prophet) and the
Linkerd/KEDA/Flagger CRDs are scaffolded but unwired. Promoting GKE to
the primary GCP target requires multi-week chart expansion + per-service
SLO wiring + production observability hook-up.

The single-VM option matches the existing
[`infrastructure/oracle/`](../../infrastructure/oracle/) pattern
exactly (one VM, docker compose, certbot, GCS backup cron), preserving
operator muscle memory across the two clouds.

## Decision

**GCP primary = single GCE VM** (`e2-standard-8`, Debian 12, amd64).
GKE is explicitly deferred and out of scope for Sprint 10.

### Why single-VM wins for *this* deployment shape

| Axis | Single-VM GCE | GKE Autopilot | GKE Standard |
|------|---------------|---------------|--------------|
| **Per-cluster cost** | $0 | ~$72/mo | ~$72/mo |
| **Per-pod cost** | $0 | ~$0.045/vCPU-hr | $0 (you pay for nodes) |
| **VM cost (8 vCPU / 32 GB)** | $195/mo on-demand, $58/mo Spot | included | comparable nodes |
| **Helm chart status** | n/a | 3 of 11 services done | 3 of 11 services done |
| **Lift to production-ready** | hours (grafted from `wip/gcp-deployment`) | weeks (chart expansion + SLO wiring) | weeks |
| **Parity with Oracle deployment** | identical compose pattern | divergent | divergent |
| **Operator surface** | 1 VM, 1 compose file, 1 nginx | clusters, namespaces, ingresses, service mesh | + node pools |

### What we keep that *is* Kubernetes-shaped

- The Sprint 9 Helm skeleton (`infrastructure/helm/synapse/`),
  Linkerd ServiceProfile, KEDA ScaledObject, and Flagger Canary
  manifests remain on disk untouched. They are the documented GKE
  upgrade path for the next sprint that crosses the budget threshold.
- The Cosign + SBOM + audit-chain hardening from Sprint 9 applies
  equally to single-VM and to GKE — those layers are
  orchestrator-shape-agnostic.

### What we explicitly do NOT do here

- We do not delete the Helm skeleton.
- We do not gate the GKE path behind "rewrite from scratch" — when the
  budget admits it, `helm install synapse infrastructure/helm/synapse`
  is the path.
- We do not promote GKE Autopilot to even the "recommended next step"
  status. ADR-037 reserves that judgement until the cost picture
  changes.

## Consequences

**Easier:**

- A working GCP deployment lands in hours, not weeks.
- The Sprint 9 audit-chain + cosign + SBOM machinery slots in unchanged.
- Operator parity across Oracle (fallback) and GCP (primary): same
  compose pattern, same nginx, same certbot, same backup script.
- Cost story is honest and bounded — see ADR-037.

**Harder:**

- Horizontal scaling beyond one VM is not available without lifting to
  GKE first. The single VM is the SPoF.
- No managed rolling restarts or canary deploys at the orchestrator
  level. The cd-gcp.yml workflow does `docker compose pull && up -d`
  which has a short outage per service.
- Flagger / KEDA / Linkerd skeletons stay dormant — operators must
  remember they are *aspirational* for GCP today, *production* for GKE
  later.

## Trigger to revisit (when to promote GKE)

Any one of:

- Monthly GCP spend justified independently of trial credit (paid
  workload, customer-funded demo, etc.).
- Multi-region requirement that exceeds what a single VM with
  Mumbai+Bengaluru overlay handles (Sprint 6 baseline = ~22 GB; one
  e2-standard-16 handles both with headroom).
- SLA requirement requiring sub-30s recovery from a single-VM failure
  (single-VM rebuild via Terraform is ~5 min; Helm rollout is faster).

## References

- [ADR-030: Dual deployment target (compose + Helm)](ADR-030-dual-deployment-target.md)
- [ADR-034: Production topology](ADR-034-production-topology.md)
- [ADR-037: Dual deployment target — cost honesty](ADR-037-dual-deployment-target-cost-honesty.md)
- [`infrastructure/gcp/README.md`](../../infrastructure/gcp/README.md)
- [`docs/deploy/gcp-quickstart.md`](../deploy/gcp-quickstart.md)
- I-1 (cost invariant) in [CLAUDE.md](../../CLAUDE.md)
