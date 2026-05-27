# SYNAPSE — Deployment Guide

> **TL;DR.** SYNAPSE supports two production deployment targets:
> 1. **GCP** (primary, Sprint 10, ADR-036) — single GCE VM with Workload Identity Federation, Artifact Registry, Cloud Armor, Secret Manager.
> 2. **Oracle Always-Free** (dev/demo, ADR-037) — single Ampere ARM VM, Neo4j Aura + Pinecone + LangSmith on free tiers.
>
> Choose by setting `SYNAPSE_DEPLOY_TARGET` in `.env`. The two paths share the same Docker images and Helm chart — only the IaC and secret-resolution layer differs.

## Why two targets?

[ADR-037 — Dual deployment target cost honesty](../adr/ADR-037-dual-deployment-target-cost-honesty.md) is the canonical answer. In short: GCP gives operational maturity (cosign keyless via OIDC, audit-archival to GCS, IAP tunneling); Oracle gives a $0/month demo path so the project remains reproducible without billing. Both targets are first-class.

## Quickstart — GCP (primary)

**Prerequisites** (one-time per GCP project):
1. `gcloud projects create synapse-prod --name='SYNAPSE Production'`
2. `gcloud config set project synapse-prod`
3. Enable APIs: `gcloud services enable compute.googleapis.com artifactregistry.googleapis.com secretmanager.googleapis.com iam.googleapis.com cloudresourcemanager.googleapis.com`
4. **Create the Workload Identity Federation pool** for GitHub OIDC (required for `cd-gcp.yml`). See [`docs/deploy/gcp-quickstart.md`](./gcp-quickstart.md) — this is a manual step that must happen before CI can push images.

**Deploy:**
```bash
cd infrastructure/gcp/terraform
cp terraform.tfvars.example terraform.tfvars   # fill in project_id, billing_account, domain
terraform init                                  # uses GCS backend; bucket is created by main.tf the first time
terraform apply                                 # creates VM, networking, Artifact Registry, secrets, Cloud Armor

# Then on the VM (set up by setup_gcp_vm.sh as a startup script):
ssh -t -i ~/.ssh/google_compute_engine ... \
    'sudo -u synapse bash -c "cd /opt/synapse && docker compose -f docker/docker-compose.gcp.yml up -d"'
```

Cost guardrail: `infrastructure/gcp/terraform/budget.tf` caps spend at the value of `var.budget_usd` (default $50/month) and emails alerts at 50%/80%/100%. Verify the alert email before `apply`.

## Quickstart — Oracle (secondary)

```bash
cd infrastructure/oracle/terraform
cp terraform.tfvars.example terraform.tfvars   # fill in tenancy_ocid, user_ocid, etc.
terraform apply

ssh ubuntu@<public_ip>
git clone https://github.com/<you>/synapse.git
cd synapse
cp .env.cloud.oracle.example .env
$EDITOR .env                                    # fill Aura/Pinecone/LangSmith keys
docker compose -f docker/docker-compose.cloud.yml pull
docker compose -f docker/docker-compose.cloud.yml up -d
```

## Quickstart — Local (development, no cloud)

```bash
cp docker/.env.template docker/.env
make up
make seed
make topics
```

## What runs where

| Component | Container | Local | Oracle | GCP |
| --- | --- | :-: | :-: | :-: |
| 8 agents | one each | ✓ | ✓ | ✓ |
| orchestrator | `orchestrator` | ✓ | ✓ | ✓ |
| API gateway | `api` | ✓ | ✓ | ✓ |
| frontend | `frontend` (nginx) | ✓ | ✓ | ✓ |
| Kafka | `kafka` | ✓ | ✓ | ✓ |
| PostgreSQL audit | `postgres` | ✓ | ✓ | ✓ |
| Redis (Feast online) | `redis` | ✓ | ✓ | ✓ |
| Neo4j graph | `neo4j` (local) / Aura (cloud) | ✓ | Aura | Aura |
| Prometheus + Grafana | per stack | ✓ | ✓ | ✓ + Cloud Operations export |
| MLflow tracking | `mlflow` | ✓ | ✓ | ✓ |
| Linkerd / KEDA / Flagger | k8s only | — | — | optional via Helm (WS-6) |

## Verification after deploy

Each deployment target's success is verified by the same set of probes:

```bash
# 1. Health of every service
make verify-services

# 2. Every claim in CLAUDE.md is enforced
make verify-claims

# 3. End-to-end: synthetic order → audit row → Kafka emission
pytest tests/integration/test_orders_to_outbox.py -v

# 4. SLO burn rate within budget
curl -s prometheus:9090/api/v1/query?query='synapse:slo_burn_rate' | jq '.data.result'
```

A deploy is "done" when all four return green and `make verify-claims` shows ≤2 FAILs (the 2 partials: digital-twin invocation, third-party anchor publication).

## Rollback

- **GCP:** the previous image tag is always live behind a Cloud Armor backend service. `gcloud compute backend-services update synapse-backend --backend-list=synapse-backend-v(N-1)` reverts in ~30s.
- **Oracle:** `docker compose -f docker/docker-compose.cloud.yml up -d` with the prior `git checkout <sha>` rebuilds in ~3 min.

## Disaster recovery

See [`docs/runbooks/dr_gcp.md`](../runbooks/dr_gcp.md) for the 30-minute RTO single-VM cold-start drill. The Oracle target has its own runbook at [`docs/runbooks/dr_oracle.md`](../runbooks/dr_oracle.md).

---

**Status:** GCP deploy code lives on branch `feat/gcp-primary-deployment` (`cc96b54`). Run `git merge --no-ff feat/gcp-primary-deployment` to land it on `main` — `git merge-tree` reports zero conflicts as of the audit. The terraform-validate CI workflow already exists on `main` (`.github/workflows/terraform-validate.yml`) and will activate automatically once the `.tf` files arrive.
