"""VehicleSource — the normalized interface every vehicle backend implements.

CAN HAT, ELM327, and the simulator all publish the same channels; nothing
downstream (alerts, widgets) knows which backend produced a value. New
backends only need to map their raw data onto these names.
"""

from __future__ import annotations

import time
from typing import Any

from ...core.provider import DataProvider

# Normalized channels → published as f"vehicle.{channel}"
CHANNELS = (
    "speed_kph",     # float
    "rpm",           # float
    "coolant_c",     # float
    "fuel_pct",      # float 0-100
    "throttle_pct",  # float 0-100
    "gear",          # str: P R N D or 1-8
    "battery_v",     # float
    "ambient_c",     # float
    "dtc_codes",     # list[str]
    "maf_gs",        # float, mass air flow g/s — fuel-economy input
    # CAN-only channels (no OBD PIDs exist; absent on the ELM327 path):
    "lane_left",     # int 0-3: camera lane-line status, left
    "lane_right",    # int 0-3: camera lane-line status, right
    "lda_buzzer",    # int: lane departure buzzer active
    "rsa_sign",      # int: road-sign-assist sign type
    "rsa_value",     # int: road-sign-assist sign value
    "rsa_unit",      # int: road-sign-assist unit enum
    "bsm_status",    # int: blind spot monitor status
    "bsm_buzzer",    # int: blind spot buzzer
    "lights_on",     # int: headlights on (night-dim source)
    "cruise_on",     # int: cruise engaged
    "cruise_set",    # float: ACC set speed (kph, on-car confirm)
    "brake_on",      # int: brake pedal
    "brake_hold",    # int: brake hold engaged
    "pcs_warn",      # int: pre-collision warning
    "trans_temp_c",  # float: transmission oil temp
    "intake_temp_c", # float: intake air temp
    "odometer_km",   # float: odometer (29-bit meter frame, speculative)
    "steer_deg",     # float: steering angle
    "power_kw",      # float: hybrid system power, negative = regen
    "hv_battery_pct",  # float 0-100: hybrid battery state of charge
    "fuel_rate_lph",   # float: engine fuel rate, L/h (trip economy input)
)


class VehicleSource(DataProvider):
    name = "vehicle"
    last_emit_ts: float = 0.0  # freshness watermark, read by the failover manager

    def emit(self, channel: str, value: Any) -> None:
        self.last_emit_ts = time.time()
        self.bus.publish(f"vehicle.{channel}", value)
