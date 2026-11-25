# Module: Layer 2 Lesson 2 lab (VLANs and trunking)
# Renders the CML topology and deploys it with cml2_lifecycle (import mode).

terraform {
  required_providers {
    cml2 = {
      source  = "CiscoDevNet/cml2"
      version = ">= 0.8.0"
    }
  }
}

resource "cml2_lifecycle" "this" {
  topology = templatefile("${path.module}/lab.yaml.tftpl", {
    lab_password   = var.lab_password
    vlan_audit_b64 = base64encode(file("${path.module}/../../../lessons/L2-02-vlans/vlan_audit.py"))
  })
}
