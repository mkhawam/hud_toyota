"""Drive recorder provider: 1 Hz telemetry rows while the engine runs.

Samples the bus last-value cache once a second (no per-message work), so
whatever mix of CAN/ELM327/GPS is currently publishing is what gets logged.
Values older than STALE_S are logged as NULL rather than repeating stale
readings. Per-drive stats reuse TripState's integration math.
"""

from __future__ import annotations

import asyncio
import time

from ..core.provider import DataProvider
from ..providers.trip import TripState
from .store import DriveStore, SessionTracker

STALE_S = 5.0
ENGINE_ON_RPM = 300


class DriveRecorder(DataProvider):
    name = "drivelog"

    async def run(self) -> None:
        db_path = self.config.get("drivelog.data_dir", "data")
        store = DriveStore(f"{db_path}/drives.db")
        store.prune(float(self.config.get("drivelog.keep_days", 90)))

        tracker = SessionTracker(idle_end_s=float(self.config.get("drivelog.idle_end_s", 600)))
        drive_id: int | None = None
        stats = TripState()
        max_speed = 0.0
        odo_start: float | None = None

        def fresh(topic: str, now: float):
            msg = self.bus.snapshot(topic).get(topic)
            if msg is None or now - msg.ts > STALE_S:
                return None
            return msg.value

        try:
            while True:
                await asyncio.sleep(1)
                now = time.time()
                rpm = fresh("vehicle.rpm", now)
                speed = fresh("vehicle.speed_kph", now)
                engine_on = (rpm or 0) > ENGINE_ON_RPM or (speed or 0) > 0.5

                event = tracker.update(now, engine_on)
                if event == "start":
                    drive_id = store.start_drive(now)
                    stats = TripState()
                    max_speed = 0.0
                    odo_start = fresh("vehicle.odometer_km", now)
                elif event == "end" and drive_id is not None:
                    store.end_drive(
                        drive_id, now,
                        self._stats_dict(stats, max_speed, odo_start,
                                         fresh("vehicle.odometer_km", now)),
                    )
                    drive_id = None

                if drive_id is not None and engine_on:
                    if speed is not None:
                        stats.on_speed(now, float(speed))
                        max_speed = max(max_speed, float(speed))
                    maf = fresh("vehicle.maf_gs", now)
                    if maf is not None:
                        stats.on_maf(now, float(maf))
                    fix = fresh("gps.position", now)
                    store.add_sample(
                        drive_id,
                        now,
                        {
                            "speed_kph": speed,
                            "rpm": rpm,
                            "coolant_c": fresh("vehicle.coolant_c", now),
                            "fuel_pct": fresh("vehicle.fuel_pct", now),
                            "lat": fix.get("lat") if isinstance(fix, dict) else None,
                            "lon": fix.get("lon") if isinstance(fix, dict) else None,
                            "limit_kph": fresh("road.speed_limit_kph", now),
                            "steer_deg": fresh("vehicle.steer_deg", now),
                        },
                    )
        finally:
            if drive_id is not None:
                now = time.time()
                store.end_drive(
                    drive_id, now,
                    self._stats_dict(stats, max_speed, odo_start,
                                     fresh("vehicle.odometer_km", now)),
                )
            store.close()

    @staticmethod
    def _stats_dict(
        stats: TripState,
        max_speed: float,
        odo_start: float | None = None,
        odo_end: float | None = None,
    ) -> dict:
        avg = stats.distance_km / (stats.moving_s / 3600) if stats.moving_s > 0 else 0.0
        return {
            "distance_km": stats.distance_km,
            "fuel_l": stats.fuel_l,
            "max_speed_kph": max_speed,
            "avg_moving_kph": avg,
            "odo_start_km": odo_start,
            "odo_end_km": odo_end,
        }
