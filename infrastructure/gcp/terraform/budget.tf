# ============================================================================
# SYNAPSE — Cloud Billing budget alert (Tier-A hardening, ADR-037)
#
# Hard cost guardrail. Honest about the I-1 ($0) invariant: the budget alert
# is what makes "GCP free trial credit + Oracle Always-Free fallback" credible
# instead of aspirational.
#
# Alerts fire at 25 / 50 / 75 / 90 / 100 % of var.budget_amount_usd. The
# default $300 matches a fresh Google Cloud free trial. The auto-stop schedule
# in main.tf keeps actual spend at ~$65/mo, so the 25 % threshold is the early
# warning, not the upper limit.
#
# Skips if var.billing_account_id is empty — single var, easy to enable later.
# ============================================================================

resource "google_billing_budget" "synapse" {
  count           = var.billing_account_id == "" ? 0 : 1
  billing_account = var.billing_account_id
  display_name    = "SYNAPSE ${var.vm_name} budget"

  budget_filter {
    projects               = ["projects/${var.project_id}"]
    credit_types_treatment = "INCLUDE_ALL_CREDITS"
  }

  amount {
    specified_amount {
      currency_code = "USD"
      units         = tostring(var.budget_amount_usd)
    }
  }

  threshold_rules {
    threshold_percent = 0.25
    spend_basis       = "CURRENT_SPEND"
  }
  threshold_rules {
    threshold_percent = 0.5
    spend_basis       = "CURRENT_SPEND"
  }
  threshold_rules {
    threshold_percent = 0.75
    spend_basis       = "CURRENT_SPEND"
  }
  threshold_rules {
    threshold_percent = 0.9
    spend_basis       = "CURRENT_SPEND"
  }
  threshold_rules {
    threshold_percent = 1.0
    spend_basis       = "CURRENT_SPEND"
  }
  # Also flag forecasted-overage early — gives 1-2 days of lead time.
  threshold_rules {
    threshold_percent = 1.0
    spend_basis       = "FORECASTED_SPEND"
  }

  all_updates_rule {
    monitoring_notification_channels = var.budget_alert_email == "" ? [] : [google_monitoring_notification_channel.budget[0].id]
    disable_default_iam_recipients   = false
  }
}

resource "google_monitoring_notification_channel" "budget" {
  count        = var.budget_alert_email == "" ? 0 : 1
  display_name = "SYNAPSE budget email"
  type         = "email"
  labels = {
    email_address = var.budget_alert_email
  }
}
