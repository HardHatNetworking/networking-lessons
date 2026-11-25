# L2-01: How a switch learns, forwards, floods and filters

A switch builds its MAC address table by reading the **source** MAC of every frame, then forwards, floods or filters based on the **destination** MAC. This lab lets you watch it happen.

## The lab

```
 PC-A (000a) ─ Gi0/1 ┐                ┌ Gi0/1 ─ PC-C (000c)
                     SW1 ─ Gi0/3 ─ Gi0/3 SW2
 PC-B (000b) ─ Gi0/2 ┘                └ Gi0/2 ─ PC-D (000d)

 Management, VLAN 99, 10.99.99.0/24 (separate from the lesson traffic):
   SW1 Gi1/0 (.11) ┐
   SW2 Gi1/0 (.12) ┼─ mgmt-sw ─ automation (.10) ─ internet-nat
```

| Device | Address |
| --- | --- |
| PC-A / PC-B / PC-C / PC-D | 10.1.1.10 / .20 / .30 / .40 (VLAN 1) |
| SW1 / SW2 management | 10.99.99.11 / .12 (VLAN 99) |
| automation (Ubuntu) | 10.99.99.10 |

The "PCs" are IOSv routers with `no ip routing` and hand-set MACs like `0000.0000.000a`, so every table entry is easy to read. Nothing in the lab is bridged to your real network. The `internet-nat` connector only lets the Ubuntu node install Netmiko on first boot.

Build it from [`terraform/environments/l2-01-mac-learning`](../../terraform/environments/l2-01-mac-learning/) (see the [main README](../../README.md)).

## Tasks

1. **Start empty.** On SW1 and SW2: `clear mac address-table dynamic`.
2. **Learn and flood.** From PC-A: `ping 10.1.1.20`. Capture on the SW1–SW2 link: the ARP broadcast crosses to SW2, the pings don't.
3. **Read the table.** On SW1: `show mac address-table vlan 1` shows `000a` on Gi0/1 and `000b` on Gi0/2.
4. **Two MACs, one port.** From PC-A ping PC-C (10.1.1.30) and PC-D (10.1.1.40). SW1 learns `000c` and `000d`, both on Gi0/3.
5. **Filter.** Clear the table on SW2 only, then ping from PC-C to PC-D. SW2 floods the unknown unicast toward SW1, and SW1 drops it because PC-D's entry points back to Gi0/3.
6. **Aging.** On SW1: `mac address-table aging-time 30`. Stop pinging and watch the entries disappear. Undo with `no mac address-table aging-time`.
7. **Static entry.** `mac address-table static 0000.0000.00ee vlan 1 interface Gi0/2` shows as STATIC and never ages out.

## Automation nugget: `mac_locator.py`

Finds the switch port a MAC address actually lives on. It pulls the MAC table from every switch and counts MACs per port: a port with exactly one MAC is an edge port, and that's where the host is. Uplinks carry many MACs.

Terraform installs the script, Python and Netmiko on the `automation` node. Open its console, log in as `student` (lab password), then:

```bash
read -s -p 'Password: ' NET_PASS; echo; export NET_PASS     # switch password, user admin
python3 mac_locator.py 10.99.99.11 10.99.99.12 --vlan 1
python3 mac_locator.py 10.99.99.11 10.99.99.12 --mac 0000.0000.000c
```

Ping between the PCs first: MAC entries age out after 5 minutes.

### Two snags from building this lab

- **Old gear speaks old SSH.** IOSvL2's SSH server only offers SHA-1 key exchanges, and Paramiko 5 (the SSH library Netmiko uses) removed them. The lab pins `paramiko<5`. You'll hit the same thing automating older production switches.
- **Vlan99 comes up down/down after boot.** IOSvL2 doesn't bring the SVI up until it's bounced, and it doesn't support `no autostate`. The switch configs include an EEM applet that bounces Vlan99 90 seconds after boot.

### Limits

- Two hosts behind an unmanaged switch give a port two MACs, so neither looks like an edge port. The script says so instead of guessing.
- It logs into every switch and pulls the whole table, so it suits a lab, not 200 switches. A later lesson follows the MAC hop by hop with CDP/LLDP instead.

## Lab credentials

Switches: `admin`. Ubuntu: `student`. Both use the `lab_password` variable (default `LabOnly-ChangeMe1`). Lab only.
