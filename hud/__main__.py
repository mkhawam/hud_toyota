"""Entry point.

    python -m hud --ui                  # native display + settings web server
    python -m hud                       # headless backend + settings web server
    python -m hud --ui --source sim     # desktop dev with simulated vehicle
    python -m hud --ui --screenshot out.png   # render, save a frame, exit
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys

from .core.config import Config


def main() -> None:
    parser = argparse.ArgumentParser(prog="hud")
    parser.add_argument("--source", choices=["sim", "auto", "can", "elm327"],
                        help="vehicle data source (overrides config)")
    parser.add_argument("--config", help="path to hud.yaml")
    parser.add_argument("--port", type=int, help="settings web server port (overrides config)")
    parser.add_argument("--ui", action="store_true", help="run the native HUD display")
    parser.add_argument("--size", default=None, help="window size on desktop, e.g. 640x480")
    parser.add_argument("--screenshot", help="save one rendered frame to this path, then exit")
    parser.add_argument("--screenshot-after", type=float, default=4.0, metavar="SECONDS")
    parser.add_argument("--press", help="dev: synthesize key presses after startup, e.g. Return,Down")
    parser.add_argument("--mirror", choices=["on", "off"],
                        help="override config mirroring for this run (not saved) — readable dev view")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")

    config = Config.load(args.config)
    if args.port:
        config.data.setdefault("server", {})["port"] = args.port
    if args.mirror:
        config.data["mirror"] = args.mirror == "on"
    source = args.source or config.get("providers.vehicle.source", "sim")

    if args.ui or args.screenshot:
        from .ui.runner import run_with_ui

        sys.exit(run_with_ui(config, source, size=args.size,
                             screenshot=args.screenshot, screenshot_after=args.screenshot_after,
                             press=args.press))

    from .app import run

    try:
        asyncio.run(run(config, source_override=source))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
