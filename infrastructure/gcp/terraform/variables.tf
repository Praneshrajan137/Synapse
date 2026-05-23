# ============================================================================
# SYNAPSE — Terraform variables for Google Cloud provisioning
# ============================================================================

variable "project_id" {
  description = "GCP project ID (NOT the display name). Find under console.cloud.google.com → top bar → Project info → ID."
  type        = string
}

variable "region" {
  description = "GCP region. asia-south1 (Mumbai) is the lowest-latency option from Bengaluru/India."
  type        = string
  default     = "asia-south1"
}

variable "zone" {
  description = "GCP zone within the region. e2-standard-8 is available in all zones."
  type        = string
  default     = "asia-south1-a"
}

# ── Compute shape ──
variable "machine_type" {
  description = "Compute Engine machine type. e2-standard-8 = 8 vCPU / 32 GB RAM (~$195/mo on-demand, ~$58/mo Spot)."
  type        = string
  default     = "e2-standard-8"
}

variable "use_spot_vm" {
  description = "Use Spot (preemptible) pricing — ~70% cheaper, but GCP can reclaim the VM with 30s notice. False = on-demand."
  type        = bool
  default     = false
}

variable "boot_disk_gb" {
  description = "Boot disk size (Debian 12 image lives here). 30 GB is plenty."
  type        = number
  default     = 30
}

variable "data_disk_gb" {
  description = "Separate data disk for /var/lib/docker + Ollama models + backups. Persists across VM rebuilds."
  type        = number
  default     = 100
}

# ── Access ──
variable "ssh_public_key_path" {
  description = "Path to SSH public key file (e.g. ~/.ssh/gcp_synapse.pub)."
  type        = string
  default     = "~/.ssh/gcp_synapse.pub"
}

variable "ssh_user" {
  description = "Linux username on the VM. GCP adds this user via metadata; matches sshUsername in OS Login."
  type        = string
  default     = "synapse"
}

variable "admin_ip_cidr" {
  description = "CIDR allowed to SSH and reach management ports (Grafana, Prometheus, agent APIs). Get yours at whatismyipaddress.com → '1.2.3.4/32'. 0.0.0.0/0 opens to the internet — only use briefly."
  type        = string
  default     = "0.0.0.0/0"
}

# ── Backup ──
variable "backup_bucket_location" {
  description = "GCS bucket location for daily Postgres/Neo4j dumps. Use the region to stay in the free 5 GB tier (multi-region buckets don't qualify)."
  type        = string
  default     = "asia-south1"
}

variable "backup_retention_days" {
  description = "Lifecycle rule deletes backups older than this. 7 days × ~200 MB/day fits the 5 GB free tier."
  type        = number
  default     = 7
}

# ── Tagging ──
variable "vm_name" {
  description = "Name for the Compute Engine instance. Lowercase, hyphens only."
  type        = string
  default     = "synapse-demo"
}

variable "labels" {
  description = "Labels applied to all resources (for billing reports and grouping)."
  type        = map(string)
  default = {
    project = "synapse"
    env     = "demo"
    managed = "terraform"
  }
}
