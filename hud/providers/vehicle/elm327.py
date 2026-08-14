"""ELM327 USB vehicle source (python-obd).

Runs a blocking poll loop in one worker thread and publishes onto the bus
via ``loop.call_soon_threadsafe`` — python-obd is synchronous serial I/O.

The active channel set is dynamic: when the CAN HAT is healthy the manager
shrinks this source to the slow channels CAN doesn't broadcast (coolant,
fuel, DTCs, ...); if CAN dies it widens back to everything. The set is read
each poll cycle, so no reconnect is needed to switch.

Poll cadence: fast channels every cycle (~5 Hz), slow channels every 2 s,
DTCs every 30 s. Repeated null replies on fast PIDs mean the link is dead
(ignition off, adapter unplugged) → raise, and the supervisor reconnects
with backoff.
"""

from __future__ import annotations

import asyncio
import threading
import time
from typing import Any, Iterable

from .base import CHANNELS, VehicleSource

FAST_CHANNELS = ("speed_kph", "rpm", "throttle_pct", "maf_gs")
SLOW_CHANNELS = ("coolant_c", "fuel_pct", "battery_v", "ambient_c")
DTC_CHANNEL = "dtc_codes"

FAST_PERIOD_S = 0.2
SLOW_PERIOD_S = 2.0
DTC_PERIOD_S = 30.0
MAX_CONSECUTIVE_NULLS = 25  # ~5 s of dead fast PIDs → link is down

# channel → (python-obd command name, pint unit to convert to, or None)
COMMANDS: dict[str, tuple[str, str | None]] = {
    "speed_kph": ("SPEED", "kph"),
    "rpm": ("RPM", None),
    "throttle_pct": ("THROTTLE_POS", None),
    "coolant_c": ("COOLANT_TEMP", "degC"),
    "fuel_pct": ("FUEL_LEVEL", None),
    "battery_v": ("ELM_VOLTAGE", "volt"),
    "ambient_c": ("AMBIANT_AIR_TEMP", "degC"),  # python-obd's spelling
    "maf_gs": ("MAF", "gram/second"),
}


def convert(channel: str, value: Any) -> Any:
    """Pint quantity → plain float for the bus."""
    _, unit = COMMANDS[channel]
    if unit is not None:
        value = value.to(unit)
    magnitude = getattr(value, "magnitude", value)
    return round(float(magnitude), 2)


class Elm327VehicleSource(VehicleSource):
    name = "vehicle-elm327"

    def __init__(self, bus, config, channels: Iterable[str] = CHANNELS) -> None:
        super().__init__(bus, config)
        self.channels: set[str] = set(channels)

    async def run(self) -> None:
        import obd  # deferred: not installed on desktop dev machines

        port = self.config.get("providers.vehicle.elm327.port")
        loop = asyncio.get_running_loop()
        stop = threading.Event()
        error: list[BaseException] = []

        def poll_loop() -> None:
            conn = None
            try:
                conn = obd.OBD(portstr=port)  # port=None → autoscan
                if not conn.is_connected():
                    raise ConnectionError(f"ELM327 not connected (port={port or 'autoscan'})")

                commands = {ch: getattr(obd.commands, cmd) for ch, (cmd, _) in COMMANDS.items()}
                nulls = 0
                next_slow = 0.0
                next_dtc = 0.0

                while not stop.is_set():
                    cycle_start = time.monotonic()
                    active = self.channels  # read each cycle — manager may shrink/widen it

                    polls = [ch for ch in FAST_CHANNELS if ch in active]
                    if cycle_start >= next_slow:
                        next_slow = cycle_start + SLOW_PERIOD_S
                        polls += [ch for ch in SLOW_CHANNELS if ch in active]

                    for ch in polls:
                        r = conn.query(commands[ch])
                        if r.is_null():
                            if ch in FAST_CHANNELS:
                                nulls += 1
                            continue
                        if ch in FAST_CHANNELS:
                            nulls = 0
                        loop.call_soon_threadsafe(self.emit, ch, convert(ch, r.value))

                    if nulls >= MAX_CONSECUTIVE_NULLS:
                        raise ConnectionError("ELM327 link dead: fast PIDs returning null")

                    if DTC_CHANNEL in active and cycle_start >= next_dtc:
                        next_dtc = cycle_start + DTC_PERIOD_S
                        r = conn.query(obd.commands.GET_DTC)
                        if not r.is_null():
                            codes = [code for code, _desc in r.value]
                            loop.call_soon_threadsafe(self.emit, DTC_CHANNEL, codes)

                    elapsed = time.monotonic() - cycle_start
                    stop.wait(max(0.0, FAST_PERIOD_S - elapsed))
            except BaseException as exc:  # propagate to the asyncio side
                error.append(exc)
            finally:
                if conn is not None:
                    conn.close()

        worker = asyncio.create_task(asyncio.to_thread(poll_loop))
        try:
            await worker
        finally:
            stop.set()
            if not worker.done():
                await worker
        if error:
            raise error[0]
