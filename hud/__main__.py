"""Entry point: python -m hud [--source sim] [--config path] [--port N]"""

from __future__ import annotations

import argparse
import asyncio
import logging

from .app import run
from .core.config import Config


def main() -> None:
    parser = argparse.ArgumentParser(prog="hud")
    parser.add_argument("--source", choices=["sim", "auto", "can", "elm327"],
                        help="vehicle data source (overrides config)")
    parser.add_argument("--config", help="path to hud.yaml")
    parser.add_argument("--port", type=int, help="HTTP port (overrides config)")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")

    config = Config.load(args.config)
    if args.port:
        config.data.setdefault("server", {})["port"] = args.port

    try:
        asyncio.run(run(config, source_override=args.source))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
