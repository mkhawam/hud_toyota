"""OBD-II over SocketCAN: active Mode 01 polling through the CAN HAT.

Newer Toyotas (e.g. the 2025 Camry) put a security gateway behind the OBD
port: the broadcast powertrain frames the passive ``canbus`` source decodes
never reach pins 6/14, but the ECUs still answer standard OBD-II requests.
This source asks for them directly — the same requests an ELM327 sends, at
CAN speed and without the serial adapter.

Protocol (ISO 15765-4, 11-bit, 500 kbit/s): a single-frame request
``[02 01 PID ...]`` to the functional broadcast ID 0x7DF; each ECU that
supports the PID answers on 0x7E8-0x7EF with ``[len 41 PID A B ...]``.
Every PID polled here fits in one frame, so no ISO-TP flow control is
needed. Requests are always functional: the 2025 Camry's gateway drops
physically-addressed requests (0x7E0) from the OBD port.

At connect it discovers which ECU supports which PID (Mode 01 PIDs 00/20/40
bitmaps) and then takes each PID's value from one ECU — preferring the
engine ECU (0x7E8) — stopping the wait as soon as that ECU has replied.

``channel: auto`` probes every CAN interface that is up — busiest first,
so an unwired controller is tried last — and uses the first one an ECU
answers on: MCP2515 HATs with two controllers probe in random order, so
can0/can1 swap names between boots.
"""

from __future__ import annotations

import asyncio
import os
import threading
import time
from typing import Any, Callable, Iterable

from .base import VehicleSource

FUNCTIONAL_ID = 0x7DF
RESP_LO, RESP_HI = 0x7E8, 0x7EF
ENGINE_RESP = 0x7E8

REPLY_TIMEOUT_S = 0.1
DISCOVER_TIMEOUT_S = 0.3
FAST_PERIOD_S = 0.1     # fast PIDs ~10 Hz
SLOW_PERIOD_S = 2.0
MAX_CONSECUTIVE_MISSES = 30  # ~3 s of silence on fast PIDs → link down

# channel → (PID, decoder(data bytes A..))
PIDS: dict[str, tuple[int, Callable[[bytes], float]]] = {
    "speed_kph":     (0x0D, lambda d: float(d[0])),
    "rpm":           (0x0C, lambda d: (d[0] * 256 + d[1]) / 4),
    "throttle_pct":  (0x11, lambda d: d[0] * 100 / 255),
    "maf_gs":        (0x10, lambda d: (d[0] * 256 + d[1]) / 100),
    "coolant_c":     (0x05, lambda d: float(d[0] - 40)),
    "intake_temp_c": (0x0F, lambda d: float(d[0] - 40)),
    "fuel_pct":      (0x2F, lambda d: d[0] * 100 / 255),
    "battery_v":     (0x42, lambda d: (d[0] * 256 + d[1]) / 1000),
    "ambient_c":     (0x46, lambda d: float(d[0] - 40)),
}
PID_LEN = {0x0C: 2, 0x10: 2, 0x42: 2}  # data bytes; default 1

FAST_CHANNELS = ("speed_kph", "rpm", "throttle_pct", "maf_gs")
SLOW_CHANNELS = ("coolant_c", "intake_temp_c", "fuel_pct", "battery_v", "ambient_c")
OBD_CHANNELS = frozenset(PIDS)

SUPPORT_PIDS = (0x00, 0x20, 0x40)


# ---- pure helpers (unit-tested) -------------------------------------------


def request(pid: int) -> bytes:
    return bytes([0x02, 0x01, pid, 0, 0, 0, 0, 0])


def parse_reply(data: bytes) -> tuple[int, bytes] | None:
    """Single-frame Mode 01 positive reply → (pid, data bytes) or None."""
    if len(data) < 3:
        return None
    length = data[0]
    if length & 0xF0 or length < 2 or data[1] != 0x41 or length > len(data) - 1:
        return None
    return data[2], bytes(data[3 : 1 + length])


def decode(channel: str, payload: bytes) -> float | None:
    pid, fn = PIDS[channel]
    if len(payload) < PID_LEN.get(pid, 1):
        return None
    return round(fn(payload), 2)


