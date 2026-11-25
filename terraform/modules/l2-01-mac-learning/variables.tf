variable "lab_password" {
  description = "Password for the lab switches (user admin) and the Ubuntu node (user student). Lab only."
  type        = string
  sensitive   = true
}
