"""Road database: schema + coordinate packing shared by the PC-side OSM
builder, the runtime matcher, and the tests (tests build tiny DBs with the
same helpers the builder uses — no .pbf fixtures needed).

Layout: driveable ways (with their raw maxspeed, NULL when untagged) and
way *chunks* (≤16 points) whose bounding boxes live in an R-tree. Chunked
polylines keep the R-tree ~10× smaller than per-segment entries while
candidate sets stay small enough for exact point-to-segment math.
"""

from __future__ import annotations

import sqlite3
import struct
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS ways (
  id INTEGER PRIMARY KEY,
  highway TEXT NOT NULL,
  maxspeed_kph REAL,
  name TEXT
);
CREATE VIRTUAL TABLE IF NOT EXISTS chunk_idx USING rtree(
  id, min_lat, max_lat, min_lon, max_lon
);
CREATE TABLE IF NOT EXISTS chunks (
  id INTEGER PRIMARY KEY,
  way_id INTEGER NOT NULL REFERENCES ways(id),
  coords BLOB NOT NULL
);
"""

MAX_CHUNK_POINTS = 16
MAX_CHUNK_LEN_M = 400.0
_SCALE = 1e7


def pack_coords(points: list[tuple[float, float]]) -> bytes:
    flat = [round(v * _SCALE) for lat, lon in points for v in (lat, lon)]
    return struct.pack(f"<{len(flat)}i", *flat)


def unpack_coords(blob: bytes) -> list[tuple[float, float]]:
    flat = struct.unpack(f"<{len(blob) // 4}i", blob)
    return [(flat[i] / _SCALE, flat[i + 1] / _SCALE) for i in range(0, len(flat), 2)]


def split_chunks(
    points: list[tuple[float, float]],
    max_pts: int = MAX_CHUNK_POINTS,
    max_len_m: float = MAX_CHUNK_LEN_M,
) -> list[list[tuple[float, float]]]:
    """Split a way polyline into overlapping-endpoint chunks bounded by
    point count and rough length (consecutive chunks share one point so
    no segment is lost)."""
    if len(points) < 2:
        return []
    chunks: list[list[tuple[float, float]]] = []
    cur = [points[0]]
    cur_len = 0.0
    for prev, pt in zip(points, points[1:]):
        # equirectangular estimate, fine for a length cap
        import math

        dy = (pt[0] - prev[0]) * 111_320.0
        dx = (pt[1] - prev[1]) * 111_320.0 * math.cos(math.radians(prev[0]))
        cur_len += (dx * dx + dy * dy) ** 0.5
        cur.append(pt)
        if len(cur) >= max_pts or cur_len >= max_len_m:
            chunks.append(cur)
            cur = [pt]
            cur_len = 0.0
    if len(cur) >= 2:
        chunks.append(cur)
    return chunks


class RoadDB:
    """Thin wrapper used by both the builder (writes) and matcher (reads)."""

    def __init__(self, path: str | Path, readonly: bool = False) -> None:
        if readonly:
            self.db = sqlite3.connect(f"file:{Path(path).as_posix()}?mode=ro", uri=True)
            self.db.execute("PRAGMA query_only=1")
            self.db.execute("PRAGMA mmap_size=100000000")
        else:
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            self.db = sqlite3.connect(str(path))
            self.db.executescript(SCHEMA)

    def close(self) -> None:
        self.db.close()

    # -- writing (builder + tests) ----------------------------------------

    def insert_way(
        self,
        way_id: int,
        highway: str,
        maxspeed_kph: float | None,
        name: str | None,
        points: list[tuple[float, float]],
    ) -> None:
        self.db.execute(
            "INSERT OR REPLACE INTO ways (id, highway, maxspeed_kph, name) VALUES (?,?,?,?)",
            (way_id, highway, maxspeed_kph, name),
        )
        for chunk in split_chunks(points):
            lats = [p[0] for p in chunk]
            lons = [p[1] for p in chunk]
            cur = self.db.execute(
                "INSERT INTO chunks (way_id, coords) VALUES (?, ?)",
                (way_id, pack_coords(chunk)),
            )
            self.db.execute(
                "INSERT INTO chunk_idx (id, min_lat, max_lat, min_lon, max_lon) VALUES (?,?,?,?,?)",
                (cur.lastrowid, min(lats), max(lats), min(lons), max(lons)),
            )

    def set_meta(self, key: str, value: str) -> None:
        self.db.execute("INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)", (key, value))

    def commit(self) -> None:
        self.db.commit()

    def finalize(self) -> None:
        self.db.commit()
        self.db.execute("ANALYZE")
        self.db.execute("VACUUM")
        self.db.commit()

    # -- reading (matcher) -------------------------------------------------

    def query_bbox(
        self, min_lat: float, max_lat: float, min_lon: float, max_lon: float
    ) -> list[tuple[int, str, float | None, str | None, bytes]]:
        """Chunks whose bbox intersects the query box, joined to their way:
        (way_id, highway, maxspeed_kph, name, coords_blob)."""
        rows = self.db.execute(
            "SELECT w.id, w.highway, w.maxspeed_kph, w.name, c.coords"
            " FROM chunk_idx i JOIN chunks c ON c.id = i.id JOIN ways w ON w.id = c.way_id"
            " WHERE i.max_lat >= ? AND i.min_lat <= ? AND i.max_lon >= ? AND i.min_lon <= ?",
            (min_lat, max_lat, min_lon, max_lon),
        ).fetchall()
        return rows
