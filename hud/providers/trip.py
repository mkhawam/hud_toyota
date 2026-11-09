"""Trip computer: distance, moving time, fuel, economy, 0-60 timer.

Integrates the vehicle stream between message timestamps (trapezoid rule):
distance from speed; fuel from the ECU's own fuel rate (PID 0x5E, L/h) when
the car reports it, else from MAF via the stoichiometric ratio (gasoline:
fuel g/s = MAF/14.7, /737 g/L → L/s, good to a few percent).

State survives restarts via cache/trip.json (best-effort, like the weather
cache); the trip auto-resets after `providers.trip.reset_hours` parked, and
manually via POST /api/trip/reset (which publishes ``trip.reset``).

Published (≤1 Hz): trip.distance_km, trip.time_s, trip.fuel_l,
trip.avg_lp100k, trip.instant_lp100k, trip.zero_sixty {last_s, best_s}.
Frontend converts to MPG/miles per the units config.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from ..core.provider import DataProvider

STOICH_AFR = 14.7
GASOLINE_G_PER_L = 737.0
SIXTY_MPH_KPH = 96.5606
MAX_GAP_S = 5.0        # ignore integration across stream gaps
INSTANT_TAU_S = 3.0    # smoothing for instant economy
LAUNCH_KPH = 0.5


@dataclass
class TripState:
    distance_km: float = 0.0
    fuel_l: float = 0.0
    moving_s: float = 0.0
    last_ts: float = 0.0
    _speed_ts: float | None = field(default=None, repr=False)
    _speed: float = field(default=0.0, repr=False)
    _maf_ts: float | None = field(default=None, repr=False)
    _maf: float = field(default=0.0, repr=False)
    _instant_lp100k: float | None = field(default=None, repr=False)
    _rate_ts: float | None = field(default=None, repr=False)
    _rate: float = field(default=0.0, repr=False)

    def _integrate_lph(self, dt: float, avg_lph: float, now_lph: float) -> None:
        self.fuel_l += avg_lph / 3600 * dt
        # smoothed instantaneous economy (needs to be moving)
        if self._speed > 5:
            inst = now_lph / self._speed * 100
            alpha = min(1.0, dt / INSTANT_TAU_S)
            prev = self._instant_lp100k if self._instant_lp100k is not None else inst
            self._instant_lp100k = prev + alpha * (inst - prev)
        else:
            self._instant_lp100k = None

    def on_fuel_rate(self, ts: float, lph: float) -> None:
        if self._rate_ts is not None:
            dt = ts - self._rate_ts
            if 0 < dt < MAX_GAP_S:
                self._integrate_lph(dt, (lph + self._rate) / 2, lph)
        self._rate_ts, self._rate = ts, lph
        self.last_ts = ts

    def on_speed(self, ts: float, kph: float) -> None:
        if self._speed_ts is not None:
            dt = ts - self._speed_ts
            if 0 < dt < MAX_GAP_S:
                avg = (kph + self._speed) / 2
                self.distance_km += avg * dt / 3600
                if avg > 1:
                    self.moving_s += dt
        self._speed_ts, self._speed = ts, kph
        self.last_ts = ts

    def on_maf(self, ts: float, gs: float) -> None:
        rate_live = self._rate_ts is not None and ts - self._rate_ts < MAX_GAP_S
        if self._maf_ts is not None and not rate_live:  # ECU fuel rate wins
            dt = ts - self._maf_ts
            if 0 < dt < MAX_GAP_S:
                to_lph = 3600 / STOICH_AFR / GASOLINE_G_PER_L
                self._integrate_lph(dt, (gs + self._maf) / 2 * to_lph, gs * to_lph)
        self._maf_ts, self._maf = ts, gs
        self.last_ts = ts

    @property
    def avg_lp100k(self) -> float | None:
        if self.distance_km < 0.05:
            return None
        return self.fuel_l / self.distance_km * 100

    @property
    def instant_lp100k(self) -> float | None:
        return self._instant_lp100k


@dataclass
class ZeroSixty:
    last_s: float | None = None
    best_s: float | None = None
    _armed: bool = False
    _still_since: float | None = None
    _launch_ts: float | None = None

    def update(self, ts: float, kph: float) -> bool:
        """Returns True when a new run was just recorded."""
        if kph < LAUNCH_KPH:
            if self._still_since is None:
                self._still_since = ts
            if ts - self._still_since >= 1.0:
                self._armed = True
            self._launch_ts = None  # aborts any run in progress
            return False

        self._still_since = None
        if self._armed:
            self._armed = False
            self._launch_ts = ts  # launch!
        if self._launch_ts is not None and kph >= SIXTY_MPH_KPH:
            t = round(ts - self._launch_ts, 2)
            self._launch_ts = None
            self.last_s = t
            self.best_s = t if self.best_s is None else min(self.best_s, t)
            return True
        return False


class TripProvider(DataProvider):
    name = "trip"

    @property
    def cache_file(self) -> Path:
        return Path(self.config.get("cache_dir", "cache")) / "trip.json"

    def _load(self) -> tuple[TripState, ZeroSixty]:
        try:
            raw = json.loads(self.cache_file.read_text())
        except (OSError, ValueError):
            return TripState(), ZeroSixty()
        state = TripState(
            distance_km=raw.get("distance_km", 0.0),
            fuel_l=raw.get("fuel_l", 0.0),
            moving_s=raw.get("moving_s", 0.0),
            last_ts=raw.get("last_ts", 0.0),
        )
        return state, ZeroSixty(best_s=raw.get("best_zero_sixty"))

    def _save(self, state: TripState, zs: ZeroSixty) -> None:
        data = {k: v for k, v in asdict(state).items() if not k.startswith("_")}
        data["best_zero_sixty"] = zs.best_s
        try:
            self.cache_file.parent.mkdir(parents=True, exist_ok=True)
            self.cache_file.write_text(json.dumps(data))
        except OSError:
            pass  # read-only root — trip just won't survive restarts

    async def run(self) -> None:
        state, zs = self._load()
        reset_s = float(self.config.get("providers.trip.reset_hours", 6)) * 3600
        last_pub = 0.0
        last_save = 0.0

        sub = self.bus.subscribe(
            "vehicle.speed_kph", "vehicle.maf_gs", "vehicle.fuel_rate_lph", "trip.reset"
        )
        try:
            async for msg in sub:
                if msg.topic == "trip.reset":
                    state = TripState()
                    self._publish(state, zs)
                    self._save(state, zs)
                    continue

                # parked long enough → new trip (best 0-60 is kept)
                if state.last_ts and msg.ts - state.last_ts > reset_s:
                    state = TripState()

                if msg.topic == "vehicle.speed_kph":
                    state.on_speed(msg.ts, float(msg.value))
                    if zs.update(msg.ts, float(msg.value)):
                        self.bus.publish("trip.zero_sixty", {"last_s": zs.last_s, "best_s": zs.best_s})
                        self._save(state, zs)
                elif msg.topic == "vehicle.maf_gs":
                    state.on_maf(msg.ts, float(msg.value))
                elif msg.topic == "vehicle.fuel_rate_lph":
                    state.on_fuel_rate(msg.ts, float(msg.value))

                if msg.ts - last_pub >= 1.0:
                    last_pub = msg.ts
                    self._publish(state, zs)
                if msg.ts - last_save >= 30.0:
                    last_save = msg.ts
                    self._save(state, zs)
        finally:
            self.bus.unsubscribe(sub)

    def _publish(self, state: TripState, zs: ZeroSixty) -> None:
        self.bus.publish("trip.distance_km", round(state.distance_km, 2))
        self.bus.publish("trip.time_s", int(state.moving_s))
        self.bus.publish("trip.fuel_l", round(state.fuel_l, 2))
        avg = state.avg_lp100k
        self.bus.publish("trip.avg_lp100k", round(avg, 1) if avg is not None else None)
        inst = state.instant_lp100k
        self.bus.publish("trip.instant_lp100k", round(inst, 1) if inst is not None else None)
        if zs.last_s is not None or zs.best_s is not None:
            self.bus.publish("trip.zero_sixty", {"last_s": zs.last_s, "best_s": zs.best_s})
