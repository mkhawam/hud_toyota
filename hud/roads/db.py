"""Road database: schema + coordinate packing shared by the PC-side OSM
builder, the runtime matcher, and the tests (tests build tiny DBs with the
same helpers the builder uses — no .pbf fixtures needed).

Layout: driveable ways (with their raw maxspeed, NULL when untagged) and
way *chunks* (≤16 points) whose bounding boxes live in an R-tree. Chunked
polylines keep the R-tree ~10× smaller than per-segment entries while
candidate sets stay small enough for exact point-to-segment math.

SQLAlchemy throughout, with one exception: the R-tree is a SQLite virtual
table, which declarative models can't express, so it lives in a Core Table
(created by literal DDL, queried like any other table).
"""

from __future__ import annotations

import math
import struct
from pathlib import Path

from sqlalchemy import (
    Column,
    Float,
    ForeignKey,
    Integer,
    MetaData,
    Table,
    create_engine,
    event,
    insert,
    select,
    text,
)
from sqlalchemy.dialects.sqlite import insert as sqlite_upsert
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class MetaEntry(Base):
    __tablename__ = "meta"

    key: Mapped[str] = mapped_column(primary_key=True)
    value: Mapped[str | None]


class Way(Base):
    __tablename__ = "ways"

    id: Mapped[int] = mapped_column(primary_key=True)
    highway: Mapped[str]
    maxspeed_kph: Mapped[float | None]
    name: Mapped[str | None]


class Chunk(Base):
    __tablename__ = "chunks"

    id: Mapped[int] = mapped_column(primary_key=True)
    way_id: Mapped[int] = mapped_column(ForeignKey("ways.id"))
    coords: Mapped[bytes]


# Kept out of Base.metadata so create_all never emits a plain CREATE TABLE
# for it — the real thing is the virtual table below.
chunk_idx = Table(
    "chunk_idx",
    MetaData(),
    Column("id", Integer, primary_key=True),
    Column("min_lat", Float),
    Column("max_lat", Float),
    Column("min_lon", Float),
    Column("max_lon", Float),
)

_RTREE_DDL = text(
    "CREATE VIRTUAL TABLE IF NOT EXISTS chunk_idx"
    " USING rtree(id, min_lat, max_lat, min_lon, max_lon)"
)

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


def _readonly_pragmas(dbapi_conn, _record) -> None:
    dbapi_conn.execute("PRAGMA query_only=1")
    dbapi_conn.execute("PRAGMA mmap_size=100000000")


class RoadDB:
    """Thin wrapper used by both the builder (writes) and matcher (reads)."""

    def __init__(self, path: str | Path, readonly: bool = False) -> None:
        if readonly:
            self._engine = create_engine(
                f"sqlite:///file:{Path(path).as_posix()}?mode=ro&uri=true"
            )
            event.listen(self._engine, "connect", _readonly_pragmas)
        else:
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            self._engine = create_engine(f"sqlite:///{Path(path).as_posix()}")
            Base.metadata.create_all(self._engine)
            with self._engine.begin() as conn:
                conn.execute(_RTREE_DDL)
        self._conn = self._engine.connect()

    def close(self) -> None:
        self._conn.close()
        self._engine.dispose()

    # -- writing (builder + tests) ----------------------------------------

    def insert_way(
        self,
        way_id: int,
        highway: str,
        maxspeed_kph: float | None,
        name: str | None,
        points: list[tuple[float, float]],
    ) -> None:
        upsert = sqlite_upsert(Way).values(
            id=way_id, highway=highway, maxspeed_kph=maxspeed_kph, name=name
        )
        self._conn.execute(
            upsert.on_conflict_do_update(
                index_elements=["id"],
                set_={
                    "highway": upsert.excluded.highway,
                    "maxspeed_kph": upsert.excluded.maxspeed_kph,
                    "name": upsert.excluded.name,
                },
            )
        )
        for chunk in split_chunks(points):
            lats = [p[0] for p in chunk]
            lons = [p[1] for p in chunk]
            chunk_id = self._conn.execute(
                insert(Chunk).values(way_id=way_id, coords=pack_coords(chunk))
            ).inserted_primary_key[0]
            self._conn.execute(
                chunk_idx.insert().values(
                    id=chunk_id,
                    min_lat=min(lats), max_lat=max(lats),
                    min_lon=min(lons), max_lon=max(lons),
                )
            )

    def set_meta(self, key: str, value: str) -> None:
        upsert = sqlite_upsert(MetaEntry).values(key=key, value=value)
        self._conn.execute(
            upsert.on_conflict_do_update(
                index_elements=["key"], set_={"value": upsert.excluded.value}
            )
        )

    def commit(self) -> None:
        self._conn.commit()

    def finalize(self) -> None:
        self._conn.commit()
        self._conn.execute(text("ANALYZE"))
        self._conn.commit()
        # VACUUM refuses to run inside a transaction, and SQLAlchemy
        # autobegins one on any execute — needs a driver-autocommit connection.
        with self._engine.connect().execution_options(
            isolation_level="AUTOCOMMIT"
        ) as conn:
            conn.execute(text("VACUUM"))

    # -- reading (matcher) -------------------------------------------------

    def query_bbox(
        self, min_lat: float, max_lat: float, min_lon: float, max_lon: float
    ) -> list[tuple[int, str, float | None, str | None, bytes]]:
        """Chunks whose bbox intersects the query box, joined to their way:
        (way_id, highway, maxspeed_kph, name, coords_blob)."""
        stmt = (
            select(Way.id, Way.highway, Way.maxspeed_kph, Way.name, Chunk.coords)
            .select_from(chunk_idx)
            .join(Chunk, Chunk.id == chunk_idx.c.id)
            .join(Way, Way.id == Chunk.way_id)
            .where(
                chunk_idx.c.max_lat >= min_lat,
                chunk_idx.c.min_lat <= max_lat,
                chunk_idx.c.max_lon >= min_lon,
                chunk_idx.c.min_lon <= max_lon,
            )
        )
        return [tuple(row) for row in self._conn.execute(stmt)]
