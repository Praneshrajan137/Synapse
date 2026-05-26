# SYNAPSE on Google Cloud — Quickstart (Primary Target)

GCP is the **primary** SYNAPSE deployment target as of Sprint 10. Oracle
Always-Free remains as the permanent $0 **fallback** (see
[ADR-037](../adr/ADR-037-dual-deployment-target-cost-honesty.md)).

This document gets you from a clean laptop to a hardened,
Cosign-verified, IAP-gated, budget-capped deployment.

---

## Cost guardrails (read this first)

| Schedule                | On-demand $/mo | Spot $/mo | Free-trial duration |
|-------------------------|----------------|-----------|---------------------|
| Always-on               | $195           | $58       | ~6 weeks            |
| 14 h/day on (default)   | ~$120          | ~$36      | ~10 weeks           |
| **8 h/day on (weekdays)** | **~$65**       | **~$19**  | **~4.5 months**    |
| Stopped                 | $24            | $24       | n/a                 |

The deployment ships with a `$300` Terraform-managed budget cap and an
auto-stop schedule (default 23:00–09:00 IST off). Both are required
for I-1 compliance — do not disable. See
[ADR-037](../adr/ADR-037-dual-deployment-target-cost-honesty.md).

If the credit runs out, fall back to Oracle:
[`infrastructure/oracle/README.md`](../../infrastructure/oracle/README.md).

---

## Prerequisites (one-time, on your laptop)

```powershell
# Windows / PowerShell
winget install Google.CloudSDK
winget install HashiCorp.Terraform

# SSH key for the VM (used only as the legacy fallback — IAP is primary)
ssh-keygen -t ed25519 -f $HOME/.ssh/gcp_synapse -N ""

# Authenticate gcloud
gcloud auth login
gcloud auth application-default login
gcloud config set project <YOUR_PROJECT_ID>

# Enable the APIs Terraform reaches for (idempotent)
gcloud services enable \
    compute.googleapis.com \
    storage.googleapis.com \
    iam.googleapis.com \
    iamcredentials.googleapis.com \
    secretmanager.googleapis.com \
    artifactregistry.googleapis.com \
    iap.googleapis.com \
    dns.googleapis.com \
    billingbudgets.googleapis.com \
    cloudresourcemanager.googleapis.com
```

You also need a **billing account ID** for the budget alert. Find it
with `gcloud billing accounts list` (format `XXXXXX-XXXXXX-XXXXXX`).

---

## Step 1 — Configure `terraform.tfvars`

```powershell
cd infrastructure/gcp/terraform
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars and set at minimum:
#   project_id          = "your-project"
#   billing_account_id  = "XXXXXX-XXXXXX-XXXXXX"
#   budget_alert_email  = "you@example.com"
#   iap_users           = ["user:you@example.com"]
#   github_repo         = "Praneshrajan137/synapse"   # for WIF
# Optional:
#   deploy_domain         = "synapse.example.com"
#   managed_zone_dns_name = "example.com."
#   ssh_public_key_path   = "~/.ssh/gcp_synapse.pub"
```

---

## Step 2 — `make deploy-gcp-terraform`

```powershell
make deploy-gcp-terraform
```

Provisions: network, static IP, persistent SSD, GCE VM with auto-stop
schedule, GCS backup bucket (versioned, 30-day noncurrent), Secret
Manager secret envelopes, Workload Identity Federation pool +
provider, Artifact Registry Docker repo, IAP IAM bindings, budget
alert (if `billing_account_id` set), Cloud DNS zone (if
`deploy_domain` set).

Capture the outputs:

```powershell
$env:GCP_IP = (terraform -chdir=infrastructure/gcp/terraform output -raw public_ip)
terraform -chdir=infrastructure/gcp/terraform output wif_provider
terraform -chdir=infrastructure/gcp/terraform output wif_service_account
terraform -chdir=infrastructure/gcp/terraform output artifact_registry_url
terraform -chdir=infrastructure/gcp/terraform output dns_name_servers   # if you set deploy_domain
```

If you set `deploy_domain`, point your registrar's NS records at the
4 nameservers printed by `dns_name_servers` and wait ~10 min for
propagation.

---

## Step 3 — Populate Secret Manager

```powershell
# Production values — these never live in git or the .env.gcp file.
gcloud secrets versions add neo4j-password         --data-file=- <<< "your_strong_password_1"
gcloud secrets versions add postgres-password      --data-file=- <<< "your_strong_password_2"
gcloud secrets versions add grafana-admin-password --data-file=- <<< "your_strong_password_3"
gcloud secrets versions add jwt-signing-key        --data-file=- <<< "$(openssl rand -base64 48)"
```

`setup_gcp_vm.sh` pulls these into `~/synapse/.env.gcp.local` at boot;
`docker-compose.gcp.yml` reads that file via `--env-file`.

---

## Step 4 — Configure GitHub repository for CI/CD

In **Settings → Secrets and variables → Actions → Variables**, set:

| Variable name      | Value (example)                                              |
|--------------------|--------------------------------------------------------------|
| `GCP_PROJECT_ID`   | `synapse-demo-471203`                                        |
| `GCP_REGION`       | `asia-south1`                                                |
| `GCP_VM`           | `synapse-demo`                                               |
| `GCP_ZONE`         | `asia-south1-a`                                              |
| `GCP_AR_REPO`      | `synapse`                                                    |
| `GCP_WIF_PROVIDER` | (from `terraform output wif_provider`)                       |
| `GCP_WIF_SA`       | (from `terraform output wif_service_account`)                |

