"""FastAPI server: WebSocket stream + config API + static frontend.

WebSocket protocol (server → client), all JSON:
  {"type": "batch", "topics": {"vehicle.rpm": [3200, 1723345.1], ...}}

Bus messages are coalesced into one batch every FLUSH_MS — per topic only
the latest value survives a flush window, so a slow client sees fresh data
rather than a backlog. On connect the client is primed with a snapshot of
every known topic.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from pathlib import Path
from typing import Any

from fastapi import Body, FastAPI, WebSocket, WebSocketDisconnect
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError

from .core.bus import Bus
from .core.config import Config
from .core.settings import SECTIONS

log = logging.getLogger(__name__)

FLUSH_MS = 50
WEB_DIST = Path(__file__).resolve().parents[1] / "web" / "dist"


def create_app(bus: Bus, config: Config) -> FastAPI:
    app = FastAPI(title="hud-toyota")
    started = time.time()

    @app.get("/api/config")
    async def get_config() -> dict:
        return config.data

    @app.post("/api/display")
    async def save_display(values: dict) -> dict:
        """Persist projection calibration (scale/offset) from the frontend."""
        allowed = {}
        for key, lo, hi in (("scale", 0.1, 1.0), ("offset_x", -1.0, 1.0), ("offset_y", -1.0, 1.0)):
            if key in values:
                try:
                    allowed[key] = min(hi, max(lo, float(values[key])))
                except (TypeError, ValueError):
                    pass
        config.save_display(allowed)
        bus.publish("config.updated", {"section": "display"})
        return config.data.get("display", {})

    @app.post("/api/settings/{section:path}")
    async def save_settings(section: str, value: Any = Body(...)) -> JSONResponse:
        """Validated write of one editable config section (phone settings page)."""
        validator = SECTIONS.get(section)
        if validator is None:
            return JSONResponse({"ok": False, "errors": ["unknown section"]}, status_code=404)
        try:
            cleaned = validator(value)
        except (ValidationError, ValueError) as exc:
            errors = exc.errors() if isinstance(exc, ValidationError) else [str(exc)]
            return JSONResponse(
                {"ok": False, "errors": jsonable_encoder(errors)}, status_code=422
            )
        config.save_section(section, cleaned)
        bus.publish("config.updated", {"section": section})
        return JSONResponse({"ok": True, "value": cleaned})

    @app.get("/api/snapshot")
    async def snapshot(pattern: str = "*") -> dict:
        """Bus last-values — lets the settings page read e.g. the GPS fix."""
        return {t: m.value for t, m in bus.snapshot(pattern).items()}

    @app.post("/api/trip/reset")
    async def trip_reset() -> dict:
        bus.publish("trip.reset", {})
        return {"ok": True}

    @app.get("/api/debug")
    async def debug_info() -> dict:
        """Everything the debug views need: uptime + every topic with age."""
        now = time.time()
        return {
            "uptime_s": round(now - started, 1),
            "topics": {
                t: {"value": m.value, "age_s": round(now - m.ts, 1)}
                for t, m in sorted(bus.snapshot().items())
            },
        }

    def _drive_store():
        from .drivelog.store import DriveStore

        return DriveStore(f"{config.get('drivelog.data_dir', 'data')}/drives.db")

    @app.get("/api/drives")
    async def list_drives(limit: int = 50) -> list:
        store = _drive_store()
        try:
            return store.list_drives(limit=min(limit, 200))
        finally:
            store.close()

    @app.get("/api/drives/{drive_id}/samples")
    async def drive_samples(drive_id: int, max_points: int = 500) -> list:
        store = _drive_store()
        try:
            return store.get_samples(drive_id, max_points=min(max_points, 2000))
        finally:
            store.close()

    @app.websocket("/ws")
    async def ws_stream(ws: WebSocket) -> None:
        await ws.accept()
        sub = bus.subscribe("*")
        try:
            # Prime with everything we know, then stream coalesced batches.
            snapshot = {t: [m.value, m.ts] for t, m in bus.snapshot().items()}
            if snapshot:
                await ws.send_json({"type": "batch", "topics": snapshot})

            pending: dict[str, list] = {}
            flush_deadline: float | None = None
            loop = asyncio.get_running_loop()

            while True:
                timeout = None
                if flush_deadline is not None:
                    timeout = max(0.0, flush_deadline - loop.time())
                try:
                    msg = await asyncio.wait_for(sub.__anext__(), timeout=timeout)
                    pending[msg.topic] = [msg.value, msg.ts]
                    if flush_deadline is None:
                        flush_deadline = loop.time() + FLUSH_MS / 1000
                except asyncio.TimeoutError:
                    await ws.send_json({"type": "batch", "topics": pending})
                    pending = {}
                    flush_deadline = None
        except (WebSocketDisconnect, RuntimeError):
            pass  # client went away (page reload, Chromium restart)
        finally:
            bus.unsubscribe(sub)

    # Static frontend (vite build output) — mounted last so /api and /ws win.
    if WEB_DIST.exists():
        app.mount("/", StaticFiles(directory=WEB_DIST, html=True), name="static")
    else:
        @app.get("/")
        async def no_frontend() -> dict:
            return {"hint": "web/dist not found — run `npm run build` in web/, or use the Vite dev server"}

    return app


@contextlib.asynccontextmanager
async def run_server(app: FastAPI, host: str, port: int):
    import uvicorn

    server = uvicorn.Server(uvicorn.Config(app, host=host, port=port, log_level="warning"))
    task = asyncio.create_task(server.serve(), name="uvicorn")
    try:
        yield server
    finally:
        server.should_exit = True
        await task
