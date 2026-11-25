# Module: Layer 2 Lesson 1 lab (MAC learning, forwarding, flooding, filtering)
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
    lab_password    = var.lab_password
    mac_locator_b64 = base64encode(file("${path.module}/../../../lessons/L2-01-mac-learning/mac_locator.py"))
  })
}
