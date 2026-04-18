# ============================================================================
# SYNAPSE — Terraform variables for Oracle Cloud provisioning
# ============================================================================

# ── OCI credentials (required; obtain from OCI Console → User Settings → API Keys) ──
variable "tenancy_ocid" {
  description = "OCID of the root tenancy"
  type        = string
}

variable "user_ocid" {
  description = "OCID of the IAM user whose API key is configured"
  type        = string
}

variable "compartment_ocid" {
  description = "OCID of the compartment to create resources in (root is fine for free tier)"
  type        = string
}

variable "fingerprint" {
  description = "Fingerprint of the OCI API public key registered for the user"
  type        = string
}

variable "private_key_path" {
  description = "Absolute path to the OCI API private key PEM file"
  type        = string
}

variable "region" {
  description = "OCI region (try alternates if A1.Flex capacity is exhausted: ap-mumbai-1, us-phoenix-1, us-ashburn-1, uk-london-1)"
  type        = string
  default     = "ap-mumbai-1"
}

# ── Compute shape (VM.Standard.A1.Flex is the only Always-Free ARM shape) ──
variable "instance_shape" {
  type    = string
  default = "VM.Standard.A1.Flex"
}

variable "ocpus" {
  description = "OCPUs — 4 uses the full Always-Free allotment"
  type        = number
  default     = 4
}

variable "memory_gb" {
  description = "Memory in GB — 24 uses the full Always-Free allotment"
  type        = number
  default     = 24
}

variable "boot_volume_gb" {
  description = "Boot volume size in GB (Always-Free block storage limit is 200 GB combined)"
  type        = number
  default     = 100
}

variable "availability_domain_index" {
  description = "Zero-based index into the region's availability domains. Increment if the first AD rejects capacity."
  type        = number
  default     = 0
}

# ── Access ──
variable "ssh_public_key" {
  description = "SSH public key contents (e.g. contents of ~/.ssh/oracle_synapse.pub)"
  type        = string
}

variable "ssh_ingress_cidr" {
  description = "CIDR allowed to SSH and hit management ports (Grafana, Prometheus, Neo4j Browser). Default is the whole internet; tighten to your IP/32 if possible."
  type        = string
  default     = "0.0.0.0/0"
}

variable "github_repo" {
  description = "owner/name of the repo cloned on first boot by cloud-init. Public repo assumed."
  type        = string
  default     = "your-org/synapse"
}
