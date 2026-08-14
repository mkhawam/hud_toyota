"""CAN bus vehicle source (SocketCAN + cantools).

Passively listens on ``can0`` and decodes broadcast frames with a DBC
(vendored opendbc Toyota powertrain file, see dbc/). Which signal feeds
which normalized channel is pure config — retargeting to another car or a
corrected DBC never touches this code:

    providers.vehicle.can.signals:
      speed_kph: { message: VSC1S03, signal: SP1 }
      rpm:       { message: ENG1F07, signal: NE1 }
    providers.vehicle.can.gear:
      message: ECT1S92
      bits: { P: B_P, R: B_R, N: B_N, D: B_D }

The gear entry is a composite: Toyota broadcasts PRND as separate bit
signals in the transmission message.

Blocking ``bus.recv`` runs in a worker thread; decoded values are emitted
onto the asyncio loop. Rate limiting: a channel is re-emitted at most every
RATE_LIMIT_S even if frames arrive faster (Toyota sends 0xB4 at ~33 Hz).
"""

from __future__ import annotations

import asyncio
import threading
import time
from typing import Any

from .base import VehicleSource

RATE_LIMIT_S = 0.05  # per-channel emit cap: 20 Hz
RECV_TIMEOUT_S = 1.0


class CanVehicleSource(VehicleSource):
    name = "vehicle-can"

    def __init__(self, bus, config) -> None:
        super().__init__(bus, config)
        self._last_emit: dict[str, float] = {}
        self._db = None
        self._frame_map: dict[int, list[tuple[str, dict[str, Any]]]] = {}

    # -- decode plumbing (pure, unit-testable) ----------------------------

    @staticmethod
    def _sanitize_dbc(text: str) -> str:
        """Fix or drop messages with malformed frame IDs. The opendbc ref
        file carries meter/body messages whose 29-bit IDs lack the DBC
        extended flag — cantools refuses those. Rewrite them as extended
        (id | 0x80000000) so they decode if the car broadcasts them; drop
        only IDs that don't even fit in 29 bits."""
        out: list[str] = []
        bad_ids: set[str] = set()
        skipping = False
        for line in text.splitlines():
            if line.startswith("BO_ "):
                parts = line.split()
                raw_id = parts[1]
                fid = int(raw_id)
                skipping = False
                if fid >= 0x800 and not fid & 0x80000000:
                    # opendbc's meter/body frames carry stray high bits (e.g.
                    # 0x40000000) — the real 29-bit ID is the masked value.
                    parts[1] = str((fid & 0x1FFFFFFF) | 0x80000000)  # extended
                    line = " ".join(parts[:2]) + " " + " ".join(parts[2:])
            elif skipping:
                if line.startswith(" SG_"):
                    continue
                skipping = False
            if line.startswith(("CM_", "BA_", "VAL_")) and line.split()[1:3] and any(
                b in line.split()[:4] for b in bad_ids
            ):
                continue
            out.append(line)
        return "\n".join(out)

    def load_dbc(self) -> None:
        import cantools

        dbc_path = self.config.get("providers.vehicle.can.dbc", "dbc/toyota_2017_ref_pt.dbc")
        with open(dbc_path, encoding="utf-8", errors="replace") as f:
            self._db = cantools.database.load_string(
                self._sanitize_dbc(f.read()), "dbc", strict=False
            )

        # frame_id → [(channel, spec)] for every configured mapping
        self._frame_map = {}
        signals = self.config.get("providers.vehicle.can.signals", {}) or {}
        for channel, spec in signals.items():
            msg = self._db.get_message_by_name(spec["message"])
            self._frame_map.setdefault(msg.frame_id, []).append((channel, spec))
        gear = self.config.get("providers.vehicle.can.gear")
        if gear:
            msg = self._db.get_message_by_name(gear["message"])
            self._frame_map.setdefault(msg.frame_id, []).append(("gear", gear))

    def handle_frame(self, frame_id: int, data: bytes) -> list[tuple[str, Any]]:
        """Decode one frame → [(channel, value)] for mapped channels."""
        specs = self._frame_map.get(frame_id)
        if not specs:
            return []
        try:
            decoded = self._db.decode_message(frame_id, data, decode_choices=False)
        except Exception:
            return []  # short/garbled frame — not worth crashing the source

        out: list[tuple[str, Any]] = []
        for channel, spec in specs:
            if channel == "gear":
                for label, sig in spec["bits"].items():
                    if decoded.get(sig):
                        out.append(("gear", label))
                        break
            elif spec["signal"] in decoded:
                out.append((channel, round(float(decoded[spec["signal"]]), 2)))
        return out

    # -- provider loop ----------------------------------------------------

    async def run(self) -> None:
        import can  # deferred: python-can only present with the [vehicle] extra

        self.load_dbc()
        channel = self.config.get("providers.vehicle.can.channel", "can0")
        loop = asyncio.get_running_loop()
        stop = threading.Event()
        error: list[BaseException] = []

        def recv_loop() -> None:
            can_bus = None
            try:
                can_bus = can.interface.Bus(channel=channel, interface="socketcan")
                while not stop.is_set():
                    frame = can_bus.recv(timeout=RECV_TIMEOUT_S)
                    if frame is None:
                        continue
                    now = time.monotonic()
                    for ch, value in self.handle_frame(frame.arbitration_id, bytes(frame.data)):
                        if now - self._last_emit.get(ch, 0.0) >= RATE_LIMIT_S:
                            self._last_emit[ch] = now
                            loop.call_soon_threadsafe(self.emit, ch, value)
            except BaseException as exc:
                error.append(exc)
            finally:
                if can_bus is not None:
                    can_bus.shutdown()

        worker = asyncio.create_task(asyncio.to_thread(recv_loop))
        try:
            await worker
        finally:
            stop.set()
            if not worker.done():
                await worker
        if error:
            raise error[0]
