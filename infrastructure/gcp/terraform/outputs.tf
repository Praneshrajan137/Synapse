# ============================================================================
# SYNAPSE — Terraform outputs (Google Cloud)
# ============================================================================

output "public_ip" {
  description = "Static external IPv4 — use in GCP_IP env var for subsequent make targets."
  value       = google_compute_address.synapse.address
}

output "vm_name" {
  description = "Compute Engine instance name (for `gcloud compute instances start/stop`)."
  value       = google_compute_instance.synapse.name
}

output "zone" {
  description = "Zone the VM lives in (needed for any gcloud command targeting the VM)."
  value       = google_compute_instance.synapse.zone
}

output "ssh_command" {
  description = "Ready-to-copy SSH command."
  value       = "ssh -i ~/.ssh/gcp_synapse ${var.ssh_user}@${google_compute_address.synapse.address}"
}

output "backup_bucket" {
  description = "GCS bucket where daily Postgres/Neo4j dumps land."
  value       = google_storage_bucket.backups.name
}

output "service_account_email" {
  description = "Service account attached to the VM (for IAM debugging)."
  value       = google_service_account.vm.email
}

output "next_steps" {
  description = "What to do after `terraform apply` succeeds."
  value = join("\n", [
    "",
    "─── SYNAPSE GCP VM provisioned ───",
    "Public IP        : ${google_compute_address.synapse.address}",
    "Zone             : ${google_compute_instance.synapse.zone}",
    "SSH user         : ${var.ssh_user}",
    "Backups          : gs://${google_storage_bucket.backups.name}",
    "Artifact Registry: ${var.region}-docker.pkg.dev/${var.project_id}/${var.artifact_registry_repo}",
    "Auto-stop        : ${var.enable_auto_stop ? "ON (${var.auto_stop_start_cron} / ${var.auto_stop_stop_cron} UTC)" : "OFF"}",
    "IAP-only access  : ${var.use_iap_only ? "ON" : "OFF (legacy admin_ip_cidr)"}",
    "",
    "1) Populate Secret Manager (one-time):",
    "     gcloud secrets versions add neo4j-password         --data-file=- <<<'<value>'",
    "     gcloud secrets versions add postgres-password      --data-file=- <<<'<value>'",
    "     gcloud secrets versions add grafana-admin-password --data-file=- <<<'<value>'",
    "     gcloud secrets versions add jwt-signing-key        --data-file=- <<<'<value>'",
    "",
    "2) Export the IP for the make targets:",
    "     export GCP_IP=${google_compute_address.synapse.address}",
    "     (PowerShell: $env:GCP_IP = '${google_compute_address.synapse.address}')",
    "",
    "3) Bootstrap (Docker, Ollama, certbot, Cloud Ops Agent, Secret Manager fetch):",
    "     make deploy-gcp-setup",
    "",
    "4) Push the stack (Cosign verify + pull from Artifact Registry, fallback to build):",
    "     make deploy-gcp-push",
    "",
    "5) Verify (endpoints + audit-chain integrity):",
    "     make deploy-gcp-verify",
    "",
    "Admin UI access (Grafana/Prometheus/MLflow): always via IAP TCP tunnel —",
    "     gcloud compute start-iap-tunnel ${var.vm_name} 3000 --local-host-port=localhost:3000 --zone=${var.zone}",
    "",
  ])
}

# ── Workload Identity Federation outputs (consumed by .github/workflows/cd-gcp.yml) ──
output "wif_provider" {
  description = "Set as github-actions/auth's workload_identity_provider input."
  value       = google_iam_workload_identity_pool_provider.github.name
}

output "wif_service_account" {
  description = "Set as github-actions/auth's service_account input."
  value       = google_service_account.github_actions.email
}

output "artifact_registry_url" {
  description = "Full Docker image registry URL prefix (for tagging in cd-gcp.yml)."
  value       = "${var.region}-docker.pkg.dev/${var.project_id}/${var.artifact_registry_repo}"
}

# ── DNS outputs ──
output "dns_name_servers" {
  description = "Cloud DNS nameservers — set these as the NS records at your domain registrar."
  value       = var.deploy_domain == "" ? [] : google_dns_managed_zone.synapse[0].name_servers
}

# ── Budget output ──
output "budget_status" {
  description = "Whether the Cloud Billing budget alert was created (requires var.billing_account_id)."
  value       = var.billing_account_id == "" ? "DISABLED (set var.billing_account_id to enable)" : "ENABLED ($${var.budget_amount_usd} cap with 25/50/75/90/100% alerts)"
}
