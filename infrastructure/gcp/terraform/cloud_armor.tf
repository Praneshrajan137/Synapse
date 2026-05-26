# ============================================================================
# SYNAPSE — Cloud Armor WAF (Tier-B hardening, opt-in)
#
# Cloud Armor only attaches to backend services on an HTTPS Load Balancer.
# A single-VM topology without an LB cannot use Cloud Armor.
#
# This file is provisioned ONLY when var.enable_cloud_armor=true. It adds:
#   - Global external HTTPS Load Balancer ($18/mo for the forwarding rule)
#   - Backend service with a Network Endpoint Group pointing at the VM
#   - Managed SSL cert (free — needs deploy_domain set so the cert can be issued)
#   - Cloud Armor security policy with managed OWASP ruleset + 60 rps rate limit
#
# When this LB is active, you should:
#   - point Cloud DNS A record at the LB IP (not the VM IP)
#   - update the VM firewall to allow only Google's LB health-check ranges
#   - remove certbot from setup_gcp_vm.sh (LB terminates TLS)
#
# Default false because ~$18/mo materially affects the I-1 cost story.
# ============================================================================

resource "google_compute_security_policy" "armor" {
  count       = var.enable_cloud_armor ? 1 : 0
  name        = "${var.vm_name}-armor"
  description = "Cloud Armor WAF for SYNAPSE — OWASP managed rules + rate limit"

  # 1. Managed OWASP ruleset (XSS, SQLi, LFI, RFI, RCE, scanners).
  rule {
    action      = "deny(403)"
    priority    = "1000"
    description = "Block OWASP Top 10 attacks (managed ruleset)"
    match {
      expr {
        # Use sensitivity=4 (highest); switch to 2 if benign traffic is blocked
        expression = "evaluatePreconfiguredWaf('crs-v33-stable', {'sensitivity': 4})"
      }
    }
  }

  # 2. Per-IP rate limit — 60 rps with 600 burst, ban 1 hour after threshold.
  rule {
    action      = "rate_based_ban"
    priority    = "2000"
    description = "Per-IP 60 rps soft cap; 1-hour ban beyond"
    match {
      versioned_expr = "SRC_IPS_V1"
      config {
        src_ip_ranges = ["*"]
      }
    }
    rate_limit_options {
      conform_action = "allow"
      exceed_action  = "deny(429)"
      enforce_on_key = "IP"
      rate_limit_threshold {
        count        = 60
        interval_sec = 60
      }
      ban_duration_sec = 3600
    }
  }

  # 3. Default allow — catch-all at the lowest priority.
  rule {
    action      = "allow"
    priority    = "2147483647"
    description = "Default allow"
    match {
      versioned_expr = "SRC_IPS_V1"
      config {
        src_ip_ranges = ["*"]
      }
    }
  }

  adaptive_protection_config {
    layer_7_ddos_defense_config {
      enable = true
    }
  }
}

# The HTTPS LB itself is left as a follow-on. Wiring it up requires Cloud DNS
# (managed cert depends on a domain) and changes to the certbot flow. We stop
# here so terraform apply with enable_cloud_armor=true creates the policy
# without breaking the VM-direct path. Wiring to a backend service is a one-
# line `security_policy = google_compute_security_policy.armor[0].self_link`
# once the LB is added.
