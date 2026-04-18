# SYNAPSE on Oracle Cloud Always-Free — Operator Guide

This is the **quality-preserving** remote execution target for SYNAPSE
Sprint 6 verification. Oracle Cloud Always-Free provides a single
`VM.Standard.A1.Flex` (4 ARM OCPU, 24 GB RAM, 200 GB block storage)
permanently at $0 cost — the only free tier that accommodates the full
SYNAPSE stack (Ollama + all 9 Mumbai containers + orchestrator + nginx +
Kafka + Neo4j + …).

The VM doubles as a **GitHub Actions self-hosted runner** so the full
Sprint 6 verification can be triggered from the GitHub UI with zero local
hardware involvement.

---

## Why this (not GitHub Actions standard runners)

GitHub-hosted `ubuntu-latest` runners expose 7 GB RAM / 2 vCPU / 14 GB SSD.
An earlier attempt (`docker/docker-compose.ci.yml`) shrank the stack to fit
by **disabling Ollama, orchestrator, nginx, and all 9 Mumbai containers**.
That verification is a subset of the system — it cannot exercise Sprint 6's
actual surface area (transfer learning convergence with a live LLM, multi-
city orchestrator consensus, rate-limited edge routing, full 39+8 invariant
test suite). It is abandoned.

Oracle Always-Free ARM is the only free tier where the full stack fits.

---

## One-time bootstrap (≈ 20–30 min)

### 1. Provision the VM

```bash
cd infrastructure/oracle/terraform
terraform init
terraform apply \
  -var="tenancy_ocid=..." \
  -var="user_ocid=..." \
  -var="compartment_ocid=..." \
  -var="fingerprint=..." \
  -var="private_key_path=$HOME/.oci/oci_api_key.pem" \
  -var="region=ap-mumbai-1" \
  -var="github_repo=your-org/synapse" \
  -var="ssh_public_key=$(cat ~/.ssh/oracle_synapse.pub)"

export ORACLE_IP=$(terraform output -raw public_ip)
```

See [`terraform/README.md`](terraform/README.md) for full variable docs and
capacity-exhausted troubleshooting.

### 2. Obtain a runner registration token

1. In the GitHub repo → **Settings → Actions → Runners → New self-hosted
   runner → Linux → ARM64**.
2. Note the token from the displayed `./config.sh` command (it expires in
   ≈ 60 min).
3. Also note the URL (`https://github.com/<owner>/<repo>`).

### 3. Bootstrap the VM

Runs Docker/Python/Node install, 8 GB swap, firewall, Ollama install,
`phi3:mini` + `deepseek-r1:14b` pulls, and GitHub Actions runner
registration:

```bash
ssh -i ~/.ssh/oracle_synapse ubuntu@$ORACLE_IP \
    "GH_RUNNER_URL=https://github.com/<owner>/<repo> \
     GH_RUNNER_TOKEN=<token from step 2> \
     bash -s" < setup_oracle_vm.sh
```

Confirm the runner shows **Idle** in GitHub → Settings → Actions → Runners.
Labels: `self-hosted`, `linux`, `arm64`, `oracle`.

### 4. (Optional) Neo4j Aura

Local Neo4j runs on the VM by default (~1 GB footprint). For a managed
alternative:

1. Create a free tier Aura instance at <https://neo4j.com/cloud/aura>.
2. Store as repo secrets:
   - `NEO4J_AURA_URI` (e.g. `neo4j+s://xxxx.databases.neo4j.io`)
   - `NEO4J_AURA_USER` (usually `neo4j`)
   - `NEO4J_AURA_PASSWORD`
3. The workflow will automatically point the compose stack to Aura instead
   of the local container.

---

## Per-run (one click, no laptop)

1. GitHub → **Actions** → **"Sprint 6 E2E — Oracle Cloud"** → **Run
   workflow**.
2. Keep defaults (`run_demo=true`, `speed_factor=3.0`) or adjust.
3. Wait 60–90 minutes for the first run (≈ 30 min on subsequent runs with
   OSRM image + Ollama models cached).
4. Download the `sprint6-e2e-evidence` artifact when the run completes:
   - `junit.xml` — all 47+ test results
   - `mlflow.sql` — MLflow experiment dump (transfer_speedup, conformal
     coverage)
   - `compose-ps.txt` — container health snapshot
   - `grafana-overview.png` — live dashboard at run time
   - `prometheus-rules.json` — alert state
   - `memory-after.txt`, `dmesg-tail.txt` — for OOM debugging

Total cost per run: **$0**. GitHub Actions free tier does not meter minutes
for self-hosted runners.

---

## Manual fallback (SSH-based)

If the workflow is failing and you need direct control:

```bash
make deploy-oracle              # full provision + push + smoke test
ssh -i ~/.ssh/oracle_synapse ubuntu@$ORACLE_IP
cd ~/synapse
make sprint6-full               # identical to what the workflow runs
```

---

## Idle reclamation

Oracle Always-Free VMs are reclaimed after 7 days of low CPU / network
activity. `setup_oracle_vm.sh` installs a 5-minute cron job reading
`/dev/urandom` to keep activity above the threshold — see line `CRON_CMD`.

---

## Teardown

```bash
cd infrastructure/oracle/terraform
terraform destroy
```

No remote state is worth preserving; everything is rebuildable from the
repo.

---

## Related files

| Path | Purpose |
|------|---------|
| `terraform/*.tf` | OCI provisioning |
| `setup_oracle_vm.sh` | VM bootstrap + runner registration |
| `../../docker/docker-compose.cloud.yml` | ARM64 compose for the VM |
| `../../docker/docker-compose.mumbai.yml` | Mumbai overlay (OSRM_IMAGE var) |
| `../osrm/Dockerfile.osrm-arm64` | ARM64 OSRM build |
| `../../.github/workflows/sprint6-e2e-oracle.yml` | One-click workflow |
| `../../Makefile` (deploy-oracle-* targets) | Manual path |
