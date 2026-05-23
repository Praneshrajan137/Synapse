# Deploy SYNAPSE to Google Cloud — Beginner Walkthrough

This is the click-by-click guide for someone who has never used GCP before.
It deploys the full SYNAPSE stack (8 agents, orchestrator, Kafka, Neo4j,
Postgres, Grafana, frontend) to a single Compute Engine VM, with HTTPS,
daily backups, and cost guardrails.

**Time required:** ~90 min, mostly waiting on downloads.
**Cost:** ~$65/mo if you stop the VM at night, ~$195/mo always-on. The free
₹28,365 credit window (~$340) covers either path through the trial period.

---

## Before you start

- [ ] You have a GCP account with billing active (free credits OK).
- [ ] You're on Windows / macOS / Linux with PowerShell, bash, or zsh.
- [ ] You have a GitHub account and the SYNAPSE repo cloned locally.

---

## Phase 0 — GCP Console setup (browser, 15 min)

1. **Open the GCP Console**: https://console.cloud.google.com/
2. **Create or rename your project**:
   - Top bar → project dropdown → **New Project** (or use the existing one).
   - Name: `synapse-demo` (or anything you like).
   - **Copy the Project ID** — it's the auto-generated string under the name,
     looks like `synapse-demo-471203`. You'll paste this into `terraform.tfvars`.
3. **Set up a budget alert** (safety net):
   - Left menu → **Billing → Budgets & alerts → Create budget**.
   - Amount: **$340** (matches your free credit).
   - Threshold rules: 25 %, 50 %, 75 %, 90 %, 100 %.
   - Email notifications: your account email.
4. **Enable required APIs**:
   - Left menu → **APIs & Services → Library**, then enable each:
     - Compute Engine API
     - Cloud Storage API
     - IAM Service Account Credentials API
     - Cloud Resource Manager API
   - Each takes ~30 seconds.

---

## Phase 1 — Install local tools (terminal, 10 min)

You'll run Terraform and gcloud from your laptop.

### Windows (PowerShell)

```powershell
# gcloud CLI
# Download installer from: https://cloud.google.com/sdk/docs/install-sdk
# Run it, then:
gcloud auth login                      # opens a browser
gcloud config set project <YOUR_PROJECT_ID>
gcloud auth application-default login  # used by Terraform

# Terraform
winget install HashiCorp.Terraform
terraform version                      # need >= 1.6

# SSH key (skip if you already have one)
ssh-keygen -t ed25519 -f $HOME/.ssh/gcp_synapse -N ""
```

### macOS / Linux

```bash
# gcloud CLI
curl https://sdk.cloud.google.com | bash
exec -l $SHELL
gcloud auth login
gcloud config set project <YOUR_PROJECT_ID>
gcloud auth application-default login

# Terraform
brew install terraform                 # macOS
# or: sudo apt install terraform       # Debian/Ubuntu

# SSH key
ssh-keygen -t ed25519 -f ~/.ssh/gcp_synapse -N ""
```

---

## Phase 2 — Provision the VM (terminal, 10 min)

From the SYNAPSE repo root:

1. **Copy templates and edit them**:
   ```powershell
   cp infrastructure/gcp/terraform/terraform.tfvars.example infrastructure/gcp/terraform/terraform.tfvars
   cp .env.gcp.example .env.gcp
   ```
