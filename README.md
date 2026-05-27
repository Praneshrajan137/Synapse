# SYNAPSE

> **Supply Yield Network with Autonomous Planning, Sensing & Execution.**
> A multi-agent reinforcement-learning platform for quick-commerce supply-chain optimisation — eight specialised agents, a four-tier consensus orchestrator, a SimPy digital twin, a Feast data fabric, and an audit trail you can cryptographically verify.

## What this actually is, today

Honesty matters more than ambition. Here is the state of the repository at a glance — every row is mechanically checked by `make verify-claims`, not just asserted in prose.

| Surface | State |
| --- | --- |
| 8 specialised agents (`agents/<name>/`) | Code-complete with A2A HTTP handlers, schema-validated outputs (I-3), 8/8 `reward_config.py`. Inter-agent comms is **HTTP-A2A, not Kafka** (ADR-038). |
| Orchestrator (4-tier consensus) | Wired end-to-end including outbox dispatcher, traceparent, idempotency, audit hash-chain (Sprint 9 + WS-2). |
| Digital twin | Full module (`monte_carlo`, `what_if`, `divergence_monitor`, Kafka state-mirror). Orchestrator does not yet invoke Tier 4 simulations against it — tracked as `CURRENT.md` C7. |
| Frontend (Atlas Console v1.1) | React + Vite + TS. Typed Zod-validated client for every backend route. JWKS rotation handle in place; full client-side sig verify is Sprint 12+. |
| Helm chart | 11/11 services templated (WS-6). Linkerd/KEDA/Flagger live inside the orchestrator subchart, gated on `global.serviceMesh / global.autoscaling / global.canary` flags. |
| GCP deployment | Code lives on `feat/gcp-primary-deployment` (cc96b54). Merges clean (zero conflicts); awaiting PR. After merge: `terraform apply` from `infrastructure/gcp/terraform/` brings up the stack. |
| Oracle Always-Free deployment | Fully wired today. `docker compose -f docker/docker-compose.cloud.yml up -d` on a fresh Oracle VM. |
| Supply chain | Cosign keyless signing on every CD build; Kyverno admission policy refuses unsigned images. SBOM diff + CVE-budget gates in CI. |
| Observability | Prometheus burn-rate rules generated from SLO YAMLs (`slo_to_rules.py --check` enforces sync); Alertmanager routes to PagerDuty + Slack; `metric_truth.py` flags any alerted metric without a corresponding source-tree emit. |
| Tests | Backend coverage floor 80%, mutation floor enforced (Stryker `break: 50`, ratcheting), Hypothesis property fuzz on consensus invariants, golden-trace tier-routing gate at 80%, KV-cache hit-rate gate at 0.70. |
| Documentation | Every "Sprint X" line above maps to a real artefact you can `cat`. The handful that are aspirational are tagged in `docs/state/CURRENT.md` so you can find them. |

Run `make verify-claims` for the live truth. Today it reports **16 PASS / 3 FAIL / 0 SKIP**.

## Quickstart — three deployment targets

```bash
# Local development (Docker Compose)
cp docker/.env.template docker/.env
make up
make seed
make topics

# Oracle Always-Free (single ARM VM)
cd infrastructure/oracle/terraform && terraform apply
ssh ubuntu@<vm> 'docker compose -f docker/docker-compose.cloud.yml up -d'

# GCP (single VM, ADR-036) — after merging feat/gcp-primary-deployment
cd infrastructure/gcp/terraform && terraform apply
# CD pipeline (cd-gcp.yml) takes over from here.
```

Full deployment guide: [`docs/deploy/README.md`](docs/deploy/README.md).

## Architecture in one paragraph

A REST/JSON-RPC gateway (FastAPI) routes operator and ingress requests to a four-tier consensus orchestrator. The orchestrator classifies each request by latency/complexity (Tier 1 RL-only ≤100ms ... Tier 4 LLM+Monte-Carlo 15-120s) and fans out via HTTP A2A to whichever agents are involved. Agent publications fan out over Kafka to the digital twin for state mirroring and to the audit sink. Every decision lands in `audit_consensus` with a chained SHA-256 hash; every operator override and steering change lands in their own audit tables with the same chain. The whole stack runs on a single VM (ADR-036) so you can run it on GCP for $50/month or on Oracle for $0/month.

## ADR index

38 architecture decision records under [`docs/adr/`](docs/adr/). The most load-bearing for understanding the system:

- **ADR-016** — Full Jitter retry only (never fixed delay).
- **ADR-026** — W3C trace propagation across HTTP, A2A, and Kafka.
- **ADR-029** — Orders ingress as the only post-Sprint-1 freeze exception.
- **ADR-033** — Audit chained-hash tamper-evidence.
- **ADR-036** — Single GCE VM, not GKE (cost honesty).
- **ADR-037** — Dual-deployment-target cost honesty (GCP + Oracle).
- **ADR-038** — HTTP-A2A primary, Kafka for event-sourcing only (closing the topology-fiction).

## License

Apache 2.0. See [LICENSE](./LICENSE).

## What's intentionally NOT here

- Real customer ingestion. SYNAPSE is currently a simulation harness with synthetic traces; the orders ingress endpoint exists but no live order pipeline is wired.
- Multi-tenancy. The architecture is single-tenant. Tenant isolation is Sprint 12+.
- GKE / multi-node Kubernetes. ADR-036 deliberately chose single-VM; revisit after a year of operational data.
