#!/usr/bin/env bash
# ============================================================================
# SYNAPSE — Google Cloud VM bootstrap (Debian 12, amd64)
# Target: e2-standard-8 (8 vCPU / 32 GB RAM) provisioned by Terraform
#
# Installs: Docker CE, Compose plugin, Ollama, certbot, Cloud Ops Agent.
# Configures: 16 GB swap, sysctl for Neo4j, ufw firewall, data disk mount,
#             daily backup cron, Ollama model pull.
#
# Re-runnable — every step is idempotent.
#
# Invoked by `make deploy-gcp-setup`, which streams this file over SSH:
#   ssh synapse@$GCP_IP 'bash -s' < infrastructure/gcp/setup_gcp_vm.sh
# ============================================================================

set -euo pipefail

log() { printf '\n=== %s ===\n' "$*"; }

OLLAMA_MODEL="${OLLAMA_MODEL:-deepseek-r1:7b}"
DATA_DEVICE="${DATA_DEVICE:-/dev/disk/by-id/google-synapse-data}"
DATA_MOUNT="${DATA_MOUNT:-/mnt/synapse-data}"
SWAP_SIZE_GB="${SWAP_SIZE_GB:-16}"
DOMAIN_NAME="${DOMAIN_NAME:-}"           # set in .env.gcp to enable certbot
LETSENCRYPT_EMAIL="${LETSENCRYPT_EMAIL:-}"

log "SYNAPSE GCP VM bootstrap starting"

# ── System updates ──────────────────────────────────────────────────────────
log "apt update + base packages"
sudo apt-get update -y
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y \
    ca-certificates curl gnupg lsb-release \
    make git jq htop ufw cron parted \
    python3 python3-pip python3-venv

# ── Mount the persistent data disk on first boot ────────────────────────────
# Terraform attaches a 100 GB pd-ssd as device "synapse-data". We mount it at
# /mnt/synapse-data and bind /var/lib/docker into it so container images and
# volumes survive VM rebuilds. Also relocates Ollama models there.
log "Provisioning data disk at $DATA_MOUNT"
if [ -b "$DATA_DEVICE" ]; then
    if ! sudo blkid "$DATA_DEVICE" >/dev/null 2>&1; then
        echo "Formatting $DATA_DEVICE as ext4 (first run)"
        sudo mkfs.ext4 -F -E lazy_itable_init=0,lazy_journal_init=0,discard "$DATA_DEVICE"
    fi
    sudo mkdir -p "$DATA_MOUNT"
    if ! mountpoint -q "$DATA_MOUNT"; then
        sudo mount -o discard,defaults "$DATA_DEVICE" "$DATA_MOUNT"
    fi
    DATA_UUID=$(sudo blkid -s UUID -o value "$DATA_DEVICE")
    if ! grep -q "$DATA_UUID" /etc/fstab; then
        echo "UUID=$DATA_UUID $DATA_MOUNT ext4 discard,defaults,nofail 0 2" | sudo tee -a /etc/fstab
    fi
    sudo mkdir -p "$DATA_MOUNT/docker" "$DATA_MOUNT/ollama" "$DATA_MOUNT/backups"
else
    echo "WARN: data disk $DATA_DEVICE not found — falling back to boot disk (rebuilds will lose data)"
fi

# ── Swap (helps Ollama model loads + Neo4j page cache pressure) ─────────────
log "Configuring ${SWAP_SIZE_GB}G swap"
if [ ! -f /swapfile ]; then
    sudo fallocate -l "${SWAP_SIZE_GB}G" /swapfile
    sudo chmod 600 /swapfile
    sudo mkswap /swapfile
    sudo swapon /swapfile
fi
if ! grep -q '^/swapfile' /etc/fstab; then
    echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
fi

# ── Sysctl for Neo4j + ES-style mmap workloads ──────────────────────────────
log "sysctl tweaks (vm.max_map_count, vm.swappiness)"
sudo tee /etc/sysctl.d/99-synapse.conf >/dev/null <<EOF
vm.max_map_count = 262144
vm.swappiness    = 10
fs.file-max      = 1048576
EOF
sudo sysctl --system >/dev/null

# ── Docker CE + Compose plugin (official repo) ──────────────────────────────
log "Installing Docker CE"
if ! command -v docker >/dev/null 2>&1; then
    sudo install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/debian/gpg \
        | sudo gpg --dearmor --yes -o /etc/apt/keyrings/docker.gpg
    sudo chmod a+r /etc/apt/keyrings/docker.gpg
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
https://download.docker.com/linux/debian $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
        | sudo tee /etc/apt/sources.list.d/docker.list >/dev/null
    sudo apt-get update -y
    sudo apt-get install -y docker-ce docker-ce-cli containerd.io \
        docker-buildx-plugin docker-compose-plugin
