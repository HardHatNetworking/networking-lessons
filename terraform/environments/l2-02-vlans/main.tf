terraform {
  required_providers {
    cml2 = {
      source  = "CiscoDevNet/cml2"
      version = ">= 0.8.0"
    }
  }
}

variable "cml_address" { type = string }
variable "cml_username" { type = string }
variable "cml_password" {
  type      = string
  sensitive = true
}

variable "lab_password" {
  description = "Password for the lab switches (admin) and the Ubuntu node (student). Lab only."
  type        = string
  sensitive   = true
  default     = "LabOnly-ChangeMe1"
}

provider "cml2" {
  address     = var.cml_address
  username    = var.cml_username
  password    = var.cml_password
  skip_verify = true
}

module "l2_02_vlans" {
  source       = "../../modules/l2-02-vlans"
  lab_password = var.lab_password
}

output "lab_id" {
  value = module.l2_02_vlans.lab_id
}

output "test_plan" {
  value = module.l2_02_vlans.test_plan
}
