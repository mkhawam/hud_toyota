"""Auto vehicle manager: CAN primary, ELM327 complement/fallback.

Both children run continuously under their own crash-restart supervision
(a missing adapter just retries with backoff — harmless). The manager only
decides *who publishes what*, based on freshness watermarks:

- CAN fresh   → ELM327 shrinks to the slow channels CAN doesn't broadcast
                (Toyota doesn't put coolant/fuel/DTCs on the PT bus).
- CAN stale   → ELM327 widens to all channels: full fallback.

It also publishes ``vehicle.source`` ("can" | "elm327" | "none") for the
frontend source badge. No start/stop dance on failover — the ELM327 poll
loop reads its channel set every cycle.
"""

from __future__ import annotations

import asyncio
import time

from ...core.provider import DataProvider
from .base import CHANNELS
from .canbus import CanVehicleSource
from .elm327 import SLOW_CHANNELS, Elm327VehicleSource

DTC_CHANNEL = "dtc_codes"
ELM_COMPLEMENT = set(SLOW_CHANNELS) | {DTC_CHANNEL}

CAN_FRESH_S = 3.0    # CAN counts as alive if it emitted this recently
CHECK_PERIOD_S = 1.0


class AutoVehicleManager(DataProvider):
    name = "vehicle"

    def __init__(self, bus, config, can=None, elm=None) -> None:
        super().__init__(bus, config)
        self.can = can or CanVehicleSource(bus, config)
        self.elm = elm or Elm327VehicleSource(bus, config, channels=ELM_COMPLEMENT)

    def _current_source(self) -> str:
        now = time.time()
        if now - self.can.last_emit_ts < CAN_FRESH_S:
            return "can"
        if now - self.elm.last_emit_ts < CAN_FRESH_S * 2:  # ELM polls slower
            return "elm327"
        return "none"

    async def run(self) -> None:
        self.can.start()
        self.elm.start()
        source = None
        try:
            while True:
                new_source = self._current_source()
                self.elm.channels = ELM_COMPLEMENT if new_source == "can" else set(CHANNELS)
                if new_source != source:
                    source = new_source
                    self.bus.publish("vehicle.source", source)
                await asyncio.sleep(CHECK_PERIOD_S)
        finally:
            await self.can.stop()
            await self.elm.stop()
