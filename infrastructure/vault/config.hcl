// SYNAPSE HashiCorp Vault configuration
// v4.0 §7.3 — secrets management. Replaces hardcoded passwords in compose.
// Apache 2.0 license.
storage "file" {
  path = "/vault/file"
}

listener "tcp" {
  address     = "0.0.0.0:8200"
  tls_disable = true  # TLS terminates at nginx; Vault sits inside the compose network
}

api_addr = "http://vault:8200"
ui       = true
disable_mlock = true

// KV v2 is mounted at secret/ (see init.sh). Engines for future use:
// - transit/ for encryption-as-a-service (audit row signing)
// - database/ for dynamic Postgres credentials
