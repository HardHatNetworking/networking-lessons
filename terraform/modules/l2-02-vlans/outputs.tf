output "lab_id" {
  description = "CML lab ID."
  value       = cml2_lifecycle.this.id
}

output "test_plan" {
  description = "What to check once the lab is up."
  value       = <<-EOT
    1. Wait a few minutes: switches boot slowly, and "automation" installs Netmiko on first boot.
    2. The lab starts broken: PC-A: ping 10.10.10.30 fails (no trunk, both ends dynamic auto).
    3. SW1/SW2 Gi0/3: switchport mode trunk / switchport nonegotiate / switchport trunk allowed vlan 10,20
    4. PC-A: ping 10.10.10.30 and PC-B: ping 10.20.20.40 now work; PC-A: ping 10.20.20.20 still fails (different VLAN).
    5. automation (user student):
         read -s -p "Password: " NET_PASS; echo; export NET_PASS
         python3 vlan_audit.py 10.99.99.11 10.99.99.12
       Before step 3: 3 problems. After step 3: no problems.
  EOT
}
