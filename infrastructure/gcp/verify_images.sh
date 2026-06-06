#!/usr/bin/env bash
# ============================================================================
# SYNAPSE — Cosign image-signature verifier (Tier-B hardening)
#
# Runs on the GCE VM *before* docker compose up. Closes the Sprint 9 supply-
# chain loop: images are signed in .github/workflows/cd-gcp.yml via Cosign
# keyless (GitHub OIDC → Fulcio), and this script refuses to start any image
# that was not signed by THIS repository's GitHub Actions OIDC subject.
#
# Required tools on the VM: cosign (installed by setup_gcp_vm.sh).
# Required env:
#   - GITHUB_REPO          owner/name (e.g. Praneshrajan137/synapse)
#   - SYNAPSE_AR_REPO_URL  full prefix, e.g. asia-south1-docker.pkg.dev/<proj>/synapse
#
# Usage (from deploy-gcp-push):
#   ./verify_images.sh
#
# Exits non-zero if any image fails verification. The Makefile wraps this with
# `|| echo "WARN ..."` for the first deploy (before any images are signed).
# ============================================================================
set -euo pipefail

GITHUB_REPO="${GITHUB_REPO:-Praneshrajan137/synapse}"
AR_REPO_URL="${SYNAPSE_AR_REPO_URL:-}"

if [ -z "$AR_REPO_URL" ]; then
    # Try metadata fallback
    AR_REPO_URL="$(curl -sf -H 'Metadata-Flavor: Google' \
        http://metadata.google.internal/computeMetadata/v1/instance/attributes/artifact-registry-repo 2>/dev/null || echo '')"
fi

if [ -z "$AR_REPO_URL" ]; then
    echo "ERROR: SYNAPSE_AR_REPO_URL not set and metadata lookup failed." >&2
    exit 2
fi

# Self-provision cosign if absent. The VM is meant to get it from
# setup_gcp_vm.sh, but if that never ran (or the VM was rebuilt) the binary is
# missing and EVERY image "fails" verification — a false negative that silently
# blocked all CD deploys (the live stack was stuck on a 7h-old manual build).
# Installing here (idempotent) makes the supply-chain gate self-healing.
COSIGN_VERSION="v2.4.1"
if ! command -v cosign >/dev/null 2>&1; then
    echo "cosign not found on VM — installing ${COSIGN_VERSION} (idempotent)…"
    COSIGN_ARCH="$(uname -m)"
    case "$COSIGN_ARCH" in
        x86_64) COSIGN_ARCH="amd64" ;;
        aarch64|arm64) COSIGN_ARCH="arm64" ;;
    esac
    if sudo curl -fsSL -o /usr/local/bin/cosign \
        "https://github.com/sigstore/cosign/releases/download/${COSIGN_VERSION}/cosign-linux-${COSIGN_ARCH}" \
        && sudo chmod +x /usr/local/bin/cosign; then
        echo "  installed: $(cosign version 2>/dev/null | head -1 || echo cosign)"
    else
        echo "ERROR: cosign install failed — cannot verify supply chain." >&2
        exit 3
    fi
fi

# Images we expect cd-gcp.yml to push + sign. Keep in lockstep with the matrix
# in .github/workflows/cd-gcp.yml — verify_claims.py check C26 enforces this.
# The `frontend` image was missing pre-ADR-039; its omission was the silent
# gap that let an old chromatic-less UI keep starting on the VM.
IMAGES=(
    api-gateway
    orchestrator
    digital-twin
    demand-prophet
    routing-navigator
    inventory-sentinel
    freshness-guardian
    pricing-oracle
    disruption-shield
    supplier-trust
    sustainability-agent
    frontend
)

OIDC_ISSUER="https://token.actions.githubusercontent.com"
IDENTITY_REGEXP="https://github.com/${GITHUB_REPO}/.github/workflows/.*"

echo "== Cosign verify =="
echo "  Registry : $AR_REPO_URL"
echo "  Repo     : $GITHUB_REPO"
echo ""

failures=0
for img in "${IMAGES[@]}"; do
    image_ref="${AR_REPO_URL}/${img}:latest"
    printf '  %-22s ' "$img"
    # Capture cosign output so a failure is diagnosable from the CD log alone
    # (the previous `>/dev/null 2>&1` hid `command not found` for weeks).
    if verify_out="$(cosign verify \
        --certificate-identity-regexp "$IDENTITY_REGEXP" \
        --certificate-oidc-issuer "$OIDC_ISSUER" \
        "$image_ref" 2>&1)"; then
        echo "OK"
    else
        echo "FAIL"
        echo "$verify_out" | tail -3 | sed 's/^/      /'
        failures=$((failures + 1))
    fi
done

if [ "$failures" -gt 0 ]; then
    echo ""
    echo "ERROR: $failures image(s) failed Cosign verification." >&2
    echo "       Refusing to start the stack. Re-run cd-gcp.yml or re-sign manually." >&2
    exit 1
fi

echo ""
echo "All ${#IMAGES[@]} images verified — supply chain intact."
