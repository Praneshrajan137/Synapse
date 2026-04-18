// Application policy — what an agent or the orchestrator can read.
// Attached to every service token.

path "secret/data/synapse/*" {
  capabilities = ["read"]
}

path "secret/metadata/synapse/*" {
  capabilities = ["list", "read"]
}

// Transit engine: agents can sign audit rows but not manage keys.
path "transit/sign/audit-hmac" {
  capabilities = ["update"]
}
path "transit/verify/audit-hmac" {
  capabilities = ["update"]
}
