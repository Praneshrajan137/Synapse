#!/bin/bash
# SYNAPSE Vault one-time init.
# Run AFTER `docker compose up vault`.
# Produces: unseal keys (save offline!), root token, app token, admin token.
set -euo pipefail

VAULT_ADDR="${VAULT_ADDR:-http://localhost:8200}"
export VAULT_ADDR

echo "=== Vault init ==="
INIT_OUTPUT=$(vault operator init -key-shares=3 -key-threshold=2 -format=json)
echo "$INIT_OUTPUT" > vault-init.json
chmod 600 vault-init.json

UNSEAL_KEY_0=$(echo "$INIT_OUTPUT" | jq -r '.unseal_keys_b64[0]')
UNSEAL_KEY_1=$(echo "$INIT_OUTPUT" | jq -r '.unseal_keys_b64[1]')
ROOT_TOKEN=$(echo "$INIT_OUTPUT" | jq -r '.root_token')

echo "=== Unseal ==="
vault operator unseal "$UNSEAL_KEY_0"
vault operator unseal "$UNSEAL_KEY_1"

export VAULT_TOKEN="$ROOT_TOKEN"

echo "=== Engines ==="
vault secrets enable -path=secret kv-v2 || true
vault secrets enable transit || true

echo "=== Audit signing key ==="
vault write -f transit/keys/audit-hmac type=hmac-sha256 || true

echo "=== Policies ==="
vault policy write synapse_app infrastructure/vault/policies/synapse_app.hcl
vault policy write synapse_admin infrastructure/vault/policies/synapse_admin.hcl

echo "=== App token (attach to service containers) ==="
vault token create -policy=synapse_app -ttl=720h -format=json \
  | jq -r '.auth.client_token' > vault-app-token.txt
chmod 600 vault-app-token.txt

echo ""
echo "Init complete. Artifacts:"
echo "  vault-init.json       — unseal keys + root token (STORE OFFLINE)"
echo "  vault-app-token.txt   — app token for services"
echo ""
echo "Seed secrets:"
echo "  vault kv put secret/synapse/neo4j password=..."
echo "  vault kv put secret/synapse/postgres password=..."
echo "  vault kv put secret/synapse/jwt private_key=@rsa.pem"
