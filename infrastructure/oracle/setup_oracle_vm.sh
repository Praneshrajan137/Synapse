#!/bin/bash
# ============================================================================
# SYNAPSE — Oracle Cloud Always-Free VM Provisioning
# Target: VM.Standard.A1.Flex (4 ARM OCPUs, 24GB RAM, 200GB storage)
# OS: Ubuntu 22.04 LTS ARM64 (Canonical image from OCI marketplace)
# Cost: $0 (Always-Free tier — permanent, no credit card charge)
# ============================================================================
#
# MANUAL STEPS (do these in OCI Console at cloud.oracle.com):
# 1. Create OCI account (may require credit card for verification — $0 charge)
# 2. Create VCN (Virtual Cloud Network) with public subnet
# 3. Create Compute Instance:
#    - Shape: VM.Standard.A1.Flex
#    - OCPUs: 4, Memory: 24GB
#    - Image: Canonical Ubuntu 22.04 Minimal aarch64
#    - Boot volume: 100GB (within 200GB free limit)
#    - Add SSH public key
# 4. Create security list rules:
#    - Ingress: TCP 22 (SSH), 80, 443, 8080-8099 (agent APIs),
#      3000 (Grafana), 9090 (Prometheus), 7474 (Neo4j Browser — optional)
# 5. Note the public IP address
#
# THEN SSH in and run this script:
#   ssh ubuntu@<PUBLIC_IP> 'bash -s' < infrastructure/oracle/setup_oracle_vm.sh
# ============================================================================

set -euo pipefail

echo "=== SYNAPSE Oracle Cloud VM Setup ==="

# ── System updates ──
sudo apt-get update && sudo apt-get upgrade -y

# ── Install Docker (ARM64 compatible) ──
if ! command -v docker &>/dev/null; then
    curl -fsSL https://get.docker.com | sh
    sudo usermod -aG docker "$USER"
fi
sudo systemctl enable docker
sudo systemctl start docker

# ── Install Docker Compose v2 ──
sudo apt-get install -y docker-compose-plugin

# ── Install Python 3.11 ──
if ! python3.11 --version &>/dev/null; then
    sudo apt-get install -y software-properties-common
    sudo add-apt-repository -y ppa:deadsnakes/ppa
    sudo apt-get update
    sudo apt-get install -y python3.11 python3.11-venv python3.11-dev
fi

# ── Install Node.js 20 LTS (ARM64) ──
if ! command -v node &>/dev/null; then
    curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
    sudo apt-get install -y nodejs
fi

# ── Install Ollama (ARM64 — for Disruption Shield reasoning) ──
if ! command -v ollama &>/dev/null; then
    curl -fsSL https://ollama.com/install.sh | sh
fi

# Pull tier models (fits in 24GB RAM with model swapping)
ollama pull phi3:mini          # 2.3GB — Tier 2
ollama pull deepseek-r1:14b    # 8.8GB — Tier 3 (Disruption Shield reasoning)

# ── Install utilities ──
sudo apt-get install -y make git curl jq

# ── Create Python virtual environment ──
if [ ! -d "$HOME/.venv/synapse" ]; then
    python3.11 -m venv "$HOME/.venv/synapse"
fi
echo 'source $HOME/.venv/synapse/bin/activate' >> "$HOME/.bashrc"

# ── Create swap (8GB — helps with model loading) ──
if [ ! -f /swapfile ]; then
    sudo fallocate -l 8G /swapfile
    sudo chmod 600 /swapfile
    sudo mkswap /swapfile
    sudo swapon /swapfile
fi
if ! grep -q '/swapfile' /etc/fstab; then
    echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
fi

# ── Prevent OCI idle instance reclamation ──
CRON_CMD="*/5 * * * * dd if=/dev/urandom bs=1 count=1 of=/dev/null 2>/dev/null"
if ! crontab -l 2>/dev/null | grep -qF 'urandom'; then
    (crontab -l 2>/dev/null; echo "$CRON_CMD") | crontab -
fi

# ── Firewall (iptables — OCI also has security lists at VCN level) ──
sudo apt-get install -y iptables-persistent || true

PORTS=(22 80 443 3000 9090)
for PORT in "${PORTS[@]}"; do
    if ! sudo iptables -C INPUT -p tcp --dport "$PORT" -j ACCEPT 2>/dev/null; then
        sudo iptables -I INPUT -p tcp --dport "$PORT" -j ACCEPT
    fi
done
if ! sudo iptables -C INPUT -p tcp -m multiport --dports 8080:8099 -j ACCEPT 2>/dev/null; then
    sudo iptables -I INPUT -p tcp -m multiport --dports 8080:8099 -j ACCEPT
fi

sudo netfilter-persistent save || true

# ── GitHub Actions self-hosted runner (ARM64) ─────────────────────────────
# Opt-in: set GH_RUNNER_URL + GH_RUNNER_TOKEN to register this VM as a runner.
# Token is ephemeral (60-minute TTL); obtain from GitHub repo → Settings →
# Actions → Runners → New self-hosted runner → Linux → ARM64.
#
# Labels applied: self-hosted, linux, arm64, oracle — matches
# `.github/workflows/sprint6-e2e-oracle.yml`'s `runs-on` selector.
if [ -n "${GH_RUNNER_URL:-}" ] && [ -n "${GH_RUNNER_TOKEN:-}" ]; then
    echo "=== Installing GitHub Actions self-hosted runner ==="
    RUNNER_VERSION="${GH_RUNNER_VERSION:-2.319.1}"
    RUNNER_DIR="$HOME/actions-runner"
    if [ ! -d "$RUNNER_DIR" ]; then
        mkdir -p "$RUNNER_DIR"
        cd "$RUNNER_DIR"
        curl -o actions-runner.tar.gz -L \
            "https://github.com/actions/runner/releases/download/v${RUNNER_VERSION}/actions-runner-linux-arm64-${RUNNER_VERSION}.tar.gz"
        tar xzf ./actions-runner.tar.gz
        rm actions-runner.tar.gz
    fi
    cd "$RUNNER_DIR"

    # Unregister previous runner if present (idempotent re-runs)
    if [ -f .runner ]; then
        sudo ./svc.sh stop 2>/dev/null || true
        sudo ./svc.sh uninstall 2>/dev/null || true
        ./config.sh remove --token "$GH_RUNNER_TOKEN" 2>/dev/null || true
    fi

    ./config.sh \
        --unattended \
        --url "$GH_RUNNER_URL" \
        --token "$GH_RUNNER_TOKEN" \
        --name "synapse-oracle-arm64" \
        --labels "self-hosted,linux,arm64,oracle" \
        --work "_work" \
        --replace

    sudo ./svc.sh install "$USER"
    sudo ./svc.sh start
    echo "=== Runner registered. Verify: GitHub → Settings → Actions → Runners ==="
else
    echo "=== Skipping runner registration (GH_RUNNER_URL/GH_RUNNER_TOKEN not set) ==="
    echo "=== To register later, re-run this script with both env vars set. ==="
fi

echo "=== Setup complete. Log out and back in for Docker group + venv. ==="
echo "=== Then: git clone <repo> && cd synapse && make up-cloud ==="
