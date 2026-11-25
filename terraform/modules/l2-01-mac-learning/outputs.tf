output "lab_id" {
  description = "CML lab ID."
  value       = cml2_lifecycle.this.id
}

output "test_plan" {
  description = "What to check once the lab is up."
  value       = <<-EOT
    1. Wait a few minutes: switches boot slowly, and "automation" installs Netmiko on first boot.
    2. SW1/SW2: clear mac address-table dynamic
    3. PC-A: ping 10.1.1.20, ping 10.1.1.30, ping 10.1.1.40
    4. SW1: show mac address-table vlan 1  -> 000a Gi0/1, 000b Gi0/2, 000c + 000d Gi0/3
    5. Filter demo: clear the table on SW2 only, then PC-C: ping 10.1.1.40
    6. automation (user student):
         read -s -p "Password: " NET_PASS; echo; export NET_PASS
         python3 mac_locator.py 10.99.99.11 10.99.99.12 --vlan 1
  EOT
}
