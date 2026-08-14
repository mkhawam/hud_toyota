"""Speed-limit provider: GPS fix → current road's limit, fully offline.

Uses the prebuilt road DB (scripts/build_speedlimits.py) and the RoadMatcher.
On every ``gps.position`` fix (heading/speed read from the bus last-value
cache) it publishes:

    road.speed_limit_kph   float | None   — plain numeric for alert rules
    road.limit             {limit_kph, limit_mph, estimated, highway, name} | None

``estimated`` means the OSM way had no maxspeed tag and an NJ statutory
default was applied — the widget marks those with "~".

A missing DB file is a clean stop (status error, no restart spam): it won't
appear until someone runs the builder and deploys the file.
"""

from __future__ import annotations

import logging
from pathlib import Path

from ..core.provider import DataProvider
from ..roads.db import RoadDB
from ..roads.matcher import RoadMatcher
from ..roads.maxspeed import MPH_TO_KPH, resolve_limit

log = logging.getLogger(__name__)


class SpeedLimitProvider(DataProvider):
    name = "speedlimit"

    async def run(self) -> None:
        db_path = self.config.get("providers.speedlimit.db", "data/speedlimits-nj.sqlite")
        if not Path(db_path).exists():
            log.warning("speed-limit DB missing: %s — run scripts/build_speedlimits.py", db_path)
            self._set_status("error", detail=f"missing {db_path}")
            return  # clean stop; a missing file won't fix itself

        defaults = self.config.get("providers.speedlimit.defaults_mph")

        db = RoadDB(db_path, readonly=True)
        matcher = RoadMatcher(db)
        sub = self.bus.subscribe("gps.position")
        try:
            async for msg in sub:
                fix = msg.value
                if not isinstance(fix, dict):
                    continue
                heading = self._snap("gps.heading")
                speed = self._snap("gps.speed_kph")
                # inline query: ~1-3 ms per fix at 1 Hz — no thread needed
                m = matcher.match(fix["lat"], fix["lon"], heading, speed)
                if m is None:
                    self.bus.publish("road.speed_limit_kph", None)
                    self.bus.publish("road.limit", None)
                    continue
                limit_kph, estimated = resolve_limit(m.maxspeed_kph, m.highway, defaults)
                self.bus.publish("road.speed_limit_kph", limit_kph)
                self.bus.publish(
                    "road.limit",
                    None
                    if limit_kph is None
                    else {
                        "limit_kph": limit_kph,
                        "limit_mph": round(limit_kph / MPH_TO_KPH),
                        "estimated": estimated,
                        "highway": m.highway,
                        "name": m.name,
                    },
                )
        finally:
            self.bus.unsubscribe(sub)
            db.close()

    def _snap(self, topic: str):
        msg = self.bus.snapshot(topic).get(topic)
        if msg is None or not isinstance(msg.value, (int, float)):
            return None
        return float(msg.value)
