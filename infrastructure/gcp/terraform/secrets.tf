# ============================================================================
# SYNAPSE — Google Secret Manager (Tier-A hardening, ADR-037)
#
# Replaces the .env.gcp plaintext anti-pattern. Each secret is created here
# empty; you populate the actual value out-of-band via:
#
#   gcloud secrets versions add neo4j-password --data-file=- <<< "<value>"
#
# The VM service account is granted secretAccessor at the project level (in
# main.tf), and `setup_gcp_vm.sh` pulls each secret at boot into a local
# ${HOME}/synapse/.env.gcp.local that docker-compose.gcp.yml reads.
#
# Rotation is `gcloud secrets versions add` + restart the affected service.
# Secret Manager keeps the previous version forever (manual disable).
# ============================================================================

resource "google_secret_manager_secret" "managed" {
  for_each  = toset(var.managed_secret_ids)
  secret_id = each.value
  labels    = var.labels

  replication {
    auto {}
  }

  # The Secret resource is safe to recreate (it has no version) — values
  # outlive the Terraform-managed envelope via versions.
  lifecycle {
    prevent_destroy = false
  }
}
