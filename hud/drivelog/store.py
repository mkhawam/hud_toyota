"""SQLite drive log (stdlib sqlite3, WAL).

One row per second while driving; a drives table with per-drive stats.
Deployment note: with overlayfs enabled the root FS is read-only — point
``drivelog.data_dir`` at a writable mount (USB stick / second partition).
"""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from typing import Any

SCHEMA = """
CREATE TABLE IF NOT EXISTS drives (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  started_at REAL NOT NULL,
  ended_at REAL,
  distance_km REAL NOT NULL DEFAULT 0,
  fuel_l REAL NOT NULL DEFAULT 0,
  max_speed_kph REAL NOT NULL DEFAULT 0,
  avg_moving_kph REAL NOT NULL DEFAULT 0,
  sample_count INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS samples (
  drive_id INTEGER NOT NULL,
  ts REAL NOT NULL,
  speed_kph REAL, rpm REAL, coolant_c REAL, fuel_pct REAL,
  lat REAL, lon REAL, limit_kph REAL, steer_deg REAL
);
CREATE INDEX IF NOT EXISTS idx_samples_drive ON samples(drive_id);
"""

SAMPLE_COLUMNS = (
    "speed_kph", "rpm", "coolant_c", "fuel_pct", "lat", "lon", "limit_kph", "steer_deg",
)

# Columns added after first release — applied to pre-existing DBs on open.
MIGRATIONS = (
    "ALTER TABLE samples ADD COLUMN steer_deg REAL",
    "ALTER TABLE drives ADD COLUMN odo_start_km REAL",
    "ALTER TABLE drives ADD COLUMN odo_end_km REAL",
)


class DriveStore:
    def __init__(self, path: str | Path) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(path))
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.executescript(SCHEMA)
        for migration in MIGRATIONS:
            try:
                self.db.execute(migration)
            except sqlite3.OperationalError:
                pass  # column already exists (fresh schema or applied before)
        self.db.commit()

    def close(self) -> None:
        self.db.close()

    # -- writing ----------------------------------------------------------

    def start_drive(self, ts: float) -> int:
        cur = self.db.execute("INSERT INTO drives (started_at) VALUES (?)", (ts,))
        self.db.commit()
        return int(cur.lastrowid)

    def add_sample(self, drive_id: int, ts: float, values: dict[str, Any]) -> None:
        cols = ", ".join(SAMPLE_COLUMNS)
        holes = ", ".join("?" * len(SAMPLE_COLUMNS))
        self.db.execute(
            f"INSERT INTO samples (drive_id, ts, {cols}) VALUES (?, ?, {holes})",
            (drive_id, ts, *(values.get(c) for c in SAMPLE_COLUMNS)),
        )
        self.db.commit()

    def end_drive(self, drive_id: int, ts: float, stats: dict[str, Any]) -> None:
        count = self.db.execute(
            "SELECT COUNT(*) FROM samples WHERE drive_id = ?", (drive_id,)
        ).fetchone()[0]
        self.db.execute(
            "UPDATE drives SET ended_at=?, distance_km=?, fuel_l=?, max_speed_kph=?,"
            " avg_moving_kph=?, sample_count=?, odo_start_km=?, odo_end_km=? WHERE id=?",
            (
                ts,
                round(stats.get("distance_km", 0.0), 2),
                round(stats.get("fuel_l", 0.0), 2),
                round(stats.get("max_speed_kph", 0.0), 1),
                round(stats.get("avg_moving_kph", 0.0), 1),
                count,
                stats.get("odo_start_km"),
                stats.get("odo_end_km"),
                drive_id,
            ),
        )
        self.db.commit()

    def prune(self, keep_days: float, now: float | None = None) -> int:
        """Delete drives older than keep_days; returns drives removed."""
        cutoff = (now if now is not None else time.time()) - keep_days * 86400
        old = [r[0] for r in self.db.execute("SELECT id FROM drives WHERE started_at < ?", (cutoff,))]
        if old:
            marks = ",".join("?" * len(old))
            self.db.execute(f"DELETE FROM samples WHERE drive_id IN ({marks})", old)
            self.db.execute(f"DELETE FROM drives WHERE id IN ({marks})", old)
            self.db.commit()
        return len(old)

    # -- reading ----------------------------------------------------------

    def list_drives(self, limit: int = 50) -> list[dict[str, Any]]:
        rows = self.db.execute(
            "SELECT * FROM drives ORDER BY started_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]

    def get_samples(self, drive_id: int, max_points: int = 500) -> list[dict[str, Any]]:
        count = self.db.execute(
            "SELECT COUNT(*) FROM samples WHERE drive_id = ?", (drive_id,)
        ).fetchone()[0]
        stride = max(1, count // max_points)
        rows = self.db.execute(
            "SELECT * FROM samples WHERE drive_id = ? ORDER BY ts", (drive_id,)
        ).fetchall()
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
