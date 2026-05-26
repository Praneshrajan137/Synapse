# ============================================================================
# SYNAPSE — Identity-Aware Proxy (Tier-B hardening)
#
# IAP TCP forwarding lets you reach Grafana/Prometheus/MLflow/agent APIs (and
# SSH) WITHOUT exposing those ports to the internet. The user identity is
# Google-signed; access is keyed by IAM, not source IP.
#
# Usage:
#   gcloud compute ssh <vm> --tunnel-through-iap
#   gcloud compute start-iap-tunnel <vm> 3000 --local-host-port=localhost:3000 \
#       --zone=<zone>
#   # then open http://localhost:3000 (Grafana)
#
# This file ONLY grants IAM. The firewall side is in main.tf (it switches
# admin/SSH source_ranges to IAP's 35.235.240.0/20 when var.use_iap_only=true).
# ============================================================================

# Grant project-level IAP tunnel access to the named users/groups.
resource "google_project_iam_member" "iap_tunnel_users" {
  for_each = toset(var.iap_users)
  project  = var.project_id
  role     = "roles/iap.tunnelResourceAccessor"
  member   = each.value
}

# Also grant compute.osLogin so they can `gcloud compute ssh`.
resource "google_project_iam_member" "iap_oslogin_users" {
  for_each = toset(var.iap_users)
  project  = var.project_id
  role     = "roles/compute.osLogin"
  member   = each.value
}
