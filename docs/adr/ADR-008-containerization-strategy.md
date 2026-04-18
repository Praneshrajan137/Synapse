# ADR-008: Containerization Strategy — Docker Compose (dev) / K3s (prod) / Oracle Free (cloud)

## Status
Accepted

## Context
SYNAPSE has 8 agents + orchestrator + digital twin + 9 Mumbai agents + base infrastructure (Kafka, Neo4j, Redis, Postgres, Prometheus, Grafana, MLflow, Ollama, nginx). Full Kubernetes is operational overhead a small team cannot absorb. Bare metal sacrifices portability and the ability to run identical stacks in dev/CI/prod. We need a tiered containerization strategy that matches each environment's constraints.

## Decision
Three deployment targets share one image set:
1. **Local development**: Docker Compose via `docker/docker-compose.yml`. Single-host, hot-reload friendly, easiest debugging.
2. **Production**: K3s (lightweight Kubernetes, Apache 2.0) via `infrastructure/k3s/*.yaml`. Provides rolling updates, pod scheduling, and HorizontalPodAutoscaler without full K8s overhead.
3. **Cloud free tier**: Docker Compose on Oracle Cloud Always-Free A1.Flex (4 ARM cores, 24 GB RAM, $0/mo) via `docker/docker-compose.cloud.yml`. K3s would consume too much RAM on the constrained VM.

All agents are multi-arch images (linux/amd64 + linux/arm64) to support both x86 development laptops and Oracle's ARM VMs.

## Consequences
- Same Dockerfile works in all three environments; only compose vs k3s manifests differ.
- Oracle Cloud path enables $0 production deployment, fulfilling I-1.
- Multi-arch builds add ~2x build time; mitigated by GHCR cache.
- K3s manifests are an additional artifact set to maintain alongside compose files.
- No automatic dev → prod promotion script; CD pipeline must handle the manifest divergence.

## Alternatives Rejected
- **Full Kubernetes everywhere**: rejected — 4+ GB control-plane footprint blows Oracle's 24 GB budget.
- **HashiCorp Nomad**: rejected — smaller ecosystem, no free managed offering.
- **Bare metal systemd units**: rejected — breaks dev/prod parity; no rolling updates.
