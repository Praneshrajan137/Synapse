# SYNAPSE on Google Cloud

Deploy the full SYNAPSE stack to a single Compute Engine VM (e2-standard-8,
8 vCPU / 32 GB RAM) on Google Cloud, sized for the free-trial credit window.

## What's in here

| File | Purpose |
|---|---|
| `terraform/` | Terraform module that provisions the VM, disk, IP, firewall, GCS backup bucket, and service account. |
| `setup_gcp_vm.sh` | First-boot bootstrap — Docker, Compose, Ollama, certbot, swap, sysctl, data-disk mount, backup cron. Idempotent. |
| `backup_to_gcs.sh` | Daily Postgres + Neo4j dump → `gs://<vm-name>-backups-*/`. Installed as a cron entry by the bootstrap script. |

The compose file is `../../docker/docker-compose.gcp.yml`. The env template is
`../../.env.gcp.example`.

## Quick start

Detailed walkthrough lives in [`docs/deploy/gcp-quickstart.md`](../../docs/deploy/gcp-quickstart.md).
Short version:

```powershell
# 0) gcloud + terraform installed locally; SSH key at ~/.ssh/gcp_synapse
gcloud auth login
gcloud auth application-default login
gcloud config set project <YOUR_PROJECT_ID>

# 1) Provision the VM
cp infrastructure/gcp/terraform/terraform.tfvars.example infrastructure/gcp/terraform/terraform.tfvars
# ...edit project_id, ssh_public_key_path, admin_ip_cidr...
cp .env.gcp.example .env.gcp
# ...set NEO4J_PASSWORD, POSTGRES_PASSWORD, GRAFANA_ADMIN_PASSWORD, DOMAIN_NAME...

make deploy-gcp-terraform
$env:GCP_IP = (terraform -chdir=infrastructure/gcp/terraform output -raw public_ip)

# 2) Bootstrap + deploy (~30 min total)
make deploy-gcp-setup
make deploy-gcp-push
make deploy-gcp-verify
```

## Cost guardrails

The e2-standard-8 VM is the dominant cost. Stop it whenever you're not actively
demoing:

```powershell
make gcp-stop-vm     # pauses compute charges; disk + static IP still billed
make gcp-start-vm    # resumes; same public IP, same data
```

Or set up an automatic schedule in the GCP Console:
**Compute Engine → VM instance schedules → Create schedule** (e.g. start 09:00
IST, stop 23:00 IST). The schedule survives across credit windows.

Set a budget alert in **Billing → Budgets & alerts** (recommended: $340 cap with
notifications at 25/50/75/90/100 %).

## Troubleshooting

- **`terraform apply` says "API not enabled"** — enable Compute Engine API, Cloud
  Storage API, and IAM Service Account Credentials API under **APIs & Services →
  Library**.
- **SSH hangs** — `admin_ip_cidr` doesn't match your real public IP. Find yours
  at https://whatismyipaddress.com, then `terraform apply` again with the
  correct CIDR.
- **`docker compose up` fails to bind port 80** — certbot's standalone challenge
  is still running. `make gcp-shell`, then `sudo systemctl stop certbot && sudo pkill certbot`.
- **Ollama pull stuck** — model download is ~5 GB; on a slow link this is slow.
  `make gcp-shell` then `ollama pull deepseek-r1:7b` manually.
- **HTTPS doesn't work** — DNS isn't pointing at the VM yet. Verify with
  `nslookup <your-domain>` from your laptop — should return `$GCP_IP`. Wait
  ~5 min for DuckDNS propagation, then re-run `make deploy-gcp-setup`.

## What's NOT in here

- **CI/CD push to Artifact Registry** — deferred. Images build on the VM via
  `docker compose up --build`. Add a `.github/workflows/cd-gcp.yml` later if
  needed.
- **GKE / Kubernetes** — explicitly out of scope; this is a single-VM deploy.
- **Cloud Load Balancer + managed TLS cert** — replaced by certbot inside the
  VM. Saves ~$18/mo.
- **Mumbai multi-city overlay** — deferred. The e2-standard-8 has room but
  tight; if you need both cities, bump to `e2-standard-16` in
  `terraform.tfvars`.