fi
sudo usermod -aG docker "$USER"

# Relocate Docker's data dir onto the persistent disk
if [ -d "$DATA_MOUNT" ]; then
    log "Pointing Docker storage at $DATA_MOUNT/docker"
    sudo mkdir -p /etc/docker
    sudo tee /etc/docker/daemon.json >/dev/null <<EOF
{
  "data-root": "$DATA_MOUNT/docker",
  "log-driver": "json-file",
  "log-opts": { "max-size": "50m", "max-file": "3" }
}
EOF
fi
sudo systemctl enable --now docker
sudo systemctl restart docker

# ── Ollama (local LLM runtime for Disruption Shield + orchestrator) ─────────
log "Installing Ollama"
if ! command -v ollama >/dev/null 2>&1; then
    curl -fsSL https://ollama.com/install.sh | sh
fi

# Point Ollama at the persistent disk so model pulls survive VM rebuilds
if [ -d "$DATA_MOUNT" ]; then
    sudo mkdir -p /etc/systemd/system/ollama.service.d
    sudo tee /etc/systemd/system/ollama.service.d/override.conf >/dev/null <<EOF
[Service]
Environment="OLLAMA_MODELS=$DATA_MOUNT/ollama"
Environment="OLLAMA_HOST=0.0.0.0:11434"
EOF
    sudo systemctl daemon-reload
fi
sudo systemctl enable --now ollama
sleep 5

log "Pulling Ollama model: $OLLAMA_MODEL"
ollama pull "$OLLAMA_MODEL" || echo "WARN: model pull failed — retry manually with 'ollama pull $OLLAMA_MODEL'"

# ── certbot for Let's Encrypt (HTTPS via nginx) ────────────────────────────
log "Installing certbot"
sudo apt-get install -y certbot

# Only request a cert if a domain is wired up
CERT_DIR=""
if [ -n "$DOMAIN_NAME" ] && [ -n "$LETSENCRYPT_EMAIL" ]; then
    log "Requesting cert for $DOMAIN_NAME"
    # Stop anything binding port 80 so the standalone challenge can listen
    sudo systemctl stop nginx 2>/dev/null || true
    sudo docker stop synapse-nginx 2>/dev/null || true
    sudo certbot certonly --standalone --non-interactive --agree-tos \
        -m "$LETSENCRYPT_EMAIL" -d "$DOMAIN_NAME" || \
        echo "WARN: certbot failed — check DNS A record for $DOMAIN_NAME points to this IP"
    CERT_DIR="/etc/letsencrypt"
    # Auto-renew via the systemd timer that ships with the package
    sudo systemctl enable --now certbot.timer
else
    echo "Skipping certbot (DOMAIN_NAME or LETSENCRYPT_EMAIL not set in .env.gcp)"
fi

# ── ufw firewall (defence in depth — GCP firewall rules are the real gate) ─
log "ufw rules"
sudo ufw --force reset >/dev/null
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
# Management ports — the GCP firewall already restricts to admin IP, this is a backstop
for p in 3000 5000 7474 7687 8080 9090 16686; do sudo ufw allow "$p/tcp"; done
sudo ufw allow 8081:8090/tcp
sudo ufw --force enable

# ── Cloud Ops Agent (free Cloud Monitoring metrics + log forwarding) ───────
log "Installing Google Cloud Ops Agent"
curl -sSO https://dl.google.com/cloudagents/add-google-cloud-ops-agent-repo.sh
sudo bash add-google-cloud-ops-agent-repo.sh --also-install
rm -f add-google-cloud-ops-agent-repo.sh

# ── Cosign (image-signature verifier — see verify_images.sh) ───────────────
log "Installing Cosign"
if ! command -v cosign >/dev/null 2>&1; then
    COSIGN_VERSION="v2.4.1"
    COSIGN_ARCH="amd64"
    sudo curl -fsSL -o /usr/local/bin/cosign \
        "https://github.com/sigstore/cosign/releases/download/${COSIGN_VERSION}/cosign-linux-${COSIGN_ARCH}"
    sudo chmod +x /usr/local/bin/cosign
fi
echo "  Cosign     : $(cosign version --short 2>/dev/null || echo not-found)"