2. **Edit `infrastructure/gcp/terraform/terraform.tfvars`**:
   - `project_id` — paste your project ID from Phase 0.
   - `ssh_public_key_path` — `~/.ssh/gcp_synapse.pub` (the one you just generated).
   - `admin_ip_cidr` — your home IP. Visit https://whatismyipaddress.com, copy
     the IPv4, append `/32`, e.g. `203.0.113.42/32`. (Leave as `0.0.0.0/0` for
     the first 10 minutes if you're not sure, then tighten.)
   - `region` / `zone` — `asia-south1` / `asia-south1-a` if you're in India.
3. **Edit `.env.gcp`**:
   - `NEO4J_PASSWORD`, `POSTGRES_PASSWORD`, `GRAFANA_ADMIN_PASSWORD` — set
     strong unique passwords (don't ship defaults).
   - Leave `DOMAIN_NAME` blank for now — we'll add it in Phase 4.
4. **Apply**:
   ```powershell
   make deploy-gcp-terraform
   ```
   Terraform prints a plan. Type `yes`. After ~2 minutes you'll see output
   ending in `next_steps`. The last line tells you what to run:
   ```powershell
   # PowerShell:
   $env:GCP_IP = (terraform -chdir=infrastructure/gcp/terraform output -raw public_ip)
   # bash/zsh:
   export GCP_IP=$(terraform -chdir=infrastructure/gcp/terraform output -raw public_ip)
   ```

---

## Phase 3 — Bootstrap + deploy the stack (terminal, 30 min)

This is the slow part. Pour a coffee.

1. **Bootstrap the VM** — installs Docker, Ollama, certbot, configures swap and
   the data disk:
   ```powershell
   make deploy-gcp-setup
   ```
   You'll see live output as the script runs. The longest step is
   `ollama pull deepseek-r1:7b` (~5 GB download, ~10 min on a typical link).
2. **Push the stack** — copies the compose file + env, builds images, starts
   everything:
   ```powershell
   make deploy-gcp-push
   ```
   First run pulls the Apache Kafka / Postgres / Neo4j / Prometheus / Grafana
   images (~2 GB) and builds the agent images from source (~10 min).
3. **Verify**:
   ```powershell
   make deploy-gcp-verify
   ```
   Output should show all containers `Up`, plus `OK` for Grafana / Prometheus /
   MLflow / frontend. If any service is `unhealthy`, check its logs:
   ```powershell
   make gcp-logs SERVICE=orchestrator
   ```

**You now have a working demo.** Visit:
- `http://$GCP_IP/` — the frontend
- `http://$GCP_IP:3000` — Grafana (admin / your `GRAFANA_ADMIN_PASSWORD`)
- `http://$GCP_IP:9090` — Prometheus

Stop here if you just want to show people a demo. Phases 4–6 add the
production-ish polish.

---

## Phase 4 — Domain + HTTPS (browser + terminal, 20 min)

Cheapest beginner-friendly path: **DuckDNS** (free, no credit card).

1. **Sign in** at https://www.duckdns.org with GitHub or Google.
2. **Claim a subdomain**, e.g. `synapse-demo`. Your domain will be
   `synapse-demo.duckdns.org`.
3. **Paste your `$GCP_IP`** into the IP box and click **Update**.
4. **Verify DNS works** from your laptop:
   ```powershell
   nslookup synapse-demo.duckdns.org
   ```
   The answer should be your `$GCP_IP`. If not, wait ~5 min and retry.
5. **Update `.env.gcp`**:
   ```env
   DOMAIN_NAME=synapse-demo.duckdns.org
   LETSENCRYPT_EMAIL=you@example.com
   ```
6. **Re-run the bootstrap** — it'll spot the domain and request a cert:
   ```powershell
   make deploy-gcp-setup
   make deploy-gcp-push       # nginx picks up the new cert via the bind mount
   ```
7. Visit `https://synapse-demo.duckdns.org/` — should load with a valid cert,
   no browser warnings.

Cert auto-renews via the `certbot.timer` systemd unit. To inspect:
```powershell
make gcp-shell
sudo systemctl status certbot.timer
sudo certbot certificates
```

If you'd rather use a real domain you own:
- Buy one at Namecheap / Google Domains / Cloudflare (~₹100/year for `.xyz`).
- Either point an A record at `$GCP_IP` from your registrar, or uncomment the
  Cloud DNS block in `terraform/main.tf` and let GCP host the zone (then update
  your registrar's nameservers).

---

## Phase 5 — Backups + cost guards (browser + terminal, 15 min)

### Backups

The bootstrap script installed a daily cron at 03:00 UTC that:
1. Runs `pg_dump` against the Postgres container.
2. Runs Neo4j's `apoc.export.cypher.all` against the Neo4j container.
3. Uploads both to your GCS backup bucket.
4. The bucket lifecycle rule auto-deletes objects older than 7 days.

**Verify it's installed**:
```powershell
make gcp-shell
grep synapse-backup /etc/crontab
```

After 24 h, check the bucket:
```powershell
gcloud storage ls gs://synapse-demo-backups-*/
```

### Auto-stop the VM nightly

This is what makes the credits last. Two options:

**Option A — manual**: just remember to `make gcp-stop-vm` when you're done
for the day. `make gcp-start-vm` to bring it back. The static IP stays attached,
so DNS doesn't change.

**Option B — automatic** (recommended):
1. GCP Console → **Compute Engine → VM instance schedules → Create schedule**.
2. Name: `synapse-business-hours`. Region: same as your VM.
3. Start schedule: every day, 09:00 (your timezone).
4. Stop schedule: every day, 23:00.
5. **Apply to VM**: select your `synapse-demo` instance.

Set-and-forget.

### Watch your spend

GCP Console → **Billing → Reports**. Group by SKU. The biggest line should be
`Compute Engine vCPU` (and `RAM`); the disk line is constant whether the VM is
on or off. If a week goes by and you've burned >$50, the schedule isn't firing
— check the schedule status.

---

## Phase 6 — Smoke test (10 min)

Confirm the system actually works end-to-end:

1. **Frontend loads**: `https://synapse-demo.duckdns.org/` — React app with the
   chromatic design tokens, no console errors in DevTools.
2. **Grafana dashboards populated**: `https://synapse-demo.duckdns.org:3000` (or
   path-routed if your nginx is configured for it). Log in, open the "SYNAPSE
   Overview" dashboard — all 8 agents healthy, Kafka topics receiving messages.
3. **Agent APIs respond**:
   ```powershell
   curl http://$env:GCP_IP:8081/health   # demand-prophet
   curl http://$env:GCP_IP:8090/health   # orchestrator
   ```
4. **Prometheus scraping**: `http://$GCP_IP:9090/targets` — all targets
   `UP` (green).
5. **Backup loop ran** (after 24 h): `gcloud storage ls gs://synapse-demo-backups-*/postgres/`
   shows yesterday's `.sql.gz`.

---

## Tear-down

When the demo is done and you want everything gone:

```powershell
make deploy-gcp-destroy
```

This destroys the VM, disk, IP, firewall, service account, and backup bucket.
Type `destroy` to confirm. **Backups are deleted with the bucket** — pull them
locally first if you want to keep them:

```powershell
gcloud storage cp -r gs://synapse-demo-backups-*/ ./local-backups/
```

---

## Common problems

| Symptom | Fix |
|---|---|
| `terraform apply` → "API has not been used in project" | Phase 0 step 4 — enable the API in the Console, wait 1 min, retry. |
| `terraform apply` → "permission denied" on bucket | Your gcloud auth doesn't have project IAM permissions. `gcloud auth login` again with an account that has Owner or Editor on the project. |
| `ssh ... Permission denied (publickey)` | `admin_ip_cidr` doesn't include your real IP. Update tfvars, `terraform apply`. |
| `make deploy-gcp-setup` hangs on `ollama pull` | Slow connection. SSH in (`make gcp-shell`), run `ollama pull deepseek-r1:7b` manually, then re-run setup. |
| `docker compose up` exits with "port 80 in use" | Certbot's standalone server didn't release the port. `make gcp-shell`, then `sudo pkill certbot && sudo systemctl stop nginx`. |
| Frontend loads but Grafana is 502 | Grafana takes ~30 s to start. Wait, then refresh. If still failing: `make gcp-logs SERVICE=grafana`. |
| Neo4j won't start, `Initial heap size` error | `vm.max_map_count` sysctl didn't apply. `make gcp-shell`, `sudo sysctl vm.max_map_count=262144`, restart the container. |
| Credits draining fast | VM is on 24/7. Set up the auto-stop schedule (Phase 5). |

If anything else breaks, `make gcp-logs SERVICE=<name>` is your friend.
