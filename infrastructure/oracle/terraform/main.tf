# ============================================================================
# SYNAPSE — Oracle Cloud Always-Free VM provisioning (Terraform IaC)
#
# Provisions:
#   - VCN with a public subnet + Internet Gateway + default route
#   - Security list (ingress on ports needed by SYNAPSE stack)
#   - VM.Standard.A1.Flex compute instance (4 OCPU, 24 GB RAM, ARM64)
#   - Canonical Ubuntu 22.04 ARM64 image (resolved dynamically)
#
# Cost: $0 — all resources live inside Oracle Cloud Always-Free limits.
#        Verify quota in OCI Console → Governance → Limits, Quotas & Usage.
#
# Usage:
#   cd infrastructure/oracle/terraform
#   terraform init
#   terraform apply \
#       -var="tenancy_ocid=ocid1.tenancy.oc1..xxxx" \
#       -var="user_ocid=ocid1.user.oc1..xxxx" \
#       -var="compartment_ocid=ocid1.compartment.oc1..xxxx" \
#       -var="fingerprint=xx:xx:..." \
#       -var="private_key_path=~/.oci/oci_api_key.pem" \
#       -var="region=ap-mumbai-1" \
#       -var="ssh_public_key=$(cat ~/.ssh/oracle_synapse.pub)"
#
#   terraform output public_ip
# ============================================================================

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    oci = {
      source  = "oracle/oci"
      version = "~> 5.40"
    }
  }
}

provider "oci" {
  tenancy_ocid     = var.tenancy_ocid
  user_ocid        = var.user_ocid
  fingerprint      = var.fingerprint
  private_key_path = var.private_key_path
  region           = var.region
}

# ── Availability domain (first AD in region; A1.Flex capacity often varies) ──
data "oci_identity_availability_domains" "ads" {
  compartment_id = var.tenancy_ocid
}

# ── Canonical Ubuntu 22.04 ARM64 image (resolved at plan time) ──
data "oci_core_images" "ubuntu_2204_arm" {
  compartment_id           = var.compartment_ocid
  operating_system         = "Canonical Ubuntu"
  operating_system_version = "22.04"
  shape                    = var.instance_shape
  sort_by                  = "TIMECREATED"
  sort_order               = "DESC"
}

# ── Network ──────────────────────────────────────────────────────────────────
resource "oci_core_vcn" "synapse" {
  compartment_id = var.compartment_ocid
  cidr_blocks    = ["10.0.0.0/16"]
  display_name   = "synapse-vcn"
  dns_label      = "synapse"
}

resource "oci_core_internet_gateway" "synapse" {
  compartment_id = var.compartment_ocid
  vcn_id         = oci_core_vcn.synapse.id
  display_name   = "synapse-igw"
  enabled        = true
}

resource "oci_core_route_table" "synapse" {
  compartment_id = var.compartment_ocid
  vcn_id         = oci_core_vcn.synapse.id
  display_name   = "synapse-rt"

  route_rules {
    destination       = "0.0.0.0/0"
    destination_type  = "CIDR_BLOCK"
    network_entity_id = oci_core_internet_gateway.synapse.id
  }
}

resource "oci_core_security_list" "synapse" {
  compartment_id = var.compartment_ocid
  vcn_id         = oci_core_vcn.synapse.id
  display_name   = "synapse-seclist"

  egress_security_rules {
    destination = "0.0.0.0/0"
    protocol    = "all"
  }

  # SSH
  ingress_security_rules {
    protocol = "6"
    source   = var.ssh_ingress_cidr
    tcp_options {
      min = 22
      max = 22
    }
  }

  # HTTP / HTTPS (nginx)
  ingress_security_rules {
    protocol = "6"
    source   = "0.0.0.0/0"
    tcp_options {
      min = 80
      max = 80
    }
  }
  ingress_security_rules {
    protocol = "6"
    source   = "0.0.0.0/0"
    tcp_options {
      min = 443
      max = 443
    }
  }

  # Grafana / Prometheus / Neo4j Browser / MLflow
  ingress_security_rules {
    protocol = "6"
    source   = var.ssh_ingress_cidr
    tcp_options {
      min = 3000
      max = 3000
    }
  }
  ingress_security_rules {
    protocol = "6"
    source   = var.ssh_ingress_cidr
    tcp_options {
      min = 9090
      max = 9090
    }
  }
  ingress_security_rules {
    protocol = "6"
    source   = var.ssh_ingress_cidr
    tcp_options {
      min = 7474
      max = 7474
    }
  }
  ingress_security_rules {
    protocol = "6"
    source   = var.ssh_ingress_cidr
    tcp_options {
      min = 5000
      max = 5000
    }
  }

  # Agent API range (Bengaluru 8001-8008 mapped as 8081-8089)
  ingress_security_rules {
    protocol = "6"
    source   = var.ssh_ingress_cidr
    tcp_options {
      min = 8080
      max = 8099
    }
  }
}

resource "oci_core_subnet" "synapse_public" {
  compartment_id      = var.compartment_ocid
  vcn_id              = oci_core_vcn.synapse.id
  cidr_block          = "10.0.1.0/24"
  display_name        = "synapse-public-subnet"
  dns_label           = "public"
  route_table_id      = oci_core_route_table.synapse.id
  security_list_ids   = [oci_core_security_list.synapse.id]
  prohibit_public_ip_on_vnic = false
}

# ── Compute instance ─────────────────────────────────────────────────────────
resource "oci_core_instance" "synapse" {
  availability_domain = data.oci_identity_availability_domains.ads.availability_domains[var.availability_domain_index].name
  compartment_id      = var.compartment_ocid
  display_name        = "synapse-sprint6-runner"
  shape               = var.instance_shape

  shape_config {
    ocpus         = var.ocpus
    memory_in_gbs = var.memory_gb
  }

  source_details {
    source_type             = "image"
    source_id               = data.oci_core_images.ubuntu_2204_arm.images[0].id
    boot_volume_size_in_gbs = var.boot_volume_gb
  }

  create_vnic_details {
    subnet_id        = oci_core_subnet.synapse_public.id
    assign_public_ip = true
    hostname_label   = "synapse"
  }

  metadata = {
    ssh_authorized_keys = var.ssh_public_key
    # Minimal cloud-init: upgrade + pull the repo so setup_oracle_vm.sh is on disk
    # for the one-time bootstrap SSH that follows terraform apply.
    user_data = base64encode(<<-EOF
      #cloud-config
      package_update: true
      package_upgrade: false
      runcmd:
        - [ sh, -c, "apt-get install -y git curl" ]
        - [ sh, -c, "sudo -u ubuntu git clone https://github.com/${var.github_repo} /home/ubuntu/synapse || true" ]
    EOF
    )
  }

  preserve_boot_volume = false

  lifecycle {
    # If Oracle rejects A1.Flex capacity in this AD, operator retries with
    # a different availability_domain_index or region — instance destroy/re-
    # create is acceptable because all state lives outside the VM.
    ignore_changes = [source_details[0].source_id]
  }
}
