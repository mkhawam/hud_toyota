"""Simulated vehicle source for desktop development.

Drives a plausible cycle — pick a target speed, approach it with bounded
accel, idle at lights — so widgets see realistic motion: fast channels
(speed/rpm/throttle) at 20 Hz, slow channels (coolant/fuel/battery) at 1 Hz.
"""

from __future__ import annotations

import asyncio
import random

from .base import VehicleSource

FAST_HZ = 20
TARGETS_KPH = [0, 0, 30, 50, 60, 80, 100, 110]  # 0 twice → stops are common
ACCEL_KPH_S = 9.0    # ~2.5 m/s²
DECEL_KPH_S = 13.0   # braking

# speed above which each gear upshifts (rough Camry-ish 8-speed feel)
GEAR_SHIFTS_KPH = [15, 30, 45, 62, 80, 100, 122]


def gear_for(speed_kph: float) -> int:
    for i, limit in enumerate(GEAR_SHIFTS_KPH):
        if speed_kph < limit:
            return i + 1
    return 8


def rpm_for(speed_kph: float, gear: int, accelerating: bool) -> float:
    if speed_kph < 1:
        return 750 + random.uniform(-20, 20)  # idle jitter
    # per-gear ratio: low gears rev higher for the same speed
    ratio = [95, 62, 45, 34, 27, 22, 18, 15][gear - 1]
    rpm = 700 + speed_kph * ratio
    if accelerating:
        rpm += 400
    return rpm


class SimVehicleSource(VehicleSource):
    async def run(self) -> None:
        speed = 0.0
        target = 0.0
        next_retarget = 0.0
        coolant = 21.0
        fuel = 87.0
        t = 0.0
        dt = 1.0 / FAST_HZ
        last_slow = -1.0
        last_gear = None
        trans_temp = 25.0
        odometer = 48213.0
        lda_alert_until = 0.0
        lane_drop_until = 0.0
        bsm_until = 0.0
        lights = 0

        while True:
            t += dt
            if t >= next_retarget:
                target = float(random.choice(TARGETS_KPH))
                next_retarget = t + random.uniform(8, 20)

            accelerating = target > speed + 0.5
            if accelerating:
                speed = min(target, speed + ACCEL_KPH_S * dt)
            elif target < speed - 0.5:
                speed = max(target, speed - DECEL_KPH_S * dt)

            gear = gear_for(speed)
            rpm = rpm_for(speed, gear, accelerating)
            self.emit("speed_kph", round(speed, 1))
            self.emit("rpm", round(rpm))
            self.emit("throttle_pct", round(random.uniform(25, 60) if accelerating else 8.0, 1))
            # MAF roughly tracks rpm and load; idles ~3 g/s, WOT ~80+ g/s
            load = 0.8 if accelerating else 0.25
            self.emit("maf_gs", round(3.0 + rpm / 6500 * 90 * load, 1))
            # hybrid power: positive under acceleration, regen while slowing
            if accelerating:
                power = 15 + (rpm / 6500) * 110
            elif target < speed - 0.5 and speed > 5:
                power = -min(45.0, speed * 0.35)  # regen braking
            else:
                power = 4 + speed * 0.08  # cruise draw
            self.emit("power_kw", round(power, 1))
            if gear != last_gear:
                self.emit("gear", "P" if speed < 0.5 and target == 0 else f"D{gear}")
                last_gear = gear

            if t - last_slow >= 1.0:
                last_slow = t
                coolant = min(90.0, coolant + 0.4)      # warm-up to operating temp
                trans_temp = min(85.0, trans_temp + 0.25)
                fuel = max(0.0, fuel - 0.003)
                odometer += speed / 3600.0
                self.emit("coolant_c", round(coolant, 1))
                self.emit("fuel_pct", round(fuel, 1))
                self.emit("battery_v", round(random.uniform(13.9, 14.2), 2))
                self.emit("ambient_c", 24.0)
                self.emit("dtc_codes", [])
                self.emit("trans_temp_c", round(trans_temp, 1))
                self.emit("intake_temp_c", round(28.0 + speed * 0.05, 1))
                self.emit("odometer_km", round(odometer, 1))
                self.emit("steer_deg", round(random.uniform(-6, 6) if speed > 5 else 0.0, 1))

                # camera lane lines: detected when moving, occasional dropout,
                # rare 2 s departure alert so widgets exercise every state
                if random.random() < 0.04:
                    lane_drop_until = t + random.uniform(2, 5)
                if speed > 40 and random.random() < 0.02:
                    lda_alert_until = t + 2.0
                seen = speed > 30
                alert = t < lda_alert_until
                left = 3 if alert else (1 if seen and t >= lane_drop_until else 0)
                right = 1 if seen else 0
                self.emit("lane_left", left)
                self.emit("lane_right", right)
                self.emit("lda_buzzer", 1 if alert else 0)

                # blind spot event roughly every 30 s while moving
                if speed > 20 and random.random() < 0.03:
                    bsm_until = t + random.uniform(3, 6)
                self.emit("bsm_status", 1 if t < bsm_until else 0)
                self.emit("bsm_buzzer", 0)

                # headlights cycle ~every 2 min (exercises CAN night-dim)
                if int(t) % 120 == 0 and t > 1:
                    lights = 1 - lights
                self.emit("lights_on", lights)

                cruising = speed > 90 and not alert
                self.emit("cruise_on", 1 if cruising else 0)
                self.emit("cruise_set", 100.0 if cruising else 0.0)
                self.emit("brake_on", 1 if target < speed - 5 else 0)
                self.emit("brake_hold", 1 if speed < 0.5 and target == 0 else 0)
                self.emit("pcs_warn", 0)

            await asyncio.sleep(dt)
