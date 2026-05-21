# SYNAPSE Vault policy — PII HMAC key (ADR-031).
#
# Grants read-only access to the HMAC key used by `synapse_common.privacy.tokenize`.
# The key is provisioned out-of-band and rotated quarterly. Tokens computed under
# old keys remain valid (audit-service can hold the rotation log to reverse).
#
# Bind this policy to the `synapse-api` role only. Agents and orchestrator do
# NOT need it — by the time payloads reach them, PII is already tokenized.

path "secret/data/synapse/pii" {
  capabilities = ["read"]
}

path "secret/metadata/synapse/pii" {
  capabilities = ["read", "list"]
}

# Defense-in-depth: forbid every other path under secret/.
path "secret/*" {
  capabilities = ["deny"]
}
