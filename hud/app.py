"""Assemble the HUD: bus + providers + server on one asyncio loop."""

from __future__ import annotations

import asyncio
import logging

from .alerts.engine import AlertsEngine
from .core.bus import Bus
from .core.config import Config
from .core.provider import DataProvider
from .providers.vehicle.sim import SimVehicleSource
from .server import create_app, run_server

log = logging.getLogger(__name__)


def make_vehicle_source(source: str, bus: Bus, config: Config) -> DataProvider:
    if source == "sim":
        return SimVehicleSource(bus, config)
    if source == "elm327":
        from .providers.vehicle.elm327 import Elm327VehicleSource

        return Elm327VehicleSource(bus, config)
    if source == "can":
        from .providers.vehicle.canbus import CanVehicleSource

        return CanVehicleSource(bus, config)
    if source == "can-obd":
        from .providers.vehicle.canobd import CanObdVehicleSource

        return CanObdVehicleSource(bus, config)
    if source == "auto":
        from .providers.vehicle.manager import AutoVehicleManager

        return AutoVehicleManager(bus, config)
    raise ValueError(f"unknown vehicle source: {source}")


def make_providers(bus: Bus, config: Config, source: str) -> list[DataProvider]:
    providers: list[DataProvider] = [
        make_vehicle_source(source, bus, config),
        AlertsEngine(bus, config),
    ]
    if config.get("providers.system.enabled", True):
        from .providers.system import SystemProvider

        providers.append(SystemProvider(bus, config))
    if config.get("providers.trip.enabled", True):
        from .providers.trip import TripProvider

        providers.append(TripProvider(bus, config))
    if config.get("drivelog.enabled", True):
        from .drivelog.recorder import DriveRecorder

        providers.append(DriveRecorder(bus, config))
    if config.get("providers.weather.enabled", True):
        from .providers.weather import WeatherProvider

        providers.append(WeatherProvider(bus, config))
    if config.get("providers.gps.enabled", False):
        from .providers.gps import GpsProvider

        providers.append(GpsProvider(bus, config))
    if config.get("providers.traffic.enabled", False) and config.get("providers.traffic.tomtom_key"):
        from .providers.traffic import TrafficProvider

        providers.append(TrafficProvider(bus, config))
    if config.get("providers.speedlimit.enabled", False):
        from .providers.speedlimit import SpeedLimitProvider

        providers.append(SpeedLimitProvider(bus, config))
    return providers


async def serve(bus: Bus, config: Config, source: str, stop: asyncio.Event,
                extra: list | None = None, screenshot=None) -> None:
    """Run providers + the settings web server until ``stop`` is set.

    ``extra`` coroutines (e.g. the native UI's bus forwarder) run alongside
    and are cancelled on the way out.
    """
    providers = make_providers(bus, config, source)
    app = create_app(bus, config, screenshot=screenshot)
    host = config.get("server.host", "0.0.0.0")
    port = int(config.get("server.port", 8000))

    for p in providers:
        p.start()
    tasks = [asyncio.create_task(c) for c in (extra or [])]
    log.info("HUD backend up: http://%s:%s (vehicle source: %s)", host, port, source)

    try:
        async with run_server(app, host, port):
            await stop.wait()
    finally:
        for t in tasks:
            t.cancel()
        for p in providers:
            await p.stop()


async def run(config: Config, source_override: str | None = None) -> None:
    """Headless: backend + settings web server only (no native display)."""
    source = source_override or config.get("providers.vehicle.source", "sim")
    await serve(Bus(), config, source, asyncio.Event())
