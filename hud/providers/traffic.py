"""Traffic provider — TomTom flow-segment data (free tier, needs an API key).

Asks "how fast is traffic moving on the road nearest to me vs free-flow"
at the current GPS position (falls back to the configured home location).
Only started when an API key is configured.

Published: ``traffic.flow`` =
    {current_kph, freeflow_kph, ratio, road_closed, fetched_at}
ratio 1.0 = flowing freely, 0.5 = half of free-flow speed.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

from ..core.provider import DataProvider

API = "https://api.tomtom.com/traffic/services/4/flowSegmentData/absolute/10/json"
RETRY_S = 120


def parse_flow(payload: dict[str, Any]) -> dict[str, Any]:
    seg = payload["flowSegmentData"]
    current = float(seg["currentSpeed"])
    freeflow = float(seg["freeFlowSpeed"])
    return {
        "current_kph": current,
        "freeflow_kph": freeflow,
        "ratio": round(current / freeflow, 2) if freeflow > 0 else 1.0,
        "road_closed": bool(seg.get("roadClosure", False)),
    }


class TrafficProvider(DataProvider):
    name = "traffic"

    def _location(self) -> tuple[float, float]:
        fix = self.bus.snapshot("gps.position").get("gps.position")
        if fix and isinstance(fix.value, dict):
            return fix.value["lat"], fix.value["lon"]
        return (
            float(self.config.get("location.lat", 40.4862)),
            float(self.config.get("location.lon", -74.4518)),
        )

    async def run(self) -> None:
        import httpx

        key = self.config.get("providers.traffic.tomtom_key")
        if not key:
            raise RuntimeError("traffic provider started without providers.traffic.tomtom_key")
        poll_s = float(self.config.get("providers.traffic.poll_minutes", 5)) * 60

        async with httpx.AsyncClient(timeout=10) as client:
            while True:
                lat, lon = self._location()
                try:
                    resp = await client.get(API, params={"point": f"{lat:.5f},{lon:.5f}", "key": key})
                    resp.raise_for_status()
                    flow = parse_flow(resp.json())
                except Exception:
                    await asyncio.sleep(RETRY_S)
                    continue

                flow["fetched_at"] = time.time()
                self.bus.publish("traffic.flow", flow)
                await asyncio.sleep(poll_s)