# ── Artifact Registry Docker auth ───────────────────────────────────────────
# Lets `docker pull <region>-docker.pkg.dev/<project>/<repo>/<image>` work
# using the VM's service account (no JSON keys).
AR_HOST="$(curl -sf -H 'Metadata-Flavor: Google' \
    http://metadata.google.internal/computeMetadata/v1/instance/attributes/artifact-registry-host 2>/dev/null || echo '')"
if [ -n "$AR_HOST" ]; then
    log "Configuring Docker auth for Artifact Registry ($AR_HOST)"
    # Quiet the gcloud component-update nag and authorize Docker.
    gcloud --quiet auth configure-docker "$AR_HOST" 2>/dev/null \
        || sudo -u "$USER" gcloud --quiet auth configure-docker "$AR_HOST"
fi

# ── Secret Manager fetch — replaces plaintext .env.gcp passwords ────────────
SYNAPSE_HOME="$HOME/synapse"
mkdir -p "$SYNAPSE_HOME"

MANAGED_IDS="$(curl -sf -H 'Metadata-Flavor: Google' \
    http://metadata.google.internal/computeMetadata/v1/instance/attributes/managed-secret-ids 2>/dev/null || echo '')"
if [ -n "$MANAGED_IDS" ]; then
    log "Fetching secrets from Google Secret Manager"
    ENV_LOCAL="$SYNAPSE_HOME/.env.gcp.local"
    : > "$ENV_LOCAL"
    chmod 600 "$ENV_LOCAL"
    # Map Secret Manager IDs (kebab-case) to env var names (UPPER_SNAKE_CASE)
    # and write only those that successfully resolve. Missing secrets are
    # logged WARN but do NOT fail bootstrap — first-run before secrets are
    # populated is expected.
    IFS=',' read -ra IDS <<< "$MANAGED_IDS"
    for sid in "${IDS[@]}"; do
        var_name="$(echo "$sid" | tr '[:lower:]-' '[:upper:]_')"
        if val="$(gcloud --quiet secrets versions access latest --secret="$sid" 2>/dev/null)"; then
            printf '%s=%s\n' "$var_name" "$val" >> "$ENV_LOCAL"
            echo "  + $var_name (from secret '$sid')"
        else
            echo "  - $var_name : secret '$sid' has no version yet (populate with 'gcloud secrets versions add')"
        fi
    done
    chown "$USER:$USER" "$ENV_LOCAL"
    echo "Wrote $ENV_LOCAL (chmod 600). docker-compose.gcp.yml's --env-file picks this up next to .env.gcp."
else
    echo "WARN: managed-secret-ids metadata not found — skipping Secret Manager fetch (falling back to .env.gcp)"
fi

# ── Daily backup cron ──────────────────────────────────────────────────────
log "Installing daily backup cron (03:00 UTC)"
BACKUP_BUCKET=$(curl -sf -H "Metadata-Flavor: Google" \
    http://metadata.google.internal/computeMetadata/v1/instance/attributes/backup-bucket || echo "")
if [ -n "$BACKUP_BUCKET" ]; then
    sudo tee /etc/synapse-backup.env >/dev/null <<EOF
BACKUP_BUCKET=$BACKUP_BUCKET
SYNAPSE_HOME=$SYNAPSE_HOME
EOF
    CRON_LINE="0 3 * * * root . /etc/synapse-backup.env && $SYNAPSE_HOME/backup_to_gcs.sh >> /var/log/synapse-backup.log 2>&1"
    if ! grep -qF 'synapse-backup' /etc/crontab 2>/dev/null; then
        echo "# synapse-backup" | sudo tee -a /etc/crontab >/dev/null
        echo "$CRON_LINE" | sudo tee -a /etc/crontab >/dev/null
    fi
    echo "Backup cron installed — backups land in gs://$BACKUP_BUCKET/"
else
    echo "WARN: backup-bucket metadata not found; backups disabled"
fi

# ── Summary ────────────────────────────────────────────────────────────────
log "Bootstrap complete"
echo "  Docker     : $(docker --version 2>/dev/null || echo not-found)"
echo "  Compose    : $(docker compose version --short 2>/dev/null || echo not-found)"
echo "  Ollama     : $(ollama --version 2>/dev/null | head -1 || echo not-found)"
echo "  Data mount : $(mountpoint -q "$DATA_MOUNT" && echo "$DATA_MOUNT (ok)" || echo "not mounted")"
echo "  Swap       : $(swapon --show=NAME,SIZE --noheadings | tr '\n' ' ')"
echo "  Cert       : ${CERT_DIR:-none}"
echo ""
echo "Next: 'make deploy-gcp-push' (copies compose + .env and runs 'docker compose up -d')."
echo "Note: log out and back in so the docker group takes effect for non-root use."
