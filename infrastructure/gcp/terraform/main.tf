# ============================================================================
# SYNAPSE — Google Cloud VM provisioning (Terraform IaC)
#
# Provisions, in this order:
#   1. Network + subnet (custom, not default — explicit for the reader)
#   2. Static external IP (regional)
#   3. Persistent SSD data disk (100 GB, separate from boot)
#   4. Service account + IAM binding for GCS backup writes
#   5. e2-standard-8 Debian 12 instance with attached data disk
#   6. Firewall rules: SSH (admin only), HTTP/HTTPS (world), management ports (admin only)
#   7. GCS bucket for daily Postgres/Neo4j backups with lifecycle expiry
#
# Cost: roughly $65/mo if VM is stopped 16 h/day, $195/mo always-on.
#       The data disk (~$17/mo) is charged whether the VM is running or not.
#       Static IP is FREE while attached to a running VM; $7/mo when VM stopped.
#
# Usage:
#   cd infrastructure/gcp/terraform
#   cp terraform.tfvars.example terraform.tfvars   # edit values
#   terraform init
#   terraform apply
#   terraform output public_ip                     # use in GCP_IP env var
# ============================================================================

provider "google" {
  project = var.project_id
  region  = var.region
  zone    = var.zone
}

# ── Bucket suffix to keep the GCS name globally unique without manual edits ──
resource "random_id" "bucket_suffix" {
  byte_length = 3
}

# ── Network ──────────────────────────────────────────────────────────────────
resource "google_compute_network" "synapse" {
  name                    = "${var.vm_name}-net"
  auto_create_subnetworks = false
  description             = "SYNAPSE VPC — single regional subnet, public IP on the VM."
}

resource "google_compute_subnetwork" "synapse" {
  name          = "${var.vm_name}-subnet"
  network       = google_compute_network.synapse.id
  ip_cidr_range = "10.10.0.0/24"
  region        = var.region
}

# ── Static external IP ───────────────────────────────────────────────────────
resource "google_compute_address" "synapse" {
  name         = "${var.vm_name}-ip"
  region       = var.region
  address_type = "EXTERNAL"
  labels       = var.labels
}

# ── Data disk (separate from boot, survives VM rebuilds) ─────────────────────
resource "google_compute_disk" "data" {
  name   = "${var.vm_name}-data"
  type   = "pd-ssd"
  zone   = var.zone
  size   = var.data_disk_gb
  labels = var.labels
}

# ── Service account for the VM (writes to its own backup bucket) ─────────────
resource "google_service_account" "vm" {
  account_id   = "${var.vm_name}-vm"
  display_name = "SYNAPSE VM service account"
  description  = "Identity used by the VM for GCS backup writes and Cloud Ops Agent."
}

resource "google_project_iam_member" "vm_logging" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.vm.email}"
}

resource "google_project_iam_member" "vm_monitoring" {
  project = var.project_id
  role    = "roles/monitoring.metricWriter"
  member  = "serviceAccount:${google_service_account.vm.email}"
}

# ── Backup bucket ────────────────────────────────────────────────────────────
resource "google_storage_bucket" "backups" {
  name          = "${var.vm_name}-backups-${random_id.bucket_suffix.hex}"
  location      = var.backup_bucket_location
  storage_class = "STANDARD"
  labels        = var.labels

  uniform_bucket_level_access = true
  force_destroy               = true # demo project — terraform destroy should wipe backups too

  versioning {
    enabled = false
  }

  lifecycle_rule {
    condition {
      age = var.backup_retention_days
    }
    action {
      type = "Delete"
    }
  }
}

# Grant the VM service account write access to its own bucket — no long-lived keys
resource "google_storage_bucket_iam_member" "vm_backup_writer" {
  bucket = google_storage_bucket.backups.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.vm.email}"
}

# ── Compute instance ─────────────────────────────────────────────────────────
resource "google_compute_instance" "synapse" {
  name         = var.vm_name
  machine_type = var.machine_type
  zone         = var.zone
  labels       = var.labels
  tags         = ["synapse", "http-server", "https-server"]

  boot_disk {
    initialize_params {
      # debian-cloud/debian-12 is the official, free, long-term-supported image
      image = "debian-cloud/debian-12"
      size  = var.boot_disk_gb
      type  = "pd-balanced"
      labels = var.labels
    }
  }

  # Attach the persistent data disk
  attached_disk {
    source      = google_compute_disk.data.id
    device_name = "synapse-data"
    mode        = "READ_WRITE"
  }

  network_interface {
    subnetwork = google_compute_subnetwork.synapse.id
    access_config {
      nat_ip = google_compute_address.synapse.address
    }
  }

  # Spot pricing — comment out the whole scheduling block for on-demand
  dynamic "scheduling" {
    for_each = var.use_spot_vm ? [1] : []
    content {
      preemptible        = true
      automatic_restart  = false
      provisioning_model = "SPOT"
    }
  }

  service_account {
    email  = google_service_account.vm.email
    scopes = ["cloud-platform"] # needed for Cloud Ops Agent + gsutil
  }

  metadata = {
    # Both metadata keys are accepted; ssh-keys is the universal one
    ssh-keys = "${var.ssh_user}:${trimspace(file(pathexpand(var.ssh_public_key_path)))}"
    # Pass the backup bucket name to the VM via metadata — setup script reads it
    backup-bucket = google_storage_bucket.backups.name
    # Disable OS Login so our metadata SSH key is honored (simpler for beginners)
    enable-oslogin = "FALSE"
  }

  allow_stopping_for_update = true

  lifecycle {
    ignore_changes = [
      # Don't recreate the VM when Google rotates the Debian image SHA
      boot_disk[0].initialize_params[0].image,
    ]
  }
}

# ── Firewall rules ───────────────────────────────────────────────────────────
# SSH — admin IP only
resource "google_compute_firewall" "ssh" {
  name        = "${var.vm_name}-allow-ssh"
  network     = google_compute_network.synapse.id
  description = "SSH from admin_ip_cidr only"

  allow {
    protocol = "tcp"
    ports    = ["22"]
  }

  source_ranges = [var.admin_ip_cidr]
  target_tags   = ["synapse"]
}

# HTTP + HTTPS — world (certbot needs port 80, frontend serves on 443)
resource "google_compute_firewall" "http" {
  name        = "${var.vm_name}-allow-http"
  network     = google_compute_network.synapse.id
  description = "HTTP/HTTPS from anywhere (frontend + certbot HTTP-01 challenge)"

  allow {
    protocol = "tcp"
    ports    = ["80", "443"]
  }

  source_ranges = ["0.0.0.0/0"]
  target_tags   = ["synapse"]
}

# Management ports — admin IP only (Grafana, Prometheus, MLflow, agent APIs)
resource "google_compute_firewall" "admin" {
  name        = "${var.vm_name}-allow-admin"
  network     = google_compute_network.synapse.id
  description = "Grafana/Prometheus/MLflow/agent APIs — admin_ip_cidr only"

  allow {
    protocol = "tcp"
    ports = [
      "3000",      # Grafana
      "5000",      # MLflow
      "7474",      # Neo4j Browser
      "7687",      # Neo4j Bolt (only if you want a remote Cypher client)
      "8080",      # Kafka UI
      "8081-8090", # 8 agents (8081-8088) + digital twin (8089) + orchestrator (8090)
      "9090",      # Prometheus
      "16686",     # Jaeger UI
    ]
  }

  source_ranges = [var.admin_ip_cidr]
  target_tags   = ["synapse"]
}
