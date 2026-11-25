#!/usr/bin/env python3
"""
mac_locator.py - Find which switch port a MAC address lives on.

Automation nugget for Layer 2 Lesson 1 (MAC learning).

How it works:
  1. SSH to every switch and run "show mac address-table dynamic".
  2. Parse each line into (vlan, mac, type, port).
  3. Count how many MACs each port has learned. A port with exactly one
     MAC is treated as an edge (host) port; ports with more are uplinks
     or hubs/unmanaged switches.
  4. Report the edge port for each MAC, or for the one MAC you ask about.

Usage:
  export NET_USER=admin NET_PASS=<lab password>
  python3 mac_locator.py 192.0.2.11 192.0.2.12
  python3 mac_locator.py 192.0.2.11 192.0.2.12 --mac 0000.0000.000c
  python3 mac_locator.py 192.0.2.11 192.0.2.12 --vlan 1

Requires: pip install netmiko
"""

import argparse
import os
import re
import sys
from collections import defaultdict

# One table row, e.g. "   1    0000.0000.000a    DYNAMIC     Gi0/1"
MAC_LINE = re.compile(
    r"^\s*(?P<vlan>\d+)\s+"
    r"(?P<mac>[0-9a-f]{4}\.[0-9a-f]{4}\.[0-9a-f]{4})\s+"
    r"(?P<type>\S+)\s+"
    r"(?P<port>\S+)\s*$",
    re.IGNORECASE | re.MULTILINE,
)


def normalize_mac(mac: str) -> str:
    """Accept aa:bb:cc:dd:ee:ff, aa-bb-..., or aabb.ccdd.eeff; return Cisco format."""
    digits = re.sub(r"[^0-9a-fA-F]", "", mac).lower()
    if len(digits) != 12:
        raise ValueError(f"Not a MAC address: {mac}")
    return f"{digits[0:4]}.{digits[4:8]}.{digits[8:12]}"


def parse_mac_table(output: str) -> list[dict]:
    """Turn 'show mac address-table' text into a list of row dicts."""
    rows = []
    for m in MAC_LINE.finditer(output):
        row = m.groupdict()
        row["mac"] = row["mac"].lower()
        row["vlan"] = int(row["vlan"])
        rows.append(row)
    return rows


def collect(hosts: list[str], username: str, password: str) -> dict[str, list[dict]]:
    """SSH to each switch and return {switch_name: [rows]}."""
    from netmiko import ConnectHandler  # imported here so the parser runs without netmiko

    tables = {}
    for host in hosts:
        device = {
            "device_type": "cisco_ios",
            "host": host,
            "username": username,
            "password": password,
        }
        try:
            with ConnectHandler(**device) as conn:
                name = conn.find_prompt().rstrip("#>")
                output = conn.send_command("show mac address-table dynamic")
        except Exception as exc:  # keep going if one switch is down
            print(f"!! {host}: {exc}", file=sys.stderr)
            continue
        tables[name] = parse_mac_table(output)
        print(f"   {name} ({host}): {len(tables[name])} MACs", file=sys.stderr)
    return tables


def locate(tables: dict[str, list[dict]], vlan: int | None = None) -> dict[str, list[dict]]:
    """
    Return {mac: [sightings]} where each sighting is a row plus the switch
    name and whether that port looks like an edge port.
    """
    # How many MACs did each (switch, port) learn?
    per_port = defaultdict(int)
    for switch, rows in tables.items():
        for r in rows:
            if vlan is None or r["vlan"] == vlan:
                per_port[(switch, r["port"])] += 1

    sightings = defaultdict(list)
    for switch, rows in tables.items():
        for r in rows:
            if vlan is not None and r["vlan"] != vlan:
                continue
            count = per_port[(switch, r["port"])]
            sightings[r["mac"]].append(
                {**r, "switch": switch, "macs_on_port": count, "edge": count == 1}
            )
    return sightings


def report(sightings: dict[str, list[dict]], only_mac: str | None = None) -> None:
    macs = [only_mac] if only_mac else sorted(sightings)
    print(f"{'MAC':<16} {'VLAN':<5} {'Lives on':<22} Also seen on (uplinks)")
    print("-" * 75)
    for mac in macs:
        seen = sightings.get(mac)
        if not seen:
            print(f"{mac:<16} not found on any switch (aged out, or never talked)")
            continue
        edges = [s for s in seen if s["edge"]]
        uplinks = [s for s in seen if not s["edge"]]
        home = (
            ", ".join(f"{s['switch']} {s['port']}" for s in edges)
            or "no single-MAC port (behind a hub/unmanaged switch?)"
        )
        also = ", ".join(f"{s['switch']} {s['port']} ({s['macs_on_port']})" for s in uplinks)
        print(f"{mac:<16} {seen[0]['vlan']:<5} {home:<22} {also}")


def main() -> None:
    p = argparse.ArgumentParser(description="Find the switch port a MAC address lives on.")
    p.add_argument("hosts", nargs="+", help="switch IPs or hostnames")
    p.add_argument("--mac", help="look up one MAC (any common format)")
    p.add_argument("--vlan", type=int, help="only consider this VLAN")
    args = p.parse_args()

    user, password = os.environ.get("NET_USER"), os.environ.get("NET_PASS")
    if not user or not password:
        sys.exit("Set NET_USER and NET_PASS environment variables first.")

    tables = collect(args.hosts, user, password)
    sightings = locate(tables, args.vlan)
    report(sightings, normalize_mac(args.mac) if args.mac else None)


if __name__ == "__main__":
    main()
