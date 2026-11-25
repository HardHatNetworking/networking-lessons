#!/usr/bin/env python3
"""
vlan_audit.py - Find VLAN and trunk mismatches between switches.

Automation nugget for Layer 2 Lesson 2 (VLANs and trunking).

How it works:
  1. SSH to every switch and run three commands, parsed into structured data
     by TextFSM (the ntc-templates library that Netmiko installs):
       show vlan brief                 -> which VLANs exist, which ports are in each
       show interfaces switchport      -> mode, access VLAN, native VLAN, allowed VLANs
       show cdp neighbors detail       -> which switch and port is on the other end
  2. Use CDP to pair up the two ends of every link between the switches.
  3. Compare the two ends and the VLAN lists, and report anything that disagrees.

Checks:
  - A VLAN that exists on some switches but not others
  - A link between switches that isn't trunking (DTP left both ends waiting)
  - Native VLAN mismatch between the two ends of a trunk
  - VLANs allowed on one end of a trunk but not the other
  - A VLAN with access ports on both sides of a trunk that the trunk doesn't carry

Usage:
  export NET_USER=admin; read -s -p 'Password: ' NET_PASS; echo; export NET_PASS
  python3 vlan_audit.py 10.99.99.11 10.99.99.12

Requires: pip install netmiko "paramiko<5"   (netmiko brings ntc-templates)
"""

import argparse
import os
import re
import sys

# VLANs every Cisco switch has and nobody configures.
DEFAULT_VLANS = {1, 1002, 1003, 1004, 1005}

SHORT_NAMES = [
    ("TenGigabitEthernet", "Te"),
    ("GigabitEthernet", "Gi"),
    ("FastEthernet", "Fa"),
    ("Ethernet", "Et"),
    ("Port-channel", "Po"),
]


def short_if(name: str) -> str:
    """GigabitEthernet0/3 -> Gi0/3, so CDP and switchport names match."""
    name = name.strip()
    for long, short in SHORT_NAMES:
        if name.startswith(long):
            return short + name[len(long):]
    return name


def expand_vlans(items: list[str]) -> set[int]:
    """['10', '20', '30-32'] -> {10, 20, 30, 31, 32}; ['ALL'] -> 1-4094; ['NONE'] -> empty."""
    vlans: set[int] = set()
    for item in items:
        for part in str(item).replace(" ", "").split(","):
            if not part:
                continue
            if part.upper() == "ALL":
                return set(range(1, 4095))
            if part.upper() == "NONE":
                continue
            if "-" in part:
                lo, hi = part.split("-", 1)
                vlans.update(range(int(lo), int(hi) + 1))
            else:
                vlans.add(int(part))
    return vlans


def compress(vlans: set[int]) -> str:
    """{10, 11, 12, 20} -> '10-12,20' for readable output."""
    out, run = [], []
    for v in sorted(vlans):
        if run and v == run[-1] + 1:
            run.append(v)
            continue
        if run:
            out.append(f"{run[0]}-{run[-1]}" if len(run) > 1 else str(run[0]))
        run = [v]
    if run:
        out.append(f"{run[0]}-{run[-1]}" if len(run) > 1 else str(run[0]))
    return ",".join(out)


def build_switch(name: str, vlan_rows: list, port_rows: list, cdp_rows: list) -> dict:
    """Turn the three parsed commands into one switch record."""
    vlans = {int(r["vlan_id"]) for r in vlan_rows}
    ports = {short_if(r["interface"]): r for r in port_rows}
    neighbors = {
        short_if(r["local_interface"]): {
            "switch": r["neighbor_name"].split(".")[0],
            "port": short_if(r["neighbor_interface"]),
        }
        for r in cdp_rows
    }
    return {"name": name, "vlans": vlans, "ports": ports, "neighbors": neighbors}


def collect(hosts: list[str], username: str, password: str) -> dict[str, dict]:
    """SSH to each switch and return {switch_name: record}."""
    from netmiko import ConnectHandler  # imported here so the audit logic runs without netmiko

    switches = {}
    for host in hosts:
        device = {"device_type": "cisco_ios", "host": host,
                  "username": username, "password": password}
        try:
            with ConnectHandler(**device) as conn:
                name = conn.find_prompt().rstrip("#>")
                parsed = [conn.send_command(cmd, use_textfsm=True) for cmd in (
                    "show vlan brief",
                    "show interfaces switchport",
                    "show cdp neighbors detail",
                )]
        except Exception as exc:  # keep going if one switch is down
            print(f"!! {host}: {exc}", file=sys.stderr)
            continue
        # TextFSM returns a list; a plain string means the output didn't parse.
        if not all(isinstance(p, list) for p in parsed):
            print(f"!! {host}: could not parse one of the commands", file=sys.stderr)
            continue
        switches[name] = build_switch(name, *parsed)
        print(f"   {name} ({host}): {len(switches[name]['vlans'])} VLANs", file=sys.stderr)
    return switches


