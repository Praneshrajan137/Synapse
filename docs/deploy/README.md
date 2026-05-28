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

**Infrastructure (one-time):**
```bash
cd infrastructure/gcp/terraform
cp terraform.tfvars.example terraform.tfvars   # fill in project_id, billing_account, domain
terraform init                                  # uses GCS backend; bucket is created by main.tf the first time
terraform apply                                 # creates VM, networking, Artifact Registry, secrets, Cloud Armor
```

Cost guardrail: `infrastructure/gcp/terraform/budget.tf` caps spend at the value of `var.budget_usd` (default $50/month) and emails alerts at 50%/80%/100%. Verify the alert email before `apply`.

### Redeploy (the only documented path — ADR-039)

The CD pipeline (`.github/workflows/cd-gcp.yml`) is the **only** way SYNAPSE code reaches the GCP VM. There is no `ssh + git pull + docker build` happy path. Three triggers:

| Trigger | When | Image tags |
|---|---|---|
| `git push origin main` (or PR merge) | **Every merge** auto-deploys | `:main-<sha7>`, `:main`, `:latest` |
| `git tag vX.Y.Z && git push origin vX.Y.Z` | Explicit release | `:X.Y.Z`, `:latest` |
| `gh workflow run cd-gcp.yml` | Manual redeploy of current `main` | `:latest` (dryrun-tagged version) |

The compose file at `docker/docker-compose.gcp.yml` references **pre-built, cosign-signed images** from Artifact Registry (`image:` directives only — no `build:`). The CD job writes `.env.gcp.version` on the VM with the exact pushed version, then runs `docker compose pull && up -d --pull always --force-recreate --remove-orphans`. The signed digest is the running digest, every time.

### Verifying a deploy succeeded

The deployed git SHA is visible in three independent places. They must all agree with `git rev-parse main`:

```bash
# 1. The API gateway reports its own SHA
curl https://<host>/version
# → {"service":"api-gateway","version":"1.1.0","git_sha":"<HEAD>","build_time":"<recent>"}

# 2. The frontend Shell shows the SHA in a chip (top-right of every page).
#    Click it to copy. A screenshot is enough to triage.

# 3. Artifact Registry holds an image tagged at the matching SHA
gcloud artifacts docker images list \
    asia-south1-docker.pkg.dev/<project>/synapse/frontend --include-tags --limit=5
```

### Troubleshooting "the UI looks stale"

Walk this list in order — each "no" maps to exactly one of the four gates ADR-039 built. If all four are green and the UI still looks wrong, the cause is the user's browser cache (hard refresh: Ctrl/Cmd+Shift+R).

1. **Does the frontend chip show HEAD's SHA?** If `dev` / `gcp` / `unknown`, the served image was not built by CI (someone ran `docker compose build` on the VM, or the deploy step was skipped).
2. **Does `curl https://<host>/version` return HEAD's SHA?** If not, the API gateway container is stale — the `--force-recreate` flag in the deploy step failed.
3. **Does `gh run list --workflow=cd-gcp.yml --limit=5` show a green run for HEAD?** If red, the CD pipeline failed at build/sign/push/deploy — open the run log. If absent, the trigger did not fire (rare; check the trigger block in `cd-gcp.yml`).
4. **Does `gcloud artifacts docker images list .../synapse/frontend --include-tags` show a `main-<sha7>` tag matching HEAD?** If not, the build-push-sign job did not push.

Force a redeploy of current `main` without merging anything: `gh workflow run cd-gcp.yml --ref main`.

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

**Status:** GCP deploy code is live on `main` as of Sprint 10. Sprint 12 (ADR-039) closed the silent gap where `docker-compose.gcp.yml` used `build:` directives that bypassed Artifact Registry and `cd-gcp.yml` only fired on `v*` tags. Merges to `main` now auto-deploy; the deployed SHA is visible via `GET /version` and the frontend chip. The verify-claims gates C26 and C27 prevent regression.
