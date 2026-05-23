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
    "Public IP : ${google_compute_address.synapse.address}",
    "Zone      : ${google_compute_instance.synapse.zone}",
    "SSH user  : ${var.ssh_user}",
    "Backups   : gs://${google_storage_bucket.backups.name}",
    "",
    "1) Export the IP for the make targets:",
    "     export GCP_IP=${google_compute_address.synapse.address}",
    "     (PowerShell: $env:GCP_IP = '${google_compute_address.synapse.address}')",
    "",
    "2) Bootstrap the VM (installs Docker, Ollama, certbot, swap, backup cron):",
    "     make deploy-gcp-setup",
    "",
    "3) Push the stack and bring it up:",
    "     make deploy-gcp-push",
    "",
    "4) Verify:",
    "     make deploy-gcp-verify",
    "",
  ])
}
