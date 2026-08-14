"""System provider: connectivity + Pi health.

``net.online`` is a cheap TCP connect to a public DNS server every 10 s —
it doesn't care whether the route is the phone hotspot or an LTE dongle,
which is exactly the point: internet widgets key off this one topic and
degrade gracefully when the car is offline.

``system.cpu_temp_c`` reads the Pi thermal zone (absent on dev machines).
"""

from __future__ import annotations

import asyncio
import socket
from pathlib import Path

from ..core.provider import DataProvider

CHECK_PERIOD_S = 10
PROBE_ADDR = ("1.1.1.1", 53)
PROBE_TIMEOUT_S = 3
THERMAL_ZONE = Path("/sys/class/thermal/thermal_zone0/temp")


def probe_online() -> bool:
    try:
        with socket.create_connection(PROBE_ADDR, timeout=PROBE_TIMEOUT_S):
            return True
    except OSError:
        return False


class SystemProvider(DataProvider):
    name = "system"

    async def run(self) -> None:
        while True:
            online = await asyncio.to_thread(probe_online)
            self.bus.publish("net.online", online)

            if THERMAL_ZONE.exists():
                millideg = int(THERMAL_ZONE.read_text().strip())
                self.bus.publish("system.cpu_temp_c", round(millideg / 1000, 1))

            await asyncio.sleep(CHECK_PERIOD_S)
