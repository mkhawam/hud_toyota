"""Auto vehicle manager: CAN broadcast primary, OBD-over-CAN and ELM327 behind it.

All children run continuously under their own crash-restart supervision
(a missing adapter just retries with backoff — harmless). The manager only
decides *who publishes what*, based on freshness watermarks:

- CAN fresh   → ELM327 shrinks to the slow channels CAN doesn't broadcast
                (Toyota doesn't put coolant/fuel/DTCs on the PT bus).
- CAN stale   → ELM327 widens to all channels: full fallback.

OBD-over-CAN (``canobd``) sits between them: it polls OBD-II PIDs through
the same HAT, which is the only way to get data on cars whose security
gateway keeps broadcast frames off the OBD port (2025 Camry). While CAN
broadcast is fresh it only polls what the broadcast lacks; while it is
fresh itself the ELM327 is left with DTCs only.

It also publishes ``vehicle.source`` ("can" | "can-obd" | "elm327" | "none") for the
frontend source badge. No start/stop dance on failover — the ELM327 poll
loop reads its channel set every cycle.
"""

from __future__ import annotations

import asyncio
import time

from ...core.provider import DataProvider
from .base import CHANNELS
from .canbus import CanVehicleSource
from .canobd import OBD_CHANNELS, CanObdVehicleSource
from .elm327 import SLOW_CHANNELS, Elm327VehicleSource

DTC_CHANNEL = "dtc_codes"
ELM_COMPLEMENT = set(SLOW_CHANNELS) | {DTC_CHANNEL}
# what the broadcast DBC mapping doesn't carry → polled over OBD meanwhile
OBD_COMPLEMENT = set(OBD_CHANNELS) & (
    set(SLOW_CHANNELS) | {"fuel_pct", "battery_v", "power_kw", "hv_battery_pct", "fuel_rate_lph"}
)

CAN_FRESH_S = 3.0    # CAN counts as alive if it emitted this recently
CHECK_PERIOD_S = 1.0


class AutoVehicleManager(DataProvider):
    name = "vehicle"

    def __init__(self, bus, config, can=None, elm=None, obd=None) -> None:
        super().__init__(bus, config)
        self.can = can or CanVehicleSource(bus, config)
        self.obd = obd or CanObdVehicleSource(bus, config)
        self.elm = elm or Elm327VehicleSource(bus, config, channels=ELM_COMPLEMENT)

    def _fresh(self) -> tuple[bool, bool, bool]:
        now = time.time()
        return (
            now - self.can.last_emit_ts < CAN_FRESH_S,
            now - self.obd.last_emit_ts < CAN_FRESH_S,
            now - self.elm.last_emit_ts < CAN_FRESH_S * 2,  # ELM polls slower
        )

    def _current_source(self) -> str:
        can, obd, elm = self._fresh()
        if can:
            return "can"
        if obd:
            return "can-obd"
        if elm:
            return "elm327"
        return "none"

    async def run(self) -> None:
        self.can.start()
        self.obd.start()
        self.elm.start()
        source = None
        try:
            while True:
                can_fresh, obd_fresh, _ = self._fresh()
                new_source = self._current_source()
                self.obd.channels = OBD_COMPLEMENT if can_fresh else set(OBD_CHANNELS)
                if obd_fresh:
                    self.elm.channels = {DTC_CHANNEL}
                elif can_fresh:
                    self.elm.channels = ELM_COMPLEMENT
                else:
                    self.elm.channels = set(CHANNELS)
                if new_source != source:
                    source = new_source
                    self.bus.publish("vehicle.source", source)
                await asyncio.sleep(CHECK_PERIOD_S)
        finally:
            await self.can.stop()
            await self.obd.stop()
            await self.elm.stop()