No service-account JSON keys are needed. CI authenticates via
Workload Identity Federation.

---

## Step 5 — Bootstrap the VM

```powershell
cp .env.gcp.example .env.gcp
# Edit .env.gcp — set DOMAIN_NAME, LETSENCRYPT_EMAIL, OLLAMA_MODEL.
# Do NOT set passwords here — those come from Secret Manager.

make deploy-gcp-setup
```

This SSH's to the VM (via IAP TCP tunnel) and runs
`infrastructure/gcp/setup_gcp_vm.sh`: data disk format + mount, 16 GB
swap, Docker CE, Compose plugin, Ollama + model pull, certbot
HTTP-01 cert for `$DOMAIN_NAME`, ufw firewall, Cloud Ops Agent,
Cosign install, Artifact Registry Docker auth, Secret Manager fetch
into `.env.gcp.local`, daily GCS backup cron.

Re-runnable — every step is idempotent.

---

## Step 6 — First-time push + verify

```powershell
make deploy-gcp-push
make deploy-gcp-verify
```

`deploy-gcp-push` runs Cosign verification against Artifact Registry
images first, then `docker compose pull`, then `up -d`. On a fresh VM
with no images yet pushed, the Cosign step warns and falls through
to `--build` for the first run.

`deploy-gcp-verify` hits `/healthz` on the frontend and runs
`orchestrator audit verify` to confirm the chained-hash audit log is
intact (Sprint 9).

---

## Step 7 — Trigger CI-driven release

```powershell
git tag -a v0.10.0 -m "Sprint 10 — GCP primary deployment"
git push origin v0.10.0
```

This fires [`.github/workflows/cd-gcp.yml`](../../.github/workflows/cd-gcp.yml):

1. WIF auth (no JSON keys).
2. Build + push + Cosign-sign 12 images in parallel.
3. SSH to the VM via IAP TCP tunnel.
4. Re-run `verify_images.sh` on the VM (Cosign verify each).
5. `docker compose pull && up -d`.
6. Wait up to 5 minutes for `/healthz`.
7. Run `orchestrator audit verify`.

The workflow surfaces a per-tag summary in the GitHub Actions UI.

---

## Day-to-day operations

```powershell
make gcp-status                    # docker compose ps via IAP
make gcp-logs SERVICE=orchestrator # tail logs of one service
make gcp-shell                     # interactive SSH via IAP (no public 22)

make gcp-stop-vm                   # halt compute charges
make gcp-start-vm                  # resume

# Open Grafana behind IAP
gcloud compute start-iap-tunnel synapse-demo 3000 --local-host-port=localhost:3000 --zone=asia-south1-a
# then: http://localhost:3000
```

---

## Teardown

```powershell
make deploy-gcp-destroy
```

`terraform destroy` removes VM, disk, IP, bucket (with versioning,
noncurrent versions linger 30 days unless you `gsutil rm -ar` first),
Secret Manager envelopes (values disappear), WIF pool, Artifact
Registry repo.

---

## Troubleshooting

**`terraform apply` says "API not enabled"** — re-run the
`gcloud services enable …` block in the Prerequisites.

**`gcloud compute ssh ... --tunnel-through-iap` says "iap.tunnels.connect"
denied** — your account is not in `var.iap_users`. Re-`terraform apply`
after adding yourself.

**`cosign verify` fails on push step** — first deploy before any signed
image exists; the Makefile wraps with `|| echo WARN` and continues.
Subsequent runs (post-cd-gcp.yml) must succeed.

**Ollama model pull stuck** — `make gcp-shell`, then
`ollama pull deepseek-r1:7b` manually.

**HTTPS doesn't work** — DNS hasn't propagated. Check
`nslookup <DOMAIN_NAME>`. If using Cloud DNS, confirm the NS records
at your registrar match `terraform output dns_name_servers`.

**Budget alert fired** — `gcloud compute instances stop synapse-demo`
to halt burn, then cut over to Oracle with
`make deploy-oracle-{terraform,setup,push,verify}`.

---

## Related files

| Path | Purpose |
|------|---------|
| [`infrastructure/gcp/terraform/`](../../infrastructure/gcp/terraform/) | IaC |
| [`infrastructure/gcp/setup_gcp_vm.sh`](../../infrastructure/gcp/setup_gcp_vm.sh) | VM bootstrap (idempotent) |
| [`infrastructure/gcp/backup_to_gcs.sh`](../../infrastructure/gcp/backup_to_gcs.sh) | Daily Postgres + Neo4j → GCS |
| [`infrastructure/gcp/verify_images.sh`](../../infrastructure/gcp/verify_images.sh) | Cosign verifier |
| [`docker/docker-compose.gcp.yml`](../../docker/docker-compose.gcp.yml) | Compose for the VM |
| [`.env.gcp.example`](../../.env.gcp.example) | env template |
| [`.github/workflows/cd-gcp.yml`](../../.github/workflows/cd-gcp.yml) | CI/CD on `v*` tags |
| [ADR-036](../adr/ADR-036-gcp-single-vm-not-gke.md) | Why single-VM, not GKE |
| [ADR-037](../adr/ADR-037-dual-deployment-target-cost-honesty.md) | GCP + Oracle dual-target cost story |
