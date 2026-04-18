# ============================================================================
# SYNAPSE — Terraform outputs
# ============================================================================

output "public_ip" {
  description = "Public IPv4 address of the Oracle VM — use in ORACLE_IP env var"
  value       = oci_core_instance.synapse.public_ip
}

output "ssh_command" {
  description = "Ready-to-copy SSH command"
  value       = "ssh -i ~/.ssh/oracle_synapse ubuntu@${oci_core_instance.synapse.public_ip}"
}

output "runner_registration_hint" {
  description = "Next step — run setup_oracle_vm.sh with a GitHub Actions runner token"
  value = join("\n", [
    "# 1) In GitHub: repo → Settings → Actions → Runners → New self-hosted runner",
    "#    Copy the token from the displayed ./config.sh command.",
    "# 2) SSH to the VM and run the setup script with the token:",
    "ssh -i ~/.ssh/oracle_synapse ubuntu@${oci_core_instance.synapse.public_ip} \\",
    "    'GH_RUNNER_TOKEN=<token> GH_RUNNER_URL=https://github.com/<owner>/<repo> bash -s' \\",
    "    < ../setup_oracle_vm.sh",
    "# 3) Confirm runner online: GitHub → Settings → Actions → Runners (labels: oracle, arm64)",
  ])
}

output "instance_ocid" {
  description = "OCID of the provisioned instance (useful for support cases and manual teardown)"
  value       = oci_core_instance.synapse.id
}
