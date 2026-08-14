"""GPS provider — speaks gpsd's JSON protocol directly over TCP.

No client library needed: connect to gpsd (localhost:2947), send a WATCH
command, and parse the TPV (time-position-velocity) stream. Publishes:

    gps.position   {lat, lon}
    gps.speed_kph  float   (GPS-derived — useful cross-check vs wheel speed)
    gps.heading    float   (degrees true)

Only reports with a 2D/3D fix (mode >= 2) are published.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from ..core.provider import DataProvider

WATCH_CMD = b'?WATCH={"enable":true,"json":true}\n'
MPS_TO_KPH = 3.6


def parse_tpv(line: str) -> dict[str, Any] | None:
    """One gpsd JSON line → normalized dict, or None if not a usable fix."""
    try:
        msg = json.loads(line)
    except ValueError:
        return None
    if msg.get("class") != "TPV" or msg.get("mode", 0) < 2:
        return None
    if "lat" not in msg or "lon" not in msg:
        return None
    out: dict[str, Any] = {"lat": float(msg["lat"]), "lon": float(msg["lon"])}
    if "speed" in msg:
        out["speed_kph"] = round(float(msg["speed"]) * MPS_TO_KPH, 1)
    if "track" in msg:
        out["heading"] = round(float(msg["track"]), 1)
    return out


class GpsProvider(DataProvider):
    name = "gps"

    async def run(self) -> None:
        host = self.config.get("providers.gps.host", "localhost")
        port = int(self.config.get("providers.gps.port", 2947))

        reader, writer = await asyncio.open_connection(host, port)
        try:
            writer.write(WATCH_CMD)
            await writer.drain()
            while True:
                line = await asyncio.wait_for(reader.readline(), timeout=30)
                if not line:
                    raise ConnectionError("gpsd closed the connection")
                fix = parse_tpv(line.decode("utf-8", errors="replace"))
                if fix is None:
                    continue
                self.bus.publish("gps.position", {"lat": fix["lat"], "lon": fix["lon"]})
                if "speed_kph" in fix:
                    self.bus.publish("gps.speed_kph", fix["speed_kph"])
                if "heading" in fix:
                    self.bus.publish("gps.heading", fix["heading"])
        finally:
            writer.close()
