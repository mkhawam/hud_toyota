"""SQLite drive log (SQLAlchemy ORM, WAL).

One row per second while driving; a drives table with per-drive stats.
Deployment note: with overlayfs enabled the root FS is read-only — point
``drivelog.data_dir`` at a writable mount (USB stick / second partition).
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, delete, event, func, select, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column


class Base(DeclarativeBase):
    pass


class Drive(Base):
    __tablename__ = "drives"
    __table_args__ = {"sqlite_autoincrement": True}

    id: Mapped[int] = mapped_column(primary_key=True)
    started_at: Mapped[float]
    ended_at: Mapped[float | None]
    distance_km: Mapped[float] = mapped_column(default=0.0, server_default="0")
    fuel_l: Mapped[float] = mapped_column(default=0.0, server_default="0")
    max_speed_kph: Mapped[float] = mapped_column(default=0.0, server_default="0")
    avg_moving_kph: Mapped[float] = mapped_column(default=0.0, server_default="0")
    sample_count: Mapped[int] = mapped_column(default=0, server_default="0")
    odo_start_km: Mapped[float | None]
    odo_end_km: Mapped[float | None]


class Sample(Base):
    """Keyed by (drive_id, ts) — samples arrive at 1 Hz, so wall-clock time
    within a drive is naturally unique; no surrogate id column needed."""

    __tablename__ = "samples"

    drive_id: Mapped[int] = mapped_column(primary_key=True)
    ts: Mapped[float] = mapped_column(primary_key=True)
    speed_kph: Mapped[float | None]
    rpm: Mapped[float | None]
    coolant_c: Mapped[float | None]
    fuel_pct: Mapped[float | None]
    lat: Mapped[float | None]
    lon: Mapped[float | None]
    limit_kph: Mapped[float | None]
    steer_deg: Mapped[float | None]


SAMPLE_COLUMNS = (
    "speed_kph", "rpm", "coolant_c", "fuel_pct", "lat", "lon", "limit_kph", "steer_deg",
)

# Columns added after first release — applied to pre-existing DBs on open.
# (create_all only builds missing tables; it never alters existing ones.)
MIGRATIONS = (
    "ALTER TABLE samples ADD COLUMN steer_deg REAL",
    "ALTER TABLE drives ADD COLUMN odo_start_km REAL",
    "ALTER TABLE drives ADD COLUMN odo_end_km REAL",
)


class DriveStore:
    def __init__(self, path: str | Path) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.engine = create_engine(f"sqlite:///{Path(path).as_posix()}")
        event.listen(
            self.engine,
            "connect",
            lambda dbapi_conn, _: dbapi_conn.execute("PRAGMA journal_mode=WAL"),
        )
        Base.metadata.create_all(self.engine)
        for migration in MIGRATIONS:
            try:
                with self.engine.begin() as conn:
                    conn.execute(text(migration))
            except OperationalError:
                pass  # column already exists (fresh schema or applied before)

    def close(self) -> None:
        self.engine.dispose()

    # -- writing ----------------------------------------------------------

    def start_drive(self, ts: float) -> int:
        with Session(self.engine) as s, s.begin():
            drive = Drive(started_at=ts)
            s.add(drive)
            s.flush()
            return drive.id

    def add_sample(self, drive_id: int, ts: float, values: dict[str, Any]) -> None:
        with Session(self.engine) as s, s.begin():
            s.add(Sample(drive_id=drive_id, ts=ts,
                         **{c: values.get(c) for c in SAMPLE_COLUMNS}))

    def end_drive(self, drive_id: int, ts: float, stats: dict[str, Any]) -> None:
        with Session(self.engine) as s, s.begin():
            drive = s.get(Drive, drive_id)
            if drive is None:
                return
            drive.ended_at = ts
            drive.distance_km = round(stats.get("distance_km", 0.0), 2)
            drive.fuel_l = round(stats.get("fuel_l", 0.0), 2)
            drive.max_speed_kph = round(stats.get("max_speed_kph", 0.0), 1)
            drive.avg_moving_kph = round(stats.get("avg_moving_kph", 0.0), 1)
            drive.sample_count = s.scalar(
                select(func.count()).select_from(Sample).where(Sample.drive_id == drive_id)
            )
            drive.odo_start_km = stats.get("odo_start_km")
            drive.odo_end_km = stats.get("odo_end_km")

    def prune(self, keep_days: float, now: float | None = None) -> int:
        """Delete drives older than keep_days; returns drives removed."""
        cutoff = (now if now is not None else time.time()) - keep_days * 86400
        with Session(self.engine) as s, s.begin():
            old = s.scalars(select(Drive.id).where(Drive.started_at < cutoff)).all()
            if old:
                s.execute(delete(Sample).where(Sample.drive_id.in_(old)))
                s.execute(delete(Drive).where(Drive.id.in_(old)))
            return len(old)

    # -- reading ----------------------------------------------------------

    def list_drives(self, limit: int = 50) -> list[dict[str, Any]]:
        with Session(self.engine) as s:
            rows = s.execute(
                select(Drive.__table__).order_by(Drive.started_at.desc()).limit(limit)
            ).mappings()
            return [dict(r) for r in rows]

    def get_samples(self, drive_id: int, max_points: int = 500) -> list[dict[str, Any]]:
        with Session(self.engine) as s:
            count = s.scalar(
                select(func.count()).select_from(Sample).where(Sample.drive_id == drive_id)
            )
            stride = max(1, count // max_points)
            rows = s.execute(
                select(Sample.__table__).where(Sample.drive_id == drive_id).order_by(Sample.ts)
            ).mappings().all()
            return [dict(r) for r in rows[::stride]]


class SessionTracker:
    """Decides when a drive starts and ends. Pure — no clock of its own."""

    def __init__(self, idle_end_s: float = 600.0) -> None:
        self.idle_end_s = idle_end_s
        self.driving = False
        self._last_active: float | None = None

    def update(self, now: float, engine_on: bool) -> str | None:
        """Returns "start", "end", or None."""
        if engine_on:
            self._last_active = now
            if not self.driving:
                self.driving = True
                return "start"
            return None
        if self.driving and self._last_active is not None and now - self._last_active > self.idle_end_s:
            self.driving = False
            return "end"
        return None
