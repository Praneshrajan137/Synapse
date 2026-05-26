# ============================================================================
# SYNAPSE — Workload Identity Federation for GitHub Actions (Tier-A)
#
# Lets the cd-gcp.yml workflow exchange its short-lived GitHub OIDC token for
# a short-lived GCP access token. No JSON service-account keys live in GitHub
# Secrets — that's the whole point. See:
#   https://cloud.google.com/iam/docs/workload-identity-federation-with-deployment-pipelines
#
# Scoping is enforced TWICE:
#   1. attribute_condition restricts the OIDC subject to var.github_repo.
#   2. iam.workloadIdentityUser binding restricts which subjects can impersonate
#      the GitHub Actions service account.
# Either change alone is a misconfiguration; both together = defence in depth.
# ============================================================================

resource "google_iam_workload_identity_pool" "github" {
  workload_identity_pool_id = "synapse-github-pool"
  display_name              = "SYNAPSE GitHub Actions"
  description               = "WIF pool for cd-gcp.yml — only ${var.github_repo} can mint tokens."
}

resource "google_iam_workload_identity_pool_provider" "github" {
  workload_identity_pool_id          = google_iam_workload_identity_pool.github.workload_identity_pool_id
  workload_identity_pool_provider_id = "github"
  display_name                       = "GitHub OIDC"
  description                        = "Trusts https://token.actions.githubusercontent.com for ${var.github_repo}"

  attribute_mapping = {
    "google.subject"       = "assertion.sub"
    "attribute.repository" = "assertion.repository"
    "attribute.ref"        = "assertion.ref"
    "attribute.actor"      = "assertion.actor"
  }

  # Refuse tokens from other GitHub repos — the WIF pool's first line of defense.
  attribute_condition = "assertion.repository == \"${var.github_repo}\""

  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }
}

# Dedicated service account that the cd-gcp.yml workflow impersonates.
# Kept distinct from the VM service account so an Actions compromise doesn't
# get backup-bucket write or VM-side privileges.
resource "google_service_account" "github_actions" {
  account_id   = "${var.vm_name}-gh-actions"
  display_name = "SYNAPSE GitHub Actions deployer"
  description  = "Impersonated by cd-gcp.yml via WIF. Pushes images to Artifact Registry and signs them with Cosign."
}

# Allow the GitHub repo's WIF subjects to impersonate the deployer SA.
resource "google_service_account_iam_member" "github_wif_binding" {
  service_account_id = google_service_account.github_actions.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github.name}/attribute.repository/${var.github_repo}"
}

# Permissions the deployer needs:
#   - artifactregistry.writer: push container images
#   - iam.serviceAccountTokenCreator: mint short-lived tokens for Cosign keyless signing
#   - iap.tunnelResourceAccessor: ssh-to-vm via IAP TCP tunnel (post-push deploy)
locals {
  github_actions_roles = [
    "roles/artifactregistry.writer",
    "roles/iam.serviceAccountTokenCreator",
    "roles/iap.tunnelResourceAccessor",
    "roles/compute.osLogin",
  ]
}

resource "google_project_iam_member" "github_actions_roles" {
  for_each = toset(local.github_actions_roles)
  project  = var.project_id
  role     = each.value
  member   = "serviceAccount:${google_service_account.github_actions.email}"
}