def links(switches: dict[str, dict]) -> list[tuple]:
    """Every link between two audited switches, once: (sw_a, port_a, sw_b, port_b)."""
    seen, out = set(), []
    for sw in switches.values():
        for port, nb in sw["neighbors"].items():
            if nb["switch"] not in switches:
                continue  # a neighbor we weren't asked to audit
            key = frozenset({(sw["name"], port), (nb["switch"], nb["port"])})
            if key not in seen:
                seen.add(key)
                out.append((sw["name"], port, nb["switch"], nb["port"]))
    return out


def allowed_text(vlans: set[int]) -> str:
    return "ALL" if len(vlans) == 4094 else (compress(vlans) or "none")


def access_vlans(sw: dict) -> set[int]:
    """VLANs this switch has access ports in."""
    return {int(p["access_vlan"]) for p in sw["ports"].values() if p["mode"] == "static access"}


def audit(switches: dict[str, dict]) -> list[str]:
    findings = []

    # 1. VLANs that exist on some switches but not others.
    every = set().union(*(s["vlans"] for s in switches.values())) - DEFAULT_VLANS
    for vlan in sorted(every):
        missing = [n for n, s in switches.items() if vlan not in s["vlans"]]
        if missing:
            findings.append(f"VLAN {vlan} is missing on {', '.join(missing)}")

    carried: dict[frozenset, set[int]] = {}  # VLANs carried between each pair of switches
    for a, pa, b, pb in links(switches):
        end_a, end_b = switches[a]["ports"].get(pa), switches[b]["ports"].get(pb)
        if not end_a or not end_b:
            continue
        label = f"{a} {pa} <-> {b} {pb}"
        pair = carried.setdefault(frozenset({a, b}), set())
        trunk_a, trunk_b = end_a["mode"] == "trunk", end_b["mode"] == "trunk"

        # A deliberate access link: both ends hard-set to access, same VLAN.
        # It carries that one VLAN and needs no trunk.
        if (not trunk_a and not trunk_b
                and "dynamic" not in end_a["admin_mode"] + end_b["admin_mode"]):
            if end_a["access_vlan"] == end_b["access_vlan"]:
                pair.add(int(end_a["access_vlan"]))
            else:
                findings.append(
                    f"{label} access VLAN mismatch ({a}: {end_a['access_vlan']}, "
                    f"{b}: {end_b['access_vlan']})")
            continue

        # 2. A link that should be a trunk but isn't (DTP, or one end hard-set to access).
        if not (trunk_a and trunk_b):
            findings.append(
                f"{label} is not trunking "
                f"({a}: {end_a['admin_mode']} -> {end_a['mode']}, "
                f"{b}: {end_b['admin_mode']} -> {end_b['mode']})")
            continue

        # 3. Native VLAN mismatch.
        if end_a["native_vlan"] != end_b["native_vlan"]:
            findings.append(
                f"{label} native VLAN mismatch ({a}: {end_a['native_vlan']}, "
                f"{b}: {end_b['native_vlan']})")

        # 4. Allowed on one end only.
        allowed_a = expand_vlans(end_a["trunking_vlans"])
        allowed_b = expand_vlans(end_b["trunking_vlans"])
        if allowed_a != allowed_b:
            findings.append(
                f"{label} allowed VLANs differ ({a}: {allowed_text(allowed_a)}, "
                f"{b}: {allowed_text(allowed_b)})")
        pair |= allowed_a & allowed_b & (switches[a]["vlans"] & switches[b]["vlans"])

    # 5. VLANs with access ports on both switches that no link between them carries.
    for pair, vlans in carried.items():
        a, b = sorted(pair)
        needed = (access_vlans(switches[a]) & access_vlans(switches[b])) - DEFAULT_VLANS
        for vlan in sorted(needed - vlans):
            findings.append(f"VLAN {vlan} has ports on {a} and {b}, but no link between them carries it")

    return findings


def main() -> None:
    p = argparse.ArgumentParser(description="Find VLAN and trunk mismatches between switches.")
    p.add_argument("hosts", nargs="+", help="switch IPs or hostnames")
    args = p.parse_args()

    user, password = os.environ.get("NET_USER"), os.environ.get("NET_PASS")
    if not user or not password:
        sys.exit("Set NET_USER and NET_PASS environment variables first.")

    switches = collect(args.hosts, user, password)
    if len(switches) < 2:
        sys.exit("Need at least two reachable switches to compare.")

    findings = audit(switches)
    if not findings:
        print("No VLAN or trunk problems found.")
        return
    print(f"{len(findings)} problem(s) found:")
    for f in findings:
        print(f"  - {f}")
    sys.exit(1)


if __name__ == "__main__":
    main()