def supported_from_bitmap(base: int, bitmap: bytes) -> set[int]:
    """Mode 01 'PIDs supported' reply (4 bytes) → set of supported PIDs."""
    out: set[int] = set()
    for i in range(32):
        if bitmap[i // 8] & (0x80 >> (i % 8)):
            out.add(base + i + 1)
    return out


def choose_ecus(support: dict[int, set[int]]) -> dict[int, int]:
    """{resp_id: pids} → {pid: resp_id to read it from}, preferring the engine."""
    order = sorted(support, key=lambda r: (r != ENGINE_RESP, r))
    plan: dict[int, int] = {}
    for resp in order:
        for pid in support[resp]:
            plan.setdefault(pid, resp)
    return plan


def can_interfaces(sys_net: str = "/sys/class/net") -> list[str]:
    """CAN interfaces (ARPHRD_CAN = 280) that are up, busiest (most frames
    received) first — probing an unwired controller leaves an unacked
    frame retrying on it, so try the one with a car on it first."""
    out: list[tuple[int, str]] = []
    for name in sorted(os.listdir(sys_net)):
        try:
            with open(f"{sys_net}/{name}/type") as f:
                if f.read().strip() != "280":
                    continue
            with open(f"{sys_net}/{name}/flags") as f:
                if not int(f.read().strip(), 16) & 0x1:  # IFF_UP
                    continue
        except OSError:
            continue
        try:
            with open(f"{sys_net}/{name}/statistics/rx_packets") as f:
                rx = int(f.read().strip())
        except (OSError, ValueError):
            rx = 0
        out.append((rx, name))
    return [name for _, name in sorted(out, key=lambda t: (-t[0], t[1]))]


# ---- source ----------------------------------------------------------------


class CanObdVehicleSource(VehicleSource):
    name = "vehicle-canobd"

    def __init__(self, bus, config, channels: Iterable[str] = OBD_CHANNELS) -> None:
        super().__init__(bus, config)
        self.channels: set[str] = set(channels)  # the manager narrows/widens this
        self.iface: str | None = None

    # -- socket helpers (run in the worker thread) ------------------------

    @staticmethod
    def _open(can_mod, iface: str):
        return can_mod.interface.Bus(
            channel=iface,
            interface="socketcan",
            can_filters=[{"can_id": RESP_LO, "can_mask": 0x7F8, "extended": False}],
            receive_own_messages=False,
        )

    @staticmethod
    def _send(can_mod, sock, arb_id: int, pid: int) -> None:
        sock.send(can_mod.Message(arbitration_id=arb_id, data=request(pid), is_extended_id=False))

    def _collect(self, sock, pid: int, timeout: float, want: int | None = None):
        """Replies for ``pid`` until timeout (or the first from ``want``)."""
        deadline = time.monotonic() + timeout
        out: list[tuple[int, bytes]] = []
        while (left := deadline - time.monotonic()) > 0:
            msg = sock.recv(timeout=left)
            if msg is None:
                break
            parsed = parse_reply(bytes(msg.data))
            if parsed is None or parsed[0] != pid:
                continue
            out.append((msg.arbitration_id, parsed[1]))
            if want is not None and msg.arbitration_id == want:
                break
        return out

    def _discover(self, can_mod, sock) -> dict[int, int]:
        support: dict[int, set[int]] = {}
        for base in SUPPORT_PIDS:
            self._send(can_mod, sock, FUNCTIONAL_ID, base)
            for resp, data in self._collect(sock, base, DISCOVER_TIMEOUT_S):
                if len(data) >= 4:
                    support.setdefault(resp, set()).update(supported_from_bitmap(base, data))
            if not any(base + 0x20 in s for s in support.values()):
                break  # nobody advertises the next range
        return choose_ecus(support)

    def _connect(self, can_mod):
        configured = self.config.get("providers.vehicle.can.channel", "auto")
        candidates = can_interfaces() if configured in (None, "", "auto") else [configured]
        if not candidates:
            raise ConnectionError("no CAN interface is up")
        for iface in candidates:
            sock = self._open(can_mod, iface)
            try:
                plan = self._discover(can_mod, sock)
            except Exception:
                sock.shutdown()
                raise
            if plan:
                return iface, sock, plan
            sock.shutdown()
        raise ConnectionError(f"no OBD reply on {', '.join(candidates)} (ignition off?)")

    # -- provider loop ------------------------------------------------------

    async def run(self) -> None:
        import can as can_mod  # python-can, [vehicle] extra

        loop = asyncio.get_running_loop()
        stop = threading.Event()
        error: list[BaseException] = []

        def poll_loop() -> None:
            sock = None
            try:
                self.iface, sock, plan = self._connect(can_mod)
                chans = {ch: PIDS[ch][0] for ch in PIDS if PIDS[ch][0] in plan}
                loop.call_soon_threadsafe(
                    self.bus.publish, "vehicle.can_obd",
                    {"iface": self.iface, "channels": sorted(chans)},
                )
                misses = 0
                next_slow = 0.0
                while not stop.is_set():
                    start = time.monotonic()
                    active = self.channels
                    polls = [c for c in FAST_CHANNELS if c in active and c in chans]
                    if start >= next_slow:
                        next_slow = start + SLOW_PERIOD_S
                        polls += [c for c in SLOW_CHANNELS if c in active and c in chans]
                    for ch in polls:
                        pid = chans[ch]
                        ecu = plan[pid]
                        self._send(can_mod, sock, FUNCTIONAL_ID, pid)
                        replies = self._collect(sock, pid, REPLY_TIMEOUT_S, want=ecu)
                        value = next((decode(ch, d) for r, d in replies if r == ecu), None)
                        if value is None:
                            if ch in FAST_CHANNELS:
                                misses += 1
                            continue
                        if ch in FAST_CHANNELS:
                            misses = 0
                        loop.call_soon_threadsafe(self.emit, ch, value)
                    if misses >= MAX_CONSECUTIVE_MISSES:
                        raise ConnectionError(f"OBD over {self.iface}: ECUs stopped answering")
                    stop.wait(max(0.0, FAST_PERIOD_S - (time.monotonic() - start)))
            except BaseException as exc:
                error.append(exc)
            finally:
                if sock is not None:
                    sock.shutdown()

        worker = asyncio.create_task(asyncio.to_thread(poll_loop))
        try:
            await worker
        finally:
            stop.set()
            if not worker.done():
                await worker
        if error:
            raise error[0]
