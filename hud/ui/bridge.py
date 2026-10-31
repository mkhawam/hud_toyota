"""Bus ⇄ QML bridge.

Two QQmlPropertyMaps are exposed to QML as context properties:

- ``topics`` — every bus topic, dots replaced by underscores
  (``vehicle.speed_kph`` → ``topics.vehicle_speed_kph``). Updated on the Qt
  thread from coalesced batches.
- ``cfg`` — the merged config flattened the same way
  (``theme.accent`` → ``cfg.theme_accent``; lists stay lists). Refreshed
  whenever ``config.updated`` arrives on the bus.

QML bindings only re-evaluate for keys that exist when they are first read,
so every topic/config key the UI uses is pre-inserted at startup.

Writes go the other way through ``Bridge`` slots, which hop onto the asyncio
loop (the bus and config aren't thread-safe) and reuse the same pydantic
validation as the phone settings page.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any

from PySide6.QtCore import QObject, Signal, Slot
from PySide6.QtQml import QQmlPropertyMap

from ..core.bus import Bus
from ..core.config import Config
from ..core.settings import SECTIONS
from ..providers.vehicle.base import CHANNELS

log = logging.getLogger(__name__)

FLUSH_S = 1 / 30  # UI batch rate — plenty for 20 Hz telemetry

# Topics the QML reads that aren't vehicle channels.
EXTRA_TOPICS = (
    "vehicle.source", "alerts.active", "net.online", "system.cpu_temp_c",
    "weather.current", "traffic.flow", "road.limit", "road.speed_limit_kph",
    "trip.distance_km", "trip.time_s", "trip.fuel_l", "trip.avg_lp100k",
    "trip.instant_lp100k", "trip.zero_sixty", "gps.position", "gps.speed_kph",
    "gps.heading", "net.ap",
)

# Config keys the QML reads (flattened); pre-inserted with these defaults.
CONFIG_DEFAULTS: dict[str, Any] = {
    "mirror": True,
    "debug": False,
    "units_speed": "mph",
    "units_temp": "f",
    "display_aspect": "3:1",
    "display_scale": 1.0,
    "display_offset_x": 0.0,
    "display_offset_y": 0.0,
    "theme_accent": "#3ce0ff",
    "theme_glow": 0.85,
    "theme_font": "chakra",
    "theme_night_mode": "auto",
    "theme_night_brightness": 0.55,
    "theme_speed_size": 36,
    "theme_rpm_width": 44,
    "gauges_rpm_max": 7000,
    "gauges_rpm_redline": 6200,
    "gauges_power_max_kw": 150,
    "gauges_power_regen_kw": 50,
    "layout": [],
}


def qkey(topic: str) -> str:
    return topic.replace(".", "_")


def flatten(data: dict[str, Any], prefix: str = "") -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in data.items():
        key = f"{prefix}_{k}" if prefix else str(k)
        if isinstance(v, dict):
            out.update(flatten(v, key))
        else:
            out[key] = v
    return out


class Bridge(QObject):
    """Owns the property maps and the write-back slots."""

    # emitted from the asyncio thread; Qt queues it onto the main thread
    batchReady = Signal(dict)
    configChanged = Signal()
    saved = Signal(str, bool, str)  # section, ok, message
    shotRequested = Signal(str)     # path — Main.qml grabs the scene into it

    def __init__(self, bus: Bus, config: Config, loop: asyncio.AbstractEventLoop) -> None:
        super().__init__()
        self.bus = bus
        self.config = config
        self.loop = loop
        self._shots: dict[str, asyncio.Future] = {}

        self.topics = QQmlPropertyMap(self)
        for ch in CHANNELS:
            self.topics.insert(qkey(f"vehicle.{ch}"), None)
        for t in EXTRA_TOPICS:
            self.topics.insert(qkey(t), None)

        self.cfg = QQmlPropertyMap(self)
        for k, v in CONFIG_DEFAULTS.items():
            self.cfg.insert(k, v)
        self._apply_config()

        self.batchReady.connect(self._apply_batch)
        self.configChanged.connect(self._apply_config)

    # -- Qt thread -----------------------------------------------------------

    @Slot(dict)
    def _apply_batch(self, batch: dict) -> None:
        for topic, value in batch.items():
            self.topics.insert(qkey(topic), value)

    @Slot()
    def _apply_config(self) -> None:
        flat = flatten(self.config.data)
        for k in CONFIG_DEFAULTS:
            if k in flat:
                self.cfg.insert(k, flat[k])

    @Slot(str, "QVariant")
    def saveSection(self, section: str, value: Any) -> None:
        """Validated write of one config section (same rules as the web API)."""
        if hasattr(value, "toVariant"):  # QJSValue from QML
            value = value.toVariant()
        self.loop.call_soon_threadsafe(self._save_on_loop, section, value)

    @Slot(str, "QVariant")
    def patchSection(self, section: str, patch: Any) -> None:
        """Merge ``patch`` into a dict section (theme/units/display/gauges) and save."""
        if hasattr(patch, "toVariant"):
            patch = patch.toVariant()
        current = self.config.get(section) or {}
        merged = {**current, **dict(patch)} if isinstance(current, dict) else patch
        self.loop.call_soon_threadsafe(self._save_on_loop, section, merged)

    @Slot()
    def resetTrip(self) -> None:
        self.loop.call_soon_threadsafe(self.bus.publish, "trip.reset", {})

    @Slot(result="QVariantList")
    def debugRows(self) -> list:
        """[topic, short value, age seconds] for the debug panel."""
        now = time.time()
        rows = []
        for topic, msg in sorted(self.bus.snapshot().items()):
            v = msg.value
            if isinstance(v, float):
                text = f"{v:.2f}"
            elif isinstance(v, (dict, list)):
                text = json.dumps(v, separators=(",", ":"), default=str)
            else:
                text = str(v)
            rows.append([topic, text[:60], round(now - msg.ts, 1)])
        return rows

    # -- asyncio thread --------------------------------------------------------

    def _save_on_loop(self, section: str, value: Any) -> None:
        validator = SECTIONS.get(section)
        if validator is None:
            self.saved.emit(section, False, "unknown section")
            return
        try:
            cleaned = validator(value)
        except Exception as exc:  # noqa: BLE001 — pydantic or ValueError
            log.warning("rejected %s from HUD menu: %s", section, exc)
            self.saved.emit(section, False, str(exc).splitlines()[0])
            return
        self.config.save_section(section, cleaned)
        self.bus.publish("config.updated", {"section": section})
        self.saved.emit(section, True, "")

    # -- screenshots (GET /api/screenshot) ------------------------------------

    @Slot(str, bool)
    def shotDone(self, path: str, ok: bool) -> None:
        fut = self._shots.pop(path, None)
        if fut is not None:
            self.loop.call_soon_threadsafe(lambda: fut.done() or fut.set_result(ok))

    async def screenshot(self, path: str, timeout: float = 5.0) -> bool:
        """Grab the rendered HUD into ``path`` (called on the asyncio loop)."""
        fut = self.loop.create_future()
        self._shots[path] = fut
        self.shotRequested.emit(path)
        try:
            return await asyncio.wait_for(fut, timeout)
        except asyncio.TimeoutError:
            self._shots.pop(path, None)
            return False

    async def forward(self) -> None:
        """Coalesce bus traffic into ≤30 Hz batches for the UI."""
        sub = self.bus.subscribe("*", replay=True)
        pending: dict[str, Any] = {}
        loop = asyncio.get_running_loop()
        deadline: float | None = None
        try:
            while True:
                timeout = None if deadline is None else max(0.0, deadline - loop.time())
                try:
                    msg = await asyncio.wait_for(sub.__anext__(), timeout=timeout)
                except asyncio.TimeoutError:
                    self.batchReady.emit(pending)
                    pending, deadline = {}, None
                    continue
                if msg.topic == "config.updated":
                    self.configChanged.emit()
                pending[msg.topic] = msg.value
                if deadline is None:
                    deadline = loop.time() + FLUSH_S
        finally:
            self.bus.unsubscribe(sub)
