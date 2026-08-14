"""DataProvider base class.

A provider is an async loop that publishes onto the bus. The base class
owns the task lifecycle and crash-restarts with backoff — in a car the
answer to a flaky adapter is always "keep retrying", never "crash the HUD".

Health is itself published on the bus (``provider.<name>.status``) so the
frontend can show per-source indicators.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from .bus import Bus
from .config import Config

log = logging.getLogger(__name__)

RESTART_BACKOFF_S = [1, 2, 5, 10, 30]  # then stays at 30


class DataProvider:
    name = "provider"

    def __init__(self, bus: Bus, config: Config) -> None:
        self.bus = bus
        self.config = config
        self._task: asyncio.Task[None] | None = None

    # -- subclass API ------------------------------------------------------

    async def run(self) -> None:
        """Publish loop. Runs until cancelled; may raise — the supervisor
        restarts it with backoff."""
        raise NotImplementedError

    # -- lifecycle ---------------------------------------------------------

    def start(self) -> None:
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._supervise(), name=f"provider:{self.name}")

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        self._set_status("stopped")

    async def _supervise(self) -> None:
        crashes = 0
        while True:
            self._set_status("starting")
            try:
                self._set_status("up")
                await self.run()
                # run() returning cleanly means the source is done (e.g. a
                # replay file ended) — report and stop supervising.
                self._set_status("stopped")
                return
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001 — keep the HUD alive
                delay = RESTART_BACKOFF_S[min(crashes, len(RESTART_BACKOFF_S) - 1)]
                crashes += 1
                log.exception("provider %s crashed, restarting in %ss", self.name, delay)
                self._set_status("error", detail=str(exc))
                await asyncio.sleep(delay)

    def _set_status(self, status: str, detail: Any = None) -> None:
        self.bus.publish(f"provider.{self.name}.status", {"status": status, "detail": detail})
