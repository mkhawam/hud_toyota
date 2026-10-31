"""System provider: connectivity + Pi health.

``net.online`` is a cheap TCP connect to a public DNS server every 10 s —
it doesn't care whether the route is the phone hotspot or an LTE dongle,
which is exactly the point: internet widgets key off this one topic and
degrade gracefully when the car is offline.

``net.ap`` tells the HUD menu how to reach the settings page:
``{active, ssid, password, url}``. When no known Wi-Fi is in range the Pi
broadcasts its own access point (NetworkManager connection ``hud-ap``,
created by deploy/install.sh); the phone joins it in the car and opens
``url``. Credentials come from the ``wifi_ap`` config section the installer
writes, so they can be shown on the windshield.

``system.cpu_temp_c`` reads the Pi thermal zone (absent on dev machines).
"""

from __future__ import annotations

import asyncio
import shutil
import socket
from pathlib import Path

from ..core.provider import DataProvider

CHECK_PERIOD_S = 10
PROBE_ADDR = ("1.1.1.1", 53)
PROBE_TIMEOUT_S = 3
THERMAL_ZONE = Path("/sys/class/thermal/thermal_zone0/temp")
AP_CONNECTION = "hud-ap"
AP_ADDRESS = "10.42.0.1"  # NetworkManager's default for ipv4.method=shared


def probe_online() -> bool:
    try:
        with socket.create_connection(PROBE_ADDR, timeout=PROBE_TIMEOUT_S):
            return True
    except OSError:
        return False


def lan_address() -> str | None:
    """Primary LAN IPv4 (no packets sent — UDP connect just picks a route)."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("10.255.255.255", 1))
            ip = s.getsockname()[0]
            return None if ip.startswith("127.") else ip
    except OSError:
        return None


async def ap_active() -> bool:
    if not shutil.which("nmcli"):
        return False
    try:
        proc = await asyncio.create_subprocess_exec(
            "nmcli", "-t", "-f", "NAME", "connection", "show", "--active",
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL,
        )
        out, _ = await asyncio.wait_for(proc.communicate(), timeout=5)
    except (OSError, asyncio.TimeoutError):
        return False
    return AP_CONNECTION in out.decode(errors="replace").splitlines()


class SystemProvider(DataProvider):
    name = "system"

    async def run(self) -> None:
        port = int(self.config.get("server.port", 8000))
        while True:
            online = await asyncio.to_thread(probe_online)
            self.bus.publish("net.online", online)

            active = await ap_active()
            host = AP_ADDRESS if active else (lan_address() or "hud.local")
            self.bus.publish("net.ap", {
                "active": active,
                "ssid": self.config.get("wifi_ap.ssid"),
                "password": self.config.get("wifi_ap.password"),
                "url": f"http://{host}:{port}/settings",
            })

            if THERMAL_ZONE.exists():
                millideg = int(THERMAL_ZONE.read_text().strip())
                self.bus.publish("system.cpu_temp_c", round(millideg / 1000, 1))

            await asyncio.sleep(CHECK_PERIOD_S)
