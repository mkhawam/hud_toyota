"""Weather provider — Open-Meteo (free, no API key).

Location comes from the last GPS fix when available (bus last-value cache),
else the configured home location. Successful fetches are cached to disk so
a cold boot with no internet still shows the last known weather; the widget
displays the fetch age so stale data is honest.

Published: ``weather.current`` =
    {temp_c, feels_c, code, wind_kph, is_day, fetched_at}
``code`` is a WMO weather code — mapped to a label on the frontend.
"""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from typing import Any

from ..core.provider import DataProvider

API = "https://api.open-meteo.com/v1/forecast"
CURRENT_FIELDS = "temperature_2m,apparent_temperature,weather_code,wind_speed_10m,is_day"
RETRY_S = 120  # after a failed fetch (offline) — cheap, it's one small request


def parse_current(payload: dict[str, Any]) -> dict[str, Any]:
    cur = payload["current"]
    return {
        "temp_c": float(cur["temperature_2m"]),
        "feels_c": float(cur["apparent_temperature"]),
        "code": int(cur["weather_code"]),
        "wind_kph": float(cur["wind_speed_10m"]),
        "is_day": bool(cur["is_day"]),
    }


class WeatherProvider(DataProvider):
    name = "weather"

    @property
    def cache_file(self) -> Path:
        return Path(self.config.get("cache_dir", "cache")) / "weather.json"

    def _location(self) -> tuple[float, float]:
        fix = self.bus.snapshot("gps.position").get("gps.position")
        if fix and isinstance(fix.value, dict):
            return fix.value["lat"], fix.value["lon"]
        return (
            float(self.config.get("location.lat", 40.4862)),
            float(self.config.get("location.lon", -74.4518)),
        )

    def _load_cache(self) -> dict[str, Any] | None:
        try:
            return json.loads(self.cache_file.read_text())
        except (OSError, ValueError):
            return None

    def _save_cache(self, data: dict[str, Any]) -> None:
        try:
            self.cache_file.parent.mkdir(parents=True, exist_ok=True)
            self.cache_file.write_text(json.dumps(data))
        except OSError:
            pass  # read-only root or full disk — cache is best-effort

    async def run(self) -> None:
        import httpx

        poll_s = float(self.config.get("providers.weather.poll_minutes", 10)) * 60

        cached = self._load_cache()
        if cached:
            self.bus.publish("weather.current", cached)

        async with httpx.AsyncClient(timeout=10) as client:
            while True:
                lat, lon = self._location()
                try:
                    resp = await client.get(
                        API,
                        params={
                            "latitude": f"{lat:.4f}",
                            "longitude": f"{lon:.4f}",
                            "current": CURRENT_FIELDS,
                        },
                    )
                    resp.raise_for_status()
                    current = parse_current(resp.json())
                except Exception:
                    await asyncio.sleep(RETRY_S)  # offline — keep last published value
                    continue

                current["fetched_at"] = time.time()
                self.bus.publish("weather.current", current)
                self._save_cache(current)
                await asyncio.sleep(poll_s)
