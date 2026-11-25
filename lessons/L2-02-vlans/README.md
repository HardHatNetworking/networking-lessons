# L2-02: VLANs and trunking

A VLAN splits one switch into several logical switches, each with its own broadcast domain and MAC table. A trunk carries many VLANs between switches on one link, tagging each frame with an 802.1Q VLAN ID. This lab starts broken and ends with a working trunk, then breaks it four more ways.

## The lab

```
 PC-A  VLAN 10 ─ Gi0/1 ┐                ┌ Gi0/1 ─ PC-C  VLAN 10
                       SW1 ─ Gi0/3 ─ Gi0/3 SW2
 PC-B  VLAN 20 ─ Gi0/2 ┘   (no trunk    └ Gi0/2 ─ PC-D  VLAN 20
                             yet)
 Management, VLAN 99, 10.99.99.0/24 (separate from the lesson traffic):
   SW1 Gi1/0 (.11) ┐
   SW2 Gi1/0 (.12) ┼─ mgmt-sw ─ automation (.10) ─ internet-nat
```

| Device | Port | VLAN | Address |
| --- | --- | --- | --- |
| PC-A | SW1 Gi0/1 | 10 OFFICE | 10.10.10.10/24 |
| PC-B | SW1 Gi0/2 | 20 CAMERAS | 10.20.20.20/24 |
| PC-C | SW2 Gi0/1 | 10 OFFICE | 10.10.10.30/24 |
| PC-D | SW2 Gi0/2 | 20 CAMERAS | 10.20.20.40/24 |
| SW1 ↔ SW2 | Gi0/3 | starts as `dynamic auto` on both ends | |

Build it from [`terraform/environments/l2-02-vlans`](../../terraform/environments/l2-02-vlans/) (see the [main README](../../README.md)).

## Tasks

1. **Prove it's broken.** From PC-A, `ping 10.10.10.30` fails. On SW1, `show interfaces gi0/3 switchport` shows *Administrative Mode: dynamic auto, Operational Mode: static access*. Two `auto` ports wait for each other forever.
2. **Build the trunk.** On both switches (the lab already set `switchport trunk encapsulation dot1q`, which IOSvL2 needs first):
   ```
   interface GigabitEthernet0/3
    switchport mode trunk
    switchport nonegotiate
    switchport trunk allowed vlan 10,20
   ```
   PC-A reaches PC-C, PC-B reaches PC-D. `show interfaces trunk` lists VLANs 10 and 20.
3. **VLANs don't talk.** From PC-A, `ping 10.20.20.20` fails: different VLAN, different subnet, no router.
4. **The missing `add`.** On SW1 only: `switchport trunk allowed vlan 30`. Both VLANs stop crossing, because the list was replaced. Restore it with `switchport trunk allowed vlan 10,20`, then compare with `switchport trunk allowed vlan add 30`.
5. **See the tag.** Capture on the SW1–SW2 link and ping PC-A to PC-C: every frame carries an 802.1Q header with VLAN ID 10.
6. **Native VLAN mismatch.** Create VLAN 999 on both switches, then `switchport trunk native vlan 999` on SW1 only. SW1 logs `%CDP-4-NATIVE_VLAN_MISMATCH`. Fix it on SW2.
7. **A VLAN on one side only.** On SW2: `no vlan 20`. PC-D's port goes inactive and VLAN 20 drops out of *allowed and active*. Recreate it with `vlan 20`.

## Automation nugget: `vlan_audit.py`

Logs into every switch, pairs up the two ends of each link with CDP, and reports VLAN and trunk mismatches. It parses the switches' output with TextFSM templates (ntc-templates) instead of hand-written regular expressions.

| Command | What the script takes from it |
| --- | --- |
| `show vlan brief` | Which VLANs exist on each switch |
| `show interfaces switchport` | Each port's mode, access VLAN, native VLAN, allowed VLANs |
| `show cdp neighbors detail` | Which switch and port is on the other end of each link |

It checks for: VLANs missing on some switches, links that should be trunks but aren't, native VLAN mismatches, allowed lists that differ between the two ends, and VLANs with ports on both switches that no link carries.

Terraform installs the script, Python and Netmiko on the `automation` node. Open its console, log in as `student` (lab password), then:

```bash
read -s -p 'Password: ' NET_PASS; echo; export NET_PASS     # switch password, user admin
python3 vlan_audit.py 10.99.99.11 10.99.99.12
```

On the freshly built lab:

```
3 problem(s) found:
  - SW1 Gi0/3 <-> SW2 Gi0/3 is not trunking (SW1: dynamic auto -> static access, SW2: dynamic auto -> static access)
  - VLAN 10 has ports on SW1 and SW2, but no link between them carries it
  - VLAN 20 has ports on SW1 and SW2, but no link between them carries it
```

After task 2: `No VLAN or trunk problems found.` It exits with code 1 when it finds problems, so it can run in a pipeline.

### Notes

- **Templates have gaps.** ntc-templates has no template for IOS `show interfaces trunk`, so the script reads `show interfaces switchport` instead, and it uses `show cdp neighbors detail` because the plain `show cdp neighbors` template can misread rows with a blank Platform column.
- **Not every switch-to-switch link should be a trunk.** The Gi1/0 management ports reach each other through the unmanaged switch, so CDP sees them as a second link. The script treats a link with both ends hard-set to access in the same VLAN as deliberate.
- The IOSvL2 snags from Lesson 1 apply here too: the lab pins `paramiko<5`, and an EEM applet brings Vlan99 up after boot.

## Lab credentials

Switches: `admin`. Ubuntu: `student`. Both use the `lab_password` variable (default `LabOnly-ChangeMe1`). Lab only.
