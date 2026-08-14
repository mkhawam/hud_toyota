"""Map-matching: GPS fix → the road you're on (pure logic, no asyncio).

Score = point-to-way distance + a bearing penalty (a perpendicular road
scores up to +20 m vs a parallel one), with hysteresis so the match doesn't
flap at intersections: the incumbent way sticks unless a challenger beats
it clearly for consecutive fixes, and short candidate droughts (overpasses,
GPS jitter) coast on the last match before honestly returning None.

Geometry is equirectangular meters centered on the fix — sub-centimeter
error at the 35 m search scale.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .db import RoadDB, unpack_coords

M_PER_DEG_LAT = 111_320.0


@dataclass
class Match:
    way_id: int
    highway: str
    maxspeed_kph: float | None
    name: str | None
    dist_m: float
    bearing_deg: float
    score: float = 0.0


class RoadMatcher:
    SEARCH_M = 35.0
    BEARING_PENALTY_M = 20.0
    MIN_HEADING_KPH = 10.0
    STICKY_MARGIN_M = 8.0
    SWITCH_FIXES = 2
    HOLD_FIXES = 3

    def __init__(self, db: RoadDB) -> None:
        self.db = db
        self._current: Match | None = None
        self._pending = 0
        self._misses = 0

    # -- public ------------------------------------------------------------

    def match(
        self,
        lat: float,
        lon: float,
        heading: float | None,
        speed_kph: float | None,
    ) -> Match | None:
        candidates = self._candidates(lat, lon)
        if not candidates:
            self._misses += 1
            if self._misses <= self.HOLD_FIXES:
                return self._current  # coast through a short drought
            self._current = None
            self._pending = 0
            return None
        self._misses = 0

        for c in candidates:
            c.score = c.dist_m + self._bearing_penalty(heading, c.bearing_deg, speed_kph)
        best = min(candidates, key=lambda c: c.score)

        incumbent = None
        if self._current is not None:
            incumbent = next((c for c in candidates if c.way_id == self._current.way_id), None)

        if incumbent is None or best.way_id == incumbent.way_id:
            self._current = best
            self._pending = 0
        elif incumbent.score - best.score > self.STICKY_MARGIN_M:
            self._pending += 1
            if self._pending >= self.SWITCH_FIXES:
                self._current = best
                self._pending = 0
            else:
                self._current = incumbent
        else:
            self._current = incumbent
            self._pending = 0
        return self._current

    # -- internals ----------------------------------------------------------

    def _bearing_penalty(
        self, heading: float | None, seg_bearing: float, speed_kph: float | None
    ) -> float:
        if heading is None or (speed_kph or 0.0) < self.MIN_HEADING_KPH:
            return 0.0
        diff = abs((heading - seg_bearing + 90.0) % 180.0 - 90.0)  # undirected 0..90
        return diff / 90.0 * self.BEARING_PENALTY_M

    def _candidates(self, lat: float, lon: float) -> list[Match]:
        dlat = self.SEARCH_M / M_PER_DEG_LAT
        dlon = self.SEARCH_M / (M_PER_DEG_LAT * math.cos(math.radians(lat)))
        rows = self.db.query_bbox(lat - dlat, lat + dlat, lon - dlon, lon + dlon)

        cos_lat = math.cos(math.radians(lat))
        best_by_way: dict[int, Match] = {}
        for way_id, highway, maxspeed, name, blob in rows:
            pts = unpack_coords(blob)
            dist, bearing = self._nearest_segment(lat, lon, cos_lat, pts)
            if dist > self.SEARCH_M:
                continue
            cur = best_by_way.get(way_id)
            if cur is None or dist < cur.dist_m:
                best_by_way[way_id] = Match(
                    way_id=way_id, highway=highway, maxspeed_kph=maxspeed,
                    name=name, dist_m=dist, bearing_deg=bearing,
                )
        return list(best_by_way.values())

    @staticmethod
    def _nearest_segment(
        lat: float, lon: float, cos_lat: float, pts: list[tuple[float, float]]
    ) -> tuple[float, float]:
        """(min distance in meters, bearing of the nearest segment)."""
        best_d = math.inf
        best_bearing = 0.0
        for (lat1, lon1), (lat2, lon2) in zip(pts, pts[1:]):
            x1 = (lon1 - lon) * M_PER_DEG_LAT * cos_lat
            y1 = (lat1 - lat) * M_PER_DEG_LAT
            x2 = (lon2 - lon) * M_PER_DEG_LAT * cos_lat
            y2 = (lat2 - lat) * M_PER_DEG_LAT
            dx, dy = x2 - x1, y2 - y1
            seg_len_sq = dx * dx + dy * dy
            if seg_len_sq == 0:
                d = math.hypot(x1, y1)
            else:
                t = max(0.0, min(1.0, -(x1 * dx + y1 * dy) / seg_len_sq))
                d = math.hypot(x1 + t * dx, y1 + t * dy)
            if d < best_d:
                best_d = d
                best_bearing = math.degrees(math.atan2(dx, dy)) % 360.0
        return best_d, best_bearing
