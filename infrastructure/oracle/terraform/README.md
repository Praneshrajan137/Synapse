# Oracle Cloud Always-Free VM — Terraform IaC

Provisions the single `VM.Standard.A1.Flex` (4 OCPU, 24 GB RAM, ARM64) that
SYNAPSE uses as its remote Sprint 6 verification target and GitHub Actions
self-hosted runner. All resources stay inside the Always-Free tier: permanent
$0 cost (confirms invariant **I-1**).

---

## Prerequisites

1. An OCI tenancy (free signup at <https://cloud.oracle.com/>). A credit card
   is required for identity verification but is **never charged** as long as
   you stay inside Always-Free limits.
2. An IAM user with a generated API signing key. From the OCI Console:
   _User Settings → API Keys → Add API Key → Generate API key pair_.
   - Download the private key to `~/.oci/oci_api_key.pem` (`chmod 600`).
   - Copy the shown **fingerprint**.
   - Copy the **tenancy OCID**, **user OCID**, and **compartment OCID** (root
     compartment is fine).
3. An SSH key pair for the VM:
   `ssh-keygen -t ed25519 -f ~/.ssh/oracle_synapse -N ""`.
4. Terraform ≥ 1.5.0 installed locally (`terraform version`).

---

## Usage

```bash
cd infrastructure/oracle/terraform

terraform init

terraform apply \
  -var="tenancy_ocid=ocid1.tenancy.oc1..aaa..." \
  -var="user_ocid=ocid1.user.oc1..aaa..." \
  -var="compartment_ocid=ocid1.compartment.oc1..aaa..." \
  -var="fingerprint=xx:xx:xx:xx:xx:xx:xx:xx:xx:xx:xx:xx:xx:xx:xx:xx" \
  -var="private_key_path=$HOME/.oci/oci_api_key.pem" \
  -var="region=ap-mumbai-1" \
  -var="github_repo=your-org/synapse" \
  -var="ssh_public_key=$(cat ~/.ssh/oracle_synapse.pub)"
```

On success, Terraform prints:

- `public_ip` — use in `export ORACLE_IP=...`.
- `ssh_command` — copy/paste to reach the VM.
- `runner_registration_hint` — the follow-up command to bootstrap Docker,
  Ollama, and the GitHub Actions runner.

---

## Capacity troubleshooting

A1.Flex capacity is often oversubscribed. If `apply` fails with
`Out of host capacity`:

1. Increment `availability_domain_index` (0 → 1 → 2) and re-apply.
2. Change `region` (try `us-phoenix-1`, `us-ashburn-1`, `uk-london-1`,
   `eu-frankfurt-1`, `ap-hyderabad-1`).
3. As a last resort, reduce `ocpus`/`memory_gb` — but the full Sprint 6 stack
   needs the full 4/24 allocation, so this should only be used temporarily.

The Oracle `oci_core_instance` resource is destroy-safe: no state persists on
the VM (everything is rebuilt by `setup_oracle_vm.sh` + compose on the next
workflow run).

---

## Tearing down

```bash
terraform destroy
```

Leaves the VCN/subnet/seclist in place only if they were pre-existing; the
compute instance, its boot volume, and the VCN created by this module are
removed. Confirm in the OCI Console that no stranded block volumes remain
(boot volumes billed separately if preserved).

---

## Next step

After `apply`, proceed to the bootstrap step in
[`../README.md`](../README.md) to install Docker, Ollama, and register the
GitHub Actions self-hosted runner.
