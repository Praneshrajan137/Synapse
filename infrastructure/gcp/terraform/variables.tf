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

# ============================================================================
# Tier-A + Tier-B hardening (ADR-036 / ADR-037)
# ============================================================================

# ── Billing budget (Tier-A) ────────────────────────────────────────────────
variable "billing_account_id" {
  description = "GCP billing account ID (XXXXXX-XXXXXX-XXXXXX). Required for the $300 budget alert. Leave empty to skip budget creation."
  type        = string
  default     = ""
}

variable "budget_amount_usd" {
  description = "Monthly budget cap in USD. Default $300 = full Google Cloud free trial credit. Alerts fire at 25/50/75/90/100 %."
  type        = number
  default     = 300
}

variable "budget_alert_email" {
  description = "Email that receives budget alerts. Falls back to the billing account's default channel if empty."
  type        = string
  default     = ""
}

# ── Workload Identity Federation (Tier-A) — GitHub Actions OIDC ────────────
variable "github_repo" {
  description = "GitHub repository in OWNER/NAME form. Used for WIF subject scoping so only this repo's workflows can mint tokens."
  type        = string
  default     = "Praneshrajan137/synapse"
}

# ── Artifact Registry (Tier-A) ─────────────────────────────────────────────
variable "artifact_registry_repo" {
  description = "Artifact Registry Docker repository ID (lowercase, hyphens only)."
  type        = string
  default     = "synapse"
}

# ── Secret Manager (Tier-A) ────────────────────────────────────────────────
variable "managed_secret_ids" {
  description = "Secret Manager secret IDs that get auto-created (you must populate values via gcloud secrets versions add)."
  type        = list(string)
  default     = ["neo4j-password", "postgres-password", "grafana-admin-password", "jwt-signing-key"]
}

# ── Identity-Aware Proxy (Tier-B) ──────────────────────────────────────────
variable "use_iap_only" {
  description = "When true, admin ports (Grafana/Prometheus/MLflow/etc.) are reachable ONLY via IAP TCP tunnel (gcloud compute start-iap-tunnel). When false, falls back to admin_ip_cidr allow-list."
  type        = bool
  default     = true
}

variable "iap_users" {
  description = "Google identities granted iap.tunnelResourceAccessor (e.g. 'user:you@example.com', 'group:team@example.com'). Required when use_iap_only=true."
  type        = list(string)
  default     = []
}

# ── Auto-stop schedule (Tier-A) ────────────────────────────────────────────
variable "enable_auto_stop" {
  description = "Attach a resource policy that stops the VM on a schedule (and optionally starts it — see enable_auto_start). Slashes credit burn."
  type        = bool
  default     = true
}

variable "enable_auto_start" {
  description = "Also attach a daily VM START schedule. OFF by default (on-demand cost model): the VM is started only by the weekly cd-gcp scheduled run or a manual deploy, then stopped again. A daily auto-start burns credits even when the VM is idle and risks ZONE_RESOURCE_POOL_EXHAUSTED on every cold start. The auto-STOP schedule stays on as a safety net regardless of this flag."
  type        = bool
  default     = false
}

variable "auto_stop_start_cron" {
  description = "Cron expression for daily VM start (UTC). Default 03:30 UTC = 09:00 IST."
  type        = string
  default     = "30 3 * * *"
}

variable "auto_stop_stop_cron" {
  description = "Cron expression for daily VM stop (UTC). Default 17:30 UTC = 23:00 IST."
  type        = string
  default     = "30 17 * * *"
}

# ── Cloud DNS (Tier-B) — optional ──────────────────────────────────────────
variable "deploy_domain" {
  description = "Public DNS name for the deployment (e.g. 'synapse.example.com'). Empty disables Cloud DNS — fall back to plain IP or DuckDNS."
  type        = string
  default     = ""
}

variable "managed_zone_dns_name" {
  description = "Cloud DNS managed zone fully-qualified name (e.g. 'example.com.'). Required when deploy_domain is set."
  type        = string
  default     = ""
}

# ── Cloud Armor WAF (Tier-B) — opt-in ──────────────────────────────────────
variable "enable_cloud_armor" {
  description = "Provision Cloud Armor WAF + global HTTPS load balancer in front of the VM. Adds ~$18/mo for the LB. Default false to keep the single-VM cost story honest."
  type        = bool
  default     = false
}

# ── GCS backup bucket hardening (Tier-B) ───────────────────────────────────
variable "enable_bucket_versioning" {
  description = "Enable object versioning on the backup bucket. Noncurrent versions are retained for 30 days (lifecycle in main.tf)."
  type        = bool
  default     = true
}
