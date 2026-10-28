#!/usr/bin/env python3
import datetime
import ipaddress
import subprocess
from pathlib import Path


def station_identity(station_id):
    hostname = "nezjištěno"
    try:
        hostname = subprocess.run(["hostname", "-f"], check=True, capture_output=True, text=True, timeout=5).stdout.strip() or hostname
    except (OSError, subprocess.SubprocessError):
        pass
    ipv4 = "nezjištěna"
    interface = ""
    try:
        route = subprocess.run(["ip", "-4", "route", "get", "1.1.1.1"], check=True, capture_output=True, text=True, timeout=5).stdout.split()
        ipv4 = route[route.index("src") + 1]
        interface = route[route.index("dev") + 1]
        if not ipaddress.ip_address(ipv4).version == 4:
            ipv4 = "nezjištěna"
            interface = ""
    except (OSError, subprocess.SubprocessError, ValueError, IndexError):
        pass
    mac = "nezjištěna"
    if interface:
        try:
            mac = Path(f"/sys/class/net/{interface}/address").read_text().strip() or mac
        except OSError:
            pass
    timestamp = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
    return "\n".join((f"Stanice: {station_id}", f"Hostname: {hostname}", f"IP: {ipv4}", f"MAC: {mac}", f"Čas stanice: {timestamp}"))
