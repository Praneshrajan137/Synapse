# ============================================================================
# SYNAPSE — Cloud DNS managed zone + A record (Tier-B, opt-in)
#
# Replaces DuckDNS for stable, low-TTL DNS. Charged at ~$0.20/month for the
# zone + $0.40 per million queries (effectively free for a demo).
#
# Skipped entirely when var.deploy_domain == "" — single switch to enable.
#
# Flow:
#   1. Set var.deploy_domain = "synapse.your-domain.example"
#   2. Set var.managed_zone_dns_name = "your-domain.example."   (trailing dot!)
#   3. terraform apply
#   4. terraform output dns_name_servers
#   5. At your domain registrar, set the NS records for your-domain.example to
#      the 4 nameservers printed above. Wait 5-30 min for propagation.
#   6. setup_gcp_vm.sh's certbot step uses the domain.
# ============================================================================

resource "google_dns_managed_zone" "synapse" {
  count       = var.deploy_domain == "" ? 0 : 1
  name        = "${var.vm_name}-zone"
  dns_name    = var.managed_zone_dns_name
  description = "SYNAPSE managed zone for ${var.deploy_domain}"
  labels      = var.labels

  visibility = "public"

  dnssec_config {
    state = "on"
  }
}

resource "google_dns_record_set" "synapse_a" {
  count        = var.deploy_domain == "" ? 0 : 1
  managed_zone = google_dns_managed_zone.synapse[0].name
  name         = "${var.deploy_domain}."
  type         = "A"
  ttl          = 300
  rrdatas      = [google_compute_address.synapse.address]
}
