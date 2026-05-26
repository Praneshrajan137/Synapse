# ============================================================================
# SYNAPSE — Artifact Registry (Tier-A hardening)
#
# A region-scoped Docker repository. CI builds and pushes images here on v*
# tags (see .github/workflows/cd-gcp.yml); the VM pulls them via the
# Compute Engine default service account → roles/artifactregistry.reader
# (granted in main.tf).
#
# Format = DOCKER, mode = STANDARD_REPOSITORY. Vulnerability scanning runs
# automatically on push (free for the first 100 scans/month — fine for a
# v*-tag-gated cadence).
# ============================================================================

resource "google_artifact_registry_repository" "synapse" {
  location      = var.region
  repository_id = var.artifact_registry_repo
  format        = "DOCKER"
  description   = "SYNAPSE container images. Built by .github/workflows/cd-gcp.yml on v* tags, signed with Cosign, pulled by the GCE VM."
  labels        = var.labels

  docker_config {
    immutable_tags = true # Tags are append-only — prevents :latest re-pointing under your feet
  }
}
